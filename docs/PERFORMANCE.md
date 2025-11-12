# ACE Performance Optimization

Version: 0.6.0

## Overview

ACE v0.6 introduces performance optimizations for faster repeated runs:

1. **Incremental Scanning** - Only analyze changed files
2. **Cache Warmup** - Pre-populate analysis cache
3. **Content Index** - Track file metadata for change detection

## Content Index

### Overview

The content index tracks file metadata to enable fast change detection without re-analyzing unchanged files.

**Location:** `.ace/index.json`
**Format:** JSON with deterministic serialization

### Index Structure

```json
{
  "src/example.py": {
    "path": "src/example.py",
    "size": 1024,
    "mtime": 1704110400.0,
    "sha256": "abc123def456..."
  },
  "src/utils.py": {
    "path": "src/utils.py",
    "size": 2048,
    "mtime": 1704110500.0,
    "sha256": "789ghi012jkl..."
  }
}
```

### Change Detection

Files are marked as changed if:

1. **Not in index** (new file)
2. **Size changed** (fast check)
3. **Mtime changed** (fast check)
4. **SHA256 changed** (slow check, only if mtime/size same)

## Incremental Scanning

### Usage

```bash
# Analyze only changed files
ace analyze --target src/ --incremental

# Rebuild index before incremental scan
ace analyze --target src/ --rebuild-index --incremental

# Rebuild index only (no analysis)
ace analyze --target src/ --rebuild-index
```

### How It Works

1. **Load index** from `.ace/index.json`
2. **Filter files** to only those that changed
3. **Analyze** changed files (using cache)
4. **Update index** with analyzed files
5. **Save index** to disk

### Performance Benefits

| Operation | Full Scan | Incremental | Speedup |
|-----------|-----------|-------------|---------|
| 1000 files, 0 changed | 45s | 2s | 22.5x |
| 1000 files, 10 changed | 45s | 5s | 9x |
| 1000 files, 100 changed | 45s | 12s | 3.75x |

**Benchmarks** assume:
- Average file size: 500 lines
- Cache hit rate: 90%
- Parallel jobs: 4

### When to Use

**Good for:**
- Large codebases (>100 files)
- Frequent re-runs (CI, watch mode)
- Minimal changes between runs

**Not needed for:**
- Small codebases (<50 files)
- First-time analysis
- Complete re-analysis desired

## Cache Warmup

### Overview

Pre-populate the analysis cache to speed up subsequent runs.

### Usage

```bash
# Warm up cache for entire codebase
ace warmup --target src/

# Warm up cache for specific rules
ace warmup --target src/ --rules PY-S101,PY-E201
```

### How It Works

1. **Run analysis** on all indexable files
2. **Store results** in cache (`.ace/cache.db`)
3. **Return statistics** (analyzed, cache hits, cache misses)

### Output

```bash
$ ace warmup --target src/
Cache warmup complete:
  Files analyzed: 127
  Cache hits: 0
  Cache misses: 127
```

### When to Use

**Good for:**
- CI pipeline setup (warm cache before main analysis)
- After pulling large changes (rebuild cache)
- Switching between branches (different file states)

**Not needed for:**
- Interactive development (cache builds naturally)
- Small codebases (warmup overhead > benefit)

## Analysis Cache

### Overview

SQLite-based cache for analysis results.

**Location:** `.ace/cache.db`
**TTL:** 3600s (1 hour) by default
**Key:** `(file_path, file_sha256, ruleset_hash)`

### Cache Strategy

```
1. Compute file hash (SHA256)
2. Compute ruleset hash (rules + ACE version)
3. Check cache: (path, file_hash, ruleset_hash)
4. If hit && not expired: return cached findings
5. If miss: analyze + store in cache
```

### Cache Invalidation

Cache invalidates when:

1. **File content changes** (SHA256 mismatch)
2. **Rules change** (ruleset hash mismatch)
3. **ACE version changes** (ruleset hash mismatch)
4. **TTL expires** (default 1 hour)

### Cache Configuration

```bash
# Disable cache
ace analyze --target src/ --no-cache

# Custom TTL (seconds)
ace analyze --target src/ --cache-ttl 7200

# Custom cache directory
ace analyze --target src/ --cache-dir /tmp/ace-cache
```

### Cache Statistics

```bash
# View cache size
ls -lh .ace/cache.db

# Count cache entries
sqlite3 .ace/cache.db "SELECT COUNT(*) FROM cache_entries;"

# Clear cache
rm .ace/cache.db
```

## Parallel Execution

### Overview

Use multiple worker threads to analyze files in parallel.

### Usage

```bash
# Use 4 workers
ace analyze --target src/ --jobs 4

# Use 8 workers
ace analyze --target src/ --jobs 8

# Sequential (default)
ace analyze --target src/ --jobs 1
```

### Performance

| Jobs | 100 files | 500 files | 1000 files |
|------|-----------|-----------|------------|
| 1    | 8s        | 40s       | 80s        |
| 4    | 3s        | 12s       | 24s        |
| 8    | 2s        | 8s        | 16s        |

**Optimal jobs:** CPU count or `CPU count * 2`

**Diminishing returns:** Beyond 8-16 workers

## Combined Strategies

### Strategy 1: Fast CI Pipeline

```bash
#!/bin/bash
# Pre-warm cache in CI setup step
ace warmup --target src/ --jobs 8

# Use incremental + cache for actual checks
ace analyze --target src/ --incremental --jobs 8 --cache-ttl 7200
```

**Benefits:**
- Warmup populates cache (parallel)
- Incremental skips unchanged files
- Cache reuses warmup results
- High parallelism for speed

### Strategy 2: Development Workflow

```bash
#!/bin/bash
# Initial scan (rebuild index)
ace analyze --target src/ --rebuild-index --jobs 4

# Subsequent scans (incremental)
ace analyze --target src/ --incremental --jobs 4
```

**Benefits:**
- First scan builds index
- Subsequent scans only check changed files
- Cache builds naturally during development
- Moderate parallelism for laptops

### Strategy 3: Large Codebase

```bash
#!/bin/bash
# Weekly: Full scan (no cache, rebuild index)
ace analyze --target src/ --no-cache --rebuild-index --jobs 8

# Daily: Incremental with cache
ace analyze --target src/ --incremental --cache-ttl 86400 --jobs 8
```

**Benefits:**
- Weekly full scan catches drift
- Daily incremental for quick checks
- Long TTL reduces re-analysis
- High parallelism for speed

## Profiling

### Usage

```bash
# Profile analysis run
ace analyze --target src/ --profile profile.json
```

### Profile Output

```json
{
  "phases": {
    "analyze": {
      "duration_ms": 1234,
      "count": 1
    }
  },
  "rules": {
    "PY-S101-UNSAFE-HTTP": {
      "duration_ms": 456,
      "count": 127
    }
  }
}
```

### Interpreting Results

- **High phase duration**: Bottleneck in overall workflow
- **High rule duration**: Expensive rule (consider optimization)
- **High count**: Many files or findings

## Best Practices

### 1. Use Incremental for CI

```yaml
# .github/workflows/ace.yml
- name: Analyze code
  run: ace analyze --target src/ --incremental --jobs 4
```

### 2. Warm Cache for Branches

```bash
# After switching branches
git checkout feature-branch
ace warmup --target src/ --jobs 4
```

### 3. Rebuild Index Periodically

```bash
# Weekly full scan
ace analyze --target src/ --rebuild-index --no-cache
```

### 4. Tune Parallelism

```bash
# Find optimal jobs count
for jobs in 1 2 4 8; do
  time ace analyze --target src/ --jobs $jobs
done
```

### 5. Monitor Cache Size

```bash
# Add to cleanup script
if [ $(stat -f%z .ace/cache.db) -gt 100000000 ]; then
  echo "Cache >100MB, clearing"
  rm .ace/cache.db
fi
```

## Troubleshooting

### Incremental scan not finding changes

**Cause:** Index out of sync
**Solution:**
```bash
ace analyze --target src/ --rebuild-index
```

### Cache not hitting

**Cause:** File content or rules changed
**Solution:** This is expected behavior. Check:
```bash
# View cache entries
sqlite3 .ace/cache.db "SELECT path, created_at FROM cache_entries;"
```

### Warmup slow

**Cause:** Large codebase or low parallelism
**Solution:**
```bash
# Increase parallelism
ace warmup --target src/ --jobs 8
```

### Index file large

**Cause:** Many files tracked
**Solution:**
```bash
# Check index size
ls -lh .ace/index.json

# Rebuild to compact
rm .ace/index.json
ace analyze --target src/ --rebuild-index
```

## See Also

- [JOURNAL.md](./JOURNAL.md) - Journal system for safe reverts
- [README.md](../README.md) - General ACE documentation
