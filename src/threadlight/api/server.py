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


class CapsuleUpdateRequest(BaseModel):
    content: Optional[dict[str, Any]] = None
    cue_phrases: Optional[list[str]] = None
    retention: Optional[str] = None


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
    tone_base: str
    permissions: Optional[list[str]] = None
    constraints: Optional[list[str]] = None
    vocal_motifs: Optional[list[str]] = None
    forbidden_patterns: Optional[list[str]] = None


class StyleProfileUpdateRequest(BaseModel):
    tone_base: Optional[str] = None
    permissions: Optional[list[str]] = None
    constraints: Optional[list[str]] = None
    vocal_motifs: Optional[list[str]] = None
    forbidden_patterns: Optional[list[str]] = None


class ImportTextRequest(BaseModel):
    content: str
    source_name: str = "web-import"
    tags: Optional[list[str]] = None


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
    ):
        """List memory capsules with optional filtering."""
        tl = get_threadlight()

        from threadlight.storage.base import CapsuleFilter

        capsule_type = CapsuleType(type) if type else None

        filter = CapsuleFilter(
            type=capsule_type,
            limit=limit,
            offset=offset,
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
        """Create a new memory capsule."""
        tl = get_threadlight()

        try:
            capsule = tl.memory.create(
                type=request.type,
                content=request.content,
                cue_phrases=request.cue_phrases,
                retention=request.retention,
                consent_confirmed=True,
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
            },
            "identity": {
                "name": tl.config.identity.name,
                "system_prompt": tl.config.identity.system_prompt,
            },
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
        )

        # Save to storage
        tl.save_style_profile(profile)

        return {
            "status": "created",
            "style_id": profile.style_id,
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

        # Update content dict
        profile.content = {
            "style_id": profile.style_id,
            "tone_base": profile.tone_base,
            "permissions": profile.permissions,
            "constraints": profile.constraints,
            "vocal_motifs": profile.vocal_motifs,
            "forbidden_patterns": profile.forbidden_patterns,
        }

        # Save
        tl.storage.update_capsule(profile)

        return {"status": "updated", "style_id": style_id}

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
