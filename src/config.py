"""Configuration utilities for the ETL QA framework.

The framework expects the following environment variables to be set
(either in your shell or via a ``.env`` file) for database connections:

- ``ORACLE_DSN`` – Oracle DB Data Source Name (e.g. ``user/password@host:port/service_name``)
- ``SQLSERVER_DSN`` – SQL Server connection string understood by ``pyodbc``
  (e.g. ``Driver={ODBC Driver 17 for SQL Server};Server=server;Database=db;UID=user;PWD=pass``)
- ``CSV_ROOT`` – Base directory that contains CSV source files

The ``get_engine`` helper returns a SQLAlchemy ``Engine`` for the requested
target type (``oracle`` or ``sqlserver``).
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from typing import Literal

# Optional: load a .env file if present (useful for local dev)
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # ``python-dotenv`` is not required for the core framework; ignore if missing.
    pass

# ---------------------------------------------------------------------------
# Helper to build a SQLAlchemy engine based on a DSN string.
# ---------------------------------------------------------------------------

def _oracle_engine() -> Engine:
    dsn = os.getenv("ORACLE_DSN")
    if not dsn:
        raise RuntimeError("ORACLE_DSN environment variable not set")
    # ``oracle+cx_oracle`` uses the raw DSN string.
    return create_engine(f"oracle+cx_oracle://{dsn}")


def _sqlserver_engine() -> Engine:
    dsn = os.getenv("SQLSERVER_DSN")
    if not dsn:
        raise RuntimeError("SQLSERVER_DSN environment variable not set")
    # ``mssql+pyodbc`` expects the DSN URL‑encoded.
    return create_engine(f"mssql+pyodbc:///?odbc_connect={dsn}")


def get_engine(target: Literal["oracle", "sqlserver"]) -> Engine:
    """Return a SQLAlchemy engine for the requested target.

    Args:
        target: Either ``"oracle"`` or ``"sqlserver"``.
    """
    if target == "oracle":
        return _oracle_engine()
    if target == "sqlserver":
        return _sqlserver_engine()
    raise ValueError(f"Unsupported target '{target}'. Use 'oracle' or 'sqlserver'.")

# ---------------------------------------------------------------------------
# Miscellaneous configuration values used throughout the framework.
# ---------------------------------------------------------------------------

CSV_ROOT = os.getenv("CSV_ROOT", "data/csv")

# Logging configuration is defined in ``src/logger.py``.
