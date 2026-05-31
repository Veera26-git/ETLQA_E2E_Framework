"""Entry point for the ETL QA framework.

Typical usage (from the command line)::

    python -m etlqa_etl.main

The script iterates over every logical table defined in ``metadata.yaml``,
extracts the source data, loads the target data, runs the configured
validations and logs a summary.  It exits with status ``0`` when *all*
validations pass, otherwise ``1``.
"""

import sys
from pathlib import Path
from typing import List

from .extractor import extract_source
from .loader import load_target
from .validation import run_validations
from ..config import logger
from .metadata import load_metadata


def _run_table(table_key: str) -> List[str]:
    """Run ETL validation for a single logical table.

    Returns a list of failure messages (empty if all pass).
    """
    logger.info("=== Validating table: %s ===", table_key)
    try:
        src_df = extract_source(table_key)
        tgt_df = load_target(table_key)
    except Exception as exc:  # pragma: no cover – protect the loop
        logger.exception("Error extracting/loading data for %s: %s", table_key, exc)
        return [f"{table_key}: extraction/loading error – {exc}"]

    failures = run_validations(table_key, src_df, tgt_df)
    if not failures:
        logger.info("All validations passed for %s", table_key)
    else:
        logger.error("%d validation(s) failed for %s", len(failures), table_key)
    return failures


def main() -> int:
    meta = load_metadata()
    all_failures: List[str] = []
    for table_key in meta.get("tables", {}):
        all_failures.extend(_run_table(table_key))
    if all_failures:
        logger.error("ETL validation completed with failures:")
        for msg in all_failures:
            logger.error("  - %s", msg)
        return 1
    logger.info("ETL validation completed successfully – no failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
