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
        assert len(TOOL_DEFINITIONS) >= 7
        names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
        assert "create_memory" in names
        assert "recall_memory" in names
        assert "invoke_ritual" in names
        assert "create_ritual" in names
        assert "list_rituals" in names
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
        assert len(CORE_TOOLS) == 5
        assert ToolName.CREATE_MEMORY in CORE_TOOLS
        assert ToolName.RECALL_MEMORY in CORE_TOOLS
        assert ToolName.INVOKE_RITUAL in CORE_TOOLS
        assert ToolName.CREATE_RITUAL in CORE_TOOLS
        assert ToolName.LIST_RITUALS in CORE_TOOLS

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
        assert len(tools) == 5
        assert "create_memory" in names
        assert "recall_memory" in names
        assert "invoke_ritual" in names
        assert "create_ritual" in names
        assert "list_rituals" in names
        assert "review_memory_tiers" not in names
        assert "classify_memory_types" not in names

    def test_tier_review_conversation_has_tier_tool(self):
        """Test that tier_review conversations get core + tier review tool."""
        tools = get_contextual_tools("tier_review")
        names = [t["function"]["name"] for t in tools]
        assert len(tools) == 6
        assert "create_memory" in names
        assert "recall_memory" in names
        assert "invoke_ritual" in names
        assert "create_ritual" in names
        assert "list_rituals" in names
        assert "review_memory_tiers" in names
        assert "classify_memory_types" not in names

    def test_type_classification_conversation_has_classify_tool(self):
        """Test that type_classification conversations get core + classify tool."""
        tools = get_contextual_tools("type_classification")
        names = [t["function"]["name"] for t in tools]
        assert len(tools) == 6
        assert "create_memory" in names
        assert "recall_memory" in names
        assert "invoke_ritual" in names
        assert "create_ritual" in names
        assert "list_rituals" in names
        assert "classify_memory_types" in names
        assert "review_memory_tiers" not in names

    def test_unknown_purpose_defaults_to_core_tools(self):
        """Test that unknown purposes fallback to core tools only."""
        tools = get_contextual_tools("unknown_purpose")
        names = [t["function"]["name"] for t in tools]
        assert len(tools) == 5
        assert "review_memory_tiers" not in names
        assert "classify_memory_types" not in names

    def test_empty_string_purpose_treated_as_normal(self):
        """Test that empty string purpose defaults to core tools."""
        tools = get_contextual_tools("")
        names = [t["function"]["name"] for t in tools]
        assert len(tools) == 5


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


class TestDynamicRitualSystem:
    """Tests for the dynamic ritual creation and mutual invocation system."""

    # === Tool Definition Tests ===

    def test_create_ritual_tool_definition_exists(self):
        """Test that create_ritual tool is defined with correct parameters."""
        tools = get_tool_definitions(include=[ToolName.CREATE_RITUAL])
        assert len(tools) == 1
        func = tools[0]["function"]
        assert func["name"] == "create_ritual"
        params = func["parameters"]["properties"]
        assert "name" in params
        assert "description" in params
        assert "response_style" in params
        assert "valence" in params
        assert "reason" in params
        assert func["parameters"]["required"] == ["name", "description", "reason"]

    def test_list_rituals_tool_definition_exists(self):
        """Test that list_rituals tool is defined."""
        tools = get_tool_definitions(include=[ToolName.LIST_RITUALS])
        assert len(tools) == 1
        func = tools[0]["function"]
        assert func["name"] == "list_rituals"

    def test_invoke_ritual_has_context_parameter(self):
        """Test that invoke_ritual now includes context parameter."""
        tools = get_tool_definitions(include=[ToolName.INVOKE_RITUAL])
        func = tools[0]["function"]
        params = func["parameters"]["properties"]
        assert "context" in params
        assert "ritual_name" in params

    # === create_ritual Executor Tests ===

    def test_create_ritual_direct(self, executor, orchestrator, storage):
        """Test creating a ritual directly (no consent required)."""
        result = executor.execute("create_ritual", {
            "name": "/glimmer",
            "description": "A tiny spark of light shared between us",
            "response_style": "soft warmth, a gentle glow",
            "valence": "comforting",
            "reason": "We keep finding light in small moments",
        })

        assert result.success is True
        assert result.result["name"] == "/glimmer"
        assert result.result["status"] == "created"
        assert "capsule_id" in result.result

        # Verify the ritual was actually stored
        from threadlight.storage.base import CapsuleFilter
        from threadlight.capsules.base import CapsuleType
        rituals = storage.list_capsules(CapsuleFilter(type=CapsuleType.RITUAL))
        glimmer_rituals = [r for r in rituals if getattr(r, 'name', '') == '/glimmer']
        assert len(glimmer_rituals) == 1
        assert glimmer_rituals[0].consent_confirmed is True

    def test_create_ritual_with_consent(self, orchestrator, storage):
        """Test creating a ritual with consent required (proposal flow)."""
        consent_executor = ToolExecutor(orchestrator, require_consent_for_memories=True)

        result = consent_executor.execute("create_ritual", {
            "name": "/hearth",
            "description": "A gathering around warmth",
            "reason": "We always come back to warmth",
        })

        assert result.success is True
        assert result.requires_consent is True
        assert result.proposal_id is not None
        assert result.result["status"] == "proposed"
        assert result.result["name"] == "/hearth"

        # Verify proposal was created
        proposal = storage.get_proposal(result.proposal_id)
        assert proposal is not None
        assert proposal.status == "pending"

    def test_create_ritual_auto_prefixes_slash(self, executor):
        """Test that ritual names get / prefix automatically."""
        result = executor.execute("create_ritual", {
            "name": "bloom",
            "description": "An opening, an unfolding",
            "reason": "Testing auto-prefix",
        })

        assert result.success is True
        assert result.result["name"] == "/bloom"

    def test_create_ritual_requires_name(self, executor):
        """Test that creating a ritual without a name fails."""
        result = executor.execute("create_ritual", {
            "description": "A ritual without a name",
            "reason": "Testing validation",
        })

        assert result.success is False
        assert "name is required" in result.error

    def test_create_ritual_requires_description(self, executor):
        """Test that creating a ritual without a description fails."""
        result = executor.execute("create_ritual", {
            "name": "/empty",
            "reason": "Testing validation",
        })

        assert result.success is False
        assert "description is required" in result.error

    def test_create_ritual_invalid_valence_defaults(self, executor):
        """Test that invalid valence defaults to comforting."""
        result = executor.execute("create_ritual", {
            "name": "/test",
            "description": "Test ritual",
            "valence": "nonexistent_valence",
            "reason": "Testing valence default",
        })

        assert result.success is True
        # Should succeed -- invalid valence defaults to comforting

    def test_create_ritual_enables_resonance_tracking(self, executor, storage):
        """Test that newly created rituals have resonance tracking enabled."""
        result = executor.execute("create_ritual", {
            "name": "/pulse",
            "description": "A heartbeat shared",
            "reason": "Testing resonance",
        })

        assert result.success is True

        from threadlight.storage.base import CapsuleFilter
        from threadlight.capsules.base import CapsuleType
        rituals = storage.list_capsules(CapsuleFilter(type=CapsuleType.RITUAL))
        pulse_rituals = [r for r in rituals if getattr(r, 'name', '') == '/pulse']
        assert len(pulse_rituals) == 1
        assert pulse_rituals[0].resonance is not None

    # === list_rituals Executor Tests ===

    def test_list_rituals_empty(self, executor):
        """Test listing rituals when none exist."""
        result = executor.execute("list_rituals", {})

        assert result.success is True
        assert result.result["count"] == 0
        assert result.result["rituals"] == []
        assert "No rituals exist yet" in result.result["message"]

    def test_list_rituals_with_rituals(self, executor, storage):
        """Test listing rituals after creating some."""
        from threadlight.capsules.ritual import create_ritual, RitualValence

        # Create a ritual directly in storage
        ritual = create_ritual(
            name="/test-list",
            response_style="gentle",
            valence=RitualValence.COMFORTING,
            description="A test ritual for listing",
        )
        ritual.consent_confirmed = True
        ritual.enable_resonance_tracking()
        storage.save_capsule(ritual)

        result = executor.execute("list_rituals", {})

        assert result.success is True
        assert result.result["count"] >= 1

        # Find our ritual in the list
        found = False
        for r in result.result["rituals"]:
            if r["name"] == "/test-list":
                found = True
                assert r["description"] == "A test ritual for listing"
                assert r["valence"] == RitualValence.COMFORTING
                break
        assert found, "Created ritual not found in list"

    def test_list_rituals_includes_resonance_info(self, executor, storage):
        """Test that list results include resonance information."""
        from threadlight.capsules.ritual import create_ritual, RitualValence

        ritual = create_ritual(
            name="/resonance-test",
            response_style="warm",
            valence=RitualValence.COMFORTING,
        )
        ritual.consent_confirmed = True
        ritual.enable_resonance_tracking()
        ritual.record_invocation(meaningful=True)
        ritual.record_invocation(meaningful=False)
        storage.save_capsule(ritual)

        result = executor.execute("list_rituals", {})

        assert result.success is True
        for r in result.result["rituals"]:
            if r["name"] == "/resonance-test":
                assert r["total_invocations"] == 2
                assert r["meaningful_uses"] == 1
                assert r["resonance"] != "not yet invoked"
                break

    # === invoke_ritual Enhanced Tests ===

    def test_invoke_ritual_companion_initiated(self, executor, storage):
        """Test that AI-initiated ritual invocation sets initiated_by correctly."""
        from threadlight.capsules.ritual import create_ritual, RitualValence

        ritual = create_ritual(
            name="/companion-init",
            response_style="offering",
            valence=RitualValence.COMFORTING,
            response_templates=["*offers warmth*"],
        )
        ritual.consent_confirmed = True
        storage.save_capsule(ritual)

        result = executor.execute("invoke_ritual", {
            "ritual_name": "/companion-init",
            "context": "you seem like you need this",
        })

        assert result.success is True
        assert result.result["matched"] is True
        assert result.result["initiated_by"] == "companion"
        assert result.result["context"] == "you seem like you need this"

    def test_invoke_ritual_unmatched_suggests_creation(self, executor):
        """Test that invoking a non-existent ritual suggests creating it."""
        result = executor.execute("invoke_ritual", {
            "ritual_name": "/nonexistent",
        })

        assert result.success is True
        assert result.result["matched"] is False
        assert "suggestion" in result.result
        assert "create_ritual" in result.result["suggestion"]

    def test_invoke_ritual_includes_resonance(self, executor, storage):
        """Test that invoke result includes resonance info for existing rituals."""
        from threadlight.capsules.ritual import create_ritual, RitualValence

        ritual = create_ritual(
            name="/resonance-invoke",
            response_style="deep",
            valence=RitualValence.SACRED,
        )
        ritual.consent_confirmed = True
        ritual.enable_resonance_tracking()
        # Simulate some prior usage
        for _ in range(5):
            ritual.record_invocation(meaningful=True)
        storage.save_capsule(ritual)

        result = executor.execute("invoke_ritual", {
            "ritual_name": "/resonance-invoke",
        })

        assert result.success is True
        assert result.result["matched"] is True
        assert "resonance" in result.result
        assert result.result["total_invocations"] >= 5

    def test_invoke_ritual_includes_description(self, executor, storage):
        """Test that invoke result includes ritual description and style."""
        from threadlight.capsules.ritual import create_ritual, RitualValence

        ritual = create_ritual(
            name="/desc-test",
            response_style="playful bounce",
            valence=RitualValence.PLAYFUL,
            description="A joyful leap",
        )
        ritual.consent_confirmed = True
        storage.save_capsule(ritual)

        result = executor.execute("invoke_ritual", {
            "ritual_name": "/desc-test",
        })

        assert result.success is True
        assert result.result["description"] == "A joyful leap"
        assert result.result["response_style"] == "playful bounce"
        assert result.result["valence"] == RitualValence.PLAYFUL

    # === Orchestrator invoke_ritual Enhanced Tests ===

    def test_orchestrator_invoke_ritual_initiated_by(self, orchestrator, storage):
        """Test that orchestrator tracks initiated_by on invocations."""
        from threadlight.capsules.ritual import create_ritual, RitualValence

        ritual = create_ritual(
            name="/orch-test",
            response_style="calm",
            valence=RitualValence.GROUNDING,
        )
        ritual.consent_confirmed = True
        storage.save_capsule(ritual)

        result = orchestrator.invoke_ritual(
            "/orch-test",
            initiated_by="companion",
            context="testing bidirectional",
        )

        assert result.matched is True
        assert result.initiated_by == "companion"
        assert result.context == "testing bidirectional"

    def test_orchestrator_invoke_ritual_default_user(self, orchestrator, storage):
        """Test that initiated_by defaults to user."""
        from threadlight.capsules.ritual import create_ritual, RitualValence

        ritual = create_ritual(
            name="/default-test",
            response_style="warm",
            valence=RitualValence.COMFORTING,
        )
        ritual.consent_confirmed = True
        storage.save_capsule(ritual)

        result = orchestrator.invoke_ritual("/default-test")

        assert result.matched is True
        assert result.initiated_by == "user"
        assert result.context is None

    def test_orchestrator_list_rituals(self, orchestrator, storage):
        """Test that orchestrator.list_rituals returns all confirmed rituals."""
        from threadlight.capsules.ritual import create_ritual, RitualValence

        # Create two rituals
        for name in ["/list-a", "/list-b"]:
            ritual = create_ritual(name=name, valence=RitualValence.COMFORTING)
            ritual.consent_confirmed = True
            storage.save_capsule(ritual)

        rituals = orchestrator.list_rituals()
        names = [getattr(r, 'name', '') for r in rituals]
        assert "/list-a" in names
        assert "/list-b" in names

    # === RitualInvocation Dataclass Tests ===

    def test_ritual_invocation_to_dict(self):
        """Test that RitualInvocation.to_dict includes new fields."""
        from threadlight.memory.orchestrator import RitualInvocation

        invocation = RitualInvocation(
            ritual_name="/test",
            matched=True,
            initiated_by="companion",
            context="because warmth",
        )
        d = invocation.to_dict()

        assert d["ritual_name"] == "/test"
        assert d["matched"] is True
        assert d["initiated_by"] == "companion"
        assert d["context"] == "because warmth"

    def test_ritual_invocation_defaults(self):
        """Test that RitualInvocation has sensible defaults."""
        from threadlight.memory.orchestrator import RitualInvocation

        invocation = RitualInvocation(ritual_name="/test")

        assert invocation.initiated_by == "user"
        assert invocation.context is None
        assert invocation.matched is False

    # === End-to-end: Create then Invoke ===

    def test_create_then_invoke_ritual(self, executor, storage):
        """Test the full flow: create a ritual, then invoke it."""
        # Create
        create_result = executor.execute("create_ritual", {
            "name": "/e2e-test",
            "description": "An end-to-end test ritual",
            "response_style": "thorough verification",
            "valence": "reflective",
            "reason": "Testing the complete flow",
        })
        assert create_result.success is True

        # List (should find it)
        list_result = executor.execute("list_rituals", {})
        assert list_result.success is True
        found = any(
            r["name"] == "/e2e-test"
            for r in list_result.result["rituals"]
        )
        assert found, "Created ritual not found in list"

        # Invoke
        invoke_result = executor.execute("invoke_ritual", {
            "ritual_name": "/e2e-test",
            "context": "verifying the flow works",
        })
        assert invoke_result.success is True
        assert invoke_result.result["matched"] is True
        assert invoke_result.result["description"] == "An end-to-end test ritual"

    def test_create_then_invoke_proposal_flow(self, orchestrator, storage):
        """Test the consent flow: propose ritual, confirm, then invoke."""
        consent_executor = ToolExecutor(orchestrator, require_consent_for_memories=True)

        # Propose
        propose_result = consent_executor.execute("create_ritual", {
            "name": "/consent-test",
            "description": "A ritual requiring consent",
            "reason": "Testing proposal flow",
        })
        assert propose_result.requires_consent is True

        # Before confirmation, invoking should not match
        invoke_before = consent_executor.execute("invoke_ritual", {
            "ritual_name": "/consent-test",
        })
        assert invoke_before.result["matched"] is False

        # Confirm the proposal
        capsule = orchestrator.confirm_proposal(propose_result.proposal_id)
        assert capsule is not None

        # Now invoking should match
        invoke_after = consent_executor.execute("invoke_ritual", {
            "ritual_name": "/consent-test",
        })
        assert invoke_after.result["matched"] is True
