"""
Memory import system for Threadlight.

Tools for importing freeform text and other sources into
memory capsules. Supports multiple import formats:

- Text files: Plain text with one memory per line
- Claude Projects: Custom instructions and project documents
- Claude Conversations: Full conversation history (soft memory)
- Claude Export: Combined zip file with all data
- ChatGPT Conversations: Conversation history from ChatGPT exports
- ChatGPT Export: Combined zip file with ChatGPT data
"""

from threadlight.import_.text_importer import (
    import_text_file,
    preview_import,
    ImportResult,
    ImportStats,
)

from threadlight.import_.claude_projects import (
    import_claude_projects,
    preview_projects,
    get_project_instructions,
    ProjectImportResult,
    ProjectImportStats,
)

from threadlight.import_.claude_conversations import (
    import_claude_conversations,
    preview_conversations,
    count_conversations,
    ConversationImportResult,
    ConversationImportStats,
)

from threadlight.import_.claude_export import (
    import_claude_export,
    preview_claude_export,
    ClaudeExportResult,
    ClaudeExportStats,
)

from threadlight.import_.chatgpt_conversations import (
    import_chatgpt_conversations,
    preview_chatgpt_conversations,
    count_chatgpt_conversations,
    ChatGPTImportResult,
    ChatGPTImportStats,
)

from threadlight.import_.chatgpt_export import (
    import_chatgpt_export,
    preview_chatgpt_export,
    ChatGPTExportResult,
    ChatGPTExportStats,
)

__all__ = [
    # Text importer
    "import_text_file",
    "preview_import",
    "ImportResult",
    "ImportStats",
    # Claude projects
    "import_claude_projects",
    "preview_projects",
    "get_project_instructions",
    "ProjectImportResult",
    "ProjectImportStats",
    # Claude conversations
    "import_claude_conversations",
    "preview_conversations",
    "count_conversations",
    "ConversationImportResult",
    "ConversationImportStats",
    # Claude combined export
    "import_claude_export",
    "preview_claude_export",
    "ClaudeExportResult",
    "ClaudeExportStats",
    # ChatGPT conversations
    "import_chatgpt_conversations",
    "preview_chatgpt_conversations",
    "count_chatgpt_conversations",
    "ChatGPTImportResult",
    "ChatGPTImportStats",
    # ChatGPT combined export
    "import_chatgpt_export",
    "preview_chatgpt_export",
    "ChatGPTExportResult",
    "ChatGPTExportStats",
]
