from pathlib import Path
from acha.agents.analysis_agent import AnalysisAgent
import json, textwrap, os, shutil

def write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(s), encoding="utf-8")

def test_unused_import(tmp_path: Path):
    src = tmp_path / "m.py"
    write(src, "import os\n\ndef f():\n    return 1\n")
    agent = AnalysisAgent()
    res = agent.run(str(tmp_path))
    rules = [i["rule"] for i in res["findings"]] if "findings" in res else [i["rule"] for i in res["issues"]]
    assert "unused_import" in rules

def test_magic_number(tmp_path: Path):
    src = tmp_path / "m.py"
    write(src, "def f():\n    x=42\n    y=42\n    return x+y\n")
    agent = AnalysisAgent()
    res = agent.run(str(tmp_path))
    rules = [i["rule"] for i in res.get("issues", res.get("findings", []))]
    assert "magic_number" in rules

def test_missing_docstring(tmp_path: Path):
    src = tmp_path / "m.py"
    write(src, "def f(x):\n    return x\n")
    agent = AnalysisAgent()
    res = agent.run(str(tmp_path))
    rules = [i["rule"] for i in res.get("issues", res.get("findings", []))]
    assert "missing_docstring" in rules

def test_high_complexity(tmp_path: Path):
    src = tmp_path / "m.py"
    # Create a function with complexity > 15
    # Count: 1 base + 17 branches = 18 complexity
    write(src, """
def f(x):
    if x > 1:        # 1
        if x > 2:    # 2
            if x > 3:  # 3
                while x > 4:  # 4
                    if x % 5 == 6:  # 5
                        for i in range(x):  # 6
                            if i > 7:  # 7
                                try:   # 8
                                    if i < 8:  # 9
                                        x = x - 9
                                        if x > 10:  # 10
                                            if x < 11:  # 11
                                                pass
                                except:  # 12
                                    pass
            elif x > 12:  # 13
                pass
        elif x > 13:  # 14
            if x < 14:  # 15
                if x == 15:  # 16
                    pass
    elif x < 16:  # 17
        pass
    return x
""")
    agent = AnalysisAgent()
    res = agent.run(str(tmp_path))
    rules = [i["rule"] for i in res.get("issues", res.get("findings", []))]
    assert "high_complexity" in rules

def test_broad_exception(tmp_path: Path):
    src = tmp_path / "m.py"
    write(src, "def f():\n    try:\n        1/0\n    except Exception:\n        pass\n")
    agent = AnalysisAgent()
    res = agent.run(str(tmp_path))
    rules = [i["rule"] for i in res.get("issues", res.get("findings", []))]
    assert "broad_exception" in rules

def test_subprocess_shell(tmp_path: Path):
    src = tmp_path / "m.py"
    write(src, "import subprocess\n\ndef f():\n    subprocess.run('ls', shell=True)\n")
    agent = AnalysisAgent()
    res = agent.run(str(tmp_path))
    rules = [i["rule"] for i in res.get("issues", res.get("findings", []))]
    assert "broad_subprocess_shell" in rules

def test_inline_suppression_line(tmp_path: Path):
    src = tmp_path / "m.py"
    write(src, "def f():  # acha: disable=missing_docstring\n    return 1\n")
    agent = AnalysisAgent()
    res = agent.run(str(tmp_path))
    rules = [i["rule"] for i in res.get("issues", res.get("findings", []))]
    assert "missing_docstring" not in rules

def test_file_wide_suppression(tmp_path: Path):
    src = tmp_path / "m.py"
    write(src, "# acha: file-disable=unused_import\nimport os\n")
    agent = AnalysisAgent()
    res = agent.run(str(tmp_path))
    rules = [i["rule"] for i in res.get("issues", res.get("findings", []))]
    assert "unused_import" not in rules
