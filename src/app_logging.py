"""
Application logging helpers.
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


LOG_FILE_NAME = "operation.log"


def get_app_directory() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_log_path() -> str:
    return os.path.join(get_app_directory(), LOG_FILE_NAME)


def configure_logging() -> str:
    log_path = get_log_path()
    root_logger = logging.getLogger()
    if getattr(configure_logging, "_configured", False):
        return log_path

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_048_576,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    configure_logging._configured = True
    return log_path
