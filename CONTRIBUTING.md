# Contributing to RPI Weather Display

Thank you for your interest in contributing to the RPI Weather Display project!

## Code of Conduct

Please keep interactions respectful and professional.

## How to Contribute

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Submit a pull request

## Development Requirements

- Python 3.11+
- Poetry for dependency management
- Ruff for linting
- Pyright for type checking
- Pytest for testing

## Setting Up the Development Environment

```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install --with dev --extras server

# For server components
poetry install --extras server

# Install Playwright browsers (required for rendering)
poetry run playwright install
```

## Testing

```bash
# Run all tests
poetry run pytest

# Run specific test files
poetry run pytest tests/client/

# Run tests with coverage
poetry run pytest --cov=src
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints for all functions and methods
- Write docstrings in Google style format
- Keep line length to 100 characters
- Use Ruff for formatting and linting
- Use Pyright for type checking

## Pull Request Process

1. Update documentation to reflect your changes, if applicable
2. Make sure all tests pass with `poetry run pytest`
3. Ensure your code passes linting with `poetry run ruff check .`
4. Add your changes to the CHANGELOG.md under the "Unreleased" section
5. Submit a pull request to the `main` branch

## Versioning Workflow

We use a tag-based workflow for versioning:

1. All development happens in feature branches or directly on `main`
2. We do not create release branches
3. When a release is ready, we:
   - Update the version in `pyproject.toml` and `src/rpi_weather_display/__init__.py`
   - Update CHANGELOG.md with the new version
   - Commit these changes to `main`
   - Create and push a tag for the new version (e.g., `v0.3.0`)
   - Create a GitHub release based on the tag

## Commit Messages

Use clear, concise commit messages that explain what the commit does. When possible, follow conventional commits format:

```
feat: add new feature
fix: correct an issue
docs: update documentation
test: add or update tests
refactor: code changes that don't affect functionality
```

## Thank You

Thank you for contributing to the RPI Weather Display project!