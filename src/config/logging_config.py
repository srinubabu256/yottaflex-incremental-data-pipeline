"""
Structured logging configuration for YottaFlex.
"""

import logging
import sys
from pathlib import Path
from src.config.settings import get_settings


def configure_logging(log_level: str | None = None, log_file: Path | None = None) -> None:
    """Configures root and application loggers."""
    settings = get_settings()
    level_name = log_level or settings.log_level
    numeric_level = getattr(logging, level_name.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(numeric_level)
    root_logger.addHandler(console_handler)

    # Optional file handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(numeric_level)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Retrieves a named logger instance."""
    return logging.getLogger(name)
