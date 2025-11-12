# Changelog

All notable changes to the ACHA/ACE (Autonomous Code-Health Agent / Autonomous Code Editor) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
