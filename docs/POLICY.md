# ACE Policy Configuration (v0.7)

Policy-as-Data: Define risk management, rule modes, and quality gates in a declarative TOML configuration.

## Overview

ACE v0.7 introduces **Policy-as-Data**, allowing teams to codify their refactoring policies in a version-controlled `policy.toml` file. This enables:

- **Data-driven risk tuning**: Configure R* weights, thresholds, and decision modes
- **Rule-specific control**: Set auto-fix vs detect-only per rule
- **Quality gates**: Define fail/warn thresholds for CI integration
- **Path suppressions**: Exclude test files, generated code, etc.
- **Risk classification**: Group rules by security, reliability, maintainability, style

## Policy File Structure

### `policy.toml` Schema

```toml
[meta]
version = "0.7.0"
description = "Team policy configuration"

[scoring]
alpha = 0.7                # Weight for severity (0.0-1.0)
beta = 0.3                 # Weight for complexity (0.0-1.0)
gamma = 0.2                # Weight for pack cohesion boost (0.0-1.0)
auto_threshold = 0.70      # Auto-apply if R* >= 0.70
suggest_threshold = 0.50   # Suggest if R* >= 0.50

[limits]
max_findings = 0           # Maximum findings (0 = unlimited)
fail_on_critical = true    # Fail if any critical findings
warn_at = 50               # Warning threshold
fail_at = 100              # Failure threshold

[modes]
"RULE-ID" = "auto-fix"     # or "detect-only"

[risk_classes]
security = ["RULE-1", "RULE-2"]
reliability = ["RULE-3"]
maintainability = ["RULE-4"]
style = ["RULE-5"]

[suppressions]
paths = ["tests/**", "**/.venv/**"]

[suppressions.rules]
"RULE-ID" = ["path/pattern/**"]

[packs]
enabled = true             # Enable macro-fix packs
min_findings = 2           # Minimum findings to form pack
prefer_packs = true        # Prefer pack plans over individual
```

## R* (Risk/Refactoring Score)

ACE uses R* to prioritize refactorings based on severity and complexity:

### Individual Findings

```
R* = α × severity + β × complexity
```

- **α (alpha)**: Weight for severity (default: 0.7)
- **β (beta)**: Weight for complexity (default: 0.3)
- **severity**: 0.0 (info) to 1.0 (critical)
- **complexity**: Estimated refactoring complexity (0.0-1.0)

### Pack Findings (v0.7+)

For macro-fix packs, cohesion provides a boost:

```
R* = α × severity + β × complexity + γ × cohesion
```

- **γ (gamma)**: Weight for cohesion boost (default: 0.2)
- **cohesion**: Ratio of unique rules to recipe rules (0.0-1.0)

**Example**: A pack fixing 2 out of 3 related rules has cohesion = 0.67

## Decision Thresholds

ACE makes refactoring decisions based on R* score:

| R* Range | Decision | Action |
|----------|----------|--------|
| ≥ 0.70 (auto_threshold) | **AUTO** | Auto-apply with `--allow auto` |
| 0.50 - 0.69 | **SUGGEST** | Propose to user, require approval |
| < 0.50 (suggest_threshold) | **SKIP** | Don't propose |

### Tuning Thresholds

**Conservative** (higher bar):
```toml
[scoring]
auto_threshold = 0.90
suggest_threshold = 0.70
```

**Aggressive** (lower bar):
```toml
[scoring]
auto_threshold = 0.50
suggest_threshold = 0.30
```

## Rule Modes

Control whether rules auto-fix or only detect:

### `auto-fix` (default)

Rule can be auto-applied if R* meets threshold:

```toml
[modes]
"PY-S101-UNSAFE-HTTP" = "auto-fix"
```

### `detect-only`

Rule only detects issues, never auto-applies:

```toml
[modes]
"PY-Q203-EVAL-EXEC" = "detect-only"  # Too risky
```

**Use detect-only for**:
- Risky transformations (shell=True, eval/exec)
- Context-dependent issues (asserts, prints)
- Subjective quality rules

## Risk Classes

Organize rules into risk categories for reporting:

```toml
[risk_classes]
security = [
    "PY-S101-UNSAFE-HTTP",
    "PY-S201-SUBPROCESS-CHECK",
]

reliability = [
    "PY-E201-BROAD-EXCEPT",
]

maintainability = [
    "PY-I101-IMPORT-SORT",
]

style = [
    "PY-S310-TRAILING-WS",
]
```

ACE aggregates findings by risk class in reports and exit codes.

## Suppressions

### Global Path Suppressions

Exclude files from all auto-fixes:

```toml
[suppressions]
paths = [
    "tests/**",           # All test files
    "**/test_*.py",       # Test modules
    "**/.venv/**",        # Virtual environments
    "**/dist/**",         # Distribution artifacts
]
```

### Rule-Specific Suppressions

Exclude paths for specific rules:

```toml
[suppressions.rules]
"PY-Q202-PRINT-IN-SRC" = [
    "scripts/**",         # Allow print() in scripts
    "tools/**",
]

"PY-Q201-ASSERT-IN-NONTEST" = [
    "scripts/**",         # Allow assert in scripts
]
```

Patterns use glob syntax (`*`, `**`, `?`).

## Quality Gates (CI Integration)

Configure exit codes for CI pipelines:

```toml
[limits]
warn_at = 50               # Exit 1 if findings >= 50
fail_at = 100              # Exit 2 if findings >= 100
fail_on_critical = true    # Exit 2 if any critical
```

**Exit codes**:
- `0`: Success
- `1`: Warning threshold exceeded
- `2`: Failure threshold or critical findings

**Example CI usage**:

```yaml
# .github/workflows/ace.yml
- name: Run ACE analysis
  run: ace analyze --policy policy.toml .
  continue-on-error: ${{ matrix.allow-warnings }}
```

## Pack Configuration

Control macro-fix pack behavior:

```toml
[packs]
enabled = true             # Enable pack synthesis
min_findings = 2           # Minimum findings per pack
prefer_packs = true        # Prefer packs over individuals
```

Packs group related findings for cohesive fixes. See [PACKS.md](./PACKS.md) for details.

## Policy Hash

ACE computes a hash of the policy configuration and records it in receipts:

```json
{
  "plan_id": "pack-abc123",
  "policy_hash": "7f8e9d6c5b4a3210",
  ...
}
```

This enables auditing: "Which policy was active when this change was applied?"

## Examples

### Strict Security Policy

High bar for auto-fixes, focus on security:

```toml
[scoring]
alpha = 0.9                # Heavy severity weight
auto_threshold = 0.85      # High auto bar

[modes]
"PY-S101-UNSAFE-HTTP" = "auto-fix"
"PY-S201-SUBPROCESS-CHECK" = "auto-fix"
"PY-S202-SUBPROCESS-SHELL" = "detect-only"  # Too risky

[limits]
fail_on_critical = true
warn_at = 10
```

### Permissive Style Policy

Low bar for auto-fixes, allow style changes:

```toml
[scoring]
alpha = 0.5
beta = 0.5
auto_threshold = 0.60

[modes]
"PY-S310-TRAILING-WS" = "auto-fix"
"PY-S311-EOF-NL" = "auto-fix"
"PY-I101-IMPORT-SORT" = "auto-fix"

[limits]
fail_on_critical = false
warn_at = 100
```

### Test-Only Mode

Detect issues but never auto-fix:

```toml
[modes]
"*" = "detect-only"        # All rules detect-only

[limits]
fail_on_critical = true
fail_at = 0                # Fail on any finding
```

## Loading Policy

### Auto-discovery

ACE searches for `policy.toml` in:
1. Current directory
2. Parent directories (up to git root)
3. Falls back to defaults if not found

### Explicit Path

```bash
ace apply --policy /path/to/policy.toml
```

### Validation

ACE validates policy on load:
- Weight ranges: [0.0, 1.0]
- Threshold ordering: auto_threshold ≥ suggest_threshold
- Mode values: "auto-fix" or "detect-only"
- Invalid policy → **fail fast** with clear error

## Best Practices

### 1. Start Conservative

Begin with high thresholds and detect-only modes:

```toml
[scoring]
auto_threshold = 0.90

[modes]
"*" = "detect-only"
```

Gradually enable auto-fix as confidence grows.

### 2. Version Control

Commit `policy.toml` to version control:

```bash
git add policy.toml
git commit -m "Add ACE policy configuration"
```

### 3. Team Alignment

Document policy decisions in comments:

```toml
[modes]
# Risky: shell injection vector
"PY-S202-SUBPROCESS-SHELL" = "detect-only"

# Safe: well-defined transformation
"PY-S310-TRAILING-WS" = "auto-fix"
```

### 4. Environment-Specific Policies

Use different policies per environment:

```bash
# CI: strict
ace analyze --policy policy.ci.toml

# Dev: permissive
ace analyze --policy policy.dev.toml
```

### 5. Monitor Policy Hash

Track policy changes in receipts:

```bash
# Which policy was active?
jq '.policy_hash' .ace/receipts/*.json
```

## Schema Evolution

Policy schema versions:

- **v0.7**: Initial policy-as-data release
  - R* scoring, thresholds, modes
  - Risk classes, suppressions
  - Pack configuration

Future versions will maintain backward compatibility. ACE warns on schema version mismatches.

## Migration from v0.6

v0.6 used hardcoded defaults. To migrate:

1. **Extract current behavior**:

```bash
# v0.6 defaults
alpha = 0.7
beta = 0.3
auto_threshold = 0.70
suggest_threshold = 0.50
```

2. **Create `policy.toml`** with equivalent configuration

3. **Test** with `ace analyze --policy policy.toml`

4. **Tune** thresholds and modes as needed

No code changes required—policy is purely additive.

## Troubleshooting

### "Policy validation failed"

Check:
- Weight ranges: `0.0 ≤ alpha, beta, gamma ≤ 1.0`
- Thresholds: `auto_threshold ≥ suggest_threshold`
- Mode values: `"auto-fix"` or `"detect-only"` only

### "Policy file not found"

- Ensure `policy.toml` exists in project root
- Or specify explicit path: `--policy path/to/policy.toml`
- ACE falls back to defaults if missing (no error)

### "Rule not auto-fixing"

Check:
1. Mode: `[modes] "RULE-ID" = "auto-fix"`
2. R* score: Must meet `auto_threshold`
3. Suppressions: Path not in `[suppressions]`

Enable explain: `ace explain --plan <id>` to see R* calculation.

## See Also

- [PACKS.md](./PACKS.md) - Macro-fix packs documentation
- [policy.toml](../policy.toml) - Example policy configuration
- [Architecture.md](./Architecture.md) - ACE system design
