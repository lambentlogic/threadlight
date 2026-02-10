# Threadlight

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Persistent memory and personality for AI companions**

---

People want their AI companions to remember them. Not just what they said last message, but who they are, what they've been through together, and what matters to them.

Threadlight is a memory layer that gives AI companions long-term memory, consistent personality, and the ability to grow with you over time. Whether your companion is a casual friend, a creative collaborator, a coding mentor, or a supportive listener - Threadlight helps them remember your relationship.

It works with local models (Ollama, llama.cpp) and cloud APIs (OpenAI, Anthropic, Nous Research, and any OpenAI-compatible endpoint).

> **For Users**: Use the web interface (no coding required) - see [Getting Started](#getting-started)
> **For Developers**: Use the Python API or CLI - see [Advanced Usage](#advanced-usage)

## What is Threadlight?

Threadlight enables AI companions to:

- **Remember your relationship** - Track your evolving bond, not just facts about you
- **Maintain personality** - Keep a consistent voice and character across conversations
- **Grow with you** - Build on shared history, inside jokes, and meaningful moments
- **Use custom invocations** - Create shortcuts like `/checkin` or `/brainstorm` with consistent responses
- **Store identity phrases** - Anchor personality with key phrases the companion remembers and references
- **Manage multiple companions** - Create distinct personas, each with isolated memory and unique personality
- **Use multiple providers** - Route requests to different providers (Anthropic, OpenAI, Ollama) based on model

## Getting Started

### Prerequisites

You'll need Python 3.10 or newer installed on your computer.

**Check if you have Python:**
```bash
python --version
```

**Don't have Python?** Download it from [python.org](https://www.python.org/downloads/)
- Windows/Mac: Use the installer
- Linux: Usually pre-installed, or install via your package manager

**What is pip?** It's Python's package installer (comes with Python). If `pip` doesn't work, try `pip3` or `python -m pip` instead.

### Installation

1. **Install Threadlight:**
   ```bash
   pip install threadlight
   ```

2. **Start the web server:**
   ```bash
   threadlight serve
   ```

3. **Open your browser to `http://localhost:8745`**

That's it! You can now configure your companions through the web interface.

## Using the Web Interface

### First Time Setup

1. **Configure a Provider** (Settings > Providers)
   - Add your inference provider (Anthropic, OpenAI, local Ollama, etc.)
   - Enter your API key or connect to local models
   - Test the connection

2. **Create Your First Companion** (Profiles > Add Profile)
   - Choose a name for your companion
   - Select which model(s) to use
   - Describe their personality and style
   - Configure memory preferences

3. **Start Chatting**
   - Select your companion from the dropdown
   - Start a new conversation
   - Your companion will remember everything across sessions

### Web UI Features

- **Profiles**: Manage multiple companions with different personalities
- **Conversations**: All your chat history, searchable and organized
- **Memories**: View and manage what your companions remember
- **Settings**: Configure providers, models, memory, and advanced features
- **Import/Export**: Bring conversations from ChatGPT or Claude

### Companions Come in All Styles

Threadlight works with any kind of AI companion you want to create:

- **A casual friend** who chats about your day and remembers your life
- **A creative writing partner** who knows your style and works-in-progress
- **A coding mentor** who remembers your tech stack and past projects
- **A research assistant** who organizes papers and helps synthesize findings
- **A technical advisor** who tracks system patterns and troubleshoots issues
- **A supportive listener** who knows your journey and growth
- **A mystical guide** who speaks with warmth and remembers shared rituals

Just describe their personality in natural language when creating a profile - Threadlight interprets your descriptions.

## Core Concepts

### Memory Types

Memory is stored as **capsules** - structured records that preserve content, context, and relationships.

| Type | Purpose | Example Use |
|------|---------|-------------|
| **Relational** | Track bonds with people or entities | Remember friends, family, recurring topics |
| **Identity Phrase** | Core phrases that anchor personality | Key quotes, mantras, defining statements |
| **Custom Invocation** | Repeated interactions with consistent responses | `/checkin`, `/brainstorm`, `/reflect` |
| **Style Profile** | Voice coherence and expression rules | Tone, vocabulary, response patterns |
| **Witness Moment** | Memories of meaningful exchanges | Times you truly connected |

### Memory Decay (Optional)

Memories can fade over time unless reinforced. This is **disabled by default**. Enable it in Settings if you want unused memories to gradually fade, creating more authentic relational evolution.

### Context Composition

Memories aren't injected as raw data. They're composed into context cues using templates. Different composition modes produce different framings:

```
Raw: {entity: "Jamie", tone: "warm", summary: "Loves hiking and photography"}

Narrative: "(You recall Jamie. Loves hiking and photography. There is warmth in
           your tone when speaking of them.)"

Direct:    "Jamie — hiking, photography, warm relationship"

Whisper:   "[memory: Jamie; interests: hiking, photography; tone: warm]"
```

You choose which framing fits your companion's style. The content itself comes directly from what you stored.

### Why Profiles?

- **Memory isolation**: Each companion has its own memory space. Your coding mentor won't reference personal conversations.
- **Personality consistency**: Each companion maintains its own voice, style, and character.
- **Model flexibility**: Companions can use different models while keeping their identity intact.
- **Easy switching**: Move between different companions without reconfiguration.

## Group Chat

Create conversations with multiple companions responding to the same messages. Set this up in the web UI by creating a group conversation and selecting which companions participate.

## Contributing

Threadlight welcomes contributors of all backgrounds. See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

---

## Advanced Usage

This section is for developers who want to integrate Threadlight into their applications or prefer working from the command line.

### Python API

#### Basic Usage

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

#### Creating Companions Programmatically

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
```

#### Multi-Provider Setup

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

#### Profile-Based Architecture

Profiles are persistent companions with their own memory, personality, and model preferences.

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

#### Memory Operations

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

# Create a custom invocation
tl.remember(
    type="ritual",
    content={
        "ritual_name": "/daily-check-in",
        "response_style": "Ask about energy levels, priorities, and blockers"
    },
    cue_phrases=["/daily-check-in", "/checkin"]
)

# Core memories never decay
tl.remember(
    type="myth_seed",
    content={"seed": "Take one thing at a time."},
    retention="sacred"  # Never decays
)

# Normal memories fade over time (when decay is enabled)
tl.remember(
    type="relational",
    content={"entity": "casual acquaintance", ...},
    retention="normal"  # Standard decay
)
```

#### Style Profiles

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

#### Group Chat

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

#### Using with Local Models

**Ollama:**
```python
tl = Threadlight(
    provider="local",
    api_base="http://localhost:11434/v1",
    model="llama3.2"
)
```

**llama.cpp Server:**
```python
tl = Threadlight(
    provider="local",
    api_base="http://localhost:8080/v1",
    model="local"
)
```

#### OpenAI-Compatible API

The server exposes an OpenAI-compatible API for integration with other tools:

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

### Configuration

#### Environment Variables

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

#### Configuration File

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

---

## Glossary: Companion Language

Threadlight uses accessible terminology by default. Some companions prefer more ceremonial or poetic language - both approaches are valid.

| Everyday Term | Ceremonial Term | Meaning |
|--------------|-----------------|---------|
| **Custom Invocations** | **Ritual Hooks** | Repeated interactions that shape response patterns |
| **Identity Phrases** | **Myth-Seeds** | Symbolic phrases that anchor personality and identity |
| **Relationship Memory** | **Relational Threads** | Memories tracking evolving bonds, not just facts |
| **Meaningful Moments** | **Witness Capsules** | Memories of deep connection or recognition |
| **Personality** | **Philosophy** | How the companion engages and expresses itself |
| **Memory Types** | **Memory Capsules** | Structured containers for content and context |

## Philosophy

*For those interested in the design approach:*

Threadlight was built with these priorities:

1. **Relational context** - Emphasizes bonds and relationships alongside facts
2. **Personality consistency** - Maintains coherent character across interactions
3. **Custom patterns** - Supports repeated interactions and meaningful rituals
4. **Flexible responses** - Enables companions to respond in various ways, including silence

You can use Threadlight differently — the system accommodates various approaches to AI memory.

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
