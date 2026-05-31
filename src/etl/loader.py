"""Target data loading utilities.

The target system in this framework is Microsoft SQL Server.  Loading is
performed via SQLAlchemy + ``pyodbc``.  The loader returns a ``pandas``
``DataFrame`` representing the destination table, which the validation
layer can compare with the source dataframe.
"""

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from typing import Literal

from ..config import get_engine, logger
from .metadata import load_metadata


def _load_sqlserver(engine: Engine, table_name: str) -> pd.DataFrame:
    """Read a table from SQL Server using ``SELECT *``.

    Args:
        engine: SQLAlchemy engine for the SQL Server target.
        table_name: Fully qualified table name (e.g. ``dbo.employees``).
    """
    logger.debug("Loading SQL Server target table %s", table_name)
    query = text(f"SELECT * FROM {table_name}")
    return pd.read_sql(query, con=engine)


def load_target(table_key: str) -> pd.DataFrame:
    """Load target data for the logical ``table_key`` defined in metadata.

    The function inspects the ``target`` configuration of a table entry
    and currently supports only SQL Server.  If support for additional
    targets (e.g., Oracle) is added later, the dispatch can be extended
    here.
    """
    meta = load_metadata()["tables"][table_key]
    target_cfg = meta["target"]
    tgt_type: Literal["sqlserver"] = target_cfg["type"]
    if tgt_type == "sqlserver":
        engine = get_engine("sqlserver")
        return _load_sqlserver(engine, target_cfg["table"])
    raise ValueError(f"Unsupported target type '{tgt_type}' for table {table_key}")
