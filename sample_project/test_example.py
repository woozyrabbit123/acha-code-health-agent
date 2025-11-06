"""Tests for example module"""
from example import get_api_key, validate_key


def test_get_api_key():
    """Test that get_api_key returns a string"""
    key = get_api_key()
    assert isinstance(key, str)
    assert len(key) > 0


def test_validate_key():
    """Test key validation"""
    # This test should pass with the API_KEY constant
    assert validate_key("secret-key-12345") is True
    assert validate_key("wrong-key") is False
