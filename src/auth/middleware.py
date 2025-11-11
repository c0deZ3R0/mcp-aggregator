# src/auth/middleware.py (UPDATED - WITH NONCE)
import logging
import secrets
from typing import Any, Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.requests import Request
from starlette.types import ASGIApp

from src.config import config
from src.auth.service import AuthService

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware with security hardening"""

    def __init__(self, app: ASGIApp, auth_service: AuthService) -> None:
        super().__init__(app)
        self.auth_service = auth_service
        self.mcp_api_token = config.MCP_API_TOKEN

    def _get_client_ip(self, request: Request) -> str:
        """Safely get client IP address"""
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        """Authenticate requests and add security headers"""

        # Generate nonce for this request
        nonce = secrets.token_urlsafe(16)
        request.scope["nonce"] = nonce

        # Check MCP endpoint authentication
        if request.url.path == "/mcp":
            if self.mcp_api_token:
                auth_header = request.headers.get("Authorization", "")

                if not auth_header.startswith("Bearer "):
                    client_ip = self._get_client_ip(request)
                    logger.warning(f"Missing Authorization header from {client_ip}")
                    return JSONResponse(
                        {"error": "Missing or invalid Authorization header"},
                        status_code=401
                    )

                token = auth_header.replace("Bearer ", "")

                if token != self.mcp_api_token:
                    client_ip = self._get_client_ip(request)
                    logger.warning(f"Invalid token attempt from {client_ip}")
                    return JSONResponse(
                        {"error": "Invalid token"},
                        status_code=403
                    )

        # Check UI authentication
        if request.url.path.startswith("/ui") or request.url.path.startswith("/api/") or request.url.path == "/logout":
            session_id = request.cookies.get("session_id")

            if not self.auth_service.is_session_valid(session_id):
                return RedirectResponse(url="/login", status_code=302)

        # CSRF check for state-changing requests
        if request.method in ["POST", "DELETE", "PUT"]:
            if request.url.path.startswith("/api/") or request.url.path.startswith("/ui"):
                csrf_token: str | None = None
                
                try:
                    if request.method == "POST":
                        form = await request.form()
                        csrf_token_value = form.get("csrf_token")
                        # Convert to string if it's not None
                        csrf_token = str(csrf_token_value) if csrf_token_value else None
                    else:
                        csrf_token = request.headers.get("X-CSRF-Token")
                    
                    if not self.auth_service.verify_csrf_token(csrf_token):
                        client_ip = self._get_client_ip(request)
                        logger.warning(f"Invalid CSRF token from {client_ip}")
                        return JSONResponse({"error": "Invalid CSRF token"}, status_code=403)
                except Exception as e:
                    client_ip = self._get_client_ip(request)
                    logger.error(f"CSRF verification error from {client_ip}: {e}")
                    return JSONResponse({"error": "CSRF verification failed"}, status_code=403)

        response = await call_next(request)
        
        # Add security headers with nonce
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"script-src 'self' https://cdn.tailwindcss.com https://unpkg.com 'nonce-{nonce}'; "
            f"style-src 'self' https://cdn.tailwindcss.com 'unsafe-inline'; "
            f"img-src 'self' data:; "
            f"font-src 'self'; "
            f"connect-src 'self'; "
            f"frame-ancestors 'none'; "
            f"base-uri 'self'; "
            f"form-action 'self'"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response