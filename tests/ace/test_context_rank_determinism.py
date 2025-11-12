"""Tests for deterministic context ranking."""
from unittest.mock import Mock, MagicMock
from ace.context_rank import ContextRanker


def test_rank_files_is_stable_order():
    """Test that rank_files returns stable, deterministic order."""
    # Create mock repo_map with test data
    mock_repo_map = Mock()
    mock_repo_map.get_files.return_value = ["a.py", "b.py", "c.py"]

    # Mock symbols for each file
    def get_file_symbols(file):
        if file == "a.py":
            return [Mock(type="function", name="foo", size=100, mtime=1000, deps=[])]
        elif file == "b.py":
            return [Mock(type="function", name="bar", size=100, mtime=1000, deps=[])]
        elif file == "c.py":
            return [Mock(type="function", name="baz", size=50, mtime=1000, deps=[])]
        return []

    mock_repo_map.get_file_symbols.side_effect = get_file_symbols

    ranker = ContextRanker(mock_repo_map)

    # Run ranking multiple times
    results1 = ranker.rank_files(query=None, limit=10)
    results2 = ranker.rank_files(query=None, limit=10)

    # Results should be identical
    assert len(results1) == len(results2)

    # File order should be deterministic
    files1 = [r.file for r in results1]
    files2 = [r.file for r in results2]
    assert files1 == files2


def test_rank_with_ties_breaks_by_filepath():
    """Test that ties in score are broken by filepath."""
    mock_repo_map = Mock()
    mock_repo_map.get_files.return_value = ["zebra.py", "alpha.py"]

    # Both files have identical scores
    def get_file_symbols(file):
        return [Mock(type="function", name="fn", size=100, mtime=1000, deps=[])]

    mock_repo_map.get_file_symbols.side_effect = get_file_symbols

    ranker = ContextRanker(mock_repo_map)
    results = ranker.rank_files(query=None, limit=10)

    # alpha.py should come before zebra.py when scores are equal
    files = [r.file for r in results]
    assert files.index("alpha.py") < files.index("zebra.py")
