# Data Model Specification

> **Version:** 0.1.0
> **Schema Engine:** Pydantic v2
> **Validation Strategy:** Strict mode with custom validators for URI patterns and identifier formats.

---

## 1. Chunk Layer

### 1.1 ChunkMeta

Metadata attached to every chunk. Represents provenance and positional information.

```python
class ChunkMeta(BaseModel):
    source: str
    start_line: int | None = None
    end_line: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
```

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `source` | `str` | Yes | Must be valid URI or absolute path. | Document origin. |
| `start_line` | `int \| None` | No | `>= 1` if present. | 1-based inclusive start line. |
| `end_line` | `int \| None` | No | `>= start_line` if both present. | 1-based inclusive end line. |
| `extra` | `dict` | No | Max depth 3; values must be JSON-serializable. | Free-form metadata (e.g., `{"heading": "## Intro"}`). |

**Validation Rule:**
```
IF start_line IS NOT None AND end_line IS NOT None:
    ASSERT end_line >= start_line
    FAIL WITH: "end_line must be >= start_line"
```

---

### 1.2 Chunk

Atomic unit of retrieval and generation context.

```python
class Chunk(BaseModel):
    id: str
    text: str
    meta: ChunkMeta
```

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `id` | `str` | Yes | Pattern: `^[a-zA-Z0-9_\-\.]+#[0-9]+$`. Must be unique within index. | Stable identifier. |
| `text` | `str` | Yes | Non-empty after strip. Max length: 10000 chars (configurable). | Raw chunk content. |
| `meta` | `ChunkMeta` | Yes | — | Provenance metadata. |

**Example:**
```json
{
  "id": "react_hooks_guide.md#3",
  "text": "useEffect is used for side effects in functional components.",
  "meta": {
    "source": "examples/react_hooks_guide.md",
    "start_line": 15,
    "end_line": 17,
    "extra": {"heading": "## useEffect"}
  }
}
```

---

### 1.3 Document

Collection of chunks derived from a single source file.

```python
class Document(BaseModel):
    id: str
    chunks: list[Chunk]
```

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `id` | `str` | Yes | Same pattern as `Chunk.id` without `#` suffix. | Source document identifier. |
| `chunks` | `list[Chunk]` | Yes | Non-empty. All chunks must have consistent `meta.source`. | Ordered list of chunks. |

---

## 2. Retrieval Layer

### 2.1 RetrievedChunk

A chunk enriched with relevance score from a retriever.

```python
class RetrievedChunk(BaseModel):
    chunk: Chunk
    score: float
```

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `chunk` | `Chunk` | Yes | — | The retrieved chunk. |
| `score` | `float` | Yes | Typically in `[0.0, 1.0]`, but retriever-dependent. | Relevance score (higher = more relevant). |

**Normalization Rule:**  
Different retrievers produce scores in different ranges (cosine similarity `[-1, 1]`, BM25 unbounded, etc.). The `FusionRetriever` applies **Reciprocal Rank Fusion (RRF)** directly on ranks, **not** on normalized scores. RRF only depends on the internal ranking of each retriever.

---

### 2.2 FusionResult

Output of multi-way recall fusion.

```python
class FusionResult(BaseModel):
    chunks: list[RetrievedChunk]
    sources: dict[str, int]  # retriever_name -> count
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `chunks` | `list[RetrievedChunk]` | Yes | Fused and reranked chunks. |
| `sources` | `dict[str, int]` | Yes | Contribution count per retriever (for debugging). |

---

### 2.3 RerankResult

Output of the reranking stage.

```python
class RerankResult(BaseModel):
    chunks: list[RetrievedChunk]
    reranker_name: str
    latency_ms: float
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `chunks` | `list[RetrievedChunk]` | Yes | Chunks with scores overwritten by reranker. |
| `reranker_name` | `str` | Yes | Identifier of the reranker used. |
| `latency_ms` | `float` | Yes | Time spent in reranking. |

---

## 3. Agent Layer

### 3.1 Observation

Result of executing a single action in the ReAct loop.

```python
class Observation(BaseModel):
    content: str
    tool_name: str | None = None
    tool_args: dict | None = None
    latency_ms: float = 0.0
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | `str` | Yes | Textual observation (e.g., tool output, retrieval result). |
| `tool_name` | `str \| None` | No | Tool that produced this observation. |
| `tool_args` | `dict \| None` | No | Arguments passed to the tool. |
| `latency_ms` | `float` | No | Execution latency. |

---

### 3.2 Step

A single step in the ReAct execution loop.

```python
class Step(BaseModel):
    thought: str
    action: str
    observation: Observation | None = None
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `thought` | `str` | Yes | LLM reasoning text. |
| `action` | `str` | Yes | Action identifier or JSON-encoded tool call. |
| `observation` | `Observation \| None` | No | Filled after action execution. |

---

### 3.3 Plan

High-level plan generated by the Planner.

```python
class Plan(BaseModel):
    query: str
    steps: list[Step]
    estimated_complexity: str = "medium"  # "low" | "medium" | "high"
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | `str` | Yes | Original user query. |
| `steps` | `list[Step]` | Yes | Ordered steps. May be empty for direct-answer queries. |
| `estimated_complexity` | `str` | No | Hint for skill routing and resource allocation. |

---

### 3.4 AgentResult

Final output of the Agent.

```python
class AgentResult(BaseModel):
    plan: Plan
    answer: str
    sources: list[ChunkMeta] = []
    metadata: dict = Field(default_factory=dict)
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `plan` | `Plan` | Yes | The executed plan (with observations filled). |
| `answer` | `str` | Yes | Final synthesized answer. |
| `sources` | `list[ChunkMeta]` | No | Source attributions for RAG answers. |
| `metadata` | `dict` | No | Debug info: `{"total_latency_ms": ..., "steps_executed": ...}`. |

---

## 4. Tool Layer

### 4.1 Tool

Schema definition for a tool (used by LLM for tool selection).

```python
class Tool(BaseModel):
    name: str
    description: str
    parameters: dict = Field(default_factory=dict)  # JSON Schema
```

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `name` | `str` | Yes | Pattern: `^[a-z_][a-z0-9_]*$`. Max 64 chars. | Unique tool name. |
| `description` | `str` | Yes | Max 1024 chars. | LLM-visible description. |
| `parameters` | `dict` | No | Must be valid JSON Schema if non-empty. | Input schema for validation. |

---

### 4.2 ToolCall

Represents a tool invocation request (usually from LLM output).

```python
class ToolCall(BaseModel):
    tool: str
    arguments: dict
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tool` | `str` | Yes | Name of the tool to invoke. |
| `arguments` | `dict` | Yes | Validated arguments matching the tool's `parameters` schema. |

---

### 4.3 ToolResult

Outcome of a tool execution.

```python
class ToolResult(BaseModel):
    tool: str
    output: Any
    error: str | None = None
    latency_ms: float = 0.0
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tool` | `str` | Yes | Tool name. |
| `output` | `Any` | Yes | Result payload. May be `None`. |
| `error` | `str \| None` | No | Human-readable error message. `None` indicates success. |
| `latency_ms` | `float` | No | Execution time. |

**Success Contract:**  
`error is None` → `output` contains the valid result.  
`error is not None` → `output` should be ignored or contain partial/degraded data.

---

## 5. Skill Layer

### 5.1 SkillLevel

```python
class SkillLevel(str, Enum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
```

| Level | Tool Exposure | Typical Use Case |
|-------|--------------|------------------|
| `BASIC` | High-level only (doc_summary, query) | Simple Q&A, single-document lookup |
| `INTERMEDIATE` | + code_analysis, cross_reference | Multi-document reasoning, code review |
| `ADVANCED` | + generate_snippet, web_fetch, MCP tools | Complex automation, external API integration |

---

### 5.2 SkillConfig

```python
class SkillConfig(BaseModel):
    name: str
    level: SkillLevel = SkillLevel.BASIC
    enabled: bool = True
    tools: list[str] = Field(default_factory=list)
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Skill identifier. |
| `level` | `SkillLevel` | No | Default exposure level. |
| `enabled` | `bool` | No | Whether this skill is active. |
| `tools` | `list[str]` | No | Explicit tool whitelist. Empty means "all tools at this level". |

---

## 6. MCP Layer

### 6.1 MCPHealthStatus

```python
class MCPHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    FAILED = "failed"
```

| Status | Meaning | Action |
|--------|---------|--------|
| `HEALTHY` | All tools responsive. | Use normally. |
| `DEGRADED` | Some tools slow or timed out. | Enable local fallback; alert user. |
| `DOWN` | Connection lost or process crashed. | Full fallback to local tools; queue reconnection. |
| `FAILED` | Spawn error or config validation failed. | Log error; do not retry auto-start. |

---

### 6.2 MCPServerConfig

```python
class MCPServerConfig(BaseModel):
    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict | None = None
    enabled: bool = True
    timeout: float = 30.0
    fallback_tools: list[str] = Field(default_factory=list)
    max_startup_time: float = 10.0
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Unique server identifier. |
| `command` | `str` | Yes | Executable name or absolute path. |
| `args` | `list[str]` | No | Command-line arguments. |
| `env` | `dict \| None` | No | Environment variable overrides. |
| `enabled` | `bool` | No | Auto-start on agent initialization. |
| `timeout` | `float` | No | Tool call timeout in seconds. |
| `fallback_tools` | `list[str]` | No | Local tool names to use when this server is down. |
| `max_startup_time` | `float` | No | Max seconds to wait for process spawn. |

### 6.3 MCPSettings (Global)

```python
class MCPSettings(BaseModel):
    enabled: bool = True
    health_check_interval: float = 30.0
    connection_timeout: float = 5.0
    degraded_threshold: int = 2
    down_threshold: int = 5
    auto_restart: bool = False
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | `bool` | No | `true` | Master switch. |
| `health_check_interval` | `float` | No | `30.0` | Seconds between health pings. |
| `connection_timeout` | `float` | No | `5.0` | TCP/stdio connection timeout. |
| `degraded_threshold` | `int` | No | `2` | Consecutive failures before marking DEGRADED. Must be >= 1. |
| `down_threshold` | `int` | No | `5` | Consecutive failures before marking DOWN. Must be >= `degraded_threshold`. |
| `auto_restart` | `bool` | No | `false` | Auto-restart DOWN servers. |

**Validation Rule:**
```
ASSERT down_threshold >= degraded_threshold >= 1
```

---

## 7. Serialization Notes

### 7.1 JSON Mode

All models support `model_dump(mode="json")` for wire transmission. `Any` fields (`ToolResult.output`) must be JSON-serializable (str, int, float, bool, None, list, dict).

### 7.2 Immutability

Models are **mutable by default**. Frozen variants may be introduced in `0.2.0` for index-time structures.

### 7.3 Versioning Strategy

- **Additive changes only in patch releases** (`0.1.x`): new optional fields, new models.
- **Minor releases** (`0.x.0`) may rename fields with deprecation aliases.
- **Major releases** (`x.0.0`) may break schemas.
