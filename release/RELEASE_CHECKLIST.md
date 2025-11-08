# ACHA Pro v1.0.0 - Release Checklist

**Version:** 1.0.0
**Date:** 2025-01-01
**Release Type:** Production (First Pro Release)

---

## Pre-Flight Checklist

Use this one-screen checklist before publishing ACHA Pro v1.0.0 to Gumroad or GitHub Releases.

---

### ✅ 1. Code Quality & Testing

- [ ] **All tests pass**: `pytest -q` returns 0 exit code
- [ ] **Coverage acceptable**: `pytest --cov` shows >80% coverage on core modules
- [ ] **No test warnings**: No deprecation warnings or unclosed resources
- [ ] **Type checking clean**: `mypy src/acha` passes (if configured)
- [ ] **Linting clean**: `ruff check src/acha tests` returns no errors
- [ ] **Formatting verified**: `black --check src/acha tests` passes

---

### ✅ 2. Determinism Verification

- [ ] **JSON stability**: Run `acha analyze` twice on same codebase, verify identical JSON output (except timestamps)
- [ ] **SARIF stability**: Run `acha analyze --output-format sarif` twice, verify identical SARIF (except UUIDs/timestamps)
- [ ] **Baseline ID stability**: Create baseline twice from same analysis.json, verify identical `baseline_id` (SHA256)
- [ ] **Parallel invariance**: Run `acha analyze --jobs 1` and `acha analyze --jobs 4`, verify identical findings (order may differ)
- [ ] **Cross-platform stability**: Run analysis on Linux + macOS/Windows, verify findings match (paths normalized)

**Verification script:**
```bash
# Run this in a test project
acha analyze --target sample_project --output-format json -o run1.json
acha analyze --target sample_project --output-format json -o run2.json
diff <(jq 'del(.metadata.timestamp)' run1.json) <(jq 'del(.metadata.timestamp)' run2.json)
# Should output nothing (files identical except timestamp)
```

---

### ✅ 3. Offline Operation (No Network Calls)

- [ ] **Disconnect network**: Disable Wi-Fi/Ethernet on test machine
- [ ] **Run analysis offline**: `acha analyze --target . --output-format json` succeeds without network
- [ ] **HTML generation offline**: `acha analyze --target . --output-format html` works (no CDN dependencies)
- [ ] **License verification offline**: Place valid `license.json`, verify Pro features work without network
- [ ] **No telemetry**: Monitor network with Wireshark/tcpdump during runs, verify ZERO outbound connections
- [ ] **No DNS lookups**: Verify no DNS queries (e.g., `strace -e trace=network` on Linux shows no connect/sendto)

**Verification commands:**
```bash
# Linux/macOS
sudo tcpdump -i any &  # Monitor all network
acha analyze --target . --output-format html
# Kill tcpdump, verify ZERO packets sent by acha process

# Windows (run as admin in PowerShell)
netsh trace start capture=yes
acha analyze --target . --output-format html
netsh trace stop
# Review .etl file, verify no network activity from acha.exe
```

---

### ✅ 4. Binary Packaging & Distribution

- [ ] **Linux binary built**: `dist/acha-linux` exists, runs `acha --version` successfully
- [ ] **macOS binary built**: `dist/acha-macos` exists, runs on macOS 10.15+
- [ ] **Windows binary built**: `dist/acha-windows.exe` exists, runs on Windows 10+
- [ ] **Binaries are standalone**: No Python installation required to run
- [ ] **PyNaCl bundled**: Binaries include PyNaCl for license verification (no `pip install` needed)
- [ ] **SHA256 checksums generated**: `checksums.txt` contains hashes for all platform binaries
- [ ] **Checksums verified**: Re-compute SHA256, match published values
- [ ] **File sizes reasonable**: Each binary <50 MB compressed

**Build commands (if using PyInstaller):**
```bash
# Linux
pyinstaller --onefile --name acha src/acha/cli.py
sha256sum dist/acha-linux >> checksums.txt

# macOS
pyinstaller --onefile --name acha src/acha/cli.py
shasum -a 256 dist/acha-macos >> checksums.txt

# Windows
pyinstaller --onefile --name acha.exe src/acha/cli.py
certutil -hashfile dist\acha-windows.exe SHA256 >> checksums.txt
```

---

### ✅ 5. Documentation Completeness

- [ ] **EULA.md present**: End-user license agreement exists and renders correctly
- [ ] **THIRD_PARTY_NOTICES.md present**: All dependencies attributed (PyNaCl, jsonschema, pytest, etc.)
- [ ] **docs/QUICKSTART_PRO.md present**: Installation and setup guide for all platforms
- [ ] **SECURITY.md present**: Security policy with threat model and vulnerability reporting
- [ ] **docs/DETERMINISM.md present**: Explains deterministic output guarantees
- [ ] **README.md updated**: Includes Community vs Pro table, privacy notes, links to new docs
- [ ] **release/RELEASE_NOTES_PRO_1.0.0.md present**: Comprehensive release notes
- [ ] **release/GUMROAD_COPY.md present**: Sales copy for Gumroad/direct sales
- [ ] **All docs render correctly**: Check Markdown formatting on GitHub preview
- [ ] **No broken links**: Verify all internal doc links resolve
- [ ] **No placeholder text**: Search for "[TO BE DETERMINED]", "[SUPPORT EMAIL]", replace with real values

---

### ✅ 6. Pro Features Validation

- [ ] **HTML reports work**: `acha analyze --output-format html` generates `reports/report.html`
- [ ] **HTML works offline**: Open `report.html` in browser with network disabled, verify full functionality
- [ ] **Baseline creation works**: `acha baseline create --analysis reports/analysis.json` succeeds
- [ ] **Baseline comparison works**: `acha baseline compare` detects NEW/EXISTING/FIXED correctly
- [ ] **Pre-commit works**: `acha precommit --target .` scans staged files, exits 1 on high severity
- [ ] **Parallel scanning works**: `acha analyze --jobs 4` uses 4 cores, produces same findings as `--jobs 1`
- [ ] **Refactor apply works**: `acha refactor --apply` creates backups, applies patches, warns on dirty tree
- [ ] **License enforcement works**: Remove license.json, verify Pro features fail with clear error message

**Pro feature test sequence:**
```bash
# 1. Remove license
rm ~/.acha/license.json

# 2. Verify Pro features blocked
acha analyze --output-format html  # Should fail with license error
acha analyze --jobs 4              # Should fail with license error
acha refactor --apply              # Should fail with license error

# 3. Place valid license
cp /path/to/license.json ~/.acha/license.json

# 4. Verify Pro features work
acha analyze --output-format html  # Should succeed
acha analyze --jobs 4              # Should succeed
acha refactor --apply --yes        # Should succeed (with backup)
```

---

### ✅ 7. License System Validation

- [ ] **Valid license works**: Place valid `license.json` in `~/.acha/`, verify Pro features unlock
- [ ] **Expired license fails**: Create expired license (past date), verify Pro features blocked
- [ ] **Invalid signature fails**: Modify license signature, verify Pro features blocked
- [ ] **Missing license fails gracefully**: Remove license, verify clear error message (not crash)
- [ ] **License search order works**: Test `~/.acha/license.json` and `./license.json` precedence
- [ ] **Ed25519 verification works**: Valid signature passes, tampered signature fails

**License test cases:**
```bash
# Test 1: Valid license
echo '{"name":"Test","email":"test@example.com","expires":"2026-01-01","signature":"..."}' > ~/.acha/license.json
acha analyze --output-format html  # Should work

# Test 2: Expired license
echo '{"name":"Test","email":"test@example.com","expires":"2020-01-01","signature":"..."}' > ~/.acha/license.json
acha analyze --output-format html  # Should fail: "License expired"

# Test 3: Invalid signature
echo '{"name":"Test","email":"test@example.com","expires":"2026-01-01","signature":"invalid"}' > ~/.acha/license.json
acha analyze --output-format html  # Should fail: "Invalid license signature"

# Test 4: Missing license
rm ~/.acha/license.json
acha analyze --output-format html  # Should fail: "Pro feature requires license"
```

---

### ✅ 8. Security & Privacy Audit

- [ ] **No hardcoded secrets**: Grep codebase for API keys, tokens, passwords
- [ ] **No telemetry**: Search for analytics, tracking, phone-home code
- [ ] **No external requests**: Search for `requests`, `urllib`, `httpx` imports (should be none)
- [ ] **License private key NOT in repo**: Verify Ed25519 private key is external (only public key in code)
- [ ] **Backups work correctly**: `acha refactor --apply` creates `backups/backup-TIMESTAMP/` before changes
- [ ] **Dirty tree warnings work**: Uncommitted changes trigger warning before refactoring

**Security grep commands:**
```bash
# Search for potential secrets
grep -r "api_key\|API_KEY\|secret\|SECRET\|token\|TOKEN" src/ --exclude="*.pyc"

# Search for network calls
grep -r "requests\.\|urllib\.\|httpx\.\|socket\.\|http\.client" src/ --exclude="*.pyc"

# Search for telemetry
grep -r "analytics\|tracking\|telemetry\|phone.home" src/ --exclude="*.pyc"

# Verify no private key in repo
git log --all --full-history --source -- "*private*" "*secret*"
```

---

### ✅ 9. CI/CD Integration

- [ ] **CodeQL workflow exists**: `.github/workflows/codeql.yml` present
- [ ] **CodeQL passes**: No security issues detected
- [ ] **Lint workflow exists**: CI runs `ruff check` and `black --check`
- [ ] **Test workflow exists**: CI runs `pytest` on all commits
- [ ] **All CI checks green**: GitHub Actions shows ✅ on latest commit

---

### ✅ 10. Release Artifacts

- [ ] **Git tag created**: `git tag -a v1.0.0-pro -m "ACHA Pro v1.0.0"`
- [ ] **Tag pushed**: `git push origin v1.0.0-pro`
- [ ] **GitHub Release created**: Release page exists with binaries attached
- [ ] **Binaries uploaded**: Linux, macOS, Windows binaries attached to release
- [ ] **Checksums published**: `checksums.txt` included in release assets
- [ ] **Release notes published**: `RELEASE_NOTES_PRO_1.0.0.md` content copied to release description
- [ ] **License template ready**: `license.json` template prepared (with placeholder signature)
- [ ] **Gumroad product created**: Product page live with copy from `GUMROAD_COPY.md`
- [ ] **Download links work**: Test all GitHub release download links
- [ ] **Email automation ready**: Gumroad/manual email system configured to send license.json

---

### ✅ 11. Final Smoke Tests

- [ ] **Fresh install test (Linux)**:
  ```bash
  wget [GITHUB_RELEASE_URL]/acha-linux.tar.gz
  tar -xzf acha-linux.tar.gz
  ./acha --version  # Should print "acha 1.0.0"
  ./acha analyze --target sample_project
  ```

- [ ] **Fresh install test (macOS)**:
  ```bash
  curl -LO [GITHUB_RELEASE_URL]/acha-macos.tar.gz
  tar -xzf acha-macos.tar.gz
  ./acha --version  # Should print "acha 1.0.0"
  ./acha analyze --target sample_project
  ```

- [ ] **Fresh install test (Windows)**:
  ```powershell
  # Download and extract acha-windows.zip
  .\acha.exe --version  # Should print "acha 1.0.0"
  .\acha.exe analyze --target sample_project
  ```

- [ ] **End-to-end workflow test**:
  ```bash
  # 1. Analyze
  acha analyze --target sample_project --output-format json

  # 2. Create baseline
  acha baseline create --analysis reports/analysis.json

  # 3. Make change to sample_project
  echo "x = 1" >> sample_project/new_file.py

  # 4. Re-analyze
  acha analyze --target sample_project --output-format json

  # 5. Compare
  acha baseline compare --analysis reports/analysis.json --baseline baseline.json
  # Should detect NEW findings

  # 6. Generate HTML
  acha analyze --target sample_project --output-format html
  # Should create report.html with NEW badges

  # 7. Pre-commit check
  git add sample_project/new_file.py
  acha precommit --target sample_project --baseline baseline.json
  # Should detect staged file issues
  ```

---

### ✅ 12. Customer-Facing Validation

- [ ] **Support email configured**: [SUPPORT_EMAIL] receives test emails
- [ ] **License delivery works**: Test purchase → automated email with license.json attachment
- [ ] **Refund process documented**: Clear steps for requesting refund within 30 days
- [ ] **FAQ accuracy verified**: All FAQ answers tested and accurate
- [ ] **System requirements verified**: Tested on minimum OS versions (Ubuntu 18.04, macOS 10.15, Windows 10 1909)
- [ ] **Quickstart guide walkthrough**: Follow QUICKSTART_PRO.md from scratch, verify all steps work

---

## Sign-Off

- [ ] **All checklist items completed**: Every box above checked
- [ ] **No known critical bugs**: Zero P0/P1 issues open
- [ ] **No open security issues**: CodeQL + manual review clean
- [ ] **Documentation complete**: All required docs present and accurate
- [ ] **Binaries tested on all platforms**: Linux, macOS, Windows smoke tests pass
- [ ] **Ready for production release**: Confident in product quality

---

**Release Manager:** ________________________
**Date Signed:** ________________________
**Version Released:** v1.0.0-pro

---

## Post-Release Tasks

After publishing to Gumroad/GitHub:

- [ ] Monitor support email for first 48 hours
- [ ] Check GitHub Issues for bug reports
- [ ] Verify download links remain accessible
- [ ] Test license delivery automation
- [ ] Collect early user feedback
- [ ] Plan v1.0.1 patch release if needed

---

**END OF CHECKLIST**
