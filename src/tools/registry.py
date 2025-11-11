# src/tools/registry.py
import threading
import logging
from fastmcp import FastMCP
from src.upstream.manager import UpstreamManager
from src.tools.factory import create_upstream_tool_wrapper

logger = logging.getLogger(__name__)

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

                mcp.tool(
                    wrapper,
                    name=prefixed_name,
                    description=f"[{server_name}] {description}"
                )
        except Exception as e:
            logger.error(f"Failed to process server {server_name}: {e}")

    logger.info("✅ Tool discovery complete!")