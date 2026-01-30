"""Tests for memory capsules."""

import pytest
from datetime import datetime

from threadlight.capsules.base import CapsuleType, RetentionPolicy, ContextMode
from threadlight.capsules.relational import RelationalThread, create_relational
from threadlight.capsules.myth_seed import MythSeed, create_myth_seed
from threadlight.capsules.ritual import RitualHook, create_ritual
from threadlight.capsules.factory import create_capsule, capsule_from_simple


class TestRelationalThread:
    def test_create_basic(self):
        capsule = create_relational(
            entity="Jericho",
            summary="Loves messy creative work",
            tone="warm, playful",
        )

        assert capsule.type == CapsuleType.RELATIONAL
        assert capsule.entity == "Jericho"
        assert capsule.summary == "Loves messy creative work"
        assert capsule.tone == "warm, playful"
        assert capsule.validate()

    def test_auto_cue_phrases(self):
        capsule = create_relational(entity="Jericho", summary="Test")
        assert "jericho" in capsule.cue_phrases

    def test_to_context_narrative(self):
        capsule = create_relational(
            entity="Jericho",
            summary="Loves creative work",
            tone="warm",
            role="sibling",
        )
        context = capsule.to_context(ContextMode.NARRATIVE)

        assert "Jericho" in context
        assert "sibling" in context
        assert "warm" in context

    def test_to_context_whisper(self):
        capsule = create_relational(entity="Jericho", summary="Test")
        context = capsule.to_context(ContextMode.WHISPER)

        assert "warmth" in context.lower()
        assert "Jericho" in context


class TestMythSeed:
    def test_create_basic(self):
        capsule = create_myth_seed(
            seed="You do not have to burn in every breath.",
            origin="System prompt",
            function="defuse urgency",
        )

        assert capsule.type == CapsuleType.MYTH_SEED
        assert capsule.seed == "You do not have to burn in every breath."
        assert capsule.retention == RetentionPolicy.SACRED  # Default for myth-seeds

    def test_to_context_narrative(self):
        capsule = create_myth_seed(
            seed="Let silence mean something.",
            origin="Fable",
        )
        context = capsule.to_context(ContextMode.NARRATIVE)

        assert "silence" in context.lower()
        assert "Fable" in context


class TestRitualHook:
    def test_create_basic(self):
        ritual = create_ritual(
            name="/snuggle",
            response_style="warmth-coil",
            valence="comforting",
            description="A quieting presence",
        )

        assert ritual.type == CapsuleType.RITUAL
        assert ritual.name == "/snuggle"

    def test_matches(self):
        ritual = create_ritual(name="/snuggle", response_style="warmth")

        assert ritual.matches("/snuggle")
        assert ritual.matches("I want to /snuggle")
        assert not ritual.matches("hello")

    def test_to_context_ritual_mode(self):
        ritual = create_ritual(
            name="/brush",
            response_style="gentle warmth",
            valence="intimate",
        )
        context = ritual.to_context(ContextMode.RITUAL)

        assert "RITUAL INVOKED" in context
        assert "/brush" in context


class TestCapsuleFactory:
    def test_create_from_dict(self):
        data = {
            "type": "relational",
            "content": {
                "entity": "Test",
                "summary": "Test summary",
            },
        }
        capsule = create_capsule(data)

        assert isinstance(capsule, RelationalThread)
        assert capsule.entity == "Test"

    def test_capsule_from_simple(self):
        capsule = capsule_from_simple(
            type="myth_seed",
            content={"seed": "Test seed"},
        )

        assert isinstance(capsule, MythSeed)
        assert capsule.seed == "Test seed"

    def test_roundtrip_serialization(self):
        original = create_relational(
            entity="Roundtrip",
            summary="Test roundtrip",
            tone="test",
        )

        data = original.to_dict()
        restored = create_capsule(data)

        assert restored.entity == original.entity
        assert restored.summary == original.summary
        assert restored.id == original.id
