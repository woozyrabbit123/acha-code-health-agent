# Changelog

All notable changes to the ACHA (Autonomous Code-Health Agent) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2025-01-07

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
