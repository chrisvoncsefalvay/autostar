from __future__ import annotations

import json
from pathlib import Path

from schema_tools import validate_instance, validate_schema_bundle


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "memory"


def test_schema_bundle_is_valid():
    assert validate_schema_bundle() == []


def test_memory_fixtures_validate_against_schemas():
    validate_instance(json.loads((FIXTURES / "disposition.json").read_text()), "disposition")
    validate_instance(json.loads((FIXTURES / "episode.json").read_text()), "episode")
    validate_instance(json.loads((FIXTURES / "run-summary.json").read_text()), "run-summary")
    validate_instance(json.loads((FIXTURES / "project-pack" / "manifest.json").read_text()), "memory-pack-manifest")
    validate_instance(json.loads((FIXTURES / "project-pack" / "project-state.json").read_text()), "project-state")

