# src/lifecycle/cleanup.py
import atexit
import signal
import logging
from typing import Any
from src.upstream.manager import UpstreamManager

logger = logging.getLogger(__name__)

def setup_cleanup_handlers(upstream: UpstreamManager) -> None:
    """Register cleanup handlers for graceful shutdown"""

    def cleanup_handler() -> None:
        upstream.cleanup_all_processes()

    def signal_handler(signum: int, frame: Any) -> None:
        logger.info(f"Received signal {signum}")
        cleanup_handler()
        exit(0)

    atexit.register(cleanup_handler)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)