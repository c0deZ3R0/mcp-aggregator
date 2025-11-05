from fastmcp import FastMCP, Client
from fastmcp.client.auth import BearerAuth
import json
from typing import Any, Optional, Union
import inspect
import os
from dotenv import load_dotenv
import subprocess
import threading
import time
import requests
import atexit
import signal
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Load environment variables from .env file
load_dotenv()

mcp = FastMCP("MCP Aggregator")

# Security configuration
MCP_API_TOKEN = os.getenv("MCP_API_TOKEN")  # Token for /mcp endpoint
UI_PASSWORD = os.getenv("UI_PASSWORD", "admin")  # Password for /ui
authenticated_sessions: set[str] = set()

class UpstreamManager:
    def __init__(self) -> None:
        # HTTP-based servers with optional auth
        self.http_servers: dict[str, dict[str, Optional[str]]] = {
            "gofastmcp": {
                "url": "https://gofastmcp.com/mcp",
                "auth_token": None
            }
        }

        # Stdio-based servers (Node, Python, etc.)
        self.stdio_servers: dict[str, dict[str, Any]] = {
            "context7": {
                "command": "npx",
                "args": ["-y", "@upstash/context7-mcp"],
                "env": {},
                "working_directory": None
            },
            "filesystem": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "."
                ],
                "env": {},
                "working_directory": "."
            }
        }

        # Service-based servers (start in background, connect via HTTP)
        self.service_servers: dict[str, dict[str, Any]] = {
            "serena": {
                "command": "uvx",
                "args": [
                    "--from",
                    "git+https://github.com/oraios/serena",
                    "serena",
                    "start-mcp-server",
                    "--transport",
                    "streamable-http",
                    "--port",
                    "9121",
                    "--context",
                    "ide-assistant"
                ],
                "port": 9121,
                "health_check_path": "/mcp",
                "startup_timeout": 30,
                "env": {},
                "working_directory": None,
                "description": "Semantic code retrieval and editing toolkit with LSP integration"
            }
        }

        self.clients: dict[str, dict[str, Any]] = {}
        self.tools_cache: dict[str, list[dict[str, Any]]] = {}
        self.background_processes: dict[str, subprocess.Popen[str]] = {}

    def _resolve_token(self, token_or_env: Optional[str]) -> Optional[str]:
        """
        Resolve a token that might be an environment variable reference.
        If it starts with $, treat it as an env var name.
        Otherwise, treat it as a literal token.
        """
        if not token_or_env:
            return None

        if token_or_env.startswith("$"):
            env_var_name = token_or_env[1:]  # Remove the $ prefix
            resolved = os.getenv(env_var_name)
            if not resolved:
                print(f"⚠️  Environment variable '{env_var_name}' not found")
            return resolved

        return token_or_env

    def _start_service(self, service_name: str, config: dict[str, Any]) -> bool:
        """Start a service in a background thread and wait for it to be ready"""
        print(f"🚀 Starting service: {service_name}")

        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(config.get("env", {}))

            # Start the process
            process = subprocess.Popen(
                [config["command"]] + config["args"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=config.get("working_directory")
            )

            self.background_processes[service_name] = process
            print(f"   Process started with PID: {process.pid}")

            # Wait for service to be ready
            port = config.get("port")
            health_check_path = config.get("health_check_path", "/mcp")
            startup_timeout = config.get("startup_timeout", 30)
            url = f"http://localhost:{port}{health_check_path}"

            print(f"   Waiting for service to be ready at {url}...")

            start_time = time.time()
            while time.time() - start_time < startup_timeout:
                # Check if process has died
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    print(f"   ❌ Process died. STDOUT: {stdout[:200] if stdout else ''}")
                    print(f"   ❌ STDERR: {stderr[:200] if stderr else ''}")
                    return False

                try:
                    response = requests.get(url, timeout=2)
                    if response.status_code < 500:  # Any response that's not a server error
                        print(f"   ✅ Service {service_name} is ready!")
                        return True
                except requests.RequestException:
                    pass

                time.sleep(1)

            print(f"   ❌ Service {service_name} failed to start within {startup_timeout}s")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            return False

        except Exception as e:
            print(f"   ❌ Error starting service {service_name}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _get_client_config(self, server: str) -> dict[str, Any]:
        """Get the appropriate client configuration for a server"""
        if server in self.http_servers:
            http_config = self.http_servers[server]
            resolved_token = self._resolve_token(http_config.get("auth_token"))
            return {
                "type": "http",
                "url": http_config["url"],
                "auth_token": resolved_token
            }
        elif server in self.service_servers:
            service_config = self.service_servers[server]
            port = service_config.get("port")
            return {
                "type": "http",
                "url": f"http://localhost:{port}/mcp",
                "auth_token": None
            }
        elif server in self.stdio_servers:
            config = self.stdio_servers[server]
            return {
                "type": "stdio",
                "command": config["command"],
                "args": config.get("args", []),
                "env": config.get("env", {}),
                "working_directory": config.get("working_directory")
            }
        else:
            raise ValueError(f"Unknown server: {server}")

    async def discover_tools(self, server: str) -> list[dict[str, Any]]:
        """Discover available tools from upstream server using FastMCP Client"""
        try:
            config = self._get_client_config(server)
            print(f"🔍 Discovering tools from: {server} (type: {config['type']})")

            # Create client based on server type
            if config["type"] == "http":
                if config.get("auth_token"):
                    client = Client(config["url"], auth=BearerAuth(config["auth_token"]))
                else:
                    client = Client(config["url"])
            else:  # stdio
                # Create MCP config format for stdio servers
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

                # Convert MCP Tool objects to dict format
                tools_list = [
                    {
                        "name": tool.name,
                        "description": tool.description or "No description",
                        "inputSchema": tool.inputSchema
                    }
                    for tool in tools
                ]

                print(f"✅ Found {len(tools_list)} tools from {server}")
                print(f"   Tools: {[t['name'] for t in tools_list]}")

                self.tools_cache[server] = tools_list
                self.clients[server] = config  # Store config for later use
                return tools_list

        except Exception as e:
            print(f"❌ Error discovering tools from {server}: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def call_tool(self, server: str, tool: str, arguments: dict[str, Any]) -> Any:
        """Route tool calls to upstream MCP servers using FastMCP Client"""
        if server not in self.clients:
            raise ValueError(f"Unknown server: {server}")

        config = self.clients[server]
        print(f"🔧 Calling {server}/{tool} with arguments: {arguments}")

        # Create client based on server type
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
            print(f"📥 Result from {server}/{tool}")

            # Extract data from the result
            # Priority: structured data > content text > None
            if result.data is not None:
                return result.data
            elif result.content:
                # Combine all text content blocks
                text_parts: list[str] = []
                for content_block in result.content:
                    # Only access 'text' if it exists and is a string
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
            raise ValueError(f"Server '{name}' already exists")

        self.http_servers[name] = {
            "url": url,
            "auth_token": auth_token
        }

    def add_stdio_server(self, name: str, command: str, args: list[str], 
                        env: Optional[dict[str, str]] = None, 
                        working_directory: Optional[str] = None) -> None:
        """Add a new stdio server"""
        if name in self.http_servers or name in self.stdio_servers or name in self.service_servers:
            raise ValueError(f"Server '{name}' already exists")

        self.stdio_servers[name] = {
            "command": command,
            "args": args,
            "env": env or {},
            "working_directory": working_directory
        }

    def add_service_server(self, name: str, command: str, args: list[str], port: int,
                          health_check_path: str = "/mcp", startup_timeout: int = 30,
                          env: Optional[dict[str, str]] = None, 
                          working_directory: Optional[str] = None) -> None:
        """Add a new service server (starts in background, connects via HTTP)"""
        if name in self.http_servers or name in self.stdio_servers or name in self.service_servers:
            raise ValueError(f"Server '{name}' already exists")

        # Check if port is already in use
        for existing_name, existing_config in self.service_servers.items():
            if existing_config.get("port") == port:
                raise ValueError(f"Port {port} is already used by service '{existing_name}'")

        self.service_servers[name] = {
            "command": command,
            "args": args,
            "port": port,
            "health_check_path": health_check_path,
            "startup_timeout": startup_timeout,
            "env": env or {},
            "working_directory": working_directory
        }

    def remove_server(self, name: str) -> None:
        """Remove a server"""
        # Stop background process if running
        if name in self.background_processes:
            process = self.background_processes[name]
            try:
                print(f"🛑 Stopping service: {name}")
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"⚠️  Force killing service: {name}")
                process.kill()
            except Exception as e:
                print(f"⚠️  Error stopping service {name}: {e}")
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

    def cleanup_all_processes(self) -> None:
        """Clean up all background processes"""
        print("\n🧹 Cleaning up background processes...")
        for name, process in list(self.background_processes.items()):
            try:
                print(f"   Stopping {name}...")
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"   Force killing {name}...")
                process.kill()
            except Exception as e:
                print(f"   Error stopping {name}: {e}")

upstream = UpstreamManager()

# Register cleanup handlers
def cleanup_handler() -> None:
    upstream.cleanup_all_processes()

atexit.register(cleanup_handler)

def signal_handler(signum: int, frame: Any) -> None:
    print(f"\n⚠️  Received signal {signum}")
    cleanup_handler()
    exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

@mcp.tool
def hello_world() -> str:
    """Say hello to the world"""
    return "Hello, World!"

def create_upstream_tool_wrapper(server_name: str, tool_name: str, input_schema: dict[str, Any]) -> Any:
    """Factory function to create tool wrappers with proper signatures"""

    # Extract parameters from the input schema
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    # Build function signature dynamically
    params: list[inspect.Parameter] = []
    annotations: dict[str, Any] = {}

    for param_name, param_info in properties.items():
        param_type = param_info.get("type", "string")

        # Map JSON schema types to Python types
        type_mapping = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        python_type = type_mapping.get(param_type, Any)
        annotations[param_name] = python_type

        # Create parameter with default if not required
        if param_name in required:
            params.append(inspect.Parameter(
                param_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=python_type
            ))
        else:
            params.append(inspect.Parameter(
                param_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=None,
                annotation=Optional[python_type]
            ))

    # Create the function dynamically
    async def upstream_tool_wrapper(**kwargs: Any) -> str:
        """Wrapper for upstream tool"""
        try:
            # Filter out None values for optional parameters
            arguments = {k: v for k, v in kwargs.items() if v is not None}

            result = await upstream.call_tool(server_name, tool_name, arguments)

            # Handle different result types
            if result is None:
                return json.dumps({"error": "No result returned from upstream"})
            elif isinstance(result, str):
                return result
            elif hasattr(result, '__dict__'):
                # Handle objects with __dict__ (like applyOutput)
                return json.dumps(result.__dict__)
            else:
                try:
                    return json.dumps(result)
                except (TypeError, ValueError):
                    return str(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return json.dumps({"error": str(e)})

    # Set the signature on the wrapper function
    sig = inspect.Signature(
        parameters=params,
        return_annotation=str
    )
    upstream_tool_wrapper.__signature__ = sig  # type: ignore
    upstream_tool_wrapper.__annotations__ = {**annotations, 'return': str}

    return upstream_tool_wrapper

# Dynamically create tools for each upstream server
async def setup_upstream_tools() -> None:
    print("🚀 Starting tool discovery...")

    # First, start all service servers and wait for them
    print("\n📦 Starting background services...")
    service_threads: list[tuple[str, threading.Thread]] = []
    for service_name in list(upstream.service_servers.keys()):
        config = upstream.service_servers[service_name]
        if service_name not in upstream.background_processes:
            # Start in a background thread
            thread = threading.Thread(
                target=upstream._start_service,
                args=(service_name, config),
                daemon=True
            )
            thread.start()
            service_threads.append((service_name, thread))

    # Wait for all services to start (with timeout)
    for service_name, thread in service_threads:
        thread.join(timeout=35)  # Slightly longer than startup_timeout
        if thread.is_alive():
            print(f"⚠️  Service {service_name} is still starting...")

    # Combine all servers
    all_servers = (list(upstream.http_servers.keys()) +
                   list(upstream.stdio_servers.keys()) +
                   list(upstream.service_servers.keys()))

    for server_name in all_servers:
        print(f"\n📡 Processing server: {server_name}")
        tools = await upstream.discover_tools(server_name)

        print(f"📝 Registering {len(tools)} tools from {server_name}")
        for tool_info in tools:
            tool_name = tool_info.get("name", "unknown")
            description = tool_info.get("description", "Upstream tool")
            input_schema = tool_info.get("inputSchema", {})

            # Create wrapper with proper signature
            wrapper = create_upstream_tool_wrapper(server_name, tool_name, input_schema)

            # Register with prefixed name
            prefixed_name = f"{server_name}_{tool_name}"
            print(f"   ✓ Registering: {prefixed_name}")
            mcp.tool(
                wrapper,
                name=prefixed_name,
                description=f"[{server_name}] {description}"
            )

    print("\n✅ Tool discovery complete!")

# ============= AUTHENTICATION MIDDLEWARE =============

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Any, call_next: Any) -> Response:
        """Authentication middleware for protected routes"""

        # Check MCP endpoint authentication
        if request.url.path == "/mcp":
            if MCP_API_TOKEN:
                auth_header = request.headers.get("Authorization", "")

                if not auth_header.startswith("Bearer "):
                    return JSONResponse(
                        {"error": "Missing or invalid Authorization header"},
                        status_code=401
                    )

                token = auth_header.replace("Bearer ", "")

                if token != MCP_API_TOKEN:
                    return JSONResponse(
                        {"error": "Invalid token"},
                        status_code=403
                    )

        # Check UI authentication (including /logout)
        if request.url.path.startswith("/ui") or request.url.path.startswith("/api/") or request.url.path == "/logout":
            session_id = request.cookies.get("session_id")

            if session_id not in authenticated_sessions:
                return RedirectResponse(url="/login", status_code=302)

        return await call_next(request)

# ============= LOGIN ROUTE =============

@mcp.custom_route("/login", methods=["GET", "POST"])
async def login(request: Any) -> Union[HTMLResponse, RedirectResponse]:
    """Simple login page"""
    if request.method == "POST":
        form = await request.form()
        password = form.get("password")

        if password == UI_PASSWORD:
            # Create session
            session_id = os.urandom(16).hex()
            authenticated_sessions.add(session_id)

            response = RedirectResponse(url="/ui", status_code=302)
            response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
            return response
        else:
            return HTMLResponse("""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Login - MCP Aggregator</title>
                <script src="https://cdn.tailwindcss.com"></script>
            </head>
            <body class="bg-gray-50 min-h-screen flex items-center justify-center">
                <div class="bg-white rounded-lg shadow-md p-8 max-w-md w-full">
                    <h1 class="text-3xl font-bold text-gray-900 mb-6">MCP Aggregator</h1>
                    <form method="post">
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">Password</label>
                            <input type="password" name="password" required
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500">
                        </div>
                        <button type="submit"
                                class="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition">
                            Login
                        </button>
                    </form>
                    <p class="text-red-600 mt-4 text-center font-semibold">Invalid password</p>
                </div>
            </body>
            </html>
            """)

    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login - MCP Aggregator</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50 min-h-screen flex items-center justify-center">
        <div class="bg-white rounded-lg shadow-md p-8 max-w-md w-full">
            <h1 class="text-3xl font-bold text-gray-900 mb-6">MCP Aggregator</h1>
            <form method="post">
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Password</label>
                    <input type="password" name="password" required
                           class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <button type="submit"
                        class="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition">
                    Login
                </button>
            </form>
        </div>
    </body>
    </html>
    """)

# ============= WEB UI ROUTES =============

@mcp.custom_route("/ui", methods=["GET"])
async def home(request: Any) -> HTMLResponse:
    """Render the main UI"""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MCP Aggregator</title>
        <script src="https://unpkg.com/htmx.org@1.9.10"></script>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50 min-h-screen">
        <div class="container mx-auto px-4 py-8 max-w-7xl">
            <div class="flex justify-between items-center mb-8">
                <h1 class="text-4xl font-bold text-gray-900">🔗 MCP Aggregator</h1>
                <a href="/logout" class="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700">Logout</a>
            </div>

            <!-- Server List -->
            <div class="bg-white rounded-lg shadow-md p-6 mb-6">
                <h2 class="text-2xl font-semibold mb-4">Connected Servers</h2>
                <div id="server-list" hx-get="/api/servers" hx-trigger="load, serverUpdate from:body" hx-swap="innerHTML">
                    Loading...
                </div>
            </div>

            <!-- Add Server Forms -->
            <div class="grid md:grid-cols-3 gap-6">
                <!-- HTTP Server Form -->
                <div class="bg-white rounded-lg shadow-md p-6">
                    <h3 class="text-xl font-semibold mb-4 text-blue-700">Add HTTP Server</h3>
                    <form hx-post="/api/servers/http" hx-target="#result" hx-swap="innerHTML">
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">Name</label>
                            <input type="text" name="name" required
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                   placeholder="my-server">
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">URL</label>
                            <input type="url" name="url" required
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                   placeholder="https://example.com/mcp">
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">Bearer Token (optional)</label>
                            <input type="text" name="auth_token"
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                   placeholder="token or $ENV_VAR_NAME">
                            <p class="text-xs text-gray-500 mt-1">Use $VAR_NAME to reference environment variables</p>
                        </div>
                        <button type="submit"
                                class="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition">
                            Add HTTP Server
                        </button>
                    </form>
                </div>

                <!-- Stdio Server Form -->
                <div class="bg-white rounded-lg shadow-md p-6">
                    <h3 class="text-xl font-semibold mb-4 text-green-700">Add Stdio Server</h3>
                    <form hx-post="/api/servers/stdio" hx-target="#result" hx-swap="innerHTML">
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">Name</label>
                            <input type="text" name="name" required
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                                   placeholder="my-node-server">
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">Command</label>
                            <input type="text" name="command" required
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                                   placeholder="npx">
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">Args (comma-separated)</label>
                            <input type="text" name="args" required
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                                   placeholder="-y,@upstash/context7-mcp">
                        </div>
                        <button type="submit"
                                class="w-full bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 transition">
                            Add Stdio Server
                        </button>
                    </form>
                </div>

                <!-- Service Server Form -->
                <div class="bg-white rounded-lg shadow-md p-6">
                    <h3 class="text-xl font-semibold mb-4 text-purple-700">Add Service Server</h3>
                    <form hx-post="/api/servers/service" hx-target="#result" hx-swap="innerHTML">
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">Name</label>
                            <input type="text" name="name" required
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                                   placeholder="my-service">
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">Command</label>
                            <input type="text" name="command" required
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                                   placeholder="uvx">
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">Args (comma-separated)</label>
                            <input type="text" name="args" required
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                                   placeholder="--from,git+https://...">
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">Port</label>
                            <input type="number" name="port" required
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                                   placeholder="9121">
                        </div>
                        <button type="submit"
                                class="w-full bg-purple-600 text-white py-2 px-4 rounded-md hover:bg-purple-700 transition">
                            Add Service Server
                        </button>
                    </form>
                </div>
            </div>

            <!-- Result Messages -->
            <div id="result" class="mt-6"></div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(html)

@mcp.custom_route("/logout", methods=["GET"])
async def logout(request: Any) -> RedirectResponse:
    """Logout and clear session"""
    session_id = request.cookies.get("session_id")
    if session_id in authenticated_sessions:
        authenticated_sessions.remove(session_id)

    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session_id")
    return response

@mcp.custom_route("/api/servers", methods=["GET"])
async def get_servers(request: Any) -> HTMLResponse:
    """Return HTML fragment with server list"""
    all_servers: list[dict[str, Any]] = []

    # Add HTTP servers
    for name, config in upstream.http_servers.items():
        tools_count = len(upstream.tools_cache.get(name, []))
        auth_indicator = "🔐" if config.get("auth_token") else ""
        all_servers.append({
            "name": name,
            "type": "HTTP",
            "config": str(config.get("url", "")),
            "auth": auth_indicator,
            "tools": tools_count,
            "status": ""
        })

    # Add stdio servers
    for name, config in upstream.stdio_servers.items():
        tools_count = len(upstream.tools_cache.get(name, []))
        args_list = config.get('args', [])
        if isinstance(args_list, list):
            config_str = f"{config['command']} {' '.join(str(arg) for arg in args_list)}"
        else:
            config_str = f"{config['command']}"
        all_servers.append({
            "name": name,
            "type": "Stdio",
            "config": config_str,
            "auth": "",
            "tools": tools_count,
            "status": ""
        })

    # Add service servers
    for name, config in upstream.service_servers.items():
        tools_count = len(upstream.tools_cache.get(name, []))

        # Check if process is actually running
        if name in upstream.background_processes:
            process = upstream.background_processes[name]
            if process.poll() is None:  # Still running
                status = "🟢 Running"
            else:
                status = "🔴 Crashed"
        else:
            status = "⚪ Not Started"

        args_list = config.get('args', [])
        if isinstance(args_list, list):
            config_str = f"{config['command']} {' '.join(str(arg) for arg in args_list)} (port {config['port']})"
        else:
            config_str = f"{config['command']} (port {config['port']})"
        all_servers.append({
            "name": name,
            "type": "Service",
            "config": config_str,
            "auth": "",
            "tools": tools_count,
            "status": status
        })

    if not all_servers:
        return HTMLResponse('<p class="text-gray-500">No servers configured</p>')

    html = '<div class="space-y-3">'
    for server in all_servers:
        type_color = {
            "HTTP": "bg-blue-100 text-blue-800",
            "Stdio": "bg-green-100 text-green-800",
            "Service": "bg-purple-100 text-purple-800"
        }.get(server["type"], "bg-gray-100 text-gray-800")

        html += f'''
        <div class="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition">
            <div class="flex-1">
                <div class="flex items-center gap-3 flex-wrap">
                    <span class="font-semibold text-lg">{server["name"]}</span>
                    <span class="px-2 py-1 text-xs rounded-full {type_color}">
                        {server["type"]}
                    </span>
                    {f'<span class="text-lg">{server["auth"]}</span>' if server["auth"] else ''}
                    {f'<span class="text-sm font-medium">{server["status"]}</span>' if server["status"] else ''}
                    <span class="text-sm text-gray-600 font-medium">{server["tools"]} tools</span>
                </div>
                <p class="text-sm text-gray-600 mt-1 break-all">{server["config"]}</p>
            </div>
            <button hx-delete="/api/servers/{server["name"]}"
                    hx-target="#result"
                    hx-confirm="Are you sure you want to remove {server["name"]}?"
                    class="ml-4 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition flex-shrink-0">
                Remove
            </button>
        </div>
        '''
    html += '</div>'

    return HTMLResponse(html)

@mcp.custom_route("/api/servers/http", methods=["POST"])
async def add_http_server(request: Any) -> HTMLResponse:
    """Add a new HTTP server"""
    form = await request.form()
    name = form.get("name")
    url = form.get("url")
    auth_token = form.get("auth_token") or None

    try:
        upstream.add_http_server(str(name), str(url), auth_token)
        # Trigger tool discovery
        await setup_upstream_tools()

        html = f'''
        <div class="p-4 bg-green-100 border border-green-400 text-green-700 rounded-md"
             hx-trigger="load"
             hx-get="/api/trigger-update">
            ✅ HTTP server "{name}" added successfully!
        </div>
        '''
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f'<div class="p-4 bg-red-100 border border-red-400 text-red-700 rounded-md">❌ Error: {str(e)}</div>')

@mcp.custom_route("/api/servers/stdio", methods=["POST"])
async def add_stdio_server(request: Any) -> HTMLResponse:
    """Add a new stdio server"""
    form = await request.form()
    name = form.get("name")
    command = form.get("command")
    args_str = form.get("args", "")
    args = [arg.strip() for arg in str(args_str).split(",") if arg.strip()]

    try:
        upstream.add_stdio_server(str(name), str(command), args)
        # Trigger tool discovery
        await setup_upstream_tools()

        html = f'''
        <div class="p-4 bg-green-100 border border-green-400 text-green-700 rounded-md"
             hx-trigger="load"
             hx-get="/api/trigger-update">
            ✅ Stdio server "{name}" added successfully!
        </div>
        '''
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f'<div class="p-4 bg-red-100 border border-red-400 text-red-700 rounded-md">❌ Error: {str(e)}</div>')

@mcp.custom_route("/api/servers/service", methods=["POST"])
async def add_service_server(request: Any) -> HTMLResponse:
    """Add a new service server"""
    form = await request.form()
    name = form.get("name")
    command = form.get("command")
    args_str = form.get("args", "")
    args = [arg.strip() for arg in str(args_str).split(",") if arg.strip()]
    port = int(form.get("port", 9121))

    try:
        upstream.add_service_server(str(name), str(command), args, port)
        # Trigger tool discovery (this will start the service)
        await setup_upstream_tools()

        html = f'''
        <div class="p-4 bg-green-100 border border-green-400 text-green-700 rounded-md"
             hx-trigger="load"
             hx-get="/api/trigger-update">
            ✅ Service server "{name}" added successfully and started!
        </div>
        '''
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f'<div class="p-4 bg-red-100 border border-red-400 text-red-700 rounded-md">❌ Error: {str(e)}</div>')

@mcp.custom_route("/api/servers/{name}", methods=["DELETE"])
async def remove_server(request: Any) -> HTMLResponse:
    """Remove a server"""
    name = request.path_params["name"]

    try:
        upstream.remove_server(name)

        html = f'''
        <div class="p-4 bg-green-100 border border-green-400 text-green-700 rounded-md"
             hx-trigger="load"
             hx-get="/api/trigger-update">
            ✅ Server "{name}" removed successfully! (Restart to remove tools)
        </div>
        '''
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f'<div class="p-4 bg-red-100 border border-red-400 text-red-700 rounded-md">❌ Error: {str(e)}</div>')

@mcp.custom_route("/api/trigger-update", methods=["GET"])
async def trigger_update(request: Any) -> HTMLResponse:
    """Trigger server list update"""
    return HTMLResponse('<script>document.body.dispatchEvent(new Event("serverUpdate"))</script>')

if __name__ == "__main__":
    import asyncio
    from starlette.middleware import Middleware

    # Setup upstream tools before running
    asyncio.run(setup_upstream_tools())

    # Create middleware list
    middleware = [
        Middleware(AuthMiddleware)
    ]

    # Create the HTTP app with middleware
    app = mcp.http_app(middleware=middleware)

    # Run with uvicorn
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3050)