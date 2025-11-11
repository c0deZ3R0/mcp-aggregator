# src/auth/validators.py (NEW FILE)
"""Input validation utilities for security"""
import re
from urllib.parse import urlparse
from typing import Optional

def validate_server_name(name: str) -> bool:
    """Validate server name (alphanumeric, dash, underscore only)"""
    if not name or len(name) > 50:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', name))

def validate_url(url: str) -> bool:
    """Validate URL (http/https only)"""
    try:
        result = urlparse(url)
        return all([
            result.scheme in ['http', 'https'],
            result.netloc,
            len(url) <= 2048  # Reasonable URL length limit
        ])
    except Exception:
        return False

def validate_command(command: str) -> bool:
    """Validate command (whitelist safe commands)"""
    safe_commands = {
        'python', 'python3', 'node', 'npx', 'uvx', 'bash', 'sh',
        'ruby', 'go', 'java', 'dotnet'
    }
    return command.lower() in safe_commands

def validate_port(port: int) -> bool:
    """Validate port number (avoid privileged ports)"""
    return 1024 <= port <= 65535

def validate_args(args: list[str]) -> bool:
    """Validate command arguments"""
    if not isinstance(args, list) or len(args) > 50:
        return False
    
    for arg in args:
        if not isinstance(arg, str) or len(arg) > 500:
            return False
        # Reject shell metacharacters
        if any(char in arg for char in ['|', '&', ';', '$', '`', '\n', '\r']):
            return False
    
    return True

def sanitize_server_name(name: str) -> str:
    """Sanitize server name"""
    return re.sub(r'[^a-zA-Z0-9_-]', '', name)[:50]

def sanitize_token(token: Optional[str]) -> Optional[str]:
    """Sanitize auth token"""
    if not token:
        return None
    # Allow alphanumeric, dash, underscore, dot, and $ for env vars
    return re.sub(r'[^a-zA-Z0-9_\-.$]', '', token)[:500]