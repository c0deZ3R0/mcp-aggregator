# tests/conftest.py
import pytest
import asyncio
from typing import Generator, Any
from unittest.mock import MagicMock


from src.auth.service import AuthService
from src.upstream.manager import UpstreamManager


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