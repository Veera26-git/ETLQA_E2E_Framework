"""Transformation utilities for the ETL QA framework.

The framework allows **column‑level business transformations** to be declared in
``metadata.yaml`` under a ``transformations`` list for each table.  Each entry
contains:

* ``name`` – an identifier (used only for documentation)
* ``source_expression`` – a Pandas‑compatible expression evaluated against the
  **source** ``DataFrame``.  The expression may reference any source column.
* ``target_column`` – the name of the column that should appear in the **target**
  table after the transformation.

The ``apply_transformations`` function reads these definitions and adds the new
columns to a copy of the source DataFrame.  It is deliberately side‑effect free –
the original DataFrame is never mutated.
"""

from __future__ import annotations

import pandas as pd
from typing import Dict, Any

from .metadata import load_metadata


def _apply_one(df: pd.DataFrame, expr: str, target_col: str) -> pd.DataFrame:
    """Evaluate ``expr`` against ``df`` and assign the result to ``target_col``.

    ``expr`` is evaluated with ``pandas.eval`` which supports NumPy‑style
    arithmetic and column references (e.g. ``"salary * 1.2"``).  The function
    returns a **new** DataFrame with the additional column.
    """
    # ``pandas.eval`` works on the DataFrame's column namespace.
    # ``engine='python'`` avoids Numexpr complications for simple arithmetic.
    result_series = pd.eval(expr, local_dict=df.to_dict('series'), engine='python')
    new_df = df.copy()
    new_df[target_col] = result_series
    return new_df


def apply_transformations(table_key: str, df: pd.DataFrame) -> pd.DataFrame:
    """Apply all declared transformations for ``table_key`` to ``df``.

    If no ``transformations`` list exists for the table, the original ``df`` is
    returned unchanged.
    """
    meta = load_metadata()["tables"].get(table_key, {})
    transforms = meta.get("transformations", [])
    transformed_df = df
    for tr in transforms:
        source_expr = tr.get("source_expression")
        target_col = tr.get("target_column")
        if not source_expr or not target_col:
            # Skip malformed entries – the framework will have warned during
            # metadata validation (not shown here).
            continue
        transformed_df = _apply_one(transformed_df, source_expr, target_col)
    return transformed_df
