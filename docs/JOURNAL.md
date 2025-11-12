# ACE Journal System

Version: 0.6.0

## Overview

The ACE journal system provides safe, reversible file modifications without requiring git. It creates an append-only log (JSONL format) of all file changes, enabling exact restoration of previous states.

## Format

**Location:** `.ace/journals/<run_id>.jsonl`
**Format:** JSONL (JSON Lines) - one JSON object per line
**Guarantees:** `fsync()` after each write for crash safety

### Entry Types

#### 1. Intent Entry

Logged **before** modifying a file:

```json
{
  "type": "intent",
  "timestamp": "2024-01-01T12:00:00Z",
  "file": "src/example.py",
  "before_sha": "abc123...",
  "before_size": 1024,
  "rule_ids": ["PY-S101", "PY-E201"],
  "plan_id": "plan-uuid",
  "pre_image": "# First 4KB of original content..."
}
```

**Fields:**
- `before_sha`: SHA256 hash of file before modification (hex, no prefix)
- `before_size`: File size in bytes before modification
- `rule_ids`: Rule IDs triggering this modification
- `plan_id`: Unique plan identifier
- `pre_image`: First 4KB of original content for restoration

#### 2. Success Entry

Logged **after** successfully modifying a file:

```json
{
  "type": "success",
  "timestamp": "2024-01-01T12:00:01Z",
  "file": "src/example.py",
  "after_sha": "def456...",
  "after_size": 1100,
  "receipt_id": "receipt-uuid"
}
```

**Fields:**
- `after_sha`: SHA256 hash of file after modification
- `after_size`: File size in bytes after modification
- `receipt_id`: Receipt identifier for this operation

#### 3. Revert Entry

Logged when reverting a modification:

```json
{
  "type": "revert",
  "timestamp": "2024-01-01T12:00:02Z",
  "file": "src/example.py",
  "from_sha": "def456...",
  "to_sha": "abc123...",
  "reason": "parse-fail"
}
```

**Fields:**
- `from_sha`: SHA256 hash before revert
- `to_sha`: SHA256 hash after revert (should match original `before_sha`)
- `reason`: Reason for revert (e.g., `"parse-fail"`, `"manual"`)

## Usage

### Applying Changes with Journal

```bash
# Apply changes with default journal location
ace apply --target src/ --yes

# Apply with custom journal directory
ace apply --target src/ --yes --journal-dir .custom/journals
```

The journal is created automatically during `ace apply` operations.

### Reverting Changes

```bash
# Revert latest journal
ace revert --journal latest

# Revert specific journal by ID
ace revert --journal 550e8400-e29b-41d4-a716-446655440000

# Revert by path
ace revert --journal .ace/journals/my-journal.jsonl
```

### Revert Process

1. **Load journal** and build revert plan (reverse chronological order)
2. **Verify current state**: Check file hash matches expected `after_sha`
3. **Restore content**: Write original content from `pre_image`
4. **Verify restoration**: Ensure file was restored correctly

**Safety:**
- Skips files where current hash ≠ expected hash (prevents overwriting unexpected changes)
- Uses atomic writes (temp + fsync + rename) for crash safety
- Reports all failures without stopping

## Guarantees

### Crash Safety

- **Atomic writes**: Temp file + `fsync()` + atomic `rename()`
- **Journal fsync**: Each entry synced to disk before returning
- **Idempotent revert**: Can re-run revert if interrupted

### Integrity

- **Hash verification**: SHA256 hashes verify exact byte-for-byte restoration
- **Ordered entries**: JSONL preserves temporal ordering
- **Immutable log**: Append-only (never modified or deleted)

### Limitations

1. **4KB pre-image**: Only first 4KB stored for restoration
   - Large files may not be fully restored
   - Sufficient for most code files (<4KB)
   - Use git for full backup of large files

2. **No compression**: Journal files can grow large for many modifications
   - Typical: ~1KB per file modification
   - Clean up old journals manually if needed

3. **Local only**: No distributed/remote journal support
   - Journal stored locally in `.ace/journals/`
   - Use git for remote backups

## Best Practices

### 1. Regular Cleanup

```bash
# Remove journals older than 7 days
find .ace/journals -name "*.jsonl" -mtime +7 -delete
```

### 2. Combine with Git

```bash
# Stash before applying (for full backup)
ace apply --target src/ --yes --stash

# Commit after applying (creates git history)
ace apply --target src/ --yes --commit
```

### 3. Budget Limits

Use budget limits to prevent creating huge journals:

```bash
# Limit to 10 files
ace apply --target src/ --max-files 10 --yes

# Limit to 500 lines
ace apply --target src/ --max-lines 500 --yes
```

### 4. Verify Integrity

Auto-verification runs after each apply:

```
✓ Integrity OK (5 receipts)
```

Failed verification indicates:
- File modified after apply
- Hash mismatch
- File deleted

## Examples

### Example 1: Simple Apply and Revert

```bash
# Apply changes
$ ace apply --target src/example.py --yes
Applied 3 plan(s) to 1 file(s)
✓ Integrity OK (3 receipts)

# Revert if something went wrong
$ ace revert --journal latest
Reverting from journal: 550e8400-e29b-41d4-a716-446655440000
Found 1 file(s) to revert
  ✓ src/example.py

Reverted: 1 file(s)
```

### Example 2: Budget-Constrained Apply

```bash
$ ace apply --target src/ --max-files 5 --yes
Budget applied: including 5/12 plans

Budget Summary:
  Included: 5 plans (5 files, 87 lines)
  Excluded: 7 plans (7 files, 143 lines) - budget limit reached

Applied 5 plan(s) to 5 file(s)
✓ Integrity OK (5 receipts)
```

### Example 3: Auto-Revert on Parse Fail

```bash
$ ace apply --target src/broken.py --yes
⚠️  Auto-reverted src/broken.py: parse check failed
Applied 0 plan(s) to 0 file(s)
```

## Troubleshooting

### "Hash mismatch" during revert

**Cause:** File was modified after `ace apply`
**Solution:** Manually restore file or use git to revert

### "Journal not found"

**Cause:** Journal file deleted or invalid run ID
**Solution:** List journals: `ls .ace/journals/` and use specific path

### "Integrity check failed"

**Cause:** File modified between apply and verification
**Solution:** Re-run apply or investigate which process modified the file

## See Also

- [PERFORMANCE.md](./PERFORMANCE.md) - Incremental scanning and cache warmup
- [README.md](../README.md) - General ACE documentation
