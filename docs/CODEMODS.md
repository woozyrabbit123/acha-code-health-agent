# ACE v1.6: Codemods Documentation

## Overview

ACE v1.6 introduces **deterministic codemods** - safe, idempotent code transformations using LibCST. Each codemod pack can be applied interactively or automatically via CLI.

### Key Principles

1. **Idempotent**: Running twice yields zero diff on second pass
2. **Guarded**: Safety checks prevent unsafe transformations
3. **Deterministic**: Same input always produces same output
4. **PatchGuard v2**: Multiple verification layers ensure correctness

## Available Codemod Packs

### 1. PY_PATHLIB - Pathlib Modernization

**Purpose**: Modernize os.path.* calls to pathlib.Path

**Transformations**:

```python
# Before
import os
path = os.path.join(base, "file.txt")
if os.path.exists(path):
    print(os.path.basename(path))

# After
from pathlib import Path
path = Path(base) / "file.txt"
if Path(path).exists():
    print(Path(path).name)
```

**Guards**:
- Skips dynamic string operations (f-strings, templates)
- Skips complex nested calls
- Only transforms simple, safe cases

**Invariants**:
- AST structure preserved
- Import added if missing
- Only simple cases transformed

**Risk Level**: Low

**Category**: Modernization

---

### 2. PY_REQUESTS_HARDEN - Requests Hardening

**Purpose**: Add timeout and error handling to requests calls

**Transformations**:

```python
# Before
import requests
response = requests.get(url)

# After
import requests
response = requests.get(url, timeout=30)
```

**Future enhancements** (not yet implemented):
- Wrap in try/except RequestException
- Add raise_for_status() calls

**Guards**:
- Only adds timeout if not already present
- Preserves existing timeout values
- Safe for all requests methods

**Invariants**:
- Timeout added to requests
- AST structure preserved

**Risk Level**: Medium

**Category**: Security

---

### 3. PY_DATACLASS_SLOTS - Dataclass Slots

**Purpose**: Add slots=True to @dataclass decorators for memory efficiency

**Transformations**:

```python
# Before
@dataclass
class Config:
    name: str
    value: int

# After
@dataclass(slots=True)
class Config:
    name: str
    value: int
```

**Guards**:
- Skips if multiple inheritance (incompatible with slots)
- Skips if __slots__ already defined
- Only applies to simple dataclasses

**Invariants**:
- No multiple inheritance
- No existing __slots__
- Class structure unchanged

**Risk Level**: Low

**Category**: Performance

**Benefits**:
- Reduces memory footprint (~40% for simple dataclasses)
- Faster attribute access
- Prevents dynamic attribute assignment

---

### 4. PY_PRINT_LOGGING - Print to Logging

**Purpose**: Convert print() calls to logging.info()

**Transformations**:

```python
# Before
def process(data):
    print(f"Processing {len(data)} items")
    return result

# After
import logging

def process(data):
    logging.info(f"Processing {len(data)} items")
    return result
```

**Guards**:
- Skips test files (test_*.py, *_test.py)
- Skips if __name__ == "__main__" blocks
- Skips debug prints in development code

**Invariants**:
- Skip tests
- Skip main blocks
- Import added if missing

**Risk Level**: Low

**Category**: Style

---

### 5. PY_DEAD_IMPORTS - Remove Dead Imports

**Purpose**: Remove unused imports (scope-aware)

**Transformations**:

```python
# Before
import os
import sys
from typing import List, Dict, Optional

def hello():
    print("Hello")

# After
def hello():
    print("Hello")
```

**Guards**:
- Never touches __future__ imports
- Preserves typing.* imports if annotations present
- Scope-aware analysis (only removes truly unused)

**Invariants**:
- Scope-aware
- Keep __future__
- Keep typing if annotations present

**Risk Level**: Low

**Category**: Style

---

## CLI Usage

### List Available Packs

```bash
ace pack list
```

**Output**:
```
Available Codemod Packs:

  PY_PATHLIB
    Name: Pathlib Modernization
    Description: Modernize os.path.* calls to pathlib.Path
    Risk: low
    Category: modernization

  PY_REQUESTS_HARDEN
    Name: Requests Hardening
    Description: Add timeout and error handling to requests calls
    Risk: medium
    Category: security

  ...
```

### Apply a Pack (Dry Run)

```bash
ace pack apply PY_PATHLIB --dry-run
```

Shows changes without applying them.

### Apply a Pack (Interactive)

```bash
ace pack apply PY_PATHLIB --interactive
```

**Interactive UI**:
```
======================================================================
MODIFIED src/utils/files.py
======================================================================
[Syntax-highlighted preview]

Action [a]ccept / [r]eject / [v]iew / [q]uit (default: a): a
✓ Approved: src/utils/files.py
```

### Apply a Pack (Auto-apply)

```bash
ace pack apply PY_PATHLIB --target src/
```

Applies all changes automatically.

### Apply to Single File

```bash
ace pack apply PY_PATHLIB --target src/utils.py
```

---

## PatchGuard v2

### Verification Layers

All codemods go through PatchGuard v2 verification:

1. **Parse Check**: Code must parse successfully
2. **AST Equivalence**: Semantic structure must match
3. **Symbol Counts**: Function and class counts must match (NEW in v2)
4. **CST Roundtrip**: Code must roundtrip cleanly through LibCST

### Symbol Counting (v2 Enhancement)

PatchGuard v2 adds symbol table verification:

```python
# Before transformation
def foo(): pass
class Bar: pass

# After transformation - counts must match
functions: 1 → 1 ✓
classes: 1 → 1 ✓
```

**Detects**:
- Accidental function deletion
- Duplicated classes
- Structural integrity violations

**Allows**:
- Import changes (controlled by flag)
- Assignment changes
- Internal refactoring

### Automatic Rollback

If PatchGuard v2 fails:
1. Change is rejected
2. File reverted via journal
3. Error logged with details
4. Exit with clear error message

**Example failure**:
```
PatchGuard v2 FAILED: symbol_count
Function count changed: 5 → 4
File reverted: src/module.py
```

---

## Pre-commit Hook

### Installation

```bash
ace install-pre-commit
```

**Output**:
```
✓ Pre-commit hook installed at .git/hooks/pre-commit
  The hook will run 'ace analyze' on staged Python files
  To bypass: git commit --no-verify
```

### Hook Behavior

**On commit**:
1. Detects staged Python files
2. Runs `ace analyze --target . --exit-on-violation`
3. Blocks commit if violations found
4. Suggests running `ace autopilot` to fix

**Bypass**:
```bash
git commit --no-verify
```

**Hook Script** (`.git/hooks/pre-commit`):
```bash
#!/bin/sh
# ACE pre-commit hook

echo "Running ACE pre-commit checks..."

# Get staged Python files
STAGED_PY_FILES=$(git diff --cached --name-only --diff-filter=ACMR | grep '\.py$')

if [ -z "$STAGED_PY_FILES" ]; then
    echo "No Python files staged, skipping ACE checks"
    exit 0
fi

# Run analyze on staged files
ace analyze --target . --exit-on-violation

if [ $? -ne 0 ]; then
    echo "ACE analysis found violations. Commit blocked."
    echo "Run 'ace autopilot' to fix issues automatically."
    exit 1
fi

echo "ACE checks passed!"
exit 0
```

---

## Autopilot Integration

Autopilot can automatically select and apply codemod packs based on repo signals (from RepoMap/context engine).

### Pack Prioritization

**If repo has many os.path calls**:
- Prioritizes PY_PATHLIB

**If requests library used**:
- Prioritizes PY_REQUESTS_HARDEN

**Detection logic** (in autopilot.py):
```python
# Use RepoMap to find patterns
if "os.path" in repo_symbols:
    suggest_pack(PY_PATHLIB)

if "requests" in imported_modules:
    suggest_pack(PY_REQUESTS_HARDEN)
```

---

## Idempotence Testing

### Verification Method

Each codemod includes `is_idempotent()` method:

```python
def is_idempotent(source_code: str, file_path: str) -> bool:
    """Check if applying twice yields same result."""
    plan1 = Codemod.plan(source_code, file_path)
    if plan1 is None:
        return True  # No changes needed

    new_code = plan1.edits[0].payload
    plan2 = Codemod.plan(new_code, file_path)

    return plan2 is None  # No further changes
```

### Acceptance Criteria

✅ Running pack twice yields zero diff:
```bash
ace pack apply PY_PATHLIB --target test.py
ace pack apply PY_PATHLIB --target test.py  # No changes
```

---

## Examples

### Example 1: Pathlib Modernization

**Before** (`utils.py`):
```python
import os

def get_config_path(base_dir):
    config_dir = os.path.join(base_dir, "config")
    if os.path.exists(config_dir):
        return os.path.join(config_dir, "app.yaml")
    return None

def list_files(directory):
    if not os.path.isdir(directory):
        return []
    return [os.path.basename(f) for f in os.listdir(directory)]
```

**After applying PY_PATHLIB**:
```python
from pathlib import Path
import os

def get_config_path(base_dir):
    config_dir = Path(base_dir) / "config"
    if Path(config_dir).exists():
        return Path(config_dir) / "app.yaml"
    return None

def list_files(directory):
    if not Path(directory).is_dir():
        return []
    return [Path(f).name for f in os.listdir(directory)]
```

### Example 2: Requests Hardening

**Before** (`api.py`):
```python
import requests

def fetch_data(url):
    response = requests.get(url)
    return response.json()

def post_update(url, data):
    response = requests.post(url, json=data)
    return response.status_code
```

**After applying PY_REQUESTS_HARDEN**:
```python
import requests

def fetch_data(url):
    response = requests.get(url, timeout=30)
    return response.json()

def post_update(url, data):
    response = requests.post(url, json=data, timeout=30)
    return response.status_code
```

### Example 3: Dataclass Slots

**Before** (`models.py`):
```python
from dataclasses import dataclass

@dataclass
class User:
    id: int
    name: str
    email: str

@dataclass
class Config:
    host: str
    port: int
    timeout: int
```

**After applying PY_DATACLASS_SLOTS**:
```python
from dataclasses import dataclass

@dataclass(slots=True)
class User:
    id: int
    name: str
    email: str

@dataclass(slots=True)
class Config:
    host: str
    port: int
    timeout: int
```

**Memory savings**: ~40% reduction in instance size

---

## Best Practices

### 1. Run in Interactive Mode First

```bash
ace pack apply <PACK_ID> --interactive
```

Review each change before accepting.

### 2. Use Dry Run for Large Codebases

```bash
ace pack apply <PACK_ID> --dry-run | less
```

Preview all changes without applying.

### 3. Apply Incrementally

```bash
ace pack apply PY_DEAD_IMPORTS --target src/utils/
ace pack apply PY_DEAD_IMPORTS --target src/models/
```

Apply to subdirectories one at a time.

### 4. Version Control

Always commit before applying codemods:
```bash
git commit -m "Checkpoint before codemods"
ace pack apply <PACK_ID>
git diff  # Review changes
git commit -m "Apply <PACK_ID> codemod"
```

### 5. Test After Applying

```bash
ace pack apply <PACK_ID>
pytest  # Run test suite
ace analyze --target .  # Verify no new issues
```

---

## Troubleshooting

### Issue: "PatchGuard v2 FAILED: symbol_count"

**Cause**: Transformation changed function or class counts

**Solution**:
1. Check the rejected file manually
2. Verify transformation is safe
3. If safe, file a bug report
4. If not, this is expected behavior (guard working correctly)

### Issue: "No changes needed" but file has patterns

**Cause**: Guards prevented transformation

**Why**: File may have:
- Dynamic string operations (f-strings)
- Complex nested calls
- Multiple inheritance (for slots)
- Test file patterns

**Solution**: This is expected - guards ensure safety

### Issue: Import conflicts after applying pack

**Cause**: Rare edge case with import order

**Solution**:
```bash
ace pack apply PY_DEAD_IMPORTS  # Clean up imports
```

---

## Performance

| Pack | Files/sec | Memory |
|------|-----------|--------|
| PY_PATHLIB | ~50 | Low |
| PY_REQUESTS_HARDEN | ~100 | Low |
| PY_DATACLASS_SLOTS | ~80 | Low |
| PY_PRINT_LOGGING | ~60 | Low |
| PY_DEAD_IMPORTS | ~40 | Medium |

**Large repos** (1000+ files):
- Use `--target` to apply incrementally
- Parallel processing planned for v1.7

---

## Roadmap

### v1.7 (Planned)
- Type annotation modernization (PEP 585)
- Exception chaining (use `from` syntax)
- Async/await modernization
- Parallel pack application

### v1.8 (Planned)
- Custom codemod API
- User-defined packs
- Multi-language support (TypeScript, Go)

---

**See Also**:
- [Context Engine](CONTEXT.md)
- [PatchGuard Architecture](ARCHITECTURE.md)
- [CLI Reference](CLI.md)
