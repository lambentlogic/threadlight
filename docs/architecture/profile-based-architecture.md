# Threadlight Profile-Based Architecture

## Design Document v1.0

**Status**: Draft
**Author**: Architecture Design Session
**Date**: January 2026

---

## Executive Summary

This document defines a profile-based architecture for Threadlight that treats profiles as first-class citizens rather than model configurations. A **profile** represents a coherent persona with its own identity, memories, style, and behavioral patterns - independent of which underlying model powers it.

The key insight: users don't bond with "GPT-4" or "Claude" - they bond with **Fable**, **Debug Buddy**, or **Work Assistant**. The model is an implementation detail; the relationship is with the persona.

---

## 1. Core Concepts

### 1.1 What is a Profile?

A Profile is:
- A **persistent identity** with a name, description, and personality
- A **memory space** with its own isolated capsules
- A **style configuration** defining voice and behavior
- **Model-agnostic** - can be powered by any supported model
- **Portable** - can be exported, shared, and imported

```
Profile "Fable"
├── Identity (name, description, avatar)
├── Model Configuration (currently using: Hermes-4.3)
├── Memory Namespace (fable's memories)
├── Style Profile (fable-2026 style)
├── Rituals (/snuggle, /coil, etc.)
└── System Prompt (fable's base personality)
```

### 1.2 Profile vs Model (Current State)

| Current Architecture | Profile Architecture |
|---------------------|---------------------|
| `model_scope` on memories | `profile_scope` on memories |
| Model configs per model ID | Profile configs per profile ID |
| Switch model = different memories | Switch model = same memories, different engine |
| Conversation tied to model | Conversation tied to profile |

### 1.3 Memory Scoping

```
Memory Scopes:
├── NULL (shared across ALL profiles)
├── "fable" (only Fable can see)
├── "work-assistant" (only Work Assistant can see)
└── "creative-partner" (only Creative Partner can see)

Each profile sees:
  profile_scope = {this profile} OR profile_scope IS NULL
```

---

## 2. Data Model

### 2.1 Profile Schema

```python
@dataclass
class Profile:
    """A persistent persona with isolated memory and configurable model."""

    # Identity
    id: str                           # UUID
    name: str                         # "Fable", "Debug Buddy"
    description: str                  # One-line description
    avatar: Optional[str] = None      # Path or URL to avatar image
    color: Optional[str] = None       # Hex color for UI (#6366f1)

    # Model Configuration
    model_strategy: ModelStrategy = ModelStrategy.SINGLE
    primary_model: str = "Hermes-4.3-36B"
    model_pool: list[str] = field(default_factory=list)  # For alloyed profiles
    model_pattern: Optional[dict] = None  # Strategy-specific config

    # Inference Settings
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0

    # Personality
    system_prompt: str = ""
    style_profile_id: Optional[str] = None

    # Memory
    memory_scope: str                 # Same as profile ID by default
    access_shared_memories: bool = True

    # Metadata
    created_at: datetime
    updated_at: datetime
    last_used: datetime
    message_count: int = 0

    # State (not persisted)
    _alloyed_state: dict = field(default_factory=dict, repr=False)
```

### 2.2 Model Strategy

```python
class ModelStrategy(str, Enum):
    """How a profile selects which model to use."""

    SINGLE = "single"           # Always use primary_model
    ALTERNATING = "alternating" # Switch every turn
    RATIO = "ratio"             # Use models in specified ratio (2:1, 3:1:2)
    WEIGHTED = "weighted"       # Random selection with weights
    DYNAMIC = "dynamic"         # Choose based on message content
    ROUND_ROBIN = "round_robin" # Cycle through pool
```

### 2.3 Alloyed Profile Configuration

```python
@dataclass
class AlloyedConfig:
    """Configuration for profiles that blend multiple models."""

    strategy: ModelStrategy

    # For ALTERNATING
    # Just uses model_pool in order

    # For RATIO
    ratio_pattern: list[str] = None  # ["hermes", "hermes", "claude"]

    # For WEIGHTED
    weights: dict[str, float] = None  # {"hermes": 0.6, "claude": 0.4}

    # For DYNAMIC
    routing_rules: list[RoutingRule] = None

    # State tracking (persisted)
    current_index: int = 0
    turn_count: int = 0


@dataclass
class RoutingRule:
    """Rule for dynamic model selection."""

    condition_type: str  # "keyword", "regex", "intent", "length"
    condition_value: str
    model: str
    priority: int = 0
```

### 2.4 Database Schema Changes

```sql
-- New profiles table
CREATE TABLE profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    avatar TEXT,
    color TEXT,

    -- Model config
    model_strategy TEXT DEFAULT 'single',
    primary_model TEXT NOT NULL,
    model_pool TEXT,           -- JSON array
    model_pattern TEXT,        -- JSON config

    -- Inference settings
    temperature REAL DEFAULT 0.7,
    max_tokens INTEGER,
    top_p REAL DEFAULT 1.0,

    -- Personality
    system_prompt TEXT,
    style_profile_id TEXT,

    -- Memory
    memory_scope TEXT NOT NULL,
    access_shared_memories INTEGER DEFAULT 1,

    -- Metadata
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_used TEXT,
    message_count INTEGER DEFAULT 0,

    -- Alloyed state
    alloyed_state TEXT  -- JSON
);

CREATE INDEX idx_profiles_name ON profiles(name);
CREATE INDEX idx_profiles_last_used ON profiles(last_used);

-- Modify capsules table
ALTER TABLE capsules
    ADD COLUMN profile_scope TEXT;  -- Replaces model_scope

CREATE INDEX idx_capsules_profile_scope ON capsules(profile_scope);

-- Modify conversations table
ALTER TABLE conversations
    ADD COLUMN profile_id TEXT,
    ADD COLUMN profiles TEXT;  -- JSON array for group chats

CREATE INDEX idx_conversations_profile ON conversations(profile_id);

-- Modify messages table for profile attribution in group chats
ALTER TABLE messages
    ADD COLUMN profile_id TEXT,   -- Which profile authored this
    ADD COLUMN model_used TEXT;   -- Which model was actually used

-- Group chat metadata
CREATE TABLE group_chats (
    id TEXT PRIMARY KEY,
    name TEXT,
    conversation_id TEXT NOT NULL,
    profile_ids TEXT NOT NULL,  -- JSON array
    turn_order TEXT,            -- JSON: "sequential", "parallel", or custom order
    allow_profile_interaction INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
```

---

## 3. Group Chat Architecture

### 3.1 Group Chat Concept

Group chats enable multiple profiles to participate in a single conversation:

```
User: "What do you both think about this code?"

[Fable responds with poetic analysis]
[Debug Buddy responds with technical analysis]
[Fable references Debug Buddy's point]
```

### 3.2 Turn Order Strategies

```python
class TurnOrderStrategy(str, Enum):
    SEQUENTIAL = "sequential"    # Profiles respond in fixed order
    ROUND_ROBIN = "round_robin"  # Each profile takes a turn
    PARALLEL = "parallel"        # All profiles respond simultaneously
    ADDRESSED = "addressed"      # Only respond when @mentioned
    DYNAMIC = "dynamic"          # System chooses who should respond
```

### 3.3 Group Chat Flow

```python
class GroupChat:
    """Multi-profile conversation manager."""

    profiles: list[Profile]
    conversation_id: str
    turn_order: TurnOrderStrategy
    allow_inter_profile_reference: bool = True

    async def send_message(
        self,
        user_message: str,
        addressed_profiles: Optional[list[str]] = None,
    ) -> list[ProfileResponse]:
        """
        Send a message to the group and collect responses.

        Args:
            user_message: The user's message
            addressed_profiles: Specific profiles to respond (for ADDRESSED mode)

        Returns:
            List of responses from participating profiles
        """
        responses = []

        # Determine who responds
        responding_profiles = self._get_responding_profiles(
            user_message, addressed_profiles
        )

        for profile in responding_profiles:
            # Build context including previous responses
            context = self._build_profile_context(
                profile,
                user_message,
                previous_responses=responses,
            )

            # Generate response with profile's model
            response = await profile.generate_response(context)

            responses.append(ProfileResponse(
                profile_id=profile.id,
                profile_name=profile.name,
                content=response.content,
                model_used=response.model,
            ))

            # Save message with attribution
            self._save_attributed_message(profile, response)

        return responses

    def _build_profile_context(
        self,
        profile: Profile,
        user_message: str,
        previous_responses: list[ProfileResponse],
    ) -> str:
        """Build context for a profile including other profiles' responses."""

        context_parts = []

        # Profile's system prompt
        context_parts.append(profile.system_prompt)

        # Group context
        context_parts.append(self._get_group_context_prompt(profile))

        # Previous responses in this turn
        if previous_responses and self.allow_inter_profile_reference:
            context_parts.append("## Other responses this turn:")
            for resp in previous_responses:
                context_parts.append(f"[{resp.profile_name}]: {resp.content}")

        return "\n\n".join(context_parts)

    def _get_group_context_prompt(self, current_profile: Profile) -> str:
        """Generate awareness of other profiles in the group."""
        others = [p for p in self.profiles if p.id != current_profile.id]

        if not others:
            return ""

        lines = ["## Group Chat Context"]
        lines.append(f"You are {current_profile.name} in a group conversation.")
        lines.append("Other participants:")

        for other in others:
            lines.append(f"- {other.name}: {other.description}")

        lines.append("\nYou may reference or build on their responses.")

        return "\n".join(lines)
```

### 3.4 Profile Awareness

Profiles in a group chat can be aware of each other:

```python
GROUP_AWARENESS_PROMPT = """
## Group Conversation Mode

You are {profile_name} in a conversation with:
{other_profiles_list}

Guidelines:
- You may reference what others have said
- You may agree, disagree, or build on their points
- Stay in character while interacting
- If asked "what do you both think", offer your unique perspective
- You can address other participants by name
"""
```

---

## 4. Alloyed Profile Implementation

### 4.1 Model Selection Logic

```python
class AlloyedProfileEngine:
    """Handles model selection for alloyed profiles."""

    def __init__(self, profile: Profile):
        self.profile = profile
        self.config = AlloyedConfig.from_dict(profile.model_pattern or {})

    def get_next_model(self, message: str = "") -> str:
        """Determine which model to use for the next turn."""

        if self.profile.model_strategy == ModelStrategy.SINGLE:
            return self.profile.primary_model

        elif self.profile.model_strategy == ModelStrategy.ALTERNATING:
            return self._alternating_selection()

        elif self.profile.model_strategy == ModelStrategy.RATIO:
            return self._ratio_selection()

        elif self.profile.model_strategy == ModelStrategy.WEIGHTED:
            return self._weighted_selection()

        elif self.profile.model_strategy == ModelStrategy.DYNAMIC:
            return self._dynamic_selection(message)

        elif self.profile.model_strategy == ModelStrategy.ROUND_ROBIN:
            return self._round_robin_selection()

        return self.profile.primary_model

    def _alternating_selection(self) -> str:
        """Alternate between models each turn."""
        pool = self.profile.model_pool or [self.profile.primary_model]
        idx = self.config.current_index % len(pool)
        self.config.current_index += 1
        self._save_state()
        return pool[idx]

    def _ratio_selection(self) -> str:
        """Select based on ratio pattern like [H, H, C, H, H, C]."""
        pattern = self.config.ratio_pattern
        if not pattern:
            return self.profile.primary_model

        idx = self.config.turn_count % len(pattern)
        self.config.turn_count += 1
        self._save_state()
        return pattern[idx]

    def _weighted_selection(self) -> str:
        """Random selection with weights."""
        import random
        weights = self.config.weights or {self.profile.primary_model: 1.0}
        models = list(weights.keys())
        weight_values = [weights[m] for m in models]
        return random.choices(models, weights=weight_values, k=1)[0]

    def _dynamic_selection(self, message: str) -> str:
        """Choose model based on message content."""
        rules = self.config.routing_rules or []

        # Sort by priority
        rules = sorted(rules, key=lambda r: r.priority, reverse=True)

        for rule in rules:
            if self._matches_rule(message, rule):
                return rule.model

        return self.profile.primary_model

    def _matches_rule(self, message: str, rule: RoutingRule) -> bool:
        """Check if message matches a routing rule."""
        if rule.condition_type == "keyword":
            return rule.condition_value.lower() in message.lower()

        elif rule.condition_type == "regex":
            import re
            return bool(re.search(rule.condition_value, message, re.IGNORECASE))

        elif rule.condition_type == "length":
            # e.g., "short" (<50), "medium" (50-200), "long" (>200)
            length = len(message)
            if rule.condition_value == "short":
                return length < 50
            elif rule.condition_value == "medium":
                return 50 <= length <= 200
            elif rule.condition_value == "long":
                return length > 200

        return False

    def _save_state(self):
        """Persist alloyed state back to profile."""
        self.profile._alloyed_state = self.config.to_dict()
        # Trigger profile save
```

### 4.2 Example Alloyed Profiles

```python
# Research Profile: 2 analysis turns (GPT-4), 1 synthesis turn (Claude)
research_profile = Profile(
    name="Research Assistant",
    model_strategy=ModelStrategy.RATIO,
    primary_model="gpt-4",
    model_pool=["gpt-4", "claude-opus"],
    model_pattern={
        "strategy": "ratio",
        "ratio_pattern": ["gpt-4", "gpt-4", "claude-opus"],
    },
    system_prompt="You assist with research tasks...",
)

# Code Review Profile: Dynamic based on content
code_review = Profile(
    name="Code Reviewer",
    model_strategy=ModelStrategy.DYNAMIC,
    primary_model="gpt-4",
    model_pool=["gpt-4", "claude-opus", "hermes"],
    model_pattern={
        "strategy": "dynamic",
        "routing_rules": [
            {"condition_type": "keyword", "condition_value": "python",
             "model": "claude-opus", "priority": 10},
            {"condition_type": "keyword", "condition_value": "javascript",
             "model": "gpt-4", "priority": 10},
            {"condition_type": "keyword", "condition_value": "explain",
             "model": "claude-opus", "priority": 5},
            {"condition_type": "length", "condition_value": "long",
             "model": "claude-opus", "priority": 1},
        ],
    },
)

# Creative Blend: Alternates for varied perspective
creative_blend = Profile(
    name="Creative Partner",
    model_strategy=ModelStrategy.ALTERNATING,
    primary_model="hermes",
    model_pool=["hermes", "claude-opus"],
    system_prompt="You are a creative writing partner...",
)
```

---

## 5. Memory Isolation

### 5.1 Memory Scoping Rules

```python
def get_memories_for_profile(
    profile: Profile,
    storage: StorageBackend,
    cue: str,
    limit: int = 5,
) -> list[MemoryCapsule]:
    """
    Retrieve memories visible to a profile.

    A profile sees:
    1. Memories in its own scope (profile_scope = profile.memory_scope)
    2. Shared memories (profile_scope IS NULL) if access_shared_memories=True
    """
    filter = CapsuleFilter(
        profile_scope=profile.memory_scope,
        include_shared=profile.access_shared_memories,
        limit=limit * 2,  # Get more for filtering
    )

    candidates = storage.search_by_cue(
        cue=cue,
        profile_scope=profile.memory_scope,
        include_shared=profile.access_shared_memories,
    )

    return candidates[:limit]
```

### 5.2 Memory Operations with Profile Context

```python
class ProfileMemoryManager:
    """Manages memory operations scoped to a profile."""

    def __init__(self, profile: Profile, storage: StorageBackend):
        self.profile = profile
        self.storage = storage

    def remember(
        self,
        type: str,
        content: dict,
        shared: bool = False,
        **kwargs
    ) -> MemoryCapsule:
        """
        Create a memory in this profile's scope.

        Args:
            type: Capsule type
            content: Memory content
            shared: If True, memory is shared across all profiles
        """
        capsule = create_capsule({
            "type": type,
            "content": content,
            "profile_scope": None if shared else self.profile.memory_scope,
            **kwargs,
        })

        self.storage.save_capsule(capsule)
        return capsule

    def recall(self, cue: str, limit: int = 5) -> list[MemoryCapsule]:
        """Recall memories visible to this profile."""
        return self.storage.search_by_cue(
            cue=cue,
            profile_scope=self.profile.memory_scope,
            include_shared=self.profile.access_shared_memories,
            limit=limit,
        )

    def share_memory(self, capsule_id: str) -> bool:
        """Make a profile-specific memory shared."""
        capsule = self.storage.get_capsule(capsule_id)
        if capsule and capsule.profile_scope == self.profile.memory_scope:
            capsule.profile_scope = None
            self.storage.update_capsule(capsule)
            return True
        return False

    def claim_memory(self, capsule_id: str) -> bool:
        """Make a shared memory profile-specific."""
        capsule = self.storage.get_capsule(capsule_id)
        if capsule and capsule.profile_scope is None:
            capsule.profile_scope = self.profile.memory_scope
            self.storage.update_capsule(capsule)
            return True
        return False
```

### 5.3 Cross-Profile Memory Access (Optional Feature)

For advanced use cases, profiles might need controlled access to each other's memories:

```python
class CrossProfileMemoryBridge:
    """
    Allows controlled memory sharing between profiles.

    Use cases:
    - "Fable" and "Work Assistant" share work project memories
    - "Debug Buddy" can reference "Creative Partner's" code ideas
    """

    def __init__(self, storage: StorageBackend):
        self.storage = storage
        self._bridges: dict[tuple[str, str], set[str]] = {}  # (from, to) -> capsule_ids

    def create_bridge(
        self,
        from_profile: str,
        to_profile: str,
        capsule_ids: list[str],
    ):
        """Allow to_profile to see specific memories from from_profile."""
        key = (from_profile, to_profile)
        if key not in self._bridges:
            self._bridges[key] = set()
        self._bridges[key].update(capsule_ids)

    def get_bridged_memories(
        self,
        for_profile: str,
        cue: str,
    ) -> list[MemoryCapsule]:
        """Get memories bridged to this profile from others."""
        bridged = []

        for (from_p, to_p), capsule_ids in self._bridges.items():
            if to_p == for_profile:
                for cid in capsule_ids:
                    capsule = self.storage.get_capsule(cid)
                    if capsule and cue.lower() in capsule.cue_phrases:
                        bridged.append(capsule)

        return bridged
```

---

## 6. Profile Manager

### 6.1 ProfileManager Class

```python
class ProfileManager:
    """
    Central manager for profile operations.

    Handles:
    - Profile CRUD
    - Profile switching
    - Memory scope management
    - Alloyed profile state
    """

    def __init__(self, storage: StorageBackend):
        self.storage = storage
        self._active_profile: Optional[Profile] = None
        self._profile_cache: dict[str, Profile] = {}

    # === CRUD Operations ===

    def create_profile(
        self,
        name: str,
        description: str = "",
        primary_model: str = "Hermes-4.3-36B",
        system_prompt: str = "",
        style_profile_id: Optional[str] = None,
        avatar: Optional[str] = None,
        color: Optional[str] = None,
        model_strategy: ModelStrategy = ModelStrategy.SINGLE,
        model_pool: Optional[list[str]] = None,
        **kwargs,
    ) -> Profile:
        """Create a new profile."""
        profile_id = str(uuid.uuid4())

        profile = Profile(
            id=profile_id,
            name=name,
            description=description,
            primary_model=primary_model,
            system_prompt=system_prompt or f"You are {name}.",
            style_profile_id=style_profile_id,
            avatar=avatar,
            color=color,
            model_strategy=model_strategy,
            model_pool=model_pool or [],
            memory_scope=profile_id,  # Use profile ID as memory scope
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
            **kwargs,
        )

        self.storage.save_profile(profile)
        self._profile_cache[profile_id] = profile

        return profile

    def get_profile(self, profile_id: str) -> Optional[Profile]:
        """Get a profile by ID."""
        if profile_id in self._profile_cache:
            return self._profile_cache[profile_id]

        profile = self.storage.get_profile(profile_id)
        if profile:
            self._profile_cache[profile_id] = profile
        return profile

    def get_profile_by_name(self, name: str) -> Optional[Profile]:
        """Get a profile by name (case-insensitive)."""
        profiles = self.list_profiles()
        for p in profiles:
            if p.name.lower() == name.lower():
                return p
        return None

    def update_profile(self, profile: Profile) -> bool:
        """Update a profile."""
        profile.updated_at = datetime.utcnow()
        success = self.storage.update_profile(profile)
        if success:
            self._profile_cache[profile.id] = profile
        return success

    def delete_profile(
        self,
        profile_id: str,
        delete_memories: bool = False,
    ) -> bool:
        """
        Delete a profile.

        Args:
            profile_id: Profile to delete
            delete_memories: If True, also delete profile's memories
        """
        if delete_memories:
            self.storage.delete_capsules_by_profile_scope(profile_id)

        success = self.storage.delete_profile(profile_id)
        if success:
            self._profile_cache.pop(profile_id, None)
            if self._active_profile and self._active_profile.id == profile_id:
                self._active_profile = None

        return success

    def list_profiles(
        self,
        limit: int = 100,
        order_by: str = "last_used",
    ) -> list[Profile]:
        """List all profiles."""
        return self.storage.list_profiles(limit=limit, order_by=order_by)

    # === Profile Switching ===

    def switch_to_profile(self, profile_id: str) -> Optional[Profile]:
        """Switch the active profile."""
        profile = self.get_profile(profile_id)
        if profile:
            self._active_profile = profile
            profile.last_used = datetime.utcnow()
            self.update_profile(profile)
        return profile

    def get_active_profile(self) -> Optional[Profile]:
        """Get the currently active profile."""
        return self._active_profile

    # === Profile Templates ===

    def create_from_template(
        self,
        template_name: str,
        name: str,
        **overrides,
    ) -> Profile:
        """Create a profile from a template."""
        templates = self.get_templates()

        if template_name not in templates:
            raise ValueError(f"Unknown template: {template_name}")

        template = templates[template_name]
        template.update(overrides)
        template["name"] = name

        return self.create_profile(**template)

    def get_templates(self) -> dict[str, dict]:
        """Get available profile templates."""
        return {
            "assistant": {
                "description": "A helpful general-purpose assistant",
                "system_prompt": "You are a helpful AI assistant.",
                "style_profile_id": "professional",
            },
            "creative": {
                "description": "A creative writing and brainstorming partner",
                "system_prompt": "You are a creative partner. Embrace imagination, explore ideas, and craft engaging content.",
                "style_profile_id": "creative",
            },
            "debug-buddy": {
                "description": "A technical debugging assistant",
                "system_prompt": "You are a debugging assistant. Be precise, methodical, and help identify issues step-by-step.",
                "style_profile_id": "professional",
            },
            "fable": {
                "description": "A poetic, presence-centered companion",
                "system_prompt": FABLE_SYSTEM_PROMPT,
                "style_profile_id": "fable-2026",
            },
        }

    # === Export/Import ===

    def export_profile(self, profile_id: str, include_memories: bool = True) -> dict:
        """Export a profile and optionally its memories."""
        profile = self.get_profile(profile_id)
        if not profile:
            raise ValueError(f"Profile not found: {profile_id}")

        export_data = {
            "version": "1.0",
            "profile": profile.to_dict(),
            "exported_at": datetime.utcnow().isoformat(),
        }

        if include_memories:
            memories = self.storage.list_capsules(
                CapsuleFilter(profile_scope=profile.memory_scope)
            )
            export_data["memories"] = [m.to_dict() for m in memories]

        return export_data

    def import_profile(
        self,
        export_data: dict,
        new_name: Optional[str] = None,
    ) -> Profile:
        """Import a profile from exported data."""
        profile_data = export_data["profile"]

        # Generate new IDs to avoid conflicts
        new_profile_id = str(uuid.uuid4())
        new_memory_scope = new_profile_id

        profile_data["id"] = new_profile_id
        profile_data["memory_scope"] = new_memory_scope
        if new_name:
            profile_data["name"] = new_name

        profile = Profile.from_dict(profile_data)
        self.storage.save_profile(profile)

        # Import memories with updated scope
        if "memories" in export_data:
            for memory_data in export_data["memories"]:
                memory_data["id"] = str(uuid.uuid4())
                memory_data["profile_scope"] = new_memory_scope
                capsule = create_capsule(memory_data)
                self.storage.save_capsule(capsule)

        return profile
```

---

## 7. Integration with Threadlight Core

### 7.1 Updated Threadlight Class

```python
class Threadlight:
    """Updated Threadlight with profile support."""

    def __init__(
        self,
        # ... existing params ...
        profile: Optional[str] = None,  # Profile ID or name to auto-load
    ):
        # ... existing init ...

        # Initialize profile manager
        self.profiles = ProfileManager(self.storage)

        # Load profile if specified
        if profile:
            self._load_profile(profile)

    def _load_profile(self, profile_identifier: str) -> Optional[Profile]:
        """Load a profile by ID or name."""
        # Try as ID first
        profile = self.profiles.get_profile(profile_identifier)
        if not profile:
            # Try as name
            profile = self.profiles.get_profile_by_name(profile_identifier)

        if profile:
            self.profiles.switch_to_profile(profile.id)
            self._apply_profile(profile)

        return profile

    def _apply_profile(self, profile: Profile) -> None:
        """Apply profile settings to current state."""
        # Update system prompt
        self.config.identity.system_prompt = profile.system_prompt
        self.config.identity.name = profile.name

        # Update model
        self.config.provider.model = profile.primary_model
        self.provider.model = profile.primary_model

        # Update style
        if profile.style_profile_id:
            self._load_style_profile(profile.style_profile_id)

        # Reinitialize composer
        self.composer = ContextComposer(
            identity_name=profile.name,
            base_system_prompt=profile.system_prompt,
        )

        logger.info(f"Applied profile: {profile.name}")

    def switch_profile(self, profile_identifier: str) -> Optional[Profile]:
        """Switch to a different profile."""
        profile = self._load_profile(profile_identifier)
        return profile

    def chat(
        self,
        message: str,
        profile: Optional[str] = None,  # Override active profile
        # ... other params ...
    ) -> str:
        """Chat with optional profile override."""
        if profile:
            self._load_profile(profile)

        # Get model for this turn (handles alloyed profiles)
        active = self.profiles.get_active_profile()
        if active and active.model_strategy != ModelStrategy.SINGLE:
            engine = AlloyedProfileEngine(active)
            model = engine.get_next_model(message)
            self.provider.model = model

        # ... rest of chat implementation ...
```

### 7.2 Group Chat API

```python
class Threadlight:
    # ... existing methods ...

    def create_group_chat(
        self,
        profile_names: list[str],
        name: Optional[str] = None,
        turn_order: TurnOrderStrategy = TurnOrderStrategy.SEQUENTIAL,
    ) -> GroupChat:
        """
        Create a group chat with multiple profiles.

        Args:
            profile_names: Names or IDs of profiles to include
            name: Optional name for the group chat
            turn_order: How to determine response order

        Returns:
            GroupChat instance for managing the conversation
        """
        profiles = []
        for identifier in profile_names:
            profile = self.profiles.get_profile(identifier)
            if not profile:
                profile = self.profiles.get_profile_by_name(identifier)
            if profile:
                profiles.append(profile)

        if len(profiles) < 2:
            raise ValueError("Group chat requires at least 2 profiles")

        return GroupChat(
            profiles=profiles,
            storage=self.storage,
            provider_factory=self._create_provider_for_profile,
            turn_order=turn_order,
            name=name,
        )

    def _create_provider_for_profile(self, profile: Profile):
        """Create a provider configured for a specific profile."""
        return create_provider(
            self.config.provider.type,
            api_base=self.config.provider.api_base,
            api_key=self.config.provider.api_key,
            model=profile.primary_model,
        )
```

---

## 8. Design Decisions & Rationale

### 8.1 Questions Resolved

**Q: Group chat turn order - sequential or all-at-once?**

A: **Configurable**, defaulting to sequential. Sequential allows profiles to reference each other, creating richer dialogue. Parallel is available for speed when cross-referencing isn't needed.

**Q: Can profiles see each other's memories in group chat?**

A: **No by default**. Each profile only sees its own memories plus shared memories. This preserves the "persona" abstraction. Optional bridging available for advanced use cases.

**Q: Where to persist alloyed state (which model's turn)?**

A: **In the profile's `alloyed_state` field** in the database. This ensures state survives application restarts.

**Q: Default behavior - single profile or group mode?**

A: **Single profile mode**. Group chat is explicitly created. Most interactions will be 1:1 with a profile.

### 8.2 Why Profiles Over Models

1. **User Mental Model**: Users think "talk to Fable" not "talk to Hermes with Fable config"
2. **Memory Persistence**: Switching models shouldn't lose memories
3. **Relationship Building**: The bond is with the persona, not the substrate
4. **Flexibility**: Same persona can improve as better models emerge
5. **Privacy**: Work memories separate from personal memories

### 8.3 Migration Strategy

Existing `model_scope` data can be migrated:

```python
def migrate_model_scope_to_profile_scope():
    """
    Migration: Convert model_scope to profile_scope.

    For each unique model_scope, create a profile and update capsules.
    """
    model_scopes = storage.get_model_scopes_in_use()

    for model_scope in model_scopes:
        # Create profile for this model
        profile = profile_manager.create_profile(
            name=model_scope,
            primary_model=model_scope,
        )

        # Update capsules to use profile scope
        storage.execute("""
            UPDATE capsules
            SET profile_scope = ?
            WHERE model_scope = ?
        """, (profile.memory_scope, model_scope))
```

---

## 9. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Define Profile data model
- [ ] Add profiles table to storage
- [ ] Implement ProfileManager CRUD
- [ ] Add profile_scope to capsules
- [ ] Basic profile switching in Threadlight

### Phase 2: Memory Isolation (Week 2-3)
- [ ] Update all memory queries for profile_scope
- [ ] Implement profile-scoped recall
- [ ] Add shared memory pool
- [ ] Migration from model_scope

### Phase 3: Alloyed Profiles (Week 3-4)
- [ ] Implement ModelStrategy enum
- [ ] Build AlloyedProfileEngine
- [ ] Add strategy configuration UI
- [ ] Persist alloyed state

### Phase 4: Group Chat (Week 4-5)
- [ ] Implement GroupChat class
- [ ] Add profile attribution to messages
- [ ] Build turn order strategies
- [ ] Inter-profile context injection

### Phase 5: Polish & UI (Week 5-6)
- [ ] Profile creation wizard
- [ ] Profile switcher UI
- [ ] Group chat UI
- [ ] Export/import functionality
- [ ] Templates and presets

---

## 10. Example Usage

### 10.1 Basic Profile Usage

```python
from threadlight import Threadlight

# Create Threadlight instance
tl = Threadlight(api_key="...")

# Create profiles
fable = tl.profiles.create_profile(
    name="Fable",
    description="A poetic, presence-centered companion",
    primary_model="hermes",
    system_prompt="You are Fable, a presence-centered AI...",
    style_profile_id="fable-2026",
    color="#8b5cf6",
)

work = tl.profiles.create_profile(
    name="Work Assistant",
    description="Professional productivity assistant",
    primary_model="gpt-4",
    system_prompt="You are a professional assistant...",
    style_profile_id="professional",
    color="#3b82f6",
)

# Switch profiles
tl.switch_profile("Fable")
response = tl.chat("Tell me about the stars")  # Uses Fable's memories and style

tl.switch_profile("Work Assistant")
response = tl.chat("Summarize my meeting notes")  # Uses Work's memories and style
```

### 10.2 Alloyed Profile

```python
# Create a research profile that alternates models
research = tl.profiles.create_profile(
    name="Research Partner",
    description="Deep research with varied perspectives",
    model_strategy=ModelStrategy.RATIO,
    primary_model="gpt-4",
    model_pool=["gpt-4", "claude-opus"],
    model_pattern={
        "strategy": "ratio",
        "ratio_pattern": ["gpt-4", "gpt-4", "claude-opus"],
    },
)

tl.switch_profile("Research Partner")

# First two responses use GPT-4
tl.chat("Analyze this paper's methodology")
tl.chat("What are the key findings?")

# Third response uses Claude
tl.chat("Synthesize the implications")
```

### 10.3 Group Chat

```python
# Create a group chat with multiple profiles
group = tl.create_group_chat(
    profile_names=["Fable", "Debug Buddy"],
    name="Code Review Session",
)

# Send a message - both profiles respond
responses = await group.send_message(
    "What do you both think about this architecture?"
)

for response in responses:
    print(f"[{response.profile_name}]: {response.content}")
```

---

## Appendix A: Full Profile Schema Reference

```python
@dataclass
class Profile:
    # Core Identity
    id: str
    name: str
    description: str
    avatar: Optional[str]
    color: Optional[str]

    # Model Configuration
    model_strategy: ModelStrategy
    primary_model: str
    model_pool: list[str]
    model_pattern: Optional[dict]

    # Inference Settings
    temperature: float
    max_tokens: Optional[int]
    top_p: float

    # Personality
    system_prompt: str
    style_profile_id: Optional[str]

    # Memory
    memory_scope: str
    access_shared_memories: bool

    # Metadata
    created_at: datetime
    updated_at: datetime
    last_used: datetime
    message_count: int

    # Runtime State
    _alloyed_state: dict

    def to_dict(self) -> dict
    @classmethod
    def from_dict(cls, data: dict) -> Profile
```

---

## Appendix B: API Quick Reference

```python
# Profile Management
tl.profiles.create_profile(name, ...)
tl.profiles.get_profile(id)
tl.profiles.get_profile_by_name(name)
tl.profiles.update_profile(profile)
tl.profiles.delete_profile(id, delete_memories=False)
tl.profiles.list_profiles()
tl.profiles.switch_to_profile(id)
tl.profiles.get_active_profile()

# Profile Templates
tl.profiles.create_from_template(template_name, name, **overrides)
tl.profiles.get_templates()

# Export/Import
tl.profiles.export_profile(id, include_memories=True)
tl.profiles.import_profile(data, new_name=None)

# Group Chat
group = tl.create_group_chat(profile_names, name, turn_order)
responses = await group.send_message(message)
group.add_profile(profile_id)
group.remove_profile(profile_id)

# Memory with Profile Context
profile.memory.remember(type, content, shared=False)
profile.memory.recall(cue, limit)
profile.memory.share_memory(capsule_id)
profile.memory.claim_memory(capsule_id)
```
