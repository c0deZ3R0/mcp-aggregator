# src/tools/registry.py (UPDATED - WITH TRACKING)
import threading
import logging
from typing import Any
from fastmcp import FastMCP
from src.upstream.manager import UpstreamManager
from src.tools.factory import create_upstream_tool_wrapper

logger = logging.getLogger(__name__)

# Global registry to track all tools
_tools_registry: dict[str, dict[str, Any]] = {}

def register_tool(name: str, description: str = "", input_schema: dict[str, Any] | None = None) -> None:
    """Register a tool in the global registry"""
    _tools_registry[name] = {
        "name": name,
        "description": description,
        "inputSchema": input_schema or {}
    }

def get_all_tools() -> list[dict[str, Any]]:
    """Get all registered tools"""
    return list(_tools_registry.values())

def clear_tools() -> None:
    """Clear the registry"""
    _tools_registry.clear()

async def register_upstream_tools(mcp: FastMCP, upstream: UpstreamManager) -> None:
    """Discover and register all upstream tools"""
    logger.info("🚀 Starting tool discovery...")

    # Start background services
    logger.info("📦 Starting background services...")
    service_threads: list[tuple[str, threading.Thread]] = []
    for service_name in list(upstream.service_servers.keys()):
        config = upstream.service_servers[service_name]
        if service_name not in upstream.background_processes:
            thread = threading.Thread(
                target=upstream._start_service,
                args=(service_name, config),
                daemon=True
            )
            thread.start()
            service_threads.append((service_name, thread))

    for service_name, thread in service_threads:
        thread.join(timeout=35)
        if thread.is_alive():
            logger.warning(f"Service {service_name} is still starting...")

    # Discover and register tools
    all_servers = (list(upstream.http_servers.keys()) +
                   list(upstream.stdio_servers.keys()) +
                   list(upstream.service_servers.keys()))

    for server_name in all_servers:
        logger.info(f"📡 Processing server: {server_name}")
        try:
            tools = await upstream.discover_tools(server_name)
            logger.info(f"📝 Registering {len(tools)} tools from {server_name}")

            for tool_info in tools:
                tool_name = tool_info.get("name", "unknown")
                description = tool_info.get("description", "Upstream tool")
                input_schema = tool_info.get("inputSchema", {})

                wrapper = create_upstream_tool_wrapper(upstream, server_name, tool_name, input_schema)
                prefixed_name = f"{server_name}_{tool_name}"
                logger.info(f"   ✓ Registering: {prefixed_name}")

                # Register in FastMCP
                mcp.tool(
                    wrapper,
                    name=prefixed_name,
                    description=f"[{server_name}] {description}"
                )
                
                # Track in our registry
                register_tool(
                    name=prefixed_name,
                    description=f"[{server_name}] {description}",
                    input_schema=input_schema
                )
        except Exception as e:
            logger.error(f"Failed to process server {server_name}: {e}")

    logger.info("✅ Tool discovery complete!")