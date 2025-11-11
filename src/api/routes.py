# src/api/routes.py (REFACTORED - USE TEMPLATES)
import logging
from pathlib import Path
from typing import Any
from jinja2 import Environment, FileSystemLoader
from starlette.responses import HTMLResponse
from fastmcp import FastMCP

from src.upstream.manager import UpstreamManager
from src.exceptions import ServerConfigError
from src.auth.validators import (
    validate_server_name,
    validate_url,
    validate_command,
    validate_port,
    validate_args,
    sanitize_token
)
from src.auth.service import AuthService

logger = logging.getLogger(__name__)

# Setup Jinja2
TEMPLATE_DIR = Path(__file__).parent.parent / "ui" / "templates"
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

def register_api_routes(mcp: FastMCP, upstream: UpstreamManager, auth_service: AuthService) -> None:
    """Register API endpoints with security validation"""

    @mcp.custom_route("/api/servers", methods=["GET"])
    async def get_servers(request: Any) -> HTMLResponse:
        """Return HTML fragment with server list"""
        try:
            all_servers: list[dict[str, Any]] = []

            for name, config in upstream.http_servers.items():
                tools_count = len(upstream.tools_cache.get(name, []))
                auth_indicator = "🔐" if config.auth_token else ""
                all_servers.append({
                    "name": name,
                    "type": "HTTP",
                    "config": config.url,
                    "auth": auth_indicator,
                    "tools": tools_count,
                    "status": ""
                })

            for name, config in upstream.stdio_servers.items():
                tools_count = len(upstream.tools_cache.get(name, []))
                config_str = f"{config.command} {' '.join(config.args)}"
                all_servers.append({
                    "name": name,
                    "type": "Stdio",
                    "config": config_str,
                    "auth": "",
                    "tools": tools_count,
                    "status": ""
                })

            for name, config in upstream.service_servers.items():
                tools_count = len(upstream.tools_cache.get(name, []))

                if name in upstream.background_processes:
                    process = upstream.background_processes[name]
                    status = "🟢 Running" if process.poll() is None else "🔴 Crashed"
                else:
                    status = "⚪ Not Started"

                config_str = f"{config.command} {' '.join(config.args)} (port {config.port})"
                all_servers.append({
                    "name": name,
                    "type": "Service",
                    "config": config_str,
                    "auth": "",
                    "tools": tools_count,
                    "status": status
                })

            template = jinja_env.get_template("api/server_list.html")
            html = template.render(servers=all_servers)
            return HTMLResponse(html)
        except Exception:
            logger.exception("Error fetching servers")
            template = jinja_env.get_template("api/error.html")
            html = template.render(message="Error loading servers")
            return HTMLResponse(html)

    @mcp.custom_route("/api/servers/http", methods=["POST"])
    async def add_http_server(request: Any) -> HTMLResponse:
        """Add a new HTTP server with validation"""
        try:
            form = await request.form()
            name = form.get("name", "").strip()
            url = form.get("url", "").strip()
            auth_token = form.get("auth_token", "").strip() or None

            if not validate_server_name(name):
                logger.warning(f"Invalid server name: {name}")
                template = jinja_env.get_template("api/error.html")
                html = template.render(message="Invalid server name (alphanumeric, dash, underscore only, max 50 chars)")
                return HTMLResponse(html)

            if not validate_url(url):
                logger.warning(f"Invalid URL: {url}")
                template = jinja_env.get_template("api/error.html")
                html = template.render(message="Invalid URL (must be http/https)")
                return HTMLResponse(html)

            if auth_token:
                auth_token = sanitize_token(auth_token)

            upstream.add_http_server(name, url, auth_token)
            from src.tools.registry import register_upstream_tools
            await register_upstream_tools(mcp, upstream)

            logger.info(f"HTTP server added: {name}")
            template = jinja_env.get_template("api/success.html")
            html = template.render(message=f'HTTP server "{name}" added successfully!')
            return HTMLResponse(html)
        except ServerConfigError:
            logger.warning("Server config error for HTTP server")
            template = jinja_env.get_template("api/error.html")
            html = template.render(message="Failed to add server")
            return HTMLResponse(html)
        except Exception:
            logger.exception("Error adding HTTP server")
            template = jinja_env.get_template("api/error.html")
            html = template.render(message="An error occurred")
            return HTMLResponse(html)

    @mcp.custom_route("/api/servers/stdio", methods=["POST"])
    async def add_stdio_server(request: Any) -> HTMLResponse:
        """Add a new stdio server with validation"""
        try:
            form = await request.form()
            name = form.get("name", "").strip()
            command = form.get("command", "").strip()
            args_str = form.get("args", "")
            args = [arg.strip() for arg in str(args_str).split(",") if arg.strip()]

            if not validate_server_name(name):
                logger.warning(f"Invalid server name: {name}")
                template = jinja_env.get_template("api/error.html")
                html = template.render(message="Invalid server name")
                return HTMLResponse(html)

            if not validate_command(command):
                logger.warning(f"Invalid command: {command}")
                template = jinja_env.get_template("api/error.html")
                html = template.render(message="Command not in whitelist")
                return HTMLResponse(html)

            if not validate_args(args):
                logger.warning(f"Invalid args for {name}")
                template = jinja_env.get_template("api/error.html")
                html = template.render(message="Invalid arguments")
                return HTMLResponse(html)

            upstream.add_stdio_server(name, command, args)
            from src.tools.registry import register_upstream_tools
            await register_upstream_tools(mcp, upstream)

            logger.info(f"Stdio server added: {name}")
            template = jinja_env.get_template("api/success.html")
            html = template.render(message=f'Stdio server "{name}" added successfully!')
            return HTMLResponse(html)
        except ServerConfigError:
            logger.warning("Server config error for stdio server")
            template = jinja_env.get_template("api/error.html")
            html = template.render(message="Failed to add server")
            return HTMLResponse(html)
        except Exception:
            logger.exception("Error adding stdio server")
            template = jinja_env.get_template("api/error.html")
            html = template.render(message="An error occurred")
            return HTMLResponse(html)

    @mcp.custom_route("/api/servers/service", methods=["POST"])
    async def add_service_server(request: Any) -> HTMLResponse:
        """Add a new service server with validation"""
        try:
            form = await request.form()
            name = form.get("name", "").strip()
            command = form.get("command", "").strip()
            args_str = form.get("args", "")
            args = [arg.strip() for arg in str(args_str).split(",") if arg.strip()]
            
            try:
                port = int(form.get("port", 9121))
            except ValueError:
                logger.warning(f"Invalid port for {name}")
                template = jinja_env.get_template("api/error.html")
                html = template.render(message="Invalid port number")
                return HTMLResponse(html)

            if not validate_server_name(name):
                logger.warning(f"Invalid server name: {name}")
                template = jinja_env.get_template("api/error.html")
                html = template.render(message="Invalid server name")
                return HTMLResponse(html)

            if not validate_command(command):
                logger.warning(f"Invalid command: {command}")
                template = jinja_env.get_template("api/error.html")
                html = template.render(message="Command not in whitelist")
                return HTMLResponse(html)

            if not validate_args(args):
                logger.warning(f"Invalid args for {name}")
                template = jinja_env.get_template("api/error.html")
                html = template.render(message="Invalid arguments")
                return HTMLResponse(html)

            if not validate_port(port):
                logger.warning(f"Invalid port: {port}")
                template = jinja_env.get_template("api/error.html")
                html = template.render(message="Port must be between 1024 and 65535")
                return HTMLResponse(html)

            upstream.add_service_server(name, command, args, port)
            from src.tools.registry import register_upstream_tools
            await register_upstream_tools(mcp, upstream)

            logger.info(f"Service server added: {name}")
            template = jinja_env.get_template("api/success.html")
            html = template.render(message=f'Service server "{name}" added successfully and started!')
            return HTMLResponse(html)
        except ServerConfigError:
            logger.warning("Server config error for service server")
            template = jinja_env.get_template("api/error.html")
            html = template.render(message="Failed to add server")
            return HTMLResponse(html)
        except Exception:
            logger.exception("Error adding service server")
            template = jinja_env.get_template("api/error.html")
            html = template.render(message="An error occurred")
            return HTMLResponse(html)

    @mcp.custom_route("/api/servers/{name}", methods=["DELETE"])
    async def remove_server(request: Any) -> HTMLResponse:
        """Remove a server"""
        try:
            name = request.path_params.get("name", "").strip()

            if not validate_server_name(name):
                logger.warning(f"Invalid server name: {name}")
                template = jinja_env.get_template("api/error.html")
                html = template.render(message="Invalid server name")
                return HTMLResponse(html)

            upstream.remove_server(name)
            logger.info(f"Server removed: {name}")

            template = jinja_env.get_template("api/success.html")
            html = template.render(message=f'Server "{name}" removed successfully!')
            return HTMLResponse(html)
        except Exception:
            logger.exception("Error removing server")
            template = jinja_env.get_template("api/error.html")
            html = template.render(message="An error occurred")
            return HTMLResponse(html)

    @mcp.custom_route("/api/trigger-update", methods=["GET"])
    async def trigger_update(request: Any) -> HTMLResponse:
        """Trigger server list update"""
        return HTMLResponse('<script>document.body.dispatchEvent(new Event("serverUpdate"))</script>')