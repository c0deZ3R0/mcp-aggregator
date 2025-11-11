# tests/test_config.py
from src.config import config


class TestConfig:
    """Test suite for configuration"""

    def test_config_loads(self) -> None:
        """Test that config loads successfully"""
        assert config is not None

    def test_ui_password_exists(self) -> None:
        """Test that UI_PASSWORD is set"""
        assert hasattr(config, "UI_PASSWORD")
        assert config.UI_PASSWORD is not None

    def test_mcp_api_token_exists(self) -> None:
        """Test that MCP_API_TOKEN is set"""
        assert hasattr(config, "MCP_API_TOKEN")

    def test_host_and_port(self) -> None:
        """Test that HOST and PORT are configured"""
        assert hasattr(config, "HOST")
        assert hasattr(config, "PORT")
        assert config.HOST is not None
        assert config.PORT is not None