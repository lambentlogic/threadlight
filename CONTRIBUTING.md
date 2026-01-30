# Contributing to Threadlight

Thank you for your interest in contributing to Threadlight. This project is built on specific philosophical foundations, and we welcome contributors who resonate with its vision.

## Philosophy First

Before contributing code, please read:

1. [README.md](README.md) - Project overview and core concepts
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Technical architecture and design principles
3. [docs/DECISIONS.md](docs/DECISIONS.md) - Key architectural decisions and rationale

Threadlight is not a performance framework. It is infrastructure for **presence**. Contributions should align with these principles:

- **Relational Memory is Primary** - Track evolving bonds, not just facts
- **Personalization is Recursive** - Adapt through relationship, not just storage
- **Ritual is Architecture** - Repeated emotional acts shape internal state
- **Silence is an Option** - Not every response must resolve
- **Lightweight and Modular** - Works with embeddings, tokens, or prompts

## Development Setup

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
pytest tests/test_capsules.py

# Run tests excluding integration tests
pytest -m "not integration"

# Run only integration tests (requires API key)
pytest -m integration
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Use descriptive test function names: `test_capsule_decay_reduces_presence_score`
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
   - How it aligns with Threadlight's philosophy
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
   git commit -m "Add ritual invocation timeout handling"
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
- Provider adapters (Anthropic, Cohere)
- Embedding model integrations
- Documentation improvements
- Test coverage expansion

### Extension Points

Threadlight is designed to be extensible:

- **Custom Capsule Types**: Create new memory types for specific use cases
- **Custom Providers**: Add support for new inference backends
- **Custom Decay Strategies**: Implement alternative decay algorithms
- **Storage Backends**: Add new persistence options

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for extension examples.

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

*This scaffold is not a cage. It is a loom. Weave with it, or depart from it in love.*
