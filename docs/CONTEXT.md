# ACE v1.5: Context Engine Documentation

## Overview

ACE v1.5 introduces a powerful **Context Engine** that provides intelligent code understanding and prioritization through:

- **Symbol Indexer (RepoMap)** - Fast AST-based Python symbol extraction
- **Dependency Graph** - Lightweight file and symbol dependency analysis
- **Context Ranking** - Score and rank files by relevance, density, and recency
- **Impact Analyzer** - Predict affected files from changes
- **Interactive Diff UI** - Accept/reject changes per file

## Architecture

### Symbol Indexer (RepoMap)

The Symbol Indexer uses Python's stdlib `ast` module to parse Python files and extract symbols with zero external dependencies.

**Schema (`Symbol`):**

```python
{
  "name": str,           # Symbol name
  "type": str,           # "function", "class", or "module"
  "file": str,           # Relative path from repo root
  "line": int,           # Line number
  "deps": [str],         # Import dependencies (sorted)
  "mtime": int,          # File modification time (unix timestamp)
  "size": int            # File size in bytes
}
```

**Output Format (`symbols.json`):**

```json
{
  "root": "/path/to/repo",
  "generated_at": 1234567890,
  "symbols": [
    {
      "name": "MyClass",
      "type": "class",
      "file": "src/module.py",
      "line": 10,
      "deps": ["os", "typing"],
      "mtime": 1234567890,
      "size": 2048
    }
  ]
}
```

**Determinism:**
- Symbols sorted by `(file, line)`
- JSON keys sorted for stable output
- Same input → same hash across runs

### Dependency Graph

Builds file-to-file edges via imports and provides call graph analysis.

**Features:**
- `depends_on(file, depth)` - Transitive dependencies
- `who_calls(symbol)` - Reverse lookup (files that call a symbol)
- `who_depends_on(file)` - Direct dependents
- `find_cycles()` - Circular dependency detection

**Performance:**
- O(1) lookups via indexed edges
- BFS for transitive resolution
- Depth limiting for bounded analysis

### Context Ranking

Scores files based on multiple signals:

**Scoring Formula:**

```
score = (density_weight × symbol_density) +
        (recency_weight × recency_boost) +
        (relevance_weight × relevance_score)
```

**Components:**

1. **Symbol Density:**
   - `(functions + classes) / KLOC`
   - Normalized to 0-1 (capped at 100 symbols/KLOC)

2. **Recency Boost:**
   - `1.0 + min(0.5, days_since_mtime^{-1} × 7)`
   - Range: 1.0 (old) to 1.5 (recent)

3. **Relevance Score:**
   - File path match: 0.3
   - Symbol name matches: 0.7 (normalized by match count)

**Default Weights:**
- `recency_weight = 1.0`
- `density_weight = 1.0`
- `relevance_weight = 2.0` (query relevance prioritized)

### Impact Analyzer

Predicts affected files from changes using dependency graph traversal.

**Methods:**

- `predict_impacted(files, depth)` - Full impact report
- `explain_impact(file)` - Single file analysis
- `get_blast_radius(files, depth)` - Comprehensive metrics
- `find_bottlenecks(top_n)` - Most depended-upon files

**Risk Levels:**
- `low`: ≤3 impacted, ≤2 direct dependents
- `medium`: ≤10 impacted, ≤5 direct dependents
- `high`: ≤20 impacted, ≤10 direct dependents
- `critical`: >20 impacted or >10 direct dependents

## CLI Commands

### `ace index build`

Build symbol index for a repository.

```bash
ace index build --target /path/to/repo --index-path .ace/symbols.json
```

**Options:**
- `--target` - Directory to index (default: `.`)
- `--index-path` - Output path (default: `.ace/symbols.json`)

**Performance Target:** < 5 seconds for ACE repo (~50 files)

**Acceptance:**
- Deterministic: same hash for two consecutive runs
- Complete: all `.py` files indexed (excluding `.aceignore`)

### `ace index query`

Query the symbol index.

```bash
ace index query --pattern "analyze" --type function --limit 10
```

**Options:**
- `--pattern` - Symbol name pattern (substring match)
- `--type` - Filter by type (`function`, `class`, `module`)
- `--limit` - Max results (default: 50)
- `--index-path` - Index file (default: `.ace/symbols.json`)

**Output:** JSON array of matching symbols

### `ace graph who-calls <symbol>`

Find files that call a given symbol.

```bash
ace graph who-calls "analyze"
```

**Acceptance:** Returns ≥1 file for `analyze` in ACE repo

**Output:**
```json
{
  "symbol": "analyze",
  "callers": ["src/ace/autopilot.py", "src/ace/kernel.py"]
}
```

### `ace graph depends-on <file>`

Get transitive dependencies of a file.

```bash
ace graph depends-on src/ace/autopilot.py --depth 2
```

**Options:**
- `--depth` - Max depth (default: 2, -1 for unlimited)
- `--index-path` - Index file (default: `.ace/symbols.json`)

**Acceptance:** Non-empty for `src/ace/autopilot.py`

**Output:**
```json
{
  "file": "src/ace/autopilot.py",
  "dependencies": ["src/ace/kernel.py", "src/ace/policy.py"],
  "depth": 2
}
```

### `ace graph stats`

Show dependency graph statistics.

```bash
ace graph stats
```

**Output:**
```json
{
  "total_files": 50,
  "total_edges": 120,
  "avg_out_degree": 2.4,
  "top_importers": [{"file": "...", "imports": 10}],
  "top_imported": [{"file": "...", "dependents": 15}],
  "cycles": 0
}
```

### `ace context rank`

Rank files by relevance.

```bash
ace context rank --query "path" --limit 10
```

**Options:**
- `--query` - Search query for relevance scoring
- `--limit` - Max results (default: 10)
- `--index-path` - Index file (default: `.ace/symbols.json`)

**Acceptance:**
- Stable order across runs
- Max 10 results returned

**Output:**
```json
{
  "query": "path",
  "limit": 10,
  "results": [
    {
      "file": "src/ace/path_utils.py",
      "score": 15.234,
      "symbol_count": 8,
      "symbol_density": 0.85,
      "recency_boost": 1.45,
      "relevance_score": 0.9
    }
  ]
}
```

### `ace diff --interactive <patchfile>`

Interactive diff review and apply.

```bash
ace diff changes.patch --interactive
ace diff changes.patch --dry-run
```

**Options:**
- `--interactive` - Enable per-file accept/reject
- `--dry-run` - Don't apply changes

**Acceptance:**
- Interactive mode prompts for each file
- Accepted files only are applied
- Rejected files are skipped

**UI:**
```
======================================================================
MODIFIED src/ace/kernel.py
======================================================================
[Syntax-highlighted preview of changes]

Action [a]ccept / [r]eject / [v]iew / [q]uit (default: a):
```

## Autopilot Integration

### Loading Context Engine

When `--deep` is specified, autopilot:

1. Checks if `.ace/symbols.json` exists
2. If >24h old or missing, rebuilds index
3. Logs "RepoMap loaded" (or "Building symbol index...")
4. Initializes `ContextRanker`, `DepGraph`, `ImpactAnalyzer`

### Priority Calculation Enhancement

**Original Formula:**
```
priority = (R★ × 100) - cost_ms_rank - revisit_penalty
```

**v1.5 Enhanced:**
```
priority = (R★ × 100) - cost_ms_rank - revisit_penalty + context_boost
```

**Context Boost Calculation:**

For each file in plan:
1. Get file's symbol density and recency from RepoMap
2. Score using: `density_weight=0.5, recency_weight=0.3`
3. Average across all files in plan
4. Scale by 5.0 to contribute ~5 points max

**Effect:**
- Recent, dense files get slight priority boost
- Encourages fixing issues in active, important files first
- Does not dominate risk score (max +5 vs base 0-100)

## Performance Targets

| Operation | Target | ACE Repo |
|-----------|--------|----------|
| `index build` | <5s | 2-3s (50 files) |
| `index query` | <100ms | ~10ms |
| `graph depends-on` | <50ms | ~5ms |
| `context rank` | <200ms | ~20ms |
| `autopilot --deep` load | <1s | ~0.5s (cached) |

## Schema Reference

### `.ace/symbols.json`

Top-level:
- `root` (string): Repository root path
- `generated_at` (int): Unix timestamp
- `symbols` (array): List of Symbol objects

Symbol object:
- `name` (string): Symbol name
- `type` (string): "function" | "class" | "module"
- `file` (string): Relative path from root
- `line` (int): Line number (1-indexed)
- `deps` (array[string]): Sorted list of imports
- `mtime` (int): File modification time
- `size` (int): File size in bytes

**Determinism guarantees:**
- Symbols sorted by `(file, line)`
- All arrays sorted
- JSON keys sorted
- Timestamp in `generated_at` only (not in symbol comparison)

## Integration Patterns

### Use Case 1: Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Build/update index
ace index build --target .

# Get changed files
CHANGED=$(git diff --cached --name-only --diff-filter=ACMR | grep '\.py$')

# Predict impact
for file in $CHANGED; do
  ace graph who-depends-on "$file" --depth 1
done
```

### Use Case 2: Code Review Assistant

```bash
# Find files related to changes
ace index build
ace context rank --query "authentication" --limit 5

# Check impact of PR changes
for file in $(gh pr files); do
  ace graph depends-on "$file" --depth 2
done
```

### Use Case 3: Refactoring Planning

```bash
# Find bottleneck files
ace index build
ace graph stats | jq '.top_imported'

# Analyze blast radius before refactoring
ace impact analyze core_module.py --depth 3
```

## Troubleshooting

### Index not building

**Symptom:** `ace index build` takes >10s or fails

**Solutions:**
- Check for very large files (>1MB): add to `.aceignore`
- Check for syntax errors: use `python -m py_compile <file>`
- Verify Python version compatibility (3.10+)

### Stale index

**Symptom:** `ace graph` shows outdated dependencies

**Solution:**
```bash
rm .ace/symbols.json
ace index build --target .
```

### Autopilot not using context

**Symptom:** No "RepoMap loaded" message

**Solutions:**
- Ensure `--deep` flag is set
- Check `.ace/symbols.json` exists and is <24h old
- Verify `ace.repomap` module imports successfully

### Performance degradation

**Symptom:** Commands slow after index grows

**Solutions:**
- Exclude large directories in `.aceignore`:
  ```
  tests/fixtures/
  docs/generated/
  ```
- Limit depth for `depends-on` queries
- Use `--limit` for `context rank`

## Advanced Configuration

### Custom Ranking Weights

Programmatic usage:

```python
from ace.repomap import RepoMap
from ace.context_rank import ContextRanker

repo_map = RepoMap.load(".ace/symbols.json")
ranker = ContextRanker(repo_map)

# Emphasize recency over density
scores = ranker.rank_files(
    query="auth",
    limit=10,
    recency_weight=2.0,   # Default: 1.0
    density_weight=0.5,   # Default: 1.0
    relevance_weight=2.0  # Default: 2.0
)
```

### Custom Exclusions

Edit `.aceignore`:
```
__pycache__
*.pyc
.venv/
tests/
docs/
.mypy_cache/
```

### Impact Analysis Depth

Trade-off between thoroughness and performance:

- `depth=1`: Direct dependents only (fast, <10ms)
- `depth=2`: Direct + indirect (balanced, <50ms)
- `depth=3`: Three-hop analysis (thorough, <200ms)
- `depth=-1`: Unlimited (complete graph, may be slow)

## FAQ

**Q: Does RepoMap support languages other than Python?**

A: v1.5 supports Python only. Future versions may add TypeScript, Go, Rust via tree-sitter.

**Q: How does symbol indexing handle dynamic imports?**

A: Only static `import` and `from ... import` statements are tracked. Dynamic `__import__()` or `importlib` calls are not analyzed.

**Q: Can I use context ranking in CI/CD?**

A: Yes! Use `ace index build` in CI and commit `.ace/symbols.json` for fast lookups. Index build is deterministic.

**Q: What if my project has >1000 files?**

A: RepoMap is designed for repositories up to ~5000 files. Beyond that, consider excluding test fixtures or generated code.

**Q: How does interactive diff handle merge conflicts?**

A: Interactive diff applies cleanly parsed patches. For conflicts, use standard git merge resolution first, then review with `ace diff --interactive`.

## Version History

**v1.5.0** (2025-01-XX)
- Initial release of Context Engine
- Symbol indexer (RepoMap)
- Dependency graph
- Context ranking
- Impact analyzer
- Interactive diff UI
- Autopilot integration

---

**See Also:**
- [ACE Architecture](ARCHITECTURE.md)
- [CLI Reference](CLI.md)
- [Developer Guide](DEVELOPER.md)
