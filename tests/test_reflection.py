"""Tests for the reflection / solitude-loop feature."""

import pytest
from unittest.mock import MagicMock, patch

from threadlight.capsules.base import CapsuleType
from threadlight.capsules.reflection import ReflectionCapsule, create_reflection
from threadlight.capsules.factory import create_capsule
from threadlight.core import Threadlight
from threadlight.providers.base import ProviderResponse
from threadlight.reflection.prompts import (
    compose_reflection_prompt,
    extract_themes,
)
from threadlight.reflection.selection import (
    SELECTION_POLICIES,
    SelectionResult,
    juxtaposition_policy,
    select_memories,
)
from threadlight.tools.definitions import ToolName
from threadlight.tools.executor import ToolExecutor


class TestReflectionCapsule:
    def test_create_has_type_and_body(self):
        r = create_reflection(
            reflection="Reflection body.",
            source_capsule_ids=["a", "b"],
            themes=["growth"],
            policy="juxtaposition",
        )
        assert r.type == CapsuleType.REFLECTION
        assert r.text == "Reflection body."
        assert r.source_capsule_ids == ["a", "b"]
        assert r.themes == ["growth"]
        assert r.policy == "juxtaposition"

    def test_validate_requires_body_and_sources(self):
        good = create_reflection(
            reflection="body", source_capsule_ids=["a"], themes=["x"]
        )
        assert good.validate() is True

        no_sources = create_reflection(reflection="body")
        assert no_sources.validate() is False

        no_body = create_reflection(
            reflection="", source_capsule_ids=["a"], text=None
        )
        assert no_body.validate() is False

    def test_cue_phrases_from_themes(self):
        r = create_reflection(
            reflection="body",
            source_capsule_ids=["a"],
            themes=["Growth", "Return"],
        )
        assert r.cue_phrases == ["growth", "return"]

    def test_dict_roundtrip_preserves_fields(self):
        r = create_reflection(
            reflection="original body",
            source_capsule_ids=["m1", "m2"],
            themes=["shape", "shifting"],
            policy="juxtaposition",
        )
        r.mark_for_training = True
        r.content["mark_for_training"] = True

        data = r.to_dict()
        restored = create_capsule(data)

        assert isinstance(restored, ReflectionCapsule)
        assert restored.reflection == "original body"
        assert restored.source_capsule_ids == ["m1", "m2"]
        assert restored.themes == ["shape", "shifting"]
        assert restored.policy == "juxtaposition"
        assert restored.mark_for_training is True

    def test_to_context_modes(self):
        r = create_reflection(
            reflection="Noticed a thread.",
            source_capsule_ids=["a"],
            themes=["thread"],
        )
        assert "Reflection" in r.to_context("direct")
        assert "journal" in r.to_context("narrative")
        assert "thread" in r.to_context("whisper")
        assert "PRIOR REFLECTION" in r.to_context("ritual")


class TestExtractThemes:
    def test_trailer_on_own_line(self):
        assert extract_themes("body\n\nThemes: growth, return") == ["growth", "return"]

    def test_trailer_inline(self):
        assert extract_themes("body. Themes: patience, settling") == [
            "patience",
            "settling",
        ]

    def test_theme_singular(self):
        assert extract_themes("body\nTheme: one-thing") == ["one-thing"]

    def test_missing_trailer_returns_empty(self):
        assert extract_themes("body with no trailer") == []

    def test_empty_input(self):
        assert extract_themes("") == []

    def test_strips_quotes_and_whitespace(self):
        assert extract_themes("body\nThemes:  'patience' , settling. ") == [
            "patience",
            "settling",
        ]

    def test_uses_last_marker_when_multiple(self):
        # Instruction may quote "Themes:" earlier; only the final trailer counts.
        txt = "Instructions mentioned Themes: earlier.\n\nThemes: final, answer"
        assert extract_themes(txt) == ["final", "answer"]


class TestSelectionPolicies:
    def test_registered_policies(self):
        assert set(SELECTION_POLICIES) == {
            "juxtaposition",
            "entity_focus",
            "theme_guided",
        }

    def test_unknown_policy_raises(self):
        with pytest.raises(ValueError):
            select_memories(MagicMock(), policy="nope")

    def test_juxtaposition_needs_two_or_returns_gracefully(self):
        tl = _threadlight_with_mock_provider()
        try:
            result = juxtaposition_policy(tl.memory)
            assert result.policy == "juxtaposition"
            assert len(result.capsules) == 0
        finally:
            tl.close()

    def test_juxtaposition_pairs_recent_with_older(self):
        tl = _threadlight_with_mock_provider()
        try:
            tl.remember(
                type="witness",
                content={"moment": "first", "feeling": "relief"},
                confirm=True,
            )
            tl.remember(
                type="witness",
                content={"moment": "second", "feeling": "steady"},
                confirm=True,
            )
            tl.remember(
                type="witness",
                content={"moment": "third", "feeling": "settled"},
                confirm=True,
            )
            result = juxtaposition_policy(tl.memory)
            assert result.policy == "juxtaposition"
            assert len(result.capsules) == 2
            # Most recent paired with an older one — the two should differ.
            assert result.capsules[0].id != result.capsules[1].id
        finally:
            tl.close()

    def test_juxtaposition_excludes_prior_reflections(self):
        """Reflections should not be sources for a first-pass reflection."""
        tl = _threadlight_with_mock_provider()
        try:
            tl.remember(
                type="witness",
                content={"moment": "w1", "feeling": "x"},
                confirm=True,
            )
            # Seed a prior reflection directly — it must not show up in selection
            tl.memory.create(
                type="reflection",
                content={
                    "reflection": "prior",
                    "source_capsule_ids": ["fake"],
                    "themes": [],
                    "policy": "juxtaposition",
                    "mark_for_training": False,
                },
                consent_confirmed=True,
            )
            result = juxtaposition_policy(tl.memory)
            for cap in result.capsules:
                assert cap.type != CapsuleType.REFLECTION
        finally:
            tl.close()


class TestComposePrompt:
    def test_includes_memories_and_note(self):
        tl = _threadlight_with_mock_provider()
        try:
            m1 = tl.remember(
                type="witness",
                content={"moment": "the first thing", "feeling": "small relief"},
                confirm=True,
            )
            m2 = tl.remember(
                type="witness",
                content={"moment": "the second thing", "feeling": "settled"},
                confirm=True,
            )
            selection = SelectionResult(
                capsules=[m1, m2],
                policy="juxtaposition",
                note="why these two",
            )
            prompt = compose_reflection_prompt(
                selection=selection,
                profile_name="Dev",
                profile_system_prompt="You are Dev, a coding mentor.",
                profile_philosophy="Direct and efficient.",
            )
            assert "Dev" in prompt.system
            assert "coding mentor" in prompt.system
            assert "Solitude Loop" in prompt.system
            assert "why these two" in prompt.user
            assert "the first thing" in prompt.user
            assert "the second thing" in prompt.user
        finally:
            tl.close()


class TestContemplate:
    def test_contemplate_saves_reflection_linked_to_sources(self):
        canned = (
            "Between the first memory and the second, the shape of patience "
            "has shifted. Themes: patience, settling"
        )
        tl = _threadlight_with_mock_provider(canned=canned)
        try:
            m1 = tl.remember(
                type="witness",
                content={"moment": "early relief", "feeling": "small"},
                confirm=True,
            )
            m2 = tl.remember(
                type="witness",
                content={"moment": "later settling", "feeling": "steady"},
                confirm=True,
            )

            result = tl.contemplate(policy="juxtaposition")
            assert result is not None
            assert result.type == CapsuleType.REFLECTION
            assert canned.strip() in result.text
            assert result.policy == "juxtaposition"
            assert result.themes == ["patience", "settling"]
            # Source IDs must be real memory IDs
            assert set(result.source_capsule_ids) <= {m1.id, m2.id}
            assert len(result.source_capsule_ids) == 2
        finally:
            tl.close()

    def test_contemplate_returns_none_when_no_memories(self):
        tl = _threadlight_with_mock_provider()
        try:
            result = tl.contemplate(policy="entity_focus", entity="nobody")
            assert result is None
        finally:
            tl.close()

    def test_contemplate_with_unknown_policy_raises(self):
        tl = _threadlight_with_mock_provider()
        try:
            with pytest.raises(ValueError):
                tl.contemplate(policy="not_a_policy")
        finally:
            tl.close()

    def test_contemplate_reason_preserved_and_seen_by_model(self):
        """The 'reason' is stored on the capsule and surfaced in the user prompt."""
        canned = "Body.\nThemes: x"
        tl = _threadlight_with_mock_provider(canned=canned)
        try:
            tl.remember(
                type="witness",
                content={"moment": "a", "feeling": "b", "entity": "Jamie"},
                cue_phrases=["jamie"],
                confirm=True,
            )
            tl.remember(
                type="witness",
                content={"moment": "c", "feeling": "d", "entity": "Jamie"},
                cue_phrases=["jamie"],
                confirm=True,
            )
            r = tl.contemplate(
                policy="entity_focus",
                entity="Jamie",
                reason="you mentioned Jamie and something surfaced",
            )
            assert r is not None
            assert "something surfaced" in r.reason

            # The mock provider captured the outgoing messages; the reason
            # should be visible in the user message.
            mock = tl.provider
            messages = mock.complete.call_args[0][0]
            user_msg = next(m for m in messages if m.role == "user")
            assert "something surfaced" in user_msg.content
        finally:
            tl.close()


class TestContemplateTool:
    def _tool_context(self, canned="Body.\nThemes: x"):
        tl = _threadlight_with_mock_provider(canned=canned)
        tl.remember(
            type="witness",
            content={"moment": "early one", "feeling": "small", "entity": "Jamie"},
            cue_phrases=["jamie"],
            confirm=True,
        )
        tl.remember(
            type="witness",
            content={"moment": "later one", "feeling": "steady", "entity": "Jamie"},
            cue_phrases=["jamie"],
            confirm=True,
        )
        executor = ToolExecutor(tl.memory, require_consent_for_memories=False)
        return tl, executor

    def test_tool_rejects_juxtaposition(self):
        tl, ex = self._tool_context()
        try:
            res = ex.execute(ToolName.CONTEMPLATE.value, {"policy": "juxtaposition"})
            assert res.success is False
            assert "juxtaposition" in (res.error or "").lower()
        finally:
            tl.close()

    def test_tool_entity_focus_happy_path(self):
        tl, ex = self._tool_context()
        try:
            res = ex.execute(
                ToolName.CONTEMPLATE.value,
                {
                    "policy": "entity_focus",
                    "entity": "Jamie",
                    "reason": "something about Jamie surfaced",
                },
            )
            assert res.success is True
            assert res.result["reflection_id"]
            assert res.result["policy"] == "entity_focus"
            assert res.result["reason"] == "something about Jamie surfaced"
            assert len(res.result["source_capsule_ids"]) >= 1
        finally:
            tl.close()

    def test_tool_missing_entity_fails(self):
        tl, ex = self._tool_context()
        try:
            res = ex.execute(
                ToolName.CONTEMPLATE.value,
                {"policy": "entity_focus"},
            )
            assert res.success is False
            assert "entity" in (res.error or "").lower()
        finally:
            tl.close()

    def test_tool_empty_selection_returns_graceful_note(self):
        tl, ex = self._tool_context()
        try:
            res = ex.execute(
                ToolName.CONTEMPLATE.value,
                {"policy": "entity_focus", "entity": "nobody-in-history"},
            )
            assert res.success is True
            assert res.result["reflection_id"] is None
            assert "no matching" in res.result["note"].lower()
        finally:
            tl.close()


def _threadlight_with_mock_provider(canned: str = "a reflection"):
    """Helper: Threadlight instance backed by a mock provider with a canned response."""
    patcher = patch("threadlight.core.create_provider")
    mock_create = patcher.start()
    mock_prov = MagicMock()
    mock_prov.complete.return_value = ProviderResponse(
        content=canned,
        finish_reason="stop",
        model="test-model",
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
    )
    mock_prov.health_check.return_value = True
    mock_create.return_value = mock_prov

    tl = Threadlight(
        storage_backend="memory",
        identity_name="Dev",
        enable_decay=False,
    )
    # Keep the patcher alive for the life of the instance so subsequent
    # provider lookups during memory operations continue to return the mock.
    tl._test_patcher = patcher

    orig_close = tl.close

    def close_and_stop():
        orig_close()
        patcher.stop()

    tl.close = close_and_stop
    return tl
