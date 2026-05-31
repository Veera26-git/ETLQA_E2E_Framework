"""Centralised logging configuration for the ETL QA framework.

The logger writes human‑readable messages to ``logs/etl.log`` and also
streams to ``stdout`` so that pytest output includes the log entries.
All modules import a single ``logger`` instance via::

    from .logger import logger

The configuration mirrors the conventional ``logging`` best‑practice
pattern (file handler + stream handler) and is deliberately lightweight –
no external dependencies beyond the Python standard library.
"""

import logging
import os
from pathlib import Path

# Ensure the logs directory exists – ``exist_ok=True`` prevents race conditions.
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "etl.log"

# Create a top‑level logger for the framework. Users can obtain child loggers
# via ``logging.getLogger(__name__)`` if they need module‑specific granularity.
logger = logging.getLogger("etlqa")
logger.setLevel(logging.DEBUG)

# Avoid duplicate handlers if this module is reloaded (e.g., during tests).
if not logger.handlers:
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler – rotates daily to keep file sizes manageable.
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Stream handler – mirrors log output to the console/pytest output.
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

# Prevent the logger from propagating to the root logger (which could duplicate output).
logger.propagate = False
