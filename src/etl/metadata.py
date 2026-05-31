"""Metadata handling for the ETL QA framework.

The framework is *metadata‑driven*: a YAML file describes each logical
entity (table) that participates in the ETL process.  The metadata is used
by the extractor, loader and validation utilities.

Typical ``metadata.yaml`` structure::

    tables:
      employees:
        source:
          type: csv
          path: employees.csv
        target:
          type: sqlserver
          table: dbo.employees
        validations:
          - count
          - null
          - duplicate
          - schema
        schema:
          id: int
          name: str
          hire_date: datetime64[ns]
          salary: float

Only a subset of fields is required – the validator functions check for the
presence of the corresponding configuration before executing.
"""

import yaml
from pathlib import Path
from typing import Dict, Any

METADATA_PATH = Path(__file__).resolve().parents[1] / "metadata.yaml"


def load_metadata() -> Dict[str, Any]:
    """Load the ``metadata.yaml`` file.

    Returns
    -------
    dict
        The parsed YAML as a Python dictionary.  The top‑level key is
        ``tables`` mapping logical table names to their configuration.
    """
    if not METADATA_PATH.is_file():
        raise FileNotFoundError(f"Metadata file not found at {METADATA_PATH}")
    with METADATA_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data
