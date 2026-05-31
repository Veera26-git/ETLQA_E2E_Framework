"""SQL‑based pytest validation suite for the ETLQA_E2E_Framework.

Each test connects to the *source* Oracle database and the *target*
Microsoft SQL Server database, executes the appropriate SQL statements,
and asserts that the result sets are identical (or meet the required
condition).

The validation logic mirrors the validation names you listed:

* count
* data
* transformation
* null
* duplicate
* referential_integrity
* reconciliation
* schema

All table‑specific configuration (source/target names, primary‑key,
foreign‑key, expected schema, etc.) is read from ``metadata.yaml`` so
adding a new table only requires editing that file – no Python code has
to be changed.
"""

import pytest
from typing import Dict, Any, List, Tuple

from sqlalchemy.engine import Engine

# ---------------------------------------------------------------------------
# Helpers – load metadata and create DB engines
# ---------------------------------------------------------------------------
from src.etl.metadata import load_metadata
from src.config import get_engine, logger


@pytest.fixture(scope="session")
def oracle_engine() -> Engine:
    """SQLAlchemy engine for the Oracle source."""
    return get_engine("oracle")


@pytest.fixture(scope="session")
def sqlserver_engine() -> Engine:
    """SQLAlchemy engine for the SQL‑Server target."""
    return get_engine("sqlserver")


@pytest.fixture(scope="session")
def tables_meta() -> Dict[str, Any]:
    """Dictionary of table configurations from ``metadata.yaml``."""
    return load_metadata()["tables"]


# ---------------------------------------------------------------------------
# Generic SQL execution helpers
# ---------------------------------------------------------------------------
def fetch_one(engine: Engine, sql: str, **params) -> Any:
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        row = result.fetchone()
        return row[0] if row else None


def fetch_all(engine: Engine, sql: str, **params) -> List[Tuple]:
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        return [tuple(row) for row in result]


def table_ids(tables_meta: Dict[str, Any]) -> List[str]:
    return list(tables_meta.keys())


# ---------------------------------------------------------------------------
# 1️⃣ Count Validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table_key", table_ids(tables_meta()))
def test_count_validation(
    oracle_engine: Engine,
    sqlserver_engine: Engine,
    tables_meta: Dict[str, Any],
    table_key: str,
):
    cfg = tables_meta[table_key]
    src_tbl = cfg["source"].get("table", table_key)
    tgt_tbl = cfg["target"]["table"]

    src_cnt = fetch_one(oracle_engine, f"SELECT COUNT(*) FROM {src_tbl}")
    tgt_cnt = fetch_one(sqlserver_engine, f"SELECT COUNT(*) FROM {tgt_tbl}")

    assert src_cnt == tgt_cnt, f"Count mismatch for {table_key}: source={src_cnt}, target={tgt_cnt}"


# ---------------------------------------------------------------------------
# 2️⃣ Data Validation (row‑wise equality)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table_key", table_ids(tables_meta()))
def test_data_validation(
    oracle_engine: Engine,
    sqlserver_engine: Engine,
    tables_meta: Dict[str, Any],
    table_key: str,
):
    cfg = tables_meta[table_key]
    src_tbl = cfg["source"].get("table", table_key)
    tgt_tbl = cfg["target"]["table"]

    missing_in_target = fetch_all(
        oracle_engine,
        f"""
        SELECT * FROM {src_tbl}
        MINUS
        SELECT * FROM {tgt_tbl}
        """,
    )
    missing_in_source = fetch_all(
        sqlserver_engine,
        f"""
        SELECT * FROM {tgt_tbl}
        EXCEPT
        SELECT * FROM {src_tbl}
        """,
    )

    assert not missing_in_target, f"{table_key}: rows missing in target: {missing_in_target}"
    assert not missing_in_source, f"{table_key}: rows missing in source: {missing_in_source}"


# ---------------------------------------------------------------------------
# 3️⃣ Transformation Validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table_key", table_ids(tables_meta()))
def test_transformation_validation(
    oracle_engine: Engine,
    sqlserver_engine: Engine,
    tables_meta: Dict[str, Any],
    table_key: str,
):
    cfg = tables_meta[table_key]
    if "transformations" not in cfg:
        pytest.skip(f"No transformations defined for {table_key}")
    src_tbl = cfg["source"].get("table", table_key)
    tgt_tbl = cfg["target"]["table"]
    for tr in cfg["transformations"]:
        src_val = fetch_one(
            oracle_engine, f"SELECT SUM({tr['source_sql']}) FROM {src_tbl}"
        )
        tgt_val = fetch_one(
            sqlserver_engine, f"SELECT SUM({tr['target_sql']}) FROM {tgt_tbl}"
        )
        assert src_val == tgt_val, f"Transformation '{tr['name']}' failed for {table_key}: source={src_val}, target={tgt_val}"


# ---------------------------------------------------------------------------
# 4️⃣ Null Validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table_key", table_ids(tables_meta()))
def test_null_validation(
    oracle_engine: Engine,
    sqlserver_engine: Engine,
    tables_meta: Dict[str, Any],
    table_key: str,
):
    cfg = tables_meta[table_key]
    src_tbl = cfg["source"].get("table", table_key)
    tgt_tbl = cfg["target"]["table"]
    allow_null = set(cfg.get("allow_null", []))
    # Get column list from Oracle data dictionary
    col_sql = """
        SELECT column_name FROM all_tab_columns WHERE table_name = :tbl
    """
    src_cols = [row[0] for row in fetch_all(oracle_engine, col_sql, tbl=src_tbl.upper())]
    for col in src_cols:
        if col.lower() in allow_null:
            continue
        src_nulls = fetch_one(
            oracle_engine, f"SELECT COUNT(*) FROM {src_tbl} WHERE {col} IS NULL"
        )
        tgt_nulls = fetch_one(
            sqlserver_engine, f"SELECT COUNT(*) FROM {tgt_tbl} WHERE {col} IS NULL"
        )
        assert src_nulls == tgt_nulls, f"NULL count mismatch on {col} of {table_key}: source={src_nulls}, target={tgt_nulls}"


# ---------------------------------------------------------------------------
# 5️⃣ Duplicate Validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table_key", table_ids(tables_meta()))
def test_duplicate_validation(
    oracle_engine: Engine,
    sqlserver_engine: Engine,
    tables_meta: Dict[str, Any],
    table_key: str,
):
    cfg = tables_meta[table_key]
    src_tbl = cfg["source"].get("table", table_key)
    tgt_tbl = cfg["target"]["table"]
    schema = cfg.get("schema", {})
    key_cols = [c for c in schema if c == "id" or c.lower().endswith("_id")]
    key_expr = ", ".join(key_cols) if key_cols else "*"
    dup_sql = f"""
        SELECT COUNT(*) FROM (
            SELECT {key_expr}, COUNT(*) cnt FROM {{tbl}}
            GROUP BY {key_expr}
            HAVING COUNT(*) > 1
        )
    """
    src_dups = fetch_one(oracle_engine, dup_sql.format(tbl=src_tbl))
    tgt_dups = fetch_one(sqlserver_engine, dup_sql.format(tbl=tgt_tbl))
    assert src_dups == 0, f"{table_key}: source has {src_dups} duplicate rows"
    assert tgt_dups == 0, f"{table_key}: target has {tgt_dups} duplicate rows"


# ---------------------------------------------------------------------------
# 6️⃣ Referential Integrity Validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table_key", table_ids(tables_meta()))
def test_referential_integrity_validation(
    oracle_engine: Engine,
    sqlserver_engine: Engine,
    tables_meta: Dict[str, Any],
    table_key: str,
):
    cfg = tables_meta[table_key]
    fkeys = cfg.get("fkeys", [])
    if not fkeys:
        pytest.skip(f"No foreign‑key definitions for {table_key}")
    src_tbl = cfg["source"].get("table", table_key)
    tgt_tbl = cfg["target"]["table"]
    for fk in fkeys:
        src_sql = f"""
            SELECT COUNT(*) FROM {src_tbl} s
            LEFT JOIN {fk['ref_table']} r ON s.{fk['column']} = r.{fk['ref_column']}
            WHERE s.{fk['column']} IS NOT NULL AND r.{fk['ref_column']} IS NULL
        """
        tgt_sql = f"""
            SELECT COUNT(*) FROM {tgt_tbl} s
            LEFT JOIN {fk['ref_table']} r ON s.{fk['column']} = r.{fk['ref_column']}
            WHERE s.{fk['column']} IS NOT NULL AND r.{fk['ref_column']} IS NULL
        """
        src_orphans = fetch_one(oracle_engine, src_sql)
        tgt_orphans = fetch_one(sqlserver_engine, tgt_sql)
        assert src_orphans == 0, f"Source referential integrity broken for {table_key}.{fk['column']}"
        assert tgt_orphans == 0, f"Target referential integrity broken for {table_key}.{fk['column']}"


# ---------------------------------------------------------------------------
# 7️⃣ Reconciliation Testing (aggregate checks)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table_key", table_ids(tables_meta()))
def test_reconciliation_validation(
    oracle_engine: Engine,
    sqlserver_engine: Engine,
    tables_meta: Dict[str, Any],
    table_key: str,
):
    cfg = tables_meta[table_key]
    src_tbl = cfg["source"].get("table", table_key)
    tgt_tbl = cfg["target"]["table"]
    schema = cfg.get("schema", {})
    numeric_cols = [c for c, t in schema.items() if t in ("int", "float", "decimal")]
    if not numeric_cols:
        pytest.skip(f"No numeric columns to reconcile for {table_key}")
    agg_parts = []
    for col in numeric_cols:
        agg_parts.extend([
            f"SUM({col}) AS sum_{col}",
            f"AVG({col}) AS avg_{col}",
            f"MIN({col}) AS min_{col}",
            f"MAX({col}) AS max_{col}",
        ])
    agg_clause = ", ".join(agg_parts)
    src_agg = fetch_one(oracle_engine, f"SELECT {agg_clause} FROM {src_tbl}")
    tgt_agg = fetch_one(sqlserver_engine, f"SELECT {agg_clause} FROM {tgt_tbl}")
    assert src_agg == tgt_agg, f"Reconciliation aggregates differ for {table_key}"


# ---------------------------------------------------------------------------
# 8️⃣ Schema Validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table_key", table_ids(tables_meta()))
def test_schema_validation(
    oracle_engine: Engine,
    sqlserver_engine: Engine,
    tables_meta: Dict[str, Any],
    table_key: str,
):
    cfg = tables_meta[table_key]
    src_tbl = cfg["source"].get("table", table_key)
    tgt_tbl = cfg["target"]["table"]
    expected = cfg.get("schema", {})

    # Oracle – ALL_TAB_COLUMNS
    oracle_sql = """
        SELECT column_name, data_type FROM all_tab_columns WHERE table_name = :tbl
    """
    oracle_cols = {row[0].lower(): row[1].lower() for row in fetch_all(oracle_engine, oracle_sql, tbl=src_tbl.upper())}

    # SQL Server – INFORMATION_SCHEMA.COLUMNS
    sqlsrv_sql = """
        SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = :tbl
    """
    sqlsrv_cols = {row[0].lower(): row[1].lower() for row in fetch_all(sqlserver_engine, sqlsrv_sql, tbl=tgt_tbl)}

    missing_src = set(expected) - set(oracle_cols)
    missing_tgt = set(expected) - set(sqlsrv_cols)
    assert not missing_src, f"{table_key}: columns missing in Oracle source: {missing_src}"
    assert not missing_tgt, f"{table_key}: columns missing in SQL Server target: {missing_tgt}"

    # Simple type‑mapping (very coarse)
    type_map = {
        "int": ["int", "integer", "number", "bigint", "smallint"],
        "float": ["float", "binary_double", "binary_float", "number"],
        "str": ["varchar", "char", "nvarchar", "nchar", "text", "clob"],
        "datetime": ["date", "timestamp", "datetime"],
    }

    def normalize(dtype: str) -> str:
        for std, aliases in type_map.items():
            if any(a in dtype for a in aliases):
                return std
        return dtype

    mismatches = []
    for col, exp_type in expected.items():
        src_type = normalize(oracle_cols[col.lower()])
        tgt_type = normalize(sqlsrv_cols[col.lower()])
        if src_type != exp_type:
            mismatches.append(f"{col}: Oracle type {src_type} != expected {exp_type}")
        if tgt_type != exp_type:
            mismatches.append(f"{col}: SQL Server type {tgt_type} != expected {exp_type}")
    assert not mismatches, f"{table_key}: schema mismatches – " + "; ".join(mismatches)
