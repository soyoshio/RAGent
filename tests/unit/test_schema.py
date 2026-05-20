"""Schema unit tests.

Covers all Pydantic models in ragents.schema:
- ChunkMeta, Chunk, Document (chunk layer)
- RetrievedChunk, FusionResult, RerankResult (retrieval layer)
- Observation, Step, Plan, AgentResult (agent layer)
- Tool, ToolCall, ToolResult (tool layer)
- SkillConfig, SkillLevel (skill layer)
- MCPHealthStatus, MCPServerConfig, MCPSettings (MCP layer)

Each model is tested for:
- Valid instantiation
- Invalid instantiation (validators)
- Serialization round-trip
- Edge cases
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ragents.schema import (
    AgentResult,
    Chunk,
    ChunkMeta,
    Document,
    FusionResult,
    MCPHealthStatus,
    MCPServerConfig,
    MCPSettings,
    Observation,
    Plan,
    RerankResult,
    RetrievedChunk,
    SkillConfig,
    SkillLevel,
    Step,
    Tool,
    ToolCall,
    ToolResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_chunk() -> Chunk:
    return Chunk(
        id="test.py#1",
        text="def hello():\n    return 'world'",
        meta=ChunkMeta(source="test.py", start_line=1, end_line=2),
    )


@pytest.fixture
def sample_step() -> Step:
    return Step(
        thought="I need to search for the answer",
        action='{"tool": "query", "args": {"q": "hello"}}',
    )


# ---------------------------------------------------------------------------
# Chunk Layer
# ---------------------------------------------------------------------------


class TestChunkMeta:
    def test_valid(self):
        meta = ChunkMeta(source="test.py", start_line=1, end_line=10)
        assert meta.source == "test.py"
        assert meta.start_line == 1
        assert meta.end_line == 10
        assert meta.extra == {}

    def test_minimal(self):
        meta = ChunkMeta(source="test.py")
        assert meta.start_line is None
        assert meta.end_line is None

    def test_with_extra(self):
        meta = ChunkMeta(
            source="test.py", start_line=1, end_line=2, extra={"heading": "## Intro"}
        )
        assert meta.extra == {"heading": "## Intro"}

    def test_end_line_less_than_start_line(self):
        with pytest.raises(ValidationError) as exc_info:
            ChunkMeta(source="test.py", start_line=5, end_line=3)
        assert "end_line must be >= start_line" in str(exc_info.value)

    def test_end_line_equal_start_line_ok(self):
        meta = ChunkMeta(source="test.py", start_line=5, end_line=5)
        assert meta.end_line == 5

    def test_none_end_line_ok(self):
        meta = ChunkMeta(source="test.py", start_line=5, end_line=None)
        assert meta.end_line is None

    def test_serialization_roundtrip(self):
        meta = ChunkMeta(source="test.py", start_line=1, end_line=2, extra={"a": 1})
        data = meta.model_dump()
        meta2 = ChunkMeta(**data)
        assert meta2.source == "test.py"
        assert meta2.extra == {"a": 1}


class TestChunk:
    def test_valid(self, sample_chunk: Chunk):
        assert sample_chunk.id == "test.py#1"
        assert "def hello()" in sample_chunk.text
        assert sample_chunk.meta.source == "test.py"

    def test_empty_text(self):
        with pytest.raises(ValidationError) as exc_info:
            Chunk(id="test#1", text="   ", meta=ChunkMeta(source="test.py"))
        assert "text must not be empty" in str(exc_info.value)

    def test_invalid_id_format(self):
        with pytest.raises(ValidationError) as exc_info:
            Chunk(id="bad_id", text="hello", meta=ChunkMeta(source="test.py"))
        assert "id must match pattern" in str(exc_info.value)

    def test_id_with_hash_no_number(self):
        with pytest.raises(ValidationError) as exc_info:
            Chunk(id="test#", text="hello", meta=ChunkMeta(source="test.py"))
        assert "id must match pattern" in str(exc_info.value)

    def test_id_various_valid_formats(self):
        valid_ids = [
            "file.py#1",
            "my-file.md#123",
            "dir/file.txt#0",
            "a_b.c#99",
        ]
        for vid in valid_ids:
            chunk = Chunk(id=vid, text="hello", meta=ChunkMeta(source="test.py"))
            assert chunk.id == vid

    def test_serialization_roundtrip(self, sample_chunk: Chunk):
        data = sample_chunk.model_dump()
        chunk2 = Chunk(**data)
        assert chunk2.id == sample_chunk.id
        assert chunk2.text == sample_chunk.text


class TestDocument:
    def test_valid(self, sample_chunk: Chunk):
        doc = Document(id="test.py", chunks=[sample_chunk])
        assert doc.id == "test.py"
        assert len(doc.chunks) == 1

    def test_empty_chunks(self):
        with pytest.raises(ValidationError) as exc_info:
            Document(id="test.py", chunks=[])
        assert "chunks must not be empty" in str(exc_info.value)

    def test_id_with_hash(self):
        with pytest.raises(ValidationError) as exc_info:
            Document(id="test#1", chunks=[
                Chunk(id="test#1", text="hello", meta=ChunkMeta(source="test"))
            ])
        assert "document id must not contain '#'" in str(exc_info.value)

    def test_multiple_chunks(self):
        chunks = [
            Chunk(id="f#1", text="line1", meta=ChunkMeta(source="f.py", start_line=1)),
            Chunk(id="f#2", text="line2", meta=ChunkMeta(source="f.py", start_line=2)),
        ]
        doc = Document(id="f.py", chunks=chunks)
        assert len(doc.chunks) == 2

    def test_serialization_roundtrip(self, sample_chunk: Chunk):
        doc = Document(id="test.py", chunks=[sample_chunk])
        data = doc.model_dump()
        doc2 = Document(**data)
        assert doc2.id == "test.py"
        assert len(doc2.chunks) == 1


# ---------------------------------------------------------------------------
# Retrieval Layer
# ---------------------------------------------------------------------------


class TestRetrievedChunk:
    def test_valid(self, sample_chunk: Chunk):
        rc = RetrievedChunk(chunk=sample_chunk, score=0.95)
        assert rc.chunk.id == "test.py#1"
        assert rc.score == 0.95

    def test_negative_score(self):
        """Score can be negative (e.g. cosine similarity)."""
        chunk = Chunk(id="t#1", text="hi", meta=ChunkMeta(source="t"))
        rc = RetrievedChunk(chunk=chunk, score=-0.5)
        assert rc.score == -0.5

    def test_serialization_roundtrip(self, sample_chunk: Chunk):
        rc = RetrievedChunk(chunk=sample_chunk, score=0.95)
        data = rc.model_dump()
        rc2 = RetrievedChunk(**data)
        assert rc2.score == 0.95
        assert rc2.chunk.id == "test.py#1"


class TestFusionResult:
    def test_valid(self, sample_chunk: Chunk):
        rc = RetrievedChunk(chunk=sample_chunk, score=0.9)
        fr = FusionResult(chunks=[rc], sources={"vector": 1})
        assert len(fr.chunks) == 1
        assert fr.sources == {"vector": 1}

    def test_empty_chunks(self):
        fr = FusionResult(chunks=[], sources={})
        assert fr.chunks == []
        assert fr.sources == {}

    def test_default_sources(self, sample_chunk: Chunk):
        rc = RetrievedChunk(chunk=sample_chunk, score=0.9)
        fr = FusionResult(chunks=[rc])
        assert fr.sources == {}

    def test_serialization_roundtrip(self, sample_chunk: Chunk):
        rc = RetrievedChunk(chunk=sample_chunk, score=0.9)
        fr = FusionResult(chunks=[rc], sources={"vector": 1, "keyword": 2})
        data = fr.model_dump()
        fr2 = FusionResult(**data)
        assert fr2.sources == {"vector": 1, "keyword": 2}


class TestRerankResult:
    def test_valid(self, sample_chunk: Chunk):
        rc = RetrievedChunk(chunk=sample_chunk, score=0.9)
        rr = RerankResult(chunks=[rc], reranker_name="cross-encoder", latency_ms=150.0)
        assert rr.reranker_name == "cross-encoder"
        assert rr.latency_ms == 150.0

    def test_defaults(self, sample_chunk: Chunk):
        rc = RetrievedChunk(chunk=sample_chunk, score=0.9)
        rr = RerankResult(chunks=[rc])
        assert rr.reranker_name == ""
        assert rr.latency_ms == 0.0

    def test_serialization_roundtrip(self, sample_chunk: Chunk):
        rc = RetrievedChunk(chunk=sample_chunk, score=0.9)
        rr = RerankResult(chunks=[rc], reranker_name="ce", latency_ms=100.0)
        data = rr.model_dump()
        rr2 = RerankResult(**data)
        assert rr2.latency_ms == 100.0


# ---------------------------------------------------------------------------
# Agent Layer
# ---------------------------------------------------------------------------


class TestObservation:
    def test_valid(self):
        obs = Observation(content="Found 3 results", tool_name="query", latency_ms=50.0)
        assert obs.content == "Found 3 results"
        assert obs.tool_name == "query"
        assert obs.latency_ms == 50.0

    def test_defaults(self):
        obs = Observation(content="hello")
        assert obs.tool_name is None
        assert obs.tool_args is None
        assert obs.latency_ms == 0.0

    def test_serialization_roundtrip(self):
        obs = Observation(content="x", tool_name="t", tool_args={"a": 1}, latency_ms=10.0)
        data = obs.model_dump()
        obs2 = Observation(**data)
        assert obs2.tool_args == {"a": 1}


class TestStep:
    def test_valid(self):
        step = Step(thought="I should search", action='{"tool": "query"}')
        assert step.thought == "I should search"
        assert step.observation is None

    def test_with_observation(self):
        obs = Observation(content="results")
        step = Step(thought="search", action="query", observation=obs)
        assert step.observation is not None
        assert step.observation.content == "results"

    def test_serialization_roundtrip(self):
        step = Step(thought="t", action="a", observation=Observation(content="o"))
        data = step.model_dump()
        step2 = Step(**data)
        assert step2.observation.content == "o"


class TestPlan:
    def test_valid(self, sample_step: Step):
        plan = Plan(query="how does X work?", steps=[sample_step])
        assert plan.query == "how does X work?"
        assert plan.estimated_complexity == "medium"

    def test_complexity_low(self, sample_step: Step):
        plan = Plan(query="q", steps=[sample_step], estimated_complexity="low")
        assert plan.estimated_complexity == "low"

    def test_complexity_high(self, sample_step: Step):
        plan = Plan(query="q", steps=[sample_step], estimated_complexity="high")
        assert plan.estimated_complexity == "high"

    def test_invalid_complexity(self, sample_step: Step):
        with pytest.raises(ValidationError) as exc_info:
            Plan(query="q", steps=[sample_step], estimated_complexity="extreme")
        assert "estimated_complexity must be low, medium, or high" in str(exc_info.value)

    def test_empty_steps(self):
        plan = Plan(query="simple question", steps=[])
        assert plan.steps == []

    def test_serialization_roundtrip(self, sample_step: Step):
        plan = Plan(query="q", steps=[sample_step], estimated_complexity="high")
        data = plan.model_dump()
        plan2 = Plan(**data)
        assert plan2.estimated_complexity == "high"


class TestAgentResult:
    def test_valid(self, sample_step: Step):
        plan = Plan(query="q", steps=[sample_step])
        result = AgentResult(plan=plan, answer="The answer is 42")
        assert result.answer == "The answer is 42"
        assert result.sources == []
        assert result.metadata == {}

    def test_with_sources_and_metadata(self, sample_step: Step):
        plan = Plan(query="q", steps=[sample_step])
        result = AgentResult(
            plan=plan,
            answer="ans",
            sources=[ChunkMeta(source="a.py")],
            metadata={"tokens": 100},
        )
        assert len(result.sources) == 1
        assert result.metadata == {"tokens": 100}

    def test_serialization_roundtrip(self, sample_step: Step):
        plan = Plan(query="q", steps=[sample_step])
        result = AgentResult(plan=plan, answer="ans")
        data = result.model_dump()
        result2 = AgentResult(**data)
        assert result2.answer == "ans"


# ---------------------------------------------------------------------------
# Tool Layer
# ---------------------------------------------------------------------------


class TestTool:
    def test_valid(self):
        tool = Tool(name="query", description="Search the index")
        assert tool.name == "query"
        assert tool.parameters == {}

    def test_with_parameters(self):
        tool = Tool(
            name="query",
            description="Search",
            parameters={"type": "object", "properties": {"q": {"type": "string"}}},
        )
        assert tool.parameters["type"] == "object"

    def test_serialization_roundtrip(self):
        tool = Tool(name="t", description="d", parameters={"a": 1})
        data = tool.model_dump()
        tool2 = Tool(**data)
        assert tool2.name == "t"


class TestToolCall:
    def test_valid(self):
        tc = ToolCall(tool="query", arguments={"q": "hello"})
        assert tc.tool == "query"
        assert tc.arguments == {"q": "hello"}

    def test_serialization_roundtrip(self):
        tc = ToolCall(tool="t", arguments={"a": 1})
        data = tc.model_dump()
        tc2 = ToolCall(**data)
        assert tc2.arguments == {"a": 1}


class TestToolResult:
    def test_success(self):
        tr = ToolResult(tool="query", output="results", latency_ms=30.0)
        assert tr.error is None
        assert tr.output == "results"

    def test_error(self):
        tr = ToolResult(tool="query", output=None, error="timeout")
        assert tr.error == "timeout"

    def test_defaults(self):
        tr = ToolResult(tool="t", output="o")
        assert tr.error is None
        assert tr.latency_ms == 0.0

    def test_serialization_roundtrip(self):
        tr = ToolResult(tool="t", output={"a": 1}, error="e", latency_ms=10.0)
        data = tr.model_dump()
        tr2 = ToolResult(**data)
        assert tr2.error == "e"
        assert tr2.output == {"a": 1}


# ---------------------------------------------------------------------------
# Skill Layer
# ---------------------------------------------------------------------------


class TestSkillLevel:
    def test_enum_values(self):
        assert SkillLevel.BASIC == "basic"
        assert SkillLevel.INTERMEDIATE == "intermediate"
        assert SkillLevel.ADVANCED == "advanced"


class TestSkillConfig:
    def test_defaults(self):
        sc = SkillConfig(name="coding")
        assert sc.name == "coding"
        assert sc.level == SkillLevel.BASIC
        assert sc.enabled is True
        assert sc.tools == []

    def test_with_level(self):
        sc = SkillConfig(name="coding", level=SkillLevel.ADVANCED)
        assert sc.level == SkillLevel.ADVANCED

    def test_with_tools(self):
        sc = SkillConfig(name="coding", tools=["query", "analyze"])
        assert sc.tools == ["query", "analyze"]

    def test_serialization_roundtrip(self):
        sc = SkillConfig(name="x", level=SkillLevel.INTERMEDIATE, enabled=False)
        data = sc.model_dump()
        sc2 = SkillConfig(**data)
        assert sc2.level == "intermediate"
        assert sc2.enabled is False


# ---------------------------------------------------------------------------
# MCP Layer
# ---------------------------------------------------------------------------


class TestMCPHealthStatus:
    def test_enum_values(self):
        assert MCPHealthStatus.HEALTHY == "healthy"
        assert MCPHealthStatus.DEGRADED == "degraded"
        assert MCPHealthStatus.DOWN == "down"
        assert MCPHealthStatus.FAILED == "failed"


class TestMCPServerConfig:
    def test_minimal(self):
        cfg = MCPServerConfig(name="my-server", command="python server.py")
        assert cfg.name == "my-server"
        assert cfg.command == "python server.py"
        assert cfg.args == []
        assert cfg.env == {}
        assert cfg.enabled is True
        assert cfg.timeout == 30.0
        assert cfg.max_startup_time == 10.0
        assert cfg.fallback_tools == []

    def test_full(self):
        cfg = MCPServerConfig(
            name="s",
            command="cmd",
            args=["--port", "8080"],
            env={"KEY": "val"},
            enabled=False,
            timeout=60.0,
            max_startup_time=20.0,
            fallback_tools=["local_query"],
        )
        assert cfg.args == ["--port", "8080"]
        assert cfg.env == {"KEY": "val"}
        assert cfg.fallback_tools == ["local_query"]

    def test_serialization_roundtrip(self):
        cfg = MCPServerConfig(name="s", command="c", args=["a"])
        data = cfg.model_dump()
        cfg2 = MCPServerConfig(**data)
        assert cfg2.args == ["a"]


class TestMCPSettings:
    def test_defaults(self):
        settings = MCPSettings()
        assert settings.enabled is True
        assert settings.health_check_interval == 30.0
        assert settings.connection_timeout == 5.0
        assert settings.degraded_threshold == 2
        assert settings.down_threshold == 5
        assert settings.auto_restart is False
        assert settings.servers == []

    def test_with_servers(self):
        server = MCPServerConfig(name="s1", command="cmd")
        settings = MCPSettings(servers=[server])
        assert len(settings.servers) == 1
        assert settings.servers[0].name == "s1"

    def test_serialization_roundtrip(self):
        server = MCPServerConfig(name="s1", command="cmd")
        settings = MCPSettings(servers=[server], auto_restart=True)
        data = settings.model_dump()
        settings2 = MCPSettings(**data)
        assert settings2.auto_restart is True
        assert len(settings2.servers) == 1


# ---------------------------------------------------------------------------
# Cross-model integration
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_agent_result_pipeline(self):
        """Build a complete AgentResult with nested models."""
        chunk = Chunk(
            id="src/main.py#1",
            text="def main(): pass",
            meta=ChunkMeta(source="src/main.py", start_line=1, end_line=1),
        )
        retrieved = RetrievedChunk(chunk=chunk, score=0.95)
        fusion = FusionResult(chunks=[retrieved], sources={"vector": 1})

        obs = Observation(content=f"Found {len(fusion.chunks)} chunks")
        step = Step(thought="Search index", action="retrieve", observation=obs)
        plan = Plan(query="how does main work?", steps=[step], estimated_complexity="low")
        result = AgentResult(
            plan=plan,
            answer="Main is the entry point.",
            sources=[chunk.meta],
            metadata={"chunks_found": len(fusion.chunks)},
        )

        # Serialize and deserialize
        data = result.model_dump(mode="json")
        result2 = AgentResult(**data)
        assert result2.answer == "Main is the entry point."
        assert result2.plan.estimated_complexity == "low"
        assert len(result2.sources) == 1
