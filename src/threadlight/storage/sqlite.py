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
                embedding BLOB
            );

            CREATE INDEX IF NOT EXISTS idx_capsules_type ON capsules(type);
            CREATE INDEX IF NOT EXISTS idx_capsules_presence ON capsules(presence_score);
            CREATE INDEX IF NOT EXISTS idx_capsules_last_accessed ON capsules(last_accessed);
            CREATE INDEX IF NOT EXISTS idx_capsules_consent ON capsules(consent_confirmed);

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
                metadata TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_source ON conversations(source);
            CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at);

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT,
                metadata TEXT,
                embedding BLOB,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
            CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);

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

        conn.execute("""
            INSERT OR REPLACE INTO capsules
            (id, type, content, created_at, updated_at, last_accessed,
             access_count, retention, decay_rate, presence_score,
             consent_origin, consent_confirmed, cue_phrases, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                embedding = ?
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

    def search_by_cue(self, cue: str, limit: int = 5) -> list[MemoryCapsule]:
        """Search capsules by cue phrase match and content text."""
        conn = self._ensure_connected()

        cue_lower = cue.lower()

        # Search both cue_phrases and content text (for ImportedMemory)
        # This allows finding imported memories by their text content
        rows = conn.execute("""
            SELECT * FROM capsules
            WHERE (LOWER(cue_phrases) LIKE ? OR LOWER(content) LIKE ?)
            AND presence_score > 0.1
            ORDER BY presence_score DESC, last_accessed DESC
            LIMIT ?
        """, (f"%{cue_lower}%", f"%{cue_lower}%", limit)).fetchall()

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
            (id, name, summary, created_at, updated_at, source, message_count, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conversation.id,
            conversation.name,
            conversation.summary,
            conversation.created_at.isoformat() if isinstance(conversation.created_at, datetime) else conversation.created_at,
            conversation.updated_at.isoformat() if isinstance(conversation.updated_at, datetime) else conversation.updated_at,
            conversation.source,
            conversation.message_count,
            json.dumps(conversation.metadata),
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
    ) -> list[Conversation]:
        """List conversations with optional filtering."""
        conn = self._ensure_connected()

        query = "SELECT * FROM conversations WHERE 1=1"
        params: list[Any] = []

        if source:
            query += " AND source = ?"
            params.append(source)

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
                metadata = ?
            WHERE id = ?
        """, (
            conversation.name,
            conversation.summary,
            conversation.updated_at.isoformat(),
            conversation.source,
            conversation.message_count,
            json.dumps(conversation.metadata),
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
            (id, conversation_id, role, content, timestamp, source, metadata, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message.id,
            message.conversation_id,
            message.role,
            message.content,
            message.timestamp.isoformat() if isinstance(message.timestamp, datetime) else message.timestamp,
            message.source,
            json.dumps(message.metadata),
            json.dumps(message.embedding) if message.embedding else None,
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
                    (id, conversation_id, role, content, timestamp, source, metadata, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    msg.id,
                    msg.conversation_id,
                    msg.role,
                    msg.content,
                    msg.timestamp.isoformat() if isinstance(msg.timestamp, datetime) else msg.timestamp,
                    msg.source,
                    json.dumps(msg.metadata),
                    json.dumps(msg.embedding) if msg.embedding else None,
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

        return Conversation(
            id=row["id"],
            name=row["name"] or "",
            summary=row["summary"] or "",
            created_at=created_at,
            updated_at=updated_at,
            source=row["source"] or "",
            message_count=row["message_count"] or 0,
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def _row_to_message(self, row: sqlite3.Row) -> Message:
        """Convert a database row to a Message."""
        timestamp = row["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        return Message(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            timestamp=timestamp,
            source=row["source"] or "",
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            embedding=json.loads(row["embedding"]) if row["embedding"] else None,
        )
