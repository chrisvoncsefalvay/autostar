from __future__ import annotations

import json
from pathlib import Path

from memory_backend import MemoryBackend


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "memory"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def make_backend(tmp_path: Path) -> MemoryBackend:
    return MemoryBackend(tmp_path / "memory.sqlite3", mirror_dir=tmp_path / "mirror")


def test_lookup_priors_prefers_exact_problem_class_and_action_intent(tmp_path):
    backend = make_backend(tmp_path)
    exact = load_fixture("disposition.json")
    backend.put_disposition(exact)
    backend.put_disposition(
        {
            **exact,
            "disposition_id": "disp_other",
            "problem_class": "python_docs_cleanup",
            "action_intent": "improve_readability",
            "prior": "Improve readability by shortening long paragraphs.",
            "confidence": 0.9,
        }
    )

    output_path = tmp_path / "retrieved.json"
    result = backend.lookup_priors(
        project_id="project_demo",
        problem_class="python_api_optimisation",
        anticipated_action_intents=["improve_type_correctness"],
        problem_description="Tighten FastAPI typing and pyright signal",
        goal="Reduce type errors in API handlers",
        artifact_description="FastAPI authentication handler",
        output_path=output_path,
    )

    matches = result["items_by_action_intent"]["improve_type_correctness"]
    assert matches[0]["disposition_id"] == "disp_demo_type"
    assert matches[0]["retrieval_score"] > matches[1]["retrieval_score"]
    assert output_path.exists()


def test_generate_and_apply_reinforce_proposal(tmp_path):
    backend = make_backend(tmp_path)
    disposition = load_fixture("disposition.json")
    backend.put_disposition(disposition)
    run_summary = load_fixture("run-summary.json")

    steps = [
        {
            "id": "run_demo_1_r2_l1_s1",
            "step_kind": "mutation",
            "action_intent": "improve_type_correctness",
            "hypothesis": "Return type annotations first improve pyright signal.",
            "composite": 0.78,
            "outcome": "keep",
            "source_dispositions": [
                {
                    "disposition_id": disposition["disposition_id"],
                    "problem_class": disposition["problem_class"],
                    "action_intent": disposition["action_intent"],
                    "version": disposition["version"],
                }
            ],
        }
    ]

    proposals = backend.generate_disposition_update_proposals(
        project_id="project_demo",
        run_id="run_demo_1",
        problem_class="python_api_optimisation",
        step_records=steps,
        run_summary=run_summary,
        auto_apply_small_deltas=False,
    )

    reinforce = next(item for item in proposals if item["proposal_type"] == "reinforce")
    assert reinforce["status"] == "pending"

    applied = backend.apply_approved_updates(update_ids=[reinforce["update_id"]], approved_by="tester")
    assert applied[0]["status"] == "applied"

    updated = backend.get_disposition("project_demo", "python_api_optimisation", "improve_type_correctness")
    assert updated is not None
    assert updated["version"] == disposition["version"] + 1
    assert updated["confidence"] > disposition["confidence"]


def test_export_and_import_project_pack_round_trip(tmp_path):
    backend = make_backend(tmp_path / "source")
    backend.put_disposition(load_fixture("disposition.json"))
    backend.append_episode(load_fixture("episode.json"))
    backend.write_run_summary(load_fixture("run-summary.json"))
    backend.set_project_state(
        json.loads((FIXTURES / "project-pack" / "project-state.json").read_text())
    )

    pack_dir = tmp_path / "pack"
    manifest = backend.export_project_pack("project_demo", pack_dir)
    assert manifest["manual_sync_required"] is True
    assert (pack_dir / "manifest.json").exists()
    assert (pack_dir / "latest-relevant-priors.json").exists()

    imported = make_backend(tmp_path / "imported")
    imported.import_project_pack(pack_dir)

    dispositions = imported.list_dispositions("project_demo")
    summaries = imported.list_run_summaries("project_demo")
    episodes = imported.fetch_recent_episodes("project_demo")

    assert len(dispositions) == 1
    assert len(summaries) == 1
    assert len(episodes) == 1


def test_project_pack_fixture_supports_manual_sync_workflow(tmp_path):
    backend = make_backend(tmp_path / "fixture")
    fixture_pack = FIXTURES / "project-pack"
    backend.import_project_pack(fixture_pack)

    retrieved = backend.lookup_priors(
        project_id="project_demo",
        problem_class="python_api_optimisation",
        anticipated_action_intents=["improve_type_correctness"],
        problem_description="Need a prior for API typing cleanup",
        memory_mode="project_pack",
    )
    assert retrieved["items_by_action_intent"]["improve_type_correctness"][0]["disposition_id"] == "disp_demo_type"

    backend.write_run_summary(
        {
            **load_fixture("run-summary.json"),
            "run_id": "run_demo_2",
            "completed_at": "2026-03-23T12:00:00Z",
            "memory_mode": "project_pack",
            "disposition_updates_proposed": [],
        }
    )
    exported = backend.export_project_pack("project_demo", tmp_path / "out-pack")
    assert exported["manual_sync_required"] is True
    run_summaries = (tmp_path / "out-pack" / "run-summaries.jsonl").read_text()
    assert "run_demo_2" in run_summaries

