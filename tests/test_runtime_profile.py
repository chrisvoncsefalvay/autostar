from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import runtime_profile
from memory_backend import MemoryProbeResult
from runtime_profile import (
    RuntimeProfile,
    load_profiles,
    match_profile,
    mission_compatibility_issues,
    resolve_profile,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PACK = REPO_ROOT / "tests" / "fixtures" / "memory" / "project-pack"


def make_args(**overrides):
    base = {
        "memory_db": None,
        "memory_connector_url": None,
        "memory_connector_token": None,
        "project_pack": None,
        "project_memory_id": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def load_profile(name: str) -> RuntimeProfile:
    profiles = load_profiles(REPO_ROOT / "autostar-skill")
    return match_profile(profiles, name)


def test_resolve_profile_reports_project_pack_mode():
    profile = load_profile("claude-ai")
    resolution = resolve_profile(profile, REPO_ROOT / "autostar-skill", make_args(project_pack=str(FIXTURE_PACK)))
    assert resolution["memory_surface"]["mode"] == "project_pack"
    assert resolution["memory_surface"]["manual_sync_required"] is True
    assert resolution["effective_profile"]["capabilities"]["long_term_memory"] is True


def test_resolve_profile_reports_short_term_only_when_no_surface():
    profile = load_profile("claude-ai")
    resolution = resolve_profile(profile, REPO_ROOT / "autostar-skill", make_args())
    assert resolution["memory_surface"]["mode"] == "none"
    assert "short-term memory only" in resolution["memory_surface"]["reason"]
    assert resolution["effective_profile"]["capabilities"]["long_term_memory"] is False


def test_resolve_profile_reports_connector_backed_mode(tmp_path):
    original_probe = runtime_profile.connector_probe
    runtime_profile.connector_probe = lambda url, token=None: MemoryProbeResult(
        mode="connector_backed",
        available=True,
        reason="mocked connector is reachable",
        connector_url=url,
    )
    try:
        profile = load_profile("claude-ai")
        resolution = resolve_profile(
            profile,
            REPO_ROOT / "autostar-skill",
            make_args(memory_connector_url="https://memory.example.test"),
        )
    finally:
        runtime_profile.connector_probe = original_probe

    assert resolution["memory_surface"]["mode"] == "connector_backed"
    assert resolution["effective_profile"]["capabilities"]["long_term_memory"] is True


def test_mission_check_can_fail_when_cross_run_learning_is_required_without_surface():
    profile = load_profile("claude-ai")
    resolution = resolve_profile(profile, REPO_ROOT / "autostar-skill", make_args())
    effective = RuntimeProfile(path=profile.path, data=resolution["effective_profile"])

    issues = mission_compatibility_issues(
        effective,
        SimpleNamespace(
            require_structured_choice="basic",
            require_file_read_write="limited",
            require_subprocess=False,
            require_local_html=False,
            require_file_presentation=False,
            require_pause_resume=True,
            require_long_term_memory=True,
            verifier=None,
        ),
    )
    assert any("long-term memory" in issue for issue in issues)
