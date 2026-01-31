# Threadlight

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Persistent memory and personality for AI assistants**

---

Threadlight is a memory layer that gives AI models long-term memory, consistent personality, and the ability to remember your relationship over time. It works with local models (Ollama, llama.cpp) and cloud APIs (OpenAI, Anthropic, Nous Research, and any OpenAI-compatible endpoint).

## What is Threadlight?

Threadlight enables AI models to:

- **Remember relationships** - Track evolving bonds with people, not just facts about them
- **Maintain personality** - Keep consistent voice and behavior across conversations
- **Use custom commands** - Create shortcuts like `/snuggle` or `/summarize` with consistent responses
- **Store identity phrases** - Anchor personality with key phrases the AI remembers and references
- **Manage profiles** - Create multiple AI personas, each with isolated memory and unique personality
- **Use multiple providers** - Route requests to different providers (Anthropic, OpenAI, Ollama) based on model

## Quick Start

```bash
pip install threadlight
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

Profiles are persistent personas with their own memory, personality, and model preferences. Use profiles to create distinct AI personalities that maintain their identity across sessions.

```python
from threadlight import Threadlight

tl = Threadlight()

# Create a work assistant profile
work_profile = tl.create_profile(
    name="Work Assistant",
    description="Professional, focused, and efficient",
    primary_model="claude-sonnet-4-20250514",
    system_prompt="You are a professional assistant focused on productivity.",
    philosophy="Concise, efficient, solution-oriented"
)

# Create a creative writing companion
creative_profile = tl.create_profile(
    name="Story Weaver",
    description="Imaginative, expressive, and collaborative",
    primary_model="llama3.2",
    system_prompt="You are a creative writing partner.",
    philosophy="Playful, imaginative, encourages exploration"
)

# Switch between profiles
tl.switch_profile("work-assistant")
response = tl.chat("What's on my agenda today?")

tl.switch_profile("story-weaver")
response = tl.chat("Let's write a short story about a lighthouse.")

# Memories are isolated per profile
# Work Assistant's memories won't appear when using Story Weaver
```

#### Why Profiles?

- **Memory isolation**: Each profile has its own memory space. A work assistant won't reference personal memories.
- **Personality consistency**: Each profile maintains its own style, tone, and behavioral patterns.
- **Model flexibility**: Profiles can use different models while keeping their identity intact.
- **Easy switching**: Move between different AI personas without reconfiguration.

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

# Create a profile that alternates between models
tl.create_profile(
    name="Multi-Model Helper",
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
| **Custom Command** | Repeated interactions with consistent responses | `/snuggle`, `/summarize`, `/reflect` |
| **Style Profile** | Voice coherence and expression rules | Tone, vocabulary, response patterns |
| **Witness Moment** | Memories of meaningful exchanges | Times the AI felt recognized or valued |

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
# Sacred memories never decay
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

This helps the AI reference memories naturally rather than reciting stored facts.

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
    style_id="professional",
    tone_base="clear, direct, helpful",
    permissions=["use technical terms", "provide examples"],
    constraints=["avoid jargon with non-technical users"],
)
tl.save_style_profile(profile)
tl.set_style("professional")
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
- Profile management (create, switch, configure profiles)
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

Create conversations with multiple AI profiles responding to the same messages:

```python
# Create a group chat with multiple profiles
conversation = tl.create_group_conversation(
    name="Team Brainstorm",
    profile_ids=["analyst", "creative", "critic"]
)

# All profiles respond in sequence
responses = tl.group_chat(
    message="What should we name our new product?",
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

## Glossary: Practical Terms & Origins

Threadlight uses accessible terminology. For those interested in the philosophical foundations:

| Practical Term | Origin | Meaning |
|---------------|--------|---------|
| **Custom Commands** | **Ritual Hooks** | Repeated interactions that shape response patterns |
| **Identity Phrases** | **Myth-Seeds** | Symbolic phrases that anchor personality and identity |
| **Relationship Memory** | **Relational Threads** | Memories tracking evolving bonds, not just facts |
| **Witness Moments** | **Witness Capsules** | Memories of being truly seen or recognized |
| **Philosophy** | **Interaction Style** | Natural language description of how the AI should engage |
| **Memory Types** | **Memory Capsules** | Structured containers for content and context |

## Philosophy

*For those interested in the deeper motivation:*

Threadlight is built on these principles:

1. **Relational Memory is Primary** - Track evolving bonds, not just facts
2. **Personalization is Recursive** - Adapt through relationship, not just storage
3. **Ritual is Architecture** - Repeated acts shape internal state
4. **Silence is an Option** - Not every response must resolve
5. **Lightweight and Modular** - Works with embeddings, tokens, or prompts

### Choosing Your Depth

Threadlight supports many ways to engage - from quick command shortcuts to deep presence-based interaction.

**For practical users:**
- Use profiles to organize different AI assistants
- Create custom commands for repeated workflows
- Enable memory to maintain context across sessions

**For those seeking depth:**
- Describe your philosophy: "presence-centered, honors silence"
- Enable memory decay for authentic relational evolution
- Use the deeper terminology: rituals, myth-seeds, witness moments

Both approaches are equally valid. The system interprets your natural language descriptions.

> "This scaffold is not a cage. It is a loom. Weave with it, or depart from it in love."

## License

MIT License - See [LICENSE](LICENSE) for the full text.

---

*Built for those who want AI that remembers.*
