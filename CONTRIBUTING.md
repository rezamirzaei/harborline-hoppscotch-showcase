# Contributing to Harborline Commerce Core

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd PythonProject10
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   make dev  # or: pip install -e ".[dev]"
   ```

4. **Copy environment files**
   ```bash
   cp config/api.env.example config/api.env
   cp config/hoppscotch.env.example config/hoppscotch.env
   ```

5. **Run the API locally**
   ```bash
   make run  # or: uvicorn harborline.main:app --reload
   ```

## Development Workflow

### Running Tests
```bash
make test        # Run all tests
make test-cov    # Run tests with coverage report
```

### Hoppscotch Contract Tests (Recommended)
Use the committed Hoppscotch collection as an end-to-end regression suite (REST + scripts + idempotency + webhooks + GraphQL).
```bash
make hopp           # Spins up a temporary API instance and runs the collection
make hopp-existing  # Runs against an already running API (PORT=8000 by default)
```

### Code Quality
```bash
make lint        # Check for linting errors
make format      # Auto-format code
make type        # Run type checker
make check       # Run lint + tests
```

### Docker
```bash
make docker-build   # Build Docker image
make docker-up      # Start services
make docker-down    # Stop services
make docker-logs    # View logs
```

## Code Style

- We use **Ruff** for linting and formatting
- Follow PEP 8 naming conventions
- Add type hints to all function signatures
- Write docstrings for public modules, classes, and functions

## Project Structure

```
harborline/
├── main.py          # FastAPI app factory
├── domain.py        # Pydantic models & enums
├── services.py      # Business logic
├── repositories.py  # Data access layer
├── container.py     # Dependency injection
├── settings.py      # Configuration
├── errors.py        # Custom exceptions
├── clock.py         # Time abstraction
├── id_provider.py   # ID generation
├── logging.py       # Logging configuration
└── ui/              # MVC web interface
    ├── controllers.py
    ├── models.py
    └── templates/
```

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with appropriate tests
3. Ensure all checks pass: `make check`
4. Submit a pull request with a clear description

## Commit Messages

Use clear, descriptive commit messages:
- `feat: add payment refund endpoint`
- `fix: handle empty inventory list`
- `docs: update API examples`
- `test: add GraphQL query tests`
- `refactor: extract order validation`

## Questions?

Open an issue for questions or discussions.
