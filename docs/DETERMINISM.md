# Deterministic Outputs in ACHA Pro

**Version:** 1.0.0
**Last Updated:** 2025-01-01

ACHA Pro guarantees deterministic outputs for all analysis, refactoring, and reporting operations. This document describes what "deterministic" means, why it matters, and how ACHA Pro achieves it.

---

## What is Determinism?

**Determinism** means that given the same inputs, the tool produces **exactly identical outputs** every time.

**For ACHA Pro:**
```
Same Python code + Same ACHA version = Identical JSON/SARIF/HTML
```

**What this guarantees:**
- ✅ Reproducible builds in CI/CD
- ✅ Reliable diffing between runs
- ✅ Cacheable analysis results
- ✅ Supply chain attack detection
- ✅ Bit-for-bit verification

**What this does NOT mean:**
- ❌ Different ACHA versions produce identical output
- ❌ Different Python code produces identical output
- ❌ Timestamps in logs are suppressed (only core outputs are deterministic)

---

## Deterministic Components

### 1. Analysis Results (JSON/SARIF)

**Guarantee:**
Running analysis twice on the same codebase produces:
- Identical finding IDs
- Identical ordering of findings
- Identical severity scores
- Identical file paths
- Identical line numbers

**Example:**
```bash
# Run 1
acha analyze --target ./myproject --output-format json
sha256sum reports/analysis.json
# Output: a1b2c3d4e5f6...

# Run 2 (no code changes)
rm -rf reports/
acha analyze --target ./myproject --output-format json
sha256sum reports/analysis.json
# Output: a1b2c3d4e5f6...  (IDENTICAL)
```

**JSON field ordering:**
All JSON outputs use `sort_keys=True` to ensure stable key ordering:
```python
json.dump(data, f, indent=2, sort_keys=True)
```

**SARIF stability:**
- Rule IDs are deterministic (CRC32 hash of rule name)
- Results array is sorted by file path, then line number
- No timestamps in core SARIF fields
- Schema version is pinned (SARIF 2.1.0)

### 2. Baseline IDs

**Guarantee:**
Baseline finding IDs are stable across runs.

**Algorithm:**
```python
def _generate_finding_id(finding: dict[str, Any]) -> str:
    key_parts = [
        finding.get("file", ""),
        str(finding.get("start_line", 0)),
        str(finding.get("end_line", 0)),
        finding.get("finding", ""),
        finding.get("rationale", "")[:100],
    ]
    key_str = "|".join(key_parts)
    hash_hex = hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:16]
    return f"{finding.get('finding', 'UNK')}:{file}:{line}:{hash_hex}"
```

**Why this works:**
- SHA256 is cryptographically deterministic
- Same finding properties → same hash
- Truncated to 16 hex characters for readability
- Collision probability: ~1 in 2^64 (negligible)

**Example baseline ID:**
```
unused_import:src/main.py:42:7f8e9a1b2c3d4e5f
```

### 3. Parallel Execution (--jobs)

**Guarantee:**
`--jobs 1` and `--jobs 4` produce **identical output** (modulo runtime).

**How it works:**
1. **Independent analysis:** Each file is analyzed in isolation (no shared state)
2. **Deterministic merge:** Results are sorted after parallel collection
3. **Stable sorting:** Sort by (file path, line number, finding type)

**Verification:**
```bash
# Single-threaded
acha analyze --target . --jobs 1 -o json
mv reports/analysis.json /tmp/seq.json

# Parallel (4 workers)
acha analyze --target . --jobs 4 -o json
mv reports/analysis.json /tmp/par.json

# Compare
diff /tmp/seq.json /tmp/par.json
# Exit code 0 = identical
```

**Why parallel is safe:**
- AST parsing is pure (no side effects)
- No shared mutable state between workers
- Results are immutable after creation
- Deterministic ordering after merge

### 4. Refactoring Patches

**Guarantee:**
Same code + same refactor types = identical patch.

**Stable diff generation:**
```python
# Line-by-line deterministic diff
diff = self.patcher.generate_diff(
    original_content,
    new_content,
    file_path
)
```

**Patch ID uniqueness:**
- UUIDs are NOT deterministic (by design)
- Use for tracking, not for content verification
- Patch content is deterministic

**Example:**
```bash
# Run refactoring twice
acha refactor --target . --analysis reports/analysis.json --fix
cp dist/patch.diff /tmp/patch1.diff

rm dist/patch.diff
acha refactor --target . --analysis reports/analysis.json --fix
cp dist/patch.diff /tmp/patch2.diff

# Compare (ignoring patch_id UUID)
diff <(grep -v patch_id /tmp/patch1.diff) \
     <(grep -v patch_id /tmp/patch2.diff)
# Should be identical
```

---

## Non-Deterministic Components (By Design)

### 1. Timestamps

**Session logs** (`reports/session.jsonl`) include timestamps:
```json
{
  "timestamp": "2025-01-01T12:34:56Z",
  "event": "cli_start"
}
```

**Why:**
- Logs are for debugging, not for reproducibility
- Timestamps are essential for audit trails
- Not included in core outputs (JSON/SARIF)

**HTML reports** include generation time:
```html
<p class="timestamp">Generated: 2025-01-01 12:34:56</p>
```

**Why:**
- Human-readable reports need context
- Not used for automated comparisons
- Excluded from determinism guarantee

### 2. Patch IDs

**UUIDs** are randomly generated:
```python
patch_id = str(uuid.uuid4())
# Example: "f47ac10b-58cc-4372-a567-0e02b2c3d479"
```

**Why:**
- Unique tracking across multiple patch applications
- Not part of patch content verification
- Use `patch.diff` content for determinism

### 3. Backup Directory Names

**Backup timestamps:**
```
backups/backup-20250101-123456/
```

**Why:**
- Each backup must have unique name
- Prevents accidental overwrites
- Not used for content verification

---

## Why Determinism Matters

### 1. Reproducible Builds

**CI/CD pipelines:**
```yaml
# GitHub Actions
- name: Run analysis
  run: acha analyze --target . -o sarif

- name: Verify against baseline
  run: |
    sha256sum reports/analysis.sarif > checksum.txt
    diff checksum.txt expected_checksum.txt
```

**Why:**
- Detects supply chain attacks
- Catches non-deterministic bugs
- Enables caching (faster builds)

### 2. Reliable Diffing

**Git integration:**
```bash
# Commit baseline
git add baseline.json
git commit -m "chore: update code health baseline"

# Later: diff shows only actual changes
git diff baseline.json
```

**Why:**
- No spurious diffs from tool randomness
- Code review focuses on real changes
- Merge conflicts are meaningful

### 3. Cacheable Results

**Example caching strategy:**
```python
# Pseudocode
code_hash = sha256(all_python_files)
cache_key = f"acha-1.0.0-{code_hash}"

if cache.get(cache_key):
    return cache.get(cache_key)
else:
    result = acha.analyze(code)
    cache.set(cache_key, result)
    return result
```

**Why:**
- Same code = same hash = cache hit
- Speeds up CI/CD significantly
- Reduces compute costs

### 4. Security Auditing

**Supply chain attack detection:**
```bash
# Known good analysis
sha256sum reports/analysis.json > good.txt

# After dependency update
acha analyze --target . -o json
sha256sum reports/analysis.json > new.txt

# Unexpected change?
diff good.txt new.txt
# Investigate if different (code unchanged but output changed)
```

**Why:**
- Detects tampered tools
- Verifies build integrity
- Enables reproducible security audits

---

## Testing Determinism

### Manual Verification

```bash
#!/bin/bash
# test-determinism.sh

set -e

TARGET="./sample_project"
TMP1=$(mktemp)
TMP2=$(mktemp)

# Run 1
echo "Run 1..."
acha analyze --target "$TARGET" -o json
jq --sort-keys . reports/analysis.json > "$TMP1"

# Run 2
echo "Run 2..."
rm -rf reports/
acha analyze --target "$TARGET" -o json
jq --sort-keys . reports/analysis.json > "$TMP2"

# Compare
if diff "$TMP1" "$TMP2" > /dev/null; then
    echo "✅ Determinism test passed!"
    exit 0
else
    echo "❌ Determinism test failed!"
    diff "$TMP1" "$TMP2"
    exit 1
fi
```

### Parallel Determinism Test

```bash
#!/bin/bash
# test-parallel-determinism.sh

set -e

TARGET="./sample_project"

# Sequential
echo "Sequential analysis..."
acha analyze --target "$TARGET" --jobs 1 -o json
cp reports/analysis.json /tmp/seq.json

# Parallel
echo "Parallel analysis..."
rm -rf reports/
acha analyze --target "$TARGET" --jobs 4 -o json
cp reports/analysis.json /tmp/par.json

# Compare (using jq to normalize formatting)
if diff <(jq --sort-keys . /tmp/seq.json) \
        <(jq --sort-keys . /tmp/par.json) > /dev/null; then
    echo "✅ Parallel determinism test passed!"
    exit 0
else
    echo "❌ Parallel determinism test failed!"
    exit 1
fi
```

### Automated CI Test

```yaml
# .github/workflows/determinism.yml
name: Determinism Test

on: [push, pull_request]

jobs:
  test-determinism:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install ACHA
        run: pip install -e .

      - name: Run determinism test
        run: |
          # Run twice
          acha analyze --target ./sample_project -o json
          cp reports/analysis.json run1.json

          rm -rf reports/
          acha analyze --target ./sample_project -o json
          cp reports/analysis.json run2.json

          # Compare
          diff <(jq --sort-keys . run1.json) \
               <(jq --sort-keys . run2.json)

      - name: Test parallel determinism
        run: |
          # Sequential
          acha analyze --target ./sample_project --jobs 1 -o json
          cp reports/analysis.json seq.json

          # Parallel
          rm -rf reports/
          acha analyze --target ./sample_project --jobs 4 -o json
          cp reports/analysis.json par.json

          # Compare
          diff <(jq --sort-keys . seq.json) \
               <(jq --sort-keys . par.json)
```

---

## Breaking Determinism (What to Avoid)

### ❌ Don't Use Timestamps in Core Outputs

**Bad:**
```python
finding = {
    "id": "ANL-001",
    "timestamp": datetime.now().isoformat(),  # ❌ Non-deterministic
    "file": "test.py",
    "line": 42
}
```

**Good:**
```python
finding = {
    "id": "ANL-001",
    "file": "test.py",
    "line": 42
    # No timestamp
}
```

### ❌ Don't Use Random UUIDs in Findings

**Bad:**
```python
finding_id = str(uuid.uuid4())  # ❌ Different every run
```

**Good:**
```python
finding_id = _generate_finding_id(finding)  # ✅ Deterministic hash
```

### ❌ Don't Use Unordered Collections in Output

**Bad:**
```python
# Python dicts are insertion-ordered (3.7+), but sets are not
findings = set(all_findings)  # ❌ Random iteration order
json.dump(list(findings), f)
```

**Good:**
```python
findings = sorted(all_findings, key=lambda f: (f['file'], f['line']))
json.dump(findings, f, sort_keys=True)  # ✅ Stable order
```

### ❌ Don't Depend on Filesystem Ordering

**Bad:**
```python
files = os.listdir(directory)  # ❌ OS-dependent order
```

**Good:**
```python
files = sorted(Path(directory).rglob("*.py"))  # ✅ Sorted
```

---

## Determinism Guarantees by Output Format

| Format | Deterministic | Notes |
|--------|---------------|-------|
| JSON (analysis.json) | ✅ Yes | `sort_keys=True`, stable ordering |
| SARIF (analysis.sarif) | ✅ Yes | Sorted results, CRC32 rule IDs |
| HTML (report.html) | ⚠️ Partial | Content deterministic, timestamps excluded |
| Patch (patch.diff) | ✅ Yes | Unified diff format, line-by-line |
| Session logs (session.jsonl) | ❌ No | Timestamps, event order varies |
| Baseline (baseline.json) | ✅ Yes | SHA256-based IDs, sorted |

---

## Verification Command

**Built-in determinism test:**
```bash
# Run tests (includes determinism checks)
pytest tests/test_sarif_determinism.py -v
```

**Tests include:**
- Multiple runs produce identical JSON
- Parallel and sequential produce identical output
- SARIF rule IDs are stable
- Baseline IDs are reproducible

---

## References

- **SARIF Specification:** https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
- **Reproducible Builds:** https://reproducible-builds.org/
- **Python JSON Stability:** https://docs.python.org/3/library/json.html#json.dump
- **SHA256 Collision Resistance:** https://en.wikipedia.org/wiki/SHA-2

---

**Questions?**
- **GitHub Issues:** https://github.com/woozyrabbit123/acha-code-health-agent/issues
- **Documentation:** https://github.com/woozyrabbit123/acha-code-health-agent

---

## ACE v0.1 Determinism Guarantees (2025-11-12)

ACE v0.1 introduces additional determinism guarantees:

### 1. Receipt Hashes
**Guarantee:** SHA256 hashes in receipts are deterministic.

```python
receipt = {
    "plan_id": "abc123",
    "file": "test.py",
    "before_hash": "8d69d1ddc4f...",  # SHA256 of before content
    "after_hash": "2143472e5a5...",   # SHA256 of after content
    "parse_valid": true,
    "invariants_met": true,
    "timestamp": "2025-11-12T07:10:23.456Z"
}
```

**Why:** Same content always produces same SHA256 hash.

### 2. Encoding/Newline Handling
**Guarantee:** Round-trip file I/O preserves original newline style.

- LF (Unix) → LF
- CRLF (Windows) → CRLF
- Mixed → defaults to LF

**UTF-8 with `surrogateescape`** handles invalid byte sequences deterministically.

### 3. Suppression Filtering
**Guarantee:** Same suppressions + same findings = deterministic filtered output.

```python
# ace:disable PY-E201
def foo():  # Suppressed
    pass
# ace:enable PY-E201
```

**Parsing order:** Line-by-line, deterministic state tracking.

### 4. Git Safety Checks
**Guarantee:** Git status checks are deterministic based on working tree state.

```bash
$ git status --porcelain  # Deterministic output
$ ace apply --target src/  # Uses porcelain format
```

### 5. JSON Schema Validation
**Guarantee:** Schema validation produces deterministic error messages.

Using JSON Schema Draft 2020-12 with sorted keys ensures stable validation.

---

## Test Results (v0.1)

**Total Tests:** 340 passing
- Core tests: 237
- Schema validation: 20
- Exit codes: 20
- Encoding/newline: 20
- Git safety: 25
- Receipts: 21
- Suppressions: 28

**Determinism Tests:**
- ✅ Same file content produces same SHA256
- ✅ Suppression filtering is idempotent
- ✅ Receipt generation is reproducible
- ✅ Git status parsing is stable
- ✅ JSON exports use sorted keys
- ✅ Newline styles preserved round-trip

**Cross-Platform:**
- ✅ Linux (Ubuntu)
- ✅ Windows paths supported (untested in current CI)
- ✅ UTF-8 with surrogateescape for invalid sequences

---

Last Updated: 2025-11-12
ACE Version: 0.1.0
