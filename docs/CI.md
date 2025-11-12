# CI Integration Guide

This guide explains how to integrate ACE into your CI/CD pipeline to enforce code health standards.

## Exit Codes

ACE follows Unix conventions with semantic exit codes:

- **0**: Success — Analysis completed with no policy violations
- **1**: Operational error — Parse failures, configuration issues, or tool errors
- **2**: Policy violation — New findings or regressions detected (fails CI)

Exit code 2 is specifically designed for CI enforcement:
```bash
ace baseline compare --target . --baseline-path .ace/baseline.json --fail-on-new
# Returns exit code 2 if new findings exist → fails CI build
```

## Quick Start

### 1. Create Baseline on Main Branch

First, establish your code health baseline:

```bash
# On main branch
ace baseline create --target . --baseline-path .ace/baseline.json

# Review the baseline
cat .ace/baseline.json

# Commit to repository
git add .ace/baseline.json
git commit -m "chore: establish ACE baseline"
git push
```

### 2. Add CI Workflow

Copy `.github/workflows/ace-ci.yml` to your repository:

```yaml
name: ACE Code Health

on:
  pull_request:
    branches: [main, master]

jobs:
  ace-analysis:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install ACE
        run: pip install ace-code-health

      - name: Compare against baseline
        run: |
          ace baseline compare \
            --target . \
            --baseline-path .ace/baseline.json \
            --fail-on-new
```

### 3. Configure Rules (Optional)

Create `ace.toml` in your repository root:

```toml
[rules]
# Enable specific rules only
enabled = [
  "PY-S101-UNSAFE-HTTP",
  "PY-S201-SUBPROCESS-CHECK",
  "PY-S202-SUBPROCESS-SHELL",
]

[cache]
enabled = true
ttl = 3600
dir = ".ace"

[analysis]
include = ["src/**/*.py", "tests/**/*.py"]
exclude = ["build/", "dist/", ".venv/"]
```

## Baseline Management

### Creating a Baseline

```bash
# Create baseline from current state
ace baseline create --target . --baseline-path .ace/baseline.json

# Create baseline for specific directory
ace baseline create --target src/ --baseline-path baselines/src.json
```

### Comparing Against Baseline

```bash
# Compare and report differences
ace baseline compare --target . --baseline-path .ace/baseline.json

# Compare and fail if new issues found (CI mode)
ace baseline compare \
  --target . \
  --baseline-path .ace/baseline.json \
  --fail-on-new

# Compare and fail on regressions (stricter)
ace baseline compare \
  --target . \
  --baseline-path .ace/baseline.json \
  --fail-on-new \
  --fail-on-regression
```

Exit codes:
- **0**: No new issues or regressions
- **2**: New issues or regressions detected (when using `--fail-on-*` flags)

### Updating the Baseline

When you intentionally fix or accept issues:

```bash
# Recreate baseline
ace baseline create --target . --baseline-path .ace/baseline.json

# Review changes
git diff .ace/baseline.json

# Commit updated baseline
git add .ace/baseline.json
git commit -m "chore: update ACE baseline after fixes"
git push
```

## CI Strategies

### Strategy 1: Block New Issues (Recommended)

Prevent technical debt from growing:

```yaml
- name: ACE - Block new issues
  run: |
    ace baseline compare \
      --target . \
      --baseline-path .ace/baseline.json \
      --fail-on-new
```

**When to use**: Established codebases with existing technical debt. Allows gradual improvement while preventing new issues.

### Strategy 2: Strict Mode

Fail on any regression or new issue:

```yaml
- name: ACE - Strict enforcement
  run: |
    ace baseline compare \
      --target . \
      --baseline-path .ace/baseline.json \
      --fail-on-new \
      --fail-on-regression
```

**When to use**: Clean codebases or critical paths. Enforces zero-tolerance policy.

### Strategy 3: Report Only

Run analysis without blocking CI:

```yaml
- name: ACE - Analysis report
  run: |
    ace analyze --target . > ace-report.json
  continue-on-error: true

- name: Upload ACE report
  uses: actions/upload-artifact@v4
  with:
    name: ace-report
    path: ace-report.json
```

**When to use**: Initial adoption phase. Provides visibility without disrupting development.

## Performance Optimization

### Parallel Analysis

Use `--jobs` for faster analysis on large codebases:

```yaml
- name: Run ACE with parallelism
  run: |
    ace analyze --target . --jobs 4
```

Recommended values:
- **Small repos (<100 files)**: `--jobs 2`
- **Medium repos (100-1000 files)**: `--jobs 4`
- **Large repos (>1000 files)**: `--jobs 8`

### Caching

ACE automatically caches analysis results. Enable in `ace.toml`:

```toml
[cache]
enabled = true
ttl = 3600  # 1 hour
dir = ".ace"
```

Cache directory structure:
```
.ace/
├── cache.db         # SQLite analysis cache
└── baseline.json    # Baseline snapshot
```

**Note**: Cache is invalidated when:
- File content changes (SHA256 hash)
- Ruleset changes (enabled rules)
- ACE version changes

### CI Cache Integration

Speed up CI with GitHub Actions cache:

```yaml
- name: Cache ACE results
  uses: actions/cache@v4
  with:
    path: .ace
    key: ace-${{ runner.os }}-${{ hashFiles('**/*.py') }}
    restore-keys: |
      ace-${{ runner.os }}-
```

## Subprocess Hardening Rules

ACE v0.4+ includes subprocess security rules:

### PY-S201-SUBPROCESS-CHECK (Auto-fix)

Adds `check=True` to `subprocess.run()` calls:

```python
# Before
subprocess.run(["git", "push"])

# After (auto-fixed)
subprocess.run(["git", "push"], check=True)
```

**Rationale**: `check=True` raises `CalledProcessError` on non-zero exit codes, preventing silent failures.

### PY-S202-SUBPROCESS-SHELL (Detect)

Flags dangerous `shell=True` usage:

```python
# ❌ Flagged - shell injection risk
subprocess.run("rm -rf " + user_input, shell=True)

# ✅ Safe - list arguments prevent injection
subprocess.run(["rm", "-rf", user_input])
```

**Severity**: High — Shell injection vulnerability

### PY-S203-SUBPROCESS-STRING-CMD (Detect)

Suggests list arguments over string commands:

```python
# ⚠️  Flagged - less robust
subprocess.run("git commit -m 'message'")

# ✅ Preferred - explicit argument list
subprocess.run(["git", "commit", "-m", "message"])
```

**Severity**: Medium — Reduces parsing ambiguity

## Troubleshooting

### Baseline Mismatch

**Error**: Baseline contains findings that don't exist in current code

**Solution**: Recreate baseline from current state
```bash
ace baseline create --target . --baseline-path .ace/baseline.json
```

### Cache Issues

**Error**: Stale cache causing incorrect results

**Solution**: Clear cache directory
```bash
rm -rf .ace/cache.db
```

### False Positives

**Solution**: Suppress specific findings with inline comments
```python
# ace-suppress: PY-S202-SUBPROCESS-SHELL
subprocess.run("safe_command", shell=True)  # Reviewed and approved
```

### CI Performance

**Issue**: CI runs too slowly

**Solutions**:
1. Enable parallel analysis: `--jobs 4`
2. Use CI cache for `.ace/` directory
3. Analyze only changed files:
   ```bash
   git diff --name-only main | xargs ace analyze --target
   ```

## Configuration Reference

Complete `ace.toml` example:

```toml
[rules]
enabled = [
  "PY-S101-UNSAFE-HTTP",
  "PY-E201-BROAD-EXCEPT",
  "PY-I101-IMPORT-SORT",
  "PY-S201-SUBPROCESS-CHECK",
  "PY-S202-SUBPROCESS-SHELL",
  "PY-S203-SUBPROCESS-STRING-CMD",
  "MD-S001-DANGEROUS-COMMAND",
  "YML-F001-DUPLICATE-KEY",
  "SH-S001-MISSING-STRICT-MODE",
]

[cache]
enabled = true
ttl = 3600
dir = ".ace"

[analysis]
include = ["src/**/*.py", "tests/**/*.py"]
exclude = [
  "build/",
  "dist/",
  ".venv/",
  "node_modules/",
  "__pycache__/",
]
```

## Best Practices

1. **Start with Report Only**: Run ACE in report-only mode initially to understand your baseline
2. **Gradual Adoption**: Enable rules incrementally, starting with high-severity issues
3. **Regular Baseline Updates**: Update baseline after deliberate fixes or accepting debt
4. **Use Suppressions Sparingly**: Document why each suppression is necessary
5. **Monitor Performance**: Optimize with `--jobs` and caching for large codebases
6. **Version Lock**: Pin ACE version in CI to ensure consistent results

## Examples

### GitHub Actions (Full)

```yaml
name: ACE Code Health

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  ace:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Cache ACE
        uses: actions/cache@v4
        with:
          path: .ace
          key: ace-${{ runner.os }}-${{ hashFiles('**/*.py') }}

      - name: Install ACE
        run: pip install ace-code-health

      - name: Run ACE analysis
        run: ace analyze --target . --jobs 4

      - name: Compare baseline
        run: |
          ace baseline compare \
            --target . \
            --baseline-path .ace/baseline.json \
            --fail-on-new
```

### GitLab CI

```yaml
ace_check:
  image: python:3.11
  stage: test
  script:
    - pip install ace-code-health
    - ace analyze --target . --jobs 4
    - |
      ace baseline compare \
        --target . \
        --baseline-path .ace/baseline.json \
        --fail-on-new
  cache:
    paths:
      - .ace/
  allow_failure: false
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: ace-check
        name: ACE Code Health
        entry: ace analyze --target .
        language: system
        pass_filenames: false
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/your-org/ace/issues
- Documentation: https://ace-docs.example.com
- Examples: https://github.com/your-org/ace-examples
