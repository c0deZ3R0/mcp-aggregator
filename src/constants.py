# src/constants.py
# Server type constants
SERVER_TYPE_HTTP = "http"
SERVER_TYPE_STDIO = "stdio"
SERVER_TYPE_SERVICE = "service"

# Default values
DEFAULT_STARTUP_TIMEOUT = 30
DEFAULT_HEALTH_CHECK_PATH = "/mcp"
DEFAULT_REQUEST_TIMEOUT = 2

# Status indicators
STATUS_RUNNING = "🟢 Running"
STATUS_CRASHED = "🔴 Crashed"
STATUS_NOT_STARTED = "⚪ Not Started"

# Type color mapping for UI
TYPE_COLORS = {
    "HTTP": "bg-blue-100 text-blue-800",
    "Stdio": "bg-green-100 text-green-800",
    "Service": "bg-purple-100 text-purple-800"
}