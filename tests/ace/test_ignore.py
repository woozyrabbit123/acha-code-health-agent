"""Tests for ACE ignore system."""

from pathlib import Path
import tempfile

from ace.ignore import IgnoreSpec, load_aceignore


def test_ignore_spec_glob_patterns():
    """Test glob pattern matching."""
    spec = IgnoreSpec(["*.pyc", "__pycache__/**"])

    assert spec.match(Path("test.pyc")) is True
    assert spec.match(Path("test.py")) is False
    assert spec.match(Path("__pycache__/foo.py")) is True
    assert spec.match(Path("src/__pycache__/bar.py")) is True


def test_ignore_spec_regex_patterns():
    """Test regex pattern matching."""
    spec = IgnoreSpec(["re:^.*_test\\.py$"])

    assert spec.match(Path("foo_test.py")) is True
    assert spec.match(Path("bar_test.py")) is True
    assert spec.match(Path("test_foo.py")) is False


def test_load_aceignore():
    """Test loading .aceignore file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        aceignore = root / ".aceignore"

        # Test with no file
        spec = load_aceignore(root)
        assert spec is None

        # Test with file
        aceignore.write_text("*.pyc\n# Comment\n\n__pycache__/**\n", encoding="utf-8")
        spec = load_aceignore(root)

        assert spec is not None
        assert spec.match(Path("test.pyc")) is True
        assert spec.match(Path("test.py")) is False


def test_ignore_deterministic_order():
    """Test that pattern evaluation is deterministic."""
    patterns1 = ["*.pyc", "*.pyo", "*.so"]
    patterns2 = ["*.so", "*.pyc", "*.pyo"]

    spec1 = IgnoreSpec(patterns1)
    spec2 = IgnoreSpec(patterns2)

    # Patterns should be sorted internally for determinism
    assert spec1.patterns == spec2.patterns
