#!/usr/bin/env python3
"""
Schema loading and validation helpers for autostar artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


REQUIRED_SCHEMA_FILES = (
    "disposition-update.schema.json",
    "disposition.schema.json",
    "episode.schema.json",
    "hypothesis-stack.schema.json",
    "memory-pack-manifest.schema.json",
    "mission.schema.json",
    "momentum.schema.json",
    "progress.schema.json",
    "project-state.schema.json",
    "reflection.schema.json",
    "retrieved-dispositions.schema.json",
    "run-summary.schema.json",
    "runtime-profile.schema.json",
    "step-record.schema.json",
    "track-trajectories.schema.json",
    "tracks.schema.json",
)

SCHEMA_ALIASES = {
    filename.replace(".schema.json", ""): filename for filename in REQUIRED_SCHEMA_FILES
}


def script_root() -> Path:
    return Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    return script_root().parent


def schema_dir() -> Path:
    return repo_root() / "schemas"


def schema_path(name: str) -> Path:
    filename = SCHEMA_ALIASES.get(name, name)
    if not filename.endswith(".schema.json"):
        filename = f"{filename}.schema.json"
    return schema_dir() / filename


def load_schema(name: str) -> dict[str, Any]:
    path = schema_path(name)
    return json.loads(path.read_text())


def validate_schema_bundle() -> list[str]:
    errors: list[str] = []
    for filename in REQUIRED_SCHEMA_FILES:
        path = schema_dir() / filename
        if not path.exists():
            errors.append(f"missing schema: {filename}")
            continue
        try:
            schema = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"{filename}: invalid JSON: {exc}")
            continue
        if "$schema" not in schema:
            errors.append(f"{filename}: missing $schema")
        if "title" not in schema:
            errors.append(f"{filename}: missing title")
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # pragma: no cover - library error formatting
            errors.append(f"{filename}: invalid JSON schema: {exc}")
    return errors


def validate_instance(instance: dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema).validate(instance)

