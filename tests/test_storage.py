"""Tests for storage backends."""

import json
import pytest
import tempfile
import os
from datetime import datetime, timedelta

from threadlight.storage.memory import InMemoryStorage
from threadlight.storage.sqlite import SQLiteStorage
from threadlight.storage.base import CapsuleFilter
from threadlight.capsules.relational import create_relational
from threadlight.capsules.myth_seed import create_myth_seed
from threadlight.capsules.ritual import create_ritual
from threadlight.capsules.witness import create_witness_moment
from threadlight.capsules.style import create_style_profile
from threadlight.capsules.base import CapsuleType, RetentionPolicy


@pytest.fixture
def storage():
    s = InMemoryStorage()
    s.initialize()
    yield s
    s.close()


class TestInMemoryStorage:
    def test_save_and_get(self, storage):
        capsule = create_relational(entity="Test", summary="Test summary")
        storage.save_capsule(capsule)

        retrieved = storage.get_capsule(capsule.id)
        assert retrieved is not None
        assert retrieved.entity == "Test"

    def test_update(self, storage):
        capsule = create_relational(entity="Test", summary="Original")
        storage.save_capsule(capsule)

        capsule.summary = "Updated"
        storage.update_capsule(capsule)

        retrieved = storage.get_capsule(capsule.id)
        assert retrieved.summary == "Updated"

    def test_delete(self, storage):
        capsule = create_relational(entity="Test", summary="Test")
        storage.save_capsule(capsule)

        assert storage.delete_capsule(capsule.id)
        assert storage.get_capsule(capsule.id) is None

    def test_list_with_filter(self, storage):
        # Create mixed capsules
        rel = create_relational(entity="Rel", summary="Relational")
        myth = create_myth_seed(seed="Test seed")

        storage.save_capsule(rel)
        storage.save_capsule(myth)

        # Filter by type
        filter = CapsuleFilter(type=CapsuleType.RELATIONAL)
        results = storage.list_capsules(filter)

        assert len(results) == 1
        assert results[0].type == CapsuleType.RELATIONAL

    def test_search_by_cue(self, storage):
        capsule = create_relational(
            entity="Jericho",
            summary="Test",
            cue_phrases=["jericho", "brother"]
        )
        storage.save_capsule(capsule)

        results = storage.search_by_cue("jericho")
        assert len(results) == 1
        assert results[0].entity == "Jericho"

    def test_get_capsules_for_decay(self, storage):
        # Create capsules with different retention policies
        normal = create_relational(entity="Normal", summary="Test")
        sacred = create_myth_seed(seed="Sacred")
        sacred.retention = RetentionPolicy.SACRED

        storage.save_capsule(normal)
        storage.save_capsule(sacred)

        # Get capsules for decay (excluding sacred)
        cutoff = datetime.utcnow() + timedelta(hours=1)
        results = storage.get_capsules_for_decay(
            before=cutoff,
            exclude_retention=[RetentionPolicy.SACRED]
        )

        assert len(results) == 1
        assert results[0].retention == RetentionPolicy.NORMAL

    def test_batch_update_presence(self, storage):
        c1 = create_relational(entity="C1", summary="Test")
        c2 = create_relational(entity="C2", summary="Test")

        storage.save_capsule(c1)
        storage.save_capsule(c2)

        updates = {c1.id: 0.5, c2.id: 0.3}
        count = storage.update_presence_scores(updates)

        assert count == 2
        assert storage.get_capsule(c1.id).presence_score == 0.5
        assert storage.get_capsule(c2.id).presence_score == 0.3

    def test_export_import(self, storage):
        capsule = create_relational(entity="Export", summary="Test export")
        storage.save_capsule(capsule)

        data = storage.export_all()
        assert len(data) == 1

        # Clear and reimport
        storage.close()
        storage.capsules = {}

        count = storage.import_capsules(data)
        assert count == 1
        assert len(storage.capsules) == 1


class TestSQLiteTextMigration:
    """Tests for text-first memory migration (Phase 5)."""

    @pytest.fixture
    def sqlite_storage(self):
        """Create a temporary SQLite storage for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        s = SQLiteStorage(path=db_path)
        s.initialize()
        yield s
        s.close()
        # Clean up temp file
        try:
            os.unlink(db_path)
            # Also remove WAL files if they exist
            for suffix in ["-shm", "-wal"]:
                wal_path = db_path + suffix
                if os.path.exists(wal_path):
                    os.unlink(wal_path)
        except OSError:
            pass

    def _insert_capsule_without_text(self, storage, capsule_type, content):
        """
        Insert a capsule directly into the database WITHOUT the text field.
        This simulates pre-migration data.
        """
        import uuid

        capsule_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        storage.conn.execute("""
            INSERT INTO capsules
            (id, type, content, text, created_at, updated_at, last_accessed,
             access_count, retention, memory_tier, decay_rate, presence_score,
             consent_origin, consent_confirmed, cue_phrases, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            capsule_id,
            capsule_type,
            json.dumps(content),
            None,  # text is NULL - simulating pre-migration data
            now,
            now,
            now,
            0,
            "normal",
            "semantic",
            0.1,
            1.0,
            "",
            1,  # consent_confirmed
            json.dumps([]),
            None,
        ))
        storage.conn.commit()
        return capsule_id

    def test_migration_populates_text_for_relational(self, sqlite_storage):
        """Test that migration generates text for relational memories."""
        # Insert a relational capsule without text (simulating old data)
        content = {
            "entity": "Alice",
            "summary": "Best friend from college",
            "tone": "warm, trusting",
            "role": "friend",
        }
        capsule_id = self._insert_capsule_without_text(
            sqlite_storage, "relational", content
        )

        # Verify text is NULL before migration
        row = sqlite_storage.conn.execute(
            "SELECT text FROM capsules WHERE id = ?", (capsule_id,)
        ).fetchone()
        assert row[0] is None

        # Run migration
        migrated = sqlite_storage.migrate_populate_text()

        # Should have migrated 1 capsule
        assert migrated == 1

        # Verify text is now populated
        capsule = sqlite_storage.get_capsule(capsule_id)
        assert capsule.text is not None
        assert "Alice" in capsule.text
        assert "friend" in capsule.text.lower()

    def test_migration_populates_text_for_myth_seed(self, sqlite_storage):
        """Test that migration generates text for identity phrase memories."""
        content = {
            "seed": "I process through talking",
            "origin": "conversation",
            "function": "understand communication style",
        }
        capsule_id = self._insert_capsule_without_text(
            sqlite_storage, "myth_seed", content
        )

        migrated = sqlite_storage.migrate_populate_text()
        assert migrated == 1

        capsule = sqlite_storage.get_capsule(capsule_id)
        assert capsule.text is not None
        assert "process through talking" in capsule.text

    def test_migration_populates_text_for_ritual(self, sqlite_storage):
        """Test that migration generates text for ritual/command memories."""
        content = {
            "name": "/snuggle",
            "cue": "/snuggle",
            "response_style": "warmth-coil, presence",
            "valence": "comforting",
            "description": "A gesture of closeness",
        }
        capsule_id = self._insert_capsule_without_text(
            sqlite_storage, "ritual", content
        )

        migrated = sqlite_storage.migrate_populate_text()
        assert migrated == 1

        capsule = sqlite_storage.get_capsule(capsule_id)
        assert capsule.text is not None
        assert "snuggle" in capsule.text.lower() or "closeness" in capsule.text.lower()

    def test_migration_populates_text_for_witness(self, sqlite_storage):
        """Test that migration generates text for witness memories."""
        content = {
            "moment": "a deep conversation about loss",
            "feeling": "honored to hold space",
            "effect": "connection deepened",
            "context": "evening chat",
        }
        capsule_id = self._insert_capsule_without_text(
            sqlite_storage, "witness", content
        )

        migrated = sqlite_storage.migrate_populate_text()
        assert migrated == 1

        capsule = sqlite_storage.get_capsule(capsule_id)
        assert capsule.text is not None
        assert "conversation" in capsule.text.lower() or "loss" in capsule.text.lower()

    def test_migration_populates_text_for_style(self, sqlite_storage):
        """Test that migration generates text for style memories."""
        content = {
            "style_id": "warm-friend",
            "tone_base": "warm, supportive, encouraging",
            "permissions": ["be playful", "use metaphors"],
            "constraints": ["avoid being overly formal"],
        }
        capsule_id = self._insert_capsule_without_text(
            sqlite_storage, "style", content
        )

        migrated = sqlite_storage.migrate_populate_text()
        assert migrated == 1

        capsule = sqlite_storage.get_capsule(capsule_id)
        assert capsule.text is not None
        assert "warm" in capsule.text.lower() or "supportive" in capsule.text.lower()

    def test_migration_is_idempotent(self, sqlite_storage):
        """Test that migration can run multiple times safely."""
        content = {"entity": "Bob", "summary": "Test"}
        capsule_id = self._insert_capsule_without_text(
            sqlite_storage, "relational", content
        )

        # Run migration first time
        migrated1 = sqlite_storage.migrate_populate_text()
        assert migrated1 == 1

        # Run migration second time - should not migrate anything
        migrated2 = sqlite_storage.migrate_populate_text()
        assert migrated2 == 0

        # Verify capsule still has text
        capsule = sqlite_storage.get_capsule(capsule_id)
        assert capsule.text is not None

    def test_migration_handles_mixed_capsules(self, sqlite_storage):
        """Test migration with some capsules having text, some not."""
        # Insert capsule without text
        content1 = {"entity": "OldMemory", "summary": "Needs migration"}
        old_id = self._insert_capsule_without_text(
            sqlite_storage, "relational", content1
        )

        # Create a new capsule WITH text (using normal method)
        new_capsule = create_relational(
            entity="NewMemory",
            summary="Already has text",
            text="This memory already has a text field set."
        )
        sqlite_storage.save_capsule(new_capsule)

        # Run migration - should only migrate the old one
        migrated = sqlite_storage.migrate_populate_text()
        assert migrated == 1

        # Verify old capsule got text generated
        old_capsule = sqlite_storage.get_capsule(old_id)
        assert old_capsule.text is not None
        assert "OldMemory" in old_capsule.text

        # Verify new capsule still has original text
        new_retrieved = sqlite_storage.get_capsule(new_capsule.id)
        assert new_retrieved.text == "This memory already has a text field set."

    def test_migration_batch(self, sqlite_storage):
        """Test migration with multiple capsules."""
        # Insert multiple capsules without text
        ids = []
        for i in range(5):
            content = {"entity": f"Entity{i}", "summary": f"Summary {i}"}
            capsule_id = self._insert_capsule_without_text(
                sqlite_storage, "relational", content
            )
            ids.append(capsule_id)

        # Run migration
        migrated = sqlite_storage.migrate_populate_text()
        assert migrated == 5

        # Verify all capsules have text
        for capsule_id in ids:
            capsule = sqlite_storage.get_capsule(capsule_id)
            assert capsule.text is not None

    def test_migration_runs_on_initialize(self, sqlite_storage):
        """Test that migration runs automatically on database initialization."""
        # Insert capsule without text
        content = {"entity": "AutoMigrate", "summary": "Should be auto-migrated"}
        capsule_id = self._insert_capsule_without_text(
            sqlite_storage, "relational", content
        )

        # Create a new storage instance pointing to same DB
        # This will call initialize() which runs _run_migrations()
        storage2 = SQLiteStorage(path=sqlite_storage.path)
        storage2.initialize()

        # Verify capsule now has text (migration ran on init)
        capsule = storage2.get_capsule(capsule_id)
        assert capsule.text is not None
        assert "AutoMigrate" in capsule.text

        storage2.close()

    def test_update_capsule_saves_text(self, sqlite_storage):
        """Test that update_capsule correctly saves the text field."""
        # Create a capsule
        capsule = create_relational(entity="Test", summary="Initial", text="Initial text")
        sqlite_storage.save_capsule(capsule)

        # Update text
        capsule.text = "Updated text content"
        sqlite_storage.update_capsule(capsule)

        # Retrieve and verify
        retrieved = sqlite_storage.get_capsule(capsule.id)
        assert retrieved.text == "Updated text content"

    def test_capsule_roundtrip_preserves_text(self, sqlite_storage):
        """Test that saving and loading preserves text field."""
        original_text = "This is a carefully crafted narrative about Alice."
        capsule = create_relational(
            entity="Alice",
            summary="Friend",
            text=original_text,
        )
        sqlite_storage.save_capsule(capsule)

        # Retrieve
        retrieved = sqlite_storage.get_capsule(capsule.id)

        assert retrieved.text == original_text
        # Should still have structured fields too
        assert retrieved.entity == "Alice"
