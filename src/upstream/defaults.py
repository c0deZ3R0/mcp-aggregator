# src/upstream/defaults.py
"""Default upstream server configurations"""

def get_default_http_servers() -> dict[str, dict[str, str | None]]:
    """Get default HTTP server configurations"""
    return {
        "gofastmcp": {
            "url": "https://gofastmcp.com/mcp",  # Make sure this is always a string
            "auth_token": None
        }
    }

def get_default_stdio_servers() -> dict[str, dict]:
    """Get default stdio server configurations"""
    return {
        "context7": {
            "command": "npx",
            "args": ["-y", "@upstash/context7-mcp"],
            "env": {},
            "working_directory": None
        },
        "filesystem": {
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                "."
            ],
            "env": {},
            "working_directory": "."
        },
        "shell": {
            "command": "uvx",
            "args": ["mcp-shell-server"],
            "env": {
                "ALLOW_COMMANDS": "ls,cat,pwd,grep,wc,touch,find"
            },
            "working_directory": None
        }

    }

def get_default_service_servers() -> dict[str, dict]:
    """Get default service server configurations"""
    return {
       "serena": {
    "command": "uvx",
    "args": [
        "--from",
        "git+https://github.com/oraios/serena",
        "serena",
        "start-mcp-server",
        "--transport",
        "streamable-http",
        "--port",
        "9121",
        "--context",
        "agent",
        "--mode",
        "no-onboarding"
    ],
    "port": 9121,
    "health_check_path": "/mcp",
    "startup_timeout": 30,
    "env": {
    },
    "working_directory": None,
    "description": "Semantic code retrieval and editing toolkit with LSP integration"
}
    }