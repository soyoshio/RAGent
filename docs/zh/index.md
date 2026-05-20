# RAGent 项目文档

> **Version:** 0.1.0

## 文档索引

```
docs/
├── en/                # 英文文档
│   ├── index.md
│   └── ...
└── zh/                # 中文文档
    ├── index.md       # 本页面
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

## 核心规范

| 文档 | 说明 |
|------|------|
| [interface_contract.md](interface_contract.md) | 类 OpenAPI 接口契约：LLMProvider、Tool Protocol、Retriever、Chunker、Embedder、Reranker、Agent、MCP Client |
| [data_model.md](data_model.md) | 完整 Pydantic 数据模型规范，含字段约束与校验规则 |
| [error_handling.md](error_handling.md) | 分层异常体系、重试策略、熔断器、CLI 错误渲染 |
| [architecture.md](architecture.md) | 系统架构设计、数据流、状态机、组件图 |

## 开发指南

| 文档 | 说明 |
|------|------|
| [development_guide.md](development_guide.md) | 添加 Tool、LLM Provider、Retriever、MCP Server 的逐步教程 |
| [testing_strategy.md](testing_strategy.md) | 测试金字塔、单元/集成/基准测试模式、CI 集成 |
| [mcp_setup.md](mcp_setup.md) | MCP Server 安装配置、健康检查、降级触发条件 |

## 使用示例

| 文档 | 说明 |
|------|------|
| [examples/basic_query.md](examples/basic_query.md) | 直接 RAG 查询的完整输入输出 |
| [examples/chat_session.md](examples/chat_session.md) | 带多轮上下文的交互式聊天 |
| [examples/custom_skill.md](examples/custom_skill.md) | 自定义技能等级与工具暴露配置 |

---

## 快速链接

- [英文文档](../en/index.md)
- [项目主页](../../README.md)
