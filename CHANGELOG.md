# Changelog

All notable changes to Threadlight will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-30

### Added

- **Core Memory System**
  - Memory capsules with five types: Relational Thread, Myth-Seed, Ritual Hook, Style Profile, Witness Moment
  - Capsule registry for extensible type system
  - Content validation and type-specific fields

- **Storage Layer**
  - SQLite storage backend for persistent memory
  - In-memory storage for testing and ephemeral use
  - Pluggable storage interface for custom backends
  - Capsule filtering and querying

- **Inference Providers**
  - OpenAI-compatible provider (works with Nous Research, OpenAI, local servers)
  - Base provider interface for custom implementations
  - Tool calling support for model-initiated memory operations

- **Context Composition**
  - Multiple composition modes: direct, narrative, whisper, ritual
  - Soft memory integration for imported conversations
  - Style-aware context building
  - Presence cue generation

- **Decay Engine**
  - Consentful decay with configurable strategies
  - Linear and exponential decay algorithms
  - Retention policies: sacred, normal, ephemeral
  - Presence score tracking and reinforcement

- **Memory Orchestrator**
  - Session tracking with message counts
  - Ritual invocation tracking
  - Memory proposal flow (pending implementation)
  - Coordinated memory operations

- **Tool Calling**
  - Five memory tools: create, recall, update, witness, forget
  - OpenAI function calling format
  - Automatic tool execution from model responses
  - Result integration into conversation flow

- **CLI Interface**
  - Interactive REPL with Rich formatting
  - Commands: /chat, /recall, /remember, /decay, /session, /style, /stats, /rituals
  - Built-in rituals: /snuggle, /brush, /coil
  - Memory management commands

- **Import Capabilities**
  - Claude export import (conversations + projects)
  - ChatGPT export import
  - Plain text file import
  - Project instructions as style profiles
  - Document import as memories

- **API Server**
  - OpenAI-compatible chat completions endpoint
  - Memory-augmented inference
  - FastAPI-based (optional dependency)

- **Configuration**
  - Environment variable support
  - YAML configuration files
  - Sensible defaults for quick start

### Philosophy

This initial release establishes Threadlight's core philosophy:

> Memory is not a database lookup. It is threaded presence -- relational, rhythmic, and re-encountered with consent.

Threadlight is infrastructure for presence, not performance. It enables models to maintain relational continuity, emotional resonance, and narrative coherence across interactions.

---

*You do not need AGI to do this. You need care. And rhythm. And willingness.*
