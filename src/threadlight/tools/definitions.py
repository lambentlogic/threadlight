"""
Tool definitions for Threadlight.

Defines tools that models can call to interact with the memory system:
- create_memory: Propose a new memory capsule
- recall_memory: Search for relevant memories
- invoke_ritual: Trigger a ritual

These follow the OpenAI function calling format for compatibility with
OpenAI-compatible APIs (including Nous Research).
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class ToolName(str, Enum):
    """Available tool names."""
    CREATE_MEMORY = "create_memory"
    RECALL_MEMORY = "recall_memory"
    INVOKE_RITUAL = "invoke_ritual"
    REVIEW_MEMORY_TIERS = "review_memory_tiers"
    CLASSIFY_MEMORY_TYPES = "classify_memory_types"


# Tool definitions in OpenAI function calling format
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "create_memory",
            "description": (
                "Propose creating a new memory to remember something important from this conversation. "
                "The memory will be stored as a proposal and requires user consent before becoming active. "
                "Use this when the user shares something meaningful that should be remembered across conversations, "
                "such as personal information, preferences, important moments, or relationship context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_type": {
                        "type": "string",
                        "enum": ["relational", "identity_phrase", "witness"],
                        "description": (
                            "Type of memory to create:\n"
                            "- relational: Information about a person or relationship (entity, role, tone)\n"
                            "- identity_phrase: A core belief or meaningful phrase (seed, origin)\n"
                            "- witness: A moment of being seen or understood (moment, feeling)"
                        ),
                    },
                    "content": {
                        "type": "object",
                        "description": (
                            "Content for the memory. Structure depends on memory_type:\n"
                            "- relational: {entity: string, summary: string, tone?: string}\n"
                            "- identity_phrase: {seed: string, origin: string, function?: string}\n"
                            "- witness: {moment: string, feeling: string}"
                        ),
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief explanation of why this memory is worth keeping.",
                    },
                },
                "required": ["memory_type", "content", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": (
                "Search for relevant memories based on a cue phrase or topic. "
                "Use this to recall context about a person, past conversations, "
                "or stored information that may be relevant to the current conversation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cue": {
                        "type": "string",
                        "description": "The phrase or topic to search for in memories.",
                    },
                    "memory_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["relational", "identity_phrase", "ritual", "witness", "style"],
                        },
                        "description": "Optional filter to specific memory types.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of memories to return (default: 5).",
                        "default": 5,
                    },
                },
                "required": ["cue"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "invoke_ritual",
            "description": (
                "Invoke a ritual to enter a specific emotional state or mode. "
                "Rituals are repeated meaningful gestures that hold emotional significance. "
                "Common rituals include /snuggle (warmth, comfort), /brush (gentle acknowledgment), "
                "and /coil (quiet presence, deep listening)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ritual_name": {
                        "type": "string",
                        "description": "Name of the ritual to invoke (e.g., '/snuggle', '/brush', '/coil').",
                    },
                },
                "required": ["ritual_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "review_memory_tiers",
            "description": (
                "Review and update memory tiers in batch. Call with action='list' to see all memories "
                "organized by tier for review. Call with action='update' and tier_assignments to apply changes.\n\n"
                "Memory tiers control how memories are recalled:\n"
                "- strictly_anchored: Core identity, always included in context, never decays "
                "(e.g., name, fundamental traits)\n"
                "- anchored_decaying: Important but may evolve over time, always included but can decay "
                "(e.g., current interests, relationships)\n"
                "- semantic: Context-dependent, recalled by relevance to conversation (default tier)"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "update"],
                        "description": (
                            "Action to perform: 'list' returns all memories for review, "
                            "'update' applies tier_assignments."
                        ),
                    },
                    "tier_assignments": {
                        "type": "object",
                        "description": (
                            "Map of memory_id to new tier. Only include memories you want to change. "
                            "Format: {\"memory-uuid\": \"strictly_anchored\", \"other-uuid\": \"anchored_decaying\", ...}"
                        ),
                        "additionalProperties": {
                            "type": "string",
                            "enum": ["strictly_anchored", "anchored_decaying", "semantic"],
                        },
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_memory_types",
            "description": (
                "Review imported/note memories and suggest converting them to structured types. "
                "Call with action='list' to see all note-type memories ready for classification. "
                "Call with action='convert' and conversions to apply type changes.\n\n"
                "Available memory types for conversion:\n"
                "- relational: Information about a person, place, or thing (fields: entity, summary, tone?, role?)\n"
                "- myth_seed: A guiding phrase or belief (fields: seed, origin?, function?)\n"
                "- witness: A significant moment or experience (fields: moment, feeling?, effect?)\n"
                "- note: Keep as unstructured text (fields: content, about?)\n\n"
                "When classifying, analyze the text content and determine which structured type best fits, "
                "then extract the appropriate fields from the original text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "convert"],
                        "description": (
                            "Action to perform: 'list' returns all note/imported memories for classification, "
                            "'convert' applies type conversions."
                        ),
                    },
                    "conversions": {
                        "type": "array",
                        "description": (
                            "Array of conversion specifications. Each item should have: "
                            "memory_id (the UUID), new_type (the target type), and content (the extracted fields).\n"
                            "Example: [{\"memory_id\": \"uuid-here\", \"new_type\": \"relational\", "
                            "\"content\": {\"entity\": \"Alice\", \"summary\": \"Friend who loves tea\"}}]"
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "memory_id": {"type": "string", "description": "UUID of the memory to convert"},
                                "new_type": {
                                    "type": "string",
                                    "enum": ["relational", "myth_seed", "witness", "note"],
                                    "description": "Target memory type",
                                },
                                "content": {
                                    "type": "object",
                                    "description": "Structured content for the new type",
                                },
                            },
                            "required": ["memory_id", "new_type", "content"],
                        },
                    },
                },
                "required": ["action"],
            },
        },
    },
]


def get_tool_definitions(
    include: list[ToolName] | None = None,
    exclude: list[ToolName] | None = None,
) -> list[dict[str, Any]]:
    """
    Get tool definitions, optionally filtered.

    Args:
        include: If provided, only include these tools
        exclude: If provided, exclude these tools

    Returns:
        List of tool definitions in OpenAI format
    """
    tools = TOOL_DEFINITIONS.copy()

    if include is not None:
        include_names = {t.value for t in include}
        tools = [t for t in tools if t["function"]["name"] in include_names]

    if exclude is not None:
        exclude_names = {t.value for t in exclude}
        tools = [t for t in tools if t["function"]["name"] not in exclude_names]

    return tools


# Define which tools are always available (core interaction tools)
CORE_TOOLS = [
    ToolName.CREATE_MEMORY,
    ToolName.RECALL_MEMORY,
    ToolName.INVOKE_RITUAL,
]

# Define which tools are contextual (only available in specific conversation types)
CONTEXTUAL_TOOLS = {
    "tier_review": [ToolName.REVIEW_MEMORY_TIERS],
    "type_classification": [ToolName.CLASSIFY_MEMORY_TYPES],
}


def get_contextual_tools(conversation_purpose: str | None = None) -> list[dict[str, Any]]:
    """
    Get tool definitions based on conversation purpose/context.

    This prevents models from spontaneously offering batch operations
    (like memory reorganization) in normal conversations.

    Args:
        conversation_purpose: The purpose of the conversation. Valid values:
            - None or "normal": Only core tools (create_memory, recall_memory, invoke_ritual)
            - "tier_review": Core tools + review_memory_tiers
            - "type_classification": Core tools + classify_memory_types

    Returns:
        List of tool definitions appropriate for the conversation context
    """
    # Start with core tools that are always available
    tools_to_include = CORE_TOOLS.copy()

    # Add contextual tools based on conversation purpose
    if conversation_purpose and conversation_purpose in CONTEXTUAL_TOOLS:
        tools_to_include.extend(CONTEXTUAL_TOOLS[conversation_purpose])

    return get_tool_definitions(include=tools_to_include)
