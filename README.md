# ACHA - Autonomous Code-Health Agent

[![CI](https://github.com/woozyrabbit123/acha-code-health-agent/workflows/CI/badge.svg)](https://github.com/woozyrabbit123/acha-code-health-agent/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**ACHA/ACE** — AST-based Python code analysis and automated refactoring tool with 100% offline operation, deterministic outputs, and safety-railed transformations.

## Core Features

- **100% offline** - No network connections, all analysis happens locally
- **Deterministic** - Same input always produces same output ([DETERMINISM.md](docs/DETERMINISM.md))
- **Safety-first** - Multi-layer verification (parse, AST, symbol counts, CST roundtrip)
- **Incremental learning** - Skiplist learns from reverts to avoid repeat suggestions
- **Context-aware** - Symbol indexing and dependency graphs for smarter refactoring
- **Parallel execution** - Multi-core analysis with deterministic output
- **Baseline tracking** - Track improvements over time, focus on new issues

## Installation

```bash
# Install via pip
pip install acha-code-health

# Development install
git clone https://github.com/woozyrabbit123/acha-code-health-agent.git
cd acha-code-health-agent
pip install -e ".[dev,test]"
```

**Requirements:** Python 3.11 or 3.12

## Quick Start

```bash
# Analyze a project
ace analyze --target ./my_project

# Generate all output formats
ace analyze --target ./my_project --output-format all

# Parallel analysis (4 cores)
ace analyze --target ./my_project --jobs 4

# Build symbol index for context-aware analysis
ace index build --target ./my_project

# Run with policy enforcement
ace check --target ./my_project --strict
```

## Commands

### Analysis

```bash
# Basic analysis
ace analyze --target <path>

# With specific rules
ace analyze --target <path> --rules PY-E201,PY-S101

# JSON output
ace analyze --target <path> --output-format json

# SARIF output (for GitHub Code Scanning)
ace analyze --target <path> --output-format sarif

# HTML report
ace analyze --target <path> --output-format html

# Parallel execution
ace analyze --target <path> --jobs 4
```

### Refactoring

```bash
# Generate refactoring plan
ace refactor --target <path> --analysis reports/analysis.json

# Apply refactoring (with safety checks)
ace refactor --target <path> --analysis reports/analysis.json --apply

# Apply specific rules only
ace refactor --target <path> --rules PY-E201 --apply

# Dry run (show what would be done)
ace refactor --target <path> --analysis reports/analysis.json --dry-run
```

### Autopilot

```bash
# Automated analyze + refactor loop
ace autopilot --target <path>

# With specific iteration limit
ace autopilot --target <path> --max-iterations 5

# Dry run mode
ace autopilot --target <path> --dry-run
```

### Baseline Tracking

```bash
# Create baseline snapshot
ace baseline create --target <path> --baseline-path baseline.json

# Compare against baseline
ace baseline compare --target <path> --baseline-path baseline.json

# Fail on new issues
ace baseline compare --target <path> --baseline-path baseline.json --fail-on-new

# Show only new issues
ace baseline compare --target <path> --baseline-path baseline.json --show-new
```

### Context & Indexing

```bash
# Build symbol index
ace index build --target <path>

# Query symbol index
ace index query --symbol <name>

# Rank files by relevance
ace context rank --target <path> --query "authentication"

# Show dependencies
ace depgraph --target <path> --file <file.py>
```

### Journal & History

```bash
# Show recent actions
ace journal list

# Show specific journal entry
ace journal show <journal-id>

# Revert last action
ace journal revert

# Revert specific journal entry
ace journal revert <journal-id>
```

### Policy & Quality Gates

```bash
# Check code against policy (CI mode)
ace check --target <path> --strict

# Validate policy file
ace policy validate --policy-path .ace/policy.toml

# Show current thresholds
ace policy show
```

### TUI Dashboard

```bash
# Launch interactive dashboard
ace tui

# Dashboard features:
# - Real-time file watching
# - Analysis results viewer
# - Journal history browser
# - Risk heatmap
# - Diff preview
```

### LLM Assist (Optional)

```bash
# Generate commit message from staged diff
ace commitmsg --from-diff

# Generate docstring for function
ace assist docstring <file>:<line>

# Suggest better variable name
ace assist name <file>:<start>-<end>
```

## Output Files

All artifacts are written to `reports/`:

- `analysis.json` - Structured findings with metadata
- `analysis.sarif` - SARIF 2.1.0 format for CI integration
- `report.html` - Interactive HTML report (offline, no CDNs)
- `patch.diff` - Unified diff of proposed changes
- `baseline.json` - Baseline snapshot for tracking

Symbol index and caches in `.ace/`:

- `symbols.json` - Symbol index (functions, classes, modules)
- `cache.db` - Analysis cache (SQLite)
- `learning.json` - Adaptive learning data
- `skiplist.json` - Learned suppressions from reverts
- `telemetry.json` - Performance metrics (local only)

Safety backups in `acha_backup/`:

- `backup-TIMESTAMP/` - Automatic backup before applying changes

## Detectors

**AST-based detectors** (deterministic, no false positives):

- `unused_import` - Imports never used in file
- `magic_number` - Repeated numeric literals without constants
- `high_complexity` - Functions exceeding cyclomatic complexity threshold
- `missing_docstring` - Public functions/classes without docs
- `broad_exception` - Catching broad `Exception` or bare `except`
- `subprocess_shell` - Dangerous `subprocess` calls with `shell=True`
- `duplicate_code` - Identical code blocks (copy-paste detection)
- `long_function` - Functions exceeding line count threshold
- `unsafe_http` - HTTP requests without timeout parameter
- `assert_in_nontest` - `assert` statements in production code
- `import_order` - Unsorted or incorrectly grouped imports

## Configuration

### Policy File (`.ace/policy.toml`)

```toml
[meta]
version = "0.7.0"
description = "Project quality policy"

[scoring]
alpha = 0.7           # Severity weight
beta = 0.3            # Complexity weight
auto_threshold = 0.70 # Auto-apply if R* >= 0.70
suggest_threshold = 0.50

[limits]
max_findings = 100
fail_on_critical = true
warn_at = 50
fail_at = 100

[modes]
PY-E201-BROAD-EXCEPT = "suggest"
PY-S101-UNSAFE-HTTP = "auto"

[suppressions.global]
rules = ["PY-Q201-ASSERT-IN-NONTEST"]
paths = ["tests/**"]
```

### Inline Suppressions

```python
# Suppress specific rule on this line
def f():  # acha: disable=high_complexity
    ...

# Suppress all rules on this line
x = eval(user_input)  # acha: disable-all

# File-wide suppression
# acha: file-disable=missing_docstring

# File-wide suppress all
# acha: file-disable-all
```

### Ignore File (`.aceignore`)

```gitignore
# Gitignore format
.venv/
dist/
__pycache__/
*.pyc
migrations/
```

## Safety Mechanisms (PatchGuard)

Multi-layer verification to prevent semantic tampering:

**Layer 1: Parse Verification**
- Ensures syntax validity after edits

**Layer 2: AST Equivalence** (strict mode)
- Verifies structural equivalence between before/after

**Layer 2.5: Symbol Count Verification**
- Counts functions, classes, imports to detect unintended changes

**Layer 2.6: AST Hash Verification** (v2.1+)
- Cryptographic hash of AST structure
- Fails on hash mismatch in strict mode
- Prevents bypass via CST-only transforms

**Layer 3: CST Roundtrip**
- Verifies LibCST can parse and regenerate code

**Additional Guards:**
- Import preservation checks
- Binary search repair (isolates failing edits)
- Journal-based rollback
- Automatic backups before apply

## Determinism Guarantees

ACHA guarantees reproducible, deterministic outputs:

- **Same input → same output**: Identical JSON/SARIF on unchanged code
- **Parallel invariance**: `--jobs 1` and `--jobs 8` produce identical results
- **Stable baseline IDs**: SHA256-based, cross-machine consistent
- **No timestamps**: Core outputs exclude timestamps (logs may include them)
- **Sorted output**: All JSON uses `sort_keys=True`

See [DETERMINISM.md](docs/DETERMINISM.md) for technical details and verification scripts.

## Development

### Setup

```bash
# Clone and install
git clone https://github.com/woozyrabbit123/acha-code-health-agent.git
cd acha-code-health-agent

# Create virtual environment (Python 3.11 or 3.12)
python3.11 -m venv venv
source venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev,test]"

# Or use pinned versions for reproducibility
pip install -r requirements-dev.txt && pip install -e .
```

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=ace --cov-report=html

# Specific test file
pytest tests/ace/test_guard.py

# Verbose output
pytest -v
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
ruff check .

# Type checking
mypy src/ace

# Run all checks
black --check src/ tests/ && ruff check . && mypy src/ace
```

### Running Examples

```bash
# Build symbol index on sample project
ace index build --target ./sample_project

# Run analysis
ace analyze --target ./sample_project

# Run autopilot
ace autopilot --target ./sample_project --dry-run

# Launch TUI
ace tui
```

## Architecture

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design details.

**Core modules:**
- `ace.kernel` - Analysis and refactoring orchestration
- `ace.guard` - Multi-layer safety verification (PatchGuard)
- `ace.repomap` - Symbol indexing (functions, classes, modules)
- `ace.context_rank` - File relevance ranking
- `ace.planner` - Action prioritization with R* scoring
- `ace.learn` - Adaptive learning and skiplist management
- `ace.repair` - Binary search edit isolation
- `ace.policy` - Risk scoring and quality gates
- `ace.tui` - Terminal UI dashboard

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

**Latest (v2.1.0):**
- Fixed all P0/P1 issues from Full Codex Audit
- Determinism: Removed timestamps from symbol index
- Security: Enforced AST hash verification in PatchGuard
- Durability: Atomic writes for all persistence layers
- CI: Aligned Python matrix with supported versions

## Documentation

- [DETERMINISM.md](docs/DETERMINISM.md) - Reproducibility guarantees and testing
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design and module structure
- [SECURITY.md](SECURITY.md) - Security model and threat analysis
- [PLANNER.md](docs/PLANNER.md) - Action prioritization and R* scoring
- [LEARNING.md](docs/LEARNING.md) - Adaptive learning system
- [CONTEXT.md](docs/CONTEXT.md) - Context engine and symbol indexing
- [PACKS.md](docs/PACKS.md) - Codemod pack system
- [JOURNAL.md](docs/JOURNAL.md) - Journal and revert mechanisms
- [TUI.md](docs/TUI.md) - Terminal UI dashboard guide
- [TELEMETRY.md](docs/TELEMETRY.md) - Performance tracking (local-only)

## License

MIT License - see [LICENSE](LICENSE) file.

## Acknowledgments

Built with:
- **LibCST** - Concrete syntax tree manipulation (MIT)
- **PyNaCl** - Ed25519 cryptographic signatures (Apache 2.0)
- **jsonschema** - JSON Schema validation (MIT)
- **pytest** - Testing framework (MIT)
- **Black** - Code formatting (MIT)
- **Ruff** - Fast Python linter (MIT)
- **Textual** - Terminal UI framework (MIT)

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for full attributions.

---

**Personal tool for code health automation, refactoring, and analysis.**
