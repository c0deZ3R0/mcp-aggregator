# src/auth/service.py
import os
from typing import Optional

class AuthService:
    """Handles authentication logic"""

    def __init__(self, ui_password: str) -> None:
        self.ui_password = ui_password
        self.authenticated_sessions: set[str] = set()

    def verify_password(self, password: str) -> bool:
        """Verify UI password"""
        return password == self.ui_password

    def create_session(self) -> str:
        """Create a new authenticated session"""
        session_id = os.urandom(16).hex()
        self.authenticated_sessions.add(session_id)
        return session_id

    def is_session_valid(self, session_id: Optional[str]) -> bool:
        """Check if session is valid"""
        return session_id is not None and session_id in self.authenticated_sessions

    def invalidate_session(self, session_id: Optional[str]) -> None:
        """Invalidate a session"""
        if session_id and session_id in self.authenticated_sessions:
            self.authenticated_sessions.remove(session_id)