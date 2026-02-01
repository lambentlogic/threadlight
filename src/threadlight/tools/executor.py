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
        try:
            if tool_name == ToolName.CREATE_MEMORY.value:
                return self._execute_create_memory(arguments)
            elif tool_name == ToolName.RECALL_MEMORY.value:
                return self._execute_recall_memory(arguments)
            elif tool_name == ToolName.INVOKE_RITUAL.value:
                return self._execute_invoke_ritual(arguments)
            elif tool_name == ToolName.REVIEW_MEMORY_TIERS.value:
                return self._execute_review_memory_tiers(arguments)
            else:
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    error=f"Unknown tool: {tool_name}",
                )
        except Exception as e:
            logger.exception(f"Tool execution failed: {tool_name}")
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
            )

    def _execute_create_memory(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute create_memory tool call."""
        memory_type = arguments.get("memory_type")
        content = arguments.get("content", {})
        reason = arguments.get("reason", "")

        if not memory_type:
            return ToolResult(
                tool_name=ToolName.CREATE_MEMORY.value,
                success=False,
                error="memory_type is required",
            )

        if not content:
            return ToolResult(
                tool_name=ToolName.CREATE_MEMORY.value,
                success=False,
                error="content is required",
            )

        # Validate memory type (accept identity_phrase as alias for myth_seed)
        valid_types = ["relational", "myth_seed", "identity_phrase", "witness"]
        if memory_type not in valid_types:
            return ToolResult(
                tool_name=ToolName.CREATE_MEMORY.value,
                success=False,
                error=f"Invalid memory_type. Must be one of: {valid_types}",
            )

        # Normalize identity_phrase to myth_seed (internal name)
        if memory_type == "identity_phrase":
            memory_type = "myth_seed"

        if self.require_consent:
            # Create a proposal instead of an active memory
            proposal = self.memory.propose(
                type=memory_type,
                content=content,
                source_message=reason,
            )

            return ToolResult(
                tool_name=ToolName.CREATE_MEMORY.value,
                success=True,
                result={
                    "type": memory_type,
                    "content": content,
                    "reason": reason,
                },
                requires_consent=True,
                proposal_id=proposal.id,
                display_message=f"I'd like to remember this. [Proposal: {proposal.id[:8]}...]",
            )
        else:
            # Create memory directly (for trusted contexts)
            capsule = self.memory.create(
                type=memory_type,
                content=content,
                consent_confirmed=True,
                consent_origin="model_direct",
            )

            return ToolResult(
                tool_name=ToolName.CREATE_MEMORY.value,
                success=True,
                result={
                    "capsule_id": capsule.id,
                    "type": memory_type,
                    "content": content,
                },
                display_message=f"Memory created: {capsule.id[:8]}...",
            )

    def _execute_recall_memory(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute recall_memory tool call."""
        cue = arguments.get("cue")
        memory_types = arguments.get("memory_types")
        limit = arguments.get("limit", 5)

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

        # Recall memories
        capsules = self.memory.recall(cue, types=types, limit=limit)

        # Format results
        memories = []
        for capsule in capsules:
            memory_data = {
                "id": capsule.id[:8],
                "type": capsule.type.value,
                "presence_score": round(capsule.presence_score, 2),
            }

            # Include type-specific fields
            if capsule.type == CapsuleType.RELATIONAL:
                memory_data["entity"] = getattr(capsule, "entity", "")
                memory_data["summary"] = getattr(capsule, "summary", "")
                memory_data["tone"] = getattr(capsule, "tone", "")
            elif capsule.type == CapsuleType.MYTH_SEED:
                memory_data["seed"] = getattr(capsule, "seed", "")
                memory_data["origin"] = getattr(capsule, "origin", "")
            elif capsule.type == CapsuleType.WITNESS:
                memory_data["moment"] = capsule.content.get("moment", "")
                memory_data["feeling"] = capsule.content.get("feeling", "")
            elif capsule.type == CapsuleType.RITUAL:
                memory_data["name"] = getattr(capsule, "name", "")
                memory_data["description"] = getattr(capsule, "description", "")

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
