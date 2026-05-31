"""Pytest suite for the ETL QA framework.

The tests focus on the validation layer.  Because the framework expects a
real SQL Server target, the tests monkey‑patch ``etl.loader.load_target`` to
return a DataFrame constructed from the same CSV source file.  This keeps the
suite fast, deterministic and runnable on a developer's laptop without any
external database.
"""

import pandas as pd
import pytest
from pathlib import Path

# Import the public helpers from the package
from src.etl.extractor import extract_source
from src.etl import validation as v

# Helper that returns a DataFrame identical to the source – used as a mock target
def _load_target_mock(table_key: str) -> pd.DataFrame:
    # The metadata declares the CSV file path for each table under ``source``
    # – we reuse that same path for the mock target.
    meta = v.load_metadata()["tables"][table_key]
    csv_path = Path(__file__).parents[2] / "data" / "csv" / meta["source"]["path"]
    return pd.read_csv(csv_path)

# Patch the real ``load_target`` function inside the ``src.etl.loader`` module.
@pytest.fixture(autouse=True)
def mock_load_target(monkeypatch):
    import src.etl.loader as loader

    monkeypatch.setattr(loader, "load_target", _load_target_mock)
    yield

# ---------------------------------------------------------------------------
# Generic helper to get all table keys from metadata
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def all_table_keys() -> list:
    return list(v.load_metadata()["tables"].keys())

# ---------------------------------------------------------------------------
# 1️⃣ All validations should pass when source == target
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table_key", ["employees", "departments", "projects"])
def test_all_validations_pass(table_key: str):
    """All configured validations should pass when source equals target."""
    src = extract_source(table_key)
    tgt = _load_target_mock(table_key)
    failures = v.run_validations(table_key, src, tgt)
    assert failures == [], f"Expected no failures for {table_key}, got: {failures}"

# ---------------------------------------------------------------------------
# 2️⃣ Duplicate validation catches duplicates
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table_key", ["employees", "departments", "projects"])
def test_duplicate_validation_catches_duplicates(table_key: str):
    src = extract_source(table_key)
    tgt = _load_target_mock(table_key)
    # Duplicate the first row
    tgt_dup = pd.concat([tgt, tgt.iloc[:1]], ignore_index=True)
    failures = v.run_validations(table_key, src, tgt_dup)
    assert any("duplicate" in f.lower() for f in failures), f"Duplicate validation did not report a failure for {table_key}"

# ---------------------------------------------------------------------------
# 3️⃣ Null validation catches NaNs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table_key", ["employees", "departments", "projects"])
def test_null_validation_catches_nulls(table_key: str):
    src = extract_source(table_key)
    tgt = _load_target_mock(table_key).copy()
    # Introduce a NaN in the first column (if possible)
    first_col = tgt.columns[0]
    tgt.loc[0, first_col] = pd.NA
    failures = v.run_validations(table_key, src, tgt)
    assert any("null" in f.lower() for f in failures), f"Null validation did not report a failure for {table_key}"

# ---------------------------------------------------------------------------
# 4️⃣ Schema validation catches type mismatches
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table_key", ["employees", "departments", "projects"])
def test_schema_validation_catches_type_mismatch(table_key: str):
    src = extract_source(table_key)
    tgt = _load_target_mock(table_key).copy()
    # Cast the first numeric column (if any) to string to provoke a type error
    numeric_cols = [c for c in tgt.columns if pd.api.types.is_numeric_dtype(tgt[c])]
    if numeric_cols:
        tgt[numeric_cols[0]] = tgt[numeric_cols[0]].astype(str)
    failures = v.run_validations(table_key, src, tgt)
    assert any("schema" in f.lower() for f in failures), f"Schema validation did not report a failure for {table_key}"
"""
