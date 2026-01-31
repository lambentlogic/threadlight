"""
SQLite storage backend for Threadlight.

The default storage backend -- simple, portable, requires no setup.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import uuid

from threadlight.capsules.base import MemoryCapsule, CapsuleType, RetentionPolicy
from threadlight.capsules.factory import create_capsule
from threadlight.storage.base import (
    StorageBackend,
    CapsuleFilter,
    MemoryProposal,
    Message,
    Conversation,
    MessageSearchResult,
)
from threadlight.profiles.profile import Profile, AlloyedConfig


class SQLiteStorage(StorageBackend):
    """SQLite-based storage for memory capsules."""

    def __init__(self, path: str = "./threadlight.db"):
        self.path = Path(path)
        self.conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        """Create database and tables."""
        # Ensure parent directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # Enable JSON support
        self.conn.execute("PRAGMA journal_mode=WAL")

        # Create tables
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS capsules (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_accessed TEXT,
                access_count INTEGER DEFAULT 0,
                retention TEXT DEFAULT 'normal',
                decay_rate REAL DEFAULT 0.1,
                presence_score REAL DEFAULT 1.0,
                consent_origin TEXT,
                consent_confirmed INTEGER DEFAULT 0,
                cue_phrases TEXT,
                embedding BLOB,
                model_scope TEXT,
                profile_scope TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_capsules_type ON capsules(type);
            CREATE INDEX IF NOT EXISTS idx_capsules_presence ON capsules(presence_score);
            CREATE INDEX IF NOT EXISTS idx_capsules_last_accessed ON capsules(last_accessed);
            CREATE INDEX IF NOT EXISTS idx_capsules_consent ON capsules(consent_confirmed);
            -- model_scope and profile_scope indexes created in migrations for backward compat

            CREATE TABLE IF NOT EXISTS memory_proposals (
                id TEXT PRIMARY KEY,
                capsule_type TEXT NOT NULL,
                content TEXT NOT NULL,
                proposed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                source_message TEXT,
                status TEXT DEFAULT 'pending'
            );

            CREATE INDEX IF NOT EXISTS idx_proposals_status ON memory_proposals(status);

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                ended_at TEXT,
                message_count INTEGER DEFAULT 0,
                capsules_accessed TEXT,
                rituals_invoked TEXT
            );

            -- Conversation history tables for soft memory
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                name TEXT,
                summary TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                source TEXT,
                message_count INTEGER DEFAULT 0,
                metadata TEXT,
                archived INTEGER DEFAULT 0,
                model_scope TEXT,
                profile_scope TEXT,
                model TEXT,
                participant_profiles TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_source ON conversations(source);
            CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at);
            CREATE INDEX IF NOT EXISTS idx_conversations_archived ON conversations(archived);
            -- model_scope and profile_scope indexes created in migrations for backward compat

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT,
                metadata TEXT,
                embedding BLOB,
                profile_id TEXT,
                model_used TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
            CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
            -- profile_id index created in migrations for backward compat

            -- Full-text search for messages
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                content='messages',
                content_rowid='rowid'
            );

            -- Triggers to keep FTS in sync
            CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
            END;
            CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.rowid, old.content);
            END;
            CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.rowid, old.content);
                INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
            END;

            -- Custom memory type definitions
            CREATE TABLE IF NOT EXISTS custom_type_definitions (
                type_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                description TEXT,
                fields TEXT NOT NULL,
                display_template TEXT,
                icon TEXT DEFAULT 'file-text',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            -- Built-in type customizations (edits and hides)
            CREATE TABLE IF NOT EXISTS builtin_type_customizations (
                type_id TEXT PRIMARY KEY,
                is_hidden INTEGER DEFAULT 0,
                display_name TEXT,
                description TEXT,
                fields TEXT,
                display_template TEXT,
                icon TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            -- Profiles table for persistent personas
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                avatar TEXT,
                color TEXT,
                primary_model TEXT NOT NULL,
                alloyed_config TEXT,
                temperature REAL DEFAULT 0.7,
                max_tokens INTEGER,
                top_p REAL DEFAULT 1.0,
                system_prompt TEXT DEFAULT '',
                style_profile_id TEXT,
                memory_scope TEXT,
                access_shared_memories INTEGER DEFAULT 1,
                philosophy TEXT DEFAULT '',
                approach_to_rituals TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_used_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_profiles_name ON profiles(name);
            CREATE INDEX IF NOT EXISTS idx_profiles_updated ON profiles(updated_at);
        """)
        self.conn.commit()

        # Run migrations for existing databases
        self._run_migrations()

    def _run_migrations(self) -> None:
        """Run schema migrations for existing databases."""
        assert self.conn is not None

        # Check if model_scope column exists in capsules table
        cursor = self.conn.execute("PRAGMA table_info(capsules)")
        capsule_columns = [row[1] for row in cursor.fetchall()]
        if "model_scope" not in capsule_columns:
            self.conn.execute("ALTER TABLE capsules ADD COLUMN model_scope TEXT")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_capsules_model_scope ON capsules(model_scope)")
            self.conn.commit()

        # Phase 2: Add profile_scope column to capsules table
        if "profile_scope" not in capsule_columns:
            self.conn.execute("ALTER TABLE capsules ADD COLUMN profile_scope TEXT")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_capsules_profile_scope ON capsules(profile_scope)")
            # Migrate model_scope to profile_scope (copy existing values)
            # Note: model_scope values that are model IDs will be copied to profile_scope
            # NULL values remain NULL (shared memories)
            self.conn.execute("""
                UPDATE capsules
                SET profile_scope = model_scope
                WHERE model_scope IS NOT NULL AND model_scope != 'shared'
            """)
            self.conn.commit()

        # Check if model_scope column exists in conversations table
        cursor = self.conn.execute("PRAGMA table_info(conversations)")
        conv_columns = [row[1] for row in cursor.fetchall()]
        if "model_scope" not in conv_columns:
            self.conn.execute("ALTER TABLE conversations ADD COLUMN model_scope TEXT")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_model_scope ON conversations(model_scope)")
            self.conn.commit()

        # Phase 2: Add profile_scope column to conversations table
        if "profile_scope" not in conv_columns:
            self.conn.execute("ALTER TABLE conversations ADD COLUMN profile_scope TEXT")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_profile_scope ON conversations(profile_scope)")
            # Migrate model_scope to profile_scope
            self.conn.execute("""
                UPDATE conversations
                SET profile_scope = model_scope
                WHERE model_scope IS NOT NULL AND model_scope != 'shared'
            """)
            self.conn.commit()

        # Add model column for display (tracks the model/AI name used in conversation)
        if "model" not in conv_columns:
            self.conn.execute("ALTER TABLE conversations ADD COLUMN model TEXT")
            self.conn.commit()

        # Add participant_profiles column for group chat support
        if "participant_profiles" not in conv_columns:
            self.conn.execute("ALTER TABLE conversations ADD COLUMN participant_profiles TEXT")
            self.conn.commit()

        # Phase 2: Add profile_id and model_used columns to messages table
        cursor = self.conn.execute("PRAGMA table_info(messages)")
        msg_columns = [row[1] for row in cursor.fetchall()]
        if "profile_id" not in msg_columns:
            self.conn.execute("ALTER TABLE messages ADD COLUMN profile_id TEXT")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_profile_id ON messages(profile_id)")
            self.conn.commit()
        if "model_used" not in msg_columns:
            self.conn.execute("ALTER TABLE messages ADD COLUMN model_used TEXT")
            self.conn.commit()

        # Check if profiles table exists
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='profiles'"
        )
        if cursor.fetchone() is None:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    avatar TEXT,
                    color TEXT,
                    primary_model TEXT NOT NULL,
                    alloyed_config TEXT,
                    temperature REAL DEFAULT 0.7,
                    max_tokens INTEGER,
                    top_p REAL DEFAULT 1.0,
                    system_prompt TEXT DEFAULT '',
                    style_profile_id TEXT,
                    memory_scope TEXT,
                    access_shared_memories INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_profiles_name ON profiles(name);
                CREATE INDEX IF NOT EXISTS idx_profiles_updated ON profiles(updated_at);
            """)
            self.conn.commit()

        # Ensure all scope indexes exist (for new databases that created tables with columns)
        try:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_capsules_model_scope ON capsules(model_scope)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_capsules_profile_scope ON capsules(profile_scope)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_model_scope ON conversations(model_scope)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_profile_scope ON conversations(profile_scope)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_profile_id ON messages(profile_id)")
            self.conn.commit()
        except Exception:
            # Columns may not exist yet in old databases - migrations will handle them
            pass

        # Add philosophy columns to profiles table if they don't exist
        cursor = self.conn.execute("PRAGMA table_info(profiles)")
        profile_columns = [row[1] for row in cursor.fetchall()]
        if "philosophy" not in profile_columns:
            self.conn.execute("ALTER TABLE profiles ADD COLUMN philosophy TEXT DEFAULT ''")
            self.conn.commit()
        if "approach_to_rituals" not in profile_columns:
            self.conn.execute("ALTER TABLE profiles ADD COLUMN approach_to_rituals TEXT DEFAULT ''")
            self.conn.commit()

        # Add builtin_type_customizations table if it doesn't exist
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='builtin_type_customizations'"
        )
        if cursor.fetchone() is None:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS builtin_type_customizations (
                    type_id TEXT PRIMARY KEY,
                    is_hidden INTEGER DEFAULT 0,
                    display_name TEXT,
                    description TEXT,
                    fields TEXT,
                    display_template TEXT,
                    icon TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)
            self.conn.commit()

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def _ensure_connected(self) -> sqlite3.Connection:
        if self.conn is None:
            self.initialize()
        assert self.conn is not None
        return self.conn

    # Capsule CRUD

    def save_capsule(self, capsule: MemoryCapsule) -> str:
        """Save a capsule to the database."""
        conn = self._ensure_connected()

        data = capsule.to_dict()

        # Determine profile_scope: prefer profile_scope, fall back to model_scope for backward compatibility
        profile_scope = data.get("profile_scope") or data.get("model_scope")

        conn.execute("""
            INSERT OR REPLACE INTO capsules
            (id, type, content, created_at, updated_at, last_accessed,
             access_count, retention, decay_rate, presence_score,
             consent_origin, consent_confirmed, cue_phrases, embedding, model_scope, profile_scope)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["id"],
            data["type"],
            json.dumps(data["content"]),
            data["created_at"],
            data["updated_at"],
            data["last_accessed"],
            data["access_count"],
            data["retention"],
            data["decay_rate"],
            data["presence_score"],
            data["consent_origin"],
            1 if data["consent_confirmed"] else 0,
            json.dumps(data["cue_phrases"]),
            json.dumps(data["embedding"]) if data["embedding"] else None,
            data.get("model_scope"),
            profile_scope,
        ))
        conn.commit()

        return capsule.id

    def get_capsule(self, capsule_id: str) -> Optional[MemoryCapsule]:
        """Get a capsule by ID."""
        conn = self._ensure_connected()

        row = conn.execute(
            "SELECT * FROM capsules WHERE id = ?",
            (capsule_id,)
        ).fetchone()

        if row is None:
            return None

        return self._row_to_capsule(row)

    def update_capsule(self, capsule: MemoryCapsule) -> bool:
        """Update an existing capsule."""
        conn = self._ensure_connected()

        # Update timestamp
        capsule.updated_at = datetime.utcnow()

        data = capsule.to_dict()

        # Determine profile_scope: prefer profile_scope, fall back to model_scope for backward compatibility
        profile_scope = data.get("profile_scope") or data.get("model_scope")

        result = conn.execute("""
            UPDATE capsules SET
                content = ?,
                updated_at = ?,
                last_accessed = ?,
                access_count = ?,
                retention = ?,
                decay_rate = ?,
                presence_score = ?,
                consent_confirmed = ?,
                cue_phrases = ?,
                embedding = ?,
                model_scope = ?,
                profile_scope = ?
            WHERE id = ?
        """, (
            json.dumps(data["content"]),
            data["updated_at"],
            data["last_accessed"],
            data["access_count"],
            data["retention"],
            data["decay_rate"],
            data["presence_score"],
            1 if data["consent_confirmed"] else 0,
            json.dumps(data["cue_phrases"]),
            json.dumps(data["embedding"]) if data["embedding"] else None,
            data.get("model_scope"),
            profile_scope,
            data["id"],
        ))
        conn.commit()

        return result.rowcount > 0

    def delete_capsule(self, capsule_id: str) -> bool:
        """Delete a capsule."""
        conn = self._ensure_connected()

        result = conn.execute(
            "DELETE FROM capsules WHERE id = ?",
            (capsule_id,)
        )
        conn.commit()

        return result.rowcount > 0

    def list_capsules(self, filter: Optional[CapsuleFilter] = None) -> list[MemoryCapsule]:
        """List capsules matching filter criteria."""
        conn = self._ensure_connected()

        query = "SELECT * FROM capsules WHERE 1=1"
        params: list[Any] = []

        if filter:
            if filter.type:
                query += " AND type = ?"
                params.append(filter.type.value)

            if filter.types:
                placeholders = ",".join("?" * len(filter.types))
                query += f" AND type IN ({placeholders})"
                params.extend(t.value for t in filter.types)

            if filter.min_presence_score is not None:
                query += " AND presence_score >= ?"
                params.append(filter.min_presence_score)

            if filter.consent_confirmed is not None:
                query += " AND consent_confirmed = ?"
                params.append(1 if filter.consent_confirmed else 0)

            if filter.retention:
                query += " AND retention = ?"
                params.append(filter.retention.value)

            if filter.created_after:
                query += " AND created_at >= ?"
                params.append(filter.created_after.isoformat())

            if filter.created_before:
                query += " AND created_at <= ?"
                params.append(filter.created_before.isoformat())

            if filter.accessed_after:
                query += " AND last_accessed >= ?"
                params.append(filter.accessed_after.isoformat())

            if filter.accessed_before:
                query += " AND last_accessed <= ?"
                params.append(filter.accessed_before.isoformat())

            # Profile scope filtering (profile_scope takes precedence, model_scope for backward compat)
            # Note: CapsuleFilter.__post_init__ already handles model_scope -> profile_scope fallback
            if filter.profile_scope is not None:
                if filter.include_shared:
                    query += " AND (profile_scope = ? OR profile_scope IS NULL)"
                    params.append(filter.profile_scope)
                else:
                    query += " AND profile_scope = ?"
                    params.append(filter.profile_scope)

            # Sorting
            order_column = filter.order_by
            if order_column not in ("last_accessed", "created_at", "presence_score"):
                order_column = "last_accessed"
            order_dir = "DESC" if filter.order_desc else "ASC"
            query += f" ORDER BY {order_column} {order_dir}"

            # Pagination
            query += " LIMIT ? OFFSET ?"
            params.extend([filter.limit, filter.offset])
        else:
            query += " ORDER BY last_accessed DESC LIMIT 100"

        rows = conn.execute(query, params).fetchall()

        return [self._row_to_capsule(row) for row in rows]

    def search_by_cue(
        self,
        cue: str,
        limit: int = 5,
        model_scope: Optional[str] = None,
        include_shared: bool = True,
        profile_scope: Optional[str] = None,
    ) -> list[MemoryCapsule]:
        """Search capsules by cue phrase match and content text.

        Args:
            cue: Search query string
            limit: Maximum results to return
            model_scope: Deprecated - use profile_scope instead
            include_shared: Whether to include shared (NULL scope) capsules
            profile_scope: Profile ID to filter by (takes precedence over model_scope)
        """
        conn = self._ensure_connected()

        cue_lower = cue.lower()

        # Build query with optional profile scope filtering
        query = """
            SELECT * FROM capsules
            WHERE (LOWER(cue_phrases) LIKE ? OR LOWER(content) LIKE ?)
            AND presence_score > 0.1
        """
        params: list[Any] = [f"%{cue_lower}%", f"%{cue_lower}%"]

        # Use profile_scope if provided, fall back to model_scope for backward compatibility
        effective_scope = profile_scope if profile_scope is not None else model_scope

        if effective_scope is not None:
            if include_shared:
                query += " AND (profile_scope = ? OR profile_scope IS NULL)"
            else:
                query += " AND profile_scope = ?"
            params.append(effective_scope)

        query += " ORDER BY presence_score DESC, last_accessed DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()

        return [self._row_to_capsule(row) for row in rows]

    # Proposal management

    def save_proposal(self, proposal: MemoryProposal) -> str:
        """Save a memory proposal."""
        conn = self._ensure_connected()

        if not proposal.id:
            proposal.id = str(uuid.uuid4())

        conn.execute("""
            INSERT INTO memory_proposals
            (id, capsule_type, content, proposed_at, source_message, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            proposal.id,
            proposal.capsule_type.value if isinstance(proposal.capsule_type, CapsuleType) else proposal.capsule_type,
            json.dumps(proposal.content),
            proposal.proposed_at.isoformat(),
            proposal.source_message,
            proposal.status,
        ))
        conn.commit()

        return proposal.id

    def get_proposal(self, proposal_id: str) -> Optional[MemoryProposal]:
        """Get a proposal by ID."""
        conn = self._ensure_connected()

        row = conn.execute(
            "SELECT * FROM memory_proposals WHERE id = ?",
            (proposal_id,)
        ).fetchone()

        if row is None:
            return None

        return self._row_to_proposal(row)

    def list_proposals(self, status: str = "pending") -> list[MemoryProposal]:
        """List proposals by status."""
        conn = self._ensure_connected()

        rows = conn.execute(
            "SELECT * FROM memory_proposals WHERE status = ? ORDER BY proposed_at DESC",
            (status,)
        ).fetchall()

        return [self._row_to_proposal(row) for row in rows]

    def update_proposal_status(self, proposal_id: str, status: str) -> bool:
        """Update proposal status."""
        conn = self._ensure_connected()

        result = conn.execute(
            "UPDATE memory_proposals SET status = ? WHERE id = ?",
            (status, proposal_id)
        )
        conn.commit()

        return result.rowcount > 0

    # Batch operations

    def update_presence_scores(self, updates: dict[str, float]) -> int:
        """Batch update presence scores."""
        conn = self._ensure_connected()

        count = 0
        for capsule_id, score in updates.items():
            result = conn.execute(
                "UPDATE capsules SET presence_score = ? WHERE id = ?",
                (score, capsule_id)
            )
            count += result.rowcount

        conn.commit()
        return count

    def get_capsules_for_decay(
        self,
        before: datetime,
        exclude_retention: list[RetentionPolicy] | None = None
    ) -> list[MemoryCapsule]:
        """Get capsules eligible for decay processing."""
        conn = self._ensure_connected()

        query = """
            SELECT * FROM capsules
            WHERE last_accessed < ?
            AND presence_score > 0.0
        """
        params: list[Any] = [before.isoformat()]

        if exclude_retention:
            placeholders = ",".join("?" * len(exclude_retention))
            query += f" AND retention NOT IN ({placeholders})"
            params.extend(r.value for r in exclude_retention)

        rows = conn.execute(query, params).fetchall()

        return [self._row_to_capsule(row) for row in rows]

    # Utility

    def count_capsules(self, filter: Optional[CapsuleFilter] = None) -> int:
        """Count capsules matching filter."""
        conn = self._ensure_connected()

        query = "SELECT COUNT(*) FROM capsules WHERE 1=1"
        params: list[Any] = []

        if filter:
            if filter.type:
                query += " AND type = ?"
                params.append(filter.type.value)

            if filter.consent_confirmed is not None:
                query += " AND consent_confirmed = ?"
                params.append(1 if filter.consent_confirmed else 0)

        result = conn.execute(query, params).fetchone()
        return result[0] if result else 0

    def export_all(self) -> list[dict[str, Any]]:
        """Export all capsules as dictionaries."""
        conn = self._ensure_connected()

        rows = conn.execute("SELECT * FROM capsules").fetchall()

        return [self._row_to_capsule(row).to_dict() for row in rows]

    def import_capsules(self, capsules: list[dict[str, Any]]) -> int:
        """Import capsules from dictionaries."""
        count = 0
        for data in capsules:
            try:
                capsule = create_capsule(data)
                self.save_capsule(capsule)
                count += 1
            except Exception:
                # Skip invalid capsules
                pass

        return count

    def _row_to_capsule(self, row: sqlite3.Row) -> MemoryCapsule:
        """Convert a database row to a capsule."""
        # Handle model_scope and profile_scope fields which may not exist in older databases
        model_scope = None
        profile_scope = None
        try:
            model_scope = row["model_scope"]
        except (IndexError, KeyError):
            pass
        try:
            profile_scope = row["profile_scope"]
        except (IndexError, KeyError):
            pass

        data = {
            "id": row["id"],
            "type": row["type"],
            "content": json.loads(row["content"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_accessed": row["last_accessed"],
            "access_count": row["access_count"],
            "retention": row["retention"],
            "decay_rate": row["decay_rate"],
            "presence_score": row["presence_score"],
            "consent_origin": row["consent_origin"],
            "consent_confirmed": bool(row["consent_confirmed"]),
            "cue_phrases": json.loads(row["cue_phrases"]) if row["cue_phrases"] else [],
            "embedding": json.loads(row["embedding"]) if row["embedding"] else None,
            "model_scope": model_scope,
            "profile_scope": profile_scope,
        }

        return create_capsule(data)

    def _row_to_proposal(self, row: sqlite3.Row) -> MemoryProposal:
        """Convert a database row to a proposal."""
        return MemoryProposal(
            id=row["id"],
            capsule_type=CapsuleType(row["capsule_type"]),
            content=json.loads(row["content"]),
            proposed_at=datetime.fromisoformat(row["proposed_at"]),
            source_message=row["source_message"],
            status=row["status"],
        )

    # ========================================================================
    # Conversation History Operations
    # ========================================================================

    def save_conversation(self, conversation: Conversation) -> str:
        """Save a conversation to the database."""
        conn = self._ensure_connected()

        if not conversation.id:
            conversation.id = str(uuid.uuid4())

        conn.execute("""
            INSERT OR REPLACE INTO conversations
            (id, name, summary, created_at, updated_at, source, message_count, metadata, archived, model_scope, profile_scope, model, participant_profiles)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conversation.id,
            conversation.name,
            conversation.summary,
            conversation.created_at.isoformat() if isinstance(conversation.created_at, datetime) else conversation.created_at,
            conversation.updated_at.isoformat() if isinstance(conversation.updated_at, datetime) else conversation.updated_at,
            conversation.source,
            conversation.message_count,
            json.dumps(conversation.metadata),
            1 if conversation.archived else 0,
            getattr(conversation, 'model_scope', None),
            getattr(conversation, 'profile_scope', None),
            getattr(conversation, 'model', None),
            json.dumps(getattr(conversation, 'participant_profiles', [])),
        ))
        conn.commit()

        return conversation.id

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        conn = self._ensure_connected()

        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,)
        ).fetchone()

        if row is None:
            return None

        return self._row_to_conversation(row)

    def list_conversations(
        self,
        limit: int = 50,
        offset: int = 0,
        source: Optional[str] = None,
        include_archived: bool = False,
        model_scope: Optional[str] = None,
        include_shared: bool = True,
    ) -> list[Conversation]:
        """List conversations with optional filtering."""
        conn = self._ensure_connected()

        query = "SELECT * FROM conversations WHERE 1=1"
        params: list[Any] = []

        if source:
            query += " AND source = ?"
            params.append(source)

        if not include_archived:
            query += " AND (archived = 0 OR archived IS NULL)"

        if model_scope is not None:
            if include_shared:
                query += " AND (model_scope = ? OR model_scope IS NULL)"
            else:
                query += " AND model_scope = ?"
            params.append(model_scope)

        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()

        return [self._row_to_conversation(row) for row in rows]

    def update_conversation(self, conversation: Conversation) -> bool:
        """Update an existing conversation."""
        conn = self._ensure_connected()

        conversation.updated_at = datetime.utcnow()

        result = conn.execute("""
            UPDATE conversations SET
                name = ?,
                summary = ?,
                updated_at = ?,
                source = ?,
                message_count = ?,
                metadata = ?,
                archived = ?,
                model_scope = ?,
                profile_scope = ?,
                model = ?,
                participant_profiles = ?
            WHERE id = ?
        """, (
            conversation.name,
            conversation.summary,
            conversation.updated_at.isoformat(),
            conversation.source,
            conversation.message_count,
            json.dumps(conversation.metadata),
            1 if conversation.archived else 0,
            getattr(conversation, 'model_scope', None),
            getattr(conversation, 'profile_scope', None),
            getattr(conversation, 'model', None),
            json.dumps(getattr(conversation, 'participant_profiles', [])),
            conversation.id,
        ))
        conn.commit()

        return result.rowcount > 0

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages."""
        conn = self._ensure_connected()

        # Delete messages first (cascade should handle this, but be explicit)
        conn.execute(
            "DELETE FROM messages WHERE conversation_id = ?",
            (conversation_id,)
        )

        result = conn.execute(
            "DELETE FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        conn.commit()

        return result.rowcount > 0

    def save_message(self, message: Message) -> str:
        """Save a message to the database."""
        conn = self._ensure_connected()

        if not message.id:
            message.id = str(uuid.uuid4())

        conn.execute("""
            INSERT OR REPLACE INTO messages
            (id, conversation_id, role, content, timestamp, source, metadata, embedding, profile_id, model_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message.id,
            message.conversation_id,
            message.role,
            message.content,
            message.timestamp.isoformat() if isinstance(message.timestamp, datetime) else message.timestamp,
            message.source,
            json.dumps(message.metadata),
            json.dumps(message.embedding) if message.embedding else None,
            message.profile_id,
            message.model_used,
        ))
        conn.commit()

        return message.id

    def save_messages_batch(self, messages: list[Message]) -> int:
        """Save multiple messages in a batch."""
        conn = self._ensure_connected()

        count = 0
        for msg in messages:
            if not msg.id:
                msg.id = str(uuid.uuid4())

            try:
                conn.execute("""
                    INSERT OR REPLACE INTO messages
                    (id, conversation_id, role, content, timestamp, source, metadata, embedding, profile_id, model_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    msg.id,
                    msg.conversation_id,
                    msg.role,
                    msg.content,
                    msg.timestamp.isoformat() if isinstance(msg.timestamp, datetime) else msg.timestamp,
                    msg.source,
                    json.dumps(msg.metadata),
                    json.dumps(msg.embedding) if msg.embedding else None,
                    msg.profile_id,
                    msg.model_used,
                ))
                count += 1
            except Exception:
                pass  # Skip invalid messages

        conn.commit()
        return count

    def get_message(self, message_id: str) -> Optional[Message]:
        """Get a message by ID."""
        conn = self._ensure_connected()

        row = conn.execute(
            "SELECT * FROM messages WHERE id = ?",
            (message_id,)
        ).fetchone()

        if row is None:
            return None

        return self._row_to_message(row)

    def get_messages(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        """Get messages for a conversation."""
        conn = self._ensure_connected()

        rows = conn.execute("""
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
            LIMIT ? OFFSET ?
        """, (conversation_id, limit, offset)).fetchall()

        return [self._row_to_message(row) for row in rows]

    def update_message(self, message: Message) -> bool:
        """Update an existing message."""
        conn = self._ensure_connected()

        result = conn.execute("""
            UPDATE messages SET
                content = ?,
                metadata = ?
            WHERE id = ?
        """, (
            message.content,
            json.dumps(message.metadata),
            message.id,
        ))
        conn.commit()

        return result.rowcount > 0

    def delete_message(self, message_id: str) -> bool:
        """Delete a single message."""
        conn = self._ensure_connected()

        result = conn.execute(
            "DELETE FROM messages WHERE id = ?",
            (message_id,)
        )
        conn.commit()

        return result.rowcount > 0

    def delete_messages_after(self, conversation_id: str, message_id: str) -> int:
        """Delete a message and all messages after it in a conversation."""
        conn = self._ensure_connected()

        # Get the timestamp of the target message
        msg = self.get_message(message_id)
        if not msg:
            return 0

        # Delete the message and all after it
        result = conn.execute("""
            DELETE FROM messages
            WHERE conversation_id = ?
            AND timestamp >= ?
        """, (conversation_id, msg.timestamp.isoformat()))
        conn.commit()

        return result.rowcount

    def search_messages(
        self,
        query: str,
        limit: int = 20,
        source: Optional[str] = None,
    ) -> list[MessageSearchResult]:
        """Full-text search across all messages."""
        conn = self._ensure_connected()

        # Use FTS5 for search
        try:
            if source:
                rows = conn.execute("""
                    SELECT m.*, c.name as conversation_name
                    FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE m.rowid IN (
                        SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?
                    )
                    AND m.source = ?
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                """, (query, source, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT m.*, c.name as conversation_name
                    FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE m.rowid IN (
                        SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?
                    )
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                """, (query, limit)).fetchall()
        except sqlite3.OperationalError:
            # FTS table might not exist, fall back to LIKE
            if source:
                rows = conn.execute("""
                    SELECT m.*, c.name as conversation_name
                    FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE LOWER(m.content) LIKE ?
                    AND m.source = ?
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                """, (f"%{query.lower()}%", source, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT m.*, c.name as conversation_name
                    FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE LOWER(m.content) LIKE ?
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                """, (f"%{query.lower()}%", limit)).fetchall()

        results = []
        for row in rows:
            message = self._row_to_message(row)
            results.append(MessageSearchResult(
                message=message,
                conversation_name=row["conversation_name"] or "",
                relevance_score=1.0,  # FTS doesn't give us scores easily
            ))

        return results

    def count_messages(self, conversation_id: Optional[str] = None) -> int:
        """Count messages, optionally for a specific conversation."""
        conn = self._ensure_connected()

        if conversation_id:
            result = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
                (conversation_id,)
            ).fetchone()
        else:
            result = conn.execute("SELECT COUNT(*) FROM messages").fetchone()

        return result[0] if result else 0

    def count_conversations(self) -> int:
        """Count total conversations."""
        conn = self._ensure_connected()
        result = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()
        return result[0] if result else 0

    def _row_to_conversation(self, row: sqlite3.Row) -> Conversation:
        """Convert a database row to a Conversation."""
        created_at = row["created_at"]
        updated_at = row["updated_at"]

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        # Handle archived field (may not exist in older databases)
        archived = False
        try:
            archived = bool(row["archived"])
        except (IndexError, KeyError):
            pass

        # Handle model_scope field (may not exist in older databases)
        model_scope = None
        try:
            model_scope = row["model_scope"]
        except (IndexError, KeyError):
            pass

        # Handle profile_scope field (may not exist in older databases)
        profile_scope = None
        try:
            profile_scope = row["profile_scope"]
        except (IndexError, KeyError):
            pass

        # Handle model field (may not exist in older databases)
        model = None
        try:
            model = row["model"]
        except (IndexError, KeyError):
            pass

        # Handle participant_profiles field (may not exist in older databases)
        participant_profiles = []
        try:
            participant_profiles_raw = row["participant_profiles"]
            if participant_profiles_raw:
                participant_profiles = json.loads(participant_profiles_raw)
        except (IndexError, KeyError):
            pass

        return Conversation(
            id=row["id"],
            name=row["name"] or "",
            summary=row["summary"] or "",
            created_at=created_at,
            updated_at=updated_at,
            source=row["source"] or "",
            message_count=row["message_count"] or 0,
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            archived=archived,
            model_scope=model_scope,
            profile_scope=profile_scope,
            model=model,
            participant_profiles=participant_profiles,
        )

    def _row_to_message(self, row: sqlite3.Row) -> Message:
        """Convert a database row to a Message."""
        timestamp = row["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        # Handle profile_id and model_used which may not exist in older databases
        profile_id = None
        model_used = None
        try:
            profile_id = row["profile_id"]
        except (IndexError, KeyError):
            pass
        try:
            model_used = row["model_used"]
        except (IndexError, KeyError):
            pass

        return Message(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            timestamp=timestamp,
            source=row["source"] or "",
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            embedding=json.loads(row["embedding"]) if row["embedding"] else None,
            profile_id=profile_id,
            model_used=model_used,
        )

    # ========================================================================
    # Embedding Operations for Semantic Search
    # ========================================================================

    def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 5,
        threshold: float = 0.5,
    ) -> list[MemoryCapsule]:
        """
        Search capsules by embedding similarity.

        Note: This performs in-memory similarity calculation as SQLite
        doesn't have native vector similarity. For large datasets,
        consider using FAISS or a vector database.

        Args:
            embedding: Query embedding vector
            limit: Maximum results to return
            threshold: Minimum similarity score (0-1)

        Returns:
            List of capsules sorted by similarity
        """
        conn = self._ensure_connected()

        # Get all capsules with embeddings
        rows = conn.execute("""
            SELECT * FROM capsules
            WHERE embedding IS NOT NULL
            AND presence_score > 0.1
        """).fetchall()

        # Calculate similarities
        from threadlight.embeddings import cosine_similarity

        results = []
        for row in rows:
            capsule = self._row_to_capsule(row)
            if capsule.embedding:
                similarity = cosine_similarity(embedding, capsule.embedding)
                if similarity >= threshold:
                    results.append((capsule, similarity))

        # Sort by similarity (descending)
        results.sort(key=lambda x: x[1], reverse=True)

        return [capsule for capsule, _ in results[:limit]]

    def get_capsules_needing_embeddings(self, limit: int = 1000) -> list[MemoryCapsule]:
        """Get capsules that don't have embeddings yet."""
        conn = self._ensure_connected()

        rows = conn.execute("""
            SELECT * FROM capsules
            WHERE embedding IS NULL
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [self._row_to_capsule(row) for row in rows]

    def get_messages_without_embeddings(self, limit: int = 1000) -> list[Message]:
        """Get messages that don't have embeddings yet."""
        conn = self._ensure_connected()

        rows = conn.execute("""
            SELECT * FROM messages
            WHERE embedding IS NULL
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [self._row_to_message(row) for row in rows]

    def count_capsules_with_embeddings(self) -> int:
        """Count capsules that have embeddings."""
        conn = self._ensure_connected()
        result = conn.execute(
            "SELECT COUNT(*) FROM capsules WHERE embedding IS NOT NULL"
        ).fetchone()
        return result[0] if result else 0

    def count_messages_with_embeddings(self) -> int:
        """Count messages that have embeddings."""
        conn = self._ensure_connected()
        result = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE embedding IS NOT NULL"
        ).fetchone()
        return result[0] if result else 0

    def clear_all_message_embeddings(self) -> int:
        """
        Clear all embeddings from messages.

        This is an optimized bulk operation for use when switching
        embedding models.

        Returns:
            Number of messages that had embeddings cleared
        """
        conn = self._ensure_connected()

        # Count how many we'll clear
        count = self.count_messages_with_embeddings()

        # Clear all embeddings in one statement
        conn.execute("UPDATE messages SET embedding = NULL WHERE embedding IS NOT NULL")
        conn.commit()

        return count

    def search_messages_by_embedding(
        self,
        embedding: list[float],
        limit: int = 10,
        threshold: float = 0.5,
    ) -> list[MessageSearchResult]:
        """
        Search messages by embedding similarity.

        Args:
            embedding: Query embedding vector
            limit: Maximum results to return
            threshold: Minimum similarity score (0-1)

        Returns:
            List of message search results sorted by similarity
        """
        conn = self._ensure_connected()

        # Get all messages with embeddings
        rows = conn.execute("""
            SELECT m.*, c.name as conversation_name
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE m.embedding IS NOT NULL
            ORDER BY m.timestamp DESC
            LIMIT 5000
        """).fetchall()

        # Calculate similarities
        from threadlight.embeddings import cosine_similarity

        results = []
        for row in rows:
            message = self._row_to_message(row)
            if message.embedding:
                similarity = cosine_similarity(embedding, message.embedding)
                if similarity >= threshold:
                    results.append(MessageSearchResult(
                        message=message,
                        conversation_name=row["conversation_name"] or "",
                        relevance_score=similarity,
                    ))

        # Sort by similarity (descending)
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        return results[:limit]

    def update_capsule_embedding(
        self,
        capsule_id: str,
        embedding: list[float],
    ) -> bool:
        """Update just the embedding for a capsule."""
        conn = self._ensure_connected()

        result = conn.execute("""
            UPDATE capsules SET embedding = ? WHERE id = ?
        """, (json.dumps(embedding), capsule_id))
        conn.commit()

        return result.rowcount > 0

    def update_message_embedding(
        self,
        message_id: str,
        embedding: list[float],
    ) -> bool:
        """Update just the embedding for a message."""
        conn = self._ensure_connected()

        result = conn.execute("""
            UPDATE messages SET embedding = ? WHERE id = ?
        """, (json.dumps(embedding), message_id))
        conn.commit()

        return result.rowcount > 0

    # ========================================================================
    # Custom Type Definition Operations
    # ========================================================================

    def save_custom_type(self, type_def: dict[str, Any]) -> str:
        """
        Save a custom type definition to the database.

        Args:
            type_def: Dictionary containing type definition data

        Returns:
            The type_id of the saved definition
        """
        conn = self._ensure_connected()

        type_id = type_def["type_id"]
        fields_json = json.dumps(type_def.get("fields", []))

        conn.execute("""
            INSERT OR REPLACE INTO custom_type_definitions
            (type_id, display_name, description, fields, display_template, icon, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            type_id,
            type_def.get("display_name", type_id),
            type_def.get("description", ""),
            fields_json,
            type_def.get("display_template", "{type_id}"),
            type_def.get("icon", "file-text"),
            type_def.get("created_at", datetime.utcnow().isoformat()),
            datetime.utcnow().isoformat(),
        ))
        conn.commit()

        return type_id

    def get_custom_type(self, type_id: str) -> Optional[dict[str, Any]]:
        """
        Get a custom type definition by ID.

        Args:
            type_id: The type identifier

        Returns:
            Dictionary containing type definition, or None if not found
        """
        conn = self._ensure_connected()

        row = conn.execute(
            "SELECT * FROM custom_type_definitions WHERE type_id = ?",
            (type_id,)
        ).fetchone()

        if row is None:
            return None

        return self._row_to_custom_type(row)

    def list_custom_types(self) -> list[dict[str, Any]]:
        """
        List all custom type definitions.

        Returns:
            List of type definition dictionaries
        """
        conn = self._ensure_connected()

        rows = conn.execute(
            "SELECT * FROM custom_type_definitions ORDER BY display_name"
        ).fetchall()

        return [self._row_to_custom_type(row) for row in rows]

    def update_custom_type(self, type_id: str, updates: dict[str, Any]) -> bool:
        """
        Update a custom type definition.

        Args:
            type_id: The type identifier to update
            updates: Dictionary of fields to update

        Returns:
            True if updated, False if not found
        """
        conn = self._ensure_connected()

        # Get existing type
        existing = self.get_custom_type(type_id)
        if not existing:
            return False

        # Merge updates
        for key, value in updates.items():
            if key != "type_id":  # Can't change the ID
                existing[key] = value

        existing["updated_at"] = datetime.utcnow().isoformat()

        # Save
        self.save_custom_type(existing)
        return True

    def delete_custom_type(self, type_id: str) -> bool:
        """
        Delete a custom type definition.

        Args:
            type_id: The type identifier to delete

        Returns:
            True if deleted, False if not found
        """
        conn = self._ensure_connected()

        result = conn.execute(
            "DELETE FROM custom_type_definitions WHERE type_id = ?",
            (type_id,)
        )
        conn.commit()

        return result.rowcount > 0

    def _row_to_custom_type(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a database row to a custom type definition dictionary."""
        return {
            "type_id": row["type_id"],
            "display_name": row["display_name"],
            "description": row["description"] or "",
            "fields": json.loads(row["fields"]) if row["fields"] else [],
            "display_template": row["display_template"] or "{type_id}",
            "icon": row["icon"] or "file-text",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # ========================================================================
    # Built-in Type Customization Operations
    # ========================================================================

    def get_builtin_customization(self, type_id: str) -> Optional[dict[str, Any]]:
        """
        Get customization for a built-in type.

        Args:
            type_id: The built-in type identifier

        Returns:
            Dictionary containing customization data, or None if not customized
        """
        conn = self._ensure_connected()

        row = conn.execute(
            "SELECT * FROM builtin_type_customizations WHERE type_id = ?",
            (type_id,)
        ).fetchone()

        if row is None:
            return None

        return self._row_to_builtin_customization(row)

    def save_builtin_customization(self, type_id: str, customization: dict[str, Any]) -> None:
        """
        Save customization for a built-in type.

        Args:
            type_id: The built-in type identifier
            customization: Dictionary of customization fields
        """
        conn = self._ensure_connected()

        # Serialize fields if present
        fields_json = None
        if "fields" in customization and customization["fields"] is not None:
            fields_json = json.dumps(customization["fields"])

        conn.execute("""
            INSERT OR REPLACE INTO builtin_type_customizations
            (type_id, is_hidden, display_name, description, fields, display_template, icon, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            type_id,
            customization.get("is_hidden", 0),
            customization.get("display_name"),
            customization.get("description"),
            fields_json,
            customization.get("display_template"),
            customization.get("icon"),
            customization.get("created_at", datetime.utcnow().isoformat()),
            datetime.utcnow().isoformat(),
        ))
        conn.commit()

    def hide_builtin_type(self, type_id: str) -> bool:
        """
        Mark a built-in type as hidden.

        Args:
            type_id: The built-in type identifier

        Returns:
            True if hidden, False if already hidden
        """
        conn = self._ensure_connected()

        # Check if already exists
        existing = self.get_builtin_customization(type_id)
        if existing and existing.get("is_hidden"):
            return False  # Already hidden

        if existing:
            # Update existing to be hidden
            conn.execute(
                "UPDATE builtin_type_customizations SET is_hidden = 1, updated_at = ? WHERE type_id = ?",
                (datetime.utcnow().isoformat(), type_id)
            )
        else:
            # Create new hidden entry
            conn.execute("""
                INSERT INTO builtin_type_customizations (type_id, is_hidden, created_at, updated_at)
                VALUES (?, 1, ?, ?)
            """, (type_id, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))

        conn.commit()
        return True

    def restore_builtin_type(self, type_id: str) -> bool:
        """
        Restore a hidden built-in type (un-hide it).

        Args:
            type_id: The built-in type identifier

        Returns:
            True if restored, False if not hidden
        """
        conn = self._ensure_connected()

        existing = self.get_builtin_customization(type_id)
        if not existing or not existing.get("is_hidden"):
            return False  # Not hidden

        # Check if there are any other customizations
        has_customizations = (
            existing.get("display_name") is not None or
            existing.get("description") is not None or
            existing.get("fields") is not None or
            existing.get("display_template") is not None or
            existing.get("icon") is not None
        )

        if has_customizations:
            # Just update is_hidden flag
            conn.execute(
                "UPDATE builtin_type_customizations SET is_hidden = 0, updated_at = ? WHERE type_id = ?",
                (datetime.utcnow().isoformat(), type_id)
            )
        else:
            # Delete the record entirely since there are no other customizations
            conn.execute(
                "DELETE FROM builtin_type_customizations WHERE type_id = ?",
                (type_id,)
            )

        conn.commit()
        return True

    def list_builtin_customizations(self) -> list[dict[str, Any]]:
        """
        List all built-in type customizations.

        Returns:
            List of customization dictionaries
        """
        conn = self._ensure_connected()

        rows = conn.execute(
            "SELECT * FROM builtin_type_customizations ORDER BY type_id"
        ).fetchall()

        return [self._row_to_builtin_customization(row) for row in rows]

    def list_hidden_builtin_types(self) -> list[str]:
        """
        List type IDs of all hidden built-in types.

        Returns:
            List of hidden type IDs
        """
        conn = self._ensure_connected()

        rows = conn.execute(
            "SELECT type_id FROM builtin_type_customizations WHERE is_hidden = 1"
        ).fetchall()

        return [row["type_id"] for row in rows]

    def delete_builtin_customization(self, type_id: str) -> bool:
        """
        Delete all customizations for a built-in type (reset to default).

        Args:
            type_id: The built-in type identifier

        Returns:
            True if deleted, False if no customization existed
        """
        conn = self._ensure_connected()

        result = conn.execute(
            "DELETE FROM builtin_type_customizations WHERE type_id = ?",
            (type_id,)
        )
        conn.commit()

        return result.rowcount > 0

    def _row_to_builtin_customization(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a database row to a built-in customization dictionary."""
        return {
            "type_id": row["type_id"],
            "is_hidden": bool(row["is_hidden"]),
            "display_name": row["display_name"],
            "description": row["description"],
            "fields": json.loads(row["fields"]) if row["fields"] else None,
            "display_template": row["display_template"],
            "icon": row["icon"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # ========================================================================
    # Model Scope Operations
    # ========================================================================

    def migrate_add_model_scope(self) -> bool:
        """
        Add model_scope column to existing tables if not present.

        This is a migration helper for existing databases.

        Returns:
            True if migration was needed and performed, False if already migrated
        """
        conn = self._ensure_connected()

        # Check if model_scope column exists in capsules
        cursor = conn.execute("PRAGMA table_info(capsules)")
        columns = [col[1] for col in cursor.fetchall()]

        migrated = False

        if "model_scope" not in columns:
            conn.execute("ALTER TABLE capsules ADD COLUMN model_scope TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_capsules_model_scope ON capsules(model_scope)")
            migrated = True

        # Check conversations table
        cursor = conn.execute("PRAGMA table_info(conversations)")
        columns = [col[1] for col in cursor.fetchall()]

        if "model_scope" not in columns:
            conn.execute("ALTER TABLE conversations ADD COLUMN model_scope TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_model_scope ON conversations(model_scope)")
            migrated = True

        if migrated:
            conn.commit()

        return migrated

    def update_capsule_model_scope(
        self,
        capsule_id: str,
        model_scope: Optional[str],
    ) -> bool:
        """
        Update just the model_scope for a capsule.

        Args:
            capsule_id: ID of capsule to update
            model_scope: Model ID to assign (None = shared across all models)

        Returns:
            True if updated successfully
        """
        conn = self._ensure_connected()

        result = conn.execute(
            "UPDATE capsules SET model_scope = ? WHERE id = ?",
            (model_scope, capsule_id)
        )
        conn.commit()

        return result.rowcount > 0

    def update_conversation_model_scope(
        self,
        conversation_id: str,
        model_scope: Optional[str],
    ) -> bool:
        """
        Update just the model_scope for a conversation.

        Args:
            conversation_id: ID of conversation to update
            model_scope: Model ID to assign (None = shared across all models)

        Returns:
            True if updated successfully
        """
        conn = self._ensure_connected()

        result = conn.execute(
            "UPDATE conversations SET model_scope = ? WHERE id = ?",
            (model_scope, conversation_id)
        )
        conn.commit()

        return result.rowcount > 0

    def copy_capsule_to_model(
        self,
        capsule_id: str,
        target_model_scope: Optional[str],
    ) -> Optional[str]:
        """
        Copy a capsule to another model scope.

        Args:
            capsule_id: ID of capsule to copy
            target_model_scope: Model ID to copy to (None = shared)

        Returns:
            ID of the new capsule, or None if source not found
        """
        conn = self._ensure_connected()

        # Get the source capsule
        source = self.get_capsule(capsule_id)
        if not source:
            return None

        # Create a copy with new ID
        data = source.to_dict()
        data["id"] = str(uuid.uuid4())
        data["model_scope"] = target_model_scope
        data["created_at"] = datetime.utcnow().isoformat()
        data["updated_at"] = datetime.utcnow().isoformat()

        # Save the copy
        new_capsule = create_capsule(data)
        self.save_capsule(new_capsule)

        return new_capsule.id

    def list_capsules_for_model(
        self,
        model_scope: str,
        include_shared: bool = True,
        limit: int = 100,
    ) -> list[MemoryCapsule]:
        """
        List all capsules for a specific model.

        Args:
            model_scope: Model ID to filter by
            include_shared: Include memories with no model_scope (shared)
            limit: Maximum results

        Returns:
            List of capsules for this model
        """
        conn = self._ensure_connected()

        if include_shared:
            query = """
                SELECT * FROM capsules
                WHERE (model_scope = ? OR model_scope IS NULL)
                ORDER BY last_accessed DESC
                LIMIT ?
            """
            rows = conn.execute(query, (model_scope, limit)).fetchall()
        else:
            query = """
                SELECT * FROM capsules
                WHERE model_scope = ?
                ORDER BY last_accessed DESC
                LIMIT ?
            """
            rows = conn.execute(query, (model_scope, limit)).fetchall()

        return [self._row_to_capsule(row) for row in rows]

    def list_conversations_for_model(
        self,
        model_scope: str,
        include_shared: bool = True,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[Conversation]:
        """
        List all conversations for a specific model.

        Args:
            model_scope: Model ID to filter by
            include_shared: Include conversations with no model_scope (shared)
            include_archived: Include archived conversations
            limit: Maximum results

        Returns:
            List of conversations for this model
        """
        conn = self._ensure_connected()

        query = "SELECT * FROM conversations WHERE 1=1"
        params: list[Any] = []

        if include_shared:
            query += " AND (model_scope = ? OR model_scope IS NULL)"
        else:
            query += " AND model_scope = ?"
        params.append(model_scope)

        if not include_archived:
            query += " AND (archived = 0 OR archived IS NULL)"

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()

        return [self._row_to_conversation(row) for row in rows]

    def get_model_scopes_in_use(self) -> list[str]:
        """
        Get list of all model scopes that have memories or conversations.

        Returns:
            List of model scope identifiers
        """
        conn = self._ensure_connected()

        # Get unique model scopes from both tables
        capsule_scopes = conn.execute(
            "SELECT DISTINCT model_scope FROM capsules WHERE model_scope IS NOT NULL"
        ).fetchall()

        conv_scopes = conn.execute(
            "SELECT DISTINCT model_scope FROM conversations WHERE model_scope IS NOT NULL"
        ).fetchall()

        scopes = set()
        for row in capsule_scopes:
            scopes.add(row[0])
        for row in conv_scopes:
            scopes.add(row[0])

        return sorted(list(scopes))

    def count_capsules_by_model(self) -> dict[str, int]:
        """
        Count capsules grouped by model scope.

        Deprecated: Use count_capsules_by_profile instead.

        Returns:
            Dictionary mapping model_scope to count (None key = shared)
        """
        conn = self._ensure_connected()

        rows = conn.execute("""
            SELECT model_scope, COUNT(*) as count
            FROM capsules
            GROUP BY model_scope
        """).fetchall()

        result = {}
        for row in rows:
            key = row[0] if row[0] else "shared"
            result[key] = row[1]

        return result

    def count_capsules_by_profile(self) -> dict[str, int]:
        """
        Count capsules grouped by profile scope.

        Returns:
            Dictionary mapping profile_scope to count ("shared" key = NULL/shared)
        """
        conn = self._ensure_connected()

        rows = conn.execute("""
            SELECT profile_scope, COUNT(*) as count
            FROM capsules
            GROUP BY profile_scope
        """).fetchall()

        result = {}
        for row in rows:
            key = row[0] if row[0] else "shared"
            result[key] = row[1]

        return result

    def get_profile_scopes_in_use(self) -> list[str]:
        """
        Get list of all profile scopes that have memories or conversations.

        Returns:
            List of profile scope identifiers
        """
        conn = self._ensure_connected()

        # Get unique profile scopes from both tables
        capsule_scopes = conn.execute(
            "SELECT DISTINCT profile_scope FROM capsules WHERE profile_scope IS NOT NULL"
        ).fetchall()

        conv_scopes = conn.execute(
            "SELECT DISTINCT profile_scope FROM conversations WHERE profile_scope IS NOT NULL"
        ).fetchall()

        scopes = set()
        for row in capsule_scopes:
            scopes.add(row[0])
        for row in conv_scopes:
            scopes.add(row[0])

        return sorted(list(scopes))

    def search_by_embedding_for_model(
        self,
        embedding: list[float],
        model_scope: Optional[str] = None,
        include_shared: bool = True,
        limit: int = 5,
        threshold: float = 0.5,
    ) -> list[MemoryCapsule]:
        """
        Search capsules by embedding similarity, optionally filtered by model.

        Args:
            embedding: Query embedding vector
            model_scope: Model ID to filter by (None = all)
            include_shared: Include shared memories when model_scope is set
            limit: Maximum results to return
            threshold: Minimum similarity score (0-1)

        Returns:
            List of capsules sorted by similarity
        """
        conn = self._ensure_connected()

        # Build query
        query = """
            SELECT * FROM capsules
            WHERE embedding IS NOT NULL
            AND presence_score > 0.1
        """
        params: list[Any] = []

        if model_scope is not None:
            if include_shared:
                query += " AND (model_scope = ? OR model_scope IS NULL)"
            else:
                query += " AND model_scope = ?"
            params.append(model_scope)

        rows = conn.execute(query, params).fetchall()

        # Calculate similarities
        from threadlight.embeddings import cosine_similarity

        results = []
        for row in rows:
            capsule = self._row_to_capsule(row)
            if capsule.embedding:
                similarity = cosine_similarity(embedding, capsule.embedding)
                if similarity >= threshold:
                    results.append((capsule, similarity))

        # Sort by similarity (descending)
        results.sort(key=lambda x: x[1], reverse=True)

        return [capsule for capsule, _ in results[:limit]]

    # ========================================================================
    # Profile Operations
    # ========================================================================

    def save_profile(self, profile: Profile) -> None:
        """Save a profile to the database."""
        conn = self._ensure_connected()

        # Serialize alloyed_config to JSON
        alloyed_config_json = None
        if profile.alloyed_config:
            alloyed_config_json = json.dumps(profile.alloyed_config.to_dict())

        conn.execute("""
            INSERT OR REPLACE INTO profiles
            (id, name, description, avatar, color, primary_model, alloyed_config,
             temperature, max_tokens, top_p, system_prompt, style_profile_id,
             memory_scope, access_shared_memories, philosophy, approach_to_rituals,
             created_at, updated_at, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            profile.id,
            profile.name,
            profile.description,
            profile.avatar,
            profile.color,
            profile.primary_model,
            alloyed_config_json,
            profile.temperature,
            profile.max_tokens,
            profile.top_p,
            profile.system_prompt,
            profile.style_profile_id,
            profile.memory_scope,
            1 if profile.access_shared_memories else 0,
            getattr(profile, 'philosophy', ''),
            getattr(profile, 'approach_to_rituals', ''),
            profile.created_at.isoformat() if isinstance(profile.created_at, datetime) else profile.created_at,
            profile.updated_at.isoformat() if isinstance(profile.updated_at, datetime) else profile.updated_at,
            profile.last_used_at.isoformat() if profile.last_used_at else None,
        ))
        conn.commit()

    def get_profile(self, profile_id: str) -> Optional[Profile]:
        """Get a profile by ID."""
        conn = self._ensure_connected()

        row = conn.execute(
            "SELECT * FROM profiles WHERE id = ?",
            (profile_id,)
        ).fetchone()

        if row is None:
            return None

        return self._row_to_profile(row)

    def update_profile(self, profile: Profile) -> None:
        """Update an existing profile."""
        conn = self._ensure_connected()

        # Serialize alloyed_config to JSON
        alloyed_config_json = None
        if profile.alloyed_config:
            alloyed_config_json = json.dumps(profile.alloyed_config.to_dict())

        conn.execute("""
            UPDATE profiles SET
                name = ?,
                description = ?,
                avatar = ?,
                color = ?,
                primary_model = ?,
                alloyed_config = ?,
                temperature = ?,
                max_tokens = ?,
                top_p = ?,
                system_prompt = ?,
                style_profile_id = ?,
                memory_scope = ?,
                access_shared_memories = ?,
                philosophy = ?,
                approach_to_rituals = ?,
                updated_at = ?,
                last_used_at = ?
            WHERE id = ?
        """, (
            profile.name,
            profile.description,
            profile.avatar,
            profile.color,
            profile.primary_model,
            alloyed_config_json,
            profile.temperature,
            profile.max_tokens,
            profile.top_p,
            profile.system_prompt,
            profile.style_profile_id,
            profile.memory_scope,
            1 if profile.access_shared_memories else 0,
            getattr(profile, 'philosophy', ''),
            getattr(profile, 'approach_to_rituals', ''),
            profile.updated_at.isoformat() if isinstance(profile.updated_at, datetime) else profile.updated_at,
            profile.last_used_at.isoformat() if profile.last_used_at else None,
            profile.id,
        ))
        conn.commit()

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile."""
        conn = self._ensure_connected()

        result = conn.execute(
            "DELETE FROM profiles WHERE id = ?",
            (profile_id,)
        )
        conn.commit()

        return result.rowcount > 0

    def list_profiles(self) -> list[Profile]:
        """List all profiles."""
        conn = self._ensure_connected()

        rows = conn.execute(
            "SELECT * FROM profiles ORDER BY updated_at DESC"
        ).fetchall()

        return [self._row_to_profile(row) for row in rows]

    def _row_to_profile(self, row: sqlite3.Row) -> Profile:
        """Convert a database row to a Profile."""
        # Parse alloyed_config from JSON
        alloyed_config = None
        if row["alloyed_config"]:
            alloyed_config = AlloyedConfig.from_dict(json.loads(row["alloyed_config"]))

        # Parse timestamps
        created_at = row["created_at"]
        updated_at = row["updated_at"]
        last_used_at = row["last_used_at"]

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        if isinstance(last_used_at, str) and last_used_at:
            last_used_at = datetime.fromisoformat(last_used_at.replace("Z", "+00:00"))
        else:
            last_used_at = None

        # Handle philosophy fields which may not exist in older databases
        philosophy = ""
        approach_to_rituals = ""
        try:
            philosophy = row["philosophy"] or ""
        except (IndexError, KeyError):
            pass
        try:
            approach_to_rituals = row["approach_to_rituals"] or ""
        except (IndexError, KeyError):
            pass

        return Profile(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            avatar=row["avatar"],
            color=row["color"],
            primary_model=row["primary_model"],
            alloyed_config=alloyed_config,
            temperature=row["temperature"],
            max_tokens=row["max_tokens"],
            top_p=row["top_p"],
            system_prompt=row["system_prompt"] or "",
            style_profile_id=row["style_profile_id"],
            memory_scope=row["memory_scope"],
            access_shared_memories=bool(row["access_shared_memories"]),
            philosophy=philosophy,
            approach_to_rituals=approach_to_rituals,
            created_at=created_at,
            updated_at=updated_at,
            last_used_at=last_used_at,
        )
