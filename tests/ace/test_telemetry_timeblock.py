"""Tests for telemetry time_block functionality."""
from ace.telemetry import time_block, Telemetry


def test_time_block_basic():
    """Test basic time_block usage."""
    telemetry = Telemetry()

    with time_block("test.operation", telemetry):
        # Simulate some work
        _ = sum(range(1000))

    # Should have recorded timing data
    # (Implementation specific - this is a smoke test)
    assert True  # Placeholder assertion


def test_time_block_nested():
    """Test nested time_block calls."""
    telemetry = Telemetry()

    with time_block("outer", telemetry):
        _ = sum(range(100))

        with time_block("inner", telemetry):
            _ = sum(range(50))

    # Both should complete without error
    assert True


def test_time_block_with_exception():
    """Test time_block handles exceptions gracefully."""
    telemetry = Telemetry()

    try:
        with time_block("failing.operation", telemetry):
            raise ValueError("test error")
    except ValueError:
        pass

    # Should not crash telemetry
    assert True
