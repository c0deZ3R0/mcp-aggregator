# src/ui/routes.py (COMPLETE FILE - WITH STATS)
import logging
from pathlib import Path
from typing import Any, Union
from jinja2 import Environment, FileSystemLoader
from starlette.responses import HTMLResponse, RedirectResponse
from fastmcp import FastMCP
import json

from src.auth.service import AuthService
from src.upstream.manager import UpstreamManager
from src.tools.registry import get_all_tools

logger = logging.getLogger(__name__)

# Setup Jinja2
TEMPLATE_DIR = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

# Add JSON filter
jinja_env.filters['tojson'] = lambda x, indent=None: json.dumps(x, indent=indent)

def register_ui_routes(mcp: FastMCP, auth_service: AuthService, upstream: UpstreamManager) -> None:
    """Register UI endpoints with security hardening"""

    @mcp.custom_route("/login", methods=["GET", "POST"])
    async def login(request: Any) -> Union[HTMLResponse, RedirectResponse]:
        """Simple login page with rate limiting"""
        nonce = request.scope.get("nonce", "")
        
        if request.method == "POST":
            client_ip = request.client.host if request.client else "unknown"
            
            if auth_service.is_rate_limited(client_ip):
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                template = jinja_env.get_template("rate_limited.html")
                csrf_token = auth_service.generate_csrf_token()
                html = template.render(csrf_token=csrf_token, nonce=nonce)
                return HTMLResponse(html)
            
            form = await request.form()
            password = form.get("password", "")

            if auth_service.verify_password(password, client_ip):
                session_id = auth_service.create_session()
                response = RedirectResponse(url="/ui", status_code=302)
                response.set_cookie(
                    "session_id",
                    session_id,
                    httponly=True,
                    samesite="lax",
                    secure=True,
                    max_age=3600
                )
                logger.info(f"Successful login from IP: {client_ip}")
                return response
            else:
                logger.warning(f"Failed login attempt from IP: {client_ip}")
                template = jinja_env.get_template("login.html")
                csrf_token = auth_service.generate_csrf_token()
                html = template.render(csrf_token=csrf_token, nonce=nonce, error="Invalid password")
                return HTMLResponse(html)

        template = jinja_env.get_template("login.html")
        csrf_token = auth_service.generate_csrf_token()
        html = template.render(csrf_token=csrf_token, nonce=nonce, error=None)
        return HTMLResponse(html)

    @mcp.custom_route("/ui", methods=["GET"])
    async def home(request: Any) -> HTMLResponse:
        """Render the main UI with CSRF token, tools, and tracking stats"""
        template = jinja_env.get_template("dashboard.html")
        csrf_token = auth_service.generate_csrf_token()
        nonce = request.scope.get("nonce", "")
        
        # Get tracking statistics
        stats = upstream.tracking.get_statistics()
        
        # Get all registered tools
        tools = get_all_tools()
        
        # Group tools by server prefix
        tools_by_server: dict[str, list[dict[str, Any]]] = {}
        for tool in tools:
            # Extract server name from prefixed tool name (e.g., "serena_list_dir" -> "serena")
            parts = tool["name"].split("_", 1)
            server_name = parts[0] if parts else "unknown"
            
            if server_name not in tools_by_server:
                tools_by_server[server_name] = []
            tools_by_server[server_name].append(tool)
        
        html = template.render(
            csrf_token=csrf_token,
            nonce=nonce,
            stats=stats,  # ADD THIS LINE
            tools=tools,
            tools_by_server=tools_by_server,
            total_tools=len(tools)
        )
        return HTMLResponse(html)

    @mcp.custom_route("/logout", methods=["GET"])
    async def logout(request: Any) -> RedirectResponse:
        """Logout and clear session"""
        session_id = request.cookies.get("session_id")
        auth_service.invalidate_session(session_id)
        logger.info(f"User logged out: {session_id[:8] if session_id else 'unknown'}...")

        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("session_id")
        return response