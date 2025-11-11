# src/config.py (updated)
import os
import logging
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration"""
    MCP_API_TOKEN: str | None = os.getenv("MCP_API_TOKEN")
    UI_PASSWORD: str = os.getenv("UI_PASSWORD", "admin")
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "3050"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

config = Config()

# Configure logging
def setup_logging() -> None:
    """Setup application logging"""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('mcp-aggregator.log')
        ]
    )

setup_logging()