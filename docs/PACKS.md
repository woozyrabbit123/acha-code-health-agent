# ACE Macro-Fix Packs (v0.7)

Apply more value per run by bundling related fixes into cohesive refactoring packs.

## Overview

**Macro-Fix Packs** group related findings that should be fixed together, producing a single EditPlan and receipt. This provides:

- **Higher efficiency**: Fix 3-5 related issues in one operation
- **Better cohesion**: Related changes stay together (e.g., HTTP safety + subprocess checks)
- **R* boost**: Packs get γ×cohesion bonus, prioritizing comprehensive fixes
- **Cleaner history**: One commit per pack instead of scattered individual fixes

## Pack Structure

### Pack Definition

A pack combines:
- **Recipe**: Rule IDs that belong together
- **Context**: Grouping level (file, function, class)
- **Findings**: Individual UIR findings matching recipe rules
- **Cohesion**: How many recipe rules are present (0.0-1.0)

### Built-in Recipes

ACE v0.7 ships with these pack recipes:

#### `PY_HTTP_SAFETY`
- **Rules**: `PY-S101-UNSAFE-HTTP`, `PY-S201-SUBPROCESS-CHECK`, `PY-I101-IMPORT-SORT`
- **Context**: `function`
- **Description**: HTTP safety and subprocess security fixes
- **Rationale**: Timeout + subprocess checks often occur in same API functions

#### `PY_EXCEPTION_HANDLING`
- **Rules**: `PY-E201-BROAD-EXCEPT`
- **Context**: `function`
- **Description**: Exception handling improvements
- **Rationale**: Single-rule pack for consistency

#### `PY_CODE_QUALITY`
- **Rules**: `PY-Q201-ASSERT-IN-NONTEST`, `PY-Q202-PRINT-IN-SRC`, `PY-Q203-EVAL-EXEC`
- **Context**: `function`
- **Description**: Code quality improvements
- **Rationale**: Anti-patterns that reduce code quality

#### `PY_STYLE`
- **Rules**: `PY-S310-TRAILING-WS`, `PY-S311-EOF-NL`, `PY-S312-BLANKLINES`
- **Context**: `file`
- **Description**: Code style and formatting
- **Rationale**: Style fixes apply file-wide

## Pack Algorithm

### Finding Packs

**Input**: List of findings from analysis

**Algorithm**:
1. For each pack recipe:
   - Find findings matching recipe rules
   - Group by context_id (computed from context level)
   - For groups with ≥ min_findings:
     - Compute cohesion = unique_rules / recipe_rules
     - Create Pack object
2. Sort packs by cohesion (desc), then context_id (asc)

**Determinism**: Same findings → same packs every time

### Context ID Computation

Context IDs group findings spatially:

| Context Level | Grouping Strategy | Example |
|---------------|-------------------|---------|
| `file` | Entire file | `test.py` |
| `function` | 50-line buckets | `test.py::L0-50` |
| `class` | 100-line buckets | `test.py::L100-200` |

**Note**: v0.7 uses line-based heuristics. Future versions may use AST-based context (actual function/class names).

### Synthesizing Pack Plans

**Input**: Packs + individual EditPlans

**Algorithm**:
1. For each pack:
   - Find individual plans for pack's findings
   - Collect all edits from those plans
   - **Validate non-overlapping spans**
   - If valid: Create pack EditPlan
   - If conflict: **Fallback to individuals**
2. Return (pack_plans, fallback_plans)

**Overlap detection**: Edits on lines [10-15] and [12-18] conflict → fallback.

**Pack plan ID**: `pack-{hash(pack_id + finding_ids)}`

## Cohesion Score

Cohesion measures how completely a pack covers its recipe:

```
cohesion = unique_rules_in_findings / total_rules_in_recipe
```

**Examples**:

- Recipe has 3 rules, findings cover all 3 → cohesion = 1.0 (perfect)
- Recipe has 3 rules, findings cover 2 → cohesion = 0.67 (good)
- Recipe has 3 rules, findings cover 1 → cohesion = 0.33 (weak)

### R* Boost

Packs with high cohesion get prioritized:

```
R*pack = α × severity + β × complexity + γ × cohesion
```

**Default**: γ = 0.2

**Example**: Individual R* = 0.60 (SUGGEST), but pack with cohesion = 1.0 → R*pack = 0.80 (AUTO)

## Pack Lifecycle

### 1. Analysis

Findings are detected as usual:

```bash
ace analyze src/
```

### 2. Pack Discovery

ACE finds packs matching recipes:

```bash
ace analyze --show-packs src/
```

**Output**:
```json
{
  "packs": [
    {
      "id": "abc123def456",
      "recipe": "PY_HTTP_SAFETY",
      "context": "test.py::L0-50",
      "findings": 3,
      "cohesion": 0.667
    }
  ]
}
```

### 3. Refactor with Packs

Generate pack plans:

```bash
ace refactor --macros src/
```

**Without `--macros`**: Individual plans only
**With `--macros`**: Pack plans + fallback individuals

### 4. Apply

Apply pack plans:

```bash
ace apply --macros --allow auto src/
```

**Result**: One receipt per pack (not per finding).

### 5. Skip or Revert

If user dislikes a pack:

```bash
# Skip future instances
ace apply --skip-pack abc123def456

# Or revert applied pack
ace revert --journal latest
```

Skiplist learns: Next run won't propose that pack again.

## Configuration

### `policy.toml`

```toml
[packs]
enabled = true             # Enable pack synthesis
min_findings = 2           # Minimum findings to form pack
prefer_packs = true        # Prefer packs over individuals
```

### Disabling Packs

Temporarily disable:

```bash
ace refactor --no-macros
```

Or in policy:

```toml
[packs]
enabled = false
```

## Invariants

Pack synthesis enforces safety invariants:

### Non-Overlapping Edits

**Rule**: Edits within a pack must not overlap line ranges.

**Example**:
- ✅ Edit A: lines 10-15, Edit B: lines 20-25 → OK
- ❌ Edit A: lines 10-15, Edit B: lines 12-18 → **Conflict**

**Fallback**: On conflict, ACE uses individual plans instead.

### Single Receipt per Pack

Pack application produces **one receipt**, not per-finding receipts:

```json
{
  "plan_id": "pack-abc123",
  "file": "test.py",
  "findings": ["finding1-id", "finding2-id", "finding3-id"],
  ...
}
```

This maintains atomicity: pack succeeds/fails as a unit.

### Deterministic IDs

Pack IDs are stable across runs:

```
pack_id = SHA256(context_id + recipe_id)[:12]
```

Same findings → same pack ID → enables skiplist matching.

## Examples

### Example 1: HTTP Safety Pack

**Findings**:
```python
# test.py, lines 10-30 (same function)
response = requests.get(url)              # Line 15: PY-S101-UNSAFE-HTTP
subprocess.run(["ls", "-la"])             # Line 20: PY-S201-SUBPROCESS-CHECK
```

**Pack**:
- Recipe: `PY_HTTP_SAFETY`
- Context: `test.py::L0-50`
- Cohesion: 2/3 = 0.67 (missing `PY-I101-IMPORT-SORT`)

**Pack Plan**:
```json
{
  "id": "pack-abc123",
  "findings": 2,
  "edits": [
    { "line": 15, "op": "replace", "payload": "requests.get(url, timeout=10)" },
    { "line": 20, "op": "replace", "payload": "subprocess.run(['ls', '-la'], check=True)" }
  ]
}
```

**Applied**: One atomic operation, one receipt.

### Example 2: Style Pack

**Findings**:
```python
# style.py (entire file)
Line 10: trailing spaces     # PY-S310-TRAILING-WS
Line 25: trailing spaces     # PY-S310-TRAILING-WS
EOF: missing newline         # PY-S311-EOF-NL
```

**Pack**:
- Recipe: `PY_STYLE`
- Context: `style.py` (file-level)
- Cohesion: 2/3 = 0.67

**Pack Plan**: Single EditPlan with 3 edits (one per line).

### Example 3: Overlap Conflict

**Findings**:
```python
# conflict.py
Line 10-15: RULE-A (replace function)
Line 12-18: RULE-B (replace different part)
```

**Conflict**: Edits overlap lines 12-15.

**Fallback**: ACE synthesizes individual plans for RULE-A and RULE-B separately.

## Benefits

### 1. Efficiency

**Before (individual)**:
- 5 findings → 5 refactor operations → 5 receipts
- 5 separate git commits (if auto-committing)

**After (packs)**:
- 5 findings → 1 pack operation → 1 receipt
- 1 cohesive git commit

### 2. Cohesion

Related changes stay together:
- HTTP timeout + subprocess check in same function
- All style fixes in one file
- Exception handling improvements in one method

### 3. Prioritization

Pack cohesion boosts R* score:
- Individual: R* = 0.60 → SUGGEST
- Pack: R*pack = 0.60 + 0.2 × 1.0 = 0.80 → AUTO

Encourages comprehensive fixes over piecemeal changes.

### 4. Discoverability

Packs surface related issues user might miss:

```bash
ace analyze --show-packs src/
```

Output shows which rules cluster together in your codebase.

## Customization

### Custom Pack Recipes

Define project-specific packs in code:

```python
from ace.packs import PackRecipe, find_packs

CUSTOM_RECIPE = PackRecipe(
    id="MYTEAM_API_SAFETY",
    rules=["RULE-1", "RULE-2", "RULE-3"],
    context="function",
    description="Team-specific API safety checks",
)

# Find packs using custom recipe
packs = find_packs(findings, recipes=[CUSTOM_RECIPE])
```

Future versions may support TOML-based recipe definitions.

### Context Granularity

Adjust line bucket sizes (requires code change in v0.7):

```python
# In packs.py, adjust bucket sizes:
function_bucket = 50  # Lines per function approximation
class_bucket = 100    # Lines per class approximation
```

Future versions may expose this in `policy.toml`.

## Limitations (v0.7)

### 1. Line-Based Context

Current context uses line buckets, not AST:
- May group unrelated findings in large files
- May split related findings across bucket boundaries

**Future**: AST-based context using actual function/class names.

### 2. Static Recipes

Pack recipes are hardcoded in `packs.py`:
- Can't define custom recipes in `policy.toml`
- Recipe changes require code modification

**Future**: TOML-based recipe configuration.

### 3. Python-Only

v0.7 pack recipes are Python-specific:
- No Markdown, YAML, Shell packs yet
- Extendable to other languages in future

### 4. No Cross-File Packs

Packs group findings within same file:
- Can't pack related changes across files
- E.g., "fix all unsafe HTTP calls in project" → separate per-file packs

**Future**: Project-level pack context.

## Troubleshooting

### "No packs found"

Check:
1. `[packs] enabled = true` in policy.toml
2. At least `min_findings` (default: 2) match recipe rules
3. Findings are in same context (file/function/class)

### "Pack always falls back to individuals"

**Cause**: Edit overlap detected.

**Debug**:
```bash
ace refactor --macros --verbose src/
```

Look for "overlap detected" messages.

**Solution**: Investigate conflicting rules. May need recipe adjustment.

### "Pack cohesion too low"

**Cause**: Only 1 rule from 3-rule recipe.

**Options**:
1. Lower `min_findings` threshold
2. Adjust recipe to have fewer rules
3. Accept individual plans for low-cohesion cases

### "Pack plan has wrong ID format"

Pack plan IDs start with `pack-`:

```
pack-abc123def456
```

If seeing individual IDs (`plan-...`), packs may be disabled or falling back.

## CLI Reference

### `ace analyze --show-packs`

Show pack summary:

```bash
ace analyze --show-packs src/

# Output includes "packs" section
{
  "findings": [...],
  "packs": [
    {
      "id": "abc123",
      "recipe": "PY_HTTP_SAFETY",
      "context": "test.py::L0-50",
      "findings": 3,
      "cohesion": 1.0
    }
  ]
}
```

### `ace refactor --macros`

Generate pack plans:

```bash
ace refactor --macros src/

# Returns pack plans + fallback individuals
```

### `ace apply --macros`

Apply with pack synthesis:

```bash
ace apply --macros --allow auto src/
```

### `ace apply --skip-pack <id>`

Skip specific pack:

```bash
# Skip pack-abc123
ace apply --skip-pack abc123 src/

# Adds to .ace/skiplist.json
```

### `ace explain --plan <pack-id>`

Explain pack plan:

```bash
ace explain --plan pack-abc123

# Shows:
# - Pack recipe and cohesion
# - All findings in pack
# - R* calculation with cohesion boost
# - Decision (AUTO/SUGGEST/SKIP)
```

## Integration

### CI/CD

Enable packs in CI for efficiency:

```yaml
# .github/workflows/ace.yml
- name: Apply ACE packs
  run: |
    ace apply --macros --allow auto --policy policy.toml src/
    git add -A
    git commit -m "refactor: ACE pack auto-fixes"
```

### Pre-commit Hook

Use packs in pre-commit:

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: ace-packs
      name: ACE Macro Packs
      entry: ace apply --macros --allow auto
      language: system
      pass_filenames: false
```

### Code Review

Show packs in PR:

```bash
# In CI, comment on PR with pack summary
ace analyze --show-packs src/ | jq '.packs'
```

Helps reviewers see related changes bundled together.

## Best Practices

### 1. Start with `--show-packs`

Understand pack behavior before applying:

```bash
ace analyze --show-packs src/
```

Review which findings group into packs.

### 2. Enable Gradually

First run: detect-only mode

```toml
[packs]
enabled = true

[modes]
"*" = "detect-only"
```

Review suggested packs, then enable auto-fix.

### 3. Monitor Cohesion

Low cohesion (< 0.5) may indicate:
- Partial fixes (intentional)
- Missing related findings (incomplete analysis)
- Recipe too broad (needs refinement)

### 4. Use Explain

Understand why packs form:

```bash
ace explain --plan pack-abc123
```

Shows cohesion, R* boost, decision rationale.

### 5. Skiplist Noisy Packs

If a pack repeatedly suggests unwanted changes:

```bash
ace apply --skip-pack abc123
```

ACE learns and won't propose it again.

## See Also

- [POLICY.md](./POLICY.md) - Policy configuration guide
- [src/ace/packs.py](../src/ace/packs.py) - Pack implementation
- [src/ace/refactor.py](../src/ace/refactor.py) - Pack synthesis algorithm
- [tests/ace/test_packs.py](../tests/ace/test_packs.py) - Pack tests
