"""
Tool executor for Threadlight.

Executes tool calls from model responses and maps them to Threadlight operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING
import json
import logging

from threadlight.tools.definitions import ToolName
from threadlight.capsules.base import CapsuleType, MemoryTier

if TYPE_CHECKING:
    from threadlight.memory.orchestrator import MemoryOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result of executing a tool call."""

    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    requires_consent: bool = False
    proposal_id: Optional[str] = None

    # For rendering in conversation
    display_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "requires_consent": self.requires_consent,
            "proposal_id": self.proposal_id,
        }

    def to_tool_response(self) -> str:
        """Format as a tool response message for the model."""
        if not self.success:
            return json.dumps({"error": self.error})

        if self.requires_consent:
            return json.dumps({
                "status": "proposal_created",
                "proposal_id": self.proposal_id,
                "message": "Memory proposal created. Awaiting user consent.",
                "result": self.result,
            })

        return json.dumps({"status": "success", "result": self.result})


class ToolExecutor:
    """
    Executes tool calls from model responses.

    Maps tool calls to Threadlight operations with proper consent handling.

    Example:
        executor = ToolExecutor(memory_orchestrator)
        result = executor.execute("create_memory", {
            "memory_type": "relational",
            "content": {"entity": "Alice", "summary": "Friend who loves tea"},
            "reason": "User mentioned their friend Alice",
        })
    """

    def __init__(
        self,
        memory: MemoryOrchestrator,
        require_consent_for_memories: bool = True,
    ):
        """
        Initialize the tool executor.

        Args:
            memory: Memory orchestrator for memory operations
            require_consent_for_memories: If True, memory creation creates proposals
                                          instead of active memories
        """
        self.memory = memory
        self.require_consent = require_consent_for_memories

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """
        Execute a tool call.

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments for the tool

        Returns:
            ToolResult with the execution result
        """
        safe_args = arguments.copy()
        if "text" in safe_args:
            text_val = safe_args["text"]
            if isinstance(text_val, str) and len(text_val) > 50:
                safe_args["text"] = f"<{len(text_val)} chars: {text_val[:50]}...>"
        logger.info(f"[tool_execute] Executing tool={tool_name} with args={safe_args}")
        try:
            if tool_name == ToolName.CREATE_MEMORY.value:
                return self._execute_create_memory(arguments)
            elif tool_name == ToolName.RECALL_MEMORY.value:
                return self._execute_recall_memory(arguments)
            elif tool_name == ToolName.INVOKE_RITUAL.value:
                return self._execute_invoke_ritual(arguments)
            elif tool_name == ToolName.REVIEW_MEMORY_TIERS.value:
                return self._execute_review_memory_tiers(arguments)
            elif tool_name == ToolName.CLASSIFY_MEMORY_TYPES.value:
                return self._execute_classify_memory_types(arguments)
            else:
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    error=f"Unknown tool: {tool_name}",
                )
        except Exception as e:
            logger.exception(f"[tool_execute] Tool execution FAILED: {tool_name}, error={e}")
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
            )

    def _execute_create_memory(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute create_memory tool call.

        Text-first architecture: The `text` parameter is the primary content.
        When text is provided, it becomes the narrative core of the memory.
        Structured fields (memory_type, content) are optional metadata for
        organization and search.
        """
        text = arguments.get("text")
        memory_type = arguments.get("memory_type")
        content = arguments.get("content", {})
        reason = arguments.get("reason", "")
        memory_tier = arguments.get("memory_tier", "semantic")

        # Text-first: either text or content must be provided
        if not text and not content:
            return ToolResult(
                tool_name=ToolName.CREATE_MEMORY.value,
                success=False,
                error="Either 'text' (preferred) or 'content' must be provided",
            )

        # Default memory_type to 'witness' if not specified (most general type)
        if not memory_type:
            memory_type = "witness"

        # Validate memory type (accept identity_phrase as alias for myth_seed)
        valid_types = ["relational", "myth_seed", "identity_phrase", "witness"]
        if memory_type not in valid_types:
            return ToolResult(
                tool_name=ToolName.CREATE_MEMORY.value,
                success=False,
                error=f"Invalid memory_type. Must be one of: {valid_types}",
            )

        # Validate memory tier
        valid_tiers = ["strictly_anchored", "anchored_decaying", "semantic"]
        if memory_tier not in valid_tiers:
            return ToolResult(
                tool_name=ToolName.CREATE_MEMORY.value,
                success=False,
                error=f"Invalid memory_tier. Must be one of: {valid_tiers}",
            )

        # Normalize identity_phrase to myth_seed (internal name)
        if memory_type == "identity_phrase":
            memory_type = "myth_seed"

        # Text-first: merge text into content for storage
        # The capsule factory and capsule classes know how to handle text
        effective_content = content.copy() if content else {}
        if text:
            effective_content["text"] = text

        if self.require_consent:
            # Create a proposal instead of an active memory
            proposal = self.memory.propose(
                type=memory_type,
                content=effective_content,
                source_message=reason,
                memory_tier=memory_tier,
            )

            # Build result showing text-first approach
            result_data = {
                "type": memory_type,
                "reason": reason,
                "memory_tier": memory_tier,
            }
            if text:
                result_data["text"] = text
                result_data["text_preview"] = text[:100] + "..." if len(text) > 100 else text
            if content:
                result_data["content"] = content

            return ToolResult(
                tool_name=ToolName.CREATE_MEMORY.value,
                success=True,
                result=result_data,
                requires_consent=True,
                proposal_id=proposal.id,
                display_message=f"I'd like to remember this. [Proposal: {proposal.id[:8]}...]",
            )
        else:
            # Create memory directly (for trusted contexts)
            capsule = self.memory.create(
                type=memory_type,
                content=effective_content,
                consent_confirmed=True,
                consent_origin="model_direct",
                memory_tier=memory_tier,
            )

            # Build result showing text-first approach
            result_data = {
                "capsule_id": capsule.id,
                "type": memory_type,
            }
            if text:
                result_data["text_preview"] = text[:100] + "..." if len(text) > 100 else text
            if content:
                result_data["content"] = content

            return ToolResult(
                tool_name=ToolName.CREATE_MEMORY.value,
                success=True,
                result=result_data,
                display_message=f"Memory created: {capsule.id[:8]}...",
            )

    def _execute_recall_memory(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute recall_memory tool call."""
        cue = arguments.get("cue")
        memory_types = arguments.get("memory_types")
        limit = arguments.get("limit", 5)
        include_linked = arguments.get("include_linked", False)
        link_depth = arguments.get("link_depth")

        if not cue:
            return ToolResult(
                tool_name=ToolName.RECALL_MEMORY.value,
                success=False,
                error="cue is required",
            )

        # Convert type strings to CapsuleType
        types = None
        if memory_types:
            try:
                types = [CapsuleType(t) for t in memory_types]
            except ValueError as e:
                return ToolResult(
                    tool_name=ToolName.RECALL_MEMORY.value,
                    success=False,
                    error=f"Invalid memory type: {e}",
                )

        # Recall memories with optional linked capsule inclusion
        capsules = self.memory.recall(
            cue,
            types=types,
            limit=limit,
            include_linked=include_linked,
            link_depth=link_depth,
        )

        # Format results
        memories = []
        for capsule in capsules:
            memory_data = {
                "id": capsule.id[:8],
                "type": capsule.type.value,
                "text": capsule.text or "",
                "presence_score": round(capsule.presence_score, 2),
            }

            # Include type-specific fields as supplementary metadata
            if capsule.type == CapsuleType.RELATIONAL:
                memory_data["entity"] = getattr(capsule, "entity", "")
                memory_data["summary"] = getattr(capsule, "summary", "")
                memory_data["quality"] = getattr(capsule, "quality", "")
            elif capsule.type == CapsuleType.MYTH_SEED:
                memory_data["seed"] = getattr(capsule, "seed", "")
                memory_data["origin"] = getattr(capsule, "origin", "")
            elif capsule.type == CapsuleType.WITNESS:
                memory_data["moment"] = capsule.content.get("moment", "")
                memory_data["feeling"] = capsule.content.get("feeling", "")
            elif capsule.type == CapsuleType.RITUAL:
                memory_data["name"] = getattr(capsule, "name", "")
                memory_data["description"] = getattr(capsule, "description", "")
            elif capsule.type == CapsuleType.STYLE:
                memory_data["style_id"] = getattr(capsule, "style_id", "")
                memory_data["tone_base"] = getattr(capsule, "tone_base", "")

            # Indicate if this is a linked (vs. directly recalled) memory
            link_context = getattr(capsule, '_link_context', None)
            if link_context:
                link = link_context.get("link")
                memory_data["linked"] = True
                memory_data["link_type"] = link.link_type if link else "related"
                memory_data["link_via"] = link_context.get("via_capsule_id", "")[:8]
                if link and link.notes:
                    memory_data["link_notes"] = link.notes

            memories.append(memory_data)

        return ToolResult(
            tool_name=ToolName.RECALL_MEMORY.value,
            success=True,
            result={
                "cue": cue,
                "count": len(memories),
                "memories": memories,
            },
            display_message=f"Recalled {len(memories)} memories for '{cue}'",
        )

    def _execute_invoke_ritual(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute invoke_ritual tool call."""
        ritual_name = arguments.get("ritual_name")

        if not ritual_name:
            return ToolResult(
                tool_name=ToolName.INVOKE_RITUAL.value,
                success=False,
                error="ritual_name is required",
            )

        # Ensure ritual name starts with /
        if not ritual_name.startswith("/"):
            ritual_name = "/" + ritual_name

        # Invoke the ritual
        invocation = self.memory.invoke_ritual(ritual_name)

        result = {
            "ritual_name": ritual_name,
            "matched": invocation.matched,
        }

        if invocation.matched:
            result["response_template"] = invocation.response_template
            result["state_effects"] = invocation.state_effects
            if invocation.capsule:
                result["capsule_id"] = invocation.capsule.id[:8]

        return ToolResult(
            tool_name=ToolName.INVOKE_RITUAL.value,
            success=True,
            result=result,
            display_message=invocation.response_template or f"Ritual invoked: {ritual_name}",
        )

    def _execute_review_memory_tiers(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute review_memory_tiers tool call."""
        action = arguments.get("action")
        tier_assignments = arguments.get("tier_assignments", {})

        if not action:
            return ToolResult(
                tool_name=ToolName.REVIEW_MEMORY_TIERS.value,
                success=False,
                error="action is required ('list' or 'update')",
            )

        if action == "list":
            return self._list_memories_for_tier_review()
        elif action == "update":
            return self._apply_tier_assignments(tier_assignments)
        else:
            return ToolResult(
                tool_name=ToolName.REVIEW_MEMORY_TIERS.value,
                success=False,
                error=f"Invalid action '{action}'. Must be 'list' or 'update'.",
            )

    def _list_memories_for_tier_review(self) -> ToolResult:
        """List all memories organized by tier for review."""
        logger.info("[tool_execute] _list_memories_for_tier_review starting")
        from threadlight.storage.base import CapsuleFilter

        # Get memories respecting profile isolation
        # If per-profile isolation is enabled, only get memories for active profile + shared
        profile_scope = None
        include_shared = True

        if hasattr(self.memory, 'threadlight') and self.memory.threadlight:
            tl = self.memory.threadlight
            if tl.config.memory.per_profile_isolation and tl.active_profile:
                profile_scope = tl.active_profile.id
                # Check if this profile can access shared memories
                include_shared = tl.active_profile.access_shared_memories

        logger.info(f"[tool_execute] profile_scope={profile_scope}, include_shared={include_shared}")

        all_filter = CapsuleFilter(
            limit=10000,
            profile_scope=profile_scope,
            include_shared=include_shared
        )
        memories = self.memory.storage.list_capsules(all_filter)

        # Group by current tier
        by_tier: dict[str, list[dict[str, Any]]] = {
            "strictly_anchored": [],
            "anchored_decaying": [],
            "semantic": [],
        }

        for m in memories:
            tier = m.memory_tier.value if hasattr(m, 'memory_tier') else 'semantic'

            # Extract content preview
            if isinstance(m.content, str):
                content_preview = m.content
            elif isinstance(m.content, dict):
                # Try common content keys
                content_preview = m.content.get('content') or m.content.get('summary') or \
                                  m.content.get('seed') or m.content.get('moment') or \
                                  m.content.get('entity') or str(m.content)
            else:
                content_preview = str(m.content)

            # Truncate if too long
            if len(content_preview) > 150:
                content_preview = content_preview[:150] + "..."

            memory_info = {
                "id": m.id,
                "type": m.type.value,
                "content": content_preview,
                "current_tier": tier,
                "access_count": m.access_count,
                "presence_score": round(m.presence_score, 2),
            }
            by_tier.get(tier, by_tier["semantic"]).append(memory_info)

        # Build result with summary and full data
        result = {
            "summary": {
                "strictly_anchored": len(by_tier["strictly_anchored"]),
                "anchored_decaying": len(by_tier["anchored_decaying"]),
                "semantic": len(by_tier["semantic"]),
                "total": len(memories),
            },
            "memories_by_tier": by_tier,
            "instructions": (
                "Review these memories and think through which should be anchored based on how "
                "foundational and unchanging they are to core identity. When ready, call this tool "
                "again with action='update' and tier_assignments containing a map of memory IDs to "
                "their new tiers (e.g., {'memory-id-1': 'strictly_anchored', 'memory-id-2': 'anchored_decaying'}). "
                "Only include memories you want to change from their current tier."
            ),
        }

        logger.info(f"[tool_execute] _list_memories_for_tier_review completed with {len(memories)} memories")
        return ToolResult(
            tool_name=ToolName.REVIEW_MEMORY_TIERS.value,
            success=True,
            result=result,
            display_message=f"Retrieved {len(memories)} memories for tier review",
        )

    def _apply_tier_assignments(self, tier_assignments: dict[str, str]) -> ToolResult:
        """Apply tier assignments to memories."""
        if not tier_assignments:
            return ToolResult(
                tool_name=ToolName.REVIEW_MEMORY_TIERS.value,
                success=False,
                error="tier_assignments is required for 'update' action",
            )

        from threadlight.storage.base import CapsuleFilter

        # Get memories respecting profile isolation (same as list method)
        profile_scope = None
        include_shared = True

        if hasattr(self.memory, 'threadlight') and self.memory.threadlight:
            tl = self.memory.threadlight
            if tl.config.memory.per_profile_isolation and tl.active_profile:
                profile_scope = tl.active_profile.id
                include_shared = tl.active_profile.access_shared_memories

        all_filter = CapsuleFilter(
            limit=10000,
            profile_scope=profile_scope,
            include_shared=include_shared
        )
        memories = self.memory.storage.list_capsules(all_filter)
        memory_map = {m.id: m for m in memories}

        updated_count = 0
        errors = []

        for memory_id, new_tier_str in tier_assignments.items():
            # Find the memory
            memory = memory_map.get(memory_id)
            if not memory:
                # Memory either doesn't exist or doesn't belong to this profile
                errors.append(f"Memory {memory_id[:8]}... not found or not accessible")
                continue

            # Validate tier
            try:
                new_tier = MemoryTier(new_tier_str)
            except ValueError:
                errors.append(f"Invalid tier '{new_tier_str}' for memory {memory_id[:8]}...")
                continue

            # Skip if tier is unchanged
            if memory.memory_tier == new_tier:
                continue

            # Update tier
            old_tier = memory.memory_tier.value
            memory.memory_tier = new_tier
            if self.memory.storage.update_capsule(memory):
                updated_count += 1
                logger.info(f"Updated memory {memory_id[:8]}... tier: {old_tier} -> {new_tier_str}")
            else:
                errors.append(f"Failed to update memory {memory_id[:8]}...")

        # Build result message
        result = {
            "updated": updated_count,
            "requested": len(tier_assignments),
            "errors": errors if errors else None,
        }

        display_msg = f"Updated {updated_count} memory tier(s)"
        if errors:
            display_msg += f" ({len(errors)} error(s))"

        return ToolResult(
            tool_name=ToolName.REVIEW_MEMORY_TIERS.value,
            success=True,
            result=result,
            display_message=display_msg,
        )

    def _execute_classify_memory_types(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute classify_memory_types tool call."""
        action = arguments.get("action")
        conversions = arguments.get("conversions", [])

        if not action:
            return ToolResult(
                tool_name=ToolName.CLASSIFY_MEMORY_TYPES.value,
                success=False,
                error="action is required ('list' or 'convert')",
            )

        if action == "list":
            return self._list_memories_for_classification()
        elif action == "convert":
            return self._apply_type_conversions(conversions)
        else:
            return ToolResult(
                tool_name=ToolName.CLASSIFY_MEMORY_TYPES.value,
                success=False,
                error=f"Invalid action '{action}'. Must be 'list' or 'convert'.",
            )

    def _list_memories_for_classification(self) -> ToolResult:
        """List all note/imported memories for type classification."""
        from threadlight.storage.base import CapsuleFilter

        # Get memories respecting profile isolation
        profile_scope = None
        include_shared = True

        if hasattr(self.memory, 'threadlight') and self.memory.threadlight:
            tl = self.memory.threadlight
            if tl.config.memory.per_profile_isolation and tl.active_profile:
                profile_scope = tl.active_profile.id
                include_shared = tl.active_profile.access_shared_memories

        # Filter for note/imported types (custom type with note subtype or imported capsule_subtype)
        all_filter = CapsuleFilter(
            limit=10000,
            profile_scope=profile_scope,
            include_shared=include_shared
        )
        all_memories = self.memory.storage.list_capsules(all_filter)

        # Filter to only note/imported type memories
        note_memories = []
        for m in all_memories:
            # Check if this is a note/imported memory
            is_note = False
            content = m.content if isinstance(m.content, dict) else {}

            # Check for capsule_subtype == 'imported' or custom_type_id == 'note'
            if content.get('capsule_subtype') == 'imported':
                is_note = True
            elif content.get('custom_type_id') == 'note':
                is_note = True
            # Also check the type attribute - custom type with note-like content
            elif m.type.value == 'custom':
                # Check for note-style fields: 'text' or 'content' key without structured type
                if 'text' in content or ('content' in content and 'custom_type_id' not in content):
                    is_note = True

            if is_note:
                # Extract text content for display
                text_content = content.get('text') or content.get('content') or str(content)
                if len(text_content) > 300:
                    text_content = text_content[:300] + "..."

                note_memories.append({
                    "id": m.id,
                    "text": text_content,
                    "current_tier": m.memory_tier.value if hasattr(m, 'memory_tier') else 'semantic',
                    "access_count": m.access_count,
                    "created_at": m.created_at.isoformat() if hasattr(m.created_at, 'isoformat') else str(m.created_at),
                })

        # Get available types for reference
        available_types = [
            {"type_id": "relational", "fields": ["entity (required)", "summary (required)", "quality", "role"]},
            {"type_id": "myth_seed", "fields": ["seed (required)", "origin", "function"]},
            {"type_id": "witness", "fields": ["moment (required)", "feeling", "effect"]},
            {"type_id": "note", "fields": ["content (required)", "about"]},
        ]

        result = {
            "total_notes": len(note_memories),
            "memories": note_memories,
            "available_types": available_types,
            "instructions": (
                "Review each note memory and determine if it would be better represented as a structured type. "
                "For each memory you want to convert, analyze the text and extract the appropriate fields.\n\n"
                "When ready, provide your suggestions as a JSON code block like this:\n"
                "```json\n"
                "[\n"
                "  {\"memory_id\": \"uuid-here\", \"new_type\": \"relational\", \"content\": {\"entity\": \"...\", \"summary\": \"...\"}},\n"
                "  {\"memory_id\": \"other-uuid\", \"new_type\": \"myth_seed\", \"content\": {\"seed\": \"...\", \"origin\": \"...\"}}\n"
                "]\n"
                "```\n\n"
                "Only include memories you want to convert. Memories that should stay as notes can be omitted."
            ),
        }

        return ToolResult(
            tool_name=ToolName.CLASSIFY_MEMORY_TYPES.value,
            success=True,
            result=result,
            display_message=f"Found {len(note_memories)} note/imported memories for classification",
        )

    def _apply_type_conversions(self, conversions: list[dict[str, Any]]) -> ToolResult:
        """Apply type conversions to memories."""
        if not conversions:
            return ToolResult(
                tool_name=ToolName.CLASSIFY_MEMORY_TYPES.value,
                success=False,
                error="conversions list is required for 'convert' action",
            )

        from threadlight.storage.base import CapsuleFilter

        # Get memories respecting profile isolation
        profile_scope = None
        include_shared = True

        if hasattr(self.memory, 'threadlight') and self.memory.threadlight:
            tl = self.memory.threadlight
            if tl.config.memory.per_profile_isolation and tl.active_profile:
                profile_scope = tl.active_profile.id
                include_shared = tl.active_profile.access_shared_memories

        all_filter = CapsuleFilter(
            limit=10000,
            profile_scope=profile_scope,
            include_shared=include_shared
        )
        memories = self.memory.storage.list_capsules(all_filter)
        memory_map = {m.id: m for m in memories}

        converted_count = 0
        errors = []

        valid_types = ["relational", "myth_seed", "witness", "note"]

        for conv in conversions:
            memory_id = conv.get("memory_id")
            new_type = conv.get("new_type")
            new_content = conv.get("content", {})

            if not memory_id:
                errors.append("Missing memory_id in conversion")
                continue

            if not new_type:
                errors.append(f"Missing new_type for memory {memory_id[:8]}...")
                continue

            if new_type not in valid_types:
                errors.append(f"Invalid type '{new_type}' for memory {memory_id[:8]}...")
                continue

            # Find the memory
            memory = memory_map.get(memory_id)
            if not memory:
                errors.append(f"Memory {memory_id[:8]}... not found or not accessible")
                continue

            # Preserve original text in content for reference
            old_content = memory.content if isinstance(memory.content, dict) else {}
            original_text = old_content.get('text') or old_content.get('content') or str(old_content)

            # Update the capsule type and content
            memory.type = CapsuleType(new_type)
            memory.content = new_content  # Use the structured content from the classification
            memory.cue_phrases = []  # Will be regenerated

            # Preserve original text for reference
            if original_text and not new_content.get('_original_text'):
                memory.content['_original_text'] = original_text

            if self.memory.storage.update_capsule(memory):
                converted_count += 1
                logger.info(f"Converted memory {memory_id[:8]}... to type: {new_type}")
            else:
                errors.append(f"Failed to update memory {memory_id[:8]}...")

        result = {
            "converted": converted_count,
            "requested": len(conversions),
            "errors": errors if errors else None,
        }

        display_msg = f"Converted {converted_count} memory type(s)"
        if errors:
            display_msg += f" ({len(errors)} error(s))"

        return ToolResult(
            tool_name=ToolName.CLASSIFY_MEMORY_TYPES.value,
            success=True,
            result=result,
            display_message=display_msg,
        )


def execute_tool_call(
    memory: MemoryOrchestrator,
    tool_name: str,
    arguments: dict[str, Any] | str,
    require_consent: bool = True,
) -> ToolResult:
    """
    Convenience function to execute a single tool call.

    Args:
        memory: Memory orchestrator
        tool_name: Name of the tool
        arguments: Tool arguments (dict or JSON string)
        require_consent: Whether memory creation requires consent

    Returns:
        ToolResult with execution result
    """
    # Parse arguments if string
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as e:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Invalid JSON arguments: {e}",
            )

    executor = ToolExecutor(memory, require_consent_for_memories=require_consent)
    return executor.execute(tool_name, arguments)
