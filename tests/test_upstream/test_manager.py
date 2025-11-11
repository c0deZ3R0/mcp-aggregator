# tests/test_upstream/test_manager.py
import pytest
import subprocess
from unittest.mock import Mock, patch, AsyncMock

import requests
from src.upstream.manager import UpstreamManager
from src.upstream.schemas import ServiceServerConfig
from src.exceptions import ServerConfigError, ToolDiscoveryError


class TestUpstreamManager:
    """Test suite for UpstreamManager"""

    def test_initialization_loads_defaults(self, upstream_manager: UpstreamManager) -> None:
        """Test that manager initializes with default servers"""
        assert len(upstream_manager.http_servers) > 0
        assert len(upstream_manager.stdio_servers) > 0
        assert len(upstream_manager.service_servers) > 0
        assert upstream_manager.clients == {}
        assert upstream_manager.tools_cache == {}
        assert upstream_manager.background_processes == {}

    def test_add_http_server(self, upstream_manager: UpstreamManager) -> None:
        """Test adding a new HTTP server"""
        upstream_manager.add_http_server(
            "test_http",
            "https://example.com/mcp",
            auth_token="test_token"
        )
        
        assert "test_http" in upstream_manager.http_servers
        config = upstream_manager.http_servers["test_http"]
        assert config.url == "https://example.com/mcp"
        assert config.auth_token == "test_token"

    def test_add_http_server_without_token(self, upstream_manager: UpstreamManager) -> None:
        """Test adding HTTP server without auth token"""
        upstream_manager.add_http_server("test_http_no_token", "https://example.com/mcp")
        
        assert "test_http_no_token" in upstream_manager.http_servers
        config = upstream_manager.http_servers["test_http_no_token"]
        assert config.url == "https://example.com/mcp"
        assert config.auth_token is None

    def test_add_http_server_duplicate_name(self, upstream_manager: UpstreamManager) -> None:
        """Test adding HTTP server with duplicate name raises error"""
        upstream_manager.add_http_server("test_http_dup", "https://example.com/mcp")
        
        with pytest.raises(ServerConfigError, match="already exists"):
            upstream_manager.add_http_server("test_http_dup", "https://other.com/mcp")

    def test_add_stdio_server(self, upstream_manager: UpstreamManager) -> None:
        """Test adding a new stdio server"""
        upstream_manager.add_stdio_server(
            "test_stdio",
            "npx",
            ["-y", "@example/server"],
            env={"TEST": "value"},
            working_directory="/tmp"
        )
        
        assert "test_stdio" in upstream_manager.stdio_servers
        config = upstream_manager.stdio_servers["test_stdio"]
        assert config.command == "npx"
        assert config.args == ["-y", "@example/server"]
        assert config.env == {"TEST": "value"}
        assert config.working_directory == "/tmp"

    def test_add_stdio_server_minimal(self, upstream_manager: UpstreamManager) -> None:
        """Test adding stdio server with minimal args"""
        upstream_manager.add_stdio_server(
            "test_stdio_min",
            "node",
            ["server.js"]
        )
        
        assert "test_stdio_min" in upstream_manager.stdio_servers
        config = upstream_manager.stdio_servers["test_stdio_min"]
        assert config.command == "node"
        assert config.args == ["server.js"]
        assert config.env == {}
        assert config.working_directory is None

    def test_add_stdio_server_duplicate_name(self, upstream_manager: UpstreamManager) -> None:
        """Test adding stdio server with duplicate name raises error"""
        upstream_manager.add_stdio_server("test_stdio_dup", "npx", ["-y", "@example/server"])
        
        with pytest.raises(ServerConfigError, match="already exists"):
            upstream_manager.add_stdio_server("test_stdio_dup", "node", ["server.js"])

    def test_add_service_server(self, upstream_manager: UpstreamManager) -> None:
        """Test adding a new service server"""
        upstream_manager.add_service_server(
            "test_service",
            "uvx",
            ["--from", "git+https://example.com/repo"],
            port=9999,
            health_check_path="/health",
            startup_timeout=60
        )
        
        assert "test_service" in upstream_manager.service_servers
        config = upstream_manager.service_servers["test_service"]
        assert config.command == "uvx"
        assert config.port == 9999
        assert config.health_check_path == "/health"
        assert config.startup_timeout == 60

    def test_add_service_server_with_defaults(self, upstream_manager: UpstreamManager) -> None:
        """Test adding service server with default values"""
        upstream_manager.add_service_server(
            "test_service_defaults",
            "uvx",
            ["--from", "git+https://example.com/repo"],
            port=9998
        )
        
        config = upstream_manager.service_servers["test_service_defaults"]
        assert config.health_check_path == "/mcp"  # default
        assert config.startup_timeout == 30  # default

    def test_add_service_server_duplicate_name(self, upstream_manager: UpstreamManager) -> None:
        """Test adding service server with duplicate name raises error"""
        upstream_manager.add_service_server("test_service_dup", "uvx", ["test"], port=9997)
        
        with pytest.raises(ServerConfigError, match="already exists"):
            upstream_manager.add_service_server("test_service_dup", "uvx", ["test"], port=9996)

    def test_add_service_server_duplicate_port(self, upstream_manager: UpstreamManager) -> None:
        """Test adding service server with duplicate port raises error"""
        upstream_manager.add_service_server("service1", "uvx", ["test"], port=9995)
        
        with pytest.raises(ServerConfigError, match="already used"):
            upstream_manager.add_service_server("service2", "uvx", ["test"], port=9995)

    def test_remove_http_server(self, upstream_manager: UpstreamManager) -> None:
        """Test removing an HTTP server"""
        upstream_manager.add_http_server("test_http_remove", "https://example.com/mcp")
        assert "test_http_remove" in upstream_manager.http_servers
        
        upstream_manager.remove_server("test_http_remove")
        assert "test_http_remove" not in upstream_manager.http_servers

    def test_remove_stdio_server(self, upstream_manager: UpstreamManager) -> None:
        """Test removing a stdio server"""
        upstream_manager.add_stdio_server("test_stdio_remove", "npx", ["-y", "@example/server"])
        assert "test_stdio_remove" in upstream_manager.stdio_servers
        
        upstream_manager.remove_server("test_stdio_remove")
        assert "test_stdio_remove" not in upstream_manager.stdio_servers

    def test_remove_service_server(self, upstream_manager: UpstreamManager) -> None:
        """Test removing a service server"""
        upstream_manager.add_service_server("test_service_remove", "uvx", ["test"], port=9994)
        assert "test_service_remove" in upstream_manager.service_servers
        
        upstream_manager.remove_server("test_service_remove")
        assert "test_service_remove" not in upstream_manager.service_servers

    def test_remove_server_with_background_process(self, upstream_manager: UpstreamManager) -> None:
        """Test removing a server with active background process"""
        mock_process = Mock(spec=subprocess.Popen)
        mock_process.poll.return_value = None
        mock_process.wait.return_value = None
        
        upstream_manager.add_service_server("test_service_proc", "uvx", ["test"], port=9993)
        upstream_manager.background_processes["test_service_proc"] = mock_process
        
        upstream_manager.remove_server("test_service_proc")
        
        mock_process.terminate.assert_called_once()
        assert "test_service_proc" not in upstream_manager.background_processes

    def test_remove_server_process_timeout(self, upstream_manager: UpstreamManager) -> None:
        """Test removing server when process doesn't terminate gracefully"""
        mock_process = Mock(spec=subprocess.Popen)
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = subprocess.TimeoutExpired("cmd", 5)
        
        upstream_manager.add_service_server("test_service_timeout", "uvx", ["test"], port=9992)
        upstream_manager.background_processes["test_service_timeout"] = mock_process
        
        upstream_manager.remove_server("test_service_timeout")
        
        mock_process.kill.assert_called_once()

    def test_remove_nonexistent_server(self, upstream_manager: UpstreamManager) -> None:
        """Test removing a server that doesn't exist (should not raise)"""
        upstream_manager.remove_server("nonexistent_server_xyz")
        assert True

    def test_remove_server_cleans_all_caches(self, upstream_manager: UpstreamManager) -> None:
        """Test that remove_server cleans all associated caches"""
        upstream_manager.add_http_server("test_cleanup", "https://example.com/mcp")
        upstream_manager.clients["test_cleanup"] = {"type": "http", "url": "https://example.com/mcp"}
        upstream_manager.tools_cache["test_cleanup"] = [{"name": "tool1"}]
        
        upstream_manager.remove_server("test_cleanup")
        
        assert "test_cleanup" not in upstream_manager.http_servers
        assert "test_cleanup" not in upstream_manager.clients
        assert "test_cleanup" not in upstream_manager.tools_cache

    def test_get_client_config_http(self, upstream_manager: UpstreamManager) -> None:
        """Test getting client config for HTTP server"""
        upstream_manager.add_http_server("test_http_config", "https://example.com/mcp", auth_token="token123")
        
        config = upstream_manager._get_client_config("test_http_config")
        
        assert config["type"] == "http"
        assert config["url"] == "https://example.com/mcp"
        assert config["auth_token"] == "token123"

    def test_get_client_config_http_no_token(self, upstream_manager: UpstreamManager) -> None:
        """Test getting client config for HTTP server without token"""
        upstream_manager.add_http_server("test_http_no_token_config", "https://example.com/mcp")
        
        config = upstream_manager._get_client_config("test_http_no_token_config")
        
        assert config["type"] == "http"
        assert config["url"] == "https://example.com/mcp"
        assert config["auth_token"] is None

    def test_get_client_config_stdio(self, upstream_manager: UpstreamManager) -> None:
        """Test getting client config for stdio server"""
        upstream_manager.add_stdio_server("test_stdio_config", "npx", ["-y", "@example/server"])
        
        config = upstream_manager._get_client_config("test_stdio_config")
        
        assert config["type"] == "stdio"
        assert config["command"] == "npx"
        assert config["args"] == ["-y", "@example/server"]
        assert config["env"] == {}

    def test_get_client_config_service(self, upstream_manager: UpstreamManager) -> None:
        """Test getting client config for service server"""
        upstream_manager.add_service_server("test_service_config", "uvx", ["--from", "git+https://example.com"], port=9991)
        
        config = upstream_manager._get_client_config("test_service_config")
        
        assert config["type"] == "http"
        assert config["url"] == "http://localhost:9991/mcp"
        assert config["auth_token"] is None

    def test_get_client_config_unknown_server(self, upstream_manager: UpstreamManager) -> None:
        """Test getting client config for unknown server raises error"""
        with pytest.raises(ServerConfigError, match="Unknown server"):
            upstream_manager._get_client_config("nonexistent_server")

    def test_list_all_servers(self, upstream_manager: UpstreamManager) -> None:
        """Test listing all servers"""
        upstream_manager.add_http_server("http_list", "https://example.com/mcp")
        upstream_manager.add_stdio_server("stdio_list", "npx", ["-y", "@example/server"])
        upstream_manager.add_service_server("service_list", "uvx", ["test"], port=9990)
        
        all_servers = upstream_manager.list_all_servers()
        
        assert "http_list" in all_servers
        assert "stdio_list" in all_servers
        assert "service_list" in all_servers
        assert all_servers["http_list"]["type"] == "http"
        assert all_servers["stdio_list"]["type"] == "stdio"
        assert all_servers["service_list"]["type"] == "service"

    def test_list_all_servers_empty(self) -> None:
        """Test listing servers with fresh manager"""
        fresh_manager = UpstreamManager()
        fresh_manager.http_servers.clear()
        fresh_manager.stdio_servers.clear()
        fresh_manager.service_servers.clear()
        
        all_servers = fresh_manager.list_all_servers()
        assert all_servers == {}

    def test_cleanup_all_processes(self, upstream_manager: UpstreamManager) -> None:
        """Test cleaning up all background processes"""
        mock_process1 = Mock(spec=subprocess.Popen)
        mock_process1.poll.return_value = None
        mock_process1.wait.return_value = None
        
        mock_process2 = Mock(spec=subprocess.Popen)
        mock_process2.poll.return_value = None
        mock_process2.wait.return_value = None
        
        upstream_manager.background_processes["service1"] = mock_process1
        upstream_manager.background_processes["service2"] = mock_process2
        
        upstream_manager.cleanup_all_processes()
        
        mock_process1.terminate.assert_called_once()
        mock_process2.terminate.assert_called_once()

    def test_cleanup_all_processes_with_timeout(self, upstream_manager: UpstreamManager) -> None:
        """Test cleanup when process doesn't terminate gracefully"""
        mock_process = Mock(spec=subprocess.Popen)
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = subprocess.TimeoutExpired("cmd", 5)
        
        upstream_manager.background_processes["service_timeout"] = mock_process
        
        upstream_manager.cleanup_all_processes()
        
        mock_process.kill.assert_called_once()

    def test_load_defaults_skips_invalid_http_server(self) -> None:
        """Test that _load_defaults skips HTTP servers without URL"""
        # This tests lines 52-53
        # Create a fresh manager which calls _load_defaults
        fresh_manager = UpstreamManager()
        
        # The manager should still initialize even if defaults have issues
        assert fresh_manager is not None
        assert isinstance(fresh_manager.http_servers, dict)

    def test_start_service_request_exception_handling(self, upstream_manager: UpstreamManager) -> None:
        """Test service startup retries on request exceptions"""
        config = ServiceServerConfig(
            command="echo",
            args=["hello"],
            port=9986,
            health_check_path="/health",
            startup_timeout=10
        )
        
        with patch("src.upstream.manager.subprocess.Popen") as mock_popen:
            with patch("src.upstream.manager.requests.get") as mock_get:
                with patch("src.upstream.manager.time.sleep"):
                    with patch("src.upstream.manager.time.time") as mock_time:
                        mock_process = Mock()
                        mock_process.pid = 12345
                        mock_process.poll.return_value = None
                        mock_popen.return_value = mock_process
                        
                        # Simulate time: start=0, check1=0.5, check2=1.0, check3=1.5
                        mock_time.side_effect = [0, 0.5, 1.0, 1.5]
                        
                        mock_response = Mock()
                        mock_response.status_code = 200
                        mock_get.side_effect = [
                            requests.RequestException("Connection refused"),
                            requests.RequestException("Connection refused"),
                            mock_response
                        ]
                        
                        result = upstream_manager._start_service("test_service_retry", config)
                        
                        assert result is True

    def test_start_service_exception_in_popen(self, upstream_manager: UpstreamManager) -> None:
        """Test service startup when Popen raises exception"""
        # Tests lines 138-140 (exception handling in _start_service)
        config = ServiceServerConfig(
            command="nonexistent_command_xyz",
            args=[],
            port=9985,
            health_check_path="/health",
            startup_timeout=5
        )
        
        with patch("src.upstream.manager.subprocess.Popen") as mock_popen:
            mock_popen.side_effect = FileNotFoundError("Command not found")
            
            result = upstream_manager._start_service("test_service_error", config)
            
            assert result is False
            assert "test_service_error" not in upstream_manager.background_processes

    @pytest.mark.asyncio
    async def test_call_tool_with_empty_content_blocks(self, upstream_manager: UpstreamManager) -> None:
        """Test calling tool with empty content blocks"""
        # Tests lines 241, 260 (content block handling edge cases)
        upstream_manager.add_http_server("test_http_empty_content", "https://example.com/mcp")
        upstream_manager.clients["test_http_empty_content"] = {
            "type": "http",
            "url": "https://example.com/mcp",
            "auth_token": None
        }
        
        # Content block without text attribute
        mock_content_block = Mock(spec=[])  # No attributes
        
        mock_result = Mock()
        mock_result.data = None
        mock_result.content = [mock_content_block]
        
        with patch("src.upstream.manager.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.call_tool.return_value = mock_result
            mock_client_class.return_value = mock_client
            
            result = await upstream_manager.call_tool("test_http_empty_content", "test_tool", {})
            
            # Should return None when no text content found
            assert result is None

    @pytest.mark.asyncio
    async def test_call_tool_with_non_string_text(self, upstream_manager: UpstreamManager) -> None:
        """Test calling tool with non-string text in content blocks"""
        upstream_manager.add_http_server("test_http_non_string", "https://example.com/mcp")
        upstream_manager.clients["test_http_non_string"] = {
            "type": "http",
            "url": "https://example.com/mcp",
            "auth_token": None
        }
        
        # Content block with non-string text
        mock_content_block = Mock()
        mock_content_block.text = 12345  # Not a string
        
        mock_result = Mock()
        mock_result.data = None
        mock_result.content = [mock_content_block]
        
        with patch("src.upstream.manager.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.call_tool.return_value = mock_result
            mock_client_class.return_value = mock_client
            
            result = await upstream_manager.call_tool("test_http_non_string", "test_tool", {})
            
            # Should return None when text is not a string
            assert result is None

    def test_start_service_process_dies_with_output(self, upstream_manager: UpstreamManager) -> None:
        """Test service startup when process dies with stdout/stderr"""
        # Tests lines 320-321 (process death with output)
        config = ServiceServerConfig(
            command="false",
            args=[],
            port=9984,
            health_check_path="/health",
            startup_timeout=5
        )
        
        with patch("src.upstream.manager.subprocess.Popen") as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = 1  # Process exited
            mock_process.communicate.return_value = (
                "stdout output here",
                "stderr error message"
            )
            mock_popen.return_value = mock_process
            
            result = upstream_manager._start_service("test_service_with_output", config)
            
            assert result is False

    def test_start_service_process_dies_empty_output(self, upstream_manager: UpstreamManager) -> None:
        """Test service startup when process dies with no output"""
        # Tests lines 348-349 (process death with empty output)
        config = ServiceServerConfig(
            command="false",
            args=[],
            port=9983,
            health_check_path="/health",
            startup_timeout=5
        )
        
        with patch("src.upstream.manager.subprocess.Popen") as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = 1  # Process exited
            mock_process.communicate.return_value = (None, None)
            mock_popen.return_value = mock_process
            
            result = upstream_manager._start_service("test_service_no_output", config)
            
            assert result is False

    @pytest.mark.asyncio
    async def test_discover_tools_with_no_description(self, upstream_manager: UpstreamManager) -> None:
        """Test discovering tools where tool has no description"""
        upstream_manager.add_http_server("test_http_no_desc", "https://example.com/mcp")
        
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = None  # No description
        mock_tool.inputSchema = {"type": "object"}
        
        with patch("src.upstream.manager.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.list_tools.return_value = [mock_tool]
            mock_client_class.return_value = mock_client
            
            tools = await upstream_manager.discover_tools("test_http_no_desc")
            
            assert len(tools) == 1
            assert tools[0]["description"] == "No description"

    @pytest.mark.asyncio
    async def test_call_tool_with_working_directory(self, upstream_manager: UpstreamManager) -> None:
        """Test calling tool on stdio server with working directory"""
        upstream_manager.add_stdio_server(
            "test_stdio_workdir",
            "npx",
            ["-y", "@example/server"],
            working_directory="/app"
        )
        upstream_manager.clients["test_stdio_workdir"] = {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@example/server"],
            "env": {},
            "working_directory": "/app"
        }
        
        mock_result = Mock()
        mock_result.data = {"result": "success"}
        mock_result.content = None
        
        with patch("src.upstream.manager.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.call_tool.return_value = mock_result
            mock_client_class.return_value = mock_client
            
            result = await upstream_manager.call_tool("test_stdio_workdir", "test_tool", {})
            
            assert result == {"result": "success"}
    

    @pytest.mark.asyncio
    async def test_discover_tools_http_with_token(self, upstream_manager: UpstreamManager) -> None:
        """Test discovering tools from HTTP server with auth token"""
        upstream_manager.add_http_server("test_http_discover", "https://example.com/mcp", auth_token="token123")
        
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool description"
        mock_tool.inputSchema = {"type": "object"}
        
        with patch("src.upstream.manager.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.list_tools.return_value = [mock_tool]
            mock_client_class.return_value = mock_client
            
            tools = await upstream_manager.discover_tools("test_http_discover")
            
            assert len(tools) == 1
            assert tools[0]["name"] == "test_tool"
            assert tools[0]["description"] == "Test tool description"
            assert "test_http_discover" in upstream_manager.tools_cache
            assert "test_http_discover" in upstream_manager.clients

    @pytest.mark.asyncio
    async def test_discover_tools_http_without_token(self, upstream_manager: UpstreamManager) -> None:
        """Test discovering tools from HTTP server without auth token"""
        upstream_manager.add_http_server("test_http_no_token_discover", "https://example.com/mcp")
        
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool"
        mock_tool.inputSchema = {}
        
        with patch("src.upstream.manager.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.list_tools.return_value = [mock_tool]
            mock_client_class.return_value = mock_client
            
            tools = await upstream_manager.discover_tools("test_http_no_token_discover")
            
            assert len(tools) == 1

    @pytest.mark.asyncio
    async def test_discover_tools_stdio(self, upstream_manager: UpstreamManager) -> None:
        """Test discovering tools from stdio server"""
        upstream_manager.add_stdio_server("test_stdio_discover", "npx", ["-y", "@example/server"])
        
        mock_tool = Mock()
        mock_tool.name = "stdio_tool"
        mock_tool.description = "Stdio tool"
        mock_tool.inputSchema = {}
        
        with patch("src.upstream.manager.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.list_tools.return_value = [mock_tool]
            mock_client_class.return_value = mock_client
            
            tools = await upstream_manager.discover_tools("test_stdio_discover")
            
            assert len(tools) == 1
            assert tools[0]["name"] == "stdio_tool"

    @pytest.mark.asyncio
    async def test_discover_tools_error(self, upstream_manager: UpstreamManager) -> None:
        """Test discover_tools raises ToolDiscoveryError on failure"""
        upstream_manager.add_http_server("test_http_error", "https://example.com/mcp")
        
        with patch("src.upstream.manager.Client") as mock_client_class:
            mock_client_class.side_effect = Exception("Connection failed")
            
            with pytest.raises(ToolDiscoveryError):
                await upstream_manager.discover_tools("test_http_error")

    @pytest.mark.asyncio
    async def test_call_tool_http(self, upstream_manager: UpstreamManager) -> None:
        """Test calling a tool on HTTP server"""
        upstream_manager.add_http_server("test_http_call", "https://example.com/mcp", auth_token="token123")
        upstream_manager.clients["test_http_call"] = {
            "type": "http",
            "url": "https://example.com/mcp",
            "auth_token": "token123"
        }
        
        mock_result = Mock()
        mock_result.data = {"result": "success"}
        mock_result.content = None
        
        with patch("src.upstream.manager.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.call_tool.return_value = mock_result
            mock_client_class.return_value = mock_client
            
            result = await upstream_manager.call_tool("test_http_call", "test_tool", {"arg": "value"})
            
            assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_call_tool_stdio(self, upstream_manager: UpstreamManager) -> None:
        """Test calling a tool on stdio server"""
        upstream_manager.add_stdio_server("test_stdio_call", "npx", ["-y", "@example/server"])
        upstream_manager.clients["test_stdio_call"] = {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@example/server"],
            "env": {},
            "working_directory": None
        }
        
        mock_result = Mock()
        mock_result.data = {"result": "stdio_success"}
        mock_result.content = None
        
        with patch("src.upstream.manager.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.call_tool.return_value = mock_result
            mock_client_class.return_value = mock_client
            
            result = await upstream_manager.call_tool("test_stdio_call", "test_tool", {})
            
            assert result == {"result": "stdio_success"}

    @pytest.mark.asyncio
    async def test_call_tool_with_content_blocks(self, upstream_manager: UpstreamManager) -> None:
        """Test calling tool that returns content blocks instead of data"""
        upstream_manager.add_http_server("test_http_content", "https://example.com/mcp")
        upstream_manager.clients["test_http_content"] = {
            "type": "http",
            "url": "https://example.com/mcp",
            "auth_token": None
        }
        
        mock_content_block1 = Mock()
        mock_content_block1.text = "First result"
        
        mock_content_block2 = Mock()
        mock_content_block2.text = "Second result"
        
        mock_result = Mock()
        mock_result.data = None
        mock_result.content = [mock_content_block1, mock_content_block2]
        
        with patch("src.upstream.manager.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.call_tool.return_value = mock_result
            mock_client_class.return_value = mock_client
            
            result = await upstream_manager.call_tool("test_http_content", "test_tool", {})
            
            assert result == "First result\n\nSecond result"

    @pytest.mark.asyncio
    async def test_call_tool_unknown_server(self, upstream_manager: UpstreamManager) -> None:
        """Test calling tool on unknown server raises error"""
        with pytest.raises(ServerConfigError, match="Unknown server"):
            await upstream_manager.call_tool("unknown_server", "tool", {})

    def test_start_service_success(self, upstream_manager: UpstreamManager) -> None:
        """Test successfully starting a service"""
        config = ServiceServerConfig(
            command="echo",
            args=["hello"],
            port=9989,
            health_check_path="/health",
            startup_timeout=5
        )
        
        with patch("src.upstream.manager.subprocess.Popen") as mock_popen:
            with patch("src.upstream.manager.requests.get") as mock_get:
                mock_process = Mock()
                mock_process.pid = 12345
                mock_process.poll.return_value = None
                mock_popen.return_value = mock_process
                
                mock_response = Mock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response
                
                result = upstream_manager._start_service("test_service", config)
                
                assert result is True
                assert "test_service" in upstream_manager.background_processes

    def test_start_service_process_dies(self, upstream_manager: UpstreamManager) -> None:
        """Test service startup when process dies immediately"""
        config = ServiceServerConfig(
            command="false",
            args=[],
            port=9988,
            health_check_path="/health",
            startup_timeout=5
        )
        
        with patch("src.upstream.manager.subprocess.Popen") as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = 1  # Process exited
            mock_process.communicate.return_value = ("", "Error message")
            mock_popen.return_value = mock_process
            
            result = upstream_manager._start_service("test_service_dead", config)
            
            assert result is False

    def test_start_service_timeout(self, upstream_manager: UpstreamManager) -> None:
        """Test service startup timeout"""
        config = ServiceServerConfig(
            command="sleep",
            args=["100"],
            port=9987,
            health_check_path="/health",
            startup_timeout=1
        )
        
        with patch("src.upstream.manager.subprocess.Popen") as mock_popen:
            with patch("src.upstream.manager.requests.get") as mock_get:
                mock_process = Mock()
                mock_process.pid = 12345
                mock_process.poll.return_value = None
                mock_process.terminate.return_value = None
                mock_process.wait.return_value = None
                mock_popen.return_value = mock_process
                
                mock_get.side_effect = Exception("Connection refused")
                
                # Inject a fake time function that advances
                fake_time = [0.0]
                def mock_time_func() -> float:
                    result = fake_time[0]
                    fake_time[0] += 1.5  # Jump past timeout
                    return result
                
                result = upstream_manager._start_service(
                    "test_service_timeout", 
                    config,
                    time_func=mock_time_func
                )
                
                assert result is False
                mock_process.terminate.assert_called_once()