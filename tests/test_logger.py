import json
from pathlib import Path
from utils.logger import JSONLLogger

def test_jsonl_append(tmp_path: Path):
    p = tmp_path / "test.jsonl"
    log = JSONLLogger(p)
    log.log("test", {"k": "v"})
    with p.open("r", encoding="utf-8") as f:
        item = json.loads(f.readline())
    assert item["event"] == "test"
    assert item["k"] == "v"
    assert "timestamp" in item

def test_rotation(tmp_path: Path):
    p = tmp_path / "rot.jsonl"
    log = JSONLLogger(p, max_size_mb=0.00001)
    log.log("x", {"data": "y" * 2000})
    log._rotate_if_needed()
    rotated = list(tmp_path.glob("rot.*.jsonl"))
    assert len(rotated) >= 1
