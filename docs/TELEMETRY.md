# ACE Telemetry v2

Performance tracking and profiling system for ACE.

## Overview

Telemetry v2 provides rich performance metrics with p95 percentiles, success/failure tracking, and time-filtered aggregation.

## Features

### Enhanced JSONL Logging

Each rule execution is logged with extended metadata:

```json
{
  "files": 1,
  "ms": 45.23,
  "ok": true,
  "reverted": false,
  "rule_id": "PY-E201-BROAD-EXCEPT",
  "timestamp": 1699564800.123
}
```

Fields:
- `ms`: Execution duration in milliseconds
- `files`: Number of files processed
- `ok`: Execution succeeded
- `reverted`: Was the change reverted (PatchGuard)

### Aggregation with P95

Summary statistics include:
- **Mean**: Average execution time
- **P95**: 95th percentile (tail latency)
- **Count**: Number of executions

### Time Filtering

Filter telemetry by time window:

```bash
ace telemetry summary --days 7
```

## CLI Commands

### Summary

```bash
ace telemetry summary --days 7
```

Output:
```
ACE Telemetry Summary (last 7 days)
============================================================

Total executions                  : 1523
Unique rules                      : 15

Top 10 slowest rules (by p95):

Rule ID                             Mean (ms)    P95 (ms)     Count
---------------------------------------------------------------------------
PY-E201-BROAD-EXCEPT                    45.23       67.89       342
PY-I101-IMPORT-SORT                     32.45       48.12       287
PY-S201-SUBPROCESS-CHECK                28.91       42.34       198
```

## Storage

Telemetry is persisted to `.ace/telemetry.jsonl` in append-only mode:

```jsonl
{"files": 1, "ms": 45.23, "ok": true, "reverted": false, "rule_id": "PY-E201", "timestamp": 1699564800.123}
{"files": 1, "ms": 32.45, "ok": true, "reverted": false, "rule_id": "PY-I101", "timestamp": 1699564801.234}
```

## Integration

Telemetry is automatically instrumented in:
- **Kernel (run_analyze)**: All rule executions wrapped with `time_block()`
- **Kernel (run_apply)**: Apply operations tracked with extended metadata
- **Autopilot**: Used for cost-based prioritization

## Performance Insights

Use telemetry to:
1. **Identify slow rules**: Focus optimization efforts
2. **Track p95 tail latency**: Catch performance regressions
3. **Optimize budgeting**: Prefer fast, high-success rules
4. **Monitor revert rates**: Correlate with PatchGuard failures

## API

```python
from ace.telemetry import Telemetry

telemetry = Telemetry()

# Record execution
telemetry.record(
    rule_id="PY-E201",
    duration_ms=45.23,
    files=1,
    ok=True,
    reverted=False
)

# Get summary
stats = telemetry.summary(days=7)

print(f"Mean: {stats.per_rule_avg_ms['PY-E201']:.2f}ms")
print(f"P95: {stats.per_rule_p95_ms['PY-E201']:.2f}ms")
print(f"Count: {stats.per_rule_count['PY-E201']}")
```

## Example Workflow

```bash
# Run analysis (telemetry collected automatically)
ace analyze .

# View performance summary
ace telemetry summary --days 30

# Identify slow rules and optimize
# (e.g., add caching, reduce complexity)
```
