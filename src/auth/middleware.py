# src/auth/middleware.py
from typing import Any, Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.requests import Request
from starlette.types import ASGIApp

from src.config import config
from src.auth.service import AuthService

class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for protected routes"""

    def __init__(self, app: ASGIApp, auth_service: AuthService) -> None:
        super().__init__(app)
        self.auth_service = auth_service
        self.mcp_api_token = config.MCP_API_TOKEN

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        """Authenticate requests"""

        # Check MCP endpoint authentication
        if request.url.path == "/mcp":
            if self.mcp_api_token:
                auth_header = request.headers.get("Authorization", "")

                if not auth_header.startswith("Bearer "):
                    return JSONResponse(
                        {"error": "Missing or invalid Authorization header"},
                        status_code=401
                    )

                token = auth_header.replace("Bearer ", "")

                if token != self.mcp_api_token:
                    return JSONResponse(
                        {"error": "Invalid token"},
                        status_code=403
                    )

        # Check UI authentication
        if request.url.path.startswith("/ui") or request.url.path.startswith("/api/") or request.url.path == "/logout":
            session_id = request.cookies.get("session_id")

            if not self.auth_service.is_session_valid(session_id):
                return RedirectResponse(url="/login", status_code=302)

        return await call_next(request)