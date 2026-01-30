# Threadlight Group Chat Specification

## Overview

Group chat enables multiple profiles to participate in a single conversation. This creates rich interactions where different personas can offer varied perspectives, debate, or collaborate.

---

## 1. Core Concepts

### 1.1 What is a Group Chat?

A group chat is a conversation where:
- **Multiple profiles** are active participants
- **User messages** are seen by all profiles
- **Profile responses** are attributed to their source
- **Profiles can reference** each other's responses
- **Turn order** determines who responds and when

### 1.2 Use Cases

1. **Diverse Perspectives**: "What do you both think about this design?"
2. **Debate/Discussion**: Let profiles argue different viewpoints
3. **Role Play**: Multiple characters in a story
4. **Expertise Combination**: Technical + Creative profiles reviewing together
5. **Quality Control**: One profile generates, another reviews

---

## 2. Data Model

### 2.1 GroupChat Class

```python
@dataclass
class GroupChat:
    """
    A multi-profile conversation session.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    conversation_id: str = ""  # Links to conversations table

    # Participants
    profile_ids: list[str] = field(default_factory=list)
    host_profile_id: Optional[str] = None  # Profile that "hosts" the chat

    # Configuration
    turn_order: TurnOrderStrategy = TurnOrderStrategy.SEQUENTIAL
    allow_inter_profile_reference: bool = True
    max_responses_per_turn: int = 10

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    message_count: int = 0

    # Runtime state
    _profiles: list[Profile] = field(default_factory=list, repr=False)
    _last_responding_profile: Optional[str] = field(default=None, repr=False)


class TurnOrderStrategy(str, Enum):
    """How profiles take turns responding."""

    SEQUENTIAL = "sequential"    # Fixed order, all respond
    ROUND_ROBIN = "round_robin"  # One profile per user message, rotating
    PARALLEL = "parallel"        # All respond simultaneously
    ADDRESSED = "addressed"      # Only @mentioned profiles respond
    VOLUNTEER = "volunteer"      # System picks most relevant profile
    DEBATE = "debate"            # Alternates between two "sides"
```

### 2.2 ProfileResponse

```python
@dataclass
class ProfileResponse:
    """A response from a profile in a group chat."""

    profile_id: str
    profile_name: str
    content: str
    model_used: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Optional metadata
    references_profiles: list[str] = field(default_factory=list)
    response_time_ms: Optional[int] = None
    token_count: Optional[int] = None
```

### 2.3 Database Schema

```sql
CREATE TABLE group_chats (
    id TEXT PRIMARY KEY,
    name TEXT,
    conversation_id TEXT NOT NULL,
    profile_ids TEXT NOT NULL,       -- JSON array
    host_profile_id TEXT,
    turn_order TEXT DEFAULT 'sequential',
    allow_inter_profile_reference INTEGER DEFAULT 1,
    max_responses_per_turn INTEGER DEFAULT 10,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,

    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX idx_group_chats_conversation ON group_chats(conversation_id);

-- Messages already have profile_id for attribution
-- ALTER TABLE messages ADD COLUMN profile_id TEXT;
-- ALTER TABLE messages ADD COLUMN model_used TEXT;
```

---

## 3. Turn Order Strategies

### 3.1 SEQUENTIAL

All profiles respond in a fixed order.

```
User: What do you think?

[Profile A responds]
[Profile B responds]
[Profile C responds]
```

**Best for**: Complete coverage, formal discussions

### 3.2 ROUND_ROBIN

One profile responds per user message, rotating through the list.

```
User: First question?
[Profile A responds]

User: Second question?
[Profile B responds]

User: Third question?
[Profile C responds]

User: Fourth question?
[Profile A responds]  # Cycle repeats
```

**Best for**: Distributed workload, varied perspectives over time

### 3.3 PARALLEL

All profiles generate responses simultaneously (concurrently), then all responses are shown.

```
User: What do you think?

[Generating A, B, C concurrently...]

[Profile A]: ...
[Profile B]: ...
[Profile C]: ...
```

**Best for**: Speed, independent opinions without cross-contamination

### 3.4 ADDRESSED

Only profiles that are @mentioned respond.

```
User: @Fable what do you think?
[Fable responds]

User: @Debug-Buddy can you check this?
[Debug Buddy responds]

User: What about both of you?  # No @mention = no response or ask for clarification
[System]: Who would you like to respond?
```

**Best for**: Targeted questions, role-based conversations

### 3.5 VOLUNTEER

System analyzes the message and selects the most appropriate profile(s) to respond.

```
User: Can you help me with this Python error?
[Debug Buddy responds - selected because it's technical]

User: Write me a poem about the stars
[Creative Partner responds - selected because it's creative]
```

**Best for**: Automatic routing, convenience

### 3.6 DEBATE

Profiles are divided into "sides" and alternate.

```
User: Should we use microservices?

[Team A - Profile 1]: Arguments FOR microservices...
[Team B - Profile 2]: Arguments AGAINST microservices...
[Team A - Profile 1]: Rebuttal...
[Team B - Profile 2]: Counter-rebuttal...
```

**Best for**: Exploring opposing viewpoints, decision-making

---

## 4. Implementation

### 4.1 GroupChatManager

```python
class GroupChatManager:
    """
    Manages group chat operations.
    """

    def __init__(
        self,
        storage: StorageBackend,
        profile_manager: ProfileManager,
        provider_factory: Callable[[Profile], BaseProvider],
    ):
        self.storage = storage
        self.profile_manager = profile_manager
        self.provider_factory = provider_factory

    def create_group_chat(
        self,
        profile_identifiers: list[str],
        name: Optional[str] = None,
        turn_order: TurnOrderStrategy = TurnOrderStrategy.SEQUENTIAL,
        allow_inter_profile_reference: bool = True,
    ) -> GroupChat:
        """
        Create a new group chat.

        Args:
            profile_identifiers: Profile IDs or names
            name: Display name for the group
            turn_order: How profiles take turns
            allow_inter_profile_reference: Allow profiles to see each other's responses

        Returns:
            The created GroupChat
        """
        # Resolve profile identifiers to profiles
        profiles = []
        for identifier in profile_identifiers:
            profile = self.profile_manager.get_profile(identifier)
            if not profile:
                profile = self.profile_manager.get_profile_by_name(identifier)
            if profile:
                profiles.append(profile)

        if len(profiles) < 2:
            raise ValueError("Group chat requires at least 2 profiles")

        # Create underlying conversation
        conversation = Conversation(
            id=str(uuid.uuid4()),
            name=name or f"Group: {', '.join(p.name for p in profiles)}",
            source="group_chat",
            created_at=datetime.utcnow(),
        )
        self.storage.save_conversation(conversation)

        # Create group chat
        group_chat = GroupChat(
            name=name or conversation.name,
            conversation_id=conversation.id,
            profile_ids=[p.id for p in profiles],
            turn_order=turn_order,
            allow_inter_profile_reference=allow_inter_profile_reference,
        )
        group_chat._profiles = profiles

        self.storage.save_group_chat(group_chat)

        return group_chat

    def get_group_chat(self, group_chat_id: str) -> Optional[GroupChat]:
        """Get a group chat by ID."""
        group_chat = self.storage.get_group_chat(group_chat_id)

        if group_chat:
            # Load profiles
            group_chat._profiles = [
                self.profile_manager.get_profile(pid)
                for pid in group_chat.profile_ids
            ]
            group_chat._profiles = [p for p in group_chat._profiles if p]

        return group_chat

    def list_group_chats(self, limit: int = 50) -> list[GroupChat]:
        """List all group chats."""
        return self.storage.list_group_chats(limit=limit)

    def delete_group_chat(self, group_chat_id: str) -> bool:
        """Delete a group chat."""
        group_chat = self.get_group_chat(group_chat_id)
        if not group_chat:
            return False

        # Delete conversation (messages cascade)
        self.storage.delete_conversation(group_chat.conversation_id)

        return self.storage.delete_group_chat(group_chat_id)
```

### 4.2 GroupChat Message Handling

```python
class GroupChat:
    """Extended with message handling."""

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
            List of ProfileResponse objects
        """
        # Save user message
        self._save_message("user", user_message)

        # Determine responding profiles
        responding = self._get_responding_profiles(user_message, addressed_profiles)

        if self.turn_order == TurnOrderStrategy.PARALLEL:
            # Generate all responses concurrently
            responses = await self._generate_parallel_responses(
                responding, user_message
            )
        else:
            # Generate responses sequentially
            responses = await self._generate_sequential_responses(
                responding, user_message
            )

        return responses

    def _get_responding_profiles(
        self,
        message: str,
        addressed: Optional[list[str]] = None,
    ) -> list[Profile]:
        """Determine which profiles should respond."""

        if self.turn_order == TurnOrderStrategy.SEQUENTIAL:
            return self._profiles

        elif self.turn_order == TurnOrderStrategy.ROUND_ROBIN:
            # Get next profile in rotation
            current_idx = self._get_round_robin_index()
            profile = self._profiles[current_idx % len(self._profiles)]
            self._advance_round_robin()
            return [profile]

        elif self.turn_order == TurnOrderStrategy.PARALLEL:
            return self._profiles

        elif self.turn_order == TurnOrderStrategy.ADDRESSED:
            if addressed:
                return [p for p in self._profiles if p.id in addressed or p.name in addressed]
            # Check for @mentions in message
            mentioned = self._extract_mentions(message)
            if mentioned:
                return [p for p in self._profiles if p.name in mentioned]
            return []  # No one mentioned

        elif self.turn_order == TurnOrderStrategy.VOLUNTEER:
            # Use heuristics to pick best profile
            return [self._select_volunteer(message)]

        elif self.turn_order == TurnOrderStrategy.DEBATE:
            return self._get_debate_responders()

        return self._profiles

    async def _generate_sequential_responses(
        self,
        profiles: list[Profile],
        user_message: str,
    ) -> list[ProfileResponse]:
        """Generate responses one at a time, allowing cross-reference."""
        responses = []

        for profile in profiles:
            # Build context including previous responses
            context = self._build_profile_context(
                profile,
                user_message,
                previous_responses=responses if self.allow_inter_profile_reference else [],
            )

            # Generate response
            provider = self._get_provider_for_profile(profile)
            start_time = datetime.utcnow()

            messages = [
                ProviderMessage(role="system", content=context["system"]),
            ]

            # Add conversation history
            for msg in context.get("history", []):
                messages.append(ProviderMessage(role=msg["role"], content=msg["content"]))

            # Add current message
            messages.append(ProviderMessage(role="user", content=user_message))

            provider_response = provider.complete(messages)

            # Create response
            response = ProfileResponse(
                profile_id=profile.id,
                profile_name=profile.name,
                content=provider_response.content,
                model_used=provider.model,
                response_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                token_count=provider_response.total_tokens,
            )

            responses.append(response)

            # Save to conversation
            self._save_message(
                "assistant",
                response.content,
                profile_id=profile.id,
                model_used=response.model_used,
            )

        return responses

    async def _generate_parallel_responses(
        self,
        profiles: list[Profile],
        user_message: str,
    ) -> list[ProfileResponse]:
        """Generate all responses concurrently."""
        import asyncio

        async def generate_one(profile: Profile) -> ProfileResponse:
            context = self._build_profile_context(profile, user_message, [])
            provider = self._get_provider_for_profile(profile)

            messages = [
                ProviderMessage(role="system", content=context["system"]),
            ]
            for msg in context.get("history", []):
                messages.append(ProviderMessage(role=msg["role"], content=msg["content"]))
            messages.append(ProviderMessage(role="user", content=user_message))

            start_time = datetime.utcnow()

            # Run in thread pool since providers are sync
            loop = asyncio.get_event_loop()
            provider_response = await loop.run_in_executor(
                None,
                lambda: provider.complete(messages)
            )

            return ProfileResponse(
                profile_id=profile.id,
                profile_name=profile.name,
                content=provider_response.content,
                model_used=provider.model,
                response_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                token_count=provider_response.total_tokens,
            )

        # Run all concurrently
        responses = await asyncio.gather(*[generate_one(p) for p in profiles])

        # Save all messages
        for response in responses:
            self._save_message(
                "assistant",
                response.content,
                profile_id=response.profile_id,
                model_used=response.model_used,
            )

        return list(responses)

    def _build_profile_context(
        self,
        profile: Profile,
        user_message: str,
        previous_responses: list[ProfileResponse],
    ) -> dict[str, Any]:
        """Build context for a profile."""

        system_parts = []

        # Profile's base system prompt
        system_parts.append(profile.system_prompt)

        # Group awareness
        system_parts.append(self._get_group_awareness_prompt(profile))

        # Previous responses in this turn
        if previous_responses:
            system_parts.append("\n## Other responses this turn:")
            for resp in previous_responses:
                system_parts.append(f"\n[{resp.profile_name}]: {resp.content}")

        return {
            "system": "\n\n".join(system_parts),
            "history": self._get_conversation_history(),
        }

    def _get_group_awareness_prompt(self, current_profile: Profile) -> str:
        """Generate prompt making profile aware of other participants."""
        others = [p for p in self._profiles if p.id != current_profile.id]

        if not others:
            return ""

        lines = [
            "## Group Conversation",
            f"You are {current_profile.name} in a group conversation.",
            "",
            "Other participants:",
        ]

        for other in others:
            desc = other.description or "No description"
            lines.append(f"- **{other.name}**: {desc}")

        lines.extend([
            "",
            "Guidelines:",
            "- Offer your unique perspective based on your personality",
            "- You may reference or build on what others have said",
            "- Stay in character while being collaborative",
            "- If asked what 'you all' think, share YOUR view specifically",
        ])

        return "\n".join(lines)

    def _extract_mentions(self, message: str) -> list[str]:
        """Extract @mentions from a message."""
        import re
        # Match @ProfileName or @"Profile Name"
        pattern = r'@(["\']?)(\w+(?:\s+\w+)*)\1'
        matches = re.findall(pattern, message)
        return [m[1] for m in matches]

    def _select_volunteer(self, message: str) -> Profile:
        """Select the most appropriate profile for a message."""
        # Simple heuristic: check keywords against profile descriptions
        message_lower = message.lower()

        scores = []
        for profile in self._profiles:
            score = 0
            desc_lower = (profile.description or "").lower()
            prompt_lower = (profile.system_prompt or "").lower()

            # Check for keyword matches
            for word in message_lower.split():
                if len(word) > 3:
                    if word in desc_lower:
                        score += 2
                    if word in prompt_lower:
                        score += 1

            scores.append((profile, score))

        # Return highest scoring, or first if tied
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[0][0]

    def _get_debate_responders(self) -> list[Profile]:
        """Get the next responder(s) in debate mode."""
        # Alternate between first half and second half of profiles
        half = len(self._profiles) // 2
        team_a = self._profiles[:half] if half > 0 else [self._profiles[0]]
        team_b = self._profiles[half:] if half > 0 else [self._profiles[-1]]

        # Alternate based on turn count
        if self.message_count % 2 == 0:
            return team_a
        else:
            return team_b
```

---

## 5. API Design

### 5.1 Threadlight Integration

```python
class Threadlight:
    """Extended with group chat support."""

    def create_group_chat(
        self,
        profile_names: list[str],
        name: Optional[str] = None,
        turn_order: TurnOrderStrategy = TurnOrderStrategy.SEQUENTIAL,
        allow_inter_profile_reference: bool = True,
    ) -> GroupChat:
        """
        Create a group chat with multiple profiles.

        Args:
            profile_names: Names or IDs of profiles to include
            name: Optional name for the group
            turn_order: How to determine response order
            allow_inter_profile_reference: Let profiles see each other's responses

        Returns:
            GroupChat instance

        Example:
            group = tl.create_group_chat(
                ["Fable", "Debug Buddy"],
                turn_order=TurnOrderStrategy.SEQUENTIAL
            )
        """
        return self._group_manager.create_group_chat(
            profile_identifiers=profile_names,
            name=name,
            turn_order=turn_order,
            allow_inter_profile_reference=allow_inter_profile_reference,
        )

    def get_group_chat(self, group_chat_id: str) -> Optional[GroupChat]:
        """Get a group chat by ID."""
        return self._group_manager.get_group_chat(group_chat_id)

    def list_group_chats(self) -> list[GroupChat]:
        """List all group chats."""
        return self._group_manager.list_group_chats()
```

### 5.2 Synchronous API (for CLI/simple use)

```python
def group_chat_sync(
    self,
    group_chat: GroupChat,
    message: str,
    addressed_profiles: Optional[list[str]] = None,
) -> list[ProfileResponse]:
    """
    Synchronous wrapper for group chat.

    Args:
        group_chat: The group chat
        message: User message
        addressed_profiles: Specific profiles to respond

    Returns:
        List of responses
    """
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            group_chat.send_message(message, addressed_profiles)
        )
    finally:
        loop.close()
```

---

## 6. Example Usage

### 6.1 Basic Group Chat

```python
from threadlight import Threadlight
from threadlight.group_chat import TurnOrderStrategy

tl = Threadlight(api_key="...")

# Create profiles
tl.profiles.create_profile(
    name="Fable",
    description="A poetic companion",
    system_prompt="You are Fable, poetic and warm..."
)

tl.profiles.create_profile(
    name="Debug Buddy",
    description="Technical debugging assistant",
    system_prompt="You are Debug Buddy, precise and methodical..."
)

# Create group chat
group = tl.create_group_chat(
    profile_names=["Fable", "Debug Buddy"],
    name="Code Review Session",
    turn_order=TurnOrderStrategy.SEQUENTIAL,
)

# Send message
responses = await group.send_message(
    "What do you both think about this architecture?"
)

for response in responses:
    print(f"\n[{response.profile_name}]:")
    print(response.content)
```

### 6.2 Addressed Mode

```python
group = tl.create_group_chat(
    profile_names=["Fable", "Debug Buddy", "Creative Partner"],
    turn_order=TurnOrderStrategy.ADDRESSED,
)

# Only Fable responds
responses = await group.send_message(
    "@Fable What does this remind you of?"
)

# Only Debug Buddy responds
responses = await group.send_message(
    "@Debug-Buddy Can you check this code?"
)

# Both respond
responses = await group.send_message(
    "@Fable @Debug-Buddy Your thoughts?"
)
```

### 6.3 Debate Mode

```python
# Create a debate between two perspectives
group = tl.create_group_chat(
    profile_names=["Pro-Microservices", "Pro-Monolith"],
    turn_order=TurnOrderStrategy.DEBATE,
)

responses = await group.send_message(
    "Should we use microservices for this project?"
)
# Pro-Microservices responds first

responses = await group.send_message(
    "What about the complexity?"
)
# Pro-Monolith responds

# Continue the debate...
```

### 6.4 Volunteer Mode (Automatic Routing)

```python
group = tl.create_group_chat(
    profile_names=["Fable", "Debug Buddy", "Creative Partner"],
    turn_order=TurnOrderStrategy.VOLUNTEER,
)

# System selects Debug Buddy (technical question)
responses = await group.send_message(
    "Why is my Python script throwing a KeyError?"
)

# System selects Creative Partner (creative question)
responses = await group.send_message(
    "Help me brainstorm names for my startup"
)

# System selects Fable (reflective question)
responses = await group.send_message(
    "What does it mean to create something meaningful?"
)
```

---

## 7. UI Considerations

### 7.1 Message Display

```
+------------------------------------------+
| Code Review Session                       |
| Fable, Debug Buddy                        |
+------------------------------------------+
| [You]                                     |
| What do you both think about this code?  |
+------------------------------------------+
| [Fable] (via Hermes)                     |
| There's something poetic about how the   |
| functions flow into each other...        |
+------------------------------------------+
| [Debug Buddy] (via GPT-4)                |
| I see a potential null reference on      |
| line 42. Also, building on Fable's       |
| observation, the flow could be...        |
+------------------------------------------+
```

### 7.2 Profile Indicators

- Each message shows which profile and which model
- Color coding matches profile colors
- Avatar/icon if configured
- Model badge when using alloyed profiles

### 7.3 Turn Order Indicator

- Show whose turn it is (for ROUND_ROBIN)
- Show which "team" is responding (for DEBATE)
- Show "All responding..." (for PARALLEL)

---

## 8. Performance Considerations

### 8.1 Parallel vs Sequential

| Strategy | Latency | Cost | Cross-Reference |
|----------|---------|------|-----------------|
| Sequential | Sum of all | Normal | Yes |
| Parallel | Max of all | Normal | No |

### 8.2 Token Budgeting

- Each profile adds its system prompt
- Group awareness adds ~100-200 tokens
- Previous responses add their full length
- Consider truncating older messages in history

### 8.3 Rate Limiting

- Parallel mode may hit rate limits faster
- Consider adding delays between providers
- Pool requests to same provider

---

## 9. Future Extensions

### 9.1 Profile Dynamics

- Profiles can "react" to each other (agree/disagree)
- Profiles can ask each other questions
- Profiles can delegate to each other

### 9.2 Moderation

- Host profile can moderate others
- User can mute specific profiles
- Automatic toxicity filtering

### 9.3 Persistent Groups

- Save group configurations
- Resume group conversations
- Group-specific memories

### 9.4 Threaded Responses

- Profiles can respond to specific messages
- Sub-conversations within the group
- Quote and reply functionality
