"""Shared logging helpers."""

import logging
import os
from pathlib import Path


def add_console_logging(logger: logging.Logger, level=logging.INFO):
    """Add a console handler to a logger if one doesn't exist."""
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        ch = logging.StreamHandler()
        ch.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)


def create_logger(name: str, log_file: str, caller_file: str = None) -> logging.Logger:
    """Create a logger with file + console handlers.
    
    Logs are written to: src/earnings_calculator/logs/
    
    Args:
        name: Logger name
        log_file: Filename for the log (e.g., "cache_debug.log")
        caller_file: __file__ from the calling module (in case it's needed for fallback)
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        # Always write logs to src/earnings_calculator/logs/
        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        log_path = os.path.join(logs_dir, log_file)
        
        fh = logging.FileHandler(log_path)
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    add_console_logging(logger, level=logging.INFO)
    return logger
