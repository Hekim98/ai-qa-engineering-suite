"""Consistent console and rotating-file logging for QA runs."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
_HANDLER_MARKER = "_ai_qa_handler"
_LOG_PATH_MARKER = "_ai_qa_log_path"


def configure_logging(
    *,
    name: str = "ai_qa",
    level: int = logging.INFO,
    log_dir: str | Path = "logs",
) -> logging.Logger:
    """Return a logger with one console handler and one rotating UTF-8 file handler."""
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    log_path = (directory / "ai-qa.log").resolve()

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    existing = [
        handler
        for handler in logger.handlers
        if getattr(handler, _HANDLER_MARKER, False)
        and getattr(handler, _LOG_PATH_MARKER, None) == log_path
    ]
    if existing:
        for handler in existing:
            handler.setLevel(level)
        return logger

    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    setattr(console, _HANDLER_MARKER, True)
    setattr(console, _LOG_PATH_MARKER, log_path)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    setattr(file_handler, _HANDLER_MARKER, True)
    setattr(file_handler, _LOG_PATH_MARKER, log_path)

    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger
