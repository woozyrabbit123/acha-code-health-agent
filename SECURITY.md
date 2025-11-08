# Security Policy

**ACHA Pro v1.0.0**
Last Updated: 2025-01-01

---

## Security Model: Local-First, Offline, Zero-Telemetry

ACHA Pro is designed with a **local-first security model**:

### ✅ **What ACHA Pro DOES:**
- Runs entirely on your local machine
- Analyzes code using AST (Abstract Syntax Tree) parsing
- Validates licenses using offline Ed25519 cryptographic signatures
- Stores all results locally in `reports/` directory
- Creates backups in `backups/` directory before refactoring
- Checks git tree status before applying changes

### ❌ **What ACHA Pro DOES NOT DO:**
- **No network connections** - Zero external communication
- **No telemetry** - Does not send usage statistics
- **No crash reporting** - No error logs sent externally
- **No "phone home"** - License validation is 100% offline
- **No cloud storage** - All data stays on your machine
- **No third-party services** - No API calls to external services

---

## Threat Model

### Out of Scope Threats

ACHA Pro operates in a **trusted execution environment**. The following threats are explicitly out of scope:

1. **Compromised local machine** - If your system is compromised, ACHA Pro cannot protect you
2. **Malicious Python interpreter** - We assume Python itself is not compromised
3. **Compromised dependencies** - PyPI supply chain attacks are mitigated by pinned versions
4. **Physical access** - Attackers with physical access to your machine
5. **Social engineering** - Phishing attacks to obtain your license file

### In-Scope Threats

ACHA Pro mitigates:

1. **Accidental data loss** - Automatic backups before refactoring
2. **Dirty tree overwrites** - Git status check warns before applying changes
3. **License sharing** - Single-seat Ed25519 signatures prevent unauthorized distribution
4. **Code execution** - AST parsing (not eval/exec) prevents arbitrary code execution
5. **Determinism violations** - Stable output ordering prevents non-deterministic behavior

---

## License File Security

### Storage & Permissions

**Recommended location (user-wide):**
```bash
# Linux/macOS
~/.acha/license.json
Permissions: 600 (read/write for owner only)

# Windows
%USERPROFILE%\.acha\license.json
Permissions: Inherit from user profile (ACL restricted)
```

**Alternative location (project-specific):**
```bash
./license.json
⚠️ Add to .gitignore to avoid committing to version control!
```

**Best practices:**
```bash
# Linux/macOS - Restrict permissions
chmod 600 ~/.acha/license.json

# Verify permissions
ls -l ~/.acha/license.json
# Should show: -rw-------
```

### License File Contents

Your `license.json` contains:
```json
{
  "name": "Your Name or Company",
  "email": "your@email.com",
  "expires": "2026-01-01",
  "signature": "base64-encoded-ed25519-signature"
}
```

**What's NOT in the license file:**
- No payment information
- No personally identifying information beyond name/email
- No device fingerprints
- No usage tracking data
- No telemetry identifiers

**License verification:**
- Ed25519 signature verification (cryptographically secure)
- Expiration date validation (client-side only)
- No network check or "activation servers"
- No device binding (use on multiple machines)

### License File Theft Mitigation

**Single-seat enforcement:**
- License is tied to a specific name/email
- Unauthorized redistribution violates EULA
- Ed25519 signature prevents forgery
- Vendor can revoke leaked licenses in future updates

**If your license is compromised:**
1. Contact support immediately: [SUPPORT EMAIL TO BE SPECIFIED]
2. Request license revocation and reissue
3. Rotate git commits if license was committed to public repo
4. Update `.gitignore` to prevent future commits

---

## Code Analysis Security

### AST-Only Analysis (Safe)

ACHA Pro uses Python's built-in `ast` module to parse code:
```python
tree = ast.parse(source_code, filename="file.py")
```

**Security guarantees:**
- ✅ **Never executes user code** - AST parsing is static analysis
- ✅ **No `eval()` or `exec()`** - No dynamic code execution
- ✅ **Sandboxed parsing** - SyntaxError on malicious code
- ✅ **Read-only by default** - Analysis phase never writes files

**Contrast with unsafe analysis:**
- ❌ `exec(open("file.py").read())` - Would execute arbitrary code
- ❌ `import user_module` - Would run module-level code
- ❌ `pickle.load()` - Would deserialize arbitrary objects

### Input Validation

**File types:**
- Only `.py` files are analyzed
- Binary files are skipped
- Non-UTF-8 files are gracefully skipped

**Path traversal prevention:**
```python
# Safe: Uses pathlib.Path.resolve()
target_path = Path(user_input).resolve()

# Prevents: ../../etc/passwd attacks
```

**Command injection prevention:**
- All subprocess calls use `list` form (not shell=True by default)
- User input is never interpolated into shell commands
- Git commands use `--porcelain` for machine-readable output

---

## Refactoring Safety

### Safety Rails (Pro Feature)

**Before applying refactorings (`--apply`):**

1. **Dirty tree check:**
   ```bash
   git status --porcelain
   # Warns if uncommitted changes exist
   ```

2. **Automatic backup:**
   ```bash
   backups/backup-YYYYMMDD-HHMMSS/
   # Full copy of target directory before changes
   ```

3. **User confirmation:**
   ```
   Apply these changes? [y/N]:
   # Requires explicit 'y' unless --yes flag used
   ```

4. **Patch generation:**
   ```bash
   dist/patch.diff
   # Always generated before applying (for review)
   ```

### Backup Behavior

**Backup location:**
```
backups/backup-YYYYMMDD-HHMMSS/
├── all files from target directory (recursive copy)
└── symlinks preserved
```

**Backup retention:**
- Backups are NOT automatically deleted
- Manual cleanup required (`rm -rf backups/backup-*`)
- Consider adding `backups/` to `.gitignore`

**Restore from backup:**
```bash
# If refactoring went wrong
cp -r backups/backup-20250101-120000/* .
# Or on Windows
robocopy backups\backup-20250101-120000 . /E
```

### Write Operation Scope

**Files modified by `--apply`:**
- Only files listed in `patch_summary.json` → `files_touched`
- Only Python `.py` files (never `.pyc`, `.pyo`, etc.)
- Only within specified `--target` directory

**Files NEVER modified:**
- Files outside target directory
- Binary files
- Hidden files (`.git/`, `.env`, etc.)
- Configuration files (`pyproject.toml`, `setup.py`, etc.)

---

## Deterministic Outputs

See [docs/DETERMINISM.md](docs/DETERMINISM.md) for full details.

**Security relevance:**
- Reproducible analyses prevent supply chain attacks
- Stable hashes enable integrity verification
- Deterministic refactorings are easier to review in diffs

**Guarantees:**
- Same code + same ACHA version = identical JSON output
- `--jobs 1` vs `--jobs 4` produce identical results (stable sort)
- No timestamps, UUIDs, or random values in core outputs

---

## Dependency Security

### Runtime Dependencies

**Required (Community):**
- `jsonschema` (v4.0.0+) - MIT License
  - Only used for schema validation
  - No network dependencies
  - Well-audited library

**Optional (Pro):**
- `PyNaCl` (v1.5.0+) - Apache 2.0 License
  - Only used for Ed25519 signature verification
  - No network dependencies
  - Cryptographically audited (libsodium wrapper)

### Build & Development Dependencies

**Not included in binaries:**
- `pytest`, `pytest-timeout`, `pytest-cov` - Testing only
- `black`, `ruff`, `mypy` - Linting/formatting only
- `PyInstaller` - Build-time only

**Binary distributions:**
- Statically bundled (all dependencies included)
- No separate pip installation required
- Reduced supply chain attack surface

### Dependency Pinning

`pyproject.toml` uses minimum version specifiers:
```toml
dependencies = [
    "jsonschema>=4.0.0",
]
```

**For production use, pin exact versions:**
```bash
pip install acha-code-health==1.0.0
pip freeze > requirements.txt
```

---

## Pre-commit Hook Security

### Scope Limitation

`acha precommit` scans **only staged files**:
```bash
git diff --cached --name-only --diff-filter=ACM
```

**What this means:**
- Unstaged changes are NOT scanned
- Untracked files are NOT scanned
- Only files you're about to commit are analyzed

**Why this matters:**
- Prevents false positives from work-in-progress code
- Focuses on what's actually being committed
- Faster execution (fewer files)

### Exit Code Behavior

```bash
acha precommit --target . --baseline baseline.json
echo $?  # Exit code
```

**Exit codes:**
- `0` - No new HIGH severities (safe to commit)
- `1` - New HIGH severities detected (commit blocked)
- `2` - License error (Pro feature without license)

**Severity threshold:**
- `critical` (severity >= 0.9) → Blocks commit
- `error` (severity >= 0.7) → Blocks commit
- `warning` (severity >= 0.4) → Allows commit
- `info` (severity < 0.4) → Allows commit

### Bypass Mechanisms

**Inline suppression (recommended):**
```python
# acha: disable=unused_import
import rarely_used_module

# acha: disable-all
legacy_code_that_fails_checks()
```

**Git commit bypass (emergency only):**
```bash
git commit --no-verify -m "emergency fix"
```

⚠️ Only use `--no-verify` in emergencies. Fix issues or suppress properly instead.

---

## Reporting Security Vulnerabilities

### Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | ✅ Active support  |
| 0.4.x   | ⚠️ Security fixes only |
| < 0.4   | ❌ No longer supported |

### How to Report

**For security vulnerabilities, please DO NOT open a public GitHub issue.**

**Instead, report privately:**
1. **Email:** [SECURITY@EXAMPLE.COM TO BE SPECIFIED]
2. **Subject:** `[SECURITY] Brief description`
3. **Include:**
   - Vulnerability description
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

**PGP encryption (optional):**
- Public key: [PGP KEY ID TO BE SPECIFIED]
- Fingerprint: [FINGERPRINT TO BE SPECIFIED]

### Response Timeline

- **Initial response:** Within 48 hours
- **Triage:** Within 1 week
- **Patch development:** Varies by severity
- **Public disclosure:** After patch release (or 90 days, whichever is sooner)

**Severity levels:**
- **Critical:** Remote code execution, credential theft → Immediate patch
- **High:** Local privilege escalation, data exfiltration → 1 week
- **Medium:** Denial of service, minor data exposure → 2 weeks
- **Low:** Information disclosure, cosmetic issues → Next release

### Security Advisories

Published at:
- https://github.com/woozyrabbit123/acha-code-health-agent/security/advisories

---

## Audit Trail

### What ACHA Pro Logs

**Session logs (optional):**
```
reports/session.jsonl
```

**Contents:**
- CLI commands executed
- Analysis start/end times
- Findings counts
- Policy violations

**NOT logged:**
- Your source code
- File contents
- Sensitive data
- License file contents

**Local storage only:**
- Session logs are written to local disk
- Never transmitted externally
- Can be disabled with `--session-log /dev/null` (Unix) or `NUL` (Windows)

---

## Compliance Notes

### GDPR (EU)

**No personal data processing:**
- ACHA Pro does not collect personal data
- No data controllers or processors involved
- License file (name/email) stored locally only
- No data transfers outside your machine

**Right to be forgotten:**
- Delete `~/.acha/` directory
- Delete `license.json` file
- No server-side data to request deletion

### SOC 2 / ISO 27001

**Relevant for organizations using ACHA Pro:**
- Local-only processing supports data residency requirements
- No vendor access to your code
- No shared infrastructure
- Audit logs available in `reports/session.jsonl`

### Offline Environments

**ACHA Pro works completely offline:**
- Air-gapped networks: ✅ Supported
- No internet requirement: ✅ Confirmed
- License validation: ✅ Offline Ed25519 signatures
- Binary distribution: ✅ No external dependencies

---

## Best Practices Summary

1. **License Security:**
   - Store in `~/.acha/license.json` with `chmod 600`
   - Never commit to version control
   - Rotate immediately if leaked

2. **Version Control:**
   - Always use git for code being refactored
   - Review `dist/patch.diff` before applying
   - Commit before running `--apply`

3. **Backup Strategy:**
   - ACHA's automatic backups are safety nets, not primary backups
   - Maintain independent git backups
   - Test restore process before production use

4. **Access Control:**
   - Restrict ACHA Pro binary to authorized users
   - Use single-user accounts (don't share license files)
   - Rotate licenses annually

5. **Incident Response:**
   - If refactoring fails: Restore from `backups/backup-*/`
   - If license compromised: Contact support immediately
   - If security issue found: Report privately to security team

---

**Questions or concerns? Contact us:**
- **Email:** [SECURITY@EXAMPLE.COM TO BE SPECIFIED]
- **GitHub:** https://github.com/woozyrabbit123/acha-code-health-agent/security

---

Last Updated: 2025-01-01
ACHA Pro Version: 1.0.0
