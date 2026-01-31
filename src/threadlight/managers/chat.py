"""
Chat orchestration for Threadlight.

This module handles core chat operations including:
- Message completion with tool calling
- Context building from memory
- Soft memory integration
- Auto-saving of conversation messages
"""

from __future__ import annotations

from typing import Any, Iterator, Optional, TYPE_CHECKING
import logging
import json

if TYPE_CHECKING:
    from threadlight.core import Threadlight
    from threadlight.capsules.base import ContextMode, MemoryCapsule, CapsuleType
    from threadlight.context.composer import ComposedContext
    from threadlight.providers.base import ProviderMessage, ProviderResponse
    from threadlight.tools.executor import ToolResult

logger = logging.getLogger(__name__)

# Maximum tool calling iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 10


class ChatManager:
    """
    Manages chat operations for Threadlight.

    This manager handles:
    - Tool calling loops
    - Context building from memory
    - Soft memory integration
    - Message auto-saving
    """

    def __init__(self, threadlight: 'Threadlight'):
        """
        Initialize the chat manager.

        Args:
            threadlight: Reference to parent Threadlight instance
        """
        self.tl = threadlight

    def complete_with_tools(
        self,
        messages: list['ProviderMessage'],
        tools: Optional[list[dict[str, Any]]] = None,
        model_id: Optional[str] = None,
        **kwargs: Any
    ) -> 'ProviderResponse':
        """
        Complete with tool calling loop.

        If the model returns tool_calls, executes them and sends results
        back to the model until it returns a text response.

        Supports multi-provider routing: if model_id is specified and the model
        has a provider_id configured, the request is routed to that provider.

        Args:
            messages: Conversation messages
            tools: Tool definitions (None to disable)
            model_id: Model to use (for multi-provider routing)
            **kwargs: Provider options

        Returns:
            Final ProviderResponse with text content
        """
        from threadlight.providers.base import ProviderMessage

        iteration = 0
        accumulated_tool_results: list['ToolResult'] = []

        # Determine which provider to use
        # If model_id specified and multi-provider is configured, use ProviderManager
        use_provider_manager = (
            model_id is not None and
            hasattr(self.tl, 'provider_manager') and
            self.tl.config.providers
        )

        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1

            # Make the API call - route to appropriate provider
            if use_provider_manager:
                response = self.tl.provider_manager.complete(
                    model_id=model_id,
                    messages=messages,
                    tools=tools,
                    **kwargs
                )
            else:
                response = self.tl.provider.complete(messages, tools=tools, **kwargs)

            # If no tool calls, we're done
            if not response.has_tool_calls:
                # Attach tool results to response metadata
                if accumulated_tool_results:
                    if response.raw is None:
                        response.raw = {}
                    response.raw["tool_results"] = [r.to_dict() for r in accumulated_tool_results]
                return response

            logger.debug(f"Model requested {len(response.tool_calls)} tool call(s)")

            # Add the assistant message with tool calls to context
            messages.append(ProviderMessage.assistant_with_tool_calls(
                content=response.content,
                tool_calls=response.tool_calls,
            ))

            # Execute each tool call
            for tool_call in response.tool_calls:
                logger.debug(f"Executing tool: {tool_call.name}")

                # Parse arguments
                try:
                    arguments = json.loads(tool_call.arguments)
                except json.JSONDecodeError as e:
                    arguments = {}
                    logger.warning(f"Failed to parse tool arguments: {e}")

                # Execute the tool
                result = self.tl.tool_executor.execute(tool_call.name, arguments)
                accumulated_tool_results.append(result)

                logger.debug(f"Tool result: success={result.success}, consent={result.requires_consent}")

                # Add tool response to messages
                messages.append(ProviderMessage.tool_response(
                    tool_call_id=tool_call.id,
                    content=result.to_tool_response(),
                ))

        # If we hit max iterations, return last response
        logger.warning(f"Hit max tool iterations ({MAX_TOOL_ITERATIONS})")
        return response

    def build_context(
        self,
        message: str,
        memory_filter: Optional[dict[str, Any]] = None,
        context_mode: Optional['ContextMode'] = None,
    ) -> 'ComposedContext':
        """Build context from memory for a message."""
        from threadlight.capsules.base import CapsuleType

        # Recall relevant memories
        capsules = self.tl.memory.recall_for_message(
            message,
            limit=self.tl.config.memory.max_capsules_per_request,
        )

        # Apply additional filter if provided
        if memory_filter:
            if "type" in memory_filter:
                filter_type = CapsuleType(memory_filter["type"])
                capsules = [c for c in capsules if c.type == filter_type]
            if "entity" in memory_filter:
                entity = memory_filter["entity"].lower()
                capsules = [
                    c for c in capsules
                    if hasattr(c, 'entity') and entity in c.entity.lower()
                ]

        # Get active ritual if any
        active_ritual = self.tl.memory.get_active_ritual()

        # Compose context
        return self.tl.composer.compose(
            capsules=capsules,
            style_profile=self.tl.style_profile,
            mode=context_mode,
            active_ritual=active_ritual,
        )

    def build_soft_memory_context(self, message: str) -> str:
        """Build soft memory context from past conversations."""
        if not self.tl.soft_memory:
            return ""

        try:
            results = self.tl.soft_memory.recall_relevant(
                message,
                limit=self.tl.config.memory.conversation.soft_memory_limit,
            )

            if not results:
                return ""

            return self.tl.soft_memory.format_for_prompt(
                results,
                header="## Relevant Past Conversations",
            )
        except Exception as e:
            logger.warning(f"Soft memory recall failed: {e}")
            return ""

    def auto_save_messages(self, user_message: str, assistant_response: str) -> None:
        """Auto-save user message and assistant response to database."""
        # Ensure we have a conversation attached to the session
        if self.tl.memory.get_current_session():
            if not self.tl.memory.get_current_session().conversation_id:
                self.tl.memory.attach_conversation_to_session()

        # Save the message pair
        self.tl.memory.save_message_pair(user_message, assistant_response)

    def stream(
        self,
        message: str,
        history: Optional[list[dict[str, str]]] = None,
        context_mode: Optional['ContextMode'] = None,
        model_id: Optional[str] = None,
        **kwargs: Any
    ) -> Iterator[str]:
        """
        Stream a response token by token.

        Supports multi-provider routing: if model_id is specified and the model
        has a provider_id configured, the request is routed to that provider.

        Args:
            message: User message
            history: Conversation history
            context_mode: Context composition mode
            model_id: Model to use (for multi-provider routing)
            **kwargs: Additional provider options

        Yields:
            Text chunks as they arrive.
        """
        from threadlight.providers.base import ProviderMessage

        messages = []

        # Build context
        if self.tl.enable_memory:
            context = self.build_context(message, context_mode=context_mode)
            if context.system_message:
                messages.append(ProviderMessage(role="system", content=context.system_message))

        if history:
            for msg in history:
                messages.append(ProviderMessage(role=msg["role"], content=msg["content"]))

        messages.append(ProviderMessage(role="user", content=message))

        # Determine which provider to use
        use_provider_manager = (
            model_id is not None and
            hasattr(self.tl, 'provider_manager') and
            self.tl.config.providers
        )

        if use_provider_manager:
            yield from self.tl.provider_manager.stream(model_id=model_id, messages=messages, **kwargs)
        else:
            yield from self.tl.provider.stream(messages, **kwargs)
