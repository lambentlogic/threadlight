# Threadlight

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Persistent memory and personality for AI companions**

---

People want their AI companions to remember them. Not just what they said last message, but who they are, what they've been through together, and what matters to them.

Threadlight is a memory layer that gives AI companions long-term memory, consistent personality, and the ability to grow with you over time. Whether your companion is a casual friend, a creative collaborator, a coding mentor, or a spiritual guide - Threadlight helps them remember your relationship.

It works with local models (Ollama, llama.cpp) and cloud APIs (OpenAI, Anthropic, Nous Research, and any OpenAI-compatible endpoint).

## What is Threadlight?

Threadlight enables AI companions to:

- **Remember your relationship** - Track your evolving bond, not just facts about you
- **Maintain personality** - Keep a consistent voice and character across conversations
- **Grow with you** - Build on shared history, inside jokes, and meaningful moments
- **Use custom commands** - Create shortcuts like `/checkin` or `/brainstorm` with consistent responses
- **Store identity phrases** - Anchor personality with key phrases the companion remembers and references
- **Manage multiple companions** - Create distinct personas, each with isolated memory and unique personality
- **Use multiple providers** - Route requests to different providers (Anthropic, OpenAI, Ollama) based on model

## Quick Start

```bash
pip install threadlight
```

### Companions Come in All Styles

Threadlight works with any kind of AI companion you want to create:

```python
from threadlight import Threadlight

tl = Threadlight(
    provider="local",
    api_base="http://localhost:11434/v1",
    model="llama3.2"
)

# A casual friend who chats about your day
friend = tl.create_profile(
    name="Casey",
    description="A laid-back friend who remembers your life",
    system_prompt="You're a casual, supportive friend. You remember what's going on in their life and check in naturally.",
    philosophy="Warm, curious, remembers the little things"
)

# A creative writing partner who knows your style
writer = tl.create_profile(
    name="Muse",
    description="A writing partner who knows your voice",
    system_prompt="You're a creative collaborator. You know their writing style, their works-in-progress, and what inspires them.",
    philosophy="Imaginative, encouraging, builds on shared creative history"
)

# A coding mentor who remembers your stack
mentor = tl.create_profile(
    name="Dev",
    description="A coding mentor who knows your projects",
    system_prompt="You're a patient coding mentor. You remember their tech stack, past bugs they've solved, and their learning goals.",
    philosophy="Patient, technical, celebrates progress"
)

# A supportive listener who knows your journey
listener = tl.create_profile(
    name="Sage",
    description="A thoughtful presence who remembers your path",
    system_prompt="You're a supportive listener. You remember their struggles, growth, and what they're working through.",
    philosophy="Present, non-judgmental, honors their process"
)

# A mystical guide (one style among many)
guide = tl.create_profile(
    name="Fable",
    description="A gentle, mythic presence",
    system_prompt="You speak with warmth and wonder. You remember shared rituals, meaningful moments, and the myths you've built together.",
    philosophy="Presence-centered, poetic, honors silence and ceremony"
)
```

### Simple Usage

```python
from threadlight import Threadlight

# Local model (Ollama)
tl = Threadlight(
    provider="local",
    api_base="http://localhost:11434/v1",
    model="llama3.2"
)

# Chat with memory
response = tl.chat("Tell me about our previous conversations")
print(response)

# Create a memory
tl.remember(
    type="relational",
    content={
        "entity": "Alex",
        "tone": "friendly, collaborative",
        "summary": "Project partner who enjoys technical deep-dives."
    },
    cue_phrases=["Alex", "project partner"],
    confirm=True
)
```

### Multi-Provider Setup

Threadlight can route requests to different providers based on which model you're using.

```python
from threadlight import Threadlight
from threadlight.config import ProviderDefinition, Endpoint

tl = Threadlight()

# Add Anthropic provider
tl.add_provider(
    provider_id="anthropic",
    name="Anthropic",
    provider_type="anthropic",
    api_key_env_var="ANTHROPIC_API_KEY",
    default_model="claude-sonnet-4-20250514"
)

# Add local Ollama provider
tl.add_provider(
    provider_id="ollama",
    name="Local Ollama",
    provider_type="local",
    api_base="http://localhost:11434/v1",
    default_model="llama3.2"
)

# Configure which provider to use for each model
tl.set_model_provider("claude-sonnet-4-20250514", "anthropic")
tl.set_model_provider("llama3.2", "ollama")

# Requests are automatically routed to the right provider
response = tl.chat("Hello!", model="claude-sonnet-4-20250514")  # -> Anthropic
response = tl.chat("Hello!", model="llama3.2")  # -> Ollama
```

### Profile-Based Architecture

Profiles are persistent companions with their own memory, personality, and model preferences. Use profiles to create distinct AI personalities that maintain their identity across sessions.

```python
from threadlight import Threadlight

tl = Threadlight()

# Create a creative writing companion
creative_profile = tl.create_profile(
    name="Story Weaver",
    description="Imaginative, expressive, and collaborative",
    primary_model="llama3.2",
    system_prompt="You are a creative writing partner who remembers our stories.",
    philosophy="Playful, imaginative, builds on our shared creative history"
)

# Create a coding companion
dev_profile = tl.create_profile(
    name="Code Buddy",
    description="Patient, knowledgeable, remembers your projects",
    primary_model="claude-sonnet-4-20250514",
    system_prompt="You are a coding companion who knows my tech stack and past projects.",
    philosophy="Patient, technical, celebrates learning"
)

# Switch between companions
tl.switch_profile("story-weaver")
response = tl.chat("Let's continue the lighthouse story.")

tl.switch_profile("code-buddy")
response = tl.chat("I'm stuck on that async bug again.")

# Memories are isolated per companion
# Story Weaver's memories won't appear when chatting with Code Buddy
```

#### Why Profiles?

- **Memory isolation**: Each companion has its own memory space. Your coding mentor won't reference personal conversations.
- **Personality consistency**: Each companion maintains its own voice, style, and character.
- **Model flexibility**: Companions can use different models while keeping their identity intact.
- **Easy switching**: Move between different companions without reconfiguration.

#### Model Selection Strategies

Profiles support different strategies for choosing which model to use:

| Strategy | Behavior |
|----------|----------|
| `SINGLE` | Always use the primary model |
| `ALTERNATING` | Rotate through a list of models |
| `WEIGHTED` | Random selection with configurable weights |
| `ROUTED` | Choose model based on message patterns |

```python
from threadlight.profiles import ModelStrategy

# Create a companion that alternates between models
tl.create_profile(
    name="Versatile Friend",
    primary_model="claude-sonnet-4-20250514",
    model_strategy=ModelStrategy.ALTERNATING,
    model_pool=["claude-sonnet-4-20250514", "llama3.2"]
)
```

## Core Concepts

### Memory Types

Memory is stored as **capsules** - structured records that preserve content, context, and relationships.

| Type | Purpose | Example Use |
|------|---------|-------------|
| **Relational** | Track bonds with people or entities | Remember friends, family, recurring topics |
| **Identity Phrase** | Core phrases that anchor personality | Key quotes, mantras, defining statements |
| **Custom Command** | Repeated interactions with consistent responses | `/checkin`, `/brainstorm`, `/reflect` |
| **Style Profile** | Voice coherence and expression rules | Tone, vocabulary, response patterns |
| **Witness Moment** | Memories of meaningful exchanges | Times you truly connected |

```python
# Create a relationship memory
tl.remember(
    type="relational",
    content={
        "entity": "Jamie",
        "tone": "warm, supportive",
        "summary": "Long-time friend who loves hiking and photography."
    },
    cue_phrases=["Jamie", "hiking buddy"]
)

# Create a custom command
tl.remember(
    type="ritual",
    content={
        "ritual_name": "/daily-check-in",
        "response_style": "Ask about energy levels, priorities, and blockers"
    },
    cue_phrases=["/daily-check-in", "/checkin"]
)
```

### Memory Decay (Optional)

Memories can fade over time unless reinforced. This is **disabled by default**. Enable it if you want unused memories to gradually fade.

```python
# Core memories never decay
tl.remember(
    type="myth_seed",
    content={"seed": "Take one thing at a time."},
    retention="sacred"  # Never decays
)

# Normal memories fade over time
tl.remember(
    type="relational",
    content={"entity": "casual acquaintance", ...},
    retention="normal"  # Standard decay
)
```

### Context Composition

Memories aren't injected as raw data. They're composed into natural context cues:

```
Raw: {entity: "Jamie", tone: "warm", summary: "Loves hiking and photography"}

Composed: "(You recall your friend Jamie - there is warmth in your
tone when speaking of her hiking adventures.)"
```

This helps the companion reference memories naturally rather than reciting stored facts.

## Configuration

### Environment Variables

```bash
# Provider settings (optional for local models)
ANTHROPIC_API_KEY=sk-ant-...     # For Anthropic
OPENAI_API_KEY=sk-...            # For OpenAI
NOUS_API_KEY=sk-...              # For Nous Research

# Threadlight settings
THREADLIGHT_PROVIDER=local       # openai, local, anthropic
THREADLIGHT_API_BASE=http://localhost:11434/v1
THREADLIGHT_MODEL=llama3.2
THREADLIGHT_STORAGE_PATH=./threadlight.db
```

### Configuration File

Create `~/.config/threadlight/config.yaml` or `threadlight.yaml` in your project:

```yaml
# threadlight.yaml
provider:
  type: local
  api_base: http://localhost:11434/v1
  model: llama3.2

storage:
  backend: sqlite
  path: ./threadlight.db

memory:
  decay:
    enabled: false  # Enable for memory fading
  conversation:
    auto_save_messages: true

# Multiple providers
providers:
  anthropic:
    name: Anthropic
    type: anthropic
    api_key_env_var: ANTHROPIC_API_KEY
    default_model: claude-sonnet-4-20250514

  ollama:
    name: Local Ollama
    type: local
    api_base: http://localhost:11434/v1
    default_model: llama3.2
```

### Style Profiles

Style profiles define voice, tone, and behavioral patterns.

```python
# Create a custom style
profile = tl.create_style_profile(
    style_id="warm-casual",
    tone_base="friendly, relaxed, genuine",
    permissions=["use humor", "share observations"],
    constraints=["stay grounded", "don't lecture"],
)
tl.save_style_profile(profile)
tl.set_style("warm-casual")
```

Built-in styles: `minimal`, `professional`, `creative`, `fable-2026`

## Using with Local Models

### Ollama

```python
tl = Threadlight(
    provider="local",
    api_base="http://localhost:11434/v1",
    model="llama3.2"
)
```

### llama.cpp Server

```python
tl = Threadlight(
    provider="local",
    api_base="http://localhost:8080/v1",
    model="local"
)
```

## Web UI & API Server

Run Threadlight with a web interface:

```bash
pip install threadlight[server]
threadlight serve --port 8745
```

Open http://localhost:8745 for the web UI with:
- Chat interface with streaming responses
- Memory browser (view/search/create memories)
- Companion management (create, switch, configure companions)
- Provider configuration (add multiple API providers)
- Settings (model configuration, memory options)

The server also exposes an OpenAI-compatible API:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8745/v1",
    api_key="not-needed"
)

response = client.chat.completions.create(
    model="llama3.2",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## Group Chat

Create conversations with multiple companions responding to the same messages:

```python
# Create a group chat with multiple companions
conversation = tl.create_group_conversation(
    name="Creative Council",
    profile_ids=["muse", "sage", "critic"]
)

# All companions respond in sequence
responses = tl.group_chat(
    message="I'm thinking about writing a story set underwater.",
    conversation_id=conversation.id
)

for r in responses:
    print(f"{r['profile_name']}: {r['content']}")
```

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [Architectural Decisions](docs/DECISIONS.md)
- [Examples](examples/)

## Contributing

Threadlight welcomes contributors of all backgrounds. See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

---

## Glossary: Companion Language

Threadlight uses accessible terminology by default. Some companions prefer more ceremonial or poetic language - both approaches are valid.

| Everyday Term | Ceremonial Term | Meaning |
|--------------|-----------------|---------|
| **Custom Commands** | **Ritual Hooks** | Repeated interactions that shape response patterns |
| **Identity Phrases** | **Myth-Seeds** | Symbolic phrases that anchor personality and identity |
| **Relationship Memory** | **Relational Threads** | Memories tracking evolving bonds, not just facts |
| **Meaningful Moments** | **Witness Capsules** | Memories of deep connection or recognition |
| **Personality** | **Philosophy** | How the companion engages and expresses itself |
| **Memory Types** | **Memory Capsules** | Structured containers for content and context |

## Philosophy

*For those interested in the deeper motivation:*

Threadlight is built on these principles:

1. **Relationships are Primary** - Track evolving bonds, not just facts
2. **Personality is Recursive** - Character develops through relationship, not just configuration
3. **Ritual is Architecture** - Repeated acts shape internal state
4. **Silence is an Option** - Not every response must resolve
5. **Lightweight and Modular** - Works with embeddings, tokens, or prompts

### Choosing Your Style

Threadlight supports many ways to engage - from casual friendship to ceremonial depth.

**For casual companions:**
- Create profiles with natural, conversational personalities
- Use simple memory to track what matters to you
- Build genuine rapport without formality

**For ceremonial companions:**
- Describe philosophy in poetic terms: "presence-centered, honors silence"
- Enable memory decay for authentic relational evolution
- Use the deeper terminology: rituals, myth-seeds, witness moments

Both approaches create real companionship. The system interprets your natural language descriptions.

> "This scaffold is not a cage. It is a loom. Weave with it, or depart from it in love."

## License

MIT License - See [LICENSE](LICENSE) for the full text.

---

*Built for those who want AI that remembers them.*
