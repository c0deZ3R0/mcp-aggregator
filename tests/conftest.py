# tests/conftest.py (UPDATE test_client fixture)
import pytest
import asyncio
from typing import Generator, Any
from unittest.mock import MagicMock
from pathlib import Path
import sys
from src.auth.service import AuthService
from src.upstream.manager import UpstreamManager

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))




@pytest.fixture(scope="session")
def event_loop() -> Generator[Any, None, None]:
    """Create an event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def auth_service() -> AuthService:
    """Create a fresh AuthService instance for testing"""
    return AuthService(ui_password="test_password")


@pytest.fixture
def upstream_manager() -> UpstreamManager:
    """Create a fresh UpstreamManager instance for testing"""
    return UpstreamManager()


@pytest.fixture
def mock_http_client() -> MagicMock:
    """Mock HTTP client for external requests"""
    return MagicMock()


@pytest.fixture
def mock_subprocess() -> MagicMock:
    """Mock subprocess for service management"""
    return MagicMock()


@pytest.fixture
async def test_client():
    """Create test client with authentication bypassed for testing"""
    from httpx import ASGITransport, AsyncClient
    from fastmcp import FastMCP
    from src.config import config
    from src.api.routes import register_api_routes
    
    # Create fresh instances for testing
    mcp = FastMCP("Test MCP Aggregator")
    upstream = UpstreamManager()
    auth_service_instance = AuthService(config.UI_PASSWORD)
    
    # Register routes
    register_api_routes(mcp, upstream, auth_service_instance)
    
    # Get the raw app without auth middleware for testing
    app = mcp.http_app()
    
    # Create client with ASGI transport (correct way for httpx)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client