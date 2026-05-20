# Architecture Design

> **Version:** 0.1.0
> **Last Updated:** 2026-05-19

---

## 1. System Overview

RAGent is a **hybrid RAG-Agent** system combining:
- **Plan-and-Execute** for complex multi-step tasks
- **ReAct** (Reasoning + Acting) for tool-augmented execution
- **Multi-way Retrieval** (vector + keyword + graph) for grounding
- **MCP Protocol** for dynamic tool ecosystem integration

```mermaid
graph TB
    subgraph UserLayer["User Layer"]
        CLI["CLI (ragents/cli/)"]
    end

    subgraph AgentLayer["Agent Layer"]
        HA["HybridAgent"]
        PL["Planner"]
        EX["ReAct Executor"]
        SY["Synthesizer"]
        SR["SkillRouter"]
    end

    subgraph ToolLayer["Tool Layer"]
        TR["ToolRegistry"]
        LT["Local Tools"]
        MCP["MCP Client Pool"]
    end

    subgraph RAGLayer["RAG Layer"]
        RT["FusionRetriever"]
        VR["VectorRetriever"]
        KR["KeywordRetriever"]
        GR["GraphRetriever"]
        RR["Reranker"]
    end

    subgraph LLMLayer["LLM Layer"]
        LLM["LLMProvider"]
        OP["OpenAIProvider"]
        AP["AnthropicProvider"]
        LP["LocalProvider"]
    end

    subgraph MemoryLayer["Memory Layer"]
        STM["ShortTermMemory"]
        LTM["LongTermMemory"]
    end

    CLI --> HA
    HA --> PL
    HA --> EX
    HA --> SY
    HA --> SR
    SR --> TR
    EX --> TR
    TR --> LT
    TR --> MCP
    EX --> RT
    RT --> VR
    RT --> KR
    RT --> GR
    RT --> RR
    PL --> LLM
    EX --> LLM
    SY --> LLM
    LLM --> OP
    LLM --> AP
    LLM --> LP
    HA --> STM
    HA -.-> LTM
```

---

## 2. Layer Responsibilities

### 2.1 CLI Layer

**Responsibilities:**
- Parse user input (commands, flags, queries)
- Render output (Markdown, tables, progress bars via `rich`)
- Handle top-level error boundaries (catch-all exception handler)
- Load configuration and environment

**Entry Points:**
| Command | Module | Agent Mode | Memory |
|---------|--------|-----------|--------|
| `ragent "..."` | `commands/query.py` | One-shot, no history | Stateless |
| `ragent chat` | `commands/chat.py` | Interactive | ShortTermMemory |
| `ragent index` | `commands/index.py` | No agent | — |
| `ragent mcp` | `commands/mcp.py` | Management | — |

---

### 2.2 Agent Layer

The Agent layer is the **orchestration core**. It decides *whether* to plan, *which* tools to use, and *how* to synthesize the final answer.

```mermaid
stateDiagram-v2
    [*] --> IntentAnalysis: Receive Query
    IntentAnalysis --> DirectAnswer: Simple Factual Query<br/>(Low Complexity)
    IntentAnalysis --> Planning: Complex / Multi-step<br/>(Medium+ Complexity)

    DirectAnswer --> RAGRetrieve: "Need grounding"
    DirectAnswer --> Synthesize: "No grounding needed"

    Planning --> PlanValidation: Generate Plan JSON
    PlanValidation --> Planning: Invalid / Empty
    PlanValidation --> Execution: Valid Plan

    Execution --> Observation: Execute Action
    Observation --> Execution: More Steps
    Observation --> Synthesize: All Steps Done

    Synthesize --> [*]: Deliver Answer

    Execution --> Fallback: Tool/MCP Failure
    Fallback --> Execution: Local Tool OK
    Fallback --> Synthesize: Degraded Result
```

#### HybridAgent Decision Flow

```mermaid
flowchart TD
    Q[User Query] --> C{Complexity?}
    C -->|Low| D[Direct RAG Retrieval]
    C -->|Medium| P1[Single-Step Plan]
    C -->|High| P2[Multi-Step Plan]

    D --> R[Reranker]
    P1 --> E1[Execute 1 Step]
    P2 --> E2[ReAct Loop]

    R --> S[Synthesize]
    E1 --> S
    E2 --> S

    S --> A[Answer]
```

| Complexity | Heuristic | Planner Action | Max Steps |
|-----------|-----------|---------------|-----------|
| Low | Single entity, no comparison | Skip planner; direct RAG | 0 |
| Medium | Comparison, cause-effect | Generate 1-3 step plan | 3 |
| High | Multi-document synthesis, code generation | Generate full ReAct plan | 10 |

---

### 2.3 RAG Layer

```mermaid
sequenceDiagram
    participant Agent
    participant Fusion as FusionRetriever
    participant Vec as VectorRetriever
    participant Kw as KeywordRetriever
    participant Graph as GraphRetriever
    participant RR as Reranker

    Agent->>Fusion: retrieve(query, top_k=5)

    par Parallel Recall
        Fusion->>Vec: retrieve(query, top_k=20)
        Fusion->>Kw: retrieve(query, top_k=20)
        Fusion->>Graph: retrieve(query, top_k=20)
    end

    Vec-->>Fusion: chunks_v (scores: cosine)
    Kw-->>Fusion: chunks_k (scores: bm25)
    Graph-->>Fusion: chunks_g (scores: graph proximity)

    Note over Fusion: RRF Fusion (ranks only, no normalization)

    Fusion->>Fusion: reciprocal_rank_fusion(k=60)
    Fusion-->>Agent: fused_top_20

    Agent->>RR: rerank(query, fused_top_20, top_k=5)
    RR-->>Agent: final_top_5
```

#### Reciprocal Rank Fusion Formula

```
RRF_score(d) = Σ 1 / (k + rank_r(d))
```

Where:
- `k = 60` (constant, prevents domination by top ranks)
- `rank_r(d)` = rank of document `d` in retriever `r`
- Documents not ranked by a retriever receive `rank = ∞` (contribution = 0)

**Important:** RRF operates on **ranks**, not scores. No Min-Max normalization is needed before fusion.

---

### 2.4 Tool Layer

```mermaid
graph LR
    Executor["ReAct Executor"] --> Registry["ToolRegistry"]
    Registry --> Route{Tool Location?}
    Route -->|MCP Available| MCP["MCP Client"]
    Route -->|MCP Down| Fallback["Local Fallback"]
    Route -->|No MCP Config| Local["Local Tool"]

    MCP --> Remote["Remote Tool Server"]
    Fallback --> Local
    Local --> Code["code_analysis"]
    Local --> Web["web_fetch"]
    Local --> Gen["generate_snippet"]
```

**Progressive Disclosure:**

| Skill Level | Tools Exposed | Example Query |
|------------|---------------|---------------|
| Basic | `doc_summary`, `query` | "What is useState?" |
| Intermediate | + `code_analysis`, `cross_reference` | "Compare useState and useReducer" |
| Advanced | + `generate_snippet`, `web_fetch`, MCP tools | "Build me a custom hook for data fetching and verify against React docs" |

---

### 2.5 MCP Layer

```mermaid
sequenceDiagram
    participant SM as ServerManager
    participant CP as ClientPool
    participant TD as ToolDiscovery
    participant S as MCP Server Process
    participant F as Fallback

    SM->>SM: load_config()
    loop For each enabled server
        SM->>S: spawn_process()
        S-->>SM: pid
        SM->>CP: register(name, client)
        CP->>CP: start_health_check(name)
    end

    TD->>CP: get_client(name)
    CP-->>TD: client
    TD->>S: list_tools()
    S-->>TD: tool_schemas
    TD->>TR: register_remote_tools(schemas)

    Note over CP: Health Check Interval: 30s
    CP->>S: ping()
    S--xCP: timeout
    CP->>SM: notify_degraded(name)
    SM->>F: activate_fallback(name)
    F->>TR: swap_remote_to_local(tools)
```

**Lifecycle States:**

```mermaid
stateDiagram-v2
    [*] --> Configured: Load .env / config
    Configured --> Starting: Auto-start enabled
    Starting --> Healthy: Process spawned
    Starting --> Failed: Spawn error
    Healthy --> Degraded: Consecutive failures reach degraded_threshold
    Degraded --> Healthy: Recovery
    Degraded --> Down: Consecutive failures reach down_threshold
    Down --> Starting: Manual restart or auto_restart=true
    Failed --> [*]: Log error
    Healthy --> [*]: Shutdown
    Down --> [*]: Shutdown
```

---

### 2.6 LLM Layer

```mermaid
graph TB
    subgraph ProviderFactory["Provider Factory"]
        PF["create_provider(name, config)"]
    end

    subgraph RetryWrapper["Retry + Circuit Breaker"]
        RP["RetryPolicy"]
        CB["CircuitBreaker"]
    end

    subgraph Providers["Concrete Providers"]
        OP["OpenAIProvider"]
        CP["AnthropicProvider"]
        LP["LocalProvider"]
    end

    PF --> OP
    PF --> CP
    PF --> LP

    OP --> RP
    CP --> RP
    LP --> RP
    RP --> CB
```

**Provider Selection Logic:**

```python
# Pseudocode
def select_provider(task_type, complexity):
    if task_type == "planning" and complexity == "high":
        return create_provider(settings.llm.planning_provider)
    elif task_type == "embed":
        return create_provider(settings.llm.embed_provider)
    elif task_type == "chat" and not internet:
        return create_provider(settings.llm.local_provider)
    else:
        return create_provider(settings.llm.default_provider)
```

---

### 2.7 Memory Layer

```mermaid
graph LR
    subgraph STM["ShortTermMemory"]
        Q[User Query]
        A[Agent Answer]
        C[Retrieved Context]
    end

    subgraph LTM["LongTermMemory (Reserved)"]
        V[(Vector Store)]
        S[Session Summaries]
    end

    CLI --> STM
    STM --> Agent
    Agent -.->|Future| LTM
```

**ShortTermMemory Design:**
- Ring buffer of last N turns (default: 10)
- Stores raw messages + retrieved context IDs
- Automatically injected into `Planner` and `Executor` context

**LongTermMemory (Reserved for v0.2):**
- Cross-session vector memory for recurring topics
- Automatic conversation summarization
- User preference learning

---

## 3. Data Flow Diagrams

### 3.1 Query Flow (Direct)

```mermaid
sequenceDiagram
    participant U as User
    participant CLI
    participant HA as HybridAgent
    participant SR as SkillRouter
    participant PL as Planner
    participant EX as Executor
    participant SY as Synthesizer
    participant RT as FusionRetriever
    participant LLM as LLMProvider
    participant REN as RichRenderer

    U->>CLI: ragent "useEffect cleanup"
    CLI->>HA: run(query)
    HA->>SR: route(query)
    SR-->>HA: level=BASIC

    alt Low Complexity
        HA->>RT: retrieve(query, top_k=5)
        RT-->>HA: chunks
        HA->>SY: synthesize(query, context)
        SY->>LLM: chat(prompt_with_context)
        LLM-->>SY: answer
        SY-->>HA: AgentResult
    else Medium+ Complexity
        HA->>PL: plan(query)
        PL->>LLM: chat(planning_prompt)
        LLM-->>PL: plan_json
        PL-->>HA: Plan(steps=[...])

        loop ReAct Execution
            HA->>EX: execute_step(step)
            EX->>RT: retrieve(step_query)
            RT-->>EX: chunks
            EX->>LLM: chat(execution_prompt)
            LLM-->>EX: action_json
            EX->>EX: execute_action()
        end

        HA->>SY: synthesize(observations)
        SY->>LLM: chat(synthesis_prompt)
        LLM-->>SY: final_answer
        SY-->>HA: AgentResult
    end

    HA-->>CLI: AgentResult
    CLI->>REN: render(result)
    REN-->>U: Markdown output
```

### 3.2 Index Flow

```mermaid
sequenceDiagram
    participant CLI
    participant CH as Chunker
    participant EM as Embedder
    participant VI as VectorIndex
    participant KI as KeywordIndex
    participant GI as GraphIndex

    CLI->>CH: chunk_file(path)
    CH-->>CLI: list[Chunk]

    par Parallel Indexing
        CLI->>EM: embed(chunk_texts)
        EM-->>CLI: vectors
        CLI->>VI: add(chunks, vectors)

        CLI->>KI: add(chunks)

        CLI->>GI: add(chunks)
    end

    VI-->>CLI: OK
    KI-->>CLI: OK
    GI-->>CLI: OK
```

### 3.3 Chat Flow (Interactive)

```mermaid
sequenceDiagram
    participant U as User
    participant CLI
    participant HA as HybridAgent
    participant STM as ShortTermMemory
    participant LLM as LLMProvider

    loop Interactive Session
        U->>CLI: "How about useReducer?"
        CLI->>HA: run(query, context={history})
        HA->>STM: get_history()
        STM-->>HA: last_10_turns

        HA->>HA: append_history_to_prompt()
        HA->>LLM: chat(augmented_prompt)
        LLM-->>HA: response

        HA->>STM: add(user=query, assistant=response)
        HA-->>CLI: AgentResult
        CLI-->>U: Answer
    end
```

---

## 4. Component Interaction Matrix

| Caller → Callee | LLMProvider | ToolRegistry | FusionRetriever | Chunker | Embedder | MCP Client | Memory |
|----------------|-------------|--------------|-----------------|---------|----------|------------|--------|
| **CLI** | — | — | — | — | — | — | — |
| **HybridAgent** | — | — | — | — | — | — | get, add |
| **Planner** | chat | — | — | — | — | — | get |
| **Executor** | chat | call | retrieve | — | — | — | — |
| **Synthesizer** | chat | — | — | — | — | — | — |
| **FusionRetriever** | — | — | — | — | — | — | — |
| **Chunker** | — | — | — | — | — | — | — |
| **MCP Client** | — | — | — | — | — | — | — |

**Design Principle:** HybridAgent does **not** directly call LLMProvider, ToolRegistry, or FusionRetriever. All interactions go through Planner, Executor, or Synthesizer.

---

## 5. Configuration Architecture

```mermaid
graph TB
    subgraph Sources["Configuration Sources"]
        Env[".env file"]
        Toml["ragents.toml (primary)"]
        Pyproject["pyproject.toml [tool.ragents] (compatibility)"]
        CLIArgs["CLI --flags"]
    end

    subgraph Loader["Config Loader"]
        PS["pydantic-settings"]
        Val["validators.py"]
    end

    subgraph Runtime["Runtime Config"]
        Settings["Settings object"]
        LLMC["LLM Config"]
        MCPC["MCP Config"]
        RAGC["RAG Config"]
    end

    Env --> PS
    Toml --> PS
    Pyproject --> PS
    CLIArgs --> PS
    PS --> Val
    Val --> Settings
    Settings --> LLMC
    Settings --> MCPC
    Settings --> RAGC
```

**Priority (highest to lowest):**
1. CLI arguments (`--model`, `--index`)
2. Environment variables (`OPENAI_API_KEY`)
3. `.env` file
4. `ragents.toml` (primary project config)
5. `pyproject.toml [tool.ragents]` (compatibility fallback)
6. Default values in `Settings` model

---

## 6. Scalability Considerations

### 6.1 Horizontal Scaling (Future)

| Component | Scaling Strategy |
|-----------|-----------------|
| LLMProvider | Load balancing across multiple API keys; local model replicas via vLLM |
| MCP Client | Connection pooling; health-check-based routing |
| FusionRetriever | Shard by document collection; parallel retriever processes |
| Embedder | Batch processing; GPU offloading for local models |

### 6.2 Caching Strategy

| Layer | Cache Target | TTL | Invalidation |
|-------|-------------|-----|--------------|
| LLM | Chat completions (exact match) | 1 hour | Manual / API key change |
| RAG | Embedding vectors | Infinite | Document re-index |
| Tool | Web fetch results | 5 minutes | Manual |
| MCP | Tool schemas | Until disconnect | Server restart |

---

## 7. Technology Stack

| Layer | Primary Libraries | Alternatives |
|-------|-------------------|--------------|
| CLI | `argparse` + `rich` | `typer`, `click` |
| Schema | `pydantic` v2 | — |
| Config | `pydantic-settings` | `python-dotenv` |
| Logging | `structlog` | Standard `logging` |
| LLM | `openai`, `anthropic` SDKs | `litellm` (future) |
| RAG (Vector) | `numpy` + custom HNSW | `faiss`, `chromadb` |
| RAG (Keyword) | `rank-bm25` | `whoosh` |
| RAG (Graph) | `networkx` | `neo4j` |
| MCP | `mcp` SDK (official) | Custom stdio/SSE |
| Testing | `pytest` | — |
| Packaging | `hatchling` + `uv` | `poetry`, `pdm` |

---

## 8. Version Boundaries

| Version | Scope | Key Changes |
|---------|-------|-------------|
| 0.1.x | MVP | Synchronous first; local tools + MCP; ShortTermMemory only |
| 0.2.x | Extension | Async first-class; LongTermMemory; frozen index structures |
| 0.3.x | Scale | Distributed retrievers; multi-model ensemble; web UI |

---

## Appendix: File Organization Rationale

**Why `src/ragents/` instead of `ragents/` at root?**

The `src-layout` (placing source under `src/`) prevents accidental imports of the development directory. It ensures that:
1. Tests run against the **installed** package, not the source tree
2. `import ragents` fails unless the package is properly installed
3. Build artifacts are cleanly separated from source
