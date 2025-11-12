# ACE Learning v2

Adaptive thresholds and personal memory system for ACE.

## Overview

Learning v2 enhances ACE's self-learning capabilities with per-rule tracking, auto-skiplist patterns, and weekly decay for time-weighted statistics.

## Features

### Per-Rule Tracking

Each rule tracks:
- `success_rate`: Applied / (Applied + Reverted)
- `revert_rate`: Reverted / (Applied + Reverted)
- `sample_size`: Total actions (minimum 5 for threshold tuning)

### Auto-Skiplist

Automatically adds file patterns to skiplist after **3 consecutive reverts** for a (rule, file) pair. This prevents ACE from repeatedly suggesting problematic fixes.

### Weekly Decay

Statistics are decayed by **0.8 per week** to prioritize recent behavior:
```python
multiplier = 0.8 ** weeks_elapsed
```

### Tuned Thresholds

Thresholds are dynamically adjusted based on rule performance:
- **High revert rate (>25%)**: Raise threshold by +0.05 (more conservative)
- **High success rate (>80%)**: Lower threshold by -0.05 (more aggressive)
- **Clamped to [0.60, 0.85]**

## CLI Commands

### Show Learning Statistics

```bash
ace learn show
```

Displays:
- Top rules by revert rate
- Rules with tuned (non-default) thresholds
- Auto-skiplist patterns
- Sample sizes

### Reset Learning Data

```bash
ace learn reset
```

Clears all learning history.

## Integration

Learning v2 is automatically wired into:
- **Autopilot**: Uses tuned thresholds for policy decisions
- **Budgeting**: Prefers high-success rules in priority calculation
- **Kernel**: Records outcomes (applied, reverted, suggested, skipped)

## Storage

Learning data is persisted to `.ace/learn.json` with deterministic serialization:

```json
{
  "auto_skiplist": {
    "PY-E201-BROAD-EXCEPT": ["src/legacy.py"]
  },
  "rules": {
    "PY-E201-BROAD-EXCEPT": {
      "applied": 50,
      "consecutive_reverts": {},
      "last_updated": 1699564800.0,
      "reverted": 5,
      "skipped": 0,
      "suggested": 0
    }
  },
  "tuning": {
    "alpha": 0.7,
    "beta": 0.3,
    "min_auto": 0.7,
    "min_suggest": 0.5
  }
}
```

## Example

```bash
# Run autopilot (automatically uses learning)
ace autopilot --target . --allow auto

# View tuned thresholds after several runs
ace learn show

# Output:
# Rules with tuned thresholds:
# Rule ID                             Tuned Threshold    Sample Size
# -----------------------------------------------------------------
# PY-E201-BROAD-EXCEPT                          0.75            12
```

## API

```python
from ace.learn import LearningEngine

learning = LearningEngine()
learning.load()

# Get tuned threshold
threshold = learning.tuned_threshold("PY-E201-BROAD-EXCEPT")

# Check if file should be skipped
should_skip = learning.should_skip_file_for_rule("PY-E201", "legacy.py")

# Record outcome
learning.record_outcome("PY-E201", "applied", file_path="test.py")
```
