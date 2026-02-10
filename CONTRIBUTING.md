# Contributing to Threadlight

Thank you for your interest in contributing to Threadlight. This project welcomes contributors of all backgrounds and experience levels.

## About Threadlight

Threadlight is a memory and personality layer for AI assistants. It supports diverse use cases:

- Practical assistants with persistent memory
- Creative companions for writing and brainstorming
- Specialized personas for different tasks
- Experimental AI relationship research

Whether you want simple memory features or rich relational interactions, Threadlight is designed to accommodate both.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/threadlight/threadlight.git
   cd threadlight
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. Set up pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Code Structure

```
src/threadlight/
├── core.py              # Main Threadlight class (coordination layer)
├── config.py            # Configuration (ThreadlightConfig, ProviderDefinition)
├── managers/            # Domain-specific managers
│   ├── chat.py          # ChatManager - completion, tools, context
│   ├── profiles.py      # ProfileInterface - profile CRUD and switching
│   ├── style.py         # StyleManager - style profile management
│   ├── model_config.py  # ModelConfigManager - per-model settings
│   ├── memory_types.py  # CustomTypeManager - custom capsule types
│   └── group_chat.py    # GroupChatManager - multi-profile conversations
├── providers/           # Inference providers
│   ├── base.py          # BaseProvider, ProviderMessage, ProviderResponse
│   ├── manager.py       # ProviderManager - multi-provider routing
│   └── openai.py        # OpenAI-compatible provider
├── profiles/            # Profile system
│   ├── profile.py       # Profile dataclass, ModelStrategy, AlloyedConfig
│   ├── manager.py       # ProfileManager (storage operations)
│   └── alloyed.py       # AlloyedProfileEngine (model selection)
├── capsules/            # Memory capsule types
│   ├── base.py          # BaseCapsule, CapsuleType, MemoryCapsule
│   ├── relational.py    # RelationalThread
│   ├── myth_seed.py     # MythSeed (identity phrases)
│   ├── ritual.py        # RitualHook (custom commands)
│   ├── style.py         # StyleProfile
│   ├── witness.py       # WitnessMoment
│   └── custom_types.py  # Custom type definitions
├── memory/              # Memory orchestration
│   └── orchestrator.py  # MemoryOrchestrator
├── context/             # Context composition
│   ├── composer.py      # ContextComposer
│   └── soft_memory.py   # SoftMemory (conversation recall)
├── storage/             # Persistence
│   ├── base.py          # StorageBackend interface
│   └── sqlite.py        # SQLite implementation
├── decay/               # Memory decay engine
│   └── engine.py        # DecayEngine
├── tools/               # Model tool calling
│   ├── definitions.py   # Tool schemas
│   └── executor.py      # Tool execution
├── embeddings/          # Semantic search
│   └── manager.py       # EmbeddingManager
├── api/                 # HTTP API
│   └── server.py        # FastAPI server
└── cli.py               # Command-line interface
```

## Code Style

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting.

### Key Guidelines

- **Line length**: 100 characters max
- **Imports**: Sorted with isort (via Ruff)
- **Type hints**: Required for all public functions
- **Docstrings**: Google style docstrings for public API

### Running Linters

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .

# Type checking
mypy src/threadlight
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/threadlight --cov-report=term-missing

# Run specific test file
pytest tests/test_profiles.py

# Run tests excluding integration tests
pytest -m "not integration"

# Run only integration tests (requires API key)
pytest -m integration
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Use descriptive test names: `test_profile_switching_updates_memory_scope`
- Mock external services (API calls, databases) in unit tests
- Mark integration tests with `@pytest.mark.integration`

## How to Contribute

### Reporting Bugs

1. Check if the issue already exists
2. Create a new issue with:
   - Clear description of the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Python version and OS
   - Relevant logs or error messages

### Suggesting Features

1. Open an issue describing:
   - The problem you're trying to solve
   - Your proposed solution
   - Example use cases
2. Wait for discussion before implementing

### Submitting Code

1. Fork the repository

2. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. Make your changes:
   - Write clear, self-documenting code
   - Add tests for new functionality
   - Update documentation if needed
   - Follow the code style guidelines

4. Commit with clear messages:
   ```bash
   git commit -m "Add profile export to JSON format"
   ```

5. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

6. Open a Pull Request:
   - Reference any related issues
   - Describe what changes you made and why
   - Ensure all tests pass

### Pull Request Guidelines

- Keep PRs focused - one feature or fix per PR
- Write descriptive PR titles
- Include tests for new code
- Update documentation for user-facing changes
- Be responsive to feedback

## Areas for Contribution

### Good First Issues

Look for issues labeled `good first issue` - these are suitable for newcomers.

### Current Priorities

- Additional storage backends (PostgreSQL, Redis)
- Provider adapters (more cloud providers)
- Embedding model integrations
- Documentation improvements
- Test coverage expansion
- CLI improvements

### Extension Points

Threadlight is designed to be extensible:

- **Custom Capsule Types**: Create new memory types for specific use cases
- **Custom Providers**: Add support for new inference backends
- **Custom Decay Strategies**: Implement alternative decay algorithms
- **Storage Backends**: Add new persistence options

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for extension examples.

## Documentation

Please read before contributing:

1. [README.md](README.md) - Project overview and quick start
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Technical architecture
3. [docs/DECISIONS.md](docs/DECISIONS.md) - Key architectural decisions

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Assume good intentions
- Welcome newcomers warmly

## Questions?

- Open an issue for general questions
- Check existing discussions first
- Be patient - maintainers are volunteers

---

*Threadlight welcomes contributions that serve any use case - practical, creative, or experimental. Thank you for helping make it better.*
