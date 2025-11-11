# main.py (UPDATED - PASS UPSTREAM TO UI ROUTES)
import logging
from pathlib import Path
from fastmcp import FastMCP

from src.config import config
from src.auth.service import AuthService
from src.auth.middleware import AuthMiddleware
from src.upstream.manager import UpstreamManager
from src.tools.registry import register_upstream_tools
from src.lifecycle.cleanup import setup_cleanup_handlers
from src.api.routes import register_api_routes
from src.ui.routes import register_ui_routes
from starlette.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

# Initialize components
mcp = FastMCP("MCP Aggregator")
upstream = UpstreamManager()
auth_service = AuthService(config.UI_PASSWORD)

# Register cleanup handlers
setup_cleanup_handlers(upstream)

# Register routes (pass upstream to UI routes)
register_ui_routes(mcp, auth_service, upstream)
register_api_routes(mcp, upstream, auth_service)

@mcp.tool
def hello_world() -> str:
    """Say hello to the world"""
    return "Hello, World!"

async def main() -> AuthMiddleware:
    """Initialize and run the application"""
    logger.info("🚀 Starting MCP Aggregator...")
    
    # Setup upstream tools
    await register_upstream_tools(mcp, upstream)
    
    # Create HTTP app first without middleware
    app = mcp.http_app()
    
    static_dir = Path(__file__).parent / "src" / "ui" / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Manually wrap the app with middleware
    app = AuthMiddleware(app, auth_service=auth_service)
    
    # Return the app (don't run uvicorn here)
    return app

if __name__ == "__main__":
    import asyncio
    import uvicorn
    
        # Get the app from async context
    app = asyncio.run(main())
    
    # Now run uvicorn outside of asyncio.run()
    logger.info(f"🌐 Server starting on {config.HOST}:{config.PORT}")
    uvicorn.run(app, host=config.HOST, port=config.PORT)