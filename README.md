# ACHA - Autonomous Code-Health Agent

[![CI](https://github.com/woozyrabbit123/acha-code-health-agent/workflows/CI/badge.svg)](https://github.com/woozyrabbit123/acha-code-health-agent/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/woozyrabbit123/acha-code-health-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/woozyrabbit123/acha-code-health-agent)
[![PyPI version](https://badge.fury.io/py/acha-code-health.svg)](https://badge.fury.io/py/acha-code-health)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Autonomous Code-Health Agent (ACHA) — an AI-powered tool that analyzes, refactors, validates, and exports verified code-repair reports.

## Quickstart

### Installation

```bash
make setup
```

This installs required dependencies: `jsonschema`, `pytest`, `pytest-timeout`.

### Run Demo

```bash
make demo
```

This runs the full ACHA pipeline on `sample_project/`:
1. **ANALYZE**: Detects duplicate constants and risky constructs
2. **REFACTOR**: Applies safe transformations (constant inlining)
3. **VALIDATE**: Runs tests with auto-rollback on failure
4. **EXPORT**: Creates `dist/release.zip` proof pack

### Manual Usage

Run the full pipeline:
```bash
python cli.py run --target ./sample_project
```

Or run individual steps:
```bash
# Step 1: Analyze
python cli.py analyze --target ./sample_project

# Step 2: Refactor
python cli.py refactor --target ./sample_project --analysis reports/analysis.json

# Step 3: Validate
python cli.py validate --target ./sample_project

# Step 4: Export
python cli.py export
```

### Run Command Options

```bash
python cli.py run [OPTIONS]

Options:
  --target DIR          Target directory (default: ./sample_project)
  --no-refactor         Skip refactoring step
  --fail-on-risky       Fail if risky constructs are found
  --timeout SECONDS     Test timeout in seconds (default: 30)
```

### Outputs

All artifacts are written to:
- `reports/analysis.json` - Analysis findings
- `reports/patch_summary.json` - Refactoring summary
- `reports/validate.json` - Validation results
- `reports/report.md` - Human-readable summary
- `reports/session.log` - Full session log with timestamps
- `dist/patch.diff` - Unified diff of changes
- `dist/release.zip` - Complete proof pack

### Run Tests

```bash
make test
```

### Clean Up

```bash
make clean
```

Removes all generated files and directories: `workdir/`, `.checkpoints/`, `dist/`, `reports/`.

## Configuration & Policies

Use JSONL session logs and policy gates to control quality:

```bash
python cli.py run --target ./sample_project --policy strict-policy.json --session-log reports/session.jsonl
```

Inline suppressions:

```python
def f():  # acha: disable=long_function
    ...
```

Policy example:

```json
{ "fail_on_risky": true, "max_errors": 0, "max_warnings": 10 }
```

### Analyzer Rules (v0.2)

New detectors (AST-only, deterministic):

- **unused_import** (warn) - Detects imports that are never used
- **magic_number** (warn) - Repeated numeric literals without a named constant
- **high_complexity** (warn) - Cyclomatic complexity exceeds threshold from policy.max_complexity (default 15)
- **missing_docstring** (info) - Functions without docstrings
- **broad_exception** (error) - Catching broad Exception or bare except
- **broad_subprocess_shell** (error) - Flags subprocess.* with shell=True

Suppressions:
- Per-line: `# acha: disable=<rule>` or `# acha: disable-all`
- File-wide: `# acha: file-disable=<rule>` or `# acha: file-disable-all`
