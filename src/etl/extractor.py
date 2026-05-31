"""Source data extraction utilities.

The framework supports CSV files and Oracle DB as *source* systems.  The
extraction logic is deliberately simple – it returns a ``pandas.DataFrame``
that callers can feed directly into the validation layer.
"""

import pandas as pd
from pathlib import Path
from typing import Literal
from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..config import CSV_ROOT, logger
from .metadata import load_metadata


def _extract_csv(relative_path: str) -> pd.DataFrame:
    """Read a CSV file located under ``CSV_ROOT``.

    Args:
        relative_path: Path relative to ``CSV_ROOT`` (e.g. ``"employees.csv"``).
    """
    csv_path = Path(CSV_ROOT) / relative_path
    logger.debug("Loading CSV source %s", csv_path)
    return pd.read_csv(csv_path)


def _extract_oracle(engine: Engine, table_name: str) -> pd.DataFrame:
    """Extract a full table from Oracle using ``SELECT *``.

    NOTE: In a real‑world scenario you would batch or filter; here the goal
    is to provide a deterministic dataset for testing.
    """
    logger.debug("Extracting Oracle table %s", table_name)
    query = text(f"SELECT * FROM {table_name}")
    return pd.read_sql(query, con=engine)


def extract_source(table_key: str) -> pd.DataFrame:
    """Extract source data for the logical ``table_key`` defined in metadata.

    The function looks up the source configuration for the given logical
    name and dispatches to the appropriate extractor.
    """
    meta = load_metadata()["tables"][table_key]
    source_cfg = meta["source"]
    src_type: Literal["csv", "oracle"] = source_cfg["type"]
    if src_type == "csv":
        return _extract_csv(source_cfg["path"])
    if src_type == "oracle":
        from ..config import get_engine

        engine = get_engine("oracle")
        return _extract_oracle(engine, source_cfg.get("table", table_key))
    raise ValueError(f"Unsupported source type '{src_type}' for table {table_key}")
