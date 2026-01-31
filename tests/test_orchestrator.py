"""Tests for the memory orchestrator."""

import pytest
from datetime import datetime, timedelta

from threadlight.memory.orchestrator import (
    MemoryOrchestrator,
    Session,
    RitualInvocation,
)
from threadlight.storage.memory import InMemoryStorage
from threadlight.decay.engine import DecayEngine, LinearDecayStrategy
from threadlight.capsules.base import CapsuleType, RetentionPolicy
from threadlight.capsules.ritual import create_ritual, RitualValence


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
        min_age_hours=0,  # Allow immediate decay for testing
    )


@pytest.fixture
def orchestrator(storage, decay_engine):
    """Create memory orchestrator."""
    return MemoryOrchestrator(
        storage=storage,
        decay_engine=decay_engine,
        auto_propose=True,
        proposal_threshold=3,
    )


class TestSession:
    def test_session_creation(self):
        session = Session()

        assert session.id is not None
        assert session.is_active
        assert session.message_count == 0
        assert len(session.capsules_accessed) == 0

    def test_session_record_access(self):
        session = Session()
        session.record_access("capsule-1")
        session.record_access("capsule-2")
        session.record_access("capsule-1")  # Duplicate

        assert len(session.capsules_accessed) == 2

    def test_session_record_creation(self):
        session = Session()
        session.record_creation("capsule-1")

        assert "capsule-1" in session.capsules_created

    def test_session_record_ritual(self):
        session = Session()
        session.record_ritual("/snuggle")

        assert "/snuggle" in session.rituals_invoked
        assert session.active_ritual == "/snuggle"

    def test_session_end(self):
        session = Session()
        session.end()

        assert not session.is_active
        assert session.ended_at is not None
        assert session.active_ritual is None

    def test_session_duration(self):
        session = Session()
        # Duration should be positive even for active session
        assert session.duration_seconds >= 0

    def test_session_to_dict(self):
        session = Session()
        session.record_access("c1")
        session.record_ritual("/test")

        data = session.to_dict()

        assert "id" in data
        assert "started_at" in data
        assert "capsules_accessed" in data
        assert "rituals_invoked" in data


class TestRitualInvocation:
    def test_invocation_to_dict(self):
        invocation = RitualInvocation(
            ritual_name="/snuggle",
            matched=True,
            response_template="*settles close*",
        )

        data = invocation.to_dict()

        assert data["ritual_name"] == "/snuggle"
        assert data["matched"] is True
        assert data["response_template"] == "*settles close*"


class TestMemoryOrchestratorCapsules:
    def test_create_capsule(self, orchestrator):
        """Test creating a capsule."""
        capsule = orchestrator.create(
            type="relational",
            content={
                "entity": "Test",
                "summary": "Test summary",
            },
            consent_confirmed=True,
        )

        assert capsule is not None
        assert capsule.type == CapsuleType.RELATIONAL
        assert capsule.consent_confirmed

    def test_get_capsule(self, orchestrator):
        """Test getting a capsule by ID."""
        created = orchestrator.create(
            type="myth_seed",
            content={"seed": "Test seed"},
            consent_confirmed=True,
        )

        retrieved = orchestrator.get(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        # Access count should be incremented
        assert retrieved.access_count >= 1

    def test_update_capsule(self, orchestrator):
        """Test updating a capsule."""
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "Test", "summary": "Original"},
            consent_confirmed=True,
        )

        capsule.content["summary"] = "Updated"
        result = orchestrator.update(capsule)

        assert result is True

    def test_delete_capsule(self, orchestrator):
        """Test deleting a capsule."""
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "Test"},
            consent_confirmed=True,
        )

        result = orchestrator.delete(capsule.id)

        assert result is True
        assert orchestrator.get(capsule.id) is None

    def test_delete_sacred_capsule_protected(self, orchestrator):
        """Test that sacred capsules require force=True to delete."""
        capsule = orchestrator.create(
            type="myth_seed",
            content={"seed": "Sacred test"},
            retention="sacred",
            consent_confirmed=True,
        )

        # Should fail without force
        result = orchestrator.delete(capsule.id, force=False)
        assert result is False

        # Should succeed with force
        result = orchestrator.delete(capsule.id, force=True)
        assert result is True

    def test_list_capsules(self, orchestrator):
        """Test listing capsules."""
        orchestrator.create(
            type="relational",
            content={"entity": "R1"},
            consent_confirmed=True,
        )
        orchestrator.create(
            type="myth_seed",
            content={"seed": "M1"},
            consent_confirmed=True,
        )

        all_caps = orchestrator.list()
        assert len(all_caps) >= 2

        # Filter by type
        relational = orchestrator.list(type=CapsuleType.RELATIONAL)
        assert all(c.type == CapsuleType.RELATIONAL for c in relational)


class TestMemoryOrchestratorRetrieval:
    def test_recall_by_cue(self, orchestrator):
        """Test recalling memories by cue phrase."""
        orchestrator.create(
            type="relational",
            content={"entity": "Jericho", "summary": "Test"},
            cue_phrases=["jericho", "brother"],
            consent_confirmed=True,
        )

        results = orchestrator.recall("Tell me about Jericho")

        assert len(results) >= 1
        assert any(hasattr(r, 'entity') and r.entity == "Jericho" for r in results)

    def test_recall_updates_access(self, orchestrator):
        """Test that recall updates access timestamp."""
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "AccessTest"},
            cue_phrases=["accesstest"],
            consent_confirmed=True,
        )

        old_accessed = capsule.last_accessed

        # Wait a tiny bit and recall
        import time
        time.sleep(0.01)

        orchestrator.recall("accesstest")

        updated = orchestrator.get(capsule.id)
        assert updated.last_accessed >= old_accessed

    def test_recall_for_message(self, orchestrator):
        """Test comprehensive message-based recall."""
        # Create various memories
        orchestrator.create(
            type="relational",
            content={"entity": "TestEntity"},
            cue_phrases=["testentity"],
            consent_confirmed=True,
        )

        results = orchestrator.recall_for_message("Hello TestEntity!")

        assert isinstance(results, list)


class TestMemoryOrchestratorProposals:
    def test_propose_memory(self, orchestrator):
        """Test proposing a memory."""
        proposal = orchestrator.propose(
            type="relational",
            content={"entity": "Proposed", "summary": "Test"},
            source_message="User mentioned Proposed",
        )

        assert proposal is not None
        assert proposal.status == "pending"

    def test_get_pending_proposals(self, orchestrator):
        """Test listing pending proposals."""
        orchestrator.propose(
            type="relational",
            content={"entity": "P1"},
        )
        orchestrator.propose(
            type="relational",
            content={"entity": "P2"},
        )

        pending = orchestrator.get_pending_proposals()

        assert len(pending) >= 2

    def test_confirm_proposal(self, orchestrator):
        """Test confirming a proposal."""
        proposal = orchestrator.propose(
            type="relational",
            content={"entity": "ToConfirm", "summary": "Test"},
        )

        capsule = orchestrator.confirm_proposal(proposal.id)

        assert capsule is not None
        assert capsule.consent_confirmed
        assert hasattr(capsule, 'entity') and capsule.entity == "ToConfirm"

    def test_reject_proposal(self, orchestrator):
        """Test rejecting a proposal."""
        proposal = orchestrator.propose(
            type="relational",
            content={"entity": "ToReject"},
        )

        result = orchestrator.reject_proposal(proposal.id)

        assert result is True


class TestMemoryOrchestratorRituals:
    def test_invoke_existing_ritual(self, orchestrator, storage):
        """Test invoking a ritual that exists."""
        # Create a ritual
        ritual = create_ritual(
            name="/snuggle",
            response_style="warmth-coil",
            valence=RitualValence.COMFORTING,
            description="Coiled presence",
            response_templates=["*settles close*"],
        )
        ritual.consent_confirmed = True
        storage.save_capsule(ritual)

        result = orchestrator.invoke_ritual("/snuggle")

        assert result.matched is True
        assert result.capsule is not None
        assert result.response_template == "*settles close*"

    def test_invoke_missing_ritual(self, orchestrator):
        """Test invoking a ritual that doesn't exist."""
        result = orchestrator.invoke_ritual("/nonexistent")

        assert result.matched is False
        assert result.capsule is None

    def test_get_active_ritual(self, orchestrator, storage):
        """Test getting active ritual from session."""
        orchestrator.start_session()

        # Create and invoke ritual
        ritual = create_ritual(name="/test", response_style="test")
        ritual.consent_confirmed = True
        storage.save_capsule(ritual)

        orchestrator.invoke_ritual("/test")

        active = orchestrator.get_active_ritual()
        assert active == "/test"

    def test_clear_ritual_state(self, orchestrator, storage):
        """Test clearing ritual state."""
        orchestrator.start_session()

        ritual = create_ritual(name="/clear", response_style="test")
        ritual.consent_confirmed = True
        storage.save_capsule(ritual)

        orchestrator.invoke_ritual("/clear")
        orchestrator.clear_ritual_state()

        assert orchestrator.get_active_ritual() is None


class TestMemoryOrchestratorDecay:
    def test_run_decay(self, orchestrator):
        """Test running decay cycle."""
        # Create a capsule
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "Decay Test"},
            consent_confirmed=True,
        )

        # Age it
        capsule.last_accessed = datetime.utcnow() - timedelta(days=60)
        orchestrator.update(capsule)

        result = orchestrator.run_decay()

        assert "processed" in result
        assert "decayed" in result

    def test_revive_dormant(self, orchestrator):
        """Test reviving a dormant capsule."""
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "Dormant"},
            consent_confirmed=True,
        )
        capsule.presence_score = 0.05
        orchestrator.update(capsule)

        revived = orchestrator.revive(capsule.id)

        assert revived is not None
        assert revived.presence_score == 1.0

    def test_get_dormant(self, orchestrator):
        """Test getting dormant capsules."""
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "VeryDormant"},
            consent_confirmed=True,
        )
        capsule.presence_score = 0.01
        orchestrator.update(capsule)

        dormant = orchestrator.get_dormant()

        assert any(d.id == capsule.id for d in dormant)


class TestMemoryOrchestratorReinforce:
    def test_reinforce_capsules(self, orchestrator):
        """Test reinforcing capsules."""
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "ToReinforce"},
            consent_confirmed=True,
        )
        capsule.presence_score = 0.5
        orchestrator.update(capsule)

        result = orchestrator.reinforce([capsule.id], strength=0.3)

        assert result.get("reinforced", 0) >= 1

        updated = orchestrator.get(capsule.id)
        assert updated.presence_score > 0.5


class TestMemoryOrchestratorSessions:
    def test_start_session(self, orchestrator):
        """Test starting a session."""
        session = orchestrator.start_session(metadata={"test": True})

        assert session is not None
        assert session.is_active
        assert session.metadata.get("test") is True

    def test_end_session(self, orchestrator):
        """Test ending a session."""
        orchestrator.start_session()
        ended = orchestrator.end_session()

        assert ended is not None
        assert not ended.is_active
        assert orchestrator.get_current_session() is None

    def test_get_current_session(self, orchestrator):
        """Test getting current session."""
        assert orchestrator.get_current_session() is None

        orchestrator.start_session()
        session = orchestrator.get_current_session()

        assert session is not None
        assert session.is_active

    def test_session_tracks_accessed(self, orchestrator):
        """Test that session tracks accessed capsules."""
        orchestrator.start_session()

        capsule = orchestrator.create(
            type="relational",
            content={"entity": "SessionTest"},
            cue_phrases=["sessiontest"],
            consent_confirmed=True,
        )

        orchestrator.recall("sessiontest")

        session = orchestrator.get_current_session()
        assert capsule.id in session.capsules_accessed

    def test_ephemeral_cleanup(self, orchestrator):
        """Test that ephemeral capsules are cleaned up on session end."""
        orchestrator.start_session()

        capsule = orchestrator.create(
            type="relational",
            content={"entity": "Ephemeral"},
            retention="ephemeral",
            consent_confirmed=True,
        )

        session = orchestrator.get_current_session()
        session.record_creation(capsule.id)

        orchestrator.end_session()

        # Ephemeral should be deleted
        assert orchestrator.get(capsule.id) is None


class TestMemoryOrchestratorUtility:
    def test_export(self, orchestrator):
        """Test exporting capsules."""
        orchestrator.create(
            type="relational",
            content={"entity": "Export1"},
            consent_confirmed=True,
        )

        exported = orchestrator.export()

        assert len(exported) >= 1
        assert isinstance(exported, list)

    def test_import(self, orchestrator, storage):
        """Test importing capsules."""
        exported = [
            {
                "id": "import-test-1",
                "type": "relational",
                "content": {"entity": "Imported"},
                "cue_phrases": [],
                "retention": "normal",
                "presence_score": 1.0,
                "consent_confirmed": True,
            }
        ]

        count = orchestrator.import_capsules(exported)

        assert count == 1

    def test_stats(self, orchestrator):
        """Test getting statistics."""
        orchestrator.create(
            type="relational",
            content={"entity": "Stats1"},
            consent_confirmed=True,
        )
        orchestrator.create(
            type="myth_seed",
            content={"seed": "Stats2"},
            consent_confirmed=True,
        )

        stats = orchestrator.stats()

        assert stats["total"] >= 2
        assert "by_type" in stats
        assert "confirmed" in stats

    def test_record_interaction(self, orchestrator):
        """Test recording interactions."""
        orchestrator.start_session()

        orchestrator.record_interaction()
        orchestrator.record_interaction()

        session = orchestrator.get_current_session()
        assert session.message_count == 2


class TestMemoryOrchestratorProfileIsolation:
    """Tests for profile-based memory isolation."""

    @pytest.fixture
    def isolated_orchestrator(self, storage, decay_engine):
        """Create orchestrator with per-profile isolation enabled."""
        return MemoryOrchestrator(
            storage=storage,
            decay_engine=decay_engine,
            per_profile_isolation=True,
            current_profile="profile-a",
        )

    def test_recall_for_message_respects_include_shared_false(self, isolated_orchestrator):
        """Test that recall_for_message excludes shared memories when include_shared=False."""
        # Create a shared memory (no profile_scope)
        shared_capsule = isolated_orchestrator.create(
            type="relational",
            content={"entity": "SharedEntity", "summary": "A shared memory"},
            cue_phrases=["sharedentity"],
            consent_confirmed=True,
            shared=True,  # Explicitly shared
        )

        # Create a profile-scoped memory
        profile_capsule = isolated_orchestrator.create(
            type="relational",
            content={"entity": "ProfileEntity", "summary": "A profile memory"},
            cue_phrases=["profileentity"],
            consent_confirmed=True,
            shared=False,  # Profile-specific
        )

        # With include_shared=False, should only get profile-scoped memories
        results = isolated_orchestrator.recall_for_message(
            "Tell me about SharedEntity and ProfileEntity",
            include_shared=False,
        )

        result_ids = [r.id for r in results]
        assert profile_capsule.id in result_ids
        assert shared_capsule.id not in result_ids

    def test_recall_for_message_includes_shared_by_default(self, isolated_orchestrator):
        """Test that recall_for_message includes shared memories by default."""
        # Create a shared memory
        shared_capsule = isolated_orchestrator.create(
            type="relational",
            content={"entity": "DefaultShared", "summary": "A shared memory"},
            cue_phrases=["defaultshared"],
            consent_confirmed=True,
            shared=True,
        )

        # With default include_shared=True, should get shared memories
        results = isolated_orchestrator.recall_for_message(
            "Tell me about DefaultShared",
            include_shared=True,
        )

        result_ids = [r.id for r in results]
        assert shared_capsule.id in result_ids

    def test_recall_for_message_profile_scoped_always_included(self, isolated_orchestrator):
        """Test that profile-scoped memories are always included for matching profile."""
        # Create a profile-scoped memory for current profile
        profile_capsule = isolated_orchestrator.create(
            type="relational",
            content={"entity": "MyProfileMemory", "summary": "My private memory"},
            cue_phrases=["myprofilememory"],
            consent_confirmed=True,
            shared=False,
        )

        # Even with include_shared=False, profile-scoped memories should be included
        results = isolated_orchestrator.recall_for_message(
            "Tell me about MyProfileMemory",
            include_shared=False,
        )

        result_ids = [r.id for r in results]
        assert profile_capsule.id in result_ids

    def test_recall_for_message_excludes_other_profile_memories(self, isolated_orchestrator):
        """Test that memories from other profiles are not included."""
        # Create a memory scoped to a different profile
        other_profile_capsule = isolated_orchestrator.create(
            type="relational",
            content={"entity": "OtherProfile", "summary": "Other profile memory"},
            cue_phrases=["otherprofile"],
            consent_confirmed=True,
            profile_scope="profile-b",  # Different profile
        )

        # Should not get memories from other profiles
        results = isolated_orchestrator.recall_for_message(
            "Tell me about OtherProfile",
            include_shared=True,
        )

        result_ids = [r.id for r in results]
        assert other_profile_capsule.id not in result_ids

    def test_ritual_filtering_respects_include_shared(self, isolated_orchestrator, storage):
        """Test that ritual filtering respects include_shared parameter."""
        # Create a shared ritual
        shared_ritual = create_ritual(
            name="/shared-ritual",
            response_style="warm",
            valence=RitualValence.COMFORTING,
        )
        shared_ritual.consent_confirmed = True
        shared_ritual.profile_scope = None  # Shared
        storage.save_capsule(shared_ritual)

        # Create a profile-scoped ritual
        profile_ritual = create_ritual(
            name="/profile-ritual",
            response_style="warm",
            valence=RitualValence.COMFORTING,
        )
        profile_ritual.consent_confirmed = True
        profile_ritual.profile_scope = "profile-a"
        storage.save_capsule(profile_ritual)

        # With include_shared=False, should only get profile-scoped rituals
        results = isolated_orchestrator.recall_for_message(
            "/shared-ritual or /profile-ritual",
            include_shared=False,
            include_rituals=True,
        )

        result_ids = [r.id for r in results]
        assert profile_ritual.id in result_ids
        assert shared_ritual.id not in result_ids

    def test_style_filtering_respects_include_shared(self, isolated_orchestrator, storage):
        """Test that style filtering respects include_shared parameter."""
        from threadlight.capsules.style import StyleProfile

        # Create a shared style
        shared_style = StyleProfile(
            style_id="shared-style",
            tone_base="warm",
            vocal_motifs=["shared"],
        )
        shared_style.consent_confirmed = True
        shared_style.profile_scope = None  # Shared
        storage.save_capsule(shared_style)

        # Create a profile-scoped style
        profile_style = StyleProfile(
            style_id="profile-style",
            tone_base="warm",
            vocal_motifs=["private"],
        )
        profile_style.consent_confirmed = True
        profile_style.profile_scope = "profile-a"
        storage.save_capsule(profile_style)

        # With include_shared=False, should only get profile-scoped styles
        results = isolated_orchestrator.recall_for_message(
            "hello",
            include_shared=False,
            include_style=True,
        )

        result_ids = [r.id for r in results]
        # Profile style should be included
        assert profile_style.id in result_ids
        # Shared style should be excluded
        assert shared_style.id not in result_ids
