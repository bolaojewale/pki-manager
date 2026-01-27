"""Logging configuration for PKI MCP server."""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
    log_format: str = "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
) -> logging.Logger:
    """Configure logging for the PKI server.

    Args:
        log_file: Optional path to log file. If None, logs to stderr only.
        level: Logging level (default INFO).
        log_format: Format string for log messages.

    Returns:
        Configured root logger for pki_mcp_server.
    """
    logger = logging.getLogger("pki_mcp_server")
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers.clear()

    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    # Always add stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(level)
    logger.addHandler(stderr_handler)

    # Add file handler if specified
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            logger.addHandler(file_handler)
        except (OSError, PermissionError) as e:
            logger.warning(f"Could not create log file {log_file}: {e}")

    return logger


def get_logger(name: str = "pki_mcp_server") -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (will be prefixed with pki_mcp_server).

    Returns:
        Logger instance.
    """
    if name == "pki_mcp_server":
        return logging.getLogger(name)
    return logging.getLogger(f"pki_mcp_server.{name}")
