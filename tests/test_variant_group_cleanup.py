"""Tests for variant group cleanup when messages are deleted."""

import os
import tempfile
import uuid
from datetime import datetime, timedelta

import pytest

from threadlight.storage.base import Message, Conversation
from threadlight.storage.memory import InMemoryStorage
from threadlight.storage.sqlite import SQLiteStorage


def _make_message(
    conversation_id: str,
    role: str = "assistant",
    content: str = "hello",
    timestamp: datetime | None = None,
    variant_group_id: str | None = None,
    variant_index: int = 0,
) -> Message:
    """Helper to create a Message with sensible defaults."""
    return Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role=role,
        content=content,
        timestamp=timestamp or datetime.utcnow(),
        variant_group_id=variant_group_id,
        variant_index=variant_index,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def memory_storage():
    s = InMemoryStorage()
    s.initialize()
    yield s
    s.close()


@pytest.fixture
def sqlite_storage():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    s = SQLiteStorage(path=db_path)
    s.initialize()
    yield s
    s.close()
    try:
        os.unlink(db_path)
        for suffix in ["-shm", "-wal"]:
            wal_path = db_path + suffix
            if os.path.exists(wal_path):
                os.unlink(wal_path)
    except OSError:
        pass


# Run every test against both backends
@pytest.fixture(params=["memory", "sqlite"])
def storage(request, memory_storage, sqlite_storage):
    if request.param == "memory":
        return memory_storage
    return sqlite_storage


def _setup_conversation(storage) -> str:
    """Create and save a conversation, return its ID."""
    conv_id = str(uuid.uuid4())
    conv = Conversation(
        id=conv_id,
        name="Test Conversation",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    storage.save_conversation(conv)
    return conv_id


# ---------------------------------------------------------------------------
# delete_message tests
# ---------------------------------------------------------------------------


class TestDeleteMessageVariantCleanup:
    """Deleting a message that belongs to a variant group should delete the
    entire group."""

    def test_delete_variant_deletes_entire_group(self, storage):
        conv_id = _setup_conversation(storage)
        group_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Create 3 variants in the same group
        msgs = []
        for i in range(3):
            m = _make_message(
                conversation_id=conv_id,
                content=f"variant {i}",
                timestamp=now + timedelta(seconds=i),
                variant_group_id=group_id,
                variant_index=i,
            )
            storage.save_message(m)
            msgs.append(m)

        # Delete one of the variants (the middle one)
        assert storage.delete_message(msgs[1].id) is True

        # All three should be gone
        for m in msgs:
            assert storage.get_message(m.id) is None

    def test_delete_variant_does_not_affect_other_messages(self, storage):
        conv_id = _setup_conversation(storage)
        group_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Create a variant group
        variant_msg = _make_message(
            conversation_id=conv_id,
            content="variant",
            timestamp=now,
            variant_group_id=group_id,
            variant_index=0,
        )
        storage.save_message(variant_msg)

        # Create a normal (non-variant) message
        normal_msg = _make_message(
            conversation_id=conv_id,
            content="normal",
            timestamp=now + timedelta(seconds=1),
        )
        storage.save_message(normal_msg)

        # Delete the variant
        storage.delete_message(variant_msg.id)

        # Normal message should still exist
        assert storage.get_message(normal_msg.id) is not None

    def test_delete_non_variant_message_works_normally(self, storage):
        conv_id = _setup_conversation(storage)

        msg = _make_message(conversation_id=conv_id, content="solo")
        storage.save_message(msg)

        assert storage.delete_message(msg.id) is True
        assert storage.get_message(msg.id) is None

    def test_delete_nonexistent_message_returns_false(self, storage):
        assert storage.delete_message("nonexistent-id") is False

    def test_delete_single_variant_in_group(self, storage):
        """Even if there is only one message with a variant_group_id, it
        should still be deleted successfully."""
        conv_id = _setup_conversation(storage)
        group_id = str(uuid.uuid4())

        msg = _make_message(
            conversation_id=conv_id,
            content="lonely variant",
            variant_group_id=group_id,
            variant_index=0,
        )
        storage.save_message(msg)

        assert storage.delete_message(msg.id) is True
        assert storage.get_message(msg.id) is None


# ---------------------------------------------------------------------------
# delete_messages_after tests
# ---------------------------------------------------------------------------


class TestDeleteMessagesAfterVariantCleanup:
    """delete_messages_after should clean up variant groups that would
    otherwise be left in an incomplete state."""

    def test_all_variants_in_range_are_deleted(self, storage):
        """If all variants fall within the deletion range, they are simply
        deleted as normal."""
        conv_id = _setup_conversation(storage)
        group_id = str(uuid.uuid4())
        base = datetime.utcnow()

        # Message before the cut point
        early = _make_message(
            conversation_id=conv_id,
            content="keep me",
            timestamp=base,
        )
        storage.save_message(early)

        # Variant group entirely after the cut point
        cut_point = _make_message(
            conversation_id=conv_id,
            content="cut",
            timestamp=base + timedelta(seconds=5),
        )
        storage.save_message(cut_point)

        for i in range(2):
            v = _make_message(
                conversation_id=conv_id,
                content=f"variant {i}",
                timestamp=base + timedelta(seconds=10 + i),
                variant_group_id=group_id,
                variant_index=i,
            )
            storage.save_message(v)

        deleted = storage.delete_messages_after(conv_id, cut_point.id)
        assert deleted == 3  # cut_point + 2 variants

        # Early message survives
        assert storage.get_message(early.id) is not None

    def test_partial_variant_group_is_fully_cleaned(self, storage):
        """If a variant group straddles the deletion boundary, the variants
        outside the range are also deleted."""
        conv_id = _setup_conversation(storage)
        group_id = str(uuid.uuid4())
        base = datetime.utcnow()

        # Variant 0: BEFORE the cut point
        v0 = _make_message(
            conversation_id=conv_id,
            content="variant 0 (early)",
            timestamp=base + timedelta(seconds=1),
            variant_group_id=group_id,
            variant_index=0,
        )
        storage.save_message(v0)

        # The cut point
        cut_msg = _make_message(
            conversation_id=conv_id,
            content="cut here",
            timestamp=base + timedelta(seconds=5),
        )
        storage.save_message(cut_msg)

        # Variant 1: AFTER the cut point
        v1 = _make_message(
            conversation_id=conv_id,
            content="variant 1 (late)",
            timestamp=base + timedelta(seconds=10),
            variant_group_id=group_id,
            variant_index=1,
        )
        storage.save_message(v1)

        deleted = storage.delete_messages_after(conv_id, cut_msg.id)

        # v0 should also have been cleaned up (orphaned from the group)
        assert storage.get_message(v0.id) is None
        assert storage.get_message(v1.id) is None
        assert storage.get_message(cut_msg.id) is None

        # Total: cut_msg + v1 (in range) + v0 (orphan cleanup)
        assert deleted == 3

    def test_non_variant_messages_unaffected_by_group_cleanup(self, storage):
        """Normal messages before the cut point should not be touched even
        when variant group cleanup happens."""
        conv_id = _setup_conversation(storage)
        group_id = str(uuid.uuid4())
        base = datetime.utcnow()

        # Normal message (early)
        keeper = _make_message(
            conversation_id=conv_id,
            content="keep",
            timestamp=base,
        )
        storage.save_message(keeper)

        # Variant 0: before cut
        v0 = _make_message(
            conversation_id=conv_id,
            content="v0",
            timestamp=base + timedelta(seconds=2),
            variant_group_id=group_id,
            variant_index=0,
        )
        storage.save_message(v0)

        # Cut point
        cut = _make_message(
            conversation_id=conv_id,
            content="cut",
            timestamp=base + timedelta(seconds=5),
        )
        storage.save_message(cut)

        # Variant 1: after cut
        v1 = _make_message(
            conversation_id=conv_id,
            content="v1",
            timestamp=base + timedelta(seconds=8),
            variant_group_id=group_id,
            variant_index=1,
        )
        storage.save_message(v1)

        storage.delete_messages_after(conv_id, cut.id)

        # The normal message should survive
        assert storage.get_message(keeper.id) is not None
        # The variant group should be entirely gone
        assert storage.get_message(v0.id) is None
        assert storage.get_message(v1.id) is None

    def test_no_variant_groups_behaves_normally(self, storage):
        """Without any variant groups, delete_messages_after should work
        exactly as before."""
        conv_id = _setup_conversation(storage)
        base = datetime.utcnow()

        msgs = []
        for i in range(5):
            m = _make_message(
                conversation_id=conv_id,
                content=f"msg {i}",
                timestamp=base + timedelta(seconds=i),
            )
            storage.save_message(m)
            msgs.append(m)

        # Delete from index 2 onward
        deleted = storage.delete_messages_after(conv_id, msgs[2].id)
        assert deleted == 3

        # First two messages survive
        assert storage.get_message(msgs[0].id) is not None
        assert storage.get_message(msgs[1].id) is not None

        # Messages 2-4 are gone
        for m in msgs[2:]:
            assert storage.get_message(m.id) is None

    def test_multiple_variant_groups_partial_cleanup(self, storage):
        """Multiple variant groups that straddle the boundary should all be
        cleaned up."""
        conv_id = _setup_conversation(storage)
        group_a = str(uuid.uuid4())
        group_b = str(uuid.uuid4())
        base = datetime.utcnow()

        # Group A: variant 0 before cut, variant 1 after cut
        a0 = _make_message(
            conversation_id=conv_id, content="a0",
            timestamp=base + timedelta(seconds=1),
            variant_group_id=group_a, variant_index=0,
        )
        a1 = _make_message(
            conversation_id=conv_id, content="a1",
            timestamp=base + timedelta(seconds=10),
            variant_group_id=group_a, variant_index=1,
        )

        # Group B: variant 0 before cut, variant 1 after cut
        b0 = _make_message(
            conversation_id=conv_id, content="b0",
            timestamp=base + timedelta(seconds=2),
            variant_group_id=group_b, variant_index=0,
        )
        b1 = _make_message(
            conversation_id=conv_id, content="b1",
            timestamp=base + timedelta(seconds=11),
            variant_group_id=group_b, variant_index=1,
        )

        for m in [a0, a1, b0, b1]:
            storage.save_message(m)

        # Cut at second 5
        cut = _make_message(
            conversation_id=conv_id, content="cut",
            timestamp=base + timedelta(seconds=5),
        )
        storage.save_message(cut)

        deleted = storage.delete_messages_after(conv_id, cut.id)

        # All variant messages and the cut point should be gone
        for m in [a0, a1, b0, b1, cut]:
            assert storage.get_message(m.id) is None

        # Total: cut + a1 + b1 (in range) + a0 + b0 (orphan cleanup)
        assert deleted == 5
