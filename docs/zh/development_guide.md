# 开发指南

> **目标读者：** 贡献者与扩展开发者
> **前置条件：** 已阅读 [architecture.md](architecture.md)、[interface_contract.md](interface_contract.md) 和 [data_model.md](data_model.md)

---

## 1. 环境搭建

### 1.1 快速开始

```bash
# 克隆代码仓库
git clone https://github.com/yourname/RAGent.git
cd RAGent

# 安装 uv（若尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
uv sync

# 激活环境
source .venv/bin/activate

# 验证安装
ragent --help
```

### 1.2 IDE 配置

推荐的 VS Code 扩展：
- `ms-python.python`
- `charliermarsh.ruff`
- `ms-python.mypy-type-checker`

添加到 `.vscode/settings.json`：

```json
{
  "python.defaultInterpreterPath": "./.venv/bin/python",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.ruff": "explicit"
  }
}
```

---

## 2. 添加新工具

### 2.1 逐步教程

**场景：** 添加一个 `weather_fetch` 工具，用于获取指定城市的当前天气。

#### 步骤 1：实现工具

创建 `src/ragents/tools/weather_fetch.py`：

```python
"""天气查询工具实现。"""

import os
import urllib.request
import json
from ragents.schema.skill import SkillLevel
from ragents.utils.logger import logger


class WeatherFetchTool:
    """获取指定城市的当前天气。"""

    name = "weather_fetch"
    description = "获取指定城市的当前天气。需要配置 OPENWEATHER_API_KEY。"
    parameters = {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名称"},
            "units": {
                "type": "string",
                "enum": ["metric", "imperial"],
                "default": "metric"
            }
        },
        "required": ["city"]
    }
    skill_level = SkillLevel.INTERMEDIATE

    def __call__(self, city: str, units: str = "metric") -> dict:
        api_key = os.environ.get("OPENWEATHER_API_KEY")
        if not api_key:
            raise ValueError("未设置 OPENWEATHER_API_KEY")

        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={city}&units={units}&appid={api_key}"
        )

        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())

        return {
            "city": city,
            "temperature": data["main"]["temp"],
            "humidity": data["main"]["humidity"],
            "description": data["weather"][0]["description"],
        }
```

#### 步骤 2：注册到 ToolRegistry

编辑 `src/ragents/tools/__init__.py`（或 `registry.py`）：

```python
from ragents.tools.registry import ToolRegistry
from ragents.tools.weather_fetch import WeatherFetchTool

registry = ToolRegistry()
registry.register(WeatherFetchTool())
```

#### 步骤 3：添加测试

创建 `tests/unit/test_weather_fetch.py`：

```python
import json
import pytest
import urllib.error
from unittest.mock import patch, MagicMock
from ragents.tools.weather_fetch import WeatherFetchTool


@patch("ragents.tools.weather_fetch.urllib.request.urlopen")
@patch.dict("os.environ", {"OPENWEATHER_API_KEY": "test-key"})
def test_weather_fetch_success(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"main":{"temp":25,"humidity":60},"weather":[{"description":"clear sky"}]}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = WeatherFetchTool()("Beijing")
    assert result["temperature"] == 25
    assert result["city"] == "Beijing"


def test_weather_fetch_missing_key():
    with pytest.raises(ValueError, match="OPENWEATHER_API_KEY"):
        WeatherFetchTool()("Beijing")


@patch("ragents.tools.weather_fetch.urllib.request.urlopen")
@patch.dict("os.environ", {"OPENWEATHER_API_KEY": "test-key"})
def test_weather_fetch_api_error(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.HTTPError(
        url="https://api.example.test",
        code=500,
        msg="server error",
        hdrs=None,
        fp=None,
    )

    with pytest.raises(urllib.error.HTTPError):
        WeatherFetchTool()("Beijing")


@patch("ragents.tools.weather_fetch.urllib.request.urlopen")
@patch.dict("os.environ", {"OPENWEATHER_API_KEY": "test-key"})
def test_weather_fetch_malformed_response(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"main":'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    with pytest.raises(json.JSONDecodeError):
        WeatherFetchTool()("Beijing")


@patch("ragents.tools.weather_fetch.urllib.request.urlopen")
@patch.dict("os.environ", {"OPENWEATHER_API_KEY": "test-key"})
def test_weather_fetch_timeout(mock_urlopen):
    mock_urlopen.side_effect = TimeoutError("timed out")

    with pytest.raises(TimeoutError):
        WeatherFetchTool()("Beijing")
```

#### 步骤 4：添加文档

在 `docs/examples/weather_tool.md` 中添加示例：

```markdown
# 天气工具示例

```bash
# 需要先在 .env 中配置 OPENWEATHER_API_KEY
ragent query "东京现在的天气如何？"
```
```

---

## 3. 添加新 LLM Provider

### 3.1 实现 Provider 类

创建 `src/ragents/llm/custom_provider.py`：

```python
"""自定义 LLM Provider 示例。"""

from typing import Any
from ragents.llm.base import LLMProvider
from ragents.llm.retry import retry
from ragents.utils.logger import logger


class CustomProvider(LLMProvider):
    """某假设 API 的 Provider 示例。"""

    def __init__(self, api_key: str, base_url: str = "https://api.example.com"):
        self.api_key = api_key
        self.base_url = base_url
        self._name = "custom"

    @property
    def name(self) -> str:
        return self._name

    @retry(max_attempts=3, base_delay=1.0)
    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        # 具体实现：构造请求、调用 API、解析响应
        logger.info("custom_provider.chat", messages_count=len(messages))
        return "Custom response"

    def embed(self, texts: list[str]) -> list[list[float]]:
        # 具体实现
        return [[0.0] * 768 for _ in texts]
```

### 3.2 注册到工厂

编辑 `src/ragents/llm/__init__.py`：

```python
from ragents.llm.custom_provider import CustomProvider

PROVIDER_MAP = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "local": LocalProvider,
    "custom": CustomProvider,  # 在此处添加
}

def create_provider(name: str, config: dict) -> LLMProvider:
    provider_cls = PROVIDER_MAP.get(name)
    if not provider_cls:
        raise ConfigError(f"未知 Provider: {name}")
    return provider_cls(**config)
```

---

## 4. 添加新检索器

### 4.1 实现检索器

创建 `src/ragents/rag/hybrid_search.py`：

```python
"""结合稠密信号与稀疏信号的混合检索器。"""

from ragents.rag.retriever import Retriever
from ragents.schema.retrieval import RetrievedChunk
from ragents.schema.chunk import Chunk


class HybridSearchRetriever(Retriever):
    """同时使用向量相似度和 BM25 评分的检索器。"""

    def __init__(self, vector_weight: float = 0.7, keyword_weight: float = 0.3):
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self._index = []

    def add(self, chunks: list[Chunk]) -> None:
        self._index.extend(chunks)

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        results = []
        for chunk in self._index:
            v_score = self._vector_score(query, chunk)
            k_score = self._keyword_score(query, chunk)
            combined = self.vector_weight * v_score + self.keyword_weight * k_score
            results.append(RetrievedChunk(chunk=chunk, score=combined))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def _vector_score(self, query: str, chunk: Chunk) -> float:
        # 占位实现
        return 0.5

    def _keyword_score(self, query: str, chunk: Chunk) -> float:
        # 占位实现
        return 0.5
```

### 4.2 注册到 FusionRetriever

编辑 `src/ragents/rag/retriever.py`（FusionRetriever）：

```python
from ragents.rag.hybrid_search import HybridSearchRetriever

class FusionRetriever:
    def __init__(self):
        self.retrievers = {
            "vector": VectorRetriever(),
            "keyword": KeywordRetriever(),
            "graph": GraphRetriever(),
            "hybrid": HybridSearchRetriever(),  # 在此处添加
        }
```

---

## 5. 添加新 MCP Server

### 5.1 配置

在 `ragents.toml` 配置文件中添加（推荐），或在 `.env` 中设置环境变量覆盖：

```toml
[[mcp.servers]]
name = "postgres"
command = "uvx"
args = ["mcp-server-postgres", "postgresql://localhost/db"]
timeout = 30.0
fallback_tools = ["doc_summary"]
```

### 5.2 注册降级映射

编辑 `src/ragents/mcp/fallback.py`：

```python
FALLBACK_MAP = {
    "postgres": ["doc_summary"],  # 当 postgres MCP 不可用时，使用本地工具降级
}
```

---

## 6. 添加新 Skill

Skill 是 Agent 层的任务路由扩展点。它不直接执行工具，而是根据查询特征决定工具暴露等级和工具白名单。

### 6.1 定义 Skill 类

创建 `src/ragents/skills/frontend_review.py`：

```python
"""前端审查 Skill。"""

from dataclasses import dataclass
from ragents.schema.skill import SkillConfig, SkillLevel


@dataclass(frozen=True)
class FrontendReviewSkill:
    """识别前端代码审查类查询。"""

    name: str = "frontend_review"
    level: SkillLevel = SkillLevel.INTERMEDIATE
    tools: tuple[str, ...] = ("code_analysis", "cross_reference", "doc_summary")
    keywords: tuple[str, ...] = ("react", "component", "css", "hook", "bug")

    def matches(self, query: str) -> bool:
        text = query.lower()
        return any(keyword in text for keyword in self.keywords)

    def to_config(self) -> SkillConfig:
        return SkillConfig(
            name=self.name,
            level=self.level,
            enabled=True,
            tools=list(self.tools),
        )
```

### 6.2 注册到 SkillRouter

编辑 `src/ragents/agent/skill_router.py`：

```python
from ragents.skills.frontend_review import FrontendReviewSkill

DEFAULT_SKILLS = (
    FrontendReviewSkill(),
)

class SkillRouter:
    def __init__(self, skills=DEFAULT_SKILLS):
        self.skills = list(skills)

    def register(self, skill) -> None:
        self.skills.append(skill)

    def route(self, query: str):
        for skill in self.skills:
            if skill.matches(query):
                return skill.to_config()
        return None
```

注册后，`SkillRouter` 应只返回技能等级和可见工具清单；实际执行仍由 `Executor` 通过 `ToolRegistry.call()` 完成。

### 6.3 配置工具暴露列表

在 `ragents.toml` 中添加：

```toml
[[skills]]
name = "frontend_review"
level = "intermediate"
enabled = true
tools = ["code_analysis", "cross_reference", "doc_summary"]
```

`tools = []` 表示暴露该等级下所有工具；显式列表适合限制高风险工具，例如 `web_fetch` 或会写文件的 MCP 工具。

---

## 7. 代码规范

### 7.1 导入顺序

```python
# 1. 标准库
import json
from pathlib import Path

# 2. 第三方库
import pydantic
from rich.console import Console

# 3. RAGent 内部模块
from ragents.schema.chunk import Chunk
from ragents.utils.logger import logger
```

### 7.2 类型注解

- 所有公共函数必须有类型注解。
- 使用 `from __future__ import annotations` 处理前向引用。
- 优先使用 `list[str]` 而非 `List[str]`（Python 3.10+）。
- 优先使用 `str | None` 而非 `Optional[str]`。

### 7.3 文档字符串

遵循 Google 风格文档字符串：

```python
def process_query(query: str, top_k: int = 5) -> list[Chunk]:
    """处理用户查询并返回相关分块。

    参数：
        query: 用户的自然语言查询。
        top_k: 返回的最大分块数量。

    返回：
        按相关性排序的 Chunk 对象列表。

    抛出：
        RetrievalError: 索引不可用时抛出。
    """
```

### 7.4 错误处理模式

```python
from ragents.utils.logger import logger
from ragents.errors import RetrievalError

def retrieve(query: str) -> list[Chunk]:
    try:
        return _do_retrieve(query)
    except IndexError as e:
        logger.error("index_corrupted", query=query, error=str(e))
        raise RetrievalError("索引已损坏，请重建。") from e
```

### 7.5 日志规范

- 禁止使用 `print()` 输出运行时诊断信息，统一使用 `structlog` 封装的项目 logger。
- 错误日志必须包含 `error_code`、层级上下文和关键参数，但不得包含 API Key、密码或完整用户隐私数据。
- 工具、MCP、LLM 调用日志应包含延迟和重试次数，便于定位慢调用和级联故障。

```python
logger.error(
    "tool_failed",
    tool="weather_fetch",
    error_code="TOOL_TIMEOUT",
    city=city,
    latency_ms=10_000,
)
```

---

## 8. 测试指南

### 8.1 测试分类

| 类别 | 位置 | 范围 | 外部依赖 |
|------|------|------|----------|
| 单元测试 | `tests/unit/` | 单个函数/类 | 无（全部 mock） |
| 集成测试 | `tests/integration/` | 多组件交互 | 默认 mock 昂贵 API；仅在专用环境中启用真实依赖 |
| 基准测试 | `tests/benchmarks/` | 性能 / 召回率 | 预构建测试数据集 |

### 8.2 Mock 外部 API

```python
from unittest.mock import patch, MagicMock

@patch("ragents.llm.openai_provider.urllib.request.urlopen")
def test_openai_chat(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"choices": [{"message": {"content": "Hello"}}]}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    provider = OpenAIProvider(api_key="test")
    result = provider.chat([{"role": "user", "content": "Hi"}])
    assert result == "Hello"
```

### 8.3 Fixtures

在 `tests/conftest.py` 中添加可复用的 fixtures：

```python
import pytest
from ragents.schema.chunk import Chunk, ChunkMeta

@pytest.fixture
def sample_chunk():
    return Chunk(
        id="test#1",
        text="def hello(): return 'world'",
        meta=ChunkMeta(source="test.py", start_line=1, end_line=2),
    )

@pytest.fixture
def mock_llm_provider():
    from unittest.mock import MagicMock
    provider = MagicMock()
    provider.chat.return_value = "Mock response"
    provider.embed.return_value = [[0.0] * 768]
    return provider
```

---

## 9. 本地调试技巧

### 9.1 开启详细日志

```bash
ragent query "解释 useEffect cleanup" --verbose
```

### 9.2 查看 Agent 执行轨迹

```bash
ragent query "比较 useState 和 useReducer" --show-reasoning
```

### 9.3 单步执行模式

```bash
ragent query "生成一个 React 数据获取 Hook" --step
```

`--show-reasoning` 和 `--step` 只用于本地开发诊断；输出应限于计划、工具调用和 Observation 摘要，不展示模型隐藏推理。面向普通用户的默认输出仍应隐藏 ReAct 中间过程。

---

## 10. 发布检查清单

若修改了公共接口或数据模型，请同步更新 `docs/zh/` 下对应的契约文档和数据模型文档，并确保英文版 `docs/en/` 同步更新；若暂时无法同步英文版，至少创建 Issue 跟踪。

提交 PR 前请完成以下检查：

- [ ] 代码通过 `ruff check src tests`
- [ ] 类型检查通过 `mypy src`
- [ ] 所有测试通过 `pytest tests/ -v`
- [ ] 基准测试通过（recall ≥ 80%，P95 < 500ms）
- [ ] MCP 健康检查通过（`ragent mcp test`）
- [ ] 新增代码的单元测试覆盖率 ≥ 80%
- [ ] 文档已更新（`docs/` 目录和文档字符串）
- [ ] `CHANGELOG.md` 已更新（若存在）
- [ ] `.env.example` 已更新（若新增环境变量）
- [ ] 接口契约文档已更新（若修改公共接口）
- [ ] 数据模型文档已更新（若修改 Pydantic 模型）
