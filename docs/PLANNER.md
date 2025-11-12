# ACE Planner v1

Deterministic action prioritization system for ACE.

## Overview

Planner v1 replaces ad-hoc priority calculations with a comprehensive, deterministic system that uses all available context (Learning, Telemetry, RepoMap) to order refactoring actions by strategic value.

## Priority Formula

Each action is assigned a priority score using a multi-factor formula:

```
priority = 100*R★ + 20*cohesion - cost_rank - revert_penalty + context_boost + success_rate_bonus
```

### Components

#### Base Priority: `100 * R★`
- **R★ (R-star)** is the plan's estimated risk score from `EditPlan.estimated_risk`
- Range: 0.0 to 1.0
- Multiplied by 100 to dominate the formula
- Higher R★ = higher confidence = higher priority

#### Cohesion Bonus: `+20`
- Awarded when multiple issues affect the **same file**
- Encourages batching related fixes
- Reduces context switching across the codebase

#### Cost Penalty: `-cost_rank`
- Based on **telemetry p95 latency** for the rule(s) in this plan
- Rules ranked by slowness (higher rank = slower)
- Deters slow, expensive rules in favor of fast wins
- Example: If rule has rank 3 out of 10 rules, penalty is -3

#### Revert Penalty: `-20`
- Applied if **learning data** shows this context has high revert history
- Uses `LearningEngine.should_skip_context(ctx_key, threshold=0.5)`
- Prevents repeatedly attempting fixes that historically fail

#### Context Boost: `+context_boost`
- Calculated from **RepoMap symbol importance** (if context engine available)
- Measures how "central" the affected files are to the codebase
- Formula: `(total_symbol_score / num_files) * 5.0`
- Prioritizes fixes in core/shared code over leaf modules

#### Success Rate Bonus: `+success_rate_bonus`
- Based on **learning success rate** for the rule(s)
- Formula: `avg_success_rate * 10.0`
- Rewards rules with proven track record
- Range: 0-10 points (0% to 100% success)

## Rationale Generation

Each action includes a human-readable rationale explaining the priority:

```python
rationale = f"R★={rstar:.2f} (base={base_priority:.1f}), "
if cohesion_bonus > 0:
    rationale += f"cohesion={cohesion_bonus:.0f}, "
if cost_penalty > 0:
    rationale += f"cost_penalty=-{cost_penalty:.1f}, "
if revert_penalty > 0:
    rationale += f"revert_penalty=-{revert_penalty:.0f}, "
if context_boost > 0:
    rationale += f"context_boost=+{context_boost:.1f}, "
if success_rate_bonus > 0:
    rationale += f"success_rate_bonus=+{success_rate_bonus:.1f}, "
rationale += f"total={priority:.1f}"
```

Example output:
```
R★=0.85 (base=85.0), cohesion=20, cost_penalty=-2.5, context_boost=+12.3, success_rate_bonus=+8.5, total=123.3
```

## Integration

### Autopilot

Planner v1 is automatically used in `ace autopilot`:

```python
from ace.planner import Planner, PlannerConfig

planner_config = PlannerConfig(
    target=cfg.target,
    use_context_engine=CONTEXT_ENGINE_AVAILABLE and repo_map is not None,
    use_learning=True,
    use_telemetry=True,
)
planner = Planner(planner_config)
actions = planner.plan_actions(approved_plans)

# Extract ordered plans
ordered_plans = [action.plan for action in actions]
```

### Rationale Logging

Autopilot logs rationales for the top 5 actions:

```bash
$ ace autopilot --target . --allow auto

Planning actions with Planner v1...

Planned 47 action(s):

  1. PY-E201-BROAD-EXCEPT-3fa2b (priority=123.3)
     Rationale: R★=0.85 (base=85.0), cohesion=20, context_boost=+12.3, success_rate_bonus=+8.5, total=123.3

  2. PY-I101-IMPORT-SORT-7c8d1 (priority=118.7)
     Rationale: R★=0.92 (base=92.0), cost_penalty=-2.5, context_boost=+18.2, success_rate_bonus=+9.0, total=118.7

  ...
```

## Configuration

```python
@dataclass
class PlannerConfig:
    target: Path
    use_context_engine: bool = True  # Enable RepoMap-based context_boost
    use_learning: bool = True        # Enable success_rate_bonus and revert_penalty
    use_telemetry: bool = True       # Enable cost_penalty from p95 latency
```

## API

```python
from ace.planner import Planner, PlannerConfig, Action

planner = Planner(PlannerConfig(target=Path(".")))
actions: list[Action] = planner.plan_actions(approved_plans)

for action in actions:
    print(f"{action.plan.id}: priority={action.priority:.1f}")
    print(f"  Rationale: {action.rationale}")
```

## Action Dataclass

```python
@dataclass
class Action:
    plan: EditPlan          # The refactoring plan
    priority: float         # Computed priority score
    rationale: str          # Human-readable explanation
```

## Determinism

Planner v1 is **fully deterministic**:
- Priority calculation uses only plan metadata, learning stats, telemetry stats, and repo map
- Ties are broken by `plan.id` (lexicographic sort)
- No randomness or timestamps affect ordering
- Same inputs → same action ordering

## Performance

Planner is optimized for speed:
- O(N log N) complexity for N plans (dominated by sorting)
- Telemetry ranking done once at initialization
- Context lookups cached per plan
- Typical overhead: <50ms for 100 plans

## Example Workflow

```bash
# Run autopilot (uses Planner v1 automatically)
ace autopilot --target . --allow auto

# Observe rationales in output
# Top actions will show why they were prioritized

# Planner adapts over time as:
# - Learning accumulates success/revert data
# - Telemetry tracks rule performance
# - RepoMap identifies core files
```

## Comparison to Ad-Hoc Ordering

**Before (v1.x):**
- Simple cost-based sorting: `key = (cost_ms, -rstar)`
- No cohesion awareness
- No revert history consideration
- No context/importance weighting

**After (v2.0 with Planner v1):**
- Multi-factor formula balancing 6 components
- Cohesion bonus for file locality
- Revert penalty from learning
- Context boost for central code
- Success rate bonus
- Transparent rationales

## Future Enhancements (v2.1+)

Potential additions:
- **Dependency ordering**: Apply plans in dependency order (using DepGraph)
- **User preferences**: Allow custom weights for formula components
- **Interactive mode**: `ace plan --interactive` to manually reorder
- **Batch constraints**: "Apply all plans touching file X together"
