"""Validation utilities for ETL QA.

Each validation receives a *source* ``DataFrame`` and a *target* ``DataFrame``
(and optionally the table's metadata) and returns a ``bool`` indicating
whether the validation passed.  When a validation fails, a human‑readable
message is logged via the central ``logger``.

Supported validation names (mirroring ``metadata.yaml``) are:

- ``count`` – row count equality
- ``aggregate`` – numeric column aggregations (sum, avg, min, max) match
- ``data`` – full row‑wise equality after optional sorting
- ``duplicate`` – duplicate rows (by primary key) are absent in both sides
- ``null`` – ``NULL``/``NaN`` counts match expectations (zero by default)
- ``schema`` – column names and dtypes conform to the declared schema
"""

import pandas as pd
from typing import Dict, Any, List
from pandas.api.types import is_numeric_dtype, is_string_dtype

from ..config import logger
from .metadata import load_metadata


def _sort_frames(src: pd.DataFrame, tgt: pd.DataFrame, keys: List[str]) -> (pd.DataFrame, pd.DataFrame):
    """Return source and target frames sorted by ``keys`` for deterministic comparison."""
    src_sorted = src.sort_values(by=keys).reset_index(drop=True)
    tgt_sorted = tgt.sort_values(by=keys).reset_index(drop=True)
    return src_sorted, tgt_sorted


def validate_count(src: pd.DataFrame, tgt: pd.DataFrame, **_: Any) -> bool:
    """Validate that source and target have the same row count."""
    if len(src) != len(tgt):
        logger.error("Count validation failed: source %d rows vs target %d rows", len(src), len(tgt))
        return False
    logger.info("Count validation passed (%d rows)", len(src))
    return True


def validate_aggregate(src: pd.DataFrame, tgt: pd.DataFrame, **_: Any) -> bool:
    """Validate numeric aggregates (sum, mean, min, max) for each numeric column.

    The function iterates over columns that are numeric in *both* frames and
    checks that the aggregates are equal (within a small tolerance for floating
    point values).
    """
    numeric_cols = [c for c in src.columns if is_numeric_dtype(src[c]) and c in tgt.columns and is_numeric_dtype(tgt[c])]
    passed = True
    for col in numeric_cols:
        src_sum, tgt_sum = src[col].sum(), tgt[col].sum()
        src_mean, tgt_mean = src[col].mean(), tgt[col].mean()
        src_min, tgt_min = src[col].min(), tgt[col].min()
        src_max, tgt_max = src[col].max(), tgt[col].max()
        if not (
            pd.isclose(src_sum, tgt_sum)
            and pd.isclose(src_mean, tgt_mean)
            and pd.isclose(src_min, tgt_min)
            and pd.isclose(src_max, tgt_max)
        ):
            logger.error(
                "Aggregate validation failed for column '%s': src(sum=%s,mean=%s,min=%s,max=%s) vs tgt(sum=%s,mean=%s,min=%s,max=%s)",
                col,
                src_sum,
                src_mean,
                src_min,
                src_max,
                tgt_sum,
                tgt_mean,
                tgt_min,
                tgt_max,
            )
            passed = False
    if passed:
        logger.info("Aggregate validation passed for %d numeric columns", len(numeric_cols))
    return passed


def validate_data(src: pd.DataFrame, tgt: pd.DataFrame, **_: Any) -> bool:
    """Validate that source and target data are identical (row‑wise).

    The frames are sorted by all columns to make the comparison order‑agnostic.
    """
    if src.empty and tgt.empty:
        logger.info("Data validation passed (both frames empty)")
        return True
    # Use all columns as sort keys; missing columns cause an error which we log.
    common_cols = [c for c in src.columns if c in tgt.columns]
    src_sorted, tgt_sorted = _sort_frames(src[common_cols], tgt[common_cols], common_cols)
    if not src_sorted.equals(tgt_sorted):
        diff = (src_sorted != tgt_sorted).stack()
        logger.error("Data validation failed – mismatched rows/columns. First diff: %s", diff.head(1))
        return False
    logger.info("Data validation passed – source and target are identical")
    return True


def validate_duplicate(src: pd.DataFrame, tgt: pd.DataFrame, **_: Any) -> bool:
    """Validate that there are no duplicate rows based on the primary key.

    The primary key is inferred from the ``schema`` section of the metadata –
    any column named ``id`` or ending with ``_id`` is considered a candidate.
    If no such column exists, the whole row set is examined for duplicates.
    """
    meta = load_metadata()
    passed = True
    for table, cfg in meta["tables"].items():
        pk_candidates = [c for c in cfg.get("schema", {}) if c == "id" or c.endswith("_id")]
        key_cols = pk_candidates or list(src.columns)
        src_dups = src.duplicated(subset=key_cols).sum()
        tgt_dups = tgt.duplicated(subset=key_cols).sum()
        if src_dups or tgt_dups:
            logger.error(
                "Duplicate validation failed for %s – source dups: %d, target dups: %d (key cols=%s)",
                table,
                src_dups,
                tgt_dups,
                key_cols,
            )
            passed = False
    if passed:
        logger.info("Duplicate validation passed – no duplicate primary keys found")
    return passed


def validate_null(src: pd.DataFrame, tgt: pd.DataFrame, **_: Any) -> bool:
    """Validate that ``NULL`` / ``NaN`` counts are identical in source and target.

    By default we expect no nulls; however, if the metadata explicitly lists a
    column under ``allow_null`` we skip that column.
    """
    meta = load_metadata()
    passed = True
    for table, cfg in meta["tables"].items():
        allow_null = cfg.get("allow_null", [])
        cols = [c for c in src.columns if c not in allow_null]
        for col in cols:
            src_null = src[col].isna().sum()
            tgt_null = tgt[col].isna().sum()
            if src_null != tgt_null:
                logger.error(
                    "Null validation failed for %s.%s – source nulls: %d, target nulls: %d",
                    table,
                    col,
                    src_null,
                    tgt_null,
                )
                passed = False
    if passed:
        logger.info("Null validation passed – null counts match expectations")
    return passed


def validate_schema(src: pd.DataFrame, tgt: pd.DataFrame, **_: Any) -> bool:
    """Validate that column names and dtypes match the declared schema.

    The function checks both source and target frames against the ``schema``
    mapping defined in ``metadata.yaml``.
    """
    meta = load_metadata()
    passed = True
    for table, cfg in meta["tables"].items():
        schema: Dict[str, str] = cfg.get("schema", {})
        for frame, name in [(src, "source"), (tgt, "target")]:
            # Column existence
            missing = set(schema.keys()) - set(frame.columns)
            extra = set(frame.columns) - set(schema.keys())
            if missing:
                logger.error("Schema validation failed (%s) – missing columns %s in %s", table, missing, name)
                passed = False
            if extra:
                logger.warning("Schema validation warning (%s) – extra columns %s in %s", table, extra, name)
            # Dtype checks (basic mapping: int, float, str, datetime)
            for col, expected_type in schema.items():
                if col not in frame.columns:
                    continue
                dtype = str(frame[col].dtype)
                # Simple heuristic – we only need to catch obvious mismatches.
                if expected_type == "int" and not pd.api.types.is_integer_dtype(frame[col]):
                    logger.error("Schema validation failed (%s) – column %s expected int, got %s", table, col, dtype)
                    passed = False
                elif expected_type == "float" and not pd.api.types.is_float_dtype(frame[col]):
                    logger.error("Schema validation failed (%s) – column %s expected float, got %s", table, col, dtype)
                    passed = False
                elif expected_type == "str" and not is_string_dtype(frame[col]):
                    logger.error("Schema validation failed (%s) – column %s expected str, got %s", table, col, dtype)
                    passed = False
                # datetime handling – pandas uses ``datetime64[ns]``
                elif expected_type.startswith("datetime") and not pd.api.types.is_datetime64_any_dtype(frame[col]):
                    logger.error("Schema validation failed (%s) – column %s expected datetime, got %s", table, col, dtype)
                    passed = False
    if passed:
        logger.info("Schema validation passed for all tables")
    return passed


# Mapping from validation name (as used in ``metadata.yaml``) to function
VALIDATORS = {
    "count": validate_count,
    "aggregate": validate_aggregate,
    "data": validate_data,
    "duplicate": validate_duplicate,
    "null": validate_null,
    "schema": validate_schema,
}


def run_validations(table_key: str, src: pd.DataFrame, tgt: pd.DataFrame) -> List[str]:
    """Run every validation listed for ``table_key`` and return a list of failures.

    Returns
    -------
    list[str]
        Human‑readable messages for each failed validation.  An empty list
        indicates that **all** checks passed.
    """
    meta = load_metadata()["tables"][table_key]
    failures: List[str] = []
    for val_name in meta.get("validations", []):
        validator = VALIDATORS.get(val_name)
        if validator is None:
            logger.warning("No validator implemented for '%s' – skipping", val_name)
            continue
        ok = validator(src, tgt)
        if not ok:
            failures.append(f"{table_key}: {val_name} validation failed")
    return failures
