# ACE Architecture

## System Overview

ACE (Autonomous Code Editor) is a modular code health analysis and refactoring system built on four core subsystems that work together to provide intelligent, safe code transformations.

### Core Architecture

```
┌─────────────┐
│   Context   │  (Repository analysis, symbol indexing, dependency graphs)
│   Engine    │  
└──────┬──────┘
       │
       v
┌─────────────┐
│  Learning   │  (Adaptive thresholds, auto-skiplist, telemetry)
│   Engine    │  
└──────┬──────┘
       │
       v
┌─────────────┐
│   Planner   │  (Risk scoring, prioritization, action rationales)
│             │
└──────┬──────┘
       │
       v
┌─────────────┐
│   Repair    │  (Binary search isolation, safe subset salvage)
│   Engine    │  
└─────────────┘
```

### Component Flow

1. **Context Engine** — Builds symbol index (RepoMap), tracks dependencies (DepGraph), and ranks files by relevance for targeted analysis
2. **Learning Engine** — Records apply/revert outcomes, tunes risk thresholds adaptively, and maintains auto-skiplist patterns to avoid repeated failures
3. **Planner** — Evaluates edit plans using multi-factor risk scoring (severity × complexity × cohesion), prioritizes actions, and generates rationales for transparency
4. **Repair Engine** — When guard failures occur, uses binary search to isolate problematic edits, salvages safe subsets, and generates detailed repair reports

### Data Flow

```
Files → Context (index/rank) → Analyze (detect issues) →
Refactor (generate plans) → Learning (filter/tune) →
Planner (prioritize) → Apply (with guards) →
Repair (if needed) → Learning (record outcome)
```

### Safety Mechanisms (PatchGuard)

ACE implements multi-layer verification in `ace.guard` to prevent semantic tampering and ensure safe code transformations:

**Layer 1: Parse Verification**
- Ensures syntax validity after edits
- Catches basic syntax errors before application

**Layer 2: AST Equivalence** (strict mode)
- Verifies structural equivalence between before/after code
- Ensures refactoring preserves program semantics

**Layer 2.5: Symbol Count Verification**
- Counts functions, classes, and imports in before/after code
- Detects unintended additions or removals of code entities

**Layer 2.6: AST Hash Verification** (v2.1+)
- Computes cryptographic hash of AST structure
- **In strict mode:** Fails on hash mismatch to detect semantic tampering
- **In non-strict mode:** Logs mismatches for telemetry
- Prevents bypass of equivalence checks via CST-only transforms

**Layer 3: CST Roundtrip**
- Verifies LibCST can parse and regenerate the code
- Ensures formatting/whitespace changes are safe

**Additional Guards:**
- **Import Preservation**: Verify critical imports remain
- **Binary Search Repair**: Isolate failing edits automatically
- **Journal Revert**: Full undo capability for all changes

### Key Design Principles

1. **Determinism** - Same input always produces same output
2. **Offline-First** - No network dependencies
3. **Incremental Learning** - System improves from user feedback
4. **Defense in Depth** - Multiple safety layers prevent breakage
5. **Transparent Reasoning** - All decisions include rationales

## Module Structure

### Core Modules

- `ace.kernel` - Analysis and refactoring orchestration
- `ace.uir` - Unified Issue Representation (cross-language findings)
- `ace.policy` - Risk scoring and thresholds (R* scoring)
- `ace.guard` - Safety verification (parse, AST, imports)
- `ace.learn` - Adaptive learning and skiplist management
- `ace.planner` - Action prioritization (v2.0)
- `ace.repair` - Edit failure isolation and salvage (v2.0)

### Analysis Modules

- `ace.skills.quick_detects` - Fast AST-based pattern detection
- `ace.skills.python` - Python-specific analyzers
- `ace.codemods.*` - Automated transformation rules
- `ace.packs_builtin` - Bundled codemod packs

### Supporting Infrastructure

- `ace.repomap` - Symbol indexing (functions, classes, modules)
- `ace.depgraph` - Dependency graph analysis
- `ace.context_rank` - File relevance ranking
- `ace.impact` - Change impact analysis
- `ace.telemetry` - Performance tracking (local only)
- `ace.tui` - Terminal UI dashboard

## Extension Points

### Adding New Rules

1. Create analyzer in `ace.skills/` directory
2. Register in `ace.kernel.run_analyze()`
3. Add codemod in `ace.codemods/` if automated fix exists
4. Define pack in `ace.packs_builtin` for grouped application

### Custom Packs

```python
from ace.packs_builtin import CodemodPack

pack = CodemodPack(
    id="CUSTOM_PACK",
    name="My Custom Pack",
    description="Description here",
    codemods=[MyCodemod1, MyCodemod2],
    risk_level="low",
    category="style"
)
```

## Configuration Files

- `.ace/config.toml` - Analysis configuration
- `.ace/policy.toml` - Risk thresholds and scoring weights
- `.ace/skiplist.json` - Manual suppressions
- `.ace/learning.json` - Adaptive learning data
- `.ace/telemetry.json` - Performance metrics
- `.aceignore` - File exclusion patterns (gitignore format)

## Performance Characteristics

- **Incremental Analysis**: Only re-analyze changed files
- **Cache TTL**: Default 1 hour for analysis results
- **Parallel Execution**: Multi-core analysis (jobs parameter)
- **Binary Search Repair**: O(log n) edit isolation
- **Symbol Index**: Built once, reused for 24 hours

## Version History

- **v1.0**: Initial release with basic analysis
- **v1.5**: Context Engine (RepoMap, DepGraph, ranking)
- **v1.6**: Codemod packs and pre-commit integration
- **v1.7**: Learning v2, Telemetry v2, TUI Dashboard
- **v2.0**: Planner v1, Optional LLM Assist, Local CI
- **v2.1**: Full Codex Audit fixes (current)
  - **P0 Fixes**: Moved mandatory deps to core, removed non-deterministic timestamps, enforced PatchGuard AST hash verification
  - **P1 Fixes**: Deterministic context ranking, hardened subprocess execution, aligned CI matrix, atomic writes for all persistence
  - **Security**: AST hash mismatches now fail in strict mode (previously informational-only)
  - **Determinism**: Symbol index and context ranking now fully reproducible
  - **Durability**: All JSON persistence uses atomic write (fsync + rename)

## Development Workflow

```bash
# Install development dependencies
pip install -e .[dev,test]

# Run tests with coverage
pytest --cov=ace --cov-fail-under=85

# Format code
black src/ tests/
ruff check .

# Build symbol index for testing
ace index build --target ./sample_project

# Run full autopilot on sample project
ace autopilot --target ./sample_project --dry-run
```

## Future Roadmap

- **v2.2**: CLI refactoring for plugin architecture
- **v2.3**: Multi-language support (JavaScript, TypeScript)
- **v2.4**: Advanced impact analysis with call graphs
- **v2.5**: Distributed analysis for monorepos
