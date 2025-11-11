# tests/test_upstream/test_utils.py
import os
from src.upstream.utils import resolve_token


class TestResolveToken:
    """Test token resolution"""

    def test_resolve_literal_token(self) -> None:
        """Test resolving a literal token (no $ prefix)"""
        token = resolve_token("my-secret-token")
        assert token == "my-secret-token"

    def test_resolve_env_var_token(self) -> None:
        """Test resolving a token from environment variable"""
        os.environ["TEST_TOKEN"] = "env-secret-token"
        token = resolve_token("$TEST_TOKEN")
        assert token == "env-secret-token"
        del os.environ["TEST_TOKEN"]

    def test_resolve_missing_env_var(self, capsys) -> None:
        """Test resolving a missing environment variable"""
        token = resolve_token("$NONEXISTENT_VAR")
        assert token is None
        
        captured = capsys.readouterr()
        assert "NONEXISTENT_VAR" in captured.out
        assert "not found" in captured.out

    def test_resolve_none_token(self) -> None:
        """Test resolving None"""
        token = resolve_token(None)
        assert token is None

    def test_resolve_empty_string(self) -> None:
        """Test resolving empty string"""
        token = resolve_token("")
        assert token is None

    def test_resolve_env_var_with_empty_value(self) -> None:
        """Test resolving env var that exists but is empty"""
        os.environ["EMPTY_VAR"] = ""
        token = resolve_token("$EMPTY_VAR")
        assert token == ""
        del os.environ["EMPTY_VAR"]