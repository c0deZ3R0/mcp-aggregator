# src/upstream/utils.py
import os
from typing import Optional

def resolve_token(token_or_env: Optional[str]) -> Optional[str]:
    """
    Resolve a token that might be an environment variable reference.
    If it starts with $, treat it as an env var name.
    Otherwise, treat it as a literal token.
    """
    if not token_or_env:
        return None

    if token_or_env.startswith("$"):
        env_var_name = token_or_env[1:]
        resolved = os.getenv(env_var_name)
        if not resolved:
            print(f"⚠️  Environment variable '{env_var_name}' not found")
        return resolved

    return token_or_env