"""Critical guardrail tests for schema isolation."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


PIPELINE_DIR = Path(__file__).parent.parent.parent / "pipeline"
FORBIDDEN_REFERENCES = [
    "schema='saddl'",
    'schema="saddl"',
    "saddl.campaigns",
    "saddl.ad_groups",
    "saddl.targets",
    "saddl.bids",
]


def get_pipeline_files():
    return list(PIPELINE_DIR.glob("**/*.py"))


@pytest.mark.parametrize("filepath", get_pipeline_files())
def test_no_saddl_schema_references(filepath):
    content = filepath.read_text()
    for forbidden in FORBIDDEN_REFERENCES:
        assert forbidden not in content, (
            f"Schema violation: {filepath.name} references '{forbidden}'. "
            "Pipeline code must never touch the saddl production schema."
        )


def test_pipeline_only_writes_to_allowed_schemas():
    db_writer = (PIPELINE_DIR / "db_writer.py").read_text()
    table_refs = re.findall(r"INTO\s+(\w+\.\w+)", db_writer, re.IGNORECASE)
    table_refs += re.findall(r"UPDATE\s+(\w+\.\w+)", db_writer, re.IGNORECASE)

    for ref in table_refs:
        schema = ref.split(".")[0].lower()
        assert schema in ("sc_raw", "sc_analytics"), (
            f"db_writer writes to forbidden schema: {ref}. "
            "Only sc_raw and sc_analytics are permitted."
        )
