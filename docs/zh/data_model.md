# 数据模型规范

> **版本：** 0.1.0
> **Schema 引擎：** Pydantic v2
> **校验策略：** 严格模式（strict mode），对 URI 模式、标识符格式等使用自定义校验器。

代码片段默认省略公共导入：`from pydantic import BaseModel, Field`、`from typing import Any`。

---

## 1. 分块层（Chunk Layer）

分块层定义了文档切分后的基本数据结构，是 RAG 系统的原子数据单元。

### 1.1 ChunkMeta（分块元数据）

附加在每个分块上的元数据，记录来源信息和位置信息。

```python
class ChunkMeta(BaseModel):
    source: str
    start_line: int | None = None
    end_line: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
```

| 字段 | 类型 | 必填 | 约束条件 | 描述 |
|------|------|------|----------|------|
| `source` | `str` | 是 | 必须是有效 URI 或绝对路径。 | 文档来源标识。 |
| `start_line` | `int \| None` | 否 | 若存在，必须 `>= 1`。 | 起始行号（从 1 开始，含）。 |
| `end_line` | `int \| None` | 否 | 若与 `start_line` 同时存在，必须 `>= start_line`。 | 结束行号（从 1 开始，含）。 |
| `extra` | `dict` | 否 | 最大嵌套深度 3；所有值必须是 JSON 可序列化的。 | 自由格式元数据，例如 `{"heading": "## 简介"}`。 |

**校验规则：**
```
IF start_line IS NOT None AND end_line IS NOT None:
    ASSERT end_line >= start_line
    FAIL WITH: "end_line 必须 >= start_line"
```

---

### 1.2 Chunk（分块）

检索与生成的原子上下文单元。

```python
class Chunk(BaseModel):
    id: str
    text: str
    meta: ChunkMeta
```

| 字段 | 类型 | 必填 | 约束条件 | 描述 |
|------|------|------|----------|------|
| `id` | `str` | 是 | 正则模式：`^[a-zA-Z0-9_\-\.]+#[0-9]+$`。在索引范围内必须唯一。 | 稳定的分块标识符。 |
| `text` | `str` | 是 | 去除首尾空白后非空。最大长度：10000 字符（可通过配置调整）。 | 原始分块文本内容。 |
| `meta` | `ChunkMeta` | 是 | — | 分块的来源与位置元数据。 |

**示例：**
```json
{
  "id": "react_hooks_guide.md#3",
  "text": "useEffect 用于在函数组件中执行副作用操作。",
  "meta": {
    "source": "examples/react_hooks_guide.md",
    "start_line": 15,
    "end_line": 17,
    "extra": {"heading": "## useEffect"}
  }
}
```

---

### 1.3 Document（文档）

从单一源文件派生出的分块集合。

```python
class Document(BaseModel):
    id: str
    chunks: list[Chunk]
```

| 字段 | 类型 | 必填 | 约束条件 | 描述 |
|------|------|------|----------|------|
| `id` | `str` | 是 | 与 `Chunk.id` 相同模式，但不含 `#` 后缀。 | 源文档标识符。 |
| `chunks` | `list[Chunk]` | 是 | 非空列表。所有分块的 `meta.source` 必须一致。 | 有序分块列表。 |

---

## 2. 检索层（Retrieval Layer）

检索层定义了召回结果的数据结构，包含原始分块及其相关性分数。

### 2.1 RetrievedChunk（已检索分块）

被检索器召回并附加相关性评分的分块。

```python
class RetrievedChunk(BaseModel):
    chunk: Chunk
    score: float
```

| 字段 | 类型 | 必填 | 约束条件 | 描述 |
|------|------|------|----------|------|
| `chunk` | `Chunk` | 是 | — | 被检索到的原始分块。 |
| `score` | `float` | 是 | 通常位于 `[0.0, 1.0]`，但具体范围取决于检索器实现。 | 相关性分数（越高表示越相关）。 |

**融合规则：**
不同检索器产生的分数范围不同：余弦相似度为 `[-1, 1]`，BM25 无上限，图谱近邻为 `[0, ∞)`。默认的 `FusionRetriever` 使用倒数排名融合（RRF），只依赖各检索器内部排序，不要求先对原始分数做 Min-Max 归一化。若未来启用加权分数融合，才需要先将不同检索器的分数统一到 `[0, 1]` 区间。

---

### 2.2 FusionResult（融合结果）

多路召回融合后的输出。

```python
class FusionResult(BaseModel):
    chunks: list[RetrievedChunk]
    sources: dict[str, int]  # retriever_name -> count
```

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `chunks` | `list[RetrievedChunk]` | 是 | 经 RRF 融合并初步排序后的分块列表。 |
| `sources` | `dict[str, int]` | 是 | 每个检索器的贡献计数（用于调试与可解释性）。 |

---

### 2.3 RerankResult（重排序结果）

重排序阶段的输出。

```python
class RerankResult(BaseModel):
    chunks: list[RetrievedChunk]
    reranker_name: str
    latency_ms: float
```

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `chunks` | `list[RetrievedChunk]` | 是 | 分数被重排序器覆盖后的分块列表。 |
| `reranker_name` | `str` | 是 | 使用的重排序器标识符（如 `cross-encoder/ms-marco`）。 |
| `latency_ms` | `float` | 是 | 重排序阶段的耗时（毫秒）。 |

---

## 3. Agent 层（Agent Layer）

Agent 层定义了 ReAct 循环中各阶段的数据结构，以及最终的 Agent 输出。

### 3.1 Observation（观察结果）

ReAct 循环中执行单个动作后的结果。

```python
class Observation(BaseModel):
    content: str
    tool_name: str | None = None
    tool_args: dict | None = None
    latency_ms: float = 0.0
```

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `content` | `str` | 是 | 文本观察结果（如工具输出、检索结果摘要）。 |
| `tool_name` | `str \| None` | 否 | 产生该观察的工具名称。若为直接检索结果，可为 `None`。 |
| `tool_args` | `dict \| None` | 否 | 传递给工具的参数。用于审计和调试。 |
| `latency_ms` | `float` | 否 | 执行延迟（毫秒）。默认 `0.0`。 |

---

### 3.2 Step（执行步骤）

ReAct 执行循环中的单一步骤。

```python
class Step(BaseModel):
    thought: str
    action: str
    observation: Observation | None = None
```

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `thought` | `str` | 是 | LLM 的推理文本，解释为什么要执行该动作。 |
| `action` | `str` | 是 | 动作标识符或 JSON 编码的工具调用（如 `{"tool": "web_fetch", "args": {"url": "..."}}`）。 |
| `observation` | `Observation \| None` | 否 | 动作执行后填充的观察结果。规划阶段为 `None`。 |

---

### 3.3 Plan（执行计划）

Planner 生成的高层执行计划。

```python
class Plan(BaseModel):
    query: str
    steps: list[Step]
    estimated_complexity: str = "medium"  # "low" | "medium" | "high"
```

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `query` | `str` | 是 | 原始用户查询。 |
| `steps` | `list[Step]` | 是 | 有序步骤列表。对于直接回答类查询可为空。 |
| `estimated_complexity` | `str` | 否 | 复杂度提示，用于技能路由和资源分配。取值：`low`、`medium`、`high`。 |

---

### 3.4 AgentResult（Agent 结果）

Agent 的最终输出。

```python
class AgentResult(BaseModel):
    plan: Plan
    answer: str
    sources: list[ChunkMeta] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `plan` | `Plan` | 是 | 已执行的计划（含各步骤的观察结果）。 |
| `answer` | `str` | 是 | 最终综合答案，已渲染为 Markdown 格式。 |
| `sources` | `list[ChunkMeta]` | 否 | RAG 答案的来源引用，用于可解释性和溯源。 |
| `metadata` | `dict` | 否 | 调试信息，如 `{"total_latency_ms": ..., "steps_executed": ..., "tokens_used": ...}`。 |

---

## 4. 工具层（Tool Layer）

工具层定义了工具声明、调用请求和调用结果的数据结构。

### 4.1 Tool（工具定义）

供 LLM 进行工具选择的模式定义。

```python
class Tool(BaseModel):
    name: str
    description: str
    parameters: dict = Field(default_factory=dict)  # JSON Schema
```

| 字段 | 类型 | 必填 | 约束条件 | 描述 |
|------|------|------|----------|------|
| `name` | `str` | 是 | 正则：`^[a-z_][a-z0-9_]*$`。最大 64 字符。 | 唯一工具名。 |
| `description` | `str` | 是 | 最大 1024 字符。 | LLM 可见的功能描述。 |
| `parameters` | `dict` | 否 | 若非空，必须是有效的 JSON Schema。 | 输入参数的模式定义，用于校验。 |

---

### 4.2 ToolCall（工具调用）

表示来自 LLM 输出的工具调用请求。

```python
class ToolCall(BaseModel):
    tool: str
    arguments: dict
```

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `tool` | `str` | 是 | 要调用的工具名称。 |
| `arguments` | `dict` | 是 | 与工具 `parameters` 模式匹配且已通过校验的参数。 |

---

### 4.3 ToolResult（工具结果）

工具执行的最终结果。

```python
class ToolResult(BaseModel):
    tool: str
    output: Any
    error: str | None = None
    latency_ms: float = 0.0
```

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `tool` | `str` | 是 | 工具名称。 |
| `output` | `Any` | 是 | 结果负载。可为 `None`。必须是 JSON 可序列化的。 |
| `error` | `str \| None` | 否 | 人类可读的错误消息。`None` 表示执行成功。 |
| `latency_ms` | `float` | 否 | 执行时间（毫秒）。 |

**成功契约：**
- `error is None` → `output` 包含有效结果，可被下游消费。
- `error is not None` → `output` 应被忽略，或仅包含部分/降级数据。

**调用边界：**
- 单个工具实现可以返回任意 JSON 可序列化值，也可以抛出 `ToolExecutionError` 等异常。
- `ToolRegistry.call()` 是对 Agent 暴露的稳定边界，必须捕获工具异常并统一转换为 `ToolResult`。
- ReAct Executor 只消费 `ToolResult`，不直接依赖具体工具的返回类型或异常类型。

---

## 5. 技能层（Skill Layer）

技能层定义了渐进式披露的能力分级配置。

### 5.1 SkillLevel（技能等级）

```python
class SkillLevel(str, Enum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
```

| 等级 | 工具暴露范围 | 典型使用场景 |
|------|-------------|-------------|
| `BASIC` | 仅基础工具（`doc_summary`、`query`） | 简单问答、单文档查询 |
| `INTERMEDIATE` | 增加 `code_analysis`、`cross_reference` | 多文档推理、代码审查 |
| `ADVANCED` | 增加 `generate_snippet`、`web_fetch`、MCP 工具 | 复杂自动化、外部 API 集成 |

---

### 5.2 SkillConfig（技能配置）

```python
class SkillConfig(BaseModel):
    name: str
    level: SkillLevel = SkillLevel.BASIC
    enabled: bool = True
    tools: list[str] = Field(default_factory=list)
```

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `name` | `str` | 是 | 技能标识符。 |
| `level` | `SkillLevel` | 否 | 默认暴露等级。 |
| `enabled` | `bool` | 否 | 该技能是否激活。 |
| `tools` | `list[str]` | 否 | 显式工具白名单。空列表表示"该等级下所有可用工具"。 |

---

## 6. MCP 层（MCP Layer）

MCP 层定义了 MCP Server 的健康状态枚举和配置模型。

### 6.1 MCPHealthStatus（MCP 健康状态）

```python
class MCPHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    FAILED = "failed"
```

| 状态 | 含义 | 建议操作 |
|------|------|----------|
| `HEALTHY` | 所有工具响应正常。 | 正常使用。 |
| `DEGRADED` | 部分工具响应缓慢或超时。 | 启用本地降级工具；向用户发出提示。 |
| `DOWN` | 连接丢失或进程崩溃。 | 完全降级到本地工具；将重新连接加入队列。 |
| `FAILED` | 进程启动失败或配置校验失败。 | 记录错误；不进入自动健康检查，除非用户手动修复配置后重启。 |

---

### 6.2 MCPServerConfig（MCP 服务器配置）

```python
class MCPServerConfig(BaseModel):
    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    timeout: float = 30.0
    max_startup_time: float = 10.0
    fallback_tools: list[str] = Field(default_factory=list)
```

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `name` | `str` | 是 | 唯一服务器标识符。 |
| `command` | `str` | 是 | 可执行文件路径或命令名。 |
| `args` | `list[str]` | 否 | 命令行参数列表。 |
| `env` | `dict[str, str]` | 否 | 环境变量覆盖。 |
| `enabled` | `bool` | 否 | 是否在 Agent 初始化时自动启动。 |
| `timeout` | `float` | 否 | 工具调用超时（秒）。默认 30.0。 |
| `max_startup_time` | `float` | 否 | 等待进程启动的最大秒数。默认 10.0。 |
| `fallback_tools` | `list[str]` | 否 | 服务器宕机时使用的本地工具名列表。 |

### 6.3 MCPSettings（MCP 全局配置）

```python
class MCPSettings(BaseModel):
    enabled: bool = True
    health_check_interval: float = 30.0
    connection_timeout: float = 5.0
    degraded_threshold: int = 2
    down_threshold: int = 5
    auto_restart: bool = False
    servers: list[MCPServerConfig] = Field(default_factory=list)
```

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `enabled` | `bool` | 否 | MCP 总开关。 |
| `health_check_interval` | `float` | 否 | 健康检查 ping 间隔（秒）。 |
| `connection_timeout` | `float` | 否 | 初始连接超时（秒）。 |
| `degraded_threshold` | `int` | 否 | 连续失败达到该值后标记为 `DEGRADED`。 |
| `down_threshold` | `int` | 否 | 连续失败达到该值后标记为 `DOWN`。 |
| `auto_restart` | `bool` | 否 | `DOWN` 状态下是否自动重启。 |
| `servers` | `list[MCPServerConfig]` | 否 | MCP Server 配置列表。 |

---

## 7. 序列化说明

### 7.1 JSON 模式

所有模型均支持 `model_dump(mode="json")` 用于网络传输。`Any` 类型字段（如 `ToolResult.output`）的值必须是 JSON 可序列化的（`str`、`int`、`float`、`bool`、`None`、`list`、`dict`）。

### 7.2 可变性

模型**默认可变**。在 `0.2.0` 版本中可能为索引时结构引入不可变变体（`frozen=True`），以保障并发安全。

### 7.3 版本策略

- **补丁版本（`0.1.x`）**：仅做增量变更 — 新增可选字段、新增模型，不破坏现有模式。
- **次要版本（`0.x.0`）**：可能重命名字段，但保留弃用别名（`Field(validation_alias=...)`）。
- **主要版本（`x.0.0`）**：可能破坏模式兼容性。

---

## 附录：字段速查表

| 模型 | 字段数 | 必填字段数 | 关键约束 |
|------|--------|-----------|----------|
| `ChunkMeta` | 4 | 1 | `end_line >= start_line` |
| `Chunk` | 3 | 3 | `text` 非空；`id` 全局唯一 |
| `Document` | 2 | 2 | `chunks` 非空；`meta.source` 一致 |
| `RetrievedChunk` | 2 | 2 | `score` 可超出 `[0,1]` |
| `FusionResult` | 2 | 2 | `sources` 调试用 |
| `RerankResult` | 3 | 3 | `latency_ms >= 0` |
| `Observation` | 4 | 1 | `latency_ms >= 0` |
| `Step` | 3 | 2 | `observation` 执行后填充 |
| `Plan` | 3 | 2 | `complexity ∈ {low,medium,high}` |
| `AgentResult` | 4 | 2 | `sources` 用于溯源 |
| `Tool` | 3 | 2 | `parameters` 需符合 JSON Schema |
| `ToolCall` | 2 | 2 | `arguments` 已校验 |
| `ToolResult` | 4 | 2 | `error=None` 表示成功 |
| `SkillConfig` | 4 | 1 | `tools` 为空表示全部 |
| `MCPServerConfig` | 8 | 2 | `timeout > 0`；`max_startup_time > 0` |
| `MCPSettings` | 7 | 0 | `down_threshold >= degraded_threshold >= 1` |
