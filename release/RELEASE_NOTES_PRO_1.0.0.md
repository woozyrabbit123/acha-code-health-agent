# ACHA Pro v1.0.0 Release Notes

**Release Date:** 2025-01-01
**License:** Commercial (Single-Seat)
**Support:** Email support included

---

## 🎉 What's New in v1.0.0

ACHA Pro v1.0.0 is the first production-ready release of the Autonomous Code-Health Agent with Pro features. This release includes offline licensing, advanced reporting, baseline tracking, and safety rails for automated refactoring.

---

## ✨ Pro Features

### 🔐 Offline Ed25519 License Verification
- **100% offline** - No network calls, no telemetry, no "phone home"
- **Ed25519 signatures** - Cryptographically secure license validation via PyNaCl
- **Single-seat licensing** - Use on multiple machines owned by one individual
- **License locations:** `~/.acha/license.json` or `./license.json`

### 📊 Self-Contained HTML Reports
- **Offline-first design** - No CDN dependencies, all CSS/JS embedded
- **Baseline delta display** - NEW/EXISTING/FIXED status badges on findings
- **Suppressed findings** - Purple badges show deliberately ignored issues
- **Multi-dimensional filtering** - Severity, rule type, status, text search
- **Interactive features** - Sortable tables, responsive design, dark mode
- **Generated with:** `acha analyze --target . --output-format html`

### 📈 Baseline Tracking & Comparison
- **Create baselines** - Capture current state with `acha baseline create`
- **Compare changes** - Detect NEW/EXISTING/FIXED findings with `acha baseline compare`
- **Deterministic IDs** - SHA256-based finding IDs for stable tracking
- **Version control friendly** - Commit baselines to git for team-wide use
- **CI/CD integration** - Exit code 1 on new findings for pipeline gating

### 🔍 Pre-commit Hook Integration
- **Scans staged files only** - Fast, focused analysis before commit
- **Blocks on HIGH severities** - Prevents committing critical/error findings
- **Respects suppressions** - `# acha: disable=RULE` inline comments honored
- **Baseline comparison** - Compare against baseline to catch regressions
- **Command:** `acha precommit --target . --baseline baseline.json`

### ⚡ Parallel Scanning
- **Multi-core analysis** - Use all CPU cores with `--jobs N`
- **Deterministic output** - `--jobs 1` and `--jobs 4` produce identical results
- **Pro-gated for > 1** - Community edition supports single-threaded only
- **Auto-scaling** - Caps at `cpu_count()` to prevent overload

### 🛡️ Safety Rails for Refactoring
- **Plan-only mode (--fix)** - Default behavior, generates diff without writes
- **Apply mode (--apply)** - Pro-gated, applies changes with safety checks
- **Pre-flight checks:**
  - Dirty tree warning (uncommitted changes)
  - Automatic backup creation (`backups/backup-TIMESTAMP/`)
  - User confirmation prompt (unless `--yes`)
  - Patch generation (`dist/patch.diff`)
- **Restore mechanism** - Easy rollback from timestamped backups

---

## 🌟 Community Features (Free)

All Community edition features remain 100% free and functional:

- ✅ AST-based code analysis (unused imports, magic numbers, complexity, etc.)
- ✅ JSON and SARIF report generation
- ✅ Automated refactoring (--fix planning mode)
- ✅ Inline suppression (`# acha: disable=RULE`)
- ✅ Policy enforcement with quality gates
- ✅ Test validation workflow
- ✅ Deterministic outputs for reproducible builds
- ✅ Single-threaded parallel analysis (--jobs 1)
- ✅ Open-source codebase (MIT License for non-Pro components)

---

## 📦 Installation Options

### Binary Installation (Recommended)

**Linux:**
```bash
wget https://github.com/woozyrabbit123/acha-code-health-agent/releases/download/v1.0.0-pro/ACHA-Pro-1.0.0-pro-linux.tar.gz
tar -xzf ACHA-Pro-1.0.0-pro-linux.tar.gz
sudo mv acha /usr/local/bin/
acha --version
```

**macOS:**
```bash
curl -LO https://github.com/woozyrabbit123/acha-code-health-agent/releases/download/v1.0.0-pro/ACHA-Pro-1.0.0-pro-macos.tar.gz
tar -xzf ACHA-Pro-1.0.0-pro-macos.tar.gz
sudo mv acha /usr/local/bin/
acha --version
```

**Windows:**
```powershell
# Download ACHA-Pro-1.0.0-pro-windows.zip from releases
# Extract and move acha.exe to a directory in your PATH
acha --version
```

### Python Installation

```bash
pip install acha-code-health[pro]
acha --version
```

---

## 🔒 Checksums (Verify Integrity)

**SHA256 checksums for v1.0.0-pro binaries:**

```
[CHECKSUMS TO BE GENERATED ON RELEASE]

# Verification:
sha256sum -c SHA256SUMS.txt  # Linux/macOS
CertUtil -hashfile ACHA-Pro-*.zip SHA256  # Windows
```

**PGP signatures (optional):**
```
[PGP SIGNATURES TO BE GENERATED ON RELEASE]

# Verification:
gpg --verify ACHA-Pro-1.0.0-pro-linux.tar.gz.asc
```

---

## 🚀 Quick Start

### 1. Install ACHA Pro
See installation options above.

### 2. Activate License
```bash
# Place license.json (provided after purchase)
mkdir -p ~/.acha
cp /path/to/license.json ~/.acha/license.json
chmod 600 ~/.acha/license.json
```

### 3. Analyze Code
```bash
cd /path/to/your/project
acha analyze --target . --output-format html
open reports/report.html  # View interactive report
```

### 4. Create Baseline
```bash
acha baseline create --analysis reports/analysis.json --output baseline.json
git add baseline.json
git commit -m "chore: add code health baseline"
```

### 5. Pre-commit Integration
```bash
# Add to .git/hooks/pre-commit
acha precommit --target . --baseline baseline.json
```

See [docs/QUICKSTART_PRO.md](../docs/QUICKSTART_PRO.md) for detailed guide.

---

## 📚 Documentation

- **Quickstart Guide:** [docs/QUICKSTART_PRO.md](../docs/QUICKSTART_PRO.md)
- **Security Policy:** [SECURITY.md](../SECURITY.md)
- **EULA:** [EULA.md](../EULA.md)
- **Determinism:** [docs/DETERMINISM.md](../docs/DETERMINISM.md)
- **Third-Party Notices:** [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)

---

## 🔧 System Requirements

**Operating Systems:**
- Linux: Ubuntu 18.04+, Debian 10+, Fedora 32+, or equivalent
- macOS: 10.15 (Catalina) or later
- Windows: Windows 10 (1909) or later, Windows Server 2019+

**Python (for pip installation):**
- Python 3.11 or 3.12
- pip 21.0+

**Disk Space:**
- Binary: ~50 MB compressed, ~150 MB installed
- Python: Varies (depends on existing Python environment)

**Memory:**
- Minimum: 512 MB RAM
- Recommended: 2 GB RAM for large codebases with parallel analysis

**Dependencies (included in binary):**
- PyNaCl 1.5.0+ (Ed25519 signatures)
- jsonschema 4.0.0+ (Schema validation)

---

## 🆕 Breaking Changes from v0.4.x

### License Requirement for Pro Features
- HTML output now requires Pro license (`--output-format html`)
- Parallel jobs > 1 require Pro license (`--jobs > 1`)
- Refactoring apply requires Pro license (`--apply`)
- Baseline commands require Pro license
- Pre-commit command requires Pro license

### Community Edition Still Fully Functional
- All v0.4.x features work without license
- JSON/SARIF output remains free
- Refactoring planning (--fix) remains free
- Single-threaded analysis remains free

### CLI Changes
- `--version` flag added (prints "acha 1.0.0")
- `--jobs` flag replaces `--max-workers` for parallel control
- `--apply` flag requires explicit opt-in for refactoring
- Pro features clearly marked in `--help` output

---

## 🐛 Known Issues

### macOS Gatekeeper Warning
**Issue:** "Cannot verify developer" warning on first run.

**Workaround:**
```bash
xattr -d com.apple.quarantine /usr/local/bin/acha
```

Or: System Preferences → Security & Privacy → "Allow anyway"

### Windows Antivirus False Positives
**Issue:** Some antivirus software flags PyInstaller binaries.

**Workaround:**
- Verify SHA256 checksum matches release
- Add ACHA to antivirus exclusions
- Use Python installation instead

---

## 📞 Support & Contact

**For license activation or technical issues:**
- **Email:** [SUPPORT EMAIL TO BE SPECIFIED]
- **Response time:** Within 48 hours (business days)

**For bug reports or feature requests:**
- **GitHub Issues:** https://github.com/woozyrabbit123/acha-code-health-agent/issues

**For security vulnerabilities:**
- **Security Email:** [SECURITY EMAIL TO BE SPECIFIED]
- **Do NOT open public issues for security bugs**

---

## 🎁 What's Included

**With your ACHA Pro purchase:**
- ✅ Single-seat license (use on multiple machines)
- ✅ All Pro features listed above
- ✅ Email support for 1 year
- ✅ Minor updates (v1.0.x, v1.1.x, etc.) free
- ✅ Security patches for lifetime of v1.x
- ✅ 30-day money-back guarantee

**Future major versions (v2.0.0+) may require separate purchase.**

---

## 🔮 Roadmap (Future Releases)

**Planned for v1.1.0:**
- Custom rule creation (Python DSL)
- Team license support (5/10/unlimited seats)
- CI/CD dashboard (HTML report aggregation)
- IDE integrations (VS Code, PyCharm)

**Under consideration:**
- GitHub App for automated PR comments
- Slack/Teams notifications
- Custom report templates
- Multi-language support (JavaScript, TypeScript)

**Vote on features:**
https://github.com/woozyrabbit123/acha-code-health-agent/discussions

---

## 🙏 Acknowledgments

ACHA Pro is built on top of excellent open-source projects:
- **PyNaCl** - Ed25519 cryptographic signatures
- **jsonschema** - JSON Schema validation
- **pytest** - Testing framework
- **ruff** - Fast Python linter
- **black** - Python code formatter

See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) for full attributions.

---

## 📜 License

- **Community features:** MIT License (open source)
- **Pro features:** Commercial EULA (see [EULA.md](../EULA.md))
- **Binaries:** Include both; Pro features gated by license file

---

**Thank you for choosing ACHA Pro! 🚀**

Questions? Email [SUPPORT EMAIL TO BE SPECIFIED]

Last Updated: 2025-01-01
Version: 1.0.0
