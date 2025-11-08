# ACHA Pro Quickstart Guide

**Version:** 1.0.0
**Last Updated:** 2025-01-01

Get up and running with ACHA Pro in under 5 minutes.

---

## Prerequisites

- **Operating System:** Linux, macOS, or Windows
- **Python:** 3.11 or 3.12 (for Python installation)
- **Git:** Recommended for baseline tracking and pre-commit integration

---

## Installation

### Option 1: Binary Installation (Recommended)

Download the pre-built binary for your platform from the [GitHub Releases](https://github.com/woozyrabbit123/acha-code-health-agent/releases) page:

**Linux:**
```bash
# Download and extract
wget https://github.com/woozyrabbit123/acha-code-health-agent/releases/download/v1.0.0-pro/ACHA-Pro-1.0.0-pro-linux.tar.gz
tar -xzf ACHA-Pro-1.0.0-pro-linux.tar.gz

# Move to PATH
sudo mv acha /usr/local/bin/
chmod +x /usr/local/bin/acha

# Verify installation
acha --version
```

**macOS:**
```bash
# Download and extract
curl -LO https://github.com/woozyrabbit123/acha-code-health-agent/releases/download/v1.0.0-pro/ACHA-Pro-1.0.0-pro-macos.tar.gz
tar -xzf ACHA-Pro-1.0.0-pro-macos.tar.gz

# Move to PATH
sudo mv acha /usr/local/bin/
chmod +x /usr/local/bin/acha

# Verify installation
acha --version
```

**Windows:**
```powershell
# Download and extract (use PowerShell or File Explorer)
# Extract ACHA-Pro-1.0.0-pro-windows.zip

# Move acha.exe to a directory in your PATH, e.g.:
# C:\Program Files\ACHA\acha.exe

# Or add the extracted directory to your PATH environment variable

# Verify installation
acha --version
```

### Option 2: Python Installation

```bash
# Install from PyPI with Pro extras
pip install acha-code-health[pro]

# Verify installation
acha --version
```

---

## License Activation

### 1. Obtain Your License

After purchasing ACHA Pro, you'll receive a `license.json` file via email. This file contains:
```json
{
  "name": "Your Name or Company",
  "email": "your@email.com",
  "expires": "2026-01-01",
  "signature": "base64-encoded-ed25519-signature"
}
```

### 2. Place License File

**Linux/macOS (User-wide installation - Recommended):**
```bash
mkdir -p ~/.acha
cp /path/to/license.json ~/.acha/license.json
chmod 600 ~/.acha/license.json  # Restrict permissions
```

**Windows (User-wide installation):**
```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.acha"
Copy-Item license.json "$env:USERPROFILE\.acha\license.json"
```

**Project-specific installation (Any OS):**
```bash
# Copy to project root (works for all platforms)
cp /path/to/license.json ./license.json

# Add to .gitignore to avoid committing
echo "license.json" >> .gitignore
```

**License file search order:**
1. `~/.acha/license.json` (user-wide)
2. `./license.json` (current directory)

### 3. Verify License

```bash
# This will fail if unlicensed (exits with code 2)
acha analyze --target . --output-format html
```

If you see:
```
⚠️  Pro Feature: HTML Report Output

This feature requires an ACHA Pro license.
```

Then your license file is not found or invalid. Check:
- File location (`~/.acha/license.json` or `./license.json`)
- File permissions (should be readable)
- File format (valid JSON)
- Expiration date (must be in the future)

---

## Basic Workflow

### Step 1: Analyze Your Code

**Generate JSON report (Community feature):**
```bash
cd /path/to/your/project
acha analyze --target . --output-format json
```

**Generate HTML report (Pro feature):**
```bash
acha analyze --target . --output-format html
```

**Parallel scanning (Pro for --jobs > 1):**
```bash
acha analyze --target . --jobs 4 --output-format html
```

**Output:**
- `reports/analysis.json` - Findings in JSON format
- `reports/analysis.sarif` - SARIF format (if requested)
- `reports/report.html` - Interactive HTML report (Pro only)

### Step 2: Create a Baseline (Pro Feature)

Capture current state to track only new issues:

```bash
# After first analysis
acha baseline create --analysis reports/analysis.json --output baseline.json

# Store baseline in version control
git add baseline.json
git commit -m "chore: add code health baseline"
```

### Step 3: Track Changes

After making code changes:

```bash
# Re-analyze
acha analyze --target . --output-format json

# Compare against baseline
acha baseline compare --analysis reports/analysis.json --baseline baseline.json
```

**Output:**
- `reports/baseline_comparison.json` - Shows NEW, EXISTING, and FIXED findings
- Exit code 1 if new findings detected
- Exit code 0 if only existing/fixed findings

**HTML Report with Baseline:**
When you generate an HTML report after running baseline compare, it will automatically show NEW/EXISTING badges on findings.

### Step 4: Pre-commit Integration (Pro Feature)

**Manual pre-commit check:**
```bash
# Before committing
acha precommit --target . --baseline baseline.json
```

**Git pre-commit hook:**

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# ACHA Pro pre-commit hook

echo "🔍 Running ACHA Pro pre-commit scan..."

acha precommit --target . --baseline baseline.json

if [ $? -ne 0 ]; then
    echo "❌ Pre-commit check failed. Fix issues or use # acha: disable=RULE to suppress."
    exit 1
fi

echo "✅ Pre-commit check passed!"
exit 0
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

**What it does:**
- Scans only staged Python files
- Compares against baseline (if provided)
- Exits 1 on NEW HIGH severities (error/critical)
- Respects inline suppressions (`# acha: disable=RULE`)

### Step 5: Refactoring with Safety Rails (Pro Feature)

**Plan refactoring (Community feature):**
```bash
acha refactor --target . --analysis reports/analysis.json --fix
```

**Apply refactoring (Pro feature):**
```bash
# With confirmation prompt
acha refactor --target . --analysis reports/analysis.json --apply

# Skip confirmation (careful!)
acha refactor --target . --analysis reports/analysis.json --apply --yes
```

**Safety features:**
- Dirty tree warning (uncommitted changes)
- Automatic backup creation (`backups/backup-TIMESTAMP/`)
- Confirmation prompt (unless --yes)
- Generates `dist/patch.diff` before applying

---

## Common Workflows

### Workflow 1: Daily Development

```bash
# 1. Start work
cd ~/projects/myapp

# 2. Make changes
# ... edit code ...

# 3. Check code health before commit
acha analyze --target . --output-format json
acha baseline compare --analysis reports/analysis.json --baseline baseline.json

# 4. Review new findings
cat reports/baseline_comparison.json | jq '.summary'

# 5. Fix issues or suppress false positives
# Add: # acha: disable=RULE_NAME

# 6. Commit
git add .
git commit -m "feat: implement new feature"
```

### Workflow 2: CI/CD Integration

```yaml
# .github/workflows/code-health.yml
name: Code Health

on: [pull_request]

jobs:
  acha:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Download ACHA Pro
        run: |
          wget https://github.com/.../ACHA-Pro-1.0.0-pro-linux.tar.gz
          tar -xzf ACHA-Pro-*.tar.gz
          chmod +x acha

      - name: Place license (from secret)
        run: |
          mkdir -p ~/.acha
          echo "${{ secrets.ACHA_PRO_LICENSE }}" > ~/.acha/license.json

      - name: Run analysis
        run: |
          ./acha analyze --target . --output-format sarif
          ./acha baseline compare --analysis reports/analysis.json --baseline baseline.json

      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: reports/analysis.sarif
```

### Workflow 3: Bulk Refactoring

```bash
# 1. Analyze
acha analyze --target . --output-format json

# 2. Plan refactoring
acha refactor --target . --analysis reports/analysis.json --fix

# 3. Review diff
cat dist/patch.diff

# 4. Apply if satisfied (Pro)
acha refactor --target . --analysis reports/analysis.json --apply

# 5. Run tests
pytest

# 6. If tests fail, restore from backup
cp -r backups/backup-20250101-120000/* .

# 7. If tests pass, commit
git add .
git commit -m "refactor: apply ACHA auto-fixes"
```

---

## Platform-Specific Notes

### Linux

**Installation paths:**
- Binary: `/usr/local/bin/acha`
- License: `~/.acha/license.json`
- Cache: `~/.acha_cache/`

**Permissions:**
```bash
# License file should be user-readable only
chmod 600 ~/.acha/license.json

# Binary should be executable
chmod +x /usr/local/bin/acha
```

### macOS

**Installation paths:**
- Binary: `/usr/local/bin/acha`
- License: `~/.acha/license.json`
- Cache: `~/.acha_cache/`

**Gatekeeper:**
If you get "unidentified developer" warning:
```bash
xattr -d com.apple.quarantine /usr/local/bin/acha
```

Or: System Preferences → Security & Privacy → "Allow anyway"

### Windows

**Installation paths:**
- Binary: `C:\Program Files\ACHA\acha.exe` (or any directory in PATH)
- License: `C:\Users\<YourName>\.acha\license.json`
- Cache: `C:\Users\<YourName>\.acha_cache\`

**PowerShell execution:**
```powershell
# Add to PATH permanently
$env:Path += ";C:\Program Files\ACHA"
[Environment]::SetEnvironmentVariable("Path", $env:Path, [System.EnvironmentVariableTarget]::User)

# Verify
acha --version
```

**Git Bash:**
Works the same as Linux:
```bash
./acha.exe analyze --target . --output-format json
```

---

## Troubleshooting

### "Pro Feature: ..." Error

**Cause:** License file not found or invalid.

**Solution:**
1. Check file exists: `ls ~/.acha/license.json` (Linux/macOS) or `dir %USERPROFILE%\.acha\license.json` (Windows)
2. Verify JSON format: `cat ~/.acha/license.json | python -m json.tool`
3. Check expiration: License `expires` field must be in the future
4. Try placing in current directory: `cp ~/.acha/license.json ./license.json`

### "PyNaCl not installed"

**Cause:** Pro license verification requires PyNaCl, but it's not installed (Python installation only).

**Solution:**
```bash
pip install PyNaCl
# Or install Pro extras
pip install acha-code-health[pro]
```

Binary distributions include PyNaCl, so this should not occur.

### "Failed to create backup"

**Cause:** Insufficient disk space or permissions.

**Solution:**
1. Check disk space: `df -h` (Linux/macOS) or `Get-PSDrive` (Windows)
2. Ensure write permissions in current directory
3. Clean old backups: `rm -rf backups/backup-*` (after verifying current code is safe)

### Slow Analysis on Large Codebases

**Solution:**
```bash
# Use parallel scanning (Pro)
acha analyze --target . --jobs 8 --output-format json

# Disable cache if stale
acha analyze --target . --no-cache --output-format json

# Exclude directories
# (Create .acha-ignore file - not yet implemented, use git-style excludes)
```

---

## Next Steps

- **Read:** [SECURITY.md](../SECURITY.md) - Understand local-first security model
- **Read:** [DETERMINISM.md](./DETERMINISM.md) - Learn about deterministic analysis
- **Explore:** HTML Reports - Open `reports/report.html` in a browser
- **Integrate:** Set up pre-commit hooks for your team
- **Automate:** Add ACHA Pro to your CI/CD pipeline

---

## Support

- **Documentation:** https://github.com/woozyrabbit123/acha-code-health-agent
- **Issues:** https://github.com/woozyrabbit123/acha-code-health-agent/issues
- **Email:** [SUPPORT EMAIL TO BE SPECIFIED]

---

**Happy analyzing! 🚀**
