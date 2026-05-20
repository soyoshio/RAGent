# Development Guide

> **Target Audience:** Contributors and extension developers
> **Prerequisite:** Read [architecture.md](architecture.md), [interface_contract.md](interface_contract.md), and [data_model.md](data_model.md)

---

## 1. Environment Setup

### 1.1 Quick Start

```bash
# Clone repository
git clone https://github.com/yourname/RAGent.git
cd RAGent

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync

# Activate environment
source .venv/bin/activate

# Verify installation
ragent --help
```

### 1.2 IDE Configuration

Recommended VS Code extensions:
- `ms-python.python`
- `charliermarsh.ruff`
- `ms-python.mypy-type-checker`

Add to `.vscode/settings.json`:

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

## 2. Adding a New Tool

### 2.1 Step-by-Step Tutorial

**Scenario:** Add a `weather_fetch` tool that retrieves current weather for a given city.

#### Step 1: Implement the Tool

Create `src/ragents/tools/weather_fetch.py`:

```python
"""Weather fetch tool implementation."""

import os
import urllib.request
import json
from ragents.schema.skill import SkillLevel
from ragents.utils.logger import logger


class WeatherFetchTool:
    """Fetch current weather for a city."""

    name = "weather_fetch"
    description = "Fetch current weather for a given city. Requires OPENWEATHER_API_KEY."
    parameters = {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name"},
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
            raise ValueError("OPENWEATHER_API_KEY not set")

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

#### Step 2: Register in ToolRegistry

Edit `src/ragents/tools/__init__.py` (or `registry.py`):

```python
from ragents.tools.registry import ToolRegistry
from ragents.tools.weather_fetch import WeatherFetchTool

registry = ToolRegistry()
registry.register(WeatherFetchTool())
```

#### Step 3: Add Tests

Create `tests/unit/test_weather_fetch.py`:

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

#### Step 4: Add Documentation

Add example to `docs/examples/weather_tool.md`:

```markdown
# Weather Tool Example

```bash
# Requires OPENWEATHER_API_KEY in .env
ragent query "What's the weather in Tokyo?"
```
```

---

## 3. Adding a New LLM Provider

### 3.1 Implement Provider Class

Create `src/ragents/llm/custom_provider.py`:

```python
"""Custom LLM provider example."""

from typing import Any
from ragents.llm.base import LLMProvider
from ragents.llm.retry import retry
from ragents.utils.logger import logger


class CustomProvider(LLMProvider):
    """Example provider for a hypothetical API."""

    def __init__(self, api_key: str, base_url: str = "https://api.example.com"):
        self.api_key = api_key
        self.base_url = base_url
        self._name = "custom"

    @property
    def name(self) -> str:
        return self._name

    @retry(max_attempts=3, base_delay=1.0)
    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        logger.info("custom_provider.chat", messages_count=len(messages))
        return "Custom response"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 768 for _ in texts]
```

### 3.2 Register in Factory

Edit `src/ragents/llm/__init__.py`:

```python
from ragents.llm.custom_provider import CustomProvider

PROVIDER_MAP = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "local": LocalProvider,
    "custom": CustomProvider,  # Add here
}

def create_provider(name: str, config: dict) -> LLMProvider:
    provider_cls = PROVIDER_MAP.get(name)
    if not provider_cls:
        raise ConfigError(f"Unknown provider: {name}")
    return provider_cls(**config)
```

---

## 4. Adding a New Retriever

### 4.1 Implement Retriever

Create `src/ragents/rag/hybrid_search.py`:

```python
"""Hybrid search retriever combining dense + sparse signals."""

from ragents.rag.retriever import Retriever
from ragents.schema.retrieval import RetrievedChunk
from ragents.schema.chunk import Chunk


class HybridSearchRetriever(Retriever):
    """Retriever that scores using both vector similarity and BM25."""

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
        return 0.5

    def _keyword_score(self, query: str, chunk: Chunk) -> float:
        return 0.5
```

### 4.2 Register in FusionRetriever

Edit `src/ragents/rag/retriever.py` (FusionRetriever):

```python
from ragents.rag.hybrid_search import HybridSearchRetriever

class FusionRetriever:
    def __init__(self):
        self.retrievers = {
            "vector": VectorRetriever(),
            "keyword": KeywordRetriever(),
            "graph": GraphRetriever(),
            "hybrid": HybridSearchRetriever(),  # Add here
        }
```

---

## 5. Adding a New MCP Server

### 5.1 Configuration

Add to `ragents.toml` (recommended), or use `.env` for environment variable overrides:

```toml
[[mcp.servers]]
name = "postgres"
command = "uvx"
args = ["mcp-server-postgres", "postgresql://localhost/db"]
timeout = 30.0
fallback_tools = ["doc_summary"]
```

### 5.2 Register Fallback Mapping

Edit `src/ragents/mcp/fallback.py`:

```python
FALLBACK_MAP = {
    "postgres": ["doc_summary"],  # When postgres MCP is down, use local tools
}
```

---

## 6. Adding a New Skill

Skill is the task routing extension point in the Agent layer. It does not directly execute tools; instead, it determines tool exposure level and tool whitelist based on query characteristics.

### 6.1 Define Skill Class

Create `src/ragents/skills/frontend_review.py`:

```python
"""Frontend review skill."""

from dataclasses import dataclass
from ragents.schema.skill import SkillConfig, SkillLevel


@dataclass(frozen=True)
class FrontendReviewSkill:
    """Identifies frontend code review queries."""

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

### 6.2 Register in SkillRouter

Edit `src/ragents/agent/skill_router.py`:

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

After registration, `SkillRouter` should only return the skill level and visible tool list; actual execution is still performed by `Executor` through `ToolRegistry.call()`.

### 6.3 Configure Tool Exposure

Add to `ragents.toml`:

```toml
[[skills]]
name = "frontend_review"
level = "intermediate"
enabled = true
tools = ["code_analysis", "cross_reference", "doc_summary"]
```

`tools = []` means expose all tools at this level; explicit lists are useful for restricting high-risk tools like `web_fetch` or file-writing MCP tools.

---

## 7. Code Style

### 7.1 Import Order

```python
# 1. Standard library
import json
from pathlib import Path

# 2. Third-party
import pydantic
from rich.console import Console

# 3. RAGent internal
from ragents.schema.chunk import Chunk
from ragents.utils.logger import logger
```

### 7.2 Type Hints

- All public functions must have type annotations.
- Use `from __future__ import annotations` for forward references.
- Prefer `list[str]` over `List[str]` (Python 3.10+).
- Prefer `str | None` over `Optional[str]`.

### 7.3 Docstrings

Follow Google-style docstrings:

```python
def process_query(query: str, top_k: int = 5) -> list[Chunk]:
    """Process a user query and return relevant chunks.

    Args:
        query: The user's natural language query.
        top_k: Maximum number of chunks to return.

    Returns:
        A list of Chunk objects ordered by relevance.

    Raises:
        RetrievalError: If the index is not available.
    """
```

### 7.4 Error Handling Pattern

```python
from ragents.utils.logger import logger
from ragents.errors import RetrievalError

def retrieve(query: str) -> list[Chunk]:
    try:
        return _do_retrieve(query)
    except IndexError as e:
        logger.error("index_corrupted", query=query, error=str(e))
        raise RetrievalError("Index corrupted. Please rebuild.") from e
```

### 7.5 Logging Standards

- Do not use `print()` for runtime diagnostics; use the project's `structlog` wrapper.
- Error logs must include `error_code`, layer context, and key parameters, but must NOT contain API keys, passwords, or full user privacy data.
- Tool, MCP, and LLM call logs should include latency and retry counts for locating slow calls and cascading failures.

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

## 8. Testing Guidelines

### 8.1 Test Categories

| Category | Location | Scope | External Dependencies |
|----------|----------|-------|----------------------|
| Unit | `tests/unit/` | Single function/class | None (mocked) |
| Integration | `tests/integration/` | Multi-component | Mock expensive APIs by default; real APIs only in dedicated environments |
| Benchmark | `tests/benchmarks/` | Performance / recall | Pre-built test dataset |

### 8.2 Mocking External APIs

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

Add reusable fixtures to `tests/conftest.py`:

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

## 9. Local Debugging Tips

### 9.1 Enable Verbose Logging

```bash
ragent query "Explain useEffect cleanup" --verbose
```

### 9.2 View Agent Execution Trace

```bash
ragent query "Compare useState and useReducer" --show-reasoning
```

### 9.3 Step-by-Step Mode

```bash
ragent query "Generate a React data fetching hook" --step
```

`--show-reasoning` and `--step` are for local development diagnostics only; output should be limited to plans, tool calls, and observation summaries, not model hidden reasoning. Default user-facing output should still hide ReAct intermediate processes.

---

## 10. Release Checklist

If you modify public interfaces or data models, please update the corresponding contract and data model documents under `docs/zh/` (and `docs/en/` if available); if you cannot sync the English version immediately, create an Issue to track it.

Before submitting a PR:

- [ ] Code passes `ruff check src tests`
- [ ] Type checking passes `mypy src`
- [ ] All tests pass `pytest tests/ -v`
- [ ] Benchmark tests pass (recall ≥ 80%, P95 < 500ms)
- [ ] MCP health checks pass (`ragent mcp test`)
- [ ] New code has unit test coverage ≥ 80%
- [ ] Documentation updated (`docs/` and docstrings)
- [ ] `CHANGELOG.md` updated (if exists)
- [ ] `.env.example` updated (if new env vars added)
- [ ] Interface contract docs updated (if public interfaces modified)
- [ ] Data model docs updated (if Pydantic models modified)
