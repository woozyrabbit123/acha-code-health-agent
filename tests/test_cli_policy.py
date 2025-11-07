import subprocess, sys
from pathlib import Path

def run_cmd(args, cwd: Path):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)

def test_run_fails_under_strict(tmp_path):
    # run against sample_project to trigger risky detection
    cmd = [sys.executable, "-m", "acha.cli", "--policy", "strict-policy.json", "--session-log", "reports/session.jsonl", "run", "--target", "./sample_project"]
    res = run_cmd(cmd, Path.cwd())
    assert res.returncode != 0, res.stdout + res.stderr

def test_run_passes_under_dev(tmp_path):
    cmd = [sys.executable, "-m", "acha.cli", "--policy", "dev-policy.json", "--session-log", "reports/session.jsonl", "run", "--target", "./sample_project"]
    res = run_cmd(cmd, Path.cwd())
    assert res.returncode == 0, res.stdout + res.stderr
