# tests/test_auth/test_service.py
from src.auth.service import AuthService


class TestAuthService:
    """Test suite for AuthService"""

    def test_verify_password_correct(self, auth_service: AuthService) -> None:
        """Test password verification with correct password"""
        assert auth_service.verify_password("test_password") is True

    def test_verify_password_incorrect(self, auth_service: AuthService) -> None:
        """Test password verification with incorrect password"""
        assert auth_service.verify_password("wrong_password") is False

    def test_create_session(self, auth_service: AuthService) -> None:
        """Test session creation"""
        session_id = auth_service.create_session()
        assert isinstance(session_id, str)
        assert len(session_id) == 32  # hex of 16 bytes
        assert auth_service.is_session_valid(session_id) is True

    def test_is_session_valid_with_valid_session(self, auth_service: AuthService) -> None:
        """Test session validation with valid session"""
        session_id = auth_service.create_session()
        assert auth_service.is_session_valid(session_id) is True

    def test_is_session_valid_with_invalid_session(self, auth_service: AuthService) -> None:
        """Test session validation with invalid session"""
        assert auth_service.is_session_valid("invalid_session") is False

    def test_is_session_valid_with_none(self, auth_service: AuthService) -> None:
        """Test session validation with None"""
        assert auth_service.is_session_valid(None) is False

    def test_invalidate_session(self, auth_service: AuthService) -> None:
        """Test session invalidation"""
        session_id = auth_service.create_session()
        assert auth_service.is_session_valid(session_id) is True
        
        auth_service.invalidate_session(session_id)
        assert auth_service.is_session_valid(session_id) is False

    def test_invalidate_nonexistent_session(self, auth_service: AuthService) -> None:
        """Test invalidating a session that doesn't exist"""
        # Should not raise an error
        auth_service.invalidate_session("nonexistent")
        assert True

    def test_multiple_sessions(self, auth_service: AuthService) -> None:
        """Test managing multiple sessions"""
        session1 = auth_service.create_session()
        session2 = auth_service.create_session()
        
        assert session1 != session2
        assert auth_service.is_session_valid(session1) is True
        assert auth_service.is_session_valid(session2) is True
        
        auth_service.invalidate_session(session1)
        assert auth_service.is_session_valid(session1) is False
        assert auth_service.is_session_valid(session2) is True