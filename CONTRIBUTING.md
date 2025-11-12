# Contributing to ACHA

Thank you for your interest in contributing to the Autonomous Code-Health Agent (ACHA)!

## Development Setup

### Prerequisites

- Python 3.11 or 3.12 (see `requires-python` in `pyproject.toml`)
- Git
- pip

### Setting Up Development Environment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/woozyrabbit123/acha-code-health-agent.git
   cd acha-code-health-agent
   ```

2. **Install in development mode:**

   **Option A: Install with extras (recommended):**
   ```bash
   pip install -e .[dev,test,pro]
   ```

   **Option B: Install with pinned versions (for reproducibility):**
   ```bash
   pip install -r requirements-dev.txt && pip install -e .
   ```

3. **Run tests to verify setup:**
   ```bash
   pytest
   ```

**Note:** As of v2.1.0, all ACE command-line tool dependencies (`libcst`, `markdown-it-py`, `pyyaml`, `textual`) are included in the base installation. No need for `[ace]` extras.

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test file
pytest tests/test_analysis.py

# Run with verbose output
pytest -v
```

### Code Quality

We use several tools to maintain code quality:

```bash
# Format code with black
black .

# Lint with ruff
ruff check .

# Type checking with mypy
mypy agents utils cli.py
```

### Making Changes

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** and ensure tests pass:
   ```bash
   pytest
   ```

3. **Commit your changes** using conventional commits:
   ```bash
   git commit -m "feat: add new feature"
   git commit -m "fix: resolve bug"
   git commit -m "docs: update documentation"
   ```

4. **Push and create a pull request:**
   ```bash
   git push origin feature/your-feature-name
   ```

## Pull Request Guidelines

### Before Submitting

- [ ] Tests pass locally (`pytest`)
- [ ] Code is formatted (`black .`)
- [ ] No linting errors (`ruff check .`)
- [ ] Documentation is updated if needed
- [ ] Commit messages follow conventional commits format

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe testing performed

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (for significant changes)
```

## Commit Message Format

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Test additions or changes
- `chore:` - Build/tooling changes

Examples:
```
feat(analysis): add support for type annotations
fix(refactor): handle multi-line import statements correctly
docs: update installation instructions
```

## Project Structure

```
acha-code-health-agent/
├── agents/           # Analysis, refactoring, validation agents
├── utils/            # Utility modules (policy, caching, reporters)
├── schemas/          # JSON schemas for validation
├── tests/            # Test suite
├── sample_project/   # Example project for testing
├── .github/          # GitHub Actions workflows
├── scripts/          # Build and release scripts
├── pyproject.toml    # Project configuration
└── README.md         # Project documentation
```

## Testing Guidelines

### Writing Tests

- Place tests in `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use pytest fixtures for common setup
- Aim for >80% code coverage

### Test Organization

```python
def test_feature_name():
    """Test that feature works correctly."""
    # Arrange
    input_data = ...

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result == expected_output
```

## Adding New Features

### Analyzers

1. Add analysis logic to `agents/analysis_agent.py`
2. Add rule definition to `utils/sarif_reporter.py`
3. Add tests to `tests/test_analyzers_expanded.py`
4. Update documentation

### Refactorings

1. Add refactoring logic to `agents/refactor_agent.py`
2. Add refactor type to `RefactorType` enum
3. Add tests to `tests/test_refactors_safe.py`
4. Update CLI help text

## Documentation

- Update `README.md` for user-facing changes
- Update docstrings for API changes
- Add examples to `sample_project/` if needed
- Update `CHANGELOG.md` for significant changes

## Release Process

Releases are managed by maintainers using the release script:

```bash
# Bump version and create release
python scripts/release.py release patch  # or minor, major

# Manual steps
python scripts/release.py bump patch
python scripts/release.py changelog
python scripts/release.py tag
```

## Getting Help

- Open an issue for bugs or feature requests
- Join discussions in GitHub Discussions
- Read existing documentation and tests for examples

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help others learn and grow

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
