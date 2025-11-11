# src/upstream/manager.py
import subprocess
import time
import requests
import os
import logging
from typing import Any, Optional

from fastmcp import Client
from fastmcp.client.auth import BearerAuth

from src.exceptions import ServerConfigError, ToolDiscoveryError
from src.constants import (
    DEFAULT_STARTUP_TIMEOUT,
    DEFAULT_HEALTH_CHECK_PATH,
    DEFAULT_REQUEST_TIMEOUT
)
from src.upstream.schemas import (
    HTTPServerConfig,
    StdioServerConfig,
    ServiceServerConfig
)
from src.upstream.utils import resolve_token
from src.upstream.defaults import (
    get_default_http_servers,
    get_default_stdio_servers,
    get_default_service_servers
)

logger = logging.getLogger(__name__)

class UpstreamManager:
    """Manages connections to upstream MCP servers"""

    def __init__(self) -> None:
        self.http_servers: dict[str, HTTPServerConfig] = {}
        self.stdio_servers: dict[str, StdioServerConfig] = {}
        self.service_servers: dict[str, ServiceServerConfig] = {}
        self.clients: dict[str, dict[str, Any]] = {}
        self.tools_cache: dict[str, list[dict[str, Any]]] = {}
        self.background_processes: dict[str, subprocess.Popen[str]] = {}
        
        # Initialize with defaults
        self._load_defaults()
    
    def _load_defaults(self) -> None:
        """Load default server configurations"""
        # Load HTTP servers
        for name, config_dict in get_default_http_servers().items():
            url = config_dict.get("url")
            if url is None:
                logger.warning(f"Skipping HTTP server '{name}': url is required")
                continue
            self.http_servers[name] = HTTPServerConfig(
                url=url,
                auth_token=config_dict.get("auth_token")
            )
        
        # Load stdio servers
        for name, config_dict in get_default_stdio_servers().items():
            self.stdio_servers[name] = StdioServerConfig(
                command=config_dict["command"],
                args=config_dict["args"],
                env=config_dict.get("env", {}),
                working_directory=config_dict.get("working_directory")
            )
        
        # Load service servers
        for name, config_dict in get_default_service_servers().items():
            self.service_servers[name] = ServiceServerConfig(
                command=config_dict["command"],
                args=config_dict["args"],
                port=config_dict["port"],
                health_check_path=config_dict.get("health_check_path", DEFAULT_HEALTH_CHECK_PATH),
                startup_timeout=config_dict.get("startup_timeout", DEFAULT_STARTUP_TIMEOUT),
                env=config_dict.get("env", {}),
                working_directory=config_dict.get("working_directory")
            )

    def _start_service(self, service_name: str, config: ServiceServerConfig) -> bool:
        """Start a service in background and wait for it to be ready"""
        logger.info(f"🚀 Starting service: {service_name}")

        try:
            env = os.environ.copy()
            env.update(config.env)

            process = subprocess.Popen(
                [config.command] + config.args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=config.working_directory
            )

            self.background_processes[service_name] = process
            logger.info(f"   Process started with PID: {process.pid}")

            url = f"http://localhost:{config.port}{config.health_check_path}"
            logger.info(f"   Waiting for service at {url}...")

            start_time = time.time()
            while time.time() - start_time < config.startup_timeout:
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    logger.error(f"   Process died. STDOUT: {stdout[:200] if stdout else ''}")
                    logger.error(f"   STDERR: {stderr[:200] if stderr else ''}")
                    return False

                try:
                    response = requests.get(url, timeout=DEFAULT_REQUEST_TIMEOUT)
                    if response.status_code < 500:
                        logger.info(f"   ✅ Service {service_name} is ready!")
                        return True
                except requests.RequestException:
                    pass

                time.sleep(1)

            logger.error(f"   Service {service_name} failed to start within {config.startup_timeout}s")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            return False

        except Exception as e:
            logger.exception(f"Error starting service {service_name}: {e}")
            return False

    def _get_client_config(self, server: str) -> dict[str, Any]:
        """Get appropriate client configuration for a server"""
        if server in self.http_servers:
            http_config = self.http_servers[server]
            resolved_token = resolve_token(http_config.auth_token)
            return {
                "type": "http",
                "url": http_config.url,
                "auth_token": resolved_token
            }
        elif server in self.service_servers:
            service_config = self.service_servers[server]
            return {
                "type": "http",
                "url": f"http://localhost:{service_config.port}/mcp",
                "auth_token": None
            }
        elif server in self.stdio_servers:
            config = self.stdio_servers[server]
            return {
                "type": "stdio",
                "command": config.command,
                "args": config.args,
                "env": config.env,
                "working_directory": config.working_directory
            }
        else:
            raise ServerConfigError(f"Unknown server: {server}")

    async def discover_tools(self, server: str) -> list[dict[str, Any]]:
        """Discover available tools from upstream server"""
        try:
            config = self._get_client_config(server)
            logger.info(f"🔍 Discovering tools from: {server} (type: {config['type']})")

            if config["type"] == "http":
                if config.get("auth_token"):
                    client = Client(config["url"], auth=BearerAuth(config["auth_token"]))
                else:
                    client = Client(config["url"])
            else:  # stdio
                mcp_config = {
                    "mcpServers": {
                        server: {
                            "command": config["command"],
                            "args": config["args"],
                            "env": config["env"]
                        }
                    }
                }
                if config["working_directory"]:
                    mcp_config["mcpServers"][server]["working_directory"] = config["working_directory"]

                client = Client(mcp_config)

            async with client:
                tools = await client.list_tools()
                tools_list = [
                    {
                        "name": tool.name,
                        "description": tool.description or "No description",
                        "inputSchema": tool.inputSchema
                    }
                    for tool in tools
                ]

                logger.info(f"✅ Found {len(tools_list)} tools from {server}")
                self.tools_cache[server] = tools_list
                self.clients[server] = config
                return tools_list

        except Exception as e:
            logger.exception(f"Error discovering tools from {server}")
            raise ToolDiscoveryError(f"Failed to discover tools from {server}: {e}")

    async def call_tool(self, server: str, tool: str, arguments: dict[str, Any]) -> Any:
        """Route tool calls to upstream MCP servers"""
        if server not in self.clients:
            raise ServerConfigError(f"Unknown server: {server}")

        config = self.clients[server]
        logger.info(f"🔧 Calling {server}/{tool} with arguments: {arguments}")

        if config["type"] == "http":
            if config.get("auth_token"):
                client = Client(config["url"], auth=BearerAuth(config["auth_token"]))
            else:
                client = Client(config["url"])
        else:  # stdio
            mcp_config = {
                "mcpServers": {
                    server: {
                        "command": config["command"],
                        "args": config["args"],
                        "env": config["env"]
                    }
                }
            }
            if config.get("working_directory"):
                mcp_config["mcpServers"][server]["working_directory"] = config["working_directory"]

            client = Client(mcp_config)

        async with client:
            result = await client.call_tool(tool, arguments)
            logger.info(f"📥 Result from {server}/{tool}")

            if result.data is not None:
                return result.data
            elif result.content:
                text_parts: list[str] = []
                for content_block in result.content:
                    if hasattr(content_block, 'text'):
                        text_value = getattr(content_block, 'text', None)
                        if isinstance(text_value, str):
                            text_parts.append(text_value)
                return "\n\n".join(text_parts) if text_parts else None
            else:
                return None

    def add_http_server(self, name: str, url: str, auth_token: Optional[str] = None) -> None:
        """Add a new HTTP server"""
        if name in self.http_servers or name in self.stdio_servers or name in self.service_servers:
            raise ServerConfigError(f"Server '{name}' already exists")

        self.http_servers[name] = HTTPServerConfig(url=url, auth_token=auth_token)
        logger.info(f"✅ Added HTTP server: {name}")

    def add_stdio_server(self, name: str, command: str, args: list[str],
                        env: Optional[dict[str, str]] = None,
                        working_directory: Optional[str] = None) -> None:
        """Add a new stdio server"""
        if name in self.http_servers or name in self.stdio_servers or name in self.service_servers:
            raise ServerConfigError(f"Server '{name}' already exists")

        self.stdio_servers[name] = StdioServerConfig(
            command=command,
            args=args,
            env=env or {},
            working_directory=working_directory
        )
        logger.info(f"✅ Added stdio server: {name}")

    def add_service_server(self, name: str, command: str, args: list[str], port: int,
                          health_check_path: str = DEFAULT_HEALTH_CHECK_PATH,
                          startup_timeout: int = DEFAULT_STARTUP_TIMEOUT,
                          env: Optional[dict[str, str]] = None,
                          working_directory: Optional[str] = None) -> None:
        """Add a new service server"""
        if name in self.http_servers or name in self.stdio_servers or name in self.service_servers:
            raise ServerConfigError(f"Server '{name}' already exists")

        for existing_name, existing_config in self.service_servers.items():
            if existing_config.port == port:
                raise ServerConfigError(f"Port {port} is already used by service '{existing_name}'")

        self.service_servers[name] = ServiceServerConfig(
            command=command,
            args=args,
            port=port,
            health_check_path=health_check_path,
            startup_timeout=startup_timeout,
            env=env or {},
            working_directory=working_directory
        )
        logger.info(f"✅ Added service server: {name}")

    def remove_server(self, name: str) -> None:
        """Remove a server and cleanup resources"""
        if name in self.background_processes:
            process = self.background_processes[name]
            try:
                logger.info(f"🛑 Stopping service: {name}")
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"Force killing service: {name}")
                process.kill()
            except Exception as e:
                logger.warning(f"Error stopping service {name}: {e}")
            del self.background_processes[name]

        if name in self.http_servers:
            del self.http_servers[name]
        if name in self.stdio_servers:
            del self.stdio_servers[name]
        if name in self.service_servers:
            del self.service_servers[name]
        if name in self.clients:
            del self.clients[name]
        if name in self.tools_cache:
            del self.tools_cache[name]

        logger.info(f"✅ Removed server: {name}")

    def cleanup_all_processes(self) -> None:
        """Clean up all background processes"""
        logger.info("🧹 Cleaning up background processes...")
        for name, process in list(self.background_processes.items()):
            try:
                logger.info(f"   Stopping {name}...")
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.info(f"   Force killing {name}...")
                process.kill()
            except Exception as e:
                logger.warning(f"   Error stopping {name}: {e}")