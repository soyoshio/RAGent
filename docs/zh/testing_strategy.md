# 测试策略

> **版本：** 0.1.0
> **测试框架：** pytest
> **目标：** 快速反馈、可靠的 CI、可量化的质量。

---

## 1. 测试金字塔

```
        /\
       /  \     端到端 / 基准测试（慢，数量少）
      /----\
     /      \   集成测试（中等速度，中等数量）
    /--------\
   /          \ 单元测试（快，数量多）
  /------------\
```

| 层级 | 目标占比 | 执行时间 | 失败信号 |
|------|---------|----------|----------|
| 单元测试 | ~80% | < 1 秒 / 测试 | 模块内逻辑错误 |
| 集成测试 | ~15% | < 10 秒 / 测试 | 组件间接口不匹配 |
| 基准测试 | ~5% | 分钟级 | 性能回归 |

---

## 2. 单元测试

### 2.1 原则

1. **无 I/O** — 所有外部调用（LLM、文件系统、网络）必须被 mock。单元测试应当完全在内存中运行。
2. **每个测试一个行为** — 测试一个行为，而非一个函数。一个函数可以有多个测试用例，覆盖不同分支。
3. **确定性** — 相同输入总是产生相同输出。避免依赖时间、随机数、全局状态（除非显式 mock）。
4. **快速执行** — 单个单元测试应在毫秒级完成，整个单元测试套件应在 10 秒内跑完。

### 2.2 目录结构

```
tests/unit/
├── __init__.py
├── test_chunker.py           # 分块器策略
├── test_skill_router.py      # 技能等级检测
├── test_schema.py            # Pydantic 校验
├── test_retriever.py         # 单个检索器
├── test_reranker.py          # 重排序器打分
├── test_embedder.py          # 嵌入形状 / 错误
├── test_tool_registry.py     # 工具注册与发现
├── test_retry.py             # 指数退避逻辑
├── test_circuit_breaker.py   # 熔断器状态机
└── test_validators.py        # 输入校验
```

### 2.3 示例：测试分块器

```python
# tests/unit/test_chunker.py
import pytest
from ragents.rag.chunker import MarkdownChunker
from ragents.schema.chunk import ChunkMeta


class TestMarkdownChunker:
    def test_splits_by_heading(self):
        text = "# 简介\n你好\n## 详情\n世界"
        chunker = MarkdownChunker()
        chunks = chunker.chunk(text, source="test.md")

        assert len(chunks) == 2
        assert chunks[0].text == "# 简介\n你好"
        assert chunks[1].meta.extra["heading"] == "## 详情"

    def test_preserves_source(self):
        chunker = MarkdownChunker()
        chunks = chunker.chunk("# A\nB", source="doc.md")
        assert all(c.meta.source == "doc.md" for c in chunks)

    def test_empty_text_raises(self):
        chunker = MarkdownChunker()
        with pytest.raises(ValueError, match="非空"):
            chunker.chunk("", source="empty.md")

    def test_meta_line_numbers(self):
        text = "line1\nline2\nline3"
        chunker = MarkdownChunker()
        chunks = chunker.chunk(text, source="test.md")
        assert chunks[0].meta.start_line == 1
        assert chunks[0].meta.end_line == 3
```

### 2.4 示例：测试重试逻辑

```python
# tests/unit/test_retry.py
import pytest
from unittest.mock import MagicMock
from ragents.llm.retry import retry, CircuitBreaker


class TestRetry:
    def test_succeeds_on_first_attempt(self):
        @retry(max_attempts=3)
        def always_works():
            return "ok"

        assert always_works() == "ok"

    def test_retries_then_succeeds(self):
        mock = MagicMock(side_effect=[Exception("fail"), "ok"])

        @retry(max_attempts=3)
        def sometimes_works():
            return mock()

        assert sometimes_works() == "ok"
        assert mock.call_count == 2

    def test_raises_after_max_attempts(self):
        @retry(max_attempts=2)
        def always_fails():
            raise ConnectionError("timeout")

        with pytest.raises(ConnectionError):
            always_fails()

    def test_respects_non_retryable_exceptions(self):
        @retry(max_attempts=3, retryable_exceptions=(ConnectionError,))
        def auth_fails():
            raise ValueError("invalid auth")

        with pytest.raises(ValueError):
            auth_fails()


class TestCircuitBreaker:
    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=2)

        def fail():
            raise Exception("boom")

        cb.call(fail)  # 失败 1
        cb.call(fail)  # 失败 2

        with pytest.raises(Exception, match="熔断器已打开"):
            cb.call(fail)  # 失败 3 — 熔断器已打开

    def test_closes_after_probe_success(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        import time
        time.sleep(0.15)
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == "closed"
```

---

## 3. 集成测试

### 3.1 原则

1. **测试组件交互** — 关注层与层之间的数据流，而非单个函数的内部逻辑。
2. **低成本时使用真实实现** — 例如真实的 `Chunker` + mock `LLM`。尽量在集成测试中保留真实的数据转换层。
3. **mock 昂贵的 I/O** — LLM API、网络请求、MCP 服务器等必须 mock，避免 flaky 测试和费用。

### 3.2 目录结构

```
tests/integration/
├── __init__.py
├── test_mcp_mock.py           # Mock MCP 服务器生命周期
├── test_rag_pipeline.py       # 端到端 RAG（分块 → 嵌入 → 检索 → 重排序）
├── test_agent_flow.py         # 规划器 → 执行器 → 综合器
└── test_cli_commands.py       # CLI 参数解析 + 退出码
```

### 3.3 示例：Mock MCP 服务器

```python
# tests/integration/test_mcp_mock.py
import pytest
import subprocess
import time
from ragents.mcp.client_pool import ClientPool
from ragents.mcp.server_manager import ServerManager


class TestMCPServerLifecycle:
    def test_server_start_stop(self):
        manager = ServerManager()
        config = {
            "name": "test-echo",
            "command": "python",
            "args": ["-c", "print('MCP server ready')"],
            "enabled": True,
        }

        manager.start("test-echo", config)
        assert "test-echo" in manager._servers

        manager.stop("test-echo")
        assert "test-echo" not in manager._servers

    def test_health_check_marks_degraded(self):
        pool = ClientPool()
        pool.register("slow-server", SlowMockClient())

        status = pool.health_check("slow-server")
        assert status == "degraded"


class SlowMockClient:
    def ping(self):
        time.sleep(5)  # 超出超时阈值

    def list_tools(self):
        return []
```

### 3.4 示例：RAG 流水线

```python
# tests/integration/test_rag_pipeline.py
import pytest
from ragents.rag.chunker import MarkdownChunker
from ragents.rag.embedder import Embedder
from ragents.rag.retriever import VectorRetriever
from ragents.schema.chunk import ChunkMeta


class MockEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        # 简单的 mock：文本长度作为向量的第一维
        return [[float(len(t))] + [0.0] * 767 for t in texts]

    def dimension(self) -> int:
        return 768


class TestRAGPipeline:
    def test_end_to_end_retrieval(self):
        # 1. 分块
        text = "# React\nReact 是一个库。\n# Hooks\nHooks 是函数。"
        chunker = MarkdownChunker()
        chunks = chunker.chunk(text, source="react.md")

        # 2. 嵌入器（mock）
        embedder = MockEmbedder()

        # 3. 建索引
        retriever = VectorRetriever(embedder=embedder)
        retriever.add(chunks)

        # 4. 检索
        results = retriever.retrieve("Hooks 是什么？", top_k=2)

        assert len(results) > 0
        assert any("Hooks" in r.chunk.text for r in results)
```

---

## 4. 基准测试

### 4.1 检索召回率基准

```python
# tests/benchmarks/test_retrieval_recall.py
import json
import pytest
from pathlib import Path

BENCHMARK_DATA = Path(__file__).with_name("data") / "benchmark_queries.json"


@pytest.mark.benchmark
class TestRetrievalRecall:
    @pytest.fixture(scope="class")
    def index(self):
        """构建或加载测试索引。"""
        from ragents.rag.retriever import FusionRetriever
        retriever = FusionRetriever()
        # 加载示例文档...
        return retriever

    def test_recall_at_k(self, index):
        queries = json.loads(BENCHMARK_DATA.read_text())

        recalls = []
        for item in queries:
            results = index.retrieve(item["query"], top_k=5)
            result_ids = {r.chunk.id for r in results}
            expected = set(item["expected_ids"])

            hit = len(expected & result_ids) / len(expected)
            recalls.append(hit)

        avg_recall = sum(recalls) / len(recalls)
        assert avg_recall >= 0.8, f"平均召回率 {avg_recall} 低于阈值"

    def test_latency_p95(self, index):
        import time
        queries = json.loads(BENCHMARK_DATA.read_text())

        latencies = []
        for item in queries:
            start = time.perf_counter()
            index.retrieve(item["query"], top_k=5)
            latencies.append((time.perf_counter() - start) * 1000)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        assert p95 < 500, f"P95 延迟 {p95}ms 超出 500ms 预算"
```

### 4.2 基准数据格式

```json
[
  {
    "query": "useEffect 是如何工作的？",
    "expected_ids": ["react_hooks_guide.md#2"],
    "difficulty": "easy"
  },
  {
    "query": "用代码示例比较 useState 和 useReducer",
    "expected_ids": ["react_hooks_guide.md#1", "react_hooks_guide.md#4"],
    "difficulty": "medium"
  }
]
```

---

## 5. 测试配置

### 5.1 pytest.ini（或 pyproject.toml）

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "slow: 标记为慢速测试（可用 '-m \"not slow\"' 排除）",
    "benchmark: 标记为基准测试（单独运行）",
    "integration: 标记为集成测试",
]
addopts = "-v --tb=short"
```

### 5.2 运行测试

```bash
# 运行全部测试
uv run pytest tests/ -v

# 仅运行单元测试
uv run pytest tests/unit -v

# 运行集成测试
uv run pytest tests/integration -v

# 运行基准测试
uv run pytest tests/benchmarks -v --benchmark-only

# 排除慢速测试
uv run pytest tests/ -v -m "not slow"

# 带覆盖率报告
uv run pytest tests/ --cov=ragents --cov-report=html

# 仅运行失败的测试
uv run pytest tests/ --lf -v
```

---

## 6. CI 集成

```yaml
# .github/workflows/ci.yml（相关片段）
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v1

      - name: 运行单元测试
        run: uv run pytest tests/unit -v

      - name: 运行集成测试
        run: uv run pytest tests/integration -v

      - name: 运行基准测试（仅 main 分支）
        if: github.ref == 'refs/heads/main'
        run: uv run pytest tests/benchmarks -v

      - name: 生成覆盖率报告
        run: uv run pytest tests/ --cov=ragents --cov-report=xml

      - name: 上传覆盖率
        uses: codecov/codecov-action@v3
```

---

## 7. 质量门禁

| 门禁 | 要求 | 工具 |
|------|------|------|
| 代码风格 | 零 ruff 错误 | `ruff check src tests` |
| 类型检查 | `src/` 目录零 mypy 错误 | `mypy src` |
| 单元测试 | 100% 通过 | `pytest tests/unit` |
| 覆盖率 | 行覆盖率 ≥ 80% | `pytest --cov` |
| 集成测试 | 100% 通过 | `pytest tests/integration` |
| 基准测试 | 召回率 ≥ 80%，P95 < 500ms | `pytest tests/benchmarks` |

---

## 8. 测试最佳实践

1. **使用参数化测试减少重复** — 对于多组输入输出相似的测试，使用 `@pytest.mark.parametrize`。
2. **Fixture 优先于 setup/teardown** — 利用 pytest fixture 的依赖注入和作用域管理。
3. **隔离测试状态** — 每个测试结束后清理全局状态，避免测试间互相影响。
4. **有意义的测试名称** — 测试函数名应描述行为，如 `test_raises_error_when_index_corrupted`。
5. **断言信息丰富** — 在复杂断言中提供自定义消息，帮助快速定位失败原因。
