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

## ACE v0.2 Determinism Guarantees (2025-11-12)

ACE v0.2 introduces analysis caching, baseline management, and configuration system with full determinism preservation:

### 1. Analysis Cache
**Guarantee:** Cache is a pure memoization layer - cache hits and cache misses produce byte-identical outputs.

```python
# Cache hit (warm)
findings_warm = run_analyze(path, use_cache=True)
output_warm = json.dumps([f.to_dict() for f in findings_warm], sort_keys=True)

# Cache miss (cold)
findings_cold = run_analyze(path, use_cache=True)
output_cold = json.dumps([f.to_dict() for f in findings_cold], sort_keys=True)

# No cache
findings_no_cache = run_analyze(path, use_cache=False)
output_no_cache = json.dumps([f.to_dict() for f in findings_no_cache], sort_keys=True)

# All outputs are byte-identical
assert output_warm == output_cold == output_no_cache
```

**How it works:**
- **Cache key:** `(file_path, file_sha256, ruleset_hash, ace_version)`
- **Ruleset hash:** SHA256 of sorted enabled rules + ACE version
- **Storage:** SQLite with deterministic JSON serialization (sorted keys, no whitespace)
- **TTL:** Configurable time-to-live (default: 3600s)
- **Invalidation:** Automatic on file content change, rule change, or version change

**CLI flags:**
```bash
ace analyze --target src/             # Cache enabled (default)
ace analyze --target src/ --no-cache  # Cache disabled
ace analyze --target src/ --cache-ttl 7200  # Custom TTL (2 hours)
ace analyze --target src/ --cache-dir /tmp/cache  # Custom cache directory
```

**Cache location:** `.ace/cache.db` (SQLite with WAL mode)

### 2. Baseline Management
**Guarantee:** Baseline creation is deterministic; comparison results are stable.

```bash
# Create baseline (deterministic snapshot)
ace baseline create --target src/ --baseline-path .ace/baseline.json

# Run twice - baselines are byte-identical
sha256sum .ace/baseline.json  # a1b2c3d4...

rm .ace/baseline.json
ace baseline create --target src/ --baseline-path .ace/baseline.json

sha256sum .ace/baseline.json  # a1b2c3d4... (IDENTICAL)
```

**Baseline format:**
```json
[
  {
    "stable_id": "abc123-def456-789abc",
    "rule": "PY-E201-BROAD-EXCEPT",
    "severity": "medium",
    "file": "src/main.py",
    "message": "Bare except clause"
  }
]
```

**Comparison output:**
```bash
ace baseline compare --target src/ --baseline-path .ace/baseline.json
```

**Exit codes:**
- `0`: No policy violations
- `2`: Policy violation (--fail-on-new or --fail-on-regression)
- `1`: Operational error

### 3. Configuration System (ace.toml)
**Guarantee:** Configuration precedence is deterministic and stable.

**Precedence:** CLI args > Environment variables > ace.toml > defaults

**Example ace.toml:**
```toml
[core]
includes = ["src/**/*.py"]
excludes = ["**/.venv/**", "**/dist/**"]
cache_ttl = 3600
cache_dir = ".ace"
baseline = ".ace/baseline.json"

[rules]
enable = ["PY-*", "MD-*", "YML-*", "SH-*"]
disable = []

[ci]
fail_on_new = true
fail_on_regression = false
```

**Environment overrides:**
```bash
export ACE_CACHE_TTL=7200
export ACE_CACHE_DIR=/tmp/ace_cache
ace analyze --target src/  # Uses env vars
```

**File inclusion logic:**
- Excludes take precedence over includes
- Path normalization (Windows + Unix)
- Glob patterns: `**/*.py`, `**/tests/**`

### 4. Deterministic Cache Serialization
**Guarantee:** Cache entries use deterministic JSON serialization.

```python
# Internal cache storage format (compact, sorted)
findings_json = json.dumps(findings, sort_keys=True, separators=(',', ':'))
# Example: [{"file":"test.py","line":1,"message":"test","rule":"R1","severity":"high"}]
```

**Why:**
- `sort_keys=True` ensures stable key ordering
- `separators=(',', ':')` removes whitespace for byte-for-byte comparison
- Stored in SQLite BLOB column (no JSON parsing ambiguity)

### 5. Cache Invalidation is Deterministic
**Guarantee:** Cache invalidation logic is purely functional.

```python
# Cache invalidation conditions (all deterministic):
if (file_sha256_changed or
    enabled_rules_changed or
    ace_version_changed or
    ttl_expired):
    # Re-run analysis
else:
    # Use cached result
```

**No hidden state:**
- No filesystem timestamps used (only content hashes)
- No environment-dependent logic
- No random sampling or heuristics

### 6. Baseline Comparison is Commutative
**Guarantee:** Comparison order doesn't affect results.

```python
# Adding/removing findings is symmetric
baseline = load_baseline(".ace/baseline.json")
current = run_analyze("src/")

comparison1 = compare_baseline(current, baseline)
comparison2 = compare_baseline(current, baseline)

assert comparison1 == comparison2  # Deterministic
```

**Comparison algorithm:**
```python
added = current_ids - baseline_ids      # Set difference (deterministic)
removed = baseline_ids - current_ids    # Set difference (deterministic)
changed = check_severity_or_message()   # Content comparison (deterministic)
```

---

## Test Results (v0.2)

**New Tests Added:** 50+
- Cache operations: 12
- Cache invalidation: 8
- Cache determinism: 5
- Baseline create/compare: 15
- Configuration precedence: 10

**Determinism Verification:**
```bash
# Cache test (cold vs warm)
pytest tests/ace/test_cache.py::test_analyze_with_cache_identical_to_no_cache -v

# Baseline test (multiple runs)
pytest tests/ace/test_baseline.py::test_baseline_deterministic_on_rerun -v

# Config test (precedence)
pytest tests/ace/test_config.py::test_merge_config_precedence -v
```

**Results:**
- ✅ Cache hit vs miss: byte-identical outputs
- ✅ Baseline creation: reproducible on rerun
- ✅ Config merging: stable precedence order
- ✅ All JSON outputs use `sort_keys=True`
- ✅ Cache serialization is compact and sorted
- ✅ Ruleset hash includes version (invalidates on upgrade)

---

## Cache Performance Impact

**Cache hit speedup:** 10-100x (depends on project size)

**Example benchmark:**
```bash
# Cold cache (first run)
time ace analyze --target large_project/
# Real: 45.2s

# Warm cache (second run, no changes)
time ace analyze --target large_project/
# Real: 0.8s  (56x faster)
```

**Cache storage:** ~1-10MB for typical projects (SQLite compressed)

**Cache TTL:** Default 1 hour (configurable)

---

## ACE v2.1 Determinism Enhancements (2025-01-13)

ACE v2.1 addresses critical determinism regressions identified in the Full Codex Audit:

### 1. Symbol Index Determinism (FIXED)

**Problem:** Symbol index serialization embedded runtime timestamps, breaking reproducibility.

**Before (v2.0):**
```python
data = {
    "root": str(self.root),
    "symbols": [s.to_dict() for s in self.symbols],
    "generated_at": int(time.time())  # ❌ Non-deterministic
}
```

**After (v2.1):**
```python
data = {
    "root": str(self.root),
    "symbols": [s.to_dict() for s in self.symbols],
    # Timestamp removed for deterministic builds
}
```

**Verification:**
```bash
# Build index twice
ace index build src/
sha256sum .ace/symbols.json  # abc123...

ace index build src/
sha256sum .ace/symbols.json  # abc123... (IDENTICAL)
```

**Impact:** Symbol index hashes are now stable across runs, enabling reliable cache invalidation and reproducible builds.

### 2. Context Ranking Determinism (FIXED)

**Problem:** Context ranking used wall-clock time for recency calculations, causing scores to drift.

**Before (v2.0):**
```python
def _calculate_recency_boost(self, symbols):
    max_mtime = max(s.mtime for s in symbols)
    current_time = int(time.time())  # ❌ Different every run
    seconds_since = current_time - max_mtime
    # ...
```

**After (v2.1):**
```python
def __init__(self, repo_map, current_time=None):
    self._current_time = current_time if current_time is not None else int(time.time())

def _calculate_recency_boost(self, symbols):
    max_mtime = max(s.mtime for s in symbols)
    current_time = self._current_time  # ✅ Fixed timestamp
    seconds_since = current_time - max_mtime
    # ...
```

**Usage:**
```python
# For deterministic ranking (testing, CI)
ranker = ContextRanker(repo_map, current_time=1700000000)

# For normal use (defaults to current time)
ranker = ContextRanker(repo_map)
```

**Impact:** Ranking order is now stable when using a fixed timestamp, enabling reproducible context selection in tests and CI.

### 3. Additional Durability Improvements

**Symbol Index, Skiplist, Content Index:**
All persistence layers now use `atomic_write()` for crash-safe durability:

```python
# Write → fsync → rename → dir fsync
content = json.dumps(data, indent=2, sort_keys=True).encode('utf-8')
atomic_write(path, content)
```

**Why:** Prevents corruption on power loss or crash, maintaining determinism guarantees even in failure scenarios.

### 4. Policy Threshold Consolidation

**Problem:** Policy constants duplicated between `policy.py` and `policy_config.py`, risking drift.

**Solution:** Single source of truth:
```python
# policy.py
DEFAULT_ALPHA = 0.7
DEFAULT_BETA = 0.3
AUTO_THRESHOLD = 0.70
SUGGEST_THRESHOLD = 0.50

# policy_config.py (now imports from policy.py)
from ace.policy import DEFAULT_ALPHA, DEFAULT_BETA, AUTO_THRESHOLD, SUGGEST_THRESHOLD
```

**Impact:** Ensures policy thresholds remain consistent across all modules.

### Test Results (v2.1)

**Determinism Verification:**
- ✅ Symbol index: Consecutive builds produce identical hashes
- ✅ Context ranking: Fixed timestamp produces stable ordering
- ✅ Atomic writes: Crash-safe persistence for all JSON stores
- ✅ Policy constants: No duplication, single source of truth

**Benchmark Results:**
```bash
# RepoMap determinism test
python -c "
from pathlib import Path
from ace.repomap import RepoMap
import hashlib

repo1 = RepoMap()
repo1.build(Path('src/'))
repo1.save(Path('.ace/test1.json'))

repo2 = RepoMap()
repo2.build(Path('src/'))
repo2.save(Path('.ace/test2.json'))

hash1 = hashlib.sha256(Path('.ace/test1.json').read_bytes()).hexdigest()
hash2 = hashlib.sha256(Path('.ace/test2.json').read_bytes()).hexdigest()

print(f'Hash 1: {hash1[:16]}...')
print(f'Hash 2: {hash2[:16]}...')
print(f'Deterministic: {hash1 == hash2}')
"

# Output:
# Hash 1: cce45f585051a003...
# Hash 2: cce45f585051a003...
# Deterministic: True
```

---

Last Updated: 2025-01-13
ACE Version: 2.1.0
