# Changelog

All notable changes to the ACHA/ACE (Autonomous Code-Health Agent / Autonomous Code Editor) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [ACE 2.1.0] - 2025-01-13

### Fixed - ACE v2.1 Codex Audit (P0/P1)

This release addresses all critical and high-priority findings from the comprehensive ACE v2.1 Full Codex Audit.

#### P0 Fixes (Critical - Blocking Production)

- **Dependencies**: Moved mandatory runtime dependencies to core requirements
  - `libcst`, `markdown-it-py`, `pyyaml`, and `textual` now in base `dependencies` array
  - Fixes `ModuleNotFoundError` on CLI startup in default installations
  - Eliminates need for `pip install acha-code-health[ace]` extras
  - File: `pyproject.toml`

- **Determinism**: Removed non-deterministic timestamp from symbol index
  - Symbol index serialization no longer embeds `generated_at = int(time.time())`
  - Consecutive `ace index build` runs now produce identical SHA256 hashes
  - Enables reproducible builds and cache invalidation
  - File: `src/ace/repomap.py`

- **Security**: Enforced PatchGuard AST hash verification
  - AST hash mismatches now fail in strict mode (previously `pass`)
  - Detects semantic tampering via CST-only transforms
  - Returns `GuardResult(passed=False, guard_type="ast_hash")` on hash divergence
  - File: `src/ace/guard.py`

#### P1 Fixes (High Priority)

- **Determinism**: Made context ranking use deterministic timestamps
  - Added optional `current_time` parameter to `ContextRanker.__init__()`
  - Recency boost calculation uses stored timestamp instead of live `time.time()` calls
  - Ranking order no longer drifts with wall-clock time
  - File: `src/ace/context_rank.py`

- **Security**: Hardened subprocess execution with `check=True`
  - TUI subprocess calls now use `check=True` and explicit path resolution via `shutil.which()`
  - CLI git subprocess calls now use `check=True` and specific exception handling
  - Improved error handling with `CalledProcessError` and `TimeoutExpired` exceptions
  - Files: `src/ace/tui/app.py`, `src/ace/cli.py`

- **CI**: Aligned Python version matrix with package requirements
  - CI matrix changed from `['3.10', '3.11']` to `['3.11', '3.12']`
  - Now matches `requires-python = ">=3.11"` in `pyproject.toml`
  - File: `.github/workflows/ci.yml`

- **Dev Dependencies**: Fixed invalid package pins
  - Updated `ruff==0.8.0` (non-existent) to `ruff==0.6.9` (published)
  - Added `build==1.2.2` for packaging tooling
  - File: `requirements-dev.txt`

- **Durability**: Extended atomic write guarantees to all persistence layers
  - Skiplist persistence now uses `atomic_write` (write → fsync → rename → dir fsync)
  - Content index persistence now uses `atomic_write` (previously plain `open()`)
  - Prevents corruption on power loss or crash
  - Files: `src/ace/skiplist.py`, `src/ace/index.py`

- **Maintainability**: Consolidated policy threshold constants
  - Imported `DEFAULT_ALPHA`, `DEFAULT_BETA`, `AUTO_THRESHOLD`, `SUGGEST_THRESHOLD` from `policy.py`
  - Eliminated hardcoded duplicates in `PolicyConfig` dataclass
  - Single source of truth prevents drift between modules
  - File: `src/ace/policy_config.py`

### Changed

- **Installation**: Base `pip install acha-code-health` now includes all ACE command-line tool dependencies
- **Documentation**: Updated README.md installation instructions to reflect new dependency structure

### Testing

- Verified RepoMap determinism: consecutive index builds produce identical hashes
- Confirmed PolicyConfig imports resolve correctly with shared constants
- Validated all critical module imports work without optional extras

## [ACE 2.0.0] - 2025-01-12

### Added - Planner v1

- **Deterministic action prioritization system** (`src/ace/planner.py`)
  - Multi-factor priority formula: `priority = 100*R★ + 20*cohesion - cost_rank - revert_penalty + context_boost + success_rate_bonus`
  - Replaces ad-hoc priority calculation in autopilot
  - Generates human-readable rationales for all actions
  - Integrates with Learning, Telemetry, and Context Engine
  - Fully deterministic (ties broken by plan.id)

- **Priority Components**:
  - **Base priority**: 100 * R★ (estimated risk score)
  - **Cohesion bonus**: +20 for multiple issues in same file
  - **Cost penalty**: Ranked by telemetry p95 latency
  - **Revert penalty**: -20 for contexts with high revert history
  - **Context boost**: +0-50 based on RepoMap symbol importance
  - **Success rate bonus**: +0-10 based on learning success rate

- **Rationale logging** in autopilot output:
  - Shows top 5 actions with priorities and explanations
  - Example: `R★=0.85 (base=85.0), cohesion=20, context_boost=+12.3, total=123.3`

### Added - LLM Assist

- **Optional language model assistance** (`src/ace/llm.py`)
  - Works fully offline by default (no network required)
  - Budget-limited to prevent runaway costs (max 4 calls, 100 tokens each)
  - Aggressive caching to `.ace/llm_cache.json`

- **Provider abstraction**:
  - `NullProvider`: Heuristic fallbacks (default, no network)
  - `OllamaProvider`: Local Ollama integration (optional, requires `OLLAMA_HOST` env var)
  - Auto-detection: Ollama if available, else NullProvider

- **Utilities**:
  - `docstring_one_liner()`: Generate docstrings from function signatures
  - `suggest_name()`: Suggest better variable/function names
  - `summarize_diff()`: Summarize git diffs for commit messages

- **CLI commands**:
  - `ace assist docstring <file>:<line>`: Generate docstring
  - `ace assist name <file>:<start>-<end>`: Suggest better name
  - `ace commitmsg --from-diff`: Generate commit message from staged diff

- **Budget enforcement**:
  - Max 4 LLM calls per run
  - 100 token limit per call
  - Falls back to heuristics when budget exceeded

- **Caching**:
  - Content fingerprinting with SHA256
  - Persists to `.ace/llm_cache.json`
  - Makes repeated calls instant

### Added - Local CI

- **`ace check --strict` command** for CI-like local gating
  - Analyzes code and fails (exit code 3) if any findings in strict mode
  - Non-strict mode: warnings only (exit code 0)
  - Ideal for pre-push checks or local CI validation

### Changed

- **Autopilot** now uses Planner v1 for action prioritization (lines 240-264 in `src/ace/autopilot.py`)
  - Removed inline cost-based sorting
  - Added rationale logging for top 5 actions
  - More strategic ordering based on multiple factors

- **Pre-commit installation** is now **idempotent** (`cmd_install_pre_commit`)
  - Detects existing ACE hook and skips if identical
  - Updates if ACE hook exists with different version
  - Appends to existing non-ACE hooks instead of overwriting
  - Reports status clearly: "already installed", "updated", or "appended"

### Documentation

- Added `docs/PLANNER.md`: Complete guide to Planner v1 with formula breakdown
- Added `docs/ASSIST.md`: LLM assist usage, providers, and examples

### Migration Guide v1.7 → v2.0

No breaking changes. New features are additive:

1. **Planner v1** is automatically used in `ace autopilot`
   - No config changes needed
   - Observe new rationale logging in output

2. **LLM Assist** is opt-in:
   - Works immediately with NullProvider (heuristics)
   - To use Ollama: `export OLLAMA_HOST=http://localhost:11434`

3. **`ace check --strict`** is a new command:
   - Add to CI: `ace check --strict --target .` (fails on any findings)

4. **Pre-commit** is now idempotent:
   - Run `ace install-pre-commit` multiple times safely

---

## [ACE 1.7.0] - 2025-01-12

### Added - Learning v2

- **Per-rule adaptive thresholds** with enhanced tracking (`src/ace/learn.py`)
  - `success_rate()`: Applied / (Applied + Reverted)
  - `revert_rate()`: Reverted / (Applied + Reverted)
  - `sample_size()`: Minimum 5 samples required for threshold tuning
  - Weekly decay (0.8 multiplier) for time-weighted statistics

- **Auto-skiplist patterns**:
  - Triggered after **3 consecutive reverts** for (rule, file) pair
  - Prevents ACE from repeatedly suggesting problematic fixes
  - Persisted to `learn.json` with rule-specific skiplist entries

- **Tuned thresholds**:
  - Dynamically adjusted based on rule performance
  - High revert rate (>25%): +0.05 threshold (more conservative)
  - High success rate (>80%): -0.05 threshold (more aggressive)
  - Clamped to [0.60, 0.85] range

- **CLI commands**:
  - `ace learn show`: Display learning statistics and tuned thresholds
  - `ace learn reset`: Clear all learning history

### Added - Telemetry v2

- **Enhanced JSONL logging** (`src/ace/telemetry.py`)
  - Extended metadata: `{rule_id, ms, files, ok, reverted, timestamp}`
  - P95 percentile calculation for tail latency tracking
  - Time-filtered aggregation with `--days N` option

- **Summary statistics**:
  - Mean execution time per rule
  - P95 (95th percentile) for performance regression detection
  - Execution count per rule
  - Success/failure tracking

- **CLI commands**:
  - `ace telemetry summary --days 7`: View performance summary
  - Identifies slowest rules by p95 latency

- **Integration**:
  - Automatic instrumentation in kernel (`run_analyze`, `run_apply`)
  - Used for cost-based prioritization in autopilot
  - Tracks PatchGuard revert events

### Added - Risk Heatmap

- **Per-file risk calculation** (`src/ace/report.py`)
  - Weighted formula: `risk = 0.4*revert_rate + 0.3*churn + 0.3*slow_rules`
  - Identifies high-risk files for focused review
  - Persisted to `.ace/metrics.json` with timeseries data

- **Static HTML report**:
  - `ace report health --target .` generates `health.html`
  - Inline CSS/JS (no external dependencies)
  - Risk heatmap visualization with color-coded bars
  - Findings summary and metrics dashboard

- **Risk metrics**:
  - Revert rate weight (0-0.4): Files with high PatchGuard revert history
  - Churn weight (0-0.3): Files with many issues
  - Slow rules weight (0-0.3): Files affected by slow-performing rules

### Added - TUI Dashboard

- **Interactive terminal UI** using Textual framework (`src/ace/tui/`)
  - Real-time monitoring of ACE operations
  - Multiple panels: Watch, Journal, Findings, Risk Heatmap, Status

- **Key bindings**:
  - `w`: Toggle watch mode (auto-refresh)
  - `a`: Run analysis
  - `r`: Refresh all panels
  - `h`: Open health report in browser
  - `q`: Quit

- **Panels**:
  - **WatchPanel**: Live updates when files change
  - **JournalPanel**: Recent refactoring history from `.ace/journal.jsonl`
  - **FindingsPanel**: Current issues with severity and file location
  - **RiskHeatmapPanel**: Visual risk bars for high-risk files
  - **StatusPanel**: System status and key bindings

- **CLI commands**:
  - `ace ui`: Launch TUI dashboard

### Changed

- **Autopilot** now uses Learning v2 for:
  - Auto-skiplist filtering (lines 166-171)
  - Success rate bonus in priority calculation
  - Outcome recording with file_path for skiplist

- **Kernel** now instruments telemetry in `run_apply`:
  - Records duration, files, success/failure, and revert events
  - Integrates with PatchGuard for revert tracking

### Documentation

- Added `docs/LEARNING.md`: Complete guide to Learning v2
- Added `docs/TELEMETRY.md`: Telemetry v2 usage and API
- Added `docs/TUI.md`: TUI dashboard guide with screenshots

### Dependencies

- Added `textual>=0.41.0` for TUI dashboard

### Migration Guide v1.6 → v1.7

No breaking changes. New features are additive:

1. **Learning v2** automatically loads from `.ace/learn.json`
   - Existing learning data is compatible
   - New fields added: `consecutive_reverts`, `last_updated`

2. **Telemetry v2** writes to `.ace/telemetry.jsonl`
   - Existing telemetry data is compatible
   - New fields added: `files`, `ok`, `reverted`

3. **TUI** requires `textual>=0.41.0`:
   - Run `pip install -e .` to update dependencies
   - Launch with `ace ui`

4. **Risk Heatmap** uses existing telemetry and learning data:
   - No migration needed
   - Generate report: `ace report health --target .`

---

## [ACE 1.6.0] - 2025-01-12

### Added

- **Deterministic Codemods** - Safe, idempotent code transformations using LibCST
  - **5 Built-in Codemod Packs** (`src/ace/codemods/`)
    - `PY_PATHLIB`: Modernize os.path.* to pathlib.Path
    - `PY_REQUESTS_HARDEN`: Add timeout=30 to requests calls
    - `PY_DATACLASS_SLOTS`: Add slots=True to @dataclass for memory efficiency (~40% memory savings)
    - `PY_PRINT_LOGGING`: Convert print() to logging.info()
    - `PY_DEAD_IMPORTS`: Remove unused imports (scope-aware)
  - Each codemod is idempotent (running twice yields zero diff)
  - Guards prevent unsafe transformations
  - Deterministic output (same input → same output)

- **Codemod Pack System** (`src/ace/packs_builtin.py`)
  - Pack registry with metadata (risk level, category)
  - `apply_pack_to_file()` and `apply_pack_to_directory()`
  - Integration with interactive diff UI from v1.5

- **CLI Commands** (v1.6)
  - `ace pack list` - List available codemod packs with descriptions
  - `ace pack apply <PACK_ID> [--interactive] [--dry-run] [--target]` - Apply packs
  - `ace install-pre-commit` - Install ACE pre-commit hook for git

- **PatchGuard v2** (Enhanced `src/ace/guard.py`)
  - New verification layer: symbol table counting
  - Ensures function and class counts match before/after transformation
  - Detects accidental deletions or duplications
  - 4-layer verification:
    1. Parse check (AST + LibCST)
    2. AST equivalence (semantic preservation)
    3. Symbol counts (NEW in v2)
    4. CST roundtrip (formatting preservation)
  - Automatic rollback on failure with journal integration
  - Mark reverted=true, reason="guard-v2" in journal

- **Pre-commit Hook**
  - POSIX-compatible shell script (`.git/hooks/pre-commit`)
  - Runs `ace analyze --exit-on-violation` on staged Python files
  - Blocks commits if violations found
  - Suggests running `ace autopilot` to fix
  - Installable via `ace install-pre-commit`
  - Bypass with `git commit --no-verify`

- **Interactive Apply**
  - Integration with v1.5 diffui module
  - Accept/reject changes per file with preview
  - Color-coded syntax highlighting (with rich support)
  - Dry-run mode for safe previews
  - Actions: [a]ccept, [r]eject, [v]iew full diff, [q]uit

- **Documentation**
  - `docs/CODEMODS.md` - Comprehensive codemod guide (1000+ lines)
    - Each pack documented with before/after examples
    - Guards and invariants explained in detail
    - PatchGuard v2 architecture and verification layers
    - Pre-commit hook setup and usage
    - Best practices, troubleshooting, and performance notes

### Performance

- Codemod application: 40-100 files/sec per pack
- Low memory footprint (LibCST streaming parse)
- Idempotence verification: <10ms per file
- PatchGuard v2: <50ms overhead per transform

### Guards & Invariants

**PY_PATHLIB**:
- Guards: Skip dynamic strings (f-strings), complex nested calls
- Invariants: AST structure preserved, import added if needed, simple cases only

**PY_REQUESTS_HARDEN**:
- Guards: Only add timeout if not already present
- Invariants: Timeout added, AST structure preserved

**PY_DATACLASS_SLOTS**:
- Guards: Skip multiple inheritance, skip existing __slots__
- Invariants: No structural changes, single inheritance only

**PY_PRINT_LOGGING**:
- Guards: Skip test files, skip if __name__ == "__main__" blocks
- Invariants: Import added, tests preserved, main blocks untouched

**PY_DEAD_IMPORTS**:
- Guards: Never touch __future__, keep typing.* if annotations present
- Invariants: Scope-aware removal, safe unused detection only

### Acceptance Criteria

- ✓ Running each pack twice yields zero diff (idempotence)
- ✓ `ace pack apply PY_PATHLIB --interactive` shows color diff and respects selections
- ✓ PatchGuard v2 trips on intentionally broken transform and reverts cleanly
- ✓ Pre-commit blocks commit on violations and prints concise summary
- ✓ Autopilot picks codemod packs based on repo signals (RepoMap integration)

## [ACE 1.5.0] - 2025-01-12

### Added

- **Context Engine** - Local "brainstem" for intelligent code understanding and prioritization
  - **Symbol Indexer** (`src/ace/repomap.py`)
    - Fast AST-based Python symbol extraction (stdlib only, zero deps)
    - `RepoMap.build()` - Parse *.py files, collect functions/classes/imports
    - `RepoMap.save()` - Deterministic JSON output to `.ace/symbols.json`
    - `RepoMap.query()` - Filter by pattern and/or type (function/class/module)
    - Symbol records: name, type, file, line, deps, mtime, size
    - Performance: <5s to index ACE repo (~50 files), deterministic hash

  - **Dependency Graph** (`src/ace/depgraph.py`)
    - Lightweight file-to-file dependency analysis from imports
    - `DepGraph.who_calls(symbol)` - Find files that use a symbol
    - `DepGraph.depends_on(file, depth)` - Transitive dependencies
    - `DepGraph.find_cycles()` - Circular dependency detection
    - `DepGraph.stats()` - Graph metrics (top importers/imported, avg degree)

  - **Context Ranking** (`src/ace/context_rank.py`)
    - Score files by relevance: symbol_density × recency_boost × relevance_score
    - `ContextRanker.rank_files(query, limit)` - Top N relevant files
    - `ContextRanker.get_related_files(file)` - Similar files by symbol overlap
    - `ContextRanker.get_hot_files(days)` - Recently modified files
    - Scoring: density (symbols/KLOC), recency (1.0-1.5 boost), query match

  - **Impact Analyzer** (`src/ace/impact.py`)
    - Predict affected files from changes via dependency traversal
    - `ImpactAnalyzer.predict_impacted(files, depth)` - Full impact report
    - `ImpactAnalyzer.explain_impact(file)` - Single-file impact breakdown
    - `ImpactAnalyzer.get_blast_radius(files)` - Comprehensive metrics
    - `ImpactAnalyzer.find_bottlenecks(top_n)` - Most depended-upon files
    - Risk assessment: low/medium/high/critical based on impact breadth

  - **Interactive Diff UI** (`src/ace/diffui.py`)
    - Per-file accept/reject for patch review
    - `interactive_review(changes)` - Terminal UI with rich (optional)
    - `apply_approved_changes(changes, approved)` - Safe application
    - Actions: [a]ccept, [r]eject, [v]iew full diff, [q]uit
    - Syntax highlighting and preview snippets

- **CLI Commands** (v1.5)
  - `ace index build` - Build symbol index for repository
  - `ace index query --pattern <name> --type <function|class|module>` - Query symbols
  - `ace graph who-calls <symbol>` - Find callers of a symbol
  - `ace graph depends-on <file> --depth N` - Get file dependencies
  - `ace graph stats` - Show dependency graph statistics
  - `ace context rank --query <pattern> --limit N` - Rank files by relevance
  - `ace diff <patchfile> --interactive` - Interactive patch review

- **Autopilot Integration**
  - Context engine loads automatically in `--deep` mode
  - Rebuilds index if >24h stale or missing
  - Logs "RepoMap loaded" on successful initialization
  - Enhanced priority calculation: `priority = R★ - cost - revisit + context_boost`
  - Context boost: avg(file_density + file_recency) × 5.0 (max ~5 points)
  - Prioritizes changes to recently-modified, symbol-dense files

- **Documentation**
  - `docs/CONTEXT.md` - Comprehensive context engine guide (600+ lines)
    - Architecture overview with schemas
    - CLI command reference with examples
    - Performance targets and benchmarks
    - Integration patterns (pre-commit hooks, code review)
    - Troubleshooting and FAQ

### Tests

- `tests/ace/test_repomap.py` - Symbol indexer (build, query, determinism)
- `tests/ace/test_depgraph.py` - Dependency graph (traversal, cycles, stats)
- `tests/ace/test_context_rank.py` - Context ranking (scoring, stability)
- `tests/ace/test_impact.py` - Impact analysis (depth-limited, blast radius)
- `tests/ace/test_diffui.py` - Interactive diff (auto-approve, apply)

### Performance

- Symbol index build: <5s for 50 files (ACE repo), <3s cached
- Index query: <100ms (typically ~10ms)
- Dependency graph traversal: <50ms for depth=2
- Context ranking: <200ms for 10 results
- Deterministic: `.ace/symbols.json` hash stable across runs

### Acceptance Criteria

- ✓ `ace index build` completes <5s on ACE repo
- ✓ `.ace/symbols.json` deterministic (same hash over two runs)
- ✓ `ace graph who-calls "analyze"` returns ≥1 file
- ✓ `ace graph depends-on src/ace/autopilot.py` non-empty
- ✓ `ace context rank --query path` returns 10 files max, stable order
- ✓ `ace autopilot --deep` logs "RepoMap loaded" and uses impact to order plans
- ✓ `ace diff --interactive` can accept/reject, accepted files only applied

## [ACE 0.9.0] - 2025-01-12

### Added
- **Workspace Health Map** (`src/ace/report.py`)
  - Deterministic HTML reports with inline CSS/JS (no CDN dependencies)
  - Visual heatmaps by directory, file, and rule
  - Statistics aggregation with time series support
  - Command: `ace report --out .ace/health.html`

- **Deterministic Patch Guard** (`src/ace/guard.py`)
  - Multi-layer verification for Python edits (parse, AST equivalence, CST roundtrip)
  - Auto-revert on verification failure via journal
  - Prevents syntactically invalid or semantically changed edits

### Tests
- `tests/ace/test_health_map.py` - Health map generation and determinism
- `tests/ace/test_patch_guard.py` - Guard verification and error handling

## [ACE 0.8.0] - 2025-01-12

### Added
- **Watch Mode Lite** (`src/ace/watch.py`)
  - Polling-based file change detection (no external dependencies)
  - Debouncing support for rapid file changes
  - Delta summary on each change detection
  - Command: `ace watch --target <dir> [--since 1s]`

- **Infrastructure Detection - Docker** (`src/ace/skills/docker.py`)
  - DOCK-001: Detect `:latest` tag usage (unpinned base images)
  - DOCK-002: Detect missing USER instruction (runs as root)
  - DOCK-003: Detect apt-get without -y flag or cleanup
  - Detect-only rules (no auto-fix available)

- **Infrastructure Detection - GitHub Actions** (`src/ace/skills/github_actions.py`)
  - GHA-001: Detect unpinned action uses (not pinned to SHA)
  - GHA-002: Detect `permissions: write-all` (overly permissive)
  - GHA-003: Detect missing permissions declaration
  - YAML-based workflow analysis

### Tests
- `tests/ace/test_watch_lite.py` - File watcher and change detection
- `tests/ace/test_infra_docker.py` - Docker security rules
- `tests/ace/test_infra_gha.py` - GitHub Actions security rules

## [ACE 0.7.0] - 2025-01-12

### Added
- **Macro-Fix Packs** (`src/ace/packs.py`, `src/ace/refactor.py`)
  - Group related findings into cohesive refactoring packs
  - Built-in recipes: `PY_HTTP_SAFETY`, `PY_EXCEPTION_HANDLING`, `PY_CODE_QUALITY`, `PY_STYLE`
  - Cohesion scoring: `unique_rules / recipe_rules`
  - R★ boost for packs: `R★pack = α×severity + β×complexity + γ×cohesion`
  - Overlap detection with automatic fallback to individual plans

- **Policy-as-Data v0** (`src/ace/policy_config.py`, `policy.toml`)
  - TOML-based policy configuration
  - Configurable R★ weights (α=0.7, β=0.3, γ=0.2) and decision thresholds
  - Rule modes: `auto-fix` vs `detect-only` per rule
  - Risk classes: security, reliability, maintainability, style
  - Path suppressions: global patterns + rule-specific
  - Quality gates for CI: `warn_at`, `fail_at`, `fail_on_critical`
  - Policy hash recorded in receipts for auditability

- **Learning Skiplist v0** (`src/ace/skiplist.py`)
  - Learn from user reverts to avoid repeat suggestions
  - Persistent skiplist in `.ace/skiplist.json`
  - Stable key: `SHA256(rule_id + content_hash + context_path)`
  - Auto-suppress matching findings in future runs
  - CLI option: `--skip-pack <id>` for manual suppression

- **Explain Feature** (`src/ace/explain.py`)
  - Human-friendly plan explanations with R★ calculation breakdown
  - Shows pack cohesion boost when applicable
  - Decision rationale (AUTO/SUGGEST/SKIP)
  - Command: `ace explain --plan <id>`

- **Documentation**
  - `docs/POLICY.md` - Comprehensive policy configuration guide (600+ lines)
  - `docs/PACKS.md` - Macro-fix packs guide (500+ lines)

### Changed
- Updated `src/ace/receipts.py`: Added `policy_hash` field (backward compatible)
- Updated `src/ace/policy.py`: Added `rstar_pack()` for pack cohesion boost

### Tests
- 220+ tests across 5 new test files:
  - `tests/ace/test_packs.py` - Pack finding and cohesion
  - `tests/ace/test_policy_config.py` - Policy loading and validation
  - `tests/ace/test_policy_modes_thresholds.py` - R★ scoring and decisions
  - `tests/ace/test_skiplist_learn_apply.py` - Skiplist learning and filtering
  - `tests/ace/test_explain.py` - Plan explanation formatting

## [ACHA 0.4.0] - 2025-01-07

### Added

- **Sprint 12: Modern Python Packaging & CI/CD**
  - PEP 517/518/621 compliant `pyproject.toml` for modern packaging
  - GitHub Actions CI workflow with multi-OS and multi-Python version testing
  - CodeQL security scanning integration
  - Automated release workflow with PyPI publishing
  - Release automation script (`scripts/release.py`) for version management
  - Code coverage reporting with Codecov integration
  - Comprehensive `CONTRIBUTING.md` guide for developers
  - Package installation tests and CLI entry point verification

### Changed

- Project structure now follows modern Python packaging standards
- Updated build system from legacy setup.py to pyproject.toml
- Improved CI/CD pipeline with comprehensive testing matrix

### Fixed

- **SARIF Determinism Hotfix**
  - Replaced non-deterministic `hash()` with `zlib.crc32()` for unknown rule IDs
  - SARIF output now consistent across runs, fixing GitHub Code Scanning integration
  - Added 5 regression tests for SARIF determinism

## [0.3.0] - 2025-01-07

### Added

- **Sprint 11: SARIF & HTML Reporting**
  - SARIF 2.1.0 compliant output for CI/CD integration
  - Self-contained HTML reports with inline CSS/JS
  - GitHub Code Scanning compatible SARIF format
  - Multi-format output support (JSON, SARIF, HTML, all)
  - Rule definitions for all 8 ACHA analyzers (ACHA001-ACHA008)
  - 11 comprehensive reporter tests

- **Sprint 10: Performance Optimizations**
  - AST caching with LRU eviction and file mtime validation
  - Parallel file analysis using ThreadPoolExecutor
  - Batch mode for analyzing multiple directories
  - CLI flags: `--parallel`, `--max-workers`, `--cache/--no-cache`
  - Performance benchmark tests demonstrating speedups
  - `make benchmark` and `make clean-cache` targets

### Fixed

- **Critical Bug Fixes (Post Sprint 9-10 Review)**
  - PolicyEnforcer now handles numeric severities correctly
  - Subprocess hardening uses AST manipulation to preserve syntax
  - Import organization respects `__future__` import ordering
  - Multi-import statement handling improved
  - 5 regression tests added for critical bugs

## [0.2.0] - 2025-01-06

### Added

- **Sprint 9: Safe AST-Based Refactorings**
  - AST-based safe refactorings: unused import removal, import organization, subprocess hardening
  - Import analyzer with stdlib/third-party/local classification
  - Multi-file refactoring with unified diff patches
  - Comprehensive refactoring tests

- **Sprint 8: Policy Engine & Inline Suppressions**
  - Policy-based quality gates with configurable thresholds
  - Inline suppression comments (`# acha: disable=rule`)
  - File-wide suppression support
  - CLI policy integration with exit codes

- **Sprint 7: Full Pipeline & Proof Pack Export**
  - End-to-end pipeline: analyze → refactor → validate → export
  - Proof pack ZIP creation with all artifacts
  - Session logging with JSONL format
  - Comprehensive exporter with schema validation

### Changed

- Analysis results now use numeric severity levels (0.1-0.9)
- Improved test coverage across all components
- Enhanced validation agent with checkpoint/restore

## [0.1.0] - 2025-01-05

### Added

- Initial release with core functionality
- AST-based code analysis engine
- Detection of common code issues:
  - Duplicate immutable constants
  - Risky constructs (eval, exec, __import__)
  - Unused imports
  - Magic numbers
  - Missing docstrings
  - High cyclomatic complexity
  - Broad exception handlers
  - Subprocess shell injection risks
- Basic refactoring capabilities
- Validation agent with test execution
- JSON schema validation
- CLI interface with multiple commands

### Infrastructure

- Test suite with pytest
- Sample project for testing
- JSON schemas for output validation
- Basic documentation

---

## Release Notes

### Versioning Scheme

We use Semantic Versioning (MAJOR.MINOR.PATCH):
- **MAJOR**: Incompatible API changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

### Upgrade Guide

When upgrading between versions, please review the changelog for:
- **Breaking changes** (MAJOR version bumps)
- **New features** (MINOR version bumps)
- **Bug fixes** (PATCH version bumps)

For detailed upgrade instructions, see the [Migration Guide](docs/migration.md) (coming soon).

---

[0.4.0]: https://github.com/woozyrabbit123/acha-code-health-agent/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/woozyrabbit123/acha-code-health-agent/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/woozyrabbit123/acha-code-health-agent/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/woozyrabbit123/acha-code-health-agent/releases/tag/v0.1.0
