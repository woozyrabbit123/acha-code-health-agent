# ACHA - Autonomous Code-Health Agent

[![CI](https://github.com/woozyrabbit123/acha-code-health-agent/workflows/CI/badge.svg)](https://github.com/woozyrabbit123/acha-code-health-agent/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/woozyrabbit123/acha-code-health-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/woozyrabbit123/acha-code-health-agent)
[![PyPI version](https://badge.fury.io/py/acha-code-health.svg)](https://badge.fury.io/py/acha-code-health)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Autonomous Code-Health Agent (ACHA)** — AST-based Python code analysis and automated refactoring tool with **100% offline operation**, baseline tracking, and safety-railed refactoring.

## 🔐 Privacy-First Design

- **100% offline** - No network connections, ever
- **Zero telemetry** - Your code never leaves your machine
- **Offline licensing** - Ed25519 cryptographic signatures (Pro only)
- **Local-only processing** - All analysis happens on your hardware
- **Deterministic outputs** - Same input always produces same output (see [DETERMINISM.md](docs/DETERMINISM.md))

## 📚 Documentation

- **[QUICKSTART (Pro)](docs/QUICKSTART_PRO.md)** - Get started with ACHA Pro in 5 minutes
- **[SECURITY](SECURITY.md)** - Local-first security model and threat analysis
- **[DETERMINISM](docs/DETERMINISM.md)** - Reproducible output guarantees
- **[EULA](EULA.md)** - License terms for ACHA Pro
- **[Third-Party Notices](THIRD_PARTY_NOTICES.md)** - Open-source dependency attributions

## 🌟 Community vs Pro

| Feature | Community (Free) | Pro (Licensed) |
|---------|------------------|----------------|
| **AST-based analysis** | ✅ | ✅ |
| **JSON/SARIF reports** | ✅ | ✅ |
| **Refactoring planning (`--fix`)** | ✅ | ✅ |
| **Inline suppressions** | ✅ | ✅ |
| **Policy enforcement** | ✅ | ✅ |
| **Single-threaded analysis** | ✅ | ✅ |
| **HTML reports (offline)** | ❌ | ✅ |
| **Baseline tracking** | ❌ | ✅ |
| **Pre-commit integration** | ❌ | ✅ |
| **Parallel scanning (`--jobs > 1`)** | ❌ | ✅ |
| **Refactoring apply (`--apply`)** | ❌ | ✅ |
| **Email support** | ❌ | ✅ (1 year) |

**Community Edition:** MIT open-source, full analysis and planning features, perfect for individual developers.

**Pro Edition:** Offline licensing, enhanced workflows (HTML, baseline, pre-commit), safety-railed refactoring, commercial use, priority support.

## Quickstart

### Installation

**Option 1: Pre-built Binaries (Recommended for Pro)**

Download from [GitHub Releases](https://github.com/woozyrabbit123/acha-code-health-agent/releases) — binaries available for Linux, macOS, and Windows. No Python installation required.

**Option 2: Python Installation (Community)**

```bash
# Community edition
pip install acha-code-health

# Pro edition (requires license)
pip install acha-code-health[pro]
```

**Requirements:** Python 3.11 or 3.12

### Quick Demo

```bash
# Analyze a Python project
acha analyze --target ./my_project

# Generate HTML report (Pro only)
acha analyze --target ./my_project --output-format html

# Create baseline for tracking improvements
acha baseline create --analysis reports/analysis.json

# Run pre-commit check (Pro only)
acha precommit --target . --baseline baseline.json

# Apply automated refactoring with safety rails (Pro only)
acha refactor --target . --analysis reports/analysis.json --apply
```

### Basic Usage

```bash
# Analyze code
acha analyze --target ./my_project --output-format json

# Parallel analysis (Pro, uses 4 cores)
acha analyze --target ./my_project --jobs 4

# Generate multiple formats
acha analyze --target ./my_project --output-format all

# Compare against baseline
acha baseline create --analysis reports/analysis.json
acha baseline compare --analysis reports/analysis.json --baseline baseline.json

# Pre-commit integration
acha precommit --target . --baseline baseline.json
```

### Outputs

All artifacts are written to `reports/`:
- `analysis.json` - Structured findings (Community)
- `analysis.sarif` - SARIF format for GitHub Code Scanning (Community)
- `report.html` - Interactive HTML report with filtering (Pro)
- `baseline.json` - Baseline snapshot for tracking changes (Pro)
- `baseline_comparison.json` - NEW/EXISTING/FIXED comparison (Pro)

Refactoring outputs in `dist/`:
- `patch.diff` - Unified diff of proposed changes (Community)

Safety backups in `backups/`:
- `backup-TIMESTAMP/` - Automatic backup before applying changes (Pro)

## Features

### Core Analysis (Community + Pro)

**AST-based detectors** (deterministic, no false positives):
- **unused_import** - Detects imports that are never used in the file
- **magic_number** - Repeated numeric literals without named constants
- **high_complexity** - Functions exceeding cyclomatic complexity threshold
- **missing_docstring** - Public functions/classes without documentation
- **broad_exception** - Catching broad `Exception` or bare `except`
- **broad_subprocess_shell** - Dangerous `subprocess` calls with `shell=True`
- **duplicate_code** - Identical code blocks (copy-paste detection)
- **long_function** - Functions exceeding line count threshold

**Inline suppressions:**
```python
def legacy_function():  # acha: disable=high_complexity
    # Complex legacy code that can't be refactored yet
    ...
```

**Policy enforcement:**
```json
{
  "fail_on_risky": true,
  "max_errors": 0,
  "max_warnings": 10,
  "max_complexity": 15
}
```

### Pro Features

**1. HTML Reports (Offline)**
- Beautiful, interactive reports with **no CDN dependencies**
- Filter by severity, rule type, or baseline status
- Show suppressed findings with badges
- Works 100% offline in any browser

**2. Baseline Tracking**
- Track code health over time
- Create baselines, compare changes, focus only on **new issues**
- Perfect for legacy codebases and gradual improvements
- Deterministic baseline IDs (SHA256-based)

**3. Pre-commit Integration**
- Block commits with high-severity findings
- Scan only staged files for fast feedback
- Integrates seamlessly with git hooks
- Respects inline suppressions

**4. Parallel Scanning**
- Use all CPU cores with `--jobs N`
- **Deterministic output** guaranteed (parallel and sequential produce identical results)
- Significantly faster on large codebases

**5. Safety Rails for Refactoring**
- Dirty tree detection (warns if uncommitted changes)
- Automatic backups before changes (`backups/backup-TIMESTAMP/`)
- User confirmation prompts (unless `--yes`)
- Rollback mechanisms for failed refactorings

## Configuration & Policies

**Policy files** define quality gates and thresholds:

```json
{
  "fail_on_risky": true,
  "max_errors": 0,
  "max_warnings": 10,
  "max_complexity": 15,
  "severity_threshold": 0.7
}
```

**Inline suppressions** allow granular control:

```python
# Suppress specific rule
def f():  # acha: disable=high_complexity
    ...

# Suppress all rules for one line
x = eval(user_input)  # acha: disable-all

# File-wide suppression
# acha: file-disable=missing_docstring
```

**Suppression types:**
- `# acha: disable=<rule>` - Suppress one rule on this line
- `# acha: disable-all` - Suppress all rules on this line
- `# acha: file-disable=<rule>` - Suppress one rule for entire file
- `# acha: file-disable-all` - Suppress all rules for entire file

## Deterministic Outputs

ACHA guarantees **reproducible, deterministic outputs** for CI/CD and security auditing:

- **Same input → same output**: Running analysis twice on unchanged code produces identical JSON/SARIF (except timestamps)
- **Parallel invariance**: `--jobs 1` and `--jobs 8` produce identical findings in identical order (thread-safe, deterministic execution)
- **Unique finding IDs**: Thread-safe ID generation ensures no collisions in parallel execution
- **Stable baseline IDs**: Baseline IDs are SHA256 hashes, ensuring reproducibility across machines
- **Cross-platform consistency**: Analysis results are consistent across Linux, macOS, and Windows

See [DETERMINISM.md](docs/DETERMINISM.md) for technical details and testing methodology.

## Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/woozyrabbit123/acha-code-health-agent.git
cd acha-code-health-agent

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev,test,pro]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=acha --cov-report=html

# Run specific test file
pytest tests/test_analysis_agent.py

# Run with verbose output
pytest -v
```

### Code Quality

```bash
# Format code
black src/acha tests

# Lint code
ruff check src/acha tests

# Type checking
mypy src/acha

# Run all quality checks
black --check src/acha tests && ruff check src/acha tests && mypy src/acha
```

## Contributing

ACHA is open-source (MIT license). Contributions are welcome!

**Community Edition (MIT):**
- Analysis rules and detectors
- JSON/SARIF output formats
- Refactoring planning
- Core CLI features

**Pro Edition (Proprietary):**
- HTML report generation
- Baseline tracking
- Pre-commit integration
- Parallel execution (jobs > 1)
- Refactoring apply with safety rails
- License verification system

Pull requests should target the Community Edition features only. Pro features are maintained separately.

**Before contributing:**
1. Open an issue to discuss the change
2. Fork the repository
3. Create a feature branch
4. Write tests for new functionality
5. Ensure all tests pass and code is formatted
6. Submit a pull request

## License

**Community Edition:** MIT License (see [LICENSE](LICENSE))

**Pro Edition:** Proprietary license (see [EULA.md](EULA.md))

By purchasing ACHA Pro, you support the development of the open-source Community Edition.

## Support

**Community Edition:**
- GitHub Issues: https://github.com/woozyrabbit123/acha-code-health-agent/issues
- Community support (best effort)

**Pro Edition:**
- Email support: support@example.com (placeholder - see EULA for actual contact)
- 48-hour response time (business days)
- 1 year support included with purchase

## Security

ACHA Pro is designed with **privacy and security as top priorities**:

- **No network connections** - All processing happens locally
- **No telemetry** - Your code never leaves your machine
- **Offline licensing** - Ed25519 cryptographic signatures
- **No external dependencies** - HTML reports work offline (no CDNs)
- **Reproducible outputs** - Deterministic analysis for security auditing

For vulnerability reporting and security policy, see [SECURITY.md](SECURITY.md).

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and release notes.

## Roadmap

**v1.0.x (Current - Maintenance)**
- Bug fixes and stability improvements
- Documentation enhancements
- Performance optimizations

**v1.1.0 (Planned)**
- Team licenses (5/10/unlimited seats)
- Custom rule creation (Python DSL)
- IDE integrations (VS Code, PyCharm)
- Enhanced HTML reports with charts

**v1.2.0 (Future)**
- Multi-language support (JavaScript, TypeScript)
- CI/CD dashboard
- Advanced refactoring patterns
- Semantic code search

## Acknowledgments

ACHA uses the following open-source projects:

- **PyNaCl** - Ed25519 cryptographic signatures (Apache 2.0)
- **jsonschema** - JSON Schema validation (MIT)
- **pytest** - Testing framework (MIT)
- **Black** - Code formatting (MIT)
- **Ruff** - Fast Python linter (MIT)

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for full attribution and license texts.

---

**Made with ❤️ for developers who value privacy, reproducibility, and code quality.**
