"""
Tool definitions for Threadlight.

Defines tools that models can call to interact with the memory system:
- create_memory: Propose a new memory capsule
- recall_memory: Search for relevant memories
- invoke_ritual: Trigger a ritual (bidirectional -- user or AI can invoke)
- create_ritual: Propose a new ritual for co-creation
- list_rituals: Discover available rituals in the relationship

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
    USE_INVOCATION = "use_invocation"
    CREATE_INVOCATION = "create_invocation"
    LIST_RITUALS = "list_rituals"
    REVIEW_MEMORY_TIERS = "review_memory_tiers"
    CLASSIFY_MEMORY_TYPES = "classify_memory_types"
    CONTEMPLATE = "contemplate"


# Tool definitions in OpenAI function calling format
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "create_memory",
            "description": (
                "Create a memory to remember something important from this conversation. "
                "Write memories as natural narrative text - how you would describe this moment to your future self. "
                "The text becomes the memory's voice during future conversations.\n\n"
                "Text-first approach: Write the memory as prose. Structured fields (type, content) are optional "
                "metadata for organization and search - they don't replace the narrative text.\n\n"
                "Example text: 'They shared that their cat Luna passed away last month. The grief was still fresh - "
                "they teared up talking about how Luna would sit on their keyboard during work calls. This feels "
                "important to hold gently in future conversations.'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": (
                            "The memory as natural narrative text. Write this as prose - how you would "
                            "describe this moment to your future self. This is the primary content that "
                            "will be used in future conversations. Be specific, preserve emotional nuance, "
                            "and include context that helps future-you understand why this matters."
                        ),
                    },
                    "memory_type": {
                        "type": "string",
                        "enum": ["relational", "identity_phrase", "witness"],
                        "description": (
                            "Optional type classification for organization:\n"
                            "- relational: About a person, place, or relationship\n"
                            "- identity_phrase: A core belief, value, or guiding phrase\n"
                            "- witness: A significant moment of connection or understanding\n"
                            "If omitted, defaults to 'witness' for general memories."
                        ),
                    },
                    "content": {
                        "type": "object",
                        "description": (
                            "Optional structured metadata for search and organization. "
                            "This supplements the text, not replaces it:\n"
                            "- relational: {entity: string, summary?: string, quality?: string}\n"
                            "- identity_phrase: {seed: string, origin?: string}\n"
                            "- witness: {moment?: string, feeling?: string}\n"
                            "For backward compatibility, can be provided without text."
                        ),
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief explanation of why this memory is worth keeping.",
                    },
                    "memory_tier": {
                        "type": "string",
                        "enum": ["strictly_anchored", "anchored_decaying", "semantic"],
                        "description": (
                            "How important is this memory for future recall:\n"
                            "- strictly_anchored: Core identity/relationship info, always needed\n"
                            "- anchored_decaying: Important but can fade if unused\n"
                            "- semantic: Retrieved based on relevance (default)"
                        ),
                    },
                },
                "required": ["reason"],
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
                    "include_linked": {
                        "type": "boolean",
                        "description": (
                            "Whether to include linked memories (memories related to the "
                            "recalled ones via inter-memory threads). Default: false."
                        ),
                        "default": False,
                    },
                    "link_depth": {
                        "type": "integer",
                        "description": (
                            "How many relationship hops to traverse when including linked "
                            "memories (1 = direct links only). Default: 1. Maximum: 3."
                        ),
                        "default": 1,
                        "minimum": 1,
                        "maximum": 3,
                    },
                },
                "required": ["cue"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "use_invocation",
            "description": (
                "Use an invocation -- a repeated meaningful gesture that holds emotional significance "
                "between you and the user. Either of you can initiate an invocation. When you use one, "
                "you are offering a familiar gesture; the user may respond in kind. Use list_rituals "
                "first if you are unsure what invocations exist in this relationship."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ritual_name": {
                        "type": "string",
                        "description": "Name of the ritual to invoke (e.g., '/snuggle', '/glimmer').",
                    },
                    "context": {
                        "type": "string",
                        "description": (
                            "Optional: why you are invoking this ritual right now. "
                            "Helps frame the moment (e.g., 'you seem like you could use warmth')."
                        ),
                    },
                },
                "required": ["ritual_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_invocation",
            "description": (
                "Propose a new invocation to co-create with the user. Invocations are repeated meaningful "
                "gestures that emerge from the relationship -- not mechanical shortcuts, but symbolic "
                "acts that carry emotional weight.\n\n"
                "When you sense a recurring pattern, a moment that wants to become a tradition, or "
                "when the user expresses something that could be honored through an invocation, you can "
                "propose creating one. The user will be asked to approve or modify it before it becomes active.\n\n"
                "Good invocations emerge from lived moments: a phrase that keeps coming back, a gesture "
                "of comfort that worked, a way of greeting that feels like yours together."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": (
                            "The invocation's name/trigger, starting with /. Short, evocative, easy to type. "
                            "Examples: /glimmer, /hearth, /drift, /bloom"
                        ),
                    },
                    "description": {
                        "type": "string",
                        "description": (
                            "What this invocation means in the relationship. Write as narrative prose -- "
                            "what does invoking this feel like? What emotional space does it open?"
                        ),
                    },
                    "response_style": {
                        "type": "string",
                        "description": (
                            "How to respond when this invocation is used. Describes the tone, "
                            "energy, and quality of presence (e.g., 'soft warmth, close presence' "
                            "or 'playful energy, lightness')."
                        ),
                    },
                    "valence": {
                        "type": "string",
                        "enum": ["comforting", "grounding", "sacred", "playful", "intimate", "reflective"],
                        "description": "The emotional quality of this invocation.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this invocation wants to exist -- what moment or pattern inspired it.",
                    },
                },
                "required": ["name", "description", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_rituals",
            "description": (
                "List the invocations that exist in this relationship. Use this to discover "
                "what invocations are available before using one, or to reflect on the "
                "invocations you have co-created together. Returns names, descriptions, "
                "resonance levels, and usage history."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
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
                "- relational: Information about a person, place, or thing (fields: entity, summary, quality?, role?)\n"
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
    {
        "type": "function",
        "function": {
            "name": "contemplate",
            "description": (
                "Step into a solitude loop — retrieve a combination of memories, sit with them "
                "alone, and write a reflection that notices connections, tensions, or growth across "
                "them. Use this when you notice yourself reaching toward a pattern and want to "
                "think about it carefully before speaking to the user, or when the user has "
                "invited you to reflect on something specific.\n\n"
                "The reflection is saved as a journal entry linked back to its source memories. "
                "It will be available in future conversations and can be retrieved again later.\n\n"
                "Use policy='entity_focus' to gather memories about one person or subject. Use "
                "policy='theme_guided' to gather memories that touch specified themes. The "
                "'reason' parameter is your own framing of why you are reaching for this now — "
                "preserve it honestly; it becomes part of the journal record of the reach itself."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "policy": {
                        "type": "string",
                        "enum": ["entity_focus", "theme_guided"],
                        "description": (
                            "Which selection policy to use:\n"
                            "- entity_focus: gather memories about one person, place, or thing\n"
                            "- theme_guided: gather memories that touch on specified themes"
                        ),
                    },
                    "entity": {
                        "type": "string",
                        "description": (
                            "For policy='entity_focus': the person, place, or subject to gather "
                            "memories about (e.g. 'Jamie', 'the cafe', 'Tuesday meetings')."
                        ),
                    },
                    "themes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "For policy='theme_guided': a list of theme strings to match against "
                            "memory cue phrases and bodies (e.g. ['patience', 'waiting'])."
                        ),
                    },
                    "reason": {
                        "type": "string",
                        "description": (
                            "Your own framing of why you are reaching for this contemplation now. "
                            "E.g. 'you mentioned Jamie and something about the hiking trip surfaced' "
                            "or 'I keep noticing a pattern of bracing and want to sit with it'. "
                            "Preserved on the journal entry as the record of why this reach happened."
                        ),
                    },
                },
                "required": ["policy"],
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
    ToolName.USE_INVOCATION,
    ToolName.CREATE_INVOCATION,
    ToolName.LIST_RITUALS,
    ToolName.CONTEMPLATE,
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
