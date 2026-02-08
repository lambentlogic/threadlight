"""Tests for the tool executor and tool definitions."""

import pytest
import json

from threadlight.tools.definitions import (
    TOOL_DEFINITIONS,
    get_tool_definitions,
    get_contextual_tools,
    CORE_TOOLS,
    CONTEXTUAL_TOOLS,
    ToolName,
)
from threadlight.tools.executor import ToolExecutor, ToolResult, execute_tool_call
from threadlight.memory.orchestrator import MemoryOrchestrator
from threadlight.storage.memory import InMemoryStorage
from threadlight.decay.engine import DecayEngine, LinearDecayStrategy
from threadlight.capsules.base import MemoryTier


@pytest.fixture
def storage():
    """Create in-memory storage."""
    s = InMemoryStorage()
    s.initialize()
    yield s
    s.close()


@pytest.fixture
def decay_engine(storage):
    """Create decay engine."""
    return DecayEngine(
        storage=storage,
        strategy=LinearDecayStrategy(),
        min_age_hours=0,
    )


@pytest.fixture
def orchestrator(storage, decay_engine):
    """Create memory orchestrator."""
    return MemoryOrchestrator(
        storage=storage,
        decay_engine=decay_engine,
    )


@pytest.fixture
def executor(orchestrator):
    """Create tool executor."""
    return ToolExecutor(orchestrator, require_consent_for_memories=False)


class TestToolDefinitions:
    def test_tool_definitions_exist(self):
        """Test that tool definitions are defined."""
        assert len(TOOL_DEFINITIONS) >= 4
        names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
        assert "create_memory" in names
        assert "recall_memory" in names
        assert "invoke_ritual" in names
        assert "review_memory_tiers" in names

    def test_get_tool_definitions_include(self):
        """Test filtering tool definitions by include."""
        tools = get_tool_definitions(include=[ToolName.CREATE_MEMORY])
        assert len(tools) == 1
        assert tools[0]["function"]["name"] == "create_memory"

    def test_get_tool_definitions_exclude(self):
        """Test filtering tool definitions by exclude."""
        tools = get_tool_definitions(exclude=[ToolName.INVOKE_RITUAL])
        names = [t["function"]["name"] for t in tools]
        assert "invoke_ritual" not in names

    def test_review_memory_tiers_definition(self):
        """Test that review_memory_tiers tool is properly defined."""
        tool = next(
            (t for t in TOOL_DEFINITIONS if t["function"]["name"] == "review_memory_tiers"),
            None
        )
        assert tool is not None

        func = tool["function"]
        assert "action" in func["parameters"]["properties"]
        assert "tier_assignments" in func["parameters"]["properties"]
        assert func["parameters"]["required"] == ["action"]


class TestContextualTools:
    """Test contextual tool filtering for different conversation purposes."""

    def test_core_tools_defined(self):
        """Test that core tools are properly defined."""
        assert len(CORE_TOOLS) == 3
        assert ToolName.CREATE_MEMORY in CORE_TOOLS
        assert ToolName.RECALL_MEMORY in CORE_TOOLS
        assert ToolName.INVOKE_RITUAL in CORE_TOOLS

    def test_contextual_tools_defined(self):
        """Test that contextual tools mapping is properly defined."""
        assert "tier_review" in CONTEXTUAL_TOOLS
        assert "type_classification" in CONTEXTUAL_TOOLS
        assert ToolName.REVIEW_MEMORY_TIERS in CONTEXTUAL_TOOLS["tier_review"]
        assert ToolName.CLASSIFY_MEMORY_TYPES in CONTEXTUAL_TOOLS["type_classification"]

    def test_normal_conversation_has_core_tools_only(self):
        """Test that normal conversations (None purpose) get only core tools."""
        tools = get_contextual_tools(None)
        names = [t["function"]["name"] for t in tools]
        assert len(tools) == 3
        assert "create_memory" in names
        assert "recall_memory" in names
        assert "invoke_ritual" in names
        assert "review_memory_tiers" not in names
        assert "classify_memory_types" not in names

    def test_tier_review_conversation_has_tier_tool(self):
        """Test that tier_review conversations get core + tier review tool."""
        tools = get_contextual_tools("tier_review")
        names = [t["function"]["name"] for t in tools]
        assert len(tools) == 4
        assert "create_memory" in names
        assert "recall_memory" in names
        assert "invoke_ritual" in names
        assert "review_memory_tiers" in names
        assert "classify_memory_types" not in names

    def test_type_classification_conversation_has_classify_tool(self):
        """Test that type_classification conversations get core + classify tool."""
        tools = get_contextual_tools("type_classification")
        names = [t["function"]["name"] for t in tools]
        assert len(tools) == 4
        assert "create_memory" in names
        assert "recall_memory" in names
        assert "invoke_ritual" in names
        assert "classify_memory_types" in names
        assert "review_memory_tiers" not in names

    def test_unknown_purpose_defaults_to_core_tools(self):
        """Test that unknown purposes fallback to core tools only."""
        tools = get_contextual_tools("unknown_purpose")
        names = [t["function"]["name"] for t in tools]
        assert len(tools) == 3
        assert "review_memory_tiers" not in names
        assert "classify_memory_types" not in names

    def test_empty_string_purpose_treated_as_normal(self):
        """Test that empty string purpose defaults to core tools."""
        tools = get_contextual_tools("")
        names = [t["function"]["name"] for t in tools]
        assert len(tools) == 3


class TestToolResult:
    def test_tool_result_to_dict(self):
        """Test ToolResult serialization."""
        result = ToolResult(
            tool_name="test",
            success=True,
            result={"key": "value"},
        )
        data = result.to_dict()

        assert data["tool_name"] == "test"
        assert data["success"] is True
        assert data["result"] == {"key": "value"}

    def test_tool_result_to_tool_response_success(self):
        """Test ToolResult response formatting for success."""
        result = ToolResult(
            tool_name="test",
            success=True,
            result={"data": "test"},
        )
        response = result.to_tool_response()
        parsed = json.loads(response)

        assert parsed["status"] == "success"
        assert parsed["result"]["data"] == "test"

    def test_tool_result_to_tool_response_error(self):
        """Test ToolResult response formatting for error."""
        result = ToolResult(
            tool_name="test",
            success=False,
            error="Something went wrong",
        )
        response = result.to_tool_response()
        parsed = json.loads(response)

        assert "error" in parsed
        assert parsed["error"] == "Something went wrong"

    def test_tool_result_to_tool_response_proposal(self):
        """Test ToolResult response formatting for proposal."""
        result = ToolResult(
            tool_name="create_memory",
            success=True,
            requires_consent=True,
            proposal_id="test-123",
            result={"type": "relational"},
        )
        response = result.to_tool_response()
        parsed = json.loads(response)

        assert parsed["status"] == "proposal_created"
        assert parsed["proposal_id"] == "test-123"


class TestToolExecutor:
    def test_execute_unknown_tool(self, executor):
        """Test executing unknown tool returns error."""
        result = executor.execute("unknown_tool", {})

        assert result.success is False
        assert "Unknown tool" in result.error

    def test_execute_create_memory(self, executor):
        """Test executing create_memory tool."""
        result = executor.execute("create_memory", {
            "memory_type": "relational",
            "content": {"entity": "Test", "summary": "Test summary"},
            "reason": "Testing",
        })

        assert result.success is True
        assert "capsule_id" in result.result

    def test_execute_recall_memory(self, executor, orchestrator):
        """Test executing recall_memory tool."""
        # Create a memory first
        orchestrator.create(
            type="relational",
            content={"entity": "RecallTest", "summary": "Test"},
            cue_phrases=["recalltest"],
            consent_confirmed=True,
        )

        result = executor.execute("recall_memory", {"cue": "recalltest"})

        assert result.success is True
        assert result.result["count"] >= 1

    def test_execute_invoke_ritual(self, executor, orchestrator, storage):
        """Test executing invoke_ritual tool."""
        from threadlight.capsules.ritual import create_ritual, RitualValence

        ritual = create_ritual(
            name="/test-ritual",
            response_style="warm",
            valence=RitualValence.COMFORTING,
            response_templates=["*warmth*"],
        )
        ritual.consent_confirmed = True
        storage.save_capsule(ritual)

        result = executor.execute("invoke_ritual", {"ritual_name": "/test-ritual"})

        assert result.success is True
        assert result.result["matched"] is True


class TestReviewMemoryTiersTool:
    """Tests for the review_memory_tiers tool."""

    def test_list_action_returns_memories(self, executor, orchestrator):
        """Test that list action returns all memories organized by tier."""
        # Create memories in different tiers
        orchestrator.create(
            type="relational",
            content={"entity": "Anchored", "summary": "Important"},
            memory_tier="strictly_anchored",
            consent_confirmed=True,
        )
        orchestrator.create(
            type="relational",
            content={"entity": "Decaying", "summary": "Moderately important"},
            memory_tier="anchored_decaying",
            consent_confirmed=True,
        )
        orchestrator.create(
            type="relational",
            content={"entity": "Semantic", "summary": "Normal"},
            memory_tier="semantic",
            consent_confirmed=True,
        )

        result = executor.execute("review_memory_tiers", {"action": "list"})

        assert result.success is True
        assert "summary" in result.result
        assert "memories_by_tier" in result.result
        assert result.result["summary"]["total"] >= 3
        assert result.result["summary"]["strictly_anchored"] >= 1
        assert result.result["summary"]["anchored_decaying"] >= 1
        assert result.result["summary"]["semantic"] >= 1

    def test_list_action_includes_memory_details(self, executor, orchestrator):
        """Test that list action includes detailed memory info."""
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "DetailTest", "summary": "Detailed summary"},
            memory_tier="semantic",
            consent_confirmed=True,
        )

        result = executor.execute("review_memory_tiers", {"action": "list"})

        # Find our memory in the results
        semantic_memories = result.result["memories_by_tier"]["semantic"]
        our_memory = next((m for m in semantic_memories if m["id"] == capsule.id), None)

        assert our_memory is not None
        assert our_memory["type"] == "relational"
        assert "content" in our_memory
        assert "access_count" in our_memory
        assert "presence_score" in our_memory

    def test_update_action_changes_tier(self, executor, orchestrator):
        """Test that update action changes memory tiers."""
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "TierChange", "summary": "To be anchored"},
            memory_tier="semantic",
            consent_confirmed=True,
        )

        result = executor.execute("review_memory_tiers", {
            "action": "update",
            "tier_assignments": {
                capsule.id: "strictly_anchored",
            },
        })

        assert result.success is True
        assert result.result["updated"] == 1

        # Verify the tier was actually changed
        updated = orchestrator.get(capsule.id)
        assert updated.memory_tier == MemoryTier.STRICTLY_ANCHORED

    def test_update_action_batch_changes(self, executor, orchestrator):
        """Test that update action can change multiple tiers at once."""
        capsule1 = orchestrator.create(
            type="relational",
            content={"entity": "Batch1"},
            memory_tier="semantic",
            consent_confirmed=True,
        )
        capsule2 = orchestrator.create(
            type="relational",
            content={"entity": "Batch2"},
            memory_tier="semantic",
            consent_confirmed=True,
        )
        capsule3 = orchestrator.create(
            type="relational",
            content={"entity": "Batch3"},
            memory_tier="semantic",
            consent_confirmed=True,
        )

        result = executor.execute("review_memory_tiers", {
            "action": "update",
            "tier_assignments": {
                capsule1.id: "strictly_anchored",
                capsule2.id: "anchored_decaying",
                capsule3.id: "semantic",  # No change
            },
        })

        assert result.success is True
        # Only 2 should be updated (capsule3 was already semantic)
        assert result.result["updated"] == 2

        # Verify each
        assert orchestrator.get(capsule1.id).memory_tier == MemoryTier.STRICTLY_ANCHORED
        assert orchestrator.get(capsule2.id).memory_tier == MemoryTier.ANCHORED_DECAYING
        assert orchestrator.get(capsule3.id).memory_tier == MemoryTier.SEMANTIC

    def test_update_action_invalid_memory_id(self, executor):
        """Test that update action handles invalid memory IDs gracefully."""
        result = executor.execute("review_memory_tiers", {
            "action": "update",
            "tier_assignments": {
                "nonexistent-id": "strictly_anchored",
            },
        })

        assert result.success is True
        assert result.result["updated"] == 0
        assert len(result.result["errors"]) == 1
        assert "not found" in result.result["errors"][0]

    def test_update_action_invalid_tier(self, executor, orchestrator):
        """Test that update action handles invalid tier values gracefully."""
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "InvalidTier"},
            consent_confirmed=True,
        )

        result = executor.execute("review_memory_tiers", {
            "action": "update",
            "tier_assignments": {
                capsule.id: "invalid_tier_name",
            },
        })

        assert result.success is True
        assert result.result["updated"] == 0
        assert len(result.result["errors"]) == 1
        assert "Invalid tier" in result.result["errors"][0]

    def test_update_action_requires_tier_assignments(self, executor):
        """Test that update action requires tier_assignments."""
        result = executor.execute("review_memory_tiers", {"action": "update"})

        assert result.success is False
        assert "tier_assignments is required" in result.error

    def test_action_is_required(self, executor):
        """Test that action parameter is required."""
        result = executor.execute("review_memory_tiers", {})

        assert result.success is False
        assert "action is required" in result.error

    def test_invalid_action(self, executor):
        """Test that invalid action returns error."""
        result = executor.execute("review_memory_tiers", {"action": "invalid"})

        assert result.success is False
        assert "Invalid action" in result.error

    def test_mixed_success_and_errors(self, executor, orchestrator):
        """Test that tool reports partial success correctly."""
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "MixedTest"},
            memory_tier="semantic",
            consent_confirmed=True,
        )

        result = executor.execute("review_memory_tiers", {
            "action": "update",
            "tier_assignments": {
                capsule.id: "strictly_anchored",  # Valid
                "fake-id-12345": "anchored_decaying",  # Invalid
            },
        })

        assert result.success is True
        assert result.result["updated"] == 1
        assert result.result["requested"] == 2
        assert len(result.result["errors"]) == 1


class TestExecuteToolCallConvenience:
    """Tests for the execute_tool_call convenience function."""

    def test_execute_tool_call_with_dict_args(self, orchestrator):
        """Test execute_tool_call with dict arguments."""
        result = execute_tool_call(
            orchestrator,
            "review_memory_tiers",
            {"action": "list"},
        )

        assert result.success is True

    def test_execute_tool_call_with_json_string_args(self, orchestrator):
        """Test execute_tool_call with JSON string arguments."""
        result = execute_tool_call(
            orchestrator,
            "review_memory_tiers",
            '{"action": "list"}',
        )

        assert result.success is True

    def test_execute_tool_call_invalid_json(self, orchestrator):
        """Test execute_tool_call with invalid JSON."""
        result = execute_tool_call(
            orchestrator,
            "review_memory_tiers",
            "not valid json",
        )

        assert result.success is False
        assert "Invalid JSON" in result.error


class TestTextFirstMemoryCreation:
    """Tests for text-first memory creation tools (Phase 3)."""

    def test_create_memory_with_text_only(self, executor, orchestrator):
        """Test creating memory with just text parameter."""
        result = executor.execute("create_memory", {
            "text": "They shared that their cat Luna passed away last month. The grief was still fresh.",
            "reason": "Important emotional context to remember",
        })

        assert result.success is True
        assert "capsule_id" in result.result
        assert result.result["type"] == "witness"  # Should default to witness

        # Verify text was stored in the capsule
        capsule = orchestrator.get(result.result["capsule_id"])
        assert capsule is not None
        assert capsule.text is not None
        assert "Luna" in capsule.text

    def test_create_memory_with_text_and_type(self, executor, orchestrator):
        """Test creating memory with text and explicit type."""
        result = executor.execute("create_memory", {
            "text": "Alice is my best friend from college. We bonded over late-night coding sessions.",
            "memory_type": "relational",
            "reason": "Relationship context",
        })

        assert result.success is True
        capsule = orchestrator.get(result.result["capsule_id"])
        assert capsule.type.value == "relational"
        assert "Alice" in capsule.text

    def test_create_memory_with_text_and_content(self, executor, orchestrator):
        """Test creating memory with both text and structured content."""
        result = executor.execute("create_memory", {
            "text": "Alice always brings homemade cookies when we meet. It's her way of showing care.",
            "memory_type": "relational",
            "content": {"entity": "Alice", "quality": "warm"},
            "reason": "Relationship detail",
        })

        assert result.success is True
        capsule = orchestrator.get(result.result["capsule_id"])
        assert capsule.text is not None
        assert "cookies" in capsule.text
        # Structured fields should also be accessible
        assert capsule.entity == "Alice" or capsule.content.get("entity") == "Alice"

    def test_create_memory_content_only_backward_compat(self, executor, orchestrator):
        """Test backward compatibility with content-only (no text)."""
        result = executor.execute("create_memory", {
            "memory_type": "relational",
            "content": {"entity": "Bob", "summary": "Colleague who loves coffee"},
            "reason": "Work relationship",
        })

        assert result.success is True
        assert "capsule_id" in result.result

    def test_create_memory_requires_text_or_content(self, executor):
        """Test that either text or content must be provided."""
        result = executor.execute("create_memory", {
            "memory_type": "witness",
            "reason": "Should fail",
        })

        assert result.success is False
        assert "text" in result.error.lower() or "content" in result.error.lower()

    def test_create_memory_text_preview_in_result(self, executor):
        """Test that long text gets a preview in the result."""
        long_text = "This is a very long memory text. " * 20  # Over 100 chars

        result = executor.execute("create_memory", {
            "text": long_text,
            "reason": "Testing preview",
        })

        assert result.success is True
        assert "text_preview" in result.result
        assert len(result.result["text_preview"]) <= 103  # 100 + "..."

    def test_create_memory_with_text_defaults_to_witness(self, executor, orchestrator):
        """Test that memory_type defaults to 'witness' when only text is provided."""
        result = executor.execute("create_memory", {
            "text": "A moment of deep connection happened today.",
            "reason": "General memory",
        })

        assert result.success is True
        capsule = orchestrator.get(result.result["capsule_id"])
        assert capsule.type.value == "witness"

    def test_create_memory_identity_phrase_with_text(self, executor, orchestrator):
        """Test creating identity_phrase (myth_seed) with text."""
        result = executor.execute("create_memory", {
            "text": "They said 'I process through talking' and it felt like a key to understanding them.",
            "memory_type": "identity_phrase",
            "content": {"seed": "I process through talking"},
            "reason": "Core communication style",
        })

        assert result.success is True
        capsule = orchestrator.get(result.result["capsule_id"])
        # identity_phrase maps to myth_seed internally
        assert capsule.type.value == "myth_seed"
        assert capsule.text is not None

    def test_create_memory_proposal_includes_text(self, orchestrator):
        """Test that proposals created with consent include text."""
        from threadlight.tools.executor import ToolExecutor

        executor = ToolExecutor(orchestrator, require_consent_for_memories=True)

        result = executor.execute("create_memory", {
            "text": "Something important to propose remembering.",
            "reason": "Testing proposals",
        })

        assert result.success is True
        assert result.requires_consent is True
        assert "text" in result.result
        assert result.result["text"] == "Something important to propose remembering."


class TestToolDefinitionsTextFirst:
    """Tests for tool definitions with text-first updates."""

    def test_create_memory_has_text_parameter(self):
        """Test that create_memory tool definition includes text parameter."""
        tool = next(
            (t for t in TOOL_DEFINITIONS if t["function"]["name"] == "create_memory"),
            None
        )
        assert tool is not None

        properties = tool["function"]["parameters"]["properties"]
        assert "text" in properties
        assert "string" == properties["text"]["type"]

    def test_create_memory_text_is_prominent_in_description(self):
        """Test that create_memory description emphasizes text-first approach."""
        tool = next(
            (t for t in TOOL_DEFINITIONS if t["function"]["name"] == "create_memory"),
            None
        )
        assert tool is not None

        description = tool["function"]["description"].lower()
        assert "text" in description
        assert "narrative" in description

    def test_create_memory_only_requires_reason(self):
        """Test that only 'reason' is strictly required (text or content needed)."""
        tool = next(
            (t for t in TOOL_DEFINITIONS if t["function"]["name"] == "create_memory"),
            None
        )
        assert tool is not None

        required = tool["function"]["parameters"]["required"]
        assert "reason" in required
        # Neither text nor content should be required at schema level
        # (validation happens at execution time)
        assert "text" not in required
        assert "content" not in required


class TestRecallMemoryReturnsText:
    """Tests that recall_memory includes the text field for all capsule types."""

    def test_recall_relational_includes_text(self, executor, orchestrator):
        """Test that recalled relational capsules include the text field."""
        orchestrator.create(
            type="relational",
            content={"entity": "Alice", "summary": "Best friend"},
            cue_phrases=["alice"],
            consent_confirmed=True,
        )

        result = executor.execute("recall_memory", {"cue": "alice"})

        assert result.success is True
        assert result.result["count"] >= 1
        memory = result.result["memories"][0]
        assert "text" in memory
        assert memory["text"] != ""
        assert "Alice" in memory["text"]

    def test_recall_myth_seed_includes_text(self, executor, orchestrator):
        """Test that recalled myth_seed capsules include the text field."""
        orchestrator.create(
            type="myth_seed",
            content={"seed": "Curiosity drives understanding"},
            cue_phrases=["curiosity"],
            consent_confirmed=True,
        )

        result = executor.execute("recall_memory", {"cue": "curiosity"})

        assert result.success is True
        assert result.result["count"] >= 1
        memory = result.result["memories"][0]
        assert "text" in memory
        assert memory["text"] != ""
        assert "Curiosity" in memory["text"]

    def test_recall_witness_includes_text(self, executor, orchestrator):
        """Test that recalled witness capsules include the text field."""
        orchestrator.create(
            type="witness",
            content={"moment": "Shared a meaningful silence", "feeling": "connected"},
            cue_phrases=["silence"],
            consent_confirmed=True,
        )

        result = executor.execute("recall_memory", {"cue": "silence"})

        assert result.success is True
        assert result.result["count"] >= 1
        memory = result.result["memories"][0]
        assert "text" in memory
        assert memory["text"] != ""

    def test_recall_with_explicit_text_returns_it(self, executor, orchestrator):
        """Test that capsules created with explicit text return that text."""
        orchestrator.create(
            type="relational",
            content={
                "entity": "Jericho",
                "summary": "Creative sibling",
                "text": "Jericho is my creative sibling who loves messy art projects.",
            },
            cue_phrases=["jericho"],
            consent_confirmed=True,
        )

        result = executor.execute("recall_memory", {"cue": "jericho"})

        assert result.success is True
        assert result.result["count"] >= 1
        memory = result.result["memories"][0]
        assert "text" in memory
        assert "messy art" in memory["text"]

    def test_recall_empty_results_have_text_field(self, executor):
        """Test that even empty recall results return properly (no text key errors)."""
        result = executor.execute("recall_memory", {"cue": "nonexistent_memory_xyz"})

        assert result.success is True
        assert result.result["count"] == 0
        assert result.result["memories"] == []
