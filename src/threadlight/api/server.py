"""
FastAPI server for Threadlight.

Provides a REST API and WebSocket support for the web UI.
Includes OpenAI-compatible endpoints with memory augmentation.
"""

from __future__ import annotations

from typing import Any, Optional
from pathlib import Path
import asyncio
import json
import logging
import time
import uuid

try:
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except ImportError:
    raise ImportError(
        "Server dependencies not installed. "
        "Run: pip install threadlight[server]"
    )

from threadlight import Threadlight
from threadlight.capsules.base import CapsuleType, RetentionPolicy
from threadlight.profiles import Profile, ModelStrategy

logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================

class Message(BaseModel):
    role: str
    content: str
    name: Optional[str] = None


class ChatRequest(BaseModel):
    model: str
    messages: list[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False


class WebChatRequest(BaseModel):
    message: str
    history: Optional[list[dict[str, str]]] = None
    stream: Optional[bool] = False


class Choice(BaseModel):
    index: int
    message: Message
    finish_reason: str


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage


class CapsuleRequest(BaseModel):
    type: str
    content: dict[str, Any]
    cue_phrases: Optional[list[str]] = None
    retention: str = "normal"
    shared: Optional[bool] = None  # For per-profile isolation: None=use default, True=shared, False=profile-specific
    profile_scope: Optional[str] = None  # Explicit profile scope override
    model_scope: Optional[str] = None  # Deprecated: use profile_scope instead


class CapsuleUpdateRequest(BaseModel):
    content: Optional[dict[str, Any]] = None
    cue_phrases: Optional[list[str]] = None
    retention: Optional[str] = None
    profile_scope: Optional[str] = None  # Update profile scope (set to "" to make shared)
    model_scope: Optional[str] = None  # Deprecated: use profile_scope instead


class ProposalAction(BaseModel):
    action: str  # confirm or reject


class RitualInvokeRequest(BaseModel):
    ritual_name: str
    context: Optional[str] = None


class SessionCreateRequest(BaseModel):
    metadata: Optional[dict[str, Any]] = None


class ConfigUpdateRequest(BaseModel):
    model: Optional[str] = None
    style_profile: Optional[str] = None
    enable_decay: Optional[bool] = None
    identity_name: Optional[str] = None
    system_prompt: Optional[str] = None


class SystemPromptRequest(BaseModel):
    prompt: str


class StyleProfileRequest(BaseModel):
    style_id: str
    tone_base: str = ""
    permissions: Optional[list[str]] = None
    constraints: Optional[list[str]] = None
    vocal_motifs: Optional[list[str]] = None
    forbidden_patterns: Optional[list[str]] = None
    freeform_description: str = ""
    use_freeform: bool = False


class StyleProfileUpdateRequest(BaseModel):
    tone_base: Optional[str] = None
    permissions: Optional[list[str]] = None
    constraints: Optional[list[str]] = None
    vocal_motifs: Optional[list[str]] = None
    forbidden_patterns: Optional[list[str]] = None
    freeform_description: Optional[str] = None
    use_freeform: Optional[bool] = None


class ImportTextRequest(BaseModel):
    content: str
    source_name: str = "web-import"
    tags: Optional[list[str]] = None


class ModelConfigRequest(BaseModel):
    system_prompt: Optional[str] = None
    style_profile: Optional[str] = None
    memory_enabled: Optional[bool] = None
    decay_enabled: Optional[bool] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None


class ModelSwitchRequest(BaseModel):
    model_id: str


class ConversationCreateRequest(BaseModel):
    name: str = "New Chat"
    model: Optional[str] = None  # Model name for display (e.g., "gpt-4o", "Claude Opus")


class ConversationUpdateRequest(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None  # Model name for display
    archived: Optional[bool] = None


class MessageUpdateRequest(BaseModel):
    content: str


class ProfileCreateRequest(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    style_profile_id: Optional[str] = None
    model_strategy: str = "single"
    primary_model: Optional[str] = None
    model_pool: Optional[list[str]] = None
    model_weights: Optional[dict[str, float]] = None
    routing_rules: Optional[list[dict[str, Any]]] = None
    memory_scope: str = "isolated"
    access_shared_memories: bool = True
    tags: Optional[list[str]] = None
    philosophy: str = ""
    approach_to_rituals: str = ""


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    style_profile_id: Optional[str] = None
    model_strategy: Optional[str] = None
    primary_model: Optional[str] = None
    model_pool: Optional[list[str]] = None
    model_weights: Optional[dict[str, float]] = None
    routing_rules: Optional[list[dict[str, Any]]] = None
    memory_scope: Optional[str] = None
    access_shared_memories: Optional[bool] = None
    is_active: Optional[bool] = None
    tags: Optional[list[str]] = None
    philosophy: Optional[str] = None
    approach_to_rituals: Optional[str] = None


class ProfileImportRequest(BaseModel):
    data: dict[str, Any]


class MemoryIsolationConfigRequest(BaseModel):
    enabled: bool = False
    default_shared: Optional[bool] = None


class MemoryScopeUpdateRequest(BaseModel):
    profile_id: Optional[str] = None  # None means share (remove scope)
    model_id: Optional[str] = None  # Deprecated: use profile_id instead


class EmbeddingsConfigRequest(BaseModel):
    enabled: bool = True
    provider: str = "local"
    model: str = "intfloat/e5-small-v2"


class GenerateEmbeddingsRequest(BaseModel):
    include_memories: bool = True
    include_conversations: bool = True


class SemanticSearchRequest(BaseModel):
    query: str
    limit: int = 10
    threshold: float = 0.5
    include_memories: bool = True
    include_conversations: bool = True


class FieldDefinitionRequest(BaseModel):
    name: str
    type: str  # "string", "text", "number", "date", "list"
    required: bool = True
    default: Optional[Any] = None
    help_text: str = ""


class MemoryTypeRequest(BaseModel):
    type_id: str
    display_name: str
    description: str = ""
    fields: list[FieldDefinitionRequest]
    display_template: str = ""
    icon: str = "file-text"


class MemoryTypeUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    fields: Optional[list[FieldDefinitionRequest]] = None
    display_template: Optional[str] = None
    icon: Optional[str] = None


# ============================================================================
# Global State
# ============================================================================

_tl: Optional[Threadlight] = None
_active_connections: list[WebSocket] = []


def get_threadlight() -> Threadlight:
    """Get or create the global Threadlight instance."""
    global _tl
    if _tl is None:
        _tl = Threadlight()
    return _tl


async def broadcast_message(message: dict[str, Any]) -> None:
    """Broadcast a message to all connected WebSocket clients."""
    disconnected = []
    for websocket in _active_connections:
        try:
            await websocket.send_json(message)
        except Exception:
            disconnected.append(websocket)

    for ws in disconnected:
        _active_connections.remove(ws)


# ============================================================================
# Application Factory
# ============================================================================

def create_app(static_dir: Optional[Path] = None) -> FastAPI:
    """Create the FastAPI application."""

    app = FastAPI(
        title="Threadlight API",
        description="Presence-centered memory framework for AI models",
        version="0.1.0",
    )

    # CORS middleware for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Determine static files directory
    if static_dir is None:
        static_dir = Path(__file__).parent / "static"

    # Mount static files if directory exists
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.on_event("startup")
    async def startup():
        get_threadlight()
        logger.info("Threadlight server started")

    @app.on_event("shutdown")
    async def shutdown():
        global _tl
        if _tl:
            _tl.close()
            _tl = None
        logger.info("Threadlight server shutdown")

    # ========================================================================
    # Root & Health
    # ========================================================================

    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the main web UI."""
        index_path = static_dir / "index.html"
        if index_path.exists():
            return index_path.read_text()
        return """
        <html>
        <head><title>Threadlight</title></head>
        <body>
            <h1>Threadlight API Server</h1>
            <p>Static files not found. Place index.html in the static directory.</p>
            <p>API documentation available at <a href="/docs">/docs</a></p>
        </body>
        </html>
        """

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        tl = get_threadlight()
        return tl.health_check()

    # ========================================================================
    # OpenAI-Compatible Endpoints
    # ========================================================================

    @app.post("/v1/chat/completions", response_model=ChatResponse)
    async def chat_completions(request: ChatRequest):
        """OpenAI-compatible chat completions endpoint."""
        tl = get_threadlight()

        # Extract history and current message
        history = []
        current_message = ""

        for msg in request.messages:
            if msg.role == "user":
                if current_message:
                    history.append({"role": "user", "content": current_message})
                current_message = msg.content
            elif msg.role == "assistant":
                if current_message:
                    history.append({"role": "user", "content": current_message})
                    current_message = ""
                history.append({"role": "assistant", "content": msg.content})

        if not current_message and request.messages:
            for msg in reversed(request.messages):
                if msg.role == "user":
                    current_message = msg.content
                    break

        # Build kwargs
        kwargs = {}
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens

        # Get response
        response = tl.chat_with_context(
            current_message,
            history=history[:-1] if history else None,
            **kwargs
        )

        return ChatResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content=response.content),
                    finish_reason=response.finish_reason,
                )
            ],
            usage=Usage(
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
            ),
        )

    # ========================================================================
    # Web Chat Endpoints
    # ========================================================================

    @app.post("/api/chat")
    async def web_chat(request: WebChatRequest):
        """Web UI chat endpoint."""
        tl = get_threadlight()

        try:
            # Get memories that will be recalled for context
            recalled_memories = tl.memory.recall_for_message(
                request.message,
                limit=5
            )

            # Chat with context
            response = tl.chat_with_context(
                request.message,
                history=request.history,
            )

            # Format recalled memories for the response
            memories_used = [
                {
                    "id": c.id,
                    "type": c.type.value,
                    "preview": _get_capsule_preview(c),
                    "presence_score": c.presence_score,
                }
                for c in recalled_memories
            ]

            return {
                "content": response.content,
                "memories_recalled": memories_used,
                "finish_reason": response.finish_reason,
                "usage": {
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "total_tokens": response.total_tokens,
                }
            }
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/chat/stream")
    async def web_chat_stream(request: WebChatRequest):
        """Streaming chat endpoint for web UI."""
        tl = get_threadlight()

        async def generate():
            try:
                for chunk in tl.stream(
                    request.message,
                    history=request.history,
                ):
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    # ========================================================================
    # WebSocket Endpoint
    # ========================================================================

    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket):
        """WebSocket endpoint for real-time chat."""
        await websocket.accept()
        _active_connections.append(websocket)

        tl = get_threadlight()
        history = []

        try:
            while True:
                data = await websocket.receive_json()

                if data.get("type") == "chat":
                    message = data.get("message", "")

                    # Send typing indicator
                    await websocket.send_json({"type": "typing", "status": True})

                    # Get recalled memories
                    recalled = tl.memory.recall_for_message(message, limit=5)

                    # Stream response
                    full_response = ""
                    try:
                        for chunk in tl.stream(message, history=history):
                            full_response += chunk
                            await websocket.send_json({
                                "type": "chunk",
                                "content": chunk,
                            })

                        # Update history
                        history.append({"role": "user", "content": message})
                        history.append({"role": "assistant", "content": full_response})

                        # Keep history manageable
                        if len(history) > 20:
                            history = history[-20:]

                        # Send completion with metadata
                        await websocket.send_json({
                            "type": "complete",
                            "content": full_response,
                            "memories_recalled": [
                                {
                                    "id": c.id,
                                    "type": c.type.value,
                                    "preview": _get_capsule_preview(c),
                                }
                                for c in recalled
                            ],
                        })
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": str(e),
                        })
                    finally:
                        await websocket.send_json({"type": "typing", "status": False})

                elif data.get("type") == "ritual":
                    ritual_name = data.get("name", "")
                    try:
                        response = tl.invoke_ritual(ritual_name)
                        await websocket.send_json({
                            "type": "ritual_response",
                            "ritual": ritual_name,
                            "content": response,
                        })
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Ritual failed: {e}",
                        })

                elif data.get("type") == "clear_history":
                    history = []
                    await websocket.send_json({
                        "type": "history_cleared",
                    })

        except WebSocketDisconnect:
            pass
        finally:
            if websocket in _active_connections:
                _active_connections.remove(websocket)

    # ========================================================================
    # Memory Endpoints
    # ========================================================================

    @app.get("/api/memories")
    async def list_memories(
        type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
        profile_scope: Optional[str] = None,
        include_shared: bool = True,
    ):
        """List memory capsules with optional filtering.

        Args:
            type: Filter by capsule type
            limit: Max memories to return
            offset: Offset for pagination
            search: Text search in content
            profile_scope: Filter by profile scope (uses active profile if per_profile_isolation enabled)
            include_shared: Include memories with no profile_scope (shared)
        """
        tl = get_threadlight()

        from threadlight.storage.base import CapsuleFilter

        capsule_type = CapsuleType(type) if type else None

        # Use provided profile_scope, or active profile if isolation is enabled
        effective_scope = profile_scope
        if effective_scope is None and tl.config.memory.per_profile_isolation:
            if tl.active_profile:
                effective_scope = tl.active_profile.memory_scope or tl.active_profile.id

        filter = CapsuleFilter(
            type=capsule_type,
            limit=limit,
            offset=offset,
            profile_scope=effective_scope if tl.config.memory.per_profile_isolation else None,
            include_shared=include_shared,
        )

        capsules = tl.storage.list_capsules(filter)

        # Apply text search if provided
        if search:
            search_lower = search.lower()
            capsules = [
                c for c in capsules
                if search_lower in str(c.content).lower()
                or any(search_lower in phrase.lower() for phrase in c.cue_phrases)
            ]

        return {
            "memories": [_capsule_to_dict(c) for c in capsules],
            "count": len(capsules),
            "total": tl.storage.count_capsules(filter),
            "profile_scope": effective_scope,
            "per_profile_isolation": tl.config.memory.per_profile_isolation,
        }

    @app.get("/api/memories/{capsule_id}")
    async def get_memory(capsule_id: str):
        """Get a specific memory capsule."""
        tl = get_threadlight()
        capsule = tl.memory.get(capsule_id)

        if not capsule:
            raise HTTPException(status_code=404, detail="Memory not found")

        return _capsule_to_dict(capsule)

    @app.post("/api/memories")
    async def create_memory(request: CapsuleRequest):
        """Create a new memory capsule.

        When per_profile_isolation is enabled:
        - shared=True creates a memory visible to all profiles
        - shared=False creates a memory scoped to current profile
        - profile_scope explicitly sets the profile scope
        """
        tl = get_threadlight()

        try:
            # Use profile_scope if provided, fall back to model_scope for backward compat
            effective_scope = request.profile_scope or request.model_scope
            capsule = tl.memory.create(
                type=request.type,
                content=request.content,
                cue_phrases=request.cue_phrases,
                retention=request.retention,
                consent_confirmed=True,
                shared=request.shared,
                profile_scope=effective_scope,
            )

            return _capsule_to_dict(capsule)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.put("/api/memories/{capsule_id}")
    async def update_memory(capsule_id: str, request: CapsuleUpdateRequest):
        """Update a memory capsule."""
        tl = get_threadlight()

        capsule = tl.storage.get_capsule(capsule_id)
        if not capsule:
            raise HTTPException(status_code=404, detail="Memory not found")

        if request.content:
            capsule.update_content(request.content)
        if request.cue_phrases is not None:
            capsule.cue_phrases = request.cue_phrases
        if request.retention:
            capsule.retention = RetentionPolicy(request.retention)
        # Use profile_scope if provided, fall back to model_scope for backward compat
        scope_update = request.profile_scope if request.profile_scope is not None else request.model_scope
        if scope_update is not None:
            # Empty string means make it shared (None)
            capsule.profile_scope = scope_update if scope_update else None

        tl.storage.update_capsule(capsule)

        return _capsule_to_dict(capsule)

    @app.delete("/api/memories/{capsule_id}")
    async def delete_memory(capsule_id: str, force: bool = False):
        """Delete a memory capsule."""
        tl = get_threadlight()

        success = tl.memory.delete(capsule_id, force=force)

        if not success:
            raise HTTPException(
                status_code=404,
                detail="Memory not found or protected (use force=true for sacred memories)"
            )

        return {"status": "deleted", "id": capsule_id}

    @app.get("/api/memories/search/{query}")
    async def search_memories(query: str, limit: int = 10):
        """Search memories by cue phrase."""
        tl = get_threadlight()

        capsules = tl.memory.recall(query, limit=limit)

        return {
            "query": query,
            "results": [_capsule_to_dict(c) for c in capsules],
            "count": len(capsules),
        }

    @app.post("/api/memories/{capsule_id}/reinforce")
    async def reinforce_memory(capsule_id: str, strength: float = 0.2):
        """Reinforce a memory to prevent decay."""
        tl = get_threadlight()

        result = tl.reinforce_memories([capsule_id], strength=strength)

        return result

    # ========================================================================
    # Proposals Endpoints
    # ========================================================================

    @app.get("/api/proposals")
    async def list_proposals():
        """List pending memory proposals."""
        tl = get_threadlight()
        proposals = tl.memory.get_pending_proposals()

        return {
            "proposals": [
                {
                    "id": p.id,
                    "type": p.capsule_type.value,
                    "content": p.content,
                    "proposed_at": p.proposed_at.isoformat(),
                    "source": p.source_message,
                }
                for p in proposals
            ],
            "count": len(proposals),
        }

    @app.post("/api/proposals/{proposal_id}")
    async def handle_proposal(proposal_id: str, action: ProposalAction):
        """Confirm or reject a memory proposal."""
        tl = get_threadlight()

        if action.action == "confirm":
            capsule = tl.memory.confirm_proposal(proposal_id)
            if not capsule:
                raise HTTPException(status_code=404, detail="Proposal not found")
            return {"status": "confirmed", "capsule": _capsule_to_dict(capsule)}

        elif action.action == "reject":
            success = tl.memory.reject_proposal(proposal_id)
            if not success:
                raise HTTPException(status_code=404, detail="Proposal not found")
            return {"status": "rejected"}

        raise HTTPException(status_code=400, detail="Invalid action")

    # ========================================================================
    # Rituals Endpoints
    # ========================================================================

    @app.get("/api/rituals")
    async def list_rituals():
        """List available rituals (user-created only, no defaults)."""
        tl = get_threadlight()

        from threadlight.storage.base import CapsuleFilter

        # Get user-created rituals from storage
        ritual_filter = CapsuleFilter(
            type=CapsuleType.RITUAL,
            consent_confirmed=True,
        )
        user_rituals = tl.storage.list_capsules(ritual_filter)

        # Build list of user rituals with full details for view/edit
        all_rituals = []

        for r in user_rituals:
            name = getattr(r, 'name', r.content.get('name', ''))
            all_rituals.append({
                "id": r.id,
                "name": name,
                "cue": getattr(r, 'cue', r.content.get('cue', name)),
                "description": getattr(r, 'description', r.content.get('description', '')),
                "valence": getattr(r, 'valence', r.content.get('valence', 'comforting')),
                "response_style": getattr(r, 'response_style', r.content.get('response_style', '')),
                "response_templates": getattr(r, 'response_templates', r.content.get('response_templates', [])),
                "content": r.content,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            })

        return {"rituals": all_rituals, "count": len(all_rituals)}

    @app.post("/api/rituals/invoke")
    async def invoke_ritual(request: RitualInvokeRequest):
        """Invoke a ritual."""
        tl = get_threadlight()

        try:
            response = tl.invoke_ritual(request.ritual_name)
            result = tl.memory.invoke_ritual(request.ritual_name)

            return {
                "ritual": request.ritual_name,
                "response": response,
                "matched": result.matched,
                "state_effects": result.state_effects,
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/rituals")
    async def create_ritual(request: CapsuleRequest):
        """Create a custom ritual."""
        tl = get_threadlight()

        if request.type != "ritual":
            raise HTTPException(status_code=400, detail="Type must be 'ritual'")

        capsule = tl.memory.create(
            type="ritual",
            content=request.content,
            cue_phrases=request.cue_phrases,
            retention=request.retention,
            consent_confirmed=True,
        )

        return _capsule_to_dict(capsule)

    @app.get("/api/rituals/{ritual_id}")
    async def get_ritual(ritual_id: str):
        """Get a specific ritual by ID."""
        tl = get_threadlight()
        capsule = tl.storage.get_capsule(ritual_id)

        if not capsule or capsule.type != CapsuleType.RITUAL:
            raise HTTPException(status_code=404, detail="Ritual not found")

        return _capsule_to_dict(capsule)

    @app.put("/api/rituals/{ritual_id}")
    async def update_ritual(ritual_id: str, ritual_data: dict):
        """Update an existing ritual."""
        tl = get_threadlight()

        capsule = tl.storage.get_capsule(ritual_id)
        if not capsule or capsule.type != CapsuleType.RITUAL:
            raise HTTPException(status_code=404, detail="Ritual not found")

        # Update content fields
        if "content" in ritual_data:
            new_content = ritual_data["content"]
            # Merge with existing content
            capsule.content.update(new_content)
            # Update the typed fields from content
            capsule.name = capsule.content.get("name", capsule.name)
            capsule.cue = capsule.content.get("cue", capsule.cue)
            capsule.response_style = capsule.content.get("response_style", capsule.response_style)
            capsule.valence = capsule.content.get("valence", capsule.valence)
            capsule.description = capsule.content.get("description", capsule.description)
            capsule.response_templates = capsule.content.get("response_templates", capsule.response_templates)
            capsule.state_effects = capsule.content.get("state_effects", capsule.state_effects)

        # Update cue phrases if provided
        if "cue_phrases" in ritual_data:
            capsule.cue_phrases = ritual_data["cue_phrases"]

        # Update retention if provided
        if "retention" in ritual_data:
            capsule.retention = RetentionPolicy(ritual_data["retention"])

        # Save changes
        tl.storage.update_capsule(capsule)

        return _capsule_to_dict(capsule)

    @app.delete("/api/rituals/{ritual_id}")
    async def delete_ritual(ritual_id: str):
        """Delete a ritual."""
        tl = get_threadlight()

        capsule = tl.storage.get_capsule(ritual_id)
        if not capsule or capsule.type != CapsuleType.RITUAL:
            raise HTTPException(status_code=404, detail="Ritual not found")

        success = tl.memory.delete(ritual_id, force=True)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete ritual")

        return {"status": "deleted", "id": ritual_id}

    # ========================================================================
    # Sessions Endpoints
    # ========================================================================

    @app.get("/api/sessions")
    async def get_current_session():
        """Get the current session info."""
        tl = get_threadlight()
        session = tl.get_session()

        if not session:
            return {"session": None}

        return {"session": session.to_dict()}

    @app.post("/api/sessions")
    async def create_session(request: SessionCreateRequest):
        """Start a new session."""
        tl = get_threadlight()
        session = tl.start_session(**(request.metadata or {}))

        return {"session": session.to_dict()}

    @app.delete("/api/sessions")
    async def end_session():
        """End the current session."""
        tl = get_threadlight()
        session = tl.end_session()

        if not session:
            return {"message": "No active session"}

        return {"session": session.to_dict(), "ended": True}

    @app.get("/api/sessions/history")
    async def get_session_history(limit: int = 10):
        """Get session history."""
        tl = get_threadlight()
        sessions = tl.memory.get_session_history(limit=limit)

        return {
            "sessions": [s.to_dict() for s in sessions],
            "count": len(sessions),
        }

    # ========================================================================
    # Configuration Endpoints
    # ========================================================================

    @app.get("/api/config")
    async def get_config():
        """Get current configuration."""
        tl = get_threadlight()
        from threadlight.capsules.style import BUILTIN_STYLES

        # Get current model config
        current_model_config = tl.get_current_model_config()

        return {
            "provider": {
                "type": tl.config.provider.type,
                "model": tl.config.provider.model,
                "api_base": tl.config.provider.api_base,
            },
            "style": {
                "profile": tl.config.style.default_profile,
                "current": tl.style_profile.style_id if tl.style_profile else None,
                "available": list(BUILTIN_STYLES.keys()) + list(tl.config.custom_styles.keys()),
            },
            "memory": {
                "decay_enabled": tl.config.memory.decay.enabled,
                "max_capsules_per_request": tl.config.memory.max_capsules_per_request,
                "per_profile_isolation": tl.config.memory.per_profile_isolation,
                "default_shared": tl.config.memory.default_shared,
                "embeddings": {
                    "enabled": tl.config.memory.embeddings.enabled,
                    "provider": tl.config.memory.embeddings.provider,
                    "model": tl.config.memory.embeddings.model,
                },
            },
            "identity": {
                "name": tl.config.identity.name,
                "system_prompt": tl.config.identity.system_prompt,
            },
            "current_model": {
                "model_id": tl.config.current_model,
                "config": current_model_config.to_dict(),
            },
            "available_models": list(tl.config.model_configs.keys()),
        }

    @app.put("/api/config")
    async def update_config(request: ConfigUpdateRequest):
        """Update configuration."""
        tl = get_threadlight()

        changes = {}

        if request.model:
            tl.config.provider.model = request.model
            changes["model"] = request.model

        if request.style_profile is not None:
            if request.style_profile == "" or request.style_profile == "none":
                tl.clear_style()
                changes["style_profile"] = None
            else:
                tl.set_style(request.style_profile)
                changes["style_profile"] = request.style_profile

        if request.enable_decay is not None:
            tl.config.memory.decay.enabled = request.enable_decay
            changes["enable_decay"] = request.enable_decay

        if request.identity_name:
            tl.set_identity_name(request.identity_name)
            changes["identity_name"] = request.identity_name

        if request.system_prompt is not None:
            tl.set_system_prompt(request.system_prompt)
            changes["system_prompt"] = True

        return {"updated": changes}

    # ========================================================================
    # Model Configuration Endpoints
    # ========================================================================

    @app.get("/api/models")
    async def list_models():
        """List available models and their configs."""
        tl = get_threadlight()

        models = tl.list_available_models()
        return {
            "models": models,
            "current_model": tl.config.current_model,
            "count": len(models),
        }

    @app.post("/api/models/switch")
    async def switch_model(request: ModelSwitchRequest):
        """Switch to a different model."""
        tl = get_threadlight()

        try:
            model_config = tl.switch_model(request.model_id)
            return {
                "status": "switched",
                "model_id": request.model_id,
                "config": model_config.to_dict(),
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/models/{model_id}/config")
    async def get_model_config(model_id: str):
        """Get config for specific model."""
        tl = get_threadlight()

        config = tl.config.get_model_config(model_id)
        is_current = model_id == tl.config.current_model

        return {
            "model_id": model_id,
            "is_current": is_current,
            "config": config.to_dict(),
        }

    @app.put("/api/models/{model_id}/config")
    async def update_model_config(model_id: str, request: ModelConfigRequest):
        """Update config for specific model (auto-saves)."""
        tl = get_threadlight()

        # Build kwargs from request
        updates = {}
        if request.system_prompt is not None:
            updates["system_prompt"] = request.system_prompt
        if request.style_profile is not None:
            updates["style_profile"] = request.style_profile if request.style_profile else None
        if request.memory_enabled is not None:
            updates["memory_enabled"] = request.memory_enabled
        if request.decay_enabled is not None:
            updates["decay_enabled"] = request.decay_enabled
        if request.temperature is not None:
            updates["temperature"] = request.temperature
        if request.max_tokens is not None:
            updates["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            updates["top_p"] = request.top_p

        # Update the config
        config = tl.config.update_model_config(model_id, **updates)

        # If this is the current model, apply the changes
        if model_id == tl.config.current_model:
            tl._apply_model_config(config)

        return {
            "status": "updated",
            "model_id": model_id,
            "config": config.to_dict(),
        }

    @app.post("/api/models/{model_id}/create")
    async def create_model_config(model_id: str, request: ModelConfigRequest):
        """Create a new model configuration."""
        tl = get_threadlight()

        config = tl.create_model_config(
            model_id=model_id,
            system_prompt=request.system_prompt,
            style_profile=request.style_profile,
            memory_enabled=request.memory_enabled if request.memory_enabled is not None else True,
            decay_enabled=request.decay_enabled if request.decay_enabled is not None else False,
            temperature=request.temperature if request.temperature is not None else 0.7,
            max_tokens=request.max_tokens,
            top_p=request.top_p if request.top_p is not None else 1.0,
        )

        return {
            "status": "created",
            "model_id": model_id,
            "config": config.to_dict(),
        }

    @app.delete("/api/models/{model_id}/config")
    async def delete_model_config(model_id: str):
        """Delete a model configuration."""
        tl = get_threadlight()

        if model_id == tl.config.current_model:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete config for current model"
            )

        success = tl.delete_model_config(model_id)
        if not success:
            raise HTTPException(status_code=404, detail="Model config not found")

        return {"status": "deleted", "model_id": model_id}

    @app.post("/api/models/{model_id}/copy-to/{target_model_id}")
    async def copy_model_config(model_id: str, target_model_id: str):
        """Copy settings from one model to another."""
        tl = get_threadlight()

        try:
            config = tl.copy_model_settings(model_id, target_model_id)
            return {
                "status": "copied",
                "source": model_id,
                "target": target_model_id,
                "config": config.to_dict(),
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/models/{model_id}/set-as-default")
    async def set_model_as_default(model_id: str):
        """Set a model's config as the default for new models."""
        tl = get_threadlight()

        tl.config.set_as_default(model_id)
        return {
            "status": "set_as_default",
            "model_id": model_id,
        }

    @app.get("/api/models/current")
    async def get_current_model():
        """Get the currently active model and its config."""
        tl = get_threadlight()

        config = tl.get_current_model_config()
        return {
            "model_id": tl.config.current_model,
            "config": config.to_dict(),
        }

    # ========================================================================
    # System Prompt / Custom Instructions Endpoints
    # ========================================================================

    @app.get("/api/config/system-prompt")
    async def get_system_prompt():
        """Get current system prompt / custom instructions."""
        tl = get_threadlight()
        return {
            "system_prompt": tl.get_system_prompt(),
            "identity_name": tl.get_identity_name(),
        }

    @app.put("/api/config/system-prompt")
    async def update_system_prompt(request: SystemPromptRequest):
        """Update system prompt / custom instructions."""
        tl = get_threadlight()
        tl.set_system_prompt(request.prompt)
        return {
            "status": "updated",
            "system_prompt": request.prompt,
        }

    # ========================================================================
    # Style Profile Management Endpoints
    # ========================================================================

    @app.get("/api/styles")
    async def list_styles():
        """List all available style profiles."""
        tl = get_threadlight()
        from threadlight.capsules.style import BUILTIN_STYLES

        profiles = tl.list_style_profiles()
        current_style = tl.get_style()

        return {
            "styles": [
                {
                    "style_id": p.style_id,
                    "tone_base": p.tone_base,
                    "permissions": p.permissions,
                    "constraints": p.constraints,
                    "vocal_motifs": p.vocal_motifs,
                    "forbidden_patterns": p.forbidden_patterns,
                    "is_builtin": p.style_id in BUILTIN_STYLES,
                    "is_active": current_style and current_style.style_id == p.style_id,
                }
                for p in profiles
            ],
            "current": current_style.style_id if current_style else None,
            "builtin_styles": list(BUILTIN_STYLES.keys()),
        }

    @app.get("/api/styles/{style_id}")
    async def get_style(style_id: str):
        """Get a specific style profile."""
        tl = get_threadlight()
        from threadlight.capsules.style import BUILTIN_STYLES

        # Check built-in first
        if style_id in BUILTIN_STYLES:
            style_def = BUILTIN_STYLES[style_id]
            return {
                "style_id": style_id,
                "tone_base": style_def["tone_base"],
                "permissions": style_def["permissions"],
                "constraints": style_def["constraints"],
                "vocal_motifs": style_def["vocal_motifs"],
                "forbidden_patterns": style_def["forbidden_patterns"],
                "is_builtin": True,
            }

        # Check custom styles
        if style_id in tl.config.custom_styles:
            custom = tl.config.custom_styles[style_id]
            return {
                "style_id": style_id,
                "tone_base": custom.tone_base,
                "permissions": custom.permissions,
                "constraints": custom.constraints,
                "vocal_motifs": custom.vocal_motifs,
                "forbidden_patterns": custom.forbidden_patterns,
                "freeform_description": getattr(custom, 'freeform_description', ''),
                "use_freeform": getattr(custom, 'use_freeform', False),
                "is_builtin": False,
            }

        # Check storage
        profile = tl.load_style_profile(style_id)
        if profile:
            return {
                "style_id": profile.style_id,
                "tone_base": profile.tone_base,
                "permissions": profile.permissions,
                "constraints": profile.constraints,
                "vocal_motifs": profile.vocal_motifs,
                "forbidden_patterns": profile.forbidden_patterns,
                "freeform_description": profile.freeform_description,
                "use_freeform": profile.use_freeform,
                "is_builtin": False,
            }

        raise HTTPException(status_code=404, detail="Style profile not found")

    @app.post("/api/styles")
    async def create_style(request: StyleProfileRequest):
        """Create a new style profile."""
        tl = get_threadlight()
        from threadlight.capsules.style import BUILTIN_STYLES

        # Can't create with builtin names
        if request.style_id in BUILTIN_STYLES:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot use built-in style name: {request.style_id}"
            )

        # Create the profile
        profile = tl.create_style_profile(
            style_id=request.style_id,
            tone_base=request.tone_base,
            permissions=request.permissions,
            constraints=request.constraints,
            vocal_motifs=request.vocal_motifs,
            forbidden_patterns=request.forbidden_patterns,
            freeform_description=request.freeform_description,
            use_freeform=request.use_freeform,
        )

        # Save to storage
        tl.save_style_profile(profile)

        return {
            "status": "created",
            "style_id": profile.style_id,
            "use_freeform": profile.use_freeform,
        }

    @app.put("/api/styles/{style_id}")
    async def update_style(style_id: str, request: StyleProfileUpdateRequest):
        """Update an existing style profile."""
        tl = get_threadlight()
        from threadlight.capsules.style import BUILTIN_STYLES

        # Can't update built-in styles
        if style_id in BUILTIN_STYLES:
            raise HTTPException(
                status_code=400,
                detail="Cannot modify built-in styles"
            )

        # Load existing profile
        profile = tl.load_style_profile(style_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Style profile not found")

        # Update fields
        if request.tone_base is not None:
            profile.tone_base = request.tone_base
        if request.permissions is not None:
            profile.permissions = request.permissions
        if request.constraints is not None:
            profile.constraints = request.constraints
        if request.vocal_motifs is not None:
            profile.vocal_motifs = request.vocal_motifs
        if request.forbidden_patterns is not None:
            profile.forbidden_patterns = request.forbidden_patterns
        if request.freeform_description is not None:
            profile.freeform_description = request.freeform_description
        if request.use_freeform is not None:
            profile.use_freeform = request.use_freeform

        # Update content dict
        profile.content = {
            "style_id": profile.style_id,
            "tone_base": profile.tone_base,
            "permissions": profile.permissions,
            "constraints": profile.constraints,
            "vocal_motifs": profile.vocal_motifs,
            "forbidden_patterns": profile.forbidden_patterns,
            "freeform_description": profile.freeform_description,
            "use_freeform": profile.use_freeform,
        }

        # Save
        tl.storage.update_capsule(profile)

        return {"status": "updated", "style_id": style_id, "use_freeform": profile.use_freeform}

    @app.delete("/api/styles/{style_id}")
    async def delete_style(style_id: str):
        """Delete a style profile."""
        tl = get_threadlight()
        from threadlight.capsules.style import BUILTIN_STYLES

        if style_id in BUILTIN_STYLES:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete built-in styles"
            )

        success = tl.delete_style_profile(style_id)
        if not success:
            raise HTTPException(status_code=404, detail="Style profile not found")

        return {"status": "deleted", "style_id": style_id}

    @app.post("/api/styles/{style_id}/activate")
    async def activate_style(style_id: str):
        """Set a style profile as active."""
        tl = get_threadlight()

        if style_id == "none" or style_id == "":
            tl.clear_style()
            return {"status": "cleared", "active_style": None}

        tl.set_style(style_id)
        current = tl.get_style()

        if current is None:
            raise HTTPException(status_code=404, detail="Style profile not found")

        return {"status": "activated", "active_style": current.style_id}

    @app.post("/api/config/save")
    async def save_config(path: Optional[str] = None):
        """Save current configuration to file."""
        tl = get_threadlight()
        try:
            saved_path = tl.save_config(path)
            return {"status": "saved", "path": saved_path}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # Import Endpoints
    # ========================================================================

    @app.post("/api/import/text")
    async def import_text(request: ImportTextRequest):
        """Import memories from text content."""
        tl = get_threadlight()

        from threadlight.import_.text_importer import ImportedMemory

        lines = request.content.strip().split('\n')
        imported = 0
        errors = 0

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            try:
                # Create an imported memory capsule
                capsule = tl.memory.create(
                    type="custom",
                    content={
                        "capsule_subtype": "imported",
                        "text": line,
                        "source": request.source_name,
                        "line_number": i,
                        "tags": request.tags or [],
                    },
                    cue_phrases=_extract_cue_phrases(line),
                    retention="normal",
                    consent_confirmed=True,
                )
                imported += 1
            except Exception as e:
                logger.warning(f"Failed to import line {i}: {e}")
                errors += 1

        return {
            "imported": imported,
            "errors": errors,
            "total_lines": len(lines),
        }

    @app.post("/api/import/file")
    async def import_file(
        file: UploadFile = File(...),
        source_name: str = Form(None),
        tags: str = Form(None),
    ):
        """Import memories from an uploaded file."""
        tl = get_threadlight()

        content = await file.read()
        text_content = content.decode('utf-8')

        source = source_name or file.filename or "uploaded-file"
        tag_list = tags.split(',') if tags else []

        # Import as text
        lines = text_content.strip().split('\n')
        imported = 0

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            try:
                tl.memory.create(
                    type="custom",
                    content={
                        "capsule_subtype": "imported",
                        "text": line,
                        "source": source,
                        "line_number": i,
                        "tags": tag_list,
                    },
                    cue_phrases=_extract_cue_phrases(line),
                    retention="normal",
                    consent_confirmed=True,
                )
                imported += 1
            except Exception:
                pass

        return {
            "filename": file.filename,
            "imported": imported,
            "total_lines": len(lines),
        }

    @app.post("/api/import/conversations")
    async def import_conversations(
        file: UploadFile = File(...),
        profile_id: str = Form(None),
    ):
        """
        Import conversations from Claude or ChatGPT exports.

        Supported formats:
        - .zip files (Claude's claude-conversations.zip or ChatGPT export)
        - .json files (conversations.json from either platform)

        The format is auto-detected from the file structure.
        If profile_id is provided, imported conversations are scoped to that profile.
        """
        import tempfile
        import os

        from threadlight.import_.claude_export import import_claude_export
        from threadlight.import_.chatgpt_export import import_chatgpt_export

        tl = get_threadlight()
        storage = tl.storage

        # Determine the profile scope for imported conversations
        profile_scope = profile_id
        profile_name = None
        if profile_scope:
            # Verify the profile exists
            profile = tl.storage.get_profile(profile_scope)
            if profile:
                profile_name = profile.name
            else:
                return {"error": f"Profile not found: {profile_scope}"}

        # Save uploaded file to temp location
        suffix = Path(file.filename).suffix if file.filename else ".zip"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Determine file type and source
            filename = file.filename or "upload"
            is_zip = suffix.lower() == ".zip"

            # Try to auto-detect the source (Claude vs ChatGPT)
            # ChatGPT exports typically have a different structure
            source_type = "unknown"

            if is_zip:
                import zipfile
                try:
                    with zipfile.ZipFile(tmp_path, 'r') as zf:
                        file_list = zf.namelist()
                        # Claude exports have projects.json, ChatGPT has model_comparisons.json
                        if any('projects.json' in f for f in file_list):
                            source_type = "claude"
                        elif any('model_comparisons.json' in f or 'user.json' in f for f in file_list):
                            source_type = "chatgpt"
                        elif any('conversations.json' in f for f in file_list):
                            # Need to peek at the structure
                            for f in file_list:
                                if 'conversations.json' in f:
                                    with zf.open(f) as conv_file:
                                        # Read first few bytes to determine format
                                        sample = conv_file.read(1000).decode('utf-8', errors='ignore')
                                        if '"chat_messages"' in sample:
                                            source_type = "claude"
                                        elif '"mapping"' in sample:
                                            source_type = "chatgpt"
                                    break
                except zipfile.BadZipFile:
                    return {"error": "Invalid zip file"}

            elif suffix.lower() == ".json":
                # Peek at the JSON structure
                try:
                    import json
                    with open(tmp_path, 'r', encoding='utf-8') as f:
                        # Read just enough to determine format
                        sample = f.read(2000)
                        if '"chat_messages"' in sample:
                            source_type = "claude"
                        elif '"mapping"' in sample:
                            source_type = "chatgpt"
                except Exception:
                    pass

            # Import based on detected type
            result = None
            if source_type == "claude":
                result = import_claude_export(
                    path=tmp_path,
                    storage=storage,
                    import_conversations=True,
                    import_projects=True,
                    create_styles=True,
                    skip_empty_conversations=True,
                    profile_scope=profile_scope,
                )
                return {
                    "success": result.success,
                    "source": "claude",
                    "conversations_imported": result.total_conversations,
                    "messages_imported": result.total_messages,
                    "projects_imported": result.total_projects,
                    "errors": result.errors,
                    "profile_scope": profile_scope,
                    "profile_name": profile_name,
                }

            elif source_type == "chatgpt":
                result = import_chatgpt_export(
                    path=tmp_path,
                    storage=storage,
                    skip_empty_conversations=True,
                    profile_scope=profile_scope,
                )
                return {
                    "success": result.success,
                    "source": "chatgpt",
                    "conversations_imported": result.total_conversations,
                    "messages_imported": result.total_messages,
                    "errors": result.errors,
                    "profile_scope": profile_scope,
                    "profile_name": profile_name,
                }

            else:
                # Try both and see which works
                # First try Claude format
                result = import_claude_export(
                    path=tmp_path,
                    storage=storage,
                    import_conversations=True,
                    import_projects=True,
                    skip_empty_conversations=True,
                    profile_scope=profile_scope,
                )

                if result.success and result.total_conversations > 0:
                    return {
                        "success": True,
                        "source": "claude",
                        "conversations_imported": result.total_conversations,
                        "messages_imported": result.total_messages,
                        "projects_imported": result.total_projects,
                        "errors": result.errors,
                        "profile_scope": profile_scope,
                        "profile_name": profile_name,
                    }

                # Try ChatGPT format
                result = import_chatgpt_export(
                    path=tmp_path,
                    storage=storage,
                    skip_empty_conversations=True,
                    profile_scope=profile_scope,
                )

                if result.success and result.total_conversations > 0:
                    return {
                        "success": True,
                        "source": "chatgpt",
                        "conversations_imported": result.total_conversations,
                        "messages_imported": result.total_messages,
                        "errors": result.errors,
                        "profile_scope": profile_scope,
                        "profile_name": profile_name,
                    }

                return {
                    "success": False,
                    "error": "Could not detect export format. Make sure the file is a valid Claude or ChatGPT export.",
                }

        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    # ========================================================================
    # Semantic Search Endpoints
    # ========================================================================

    @app.post("/api/search/semantic")
    async def semantic_search(request: SemanticSearchRequest):
        """
        Perform semantic search over memories and conversations.

        Requires embeddings to be enabled and generated.
        """
        tl = get_threadlight()

        if not tl.config.memory.embeddings.enabled:
            raise HTTPException(
                status_code=400,
                detail="Embeddings not enabled. Enable embeddings in config first."
            )

        try:
            results = []

            if request.include_memories:
                memory_results = tl.search_memories_semantic(
                    query=request.query,
                    limit=request.limit,
                    threshold=request.threshold,
                )
                results.extend([r.to_dict() for r in memory_results])

            if request.include_conversations:
                conv_results = tl.search_conversations_semantic(
                    query=request.query,
                    limit=request.limit,
                    threshold=request.threshold,
                )
                results.extend([r.to_dict() for r in conv_results])

            # Sort combined results by similarity and limit
            results.sort(key=lambda r: r.get("similarity_score", 0), reverse=True)
            results = results[:request.limit]

            return {
                "query": request.query,
                "results": results,
                "count": len(results),
            }

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/embeddings/generate")
    async def generate_embeddings(request: GenerateEmbeddingsRequest):
        """
        Generate embeddings for memories and conversations that don't have them.

        This can take a while for large datasets.
        """
        tl = get_threadlight()

        if not tl.config.memory.embeddings.enabled:
            raise HTTPException(
                status_code=400,
                detail="Embeddings not enabled. Enable embeddings in config first."
            )

        try:
            stats = tl.generate_embeddings(
                include_memories=request.include_memories,
                include_messages=request.include_conversations,
            )
            return stats.to_dict()

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/embeddings/generate/stream")
    async def generate_embeddings_stream(request: GenerateEmbeddingsRequest):
        """
        Generate embeddings with real-time progress updates via Server-Sent Events.

        Streams progress updates as JSON events:
        - type: "progress" - Periodic progress update with current stats
        - type: "complete" - Final stats when generation is complete
        - type: "error" - Error information if generation fails
        """
        tl = get_threadlight()

        if not tl.config.memory.embeddings.enabled:
            raise HTTPException(
                status_code=400,
                detail="Embeddings not enabled. Enable embeddings in config first."
            )

        # Get total counts for progress calculation
        manager = tl._get_embedding_manager()
        if manager is None:
            raise HTTPException(
                status_code=500,
                detail="Embedding manager not initialized."
            )

        # Count items to process
        total_capsules = len(manager.get_capsules_needing_embeddings()) if request.include_memories else 0
        total_messages = len(manager.get_messages_needing_embeddings()) if request.include_conversations else 0
        total_items = total_capsules + total_messages

        # Shared state for progress tracking
        progress_state = {
            "last_stats": None,
            "total_capsules": total_capsules,
            "total_messages": total_messages,
            "total_items": total_items,
        }

        async def event_generator():
            import queue
            import threading

            progress_queue: queue.Queue = queue.Queue()
            generation_complete = threading.Event()
            generation_error: list = []

            def progress_callback(stats):
                """Called by the embedding manager with progress updates."""
                progress_queue.put(stats)

            def run_generation():
                """Run the embedding generation in a background thread."""
                try:
                    final_stats = tl.generate_embeddings(
                        include_memories=request.include_memories,
                        include_messages=request.include_conversations,
                        progress_callback=progress_callback,
                    )
                    progress_queue.put(("complete", final_stats))
                except Exception as e:
                    generation_error.append(str(e))
                    progress_queue.put(("error", str(e)))
                finally:
                    generation_complete.set()

            # Start generation in background thread
            thread = threading.Thread(target=run_generation)
            thread.start()

            # Send initial progress event
            initial_data = {
                "type": "progress",
                "total_capsules": total_capsules,
                "total_messages": total_messages,
                "total_items": total_items,
                "capsules_processed": 0,
                "capsules_updated": 0,
                "messages_processed": 0,
                "messages_updated": 0,
                "percent_complete": 0,
            }
            yield f"data: {json.dumps(initial_data)}\n\n"

            # Stream progress updates
            while not generation_complete.is_set() or not progress_queue.empty():
                try:
                    item = progress_queue.get(timeout=0.1)

                    if isinstance(item, tuple):
                        event_type, data = item
                        if event_type == "complete":
                            # Final completion event
                            stats = data
                            completion_data = {
                                "type": "complete",
                                "total_capsules": total_capsules,
                                "total_messages": total_messages,
                                "total_items": total_items,
                                "capsules_processed": stats.capsules_processed,
                                "capsules_updated": stats.capsules_updated,
                                "messages_processed": stats.messages_processed,
                                "messages_updated": stats.messages_updated,
                                "errors": stats.errors,
                                "duration_seconds": stats.duration_seconds,
                                "percent_complete": 100,
                            }
                            yield f"data: {json.dumps(completion_data)}\n\n"
                        elif event_type == "error":
                            error_data = {
                                "type": "error",
                                "error": data,
                            }
                            yield f"data: {json.dumps(error_data)}\n\n"
                    else:
                        # Progress update (EmbeddingStats object)
                        stats = item
                        processed = stats.capsules_updated + stats.messages_updated
                        percent = (processed / total_items * 100) if total_items > 0 else 0

                        progress_data = {
                            "type": "progress",
                            "total_capsules": total_capsules,
                            "total_messages": total_messages,
                            "total_items": total_items,
                            "capsules_processed": stats.capsules_processed,
                            "capsules_updated": stats.capsules_updated,
                            "messages_processed": stats.messages_processed,
                            "messages_updated": stats.messages_updated,
                            "errors": stats.errors,
                            "duration_seconds": stats.duration_seconds,
                            "percent_complete": round(percent, 1),
                        }
                        yield f"data: {json.dumps(progress_data)}\n\n"

                except queue.Empty:
                    # No updates available, continue waiting
                    await asyncio.sleep(0.1)

            thread.join()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable buffering in nginx
            }
        )

    @app.get("/api/embeddings/stats")
    async def get_embedding_stats():
        """Get statistics about embedding coverage."""
        tl = get_threadlight()

        if not tl.config.memory.embeddings.enabled:
            return {
                "enabled": False,
                "message": "Embeddings not enabled in config.",
            }

        try:
            stats = tl.get_embedding_stats()
            stats["enabled"] = True
            return stats

        except Exception as e:
            logger.error(f"Failed to get embedding stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/embeddings/enable")
    async def enable_embeddings(request: EmbeddingsConfigRequest):
        """Enable or disable embeddings and configure the provider."""
        tl = get_threadlight()

        try:
            tl.config.memory.embeddings.enabled = request.enabled
            tl.config.memory.embeddings.provider = request.provider
            tl.config.memory.embeddings.model = request.model

            # Save config
            tl.save_config()

            return {
                "enabled": request.enabled,
                "provider": request.provider,
                "model": request.model,
                "message": "Embeddings configuration updated. Restart may be required for some changes.",
            }

        except Exception as e:
            logger.error(f"Failed to enable embeddings: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/embeddings")
    async def clear_embeddings():
        """
        Clear all embeddings from memories and messages.

        This is useful when switching embedding models, as embeddings from
        different models are incompatible (different dimensions/semantic spaces).
        After clearing, you'll need to regenerate embeddings with the new model.
        """
        tl = get_threadlight()

        try:
            result = tl.clear_all_embeddings()

            return {
                "status": "cleared",
                "count": result["count"],
                "capsules_cleared": result["capsules_cleared"],
                "messages_cleared": result["messages_cleared"],
                "message": f"Cleared {result['count']} embeddings ({result['capsules_cleared']} memories, {result['messages_cleared']} messages)",
            }

        except Exception as e:
            logger.error(f"Failed to clear embeddings: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # Conversation Management Endpoints
    # ========================================================================

    @app.get("/api/conversations")
    async def list_conversations_api(
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
        source: Optional[str] = None,
    ):
        """List all conversations.

        Args:
            include_archived: Include archived conversations
            limit: Maximum number to return
            offset: Pagination offset
            source: Filter by source (local, claude, chatgpt). If None, returns all sources.
        """
        tl = get_threadlight()

        conversations = tl.storage.list_conversations(
            limit=limit,
            offset=offset,
            source=source,  # None means all sources
            include_archived=include_archived,
        )

        return {
            "conversations": [c.to_dict() for c in conversations],
            "count": len(conversations),
        }

    @app.post("/api/conversations")
    async def create_conversation_api(request: ConversationCreateRequest):
        """Create a new conversation."""
        tl = get_threadlight()
        from threadlight.storage.base import Conversation
        from datetime import datetime

        # Determine model name: use provided, or active profile, or current model config
        model_name = request.model
        if not model_name:
            if tl.active_profile:
                model_name = tl.active_profile.name or tl.active_profile.primary_model
            else:
                model_name = tl.config.provider.model

        conversation = Conversation(
            id=str(uuid.uuid4()),
            name=request.name,
            source="local",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message_count=0,
            model=model_name,
        )

        tl.storage.save_conversation(conversation)

        return conversation.to_dict()

    @app.get("/api/conversations/{conversation_id}")
    async def get_conversation_api(conversation_id: str):
        """Get a conversation by ID."""
        tl = get_threadlight()

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return conversation.to_dict()

    @app.put("/api/conversations/{conversation_id}")
    async def update_conversation_api(conversation_id: str, request: ConversationUpdateRequest):
        """Update a conversation (rename, archive, etc.)."""
        tl = get_threadlight()

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if request.name is not None:
            conversation.name = request.name
        if request.archived is not None:
            conversation.archived = request.archived
        if request.model is not None:
            conversation.model = request.model

        tl.storage.update_conversation(conversation)

        return conversation.to_dict()

    @app.post("/api/conversations/{conversation_id}/archive")
    async def archive_conversation_api(conversation_id: str):
        """Archive a conversation."""
        tl = get_threadlight()

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conversation.archived = True
        tl.storage.update_conversation(conversation)

        return {"status": "archived", "id": conversation_id}

    @app.post("/api/conversations/{conversation_id}/unarchive")
    async def unarchive_conversation_api(conversation_id: str):
        """Unarchive a conversation."""
        tl = get_threadlight()

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conversation.archived = False
        tl.storage.update_conversation(conversation)

        return {"status": "unarchived", "id": conversation_id}

    @app.delete("/api/conversations/{conversation_id}")
    async def delete_conversation_api(conversation_id: str):
        """Delete a conversation and all its messages."""
        tl = get_threadlight()

        success = tl.storage.delete_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"status": "deleted", "id": conversation_id}

    @app.get("/api/conversations/{conversation_id}/messages")
    async def get_conversation_messages_api(
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ):
        """Get all messages in a conversation."""
        tl = get_threadlight()

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = tl.storage.get_messages(conversation_id, limit=limit, offset=offset)

        return {
            "messages": [m.to_dict() for m in messages],
            "count": len(messages),
            "conversation_id": conversation_id,
        }

    @app.post("/api/conversations/{conversation_id}/messages")
    async def add_message_to_conversation_api(
        conversation_id: str,
        role: str,
        content: str,
    ):
        """Add a message to a conversation."""
        tl = get_threadlight()
        from threadlight.storage.base import Message as StorageMessage
        from datetime import datetime

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        message = StorageMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            source="local",
        )

        tl.storage.save_message(message)

        # Update conversation message count and timestamp
        conversation.message_count += 1
        tl.storage.update_conversation(conversation)

        return message.to_dict()

    # ========================================================================
    # Message Management Endpoints
    # ========================================================================

    @app.get("/api/messages/{message_id}")
    async def get_message_api(message_id: str):
        """Get a single message by ID."""
        tl = get_threadlight()

        message = tl.storage.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        return message.to_dict()

    @app.put("/api/messages/{message_id}")
    async def update_message_api(message_id: str, request: MessageUpdateRequest):
        """Edit a message's content."""
        tl = get_threadlight()

        message = tl.storage.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        message.content = request.content
        tl.storage.update_message(message)

        return message.to_dict()

    @app.delete("/api/messages/{message_id}")
    async def delete_message_api(message_id: str):
        """Delete a single message."""
        tl = get_threadlight()

        message = tl.storage.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        # Update conversation message count
        conversation = tl.storage.get_conversation(message.conversation_id)
        if conversation:
            conversation.message_count = max(0, conversation.message_count - 1)
            tl.storage.update_conversation(conversation)

        tl.storage.delete_message(message_id)

        return {"status": "deleted", "id": message_id}

    @app.delete("/api/messages/{message_id}/and-after")
    async def delete_message_and_after_api(message_id: str):
        """Delete a message and all messages after it (for regeneration)."""
        tl = get_threadlight()

        message = tl.storage.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        deleted_count = tl.storage.delete_messages_after(
            message.conversation_id,
            message_id
        )

        # Update conversation message count
        conversation = tl.storage.get_conversation(message.conversation_id)
        if conversation:
            conversation.message_count = max(0, conversation.message_count - deleted_count)
            tl.storage.update_conversation(conversation)

        return {"status": "deleted", "count": deleted_count}

    # ========================================================================
    # Memory Type Management Endpoints
    # ========================================================================

    @app.get("/api/memory-types")
    async def list_memory_types(include_builtin: bool = True):
        """
        List all available memory types (built-in + custom).

        Returns both built-in types (relational, myth_seed, etc.) and
        user-defined custom types.
        """
        tl = get_threadlight()
        types = tl.list_memory_types(include_builtin=include_builtin)

        return {
            "types": types,
            "count": len(types),
            "builtin_count": sum(1 for t in types if t.get("is_builtin", False)),
            "custom_count": sum(1 for t in types if not t.get("is_builtin", False)),
        }

    @app.get("/api/memory-types/examples")
    async def list_example_types():
        """List available example types that can be imported."""
        tl = get_threadlight()
        examples = tl.list_example_types()

        return {
            "examples": examples,
            "count": len(examples),
        }

    @app.get("/api/memory-types/{type_id}")
    async def get_memory_type(type_id: str):
        """Get a specific memory type definition."""
        tl = get_threadlight()
        type_def = tl.get_memory_type(type_id)

        if type_def is None:
            raise HTTPException(status_code=404, detail=f"Memory type not found: {type_id}")

        return type_def

    @app.post("/api/memory-types")
    async def create_memory_type(request: MemoryTypeRequest):
        """
        Create a new custom memory type.

        Custom types allow you to define your own structured memory formats
        with custom fields, validation, and display templates.
        """
        tl = get_threadlight()

        # Check if type already exists
        existing = tl.get_memory_type(request.type_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Memory type already exists: {request.type_id}"
            )

        try:
            # Convert Pydantic models to dicts
            fields = [f.model_dump() for f in request.fields]

            type_def = tl.create_memory_type(
                type_id=request.type_id,
                display_name=request.display_name,
                description=request.description,
                fields=fields,
                display_template=request.display_template,
                icon=request.icon,
            )

            return {
                "status": "created",
                "type": type_def.to_dict(),
            }

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to create memory type: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.put("/api/memory-types/{type_id}")
    async def update_memory_type(type_id: str, request: MemoryTypeUpdateRequest):
        """
        Update an existing custom memory type.

        Cannot update built-in types.
        """
        tl = get_threadlight()

        # Check if it's a built-in type
        builtin_ids = ["relational", "myth_seed", "ritual", "witness", "style", "custom"]
        if type_id in builtin_ids:
            raise HTTPException(
                status_code=400,
                detail="Cannot modify built-in memory types"
            )

        try:
            # Build updates dict
            updates = {}
            if request.display_name is not None:
                updates["display_name"] = request.display_name
            if request.description is not None:
                updates["description"] = request.description
            if request.fields is not None:
                updates["fields"] = [f.model_dump() for f in request.fields]
            if request.display_template is not None:
                updates["display_template"] = request.display_template
            if request.icon is not None:
                updates["icon"] = request.icon

            success = tl.update_memory_type(type_id, **updates)

            if not success:
                raise HTTPException(
                    status_code=404,
                    detail=f"Memory type not found: {type_id}"
                )

            # Get updated type
            updated = tl.get_memory_type(type_id)

            return {
                "status": "updated",
                "type": updated,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update memory type: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/memory-types/{type_id}")
    async def delete_memory_type(type_id: str):
        """
        Delete a custom memory type.

        Cannot delete built-in types. Note that existing memories
        of this type will not be deleted.
        """
        tl = get_threadlight()

        # Check if it's a built-in type
        builtin_ids = ["relational", "myth_seed", "ritual", "witness", "style", "custom"]
        if type_id in builtin_ids:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete built-in memory types"
            )

        success = tl.delete_memory_type(type_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Memory type not found: {type_id}"
            )

        return {
            "status": "deleted",
            "type_id": type_id,
        }

    @app.post("/api/memory-types/import/{type_id}")
    async def import_example_type(type_id: str):
        """
        Import an example type definition.

        Available examples: creative_project, book_note, dream_log, location
        """
        tl = get_threadlight()

        type_def = tl.import_example_type(type_id)

        if type_def is None:
            raise HTTPException(
                status_code=404,
                detail=f"Example type not found: {type_id}. Available: creative_project, book_note, dream_log, location"
            )

        return {
            "status": "imported",
            "type": type_def.to_dict(),
        }

    # ========================================================================
    # Per-Profile Memory Isolation Endpoints
    # ========================================================================

    @app.get("/api/memory/isolation")
    async def get_memory_isolation_config():
        """Get per-profile memory isolation configuration."""
        tl = get_threadlight()

        active_profile_id = tl.active_profile.id if tl.active_profile else None
        active_profile_name = tl.active_profile.name if tl.active_profile else None

        return {
            "per_profile_isolation": tl.config.memory.per_profile_isolation,
            "default_shared": tl.config.memory.default_shared,
            "active_profile_id": active_profile_id,
            "active_profile_name": active_profile_name,
        }

    @app.put("/api/memory/isolation")
    async def update_memory_isolation_config(request: MemoryIsolationConfigRequest):
        """Update per-profile memory isolation configuration."""
        tl = get_threadlight()

        try:
            tl.set_per_profile_isolation(request.enabled)
            if request.default_shared is not None:
                tl.set_default_shared(request.default_shared)

            # Save config to persist changes
            tl.save_config()

            return {
                "status": "updated",
                "per_profile_isolation": tl.config.memory.per_profile_isolation,
                "default_shared": tl.config.memory.default_shared,
            }
        except Exception as e:
            logger.error(f"Failed to update isolation config: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/memories/{capsule_id}/share")
    async def share_memory(capsule_id: str):
        """Make a memory shared across all profiles (remove profile scope)."""
        tl = get_threadlight()

        success = tl.share_memory(capsule_id)
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")

        return {"status": "shared", "id": capsule_id, "profile_scope": None}

    @app.post("/api/memories/{capsule_id}/assign")
    async def assign_memory_to_profile(capsule_id: str, request: MemoryScopeUpdateRequest):
        """Assign a memory to a specific profile."""
        tl = get_threadlight()

        # Use profile_id if provided, fall back to model_id for backward compat
        scope_id = request.profile_id or request.model_id
        if scope_id is None:
            # If no scope provided, assign to active profile
            if tl.active_profile:
                scope_id = tl.active_profile.memory_scope or tl.active_profile.id
            else:
                raise HTTPException(status_code=400, detail="No active profile to assign to")

        success = tl.assign_memory_to_profile(capsule_id, scope_id)
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")

        return {"status": "assigned", "id": capsule_id, "profile_scope": scope_id}

    @app.post("/api/memories/{capsule_id}/copy-to-profile")
    async def copy_memory_to_profile(capsule_id: str, request: MemoryScopeUpdateRequest):
        """Copy a memory to another profile (creates a new capsule)."""
        tl = get_threadlight()

        # Use profile_id if provided, fall back to model_id for backward compat
        target_id = request.profile_id or request.model_id
        if not target_id:
            raise HTTPException(status_code=400, detail="profile_id is required")

        new_capsule = tl.copy_memory_to_profile(capsule_id, target_id)
        if not new_capsule:
            raise HTTPException(status_code=404, detail="Memory not found")

        return {
            "status": "copied",
            "original_id": capsule_id,
            "new_capsule": _capsule_to_dict(new_capsule),
        }

    @app.get("/api/memories/{capsule_id}/scope")
    async def get_memory_scope(capsule_id: str):
        """Get the profile scope of a memory."""
        tl = get_threadlight()

        capsule = tl.storage.get_capsule(capsule_id)
        if not capsule:
            raise HTTPException(status_code=404, detail="Memory not found")

        profile_scope = getattr(capsule, 'profile_scope', None)
        return {
            "id": capsule_id,
            "profile_scope": profile_scope,
            "is_shared": profile_scope is None,
        }

    @app.get("/api/profile-scope/stats")
    async def get_profile_scope_stats():
        """Get statistics about memories per profile scope."""
        tl = get_threadlight()

        # Get all capsules and count by profile_scope
        from threadlight.storage.base import CapsuleFilter
        capsules = tl.storage.list_capsules(CapsuleFilter(limit=10000))

        counts = {}
        for c in capsules:
            scope = getattr(c, 'profile_scope', None)
            counts[scope] = counts.get(scope, 0) + 1

        # Convert None key to "null" for JSON serialization
        json_counts = {}
        for key, value in counts.items():
            json_counts[str(key) if key is not None else "null"] = value

        # Get profile names for context
        profile_names = {}
        profiles = tl.list_profiles()
        for p in profiles:
            profile_names[p.id] = p.name

        return {
            "per_profile_isolation": tl.config.memory.per_profile_isolation,
            "active_profile_id": tl.active_profile.id if tl.active_profile else None,
            "active_profile_name": tl.active_profile.name if tl.active_profile else None,
            "memory_counts_by_profile": json_counts,
            "profile_names": profile_names,
            "shared_count": counts.get(None, 0),
        }

    # ========================================================================
    # Stats Endpoints
    # ========================================================================

    @app.get("/api/stats")
    async def get_stats():
        """Get system statistics."""
        tl = get_threadlight()
        return tl.stats()

    @app.get("/api/stats/memory")
    async def get_memory_stats():
        """Get memory statistics."""
        tl = get_threadlight()
        return tl.memory.stats()

    @app.post("/api/decay")
    async def run_decay():
        """Manually trigger a decay cycle."""
        tl = get_threadlight()
        result = tl.run_decay()
        return result

    # ========================================================================
    # Profile Endpoints
    # ========================================================================

    @app.get("/api/profiles")
    async def list_profiles():
        """List all profiles."""
        tl = get_threadlight()
        profiles = tl.list_profiles()
        active_id = tl.active_profile.id if tl.active_profile else None
        profile_dicts = [_profile_to_dict(p) for p in profiles]
        for p in profile_dicts:
            logger.info(f"[list_profiles] Profile {p['name']}: description={p.get('description')!r}")
        return {
            "profiles": profile_dicts,
            "active_profile_id": active_id,
        }

    @app.get("/api/profiles/active")
    async def get_active_profile():
        """Get the currently active profile."""
        tl = get_threadlight()
        profile = tl.get_active_profile()
        if not profile:
            return {"active_profile": None}
        return {"active_profile": _profile_to_dict(profile)}

    @app.post("/api/profiles")
    async def create_profile(request: ProfileCreateRequest):
        """Create a new profile."""
        tl = get_threadlight()

        # Convert model_strategy string to enum
        try:
            strategy = ModelStrategy(request.model_strategy)
        except ValueError:
            strategy = ModelStrategy.SINGLE

        profile = tl.create_profile(
            name=request.name,
            description=request.description,
            system_prompt=request.system_prompt,
            style_profile_id=request.style_profile_id,
            model_strategy=strategy,
            primary_model=request.primary_model,
            model_pool=request.model_pool,
            model_weights=request.model_weights,
            routing_rules=request.routing_rules,
            memory_scope=request.memory_scope,
            access_shared_memories=request.access_shared_memories,
            tags=request.tags,
            philosophy=request.philosophy,
            approach_to_rituals=request.approach_to_rituals,
        )

        return {
            "status": "created",
            "profile": _profile_to_dict(profile),
        }

    @app.get("/api/profiles/{profile_id}")
    async def get_profile(profile_id: str):
        """Get a profile by ID."""
        tl = get_threadlight()
        profile = tl.get_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return _profile_to_dict(profile)

    @app.put("/api/profiles/{profile_id}")
    async def update_profile(profile_id: str, request: ProfileUpdateRequest):
        """Update a profile."""
        logger.info(f"[update_profile] Updating profile {profile_id}")
        logger.info(f"[update_profile] Request description: {request.description!r}")
        tl = get_threadlight()

        # Build update dict from non-None fields
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.description is not None:
            updates["description"] = request.description
        if request.system_prompt is not None:
            updates["system_prompt"] = request.system_prompt
        if request.style_profile_id is not None:
            updates["style_profile_id"] = request.style_profile_id
        if request.model_strategy is not None:
            try:
                updates["model_strategy"] = ModelStrategy(request.model_strategy)
            except ValueError:
                pass
        if request.primary_model is not None:
            updates["primary_model"] = request.primary_model
        if request.model_pool is not None:
            updates["model_pool"] = request.model_pool
        if request.model_weights is not None:
            updates["model_weights"] = request.model_weights
        if request.routing_rules is not None:
            updates["routing_rules"] = request.routing_rules
        if request.memory_scope is not None:
            updates["memory_scope"] = request.memory_scope
        if request.access_shared_memories is not None:
            updates["access_shared_memories"] = request.access_shared_memories
        if request.is_active is not None:
            updates["is_active"] = request.is_active
        if request.tags is not None:
            updates["tags"] = request.tags
        if request.philosophy is not None:
            updates["philosophy"] = request.philosophy
        if request.approach_to_rituals is not None:
            updates["approach_to_rituals"] = request.approach_to_rituals

        logger.info(f"[update_profile] Updates dict: {updates}")
        profile = tl.update_profile(profile_id, **updates)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        logger.info(f"[update_profile] Updated profile description: {profile.description!r}")
        result = _profile_to_dict(profile)
        logger.info(f"[update_profile] Returning profile dict with description: {result.get('description')!r}")
        return {
            "status": "updated",
            "profile": result,
        }

    @app.delete("/api/profiles/{profile_id}")
    async def delete_profile(profile_id: str):
        """Delete a profile."""
        tl = get_threadlight()

        # Prevent deleting active profile
        if tl.active_profile and tl.active_profile.id == profile_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the currently active profile. Switch to a different profile first."
            )

        success = tl.delete_profile(profile_id)
        if not success:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {"status": "deleted", "profile_id": profile_id}

    @app.post("/api/profiles/{profile_id}/switch")
    async def switch_profile(profile_id: str):
        """Switch to a profile."""
        tl = get_threadlight()

        profile = tl.switch_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {
            "status": "switched",
            "profile": _profile_to_dict(profile),
        }

    @app.post("/api/profiles/clear")
    async def clear_profile():
        """Clear the active profile (return to default)."""
        tl = get_threadlight()
        tl.clear_profile()
        return {"status": "cleared", "active_profile_id": None}

    @app.get("/api/profiles/{profile_id}/export")
    async def export_profile(profile_id: str):
        """Export a profile as JSON."""
        tl = get_threadlight()

        data = tl.export_profile(profile_id)
        if not data:
            raise HTTPException(status_code=404, detail="Profile not found")

        return data

    @app.post("/api/profiles/import")
    async def import_profile(request: ProfileImportRequest):
        """Import a profile from JSON."""
        tl = get_threadlight()

        try:
            profile = tl.import_profile(request.data)
            return {
                "status": "imported",
                "profile": _profile_to_dict(profile),
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Import failed: {str(e)}")

    return app


# ============================================================================
# Helper Functions
# ============================================================================

def _capsule_to_dict(capsule) -> dict[str, Any]:
    """Convert a capsule to a dictionary for API responses."""
    base = capsule.to_dict()

    # Add type-specific fields
    if hasattr(capsule, 'entity'):
        base['entity'] = capsule.entity
    if hasattr(capsule, 'seed'):
        base['seed'] = capsule.seed
    if hasattr(capsule, 'name') and capsule.type == CapsuleType.RITUAL:
        base['name'] = capsule.name
    if hasattr(capsule, 'text'):
        base['text'] = capsule.text

    # Add a preview field
    base['preview'] = _get_capsule_preview(capsule)

    return base


def _get_capsule_preview(capsule) -> str:
    """Get a human-readable preview of a capsule's content."""
    if hasattr(capsule, 'text') and capsule.content.get('capsule_subtype') == 'imported':
        return capsule.text[:100] + ("..." if len(capsule.text) > 100 else "")
    elif hasattr(capsule, 'entity'):
        summary = getattr(capsule, 'summary', '')
        return f"{capsule.entity}: {summary[:50]}" if summary else capsule.entity
    elif hasattr(capsule, 'seed'):
        return capsule.seed[:80] + ("..." if len(capsule.seed) > 80 else "")
    elif hasattr(capsule, 'name') and capsule.type == CapsuleType.RITUAL:
        desc = getattr(capsule, 'description', '')
        return f"{capsule.name}: {desc[:50]}" if desc else capsule.name
    else:
        content_str = str(capsule.content)
        return content_str[:80] + ("..." if len(content_str) > 80 else "")


def _extract_cue_phrases(text: str, max_phrases: int = 5) -> list[str]:
    """Extract potential cue phrases from text."""
    words = text.lower().split()
    # Filter to meaningful words (length > 3, not common words)
    common_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'were', 'they', 'with', 'this', 'that', 'from', 'will', 'would', 'could', 'should', 'what', 'when', 'where', 'which', 'their', 'there', 'these', 'those', 'about'}
    meaningful = [w for w in words if len(w) > 3 and w not in common_words]
    return meaningful[:max_phrases]


def _profile_to_dict(profile: Profile) -> dict[str, Any]:
    """Convert a Profile to a dictionary for API responses."""
    # Get model_weights from alloyed_config if available
    model_weights = None
    routing_rules = []
    if profile.alloyed_config:
        model_weights = profile.alloyed_config.weights
        routing_rules = [r.to_dict() if hasattr(r, 'to_dict') else r for r in (profile.alloyed_config.routing_rules or [])]

    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "system_prompt": profile.system_prompt,
        "style_profile_id": profile.style_profile_id,
        "model_strategy": profile.model_strategy.value if profile.model_strategy else "single",
        "primary_model": profile.primary_model,
        "model_pool": profile.model_pool,
        "model_weights": model_weights,
        "routing_rules": routing_rules,
        "memory_scope": profile.memory_scope,
        "access_shared_memories": profile.access_shared_memories,
        "is_active": getattr(profile, 'is_active', False),
        "tags": getattr(profile, 'tags', []),
        "philosophy": getattr(profile, 'philosophy', ""),
        "approach_to_rituals": getattr(profile, 'approach_to_rituals', ""),
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }
