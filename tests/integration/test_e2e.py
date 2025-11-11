# tests/integration/test_e2e.py
"""End-to-end integration tests for UpstreamManager"""
import pytest
import time
from typing import Generator
from src.upstream.manager import UpstreamManager
from src.upstream.schemas import ServiceServerConfig


@pytest.fixture
def integration_manager() -> Generator[UpstreamManager, None, None]:
    """Create a fresh UpstreamManager for integration tests"""
    manager = UpstreamManager()
    manager.http_servers.clear()
    manager.stdio_servers.clear()
    manager.service_servers.clear()
    yield manager
    # Cleanup
    manager.cleanup_all_processes()


class TestUpstreamManagerIntegration:
    """Integration tests for UpstreamManager with real servers"""

    def test_add_and_list_servers(self, integration_manager: UpstreamManager) -> None:
        """Test adding servers and listing them"""
        # Add HTTP server
        integration_manager.add_http_server(
            "http_test",
            "https://api.example.com/mcp",
            auth_token="test_token"
        )
        
        # Add stdio server
        integration_manager.add_stdio_server(
            "stdio_test",
            "node",
            ["server.js"]
        )
        
        # List all servers
        all_servers = integration_manager.list_all_servers()
        
        assert len(all_servers) == 2
        assert "http_test" in all_servers
        assert "stdio_test" in all_servers
        assert all_servers["http_test"]["type"] == "http"
        assert all_servers["stdio_test"]["type"] == "stdio"

    def test_remove_server_cleanup(self, integration_manager: UpstreamManager) -> None:
        """Test that removing servers properly cleans up"""
        integration_manager.add_http_server("cleanup_test", "https://example.com/mcp")
        integration_manager.add_stdio_server("cleanup_test2", "node", ["server.js"])
        
        assert len(integration_manager.list_all_servers()) == 2
        
        integration_manager.remove_server("cleanup_test")
        assert len(integration_manager.list_all_servers()) == 1
        
        integration_manager.remove_server("cleanup_test2")
        assert len(integration_manager.list_all_servers()) == 0

    def test_service_server_startup_and_health_check(self, integration_manager: UpstreamManager) -> None:
        """Test starting a real service and health check"""
        # Use a simple HTTP server for testing
        config = ServiceServerConfig(
            command="python",
            args=["-m", "http.server", "9999", "--bind", "127.0.0.1"],
            port=9999,
            health_check_path="/",
            startup_timeout=10
        )
        
        result = integration_manager._start_service("http_server_test", config)
        
        try:
            # Give it a moment to start
            time.sleep(0.5)
            
            # Verify process is running
            assert result is True
            assert "http_server_test" in integration_manager.background_processes
            
            process = integration_manager.background_processes["http_server_test"]
            assert process.poll() is None  # Process still running
            
        finally:
            # Cleanup
            integration_manager.remove_server("http_server_test")

    def test_multiple_service_servers(self, integration_manager: UpstreamManager) -> None:
        """Test managing multiple service servers"""
        configs = [
            ServiceServerConfig(
                command="python",
                args=["-m", "http.server", "9990", "--bind", "127.0.0.1"],
                port=9990,
                health_check_path="/",
                startup_timeout=10
            ),
            ServiceServerConfig(
                command="python",
                args=["-m", "http.server", "9991", "--bind", "127.0.0.1"],
                port=9991,
                health_check_path="/",
                startup_timeout=10
            ),
        ]
        
        # Start both servers
        result1 = integration_manager._start_service("server1", configs[0])
        result2 = integration_manager._start_service("server2", configs[1])
        
        try:
            assert result1 is True
            assert result2 is True
            
            # Verify both are running
            all_servers = integration_manager.list_all_servers()
            assert len(all_servers) == 2
            
        finally:
            # Cleanup
            integration_manager.cleanup_all_processes()

    def test_service_server_with_env_vars(self, integration_manager: UpstreamManager) -> None:
        """Test service server with environment variables"""
        config = ServiceServerConfig(
            command="python",
            args=["-m", "http.server", "9992", "--bind", "127.0.0.1"],
            port=9992,
            health_check_path="/",
            startup_timeout=10,
            env={"PYTHONUNBUFFERED": "1"}
        )
        
        result = integration_manager._start_service("env_test", config)
        
        try:
            assert result is True
            assert "env_test" in integration_manager.background_processes
        finally:
            integration_manager.remove_server("env_test")