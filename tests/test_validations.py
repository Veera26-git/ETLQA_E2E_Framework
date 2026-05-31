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


def test_all_validations_pass_for_employees():
    """All configured validations should pass when source == target."""
    table = "employees"
    src = extract_source(table)
    tgt = _load_target_mock(table)
    failures = v.run_validations(table, src, tgt)
    assert failures == [], f"Expected no failures, got: {failures}"


def test_duplicate_validation_catches_duplicates():
    """Inject a duplicate row in the target and ensure the duplicate validator fails."""
    table = "employees"
    src = extract_source(table)
    tgt = _load_target_mock(table)
    # Duplicate the first row
    tgt_dup = pd.concat([tgt, tgt.iloc[:1]], ignore_index=True)
    failures = v.run_validations(table, src, tgt_dup)
    # The duplicate validator adds a message ending with "duplicate validation failed"
    assert any("duplicate" in f.lower() for f in failures), "Duplicate validation did not report a failure"


def test_null_validation_catches_nulls():
    """Introduce NaN values in the target and expect the null validator to fail."""
    table = "employees"
    src = extract_source(table)
    tgt = _load_target_mock(table).copy()
    tgt.loc[0, "salary"] = pd.NA
    failures = v.run_validations(table, src, tgt)
    assert any("null" in f.lower() for f in failures), "Null validation did not report a failure"


def test_schema_validation_catches_type_mismatch():
    """Change a column dtype to string and verify the schema validator fails."""
    table = "employees"
    src = extract_source(table)
    tgt = _load_target_mock(table).copy()
    # Cast salary to string – schema expects ``float``
    tgt["salary"] = tgt["salary"].astype(str)
    failures = v.run_validations(table, src, tgt)
    assert any("schema" in f.lower() for f in failures), "Schema validation did not report a failure"
