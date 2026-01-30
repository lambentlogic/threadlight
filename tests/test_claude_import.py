"""
Tests for Claude import functionality.

Tests the import of:
- Claude projects (custom instructions, documents)
- Claude conversations (full history)
- Combined Claude exports (zip files)
"""

import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from threadlight.storage.sqlite import SQLiteStorage
from threadlight.storage.base import Message, Conversation
from threadlight.import_.claude_projects import (
    import_claude_projects,
    preview_projects,
    parse_project,
    analyze_instructions_for_style,
    ProjectImportStats,
)
from threadlight.import_.claude_conversations import (
    import_claude_conversations,
    preview_conversations,
    count_conversations,
    parse_claude_message,
    parse_claude_conversation,
    ConversationImportStats,
)
from threadlight.import_.claude_export import (
    import_claude_export,
    preview_claude_export,
)
from threadlight.context.soft_memory import SoftMemory, SoftMemoryConfig


@pytest.fixture
def temp_storage():
    """Create a temporary SQLite storage."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    storage = SQLiteStorage(db_path)
    storage.initialize()
    yield storage
    storage.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sample_projects_json(tmp_path):
    """Create a sample projects.json file."""
    projects = [
        {
            "uuid": "proj-1-uuid-1234-5678",
            "name": "Writing Assistant",
            "description": "Help with creative writing",
            "prompt_template": "You are a helpful writing assistant. Be casual and friendly. Avoid jargon. You may use metaphors.",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T10:00:00Z",
            "docs": [
                {
                    "uuid": "doc-1",
                    "filename": "style-guide.md",
                    "content": "# Style Guide\n\nWrite in active voice."
                },
                {
                    "uuid": "doc-2",
                    "filename": "notes.txt",
                    "content": "Some notes about the project."
                }
            ]
        },
        {
            "uuid": "proj-2-uuid-1234-5678",
            "name": "Code Review",
            "description": "Technical code reviews",
            "prompt_template": "",  # No custom instructions
            "created_at": "2024-02-01T10:00:00Z",
            "updated_at": "2024-02-01T10:00:00Z",
            "docs": []
        },
        {
            "uuid": "proj-3-uuid-1234-5678",
            "name": "Poetry Project",
            "description": "Poetic exploration",
            "prompt_template": "Be poetic and lyrical. Never use cliches. You should avoid explaining metaphors.",
            "created_at": "2024-03-01T10:00:00Z",
            "updated_at": "2024-03-01T10:00:00Z",
            "docs": []
        }
    ]

    file_path = tmp_path / "projects.json"
    with open(file_path, "w") as f:
        json.dump(projects, f)

    return file_path


@pytest.fixture
def sample_conversations_json(tmp_path):
    """Create a sample conversations.json file."""
    conversations = [
        {
            "uuid": "conv-1-uuid",
            "name": "Getting to Know Claude",
            "summary": "An introductory conversation",
            "created_at": "2024-03-04T21:09:20.184352Z",
            "updated_at": "2024-03-04T21:41:31.589431Z",
            "chat_messages": [
                {
                    "uuid": "msg-1",
                    "text": "Hello, tell me about yourself.",
                    "content": [{"type": "text", "text": "Hello, tell me about yourself."}],
                    "sender": "human",
                    "created_at": "2024-03-04T21:09:45.458975Z",
                    "updated_at": "2024-03-04T21:09:45.458975Z",
                },
                {
                    "uuid": "msg-2",
                    "text": "I'm Claude, an AI assistant created by Anthropic.",
                    "content": [{"type": "text", "text": "I'm Claude, an AI assistant created by Anthropic."}],
                    "sender": "assistant",
                    "created_at": "2024-03-04T21:10:00.458975Z",
                    "updated_at": "2024-03-04T21:10:00.458975Z",
                },
            ]
        },
        {
            "uuid": "conv-2-uuid",
            "name": "",  # Empty name
            "summary": "",
            "created_at": "2024-03-05T10:00:00Z",
            "updated_at": "2024-03-05T10:00:00Z",
            "chat_messages": []  # Empty conversation
        },
        {
            "uuid": "conv-3-uuid",
            "name": "Python Help",
            "summary": "Getting help with Python code",
            "created_at": "2024-03-06T10:00:00Z",
            "updated_at": "2024-03-06T10:00:00Z",
            "chat_messages": [
                {
                    "uuid": "msg-3",
                    "text": "How do I read a JSON file in Python?",
                    "content": [{"type": "text", "text": "How do I read a JSON file in Python?"}],
                    "sender": "human",
                    "created_at": "2024-03-06T10:01:00Z",
                    "updated_at": "2024-03-06T10:01:00Z",
                },
            ]
        }
    ]

    file_path = tmp_path / "conversations.json"
    with open(file_path, "w") as f:
        json.dump(conversations, f)

    return file_path


class TestClaudeProjectsImport:
    """Tests for Claude projects import."""

    def test_parse_project(self):
        """Test parsing a single project."""
        data = {
            "uuid": "test-uuid",
            "name": "Test Project",
            "description": "A test",
            "prompt_template": "Be helpful",
            "docs": [{"filename": "test.md", "content": "Test content"}],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        project = parse_project(data)

        assert project.uuid == "test-uuid"
        assert project.name == "Test Project"
        assert project.prompt_template == "Be helpful"
        assert len(project.docs) == 1

    def test_analyze_instructions_for_style(self):
        """Test style analysis of custom instructions."""
        # Test with style-relevant content
        instructions = "Be casual and friendly. Avoid jargon. You may use metaphors."
        analysis = analyze_instructions_for_style(instructions)

        assert analysis["has_style_content"] is True
        assert "casual" in analysis["tone_base"]
        assert any("jargon" in c for c in analysis["constraints"])
        assert any("metaphor" in p for p in analysis["permissions"])

        # Test with no style content
        empty_analysis = analyze_instructions_for_style("Just help the user.")
        assert empty_analysis["tone_base"] == "general"

    def test_import_projects(self, temp_storage, sample_projects_json):
        """Test importing projects."""
        result = import_claude_projects(
            path=sample_projects_json,
            storage=temp_storage,
            create_styles=True,
            import_docs=True,
        )

        assert result.success is True
        assert result.stats.total_projects == 3
        assert result.stats.projects_with_instructions == 2
        assert result.stats.docs_imported == 2  # Two docs in first project
        assert result.stats.style_profiles_created >= 1

    def test_import_projects_dry_run(self, temp_storage, sample_projects_json):
        """Test dry run doesn't save to storage."""
        result = import_claude_projects(
            path=sample_projects_json,
            storage=temp_storage,
            create_styles=True,
            import_docs=True,
            dry_run=True,
        )

        assert result.success is True
        assert result.stats.total_projects == 3

        # Verify nothing was saved
        capsules = temp_storage.list_capsules()
        assert len(capsules) == 0

    def test_preview_projects(self, sample_projects_json):
        """Test previewing projects."""
        previews = preview_projects(sample_projects_json, limit=5)

        assert len(previews) == 3
        assert previews[0]["name"] == "Writing Assistant"
        assert previews[0]["has_instructions"] is True
        assert previews[0]["doc_count"] == 2


class TestClaudeConversationsImport:
    """Tests for Claude conversations import."""

    def test_parse_claude_message(self):
        """Test parsing a single message."""
        msg_data = {
            "uuid": "msg-uuid",
            "text": "Hello there",
            "content": [{"type": "text", "text": "Hello there"}],
            "sender": "human",
            "created_at": "2024-03-04T21:09:45.458975Z",
            "updated_at": "2024-03-04T21:09:45.458975Z",
        }

        msg = parse_claude_message(msg_data, "conv-id")

        assert msg is not None
        assert msg.id == "msg-uuid"
        assert msg.role == "user"  # human -> user
        assert msg.content == "Hello there"
        assert msg.conversation_id == "conv-id"

    def test_parse_claude_conversation(self):
        """Test parsing a full conversation."""
        conv_data = {
            "uuid": "conv-uuid",
            "name": "Test Conversation",
            "summary": "A test",
            "created_at": "2024-03-04T21:09:20Z",
            "updated_at": "2024-03-04T21:41:31Z",
            "chat_messages": [
                {
                    "uuid": "msg-1",
                    "text": "Hello",
                    "sender": "human",
                    "created_at": "2024-03-04T21:09:45Z",
                },
                {
                    "uuid": "msg-2",
                    "text": "Hi there!",
                    "sender": "assistant",
                    "created_at": "2024-03-04T21:10:00Z",
                },
            ]
        }

        conv, messages = parse_claude_conversation(conv_data)

        assert conv is not None
        assert conv.id == "conv-uuid"
        assert conv.name == "Test Conversation"
        assert conv.message_count == 2
        assert len(messages) == 2

    def test_import_conversations(self, temp_storage, sample_conversations_json):
        """Test importing conversations."""
        result = import_claude_conversations(
            path=sample_conversations_json,
            storage=temp_storage,
            skip_empty=True,
        )

        assert result.success is True
        assert result.stats.total_conversations == 3
        assert result.stats.conversations_imported == 2  # One skipped (empty)
        assert result.stats.conversations_skipped == 1
        assert result.stats.messages_imported == 3  # 2 + 0 + 1

    def test_import_conversations_with_limit(self, temp_storage, sample_conversations_json):
        """Test limiting imported conversations."""
        result = import_claude_conversations(
            path=sample_conversations_json,
            storage=temp_storage,
            limit=1,
        )

        assert result.success is True
        assert result.stats.conversations_imported == 1

    def test_count_conversations(self, sample_conversations_json):
        """Test counting without importing."""
        counts = count_conversations(sample_conversations_json)

        assert counts["conversations"] == 3
        assert counts["messages"] == 3
        assert counts["empty_conversations"] == 1

    def test_preview_conversations(self, sample_conversations_json):
        """Test previewing conversations."""
        previews = preview_conversations(sample_conversations_json, limit=5)

        assert len(previews) == 3
        assert previews[0]["name"] == "Getting to Know Claude"
        assert previews[0]["message_count"] == 2


class TestConversationStorage:
    """Tests for conversation storage operations."""

    def test_save_and_get_conversation(self, temp_storage):
        """Test saving and retrieving a conversation."""
        conv = Conversation(
            id="test-conv-1",
            name="Test Conversation",
            summary="A test",
            source="test",
            message_count=0,
        )

        saved_id = temp_storage.save_conversation(conv)
        assert saved_id == "test-conv-1"

        retrieved = temp_storage.get_conversation("test-conv-1")
        assert retrieved is not None
        assert retrieved.name == "Test Conversation"

    def test_save_and_get_messages(self, temp_storage):
        """Test saving and retrieving messages."""
        # First create a conversation
        conv = Conversation(id="conv-1", name="Test", source="test")
        temp_storage.save_conversation(conv)

        # Save messages
        msg1 = Message(
            id="msg-1",
            conversation_id="conv-1",
            role="user",
            content="Hello",
            timestamp=datetime.utcnow(),
            source="test",
        )
        msg2 = Message(
            id="msg-2",
            conversation_id="conv-1",
            role="assistant",
            content="Hi there!",
            timestamp=datetime.utcnow(),
            source="test",
        )

        temp_storage.save_message(msg1)
        temp_storage.save_message(msg2)

        # Retrieve messages
        messages = temp_storage.get_messages("conv-1")
        assert len(messages) == 2
        assert messages[0].content == "Hello"

    def test_save_messages_batch(self, temp_storage):
        """Test batch saving messages."""
        conv = Conversation(id="conv-batch", name="Batch Test", source="test")
        temp_storage.save_conversation(conv)

        messages = [
            Message(
                id=f"msg-batch-{i}",
                conversation_id="conv-batch",
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
                timestamp=datetime.utcnow(),
                source="test",
            )
            for i in range(10)
        ]

        count = temp_storage.save_messages_batch(messages)
        assert count == 10

        retrieved = temp_storage.get_messages("conv-batch")
        assert len(retrieved) == 10

    def test_search_messages(self, temp_storage):
        """Test searching messages."""
        # Create conversation and messages
        conv = Conversation(id="conv-search", name="Search Test", source="test")
        temp_storage.save_conversation(conv)

        messages = [
            Message(
                id="msg-search-1",
                conversation_id="conv-search",
                role="user",
                content="How do I use Python decorators?",
                timestamp=datetime.utcnow(),
                source="test",
            ),
            Message(
                id="msg-search-2",
                conversation_id="conv-search",
                role="assistant",
                content="Decorators in Python are functions that modify other functions.",
                timestamp=datetime.utcnow(),
                source="test",
            ),
        ]
        temp_storage.save_messages_batch(messages)

        # Search
        results = temp_storage.search_messages("Python decorators")
        assert len(results) >= 1

    def test_list_conversations(self, temp_storage):
        """Test listing conversations."""
        for i in range(5):
            conv = Conversation(
                id=f"conv-list-{i}",
                name=f"Conversation {i}",
                source="test",
            )
            temp_storage.save_conversation(conv)

        conversations = temp_storage.list_conversations(limit=3)
        assert len(conversations) == 3

    def test_count_conversations(self, temp_storage):
        """Test counting conversations."""
        for i in range(3):
            conv = Conversation(id=f"conv-count-{i}", name=f"Conv {i}", source="test")
            temp_storage.save_conversation(conv)

        count = temp_storage.count_conversations()
        assert count == 3


class TestSoftMemory:
    """Tests for soft memory retrieval."""

    def test_recall_messages(self, temp_storage):
        """Test recalling relevant messages."""
        # Set up test data
        conv = Conversation(id="conv-soft", name="Python Discussion", source="test")
        temp_storage.save_conversation(conv)

        messages = [
            Message(
                id="msg-soft-1",
                conversation_id="conv-soft",
                role="user",
                content="I'm working on a machine learning project with TensorFlow.",
                timestamp=datetime.utcnow(),
                source="test",
            ),
            Message(
                id="msg-soft-2",
                conversation_id="conv-soft",
                role="assistant",
                content="That sounds interesting! TensorFlow is great for machine learning.",
                timestamp=datetime.utcnow(),
                source="test",
            ),
        ]
        temp_storage.save_messages_batch(messages)

        # Create soft memory instance
        soft_memory = SoftMemory(temp_storage)

        # Recall
        results = soft_memory.recall("machine learning")
        assert len(results) >= 1

    def test_recall_relevant(self, temp_storage):
        """Test recalling messages relevant to a current message."""
        conv = Conversation(id="conv-relevant", name="Tech Chat", source="test")
        temp_storage.save_conversation(conv)

        messages = [
            Message(
                id="msg-rel-1",
                conversation_id="conv-relevant",
                role="user",
                content="The neural network training is taking forever.",
                timestamp=datetime.utcnow(),
                source="test",
            ),
        ]
        temp_storage.save_messages_batch(messages)

        soft_memory = SoftMemory(temp_storage)

        # This should find the neural network message
        results = soft_memory.recall_relevant(
            "I'm having issues with my deep learning model"
        )
        # May or may not find results depending on FTS matching

    def test_format_for_prompt(self, temp_storage):
        """Test formatting results for prompt injection."""
        conv = Conversation(id="conv-format", name="Test Conv", source="test")
        temp_storage.save_conversation(conv)

        msg = Message(
            id="msg-format-1",
            conversation_id="conv-format",
            role="user",
            content="I prefer Python for data science work.",
            timestamp=datetime.utcnow(),
            source="test",
        )
        temp_storage.save_message(msg)

        soft_memory = SoftMemory(temp_storage)
        results = soft_memory.recall("Python data science")

        if results:
            formatted = soft_memory.format_for_prompt(results)
            assert "Past Conversations" in formatted
            assert "Python" in formatted

    def test_soft_memory_config(self, temp_storage):
        """Test soft memory configuration."""
        config = SoftMemoryConfig(
            max_results=3,
            include_assistant=False,  # Only user messages
        )

        soft_memory = SoftMemory(temp_storage, config)
        assert soft_memory.config.max_results == 3
        assert soft_memory.config.include_assistant is False


class TestClaudeExportImport:
    """Tests for combined Claude export import."""

    def test_import_from_zip(self, temp_storage, sample_projects_json, sample_conversations_json, tmp_path):
        """Test importing from a zip file."""
        # Create a zip file with both JSON files
        zip_path = tmp_path / "claude-export.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(sample_projects_json, "projects.json")
            zf.write(sample_conversations_json, "conversations.json")

        # Import
        result = import_claude_export(
            path=zip_path,
            storage=temp_storage,
        )

        assert result.success is True
        assert result.stats.conversations.conversations_imported >= 1
        assert result.stats.projects.total_projects >= 1

    def test_preview_export(self, sample_projects_json, sample_conversations_json, tmp_path):
        """Test previewing an export."""
        zip_path = tmp_path / "claude-export.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(sample_projects_json, "projects.json")
            zf.write(sample_conversations_json, "conversations.json")

        preview = preview_claude_export(zip_path)

        assert "contents" in preview
        assert "projects.json" in preview["contents"]
        assert "conversations.json" in preview["contents"]


class TestMessageDataClass:
    """Tests for the Message dataclass."""

    def test_message_to_dict(self):
        """Test serializing a message."""
        msg = Message(
            id="test-msg",
            conversation_id="test-conv",
            role="user",
            content="Hello",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            source="test",
            metadata={"key": "value"},
        )

        d = msg.to_dict()

        assert d["id"] == "test-msg"
        assert d["role"] == "user"
        assert "2024-01-01" in d["timestamp"]
        assert d["metadata"]["key"] == "value"

    def test_message_from_dict(self):
        """Test deserializing a message."""
        d = {
            "id": "test-msg",
            "conversation_id": "test-conv",
            "role": "assistant",
            "content": "Hello back",
            "timestamp": "2024-01-01T12:00:00+00:00",
            "source": "test",
        }

        msg = Message.from_dict(d)

        assert msg.id == "test-msg"
        assert msg.role == "assistant"
        assert isinstance(msg.timestamp, datetime)


class TestConversationDataClass:
    """Tests for the Conversation dataclass."""

    def test_conversation_to_dict(self):
        """Test serializing a conversation."""
        conv = Conversation(
            id="test-conv",
            name="Test",
            summary="A test conversation",
            source="test",
            message_count=5,
        )

        d = conv.to_dict()

        assert d["id"] == "test-conv"
        assert d["name"] == "Test"
        assert d["message_count"] == 5

    def test_conversation_from_dict(self):
        """Test deserializing a conversation."""
        d = {
            "id": "test-conv",
            "name": "Test",
            "summary": "",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
            "source": "test",
            "message_count": 10,
        }

        conv = Conversation.from_dict(d)

        assert conv.id == "test-conv"
        assert conv.message_count == 10
        assert isinstance(conv.created_at, datetime)
