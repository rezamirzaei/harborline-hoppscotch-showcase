"""Logging configuration for Harborline."""

from __future__ import annotations

import logging
import sys
from typing import Any


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    # Reduce noise from third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


class ServiceLogger:
    """Structured logger for service operations."""

    def __init__(self, service_name: str) -> None:
        self._logger = get_logger(f"harborline.{service_name}")

    def info(self, message: str, **context: Any) -> None:
        self._log(logging.INFO, message, context)

    def warning(self, message: str, **context: Any) -> None:
        self._log(logging.WARNING, message, context)

    def error(self, message: str, **context: Any) -> None:
        self._log(logging.ERROR, message, context)

    def debug(self, message: str, **context: Any) -> None:
        self._log(logging.DEBUG, message, context)

    def _log(self, level: int, message: str, context: dict[str, Any]) -> None:
        if context:
            context_str = " | ".join(f"{k}={v}" for k, v in context.items())
            message = f"{message} | {context_str}"
        self._logger.log(level, message)
