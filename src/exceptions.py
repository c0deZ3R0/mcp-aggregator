# src/exceptions.py
class MCPException(Exception):
    """Base exception for MCP aggregator"""
    pass

class ServerConfigError(MCPException):
    """Raised when server configuration is invalid"""
    pass

class ServerNotFoundError(MCPException):
    """Raised when server is not found"""
    pass

class ToolDiscoveryError(MCPException):
    """Raised when tool discovery fails"""
    pass

class ToolExecutionError(MCPException):
    """Raised when tool execution fails"""
    pass