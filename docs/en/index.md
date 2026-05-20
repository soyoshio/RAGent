# RAGent Documentation

> **Version:** 0.1.0

## Document Index

```
docs/
├── zh/                # Chinese documentation
│   └── ...
└── en/                # English documentation (this directory)
    ├── index.md              # This page
    ├── interface_contract.md
    ├── data_model.md
    ├── error_handling.md
    ├── architecture.md
    ├── development_guide.md
    ├── testing_strategy.md
    ├── mcp_setup.md
    └── examples/
        ├── basic_query.md
        ├── chat_session.md
        └── custom_skill.md
```

---

## Core Specifications

| Document | Description |
|----------|-------------|
| [interface_contract.md](interface_contract.md) | OpenAPI-style contracts for LLMProvider, Tool Protocol, Retriever, Chunker, Embedder, Reranker, Agent, MCP Client |
| [data_model.md](data_model.md) | Complete Pydantic schema specifications with field constraints and validation rules |
| [error_handling.md](error_handling.md) | Hierarchical exception hierarchy, retry policies, circuit breaker, CLI rendering |
| [architecture.md](architecture.md) | System architecture, data flows, state machines, component diagrams |

## Development

| Document | Description |
|----------|-------------|
| [development_guide.md](development_guide.md) | Step-by-step tutorials for adding tools, LLM providers, retrievers, MCP servers |
| [testing_strategy.md](testing_strategy.md) | Testing pyramid, unit/integration/benchmark patterns, CI integration |
| [mcp_setup.md](mcp_setup.md) | MCP Server installation, configuration, health checks, fallback triggers |

## Examples

| Document | Description |
|----------|-------------|
| [examples/basic_query.md](examples/basic_query.md) | Direct RAG query with complete input/output |
| [examples/chat_session.md](examples/chat_session.md) | Interactive chat with multi-turn context |
| [examples/custom_skill.md](examples/custom_skill.md) | Configuring custom skill levels and tool exposure |

---

## Quick Links

- [Chinese Documentation](../zh/index.md)
- [Project Homepage](../../README.md)
