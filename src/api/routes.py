# src/api/routes.py
from typing import Any
from starlette.responses import HTMLResponse
from fastmcp import FastMCP

from src.upstream.manager import UpstreamManager
from src.exceptions import ServerConfigError

def register_api_routes(mcp: FastMCP, upstream: UpstreamManager) -> None:
    """Register API endpoints"""

    @mcp.custom_route("/api/servers", methods=["GET"])
    async def get_servers(request: Any) -> HTMLResponse:
        """Return HTML fragment with server list"""
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
                        <span class="px-2 py-1 text-xs rounded-full {type_color}">{server["type"]}</span>
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
            from src.tools.registry import register_upstream_tools
            await register_upstream_tools(mcp, upstream)

            return HTMLResponse(f'''
            <div class="p-4 bg-green-100 border border-green-400 text-green-700 rounded-md"
                 hx-trigger="load"
                 hx-get="/api/trigger-update">
                ✅ HTTP server "{name}" added successfully!
            </div>
            ''')
        except ServerConfigError as e:
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
            from src.tools.registry import register_upstream_tools
            await register_upstream_tools(mcp, upstream)

            return HTMLResponse(f'''
            <div class="p-4 bg-green-100 border border-green-400 text-green-700 rounded-md"
                 hx-trigger="load"
                 hx-get="/api/trigger-update">
                ✅ Stdio server "{name}" added successfully!
            </div>
            ''')
        except ServerConfigError as e:
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
            from src.tools.registry import register_upstream_tools
            await register_upstream_tools(mcp, upstream)

            return HTMLResponse(f'''
            <div class="p-4 bg-green-100 border border-green-400 text-green-700 rounded-md"
                 hx-trigger="load"
                 hx-get="/api/trigger-update">
                ✅ Service server "{name}" added successfully and started!
            </div>
            ''')
        except ServerConfigError as e:
            return HTMLResponse(f'<div class="p-4 bg-red-100 border border-red-400 text-red-700 rounded-md">❌ Error: {str(e)}</div>')

    @mcp.custom_route("/api/servers/{name}", methods=["DELETE"])
    async def remove_server(request: Any) -> HTMLResponse:
        """Remove a server"""
        name = request.path_params["name"]

        try:
            upstream.remove_server(name)

            return HTMLResponse(f'''
            <div class="p-4 bg-green-100 border border-green-400 text-green-700 rounded-md"
                 hx-trigger="load"
                 hx-get="/api/trigger-update">
                ✅ Server "{name}" removed successfully!
            </div>
            ''')
        except Exception as e:
            return HTMLResponse(f'<div class="p-4 bg-red-100 border border-red-400 text-red-700 rounded-md">❌ Error: {str(e)}</div>')

    @mcp.custom_route("/api/trigger-update", methods=["GET"])
    async def trigger_update(request: Any) -> HTMLResponse:
        """Trigger server list update"""
        return HTMLResponse('<script>document.body.dispatchEvent(new Event("serverUpdate"))</script>')