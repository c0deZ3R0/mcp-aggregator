# src/upstream/schemas.py
from typing import Optional
from dataclasses import dataclass, field

@dataclass
class HTTPServerConfig:
    """HTTP server configuration"""
    url: str
    auth_token: Optional[str] = None

@dataclass
class StdioServerConfig:
    """Stdio server configuration"""
    command: str
    args: list[str]
    env: dict[str, str] = field(default_factory=dict)
    working_directory: Optional[str] = None

@dataclass
class ServiceServerConfig:
    """Service server configuration"""
    command: str
    args: list[str]
    port: int
    health_check_path: str = "/mcp"
    startup_timeout: int = 30
    env: dict[str, str] = field(default_factory=dict)
    working_directory: Optional[str] = None
    description: Optional[str] = None