# src/auth/service.py
import json
import logging
import os
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

class AuthService:
    """Handles authentication logic with security hardening"""

    def __init__(self, ui_password: str) -> None:
        self.ui_password = ui_password
        self.sessions_file = Path(".sessions.json")
        self.session_ttl = 3600  # 1 hour
        self.authenticated_sessions: dict[str, float] = self._load_sessions()
        
        # Rate limiting
        self.failed_attempts: dict[str, list[float]] = defaultdict(list)
        self.max_attempts = 5
        self.lockout_duration = 300  # 5 minutes
        
        # CSRF tokens
        self.csrf_tokens: dict[str, float] = {}

    def _load_sessions(self) -> dict[str, float]:
        """Load sessions from disk and clean expired ones"""
        if self.sessions_file.exists():
            try:
                data = json.loads(self.sessions_file.read_text())
                # Clean expired sessions
                now = datetime.now().timestamp()
                valid_sessions = {
                    sid: exp for sid, exp in data.items() 
                    if exp > now
                }
                if len(valid_sessions) != len(data):
                    self._save_sessions_to_disk(valid_sessions)
                return valid_sessions
            except Exception as e:
                logger.error(f"Error loading sessions: {e}")
                return {}
        return {}

    def _save_sessions_to_disk(self, sessions: Optional[dict[str, float]] = None) -> None:
        """Persist sessions to disk"""
        try:
            sessions_to_save = sessions or self.authenticated_sessions
            self.sessions_file.write_text(json.dumps(sessions_to_save))
        except Exception as e:
            logger.error(f"Error saving sessions: {e}")

    def verify_password(self, password: str, ip: str) -> bool:
        """Verify UI password with rate limiting"""
        if self.is_rate_limited(ip):
            logger.warning(f"Rate limit exceeded for IP: {ip}")
            return False
        
        if password != self.ui_password:
            self.record_failed_attempt(ip)
            logger.warning(f"Failed login attempt from IP: {ip}")
            return False
        
        # Clear attempts on success
        self.failed_attempts[ip] = []
        return True

    def is_rate_limited(self, ip: str) -> bool:
        """Check if IP is rate limited"""
        now = datetime.now().timestamp()
        # Clean old attempts
        self.failed_attempts[ip] = [
            t for t in self.failed_attempts[ip] 
            if now - t < self.lockout_duration
        ]
        return len(self.failed_attempts[ip]) >= self.max_attempts

    def record_failed_attempt(self, ip: str) -> None:
        """Record a failed login attempt"""
        self.failed_attempts[ip].append(datetime.now().timestamp())

    def create_session(self) -> str:
        """Create a new authenticated session with expiry"""
        session_id = os.urandom(32).hex()  # 256-bit random token
        expiry = (datetime.now() + timedelta(seconds=self.session_ttl)).timestamp()
        self.authenticated_sessions[session_id] = expiry
        self._save_sessions_to_disk()
        logger.info(f"Session created: {session_id[:8]}...")
        return session_id

    def is_session_valid(self, session_id: Optional[str]) -> bool:
        """Check if session is valid and not expired"""
        if not session_id or session_id not in self.authenticated_sessions:
            return False
        
        expiry = self.authenticated_sessions[session_id]
        if datetime.now().timestamp() > expiry:
            self.authenticated_sessions.pop(session_id, None)
            self._save_sessions_to_disk()
            return False
        
        return True

    def invalidate_session(self, session_id: Optional[str]) -> None:
        """Invalidate a session"""
        if session_id and session_id in self.authenticated_sessions:
            self.authenticated_sessions.pop(session_id, None)
            self._save_sessions_to_disk()
            logger.info(f"Session invalidated: {session_id[:8]}...")

    def generate_csrf_token(self) -> str:
        """Generate a CSRF token with expiry"""
        token = os.urandom(32).hex()
        expiry = (datetime.now() + timedelta(hours=1)).timestamp()
        self.csrf_tokens[token] = expiry
        return token

    def verify_csrf_token(self, token: Optional[str]) -> bool:
        """Verify CSRF token (one-time use)"""
        if not token or token not in self.csrf_tokens:
            return False
        
        expiry = self.csrf_tokens[token]
        if datetime.now().timestamp() > expiry:
            self.csrf_tokens.pop(token, None)
            return False
        
        # One-time use - delete after verification
        self.csrf_tokens.pop(token, None)
        return True