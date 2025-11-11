# src/ui/routes.py
from typing import Any, Union
from starlette.responses import HTMLResponse, RedirectResponse
from fastmcp import FastMCP

from src.auth.service import AuthService

def register_ui_routes(mcp: FastMCP, auth_service: AuthService) -> None:
    """Register UI endpoints"""

    @mcp.custom_route("/login", methods=["GET", "POST"])
    async def login(request: Any) -> Union[HTMLResponse, RedirectResponse]:
        """Simple login page"""
        if request.method == "POST":
            form = await request.form()
            password = form.get("password")

            if auth_service.verify_password(password):
                session_id = auth_service.create_session()
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
        auth_service.invalidate_session(session_id)

        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("session_id")
        return response