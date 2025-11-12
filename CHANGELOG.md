# Changelog

All notable changes to the ACHA/ACE (Autonomous Code-Health Agent / Autonomous Code Editor) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
