# tests/test_auth/test_service.py
"""Tests for AuthService"""
import pytest
from src.auth.service import AuthService


@pytest.fixture
def auth_service() -> AuthService:
    """Create a fresh AuthService for testing"""
    return AuthService("test_password")


class TestAuthService:
    """Test AuthService functionality"""

    def test_verify_password_correct(self, auth_service: AuthService) -> None:
        """Test verifying correct password"""
        assert auth_service.verify_password("test_password", "127.0.0.1") is True

    def test_verify_password_incorrect(self, auth_service: AuthService) -> None:
        """Test verifying incorrect password"""
        assert auth_service.verify_password("wrong_password", "127.0.0.1") is False

    def test_create_session(self, auth_service: AuthService) -> None:
        """Test session creation"""
        session_id = auth_service.create_session()
        assert session_id is not None
        assert len(session_id) == 64  # 32 bytes = 64 hex chars
        assert auth_service.is_session_valid(session_id) is True

    def test_session_validity(self, auth_service: AuthService) -> None:
        """Test session validity check"""
        session_id = auth_service.create_session()
        assert auth_service.is_session_valid(session_id) is True
        assert auth_service.is_session_valid("invalid_session") is False
        assert auth_service.is_session_valid(None) is False

    def test_invalidate_session(self, auth_service: AuthService) -> None:
        """Test session invalidation"""
        session_id = auth_service.create_session()
        assert auth_service.is_session_valid(session_id) is True
        
        auth_service.invalidate_session(session_id)
        assert auth_service.is_session_valid(session_id) is False

    def test_rate_limiting(self, auth_service: AuthService) -> None:
        """Test rate limiting on failed attempts"""
        ip = "192.168.1.1"
        
        # First 5 attempts should fail but not be rate limited
        for i in range(5):
            assert auth_service.is_rate_limited(ip) is False
            auth_service.verify_password("wrong", ip)
        
        # 6th attempt should be rate limited
        assert auth_service.is_rate_limited(ip) is True

    def test_rate_limit_cleared_on_success(self, auth_service: AuthService) -> None:
        """Test that rate limit is cleared on successful login"""
        ip = "192.168.1.2"
        
        # Record some failed attempts
        for _ in range(3):
            auth_service.verify_password("wrong", ip)
        
        # Successful login should clear attempts
        assert auth_service.verify_password("test_password", ip) is True
        assert len(auth_service.failed_attempts[ip]) == 0

    def test_csrf_token_generation(self, auth_service: AuthService) -> None:
        """Test CSRF token generation"""
        token = auth_service.generate_csrf_token()
        assert token is not None
        assert len(token) > 0
        assert auth_service.verify_csrf_token(token) is True

    def test_csrf_token_one_time_use(self, auth_service: AuthService) -> None:
        """Test that CSRF tokens are one-time use"""
        token = auth_service.generate_csrf_token()
        
        # First use should succeed
        assert auth_service.verify_csrf_token(token) is True
        
        # Second use should fail
        assert auth_service.verify_csrf_token(token) is False

    def test_csrf_token_invalid(self, auth_service: AuthService) -> None:
        """Test invalid CSRF token"""
        assert auth_service.verify_csrf_token("invalid_token") is False
        assert auth_service.verify_csrf_token(None) is False

    def test_multiple_sessions(self, auth_service: AuthService) -> None:
        """Test managing multiple sessions"""
        session1 = auth_service.create_session()
        session2 = auth_service.create_session()
        
        assert auth_service.is_session_valid(session1) is True
        assert auth_service.is_session_valid(session2) is True
        
        auth_service.invalidate_session(session1)
        assert auth_service.is_session_valid(session1) is False
        assert auth_service.is_session_valid(session2) is True

    def test_different_ips_rate_limited_separately(self, auth_service: AuthService) -> None:
        """Test that rate limiting is per-IP"""
        ip1 = "192.168.1.1"
        ip2 = "192.168.1.2"
        
        # Rate limit IP1
        for _ in range(5):
            auth_service.verify_password("wrong", ip1)
        
        assert auth_service.is_rate_limited(ip1) is True
        assert auth_service.is_rate_limited(ip2) is False