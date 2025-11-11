# tests/test_upstream/test_schemas.py

from src.upstream.schemas import HTTPServerConfig, StdioServerConfig, ServiceServerConfig


class TestHTTPServerConfig:
    """Test HTTPServerConfig dataclass"""

    def test_creation_with_auth(self) -> None:
        """Test creating HTTP config with auth token"""
        config = HTTPServerConfig(
            url="https://example.com/mcp",
            auth_token="test_token"
        )
        assert config.url == "https://example.com/mcp"
        assert config.auth_token == "test_token"

    def test_creation_without_auth(self) -> None:
        """Test creating HTTP config without auth token"""
        config = HTTPServerConfig(url="https://example.com/mcp")
        assert config.url == "https://example.com/mcp"
        assert config.auth_token is None


class TestStdioServerConfig:
    """Test StdioServerConfig dataclass"""

    def test_creation_with_defaults(self) -> None:
        """Test creating stdio config with defaults"""
        config = StdioServerConfig(
            command="npx",
            args=["-y", "@example/server"]
        )
        assert config.command == "npx"
        assert config.args == ["-y", "@example/server"]
        assert config.env == {}
        assert config.working_directory is None

    def test_creation_with_env(self) -> None:
        """Test creating stdio config with environment variables"""
        config = StdioServerConfig(
            command="npx",
            args=["-y", "@example/server"],
            env={"TEST": "value"}
        )
        assert config.env == {"TEST": "value"}

    def test_mutable_default_isolation(self) -> None:
        """Test that mutable defaults are isolated between instances"""
        config1 = StdioServerConfig(command="cmd1", args=["arg1"])
        config2 = StdioServerConfig(command="cmd2", args=["arg2"])
        
        config1.env["KEY"] = "value1"
        
        assert "KEY" not in config2.env


class TestServiceServerConfig:
    """Test ServiceServerConfig dataclass"""

    def test_creation_with_defaults(self) -> None:
        """Test creating service config with defaults"""
        config = ServiceServerConfig(
            command="uvx",
            args=["--from", "git+https://example.com"],
            port=9121
        )
        assert config.command == "uvx"
        assert config.port == 9121
        assert config.health_check_path == "/mcp"
        assert config.startup_timeout == 30
        assert config.env == {}

    def test_creation_with_custom_values(self) -> None:
        """Test creating service config with custom values"""
        config = ServiceServerConfig(
            command="uvx",
            args=["--from", "git+https://example.com"],
            port=9999,
            health_check_path="/health",
            startup_timeout=60,
            env={"DEBUG": "true"}
        )
        assert config.port == 9999
        assert config.health_check_path == "/health"
        assert config.startup_timeout == 60
        assert config.env == {"DEBUG": "true"}