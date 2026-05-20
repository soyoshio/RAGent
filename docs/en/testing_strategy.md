# Testing Strategy

> **Version:** 0.1.0
> **Framework:** pytest
> **Goal:** Fast feedback, reliable CI, measurable quality.

---

## 1. Testing Pyramid

```
        /\
       /  \     E2E / Benchmark (slow, few)
      /----\
     /      \   Integration (medium speed, medium count)
    /--------\
   /          \ Unit (fast, many)
  /------------\
```

| Layer | Count Target | Execution Time | Failure Signal |
|-------|-------------|----------------|----------------|
| Unit | ~80% of tests | < 1s per test | Logic bug in module |
| Integration | ~15% of tests | < 10s per test | Interface mismatch |
| Benchmark | ~5% of tests | Minutes | Performance regression |

---

## 2. Unit Testing

### 2.1 Principles

1. **No I/O** — All external calls (LLM, filesystem, network) must be mocked.
2. **One assertion concept per test** — Test one behavior, not one function.
3. **Deterministic** — Same input → same output, always.

### 2.2 Directory Structure

```
tests/unit/
├── __init__.py
├── test_chunker.py           # Chunker strategies
├── test_skill_router.py      # Skill level detection
├── test_schema.py            # Pydantic validation
├── test_retriever.py         # Individual retrievers
├── test_reranker.py          # Reranker scoring
├── test_embedder.py          # Embedding shapes / errors
├── test_tool_registry.py     # Tool registration & discovery
├── test_retry.py             # Exponential backoff logic
└── test_validators.py        # Input validation
```

### 2.3 Example: Testing Chunker

```python
# tests/unit/test_chunker.py
import pytest
from ragents.rag.chunker import MarkdownChunker
from ragents.schema.chunk import ChunkMeta


class TestMarkdownChunker:
    def test_splits_by_heading(self):
        text = "# Intro\nHello\n## Details\nWorld"
        chunker = MarkdownChunker()
        chunks = chunker.chunk(text, source="test.md")

        assert len(chunks) == 2
        assert chunks[0].text == "# Intro\nHello"
        assert chunks[1].meta.extra["heading"] == "## Details"

    def test_preserves_source(self):
        chunker = MarkdownChunker()
        chunks = chunker.chunk("# A\nB", source="doc.md")
        assert all(c.meta.source == "doc.md" for c in chunks)

    def test_empty_text_raises(self):
        chunker = MarkdownChunker()
        with pytest.raises(ValueError, match="non-empty"):
            chunker.chunk("", source="empty.md")
```

### 2.4 Example: Testing Retry Logic

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


class TestCircuitBreaker:
    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=2)

        def fail():
            raise Exception("boom")

        cb.call(fail)  # fail 1
        cb.call(fail)  # fail 2

        with pytest.raises(Exception, match="Circuit breaker is open"):
            cb.call(fail)  # fail 3 - circuit open
```

---

## 3. Integration Testing

### 3.1 Principles

1. **Test component interaction** — Focus on data flow between layers.
2. **Use real implementations where cheap** — e.g., real `Chunker` + mock `LLM`.
3. **Mock expensive I/O** — LLM APIs, web requests, MCP servers.

### 3.2 Directory Structure

```
tests/integration/
├── __init__.py
├── test_mcp_mock.py           # Mock MCP server lifecycle
├── test_rag_pipeline.py       # End-to-end RAG (chunk → embed → retrieve → rerank)
├── test_agent_flow.py         # Planner → Executor → Synthesis
└── test_cli_commands.py       # CLI argument parsing + exit codes
```

### 3.3 Example: Mock MCP Server

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
        time.sleep(5)  # Exceeds timeout
```

### 3.4 Example: RAG Pipeline

```python
# tests/integration/test_rag_pipeline.py
import pytest
from ragents.rag.chunker import MarkdownChunker
from ragents.rag.retriever import VectorRetriever
from ragents.schema.chunk import ChunkMeta


class TestRAGPipeline:
    def test_end_to_end_retrieval(self):
        # 1. Chunk
        text = "# React\nReact is a library.\n# Hooks\nHooks are functions."
        chunker = MarkdownChunker()
        chunks = chunker.chunk(text, source="react.md")

        # 2. Embed (mock)
        embedder = MockEmbedder()
        vectors = embedder.embed([c.text for c in chunks])

        # 3. Index
        retriever = VectorRetriever(embedder=embedder)
        for chunk, vector in zip(chunks, vectors):
            retriever.add(chunk, vector)

        # 4. Retrieve
        query_vec = embedder.embed(["What are Hooks?"])[0]
        results = retriever.retrieve_by_vector(query_vec, top_k=2)

        assert len(results) > 0
        assert any("Hooks" in r.chunk.text for r in results)
```

---

## 4. Benchmark Testing

### 4.1 Retrieval Recall Benchmark

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
        from ragents.rag.retriever import FusionRetriever
        retriever = FusionRetriever()
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
        assert avg_recall >= 0.8, f"Average recall {avg_recall} below threshold"

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
        assert p95 < 500, f"P95 latency {p95}ms exceeds 500ms budget"
```

### 4.2 Benchmark Data Format

```json
[
  {
    "query": "How does useEffect work?",
    "expected_ids": ["react_hooks_guide.md#2"],
    "difficulty": "easy"
  },
  {
    "query": "Compare useState and useReducer with code examples",
    "expected_ids": ["react_hooks_guide.md#1", "react_hooks_guide.md#4"],
    "difficulty": "medium"
  }
]
```

---

## 5. Test Configuration

### 5.1 pytest.ini (or pyproject.toml)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "benchmark: marks tests as benchmarks (run separately)",
    "integration: marks tests as integration tests",
]
addopts = "-v --tb=short"
```

### 5.2 Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run only unit tests
uv run pytest tests/unit -v

# Run integration tests
uv run pytest tests/integration -v

# Run benchmarks
uv run pytest tests/benchmarks -v --benchmark-only

# Exclude slow tests
uv run pytest tests/ -v -m "not slow"

# With coverage
uv run pytest tests/ --cov=ragents --cov-report=html
```

---

## 6. CI Integration

```yaml
# .github/workflows/ci.yml (relevant section)
- name: Run tests
  run: |
    uv run pytest tests/unit -v
    uv run pytest tests/integration -v

- name: Run benchmarks (on main only)
  if: github.ref == 'refs/heads/main'
  run: uv run pytest tests/benchmarks -v
```

---

## 7. Quality Gates

| Gate | Requirement | Tool |
|------|-------------|------|
| Lint | Zero ruff errors | `ruff check src tests` |
| Type Check | Zero mypy errors in `src/` | `mypy src` |
| Unit Tests | 100% pass | `pytest tests/unit` |
| Coverage | ≥ 80% line coverage | `pytest --cov` |
| Integration | 100% pass | `pytest tests/integration` |
| Benchmark | Recall ≥ 80%, P95 < 500ms | `pytest tests/benchmarks` |
