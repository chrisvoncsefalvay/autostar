#!/usr/bin/env python3
"""
Thin command surface over the canonical memory backend.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from memory_backend import MemoryBackend
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from .memory_backend import MemoryBackend


def load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate the autostar memory backend")
    parser.add_argument("--db", required=True, help="Path to the SQLite memory backend")
    parser.add_argument("--mirror-dir", help="Mirror export directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize the backend and export mirrors")
    subparsers.add_parser("health", help="Emit backend health information")

    lookup = subparsers.add_parser("lookup-priors", help="Retrieve priors for anticipated action intents")
    lookup.add_argument("--project-id", required=True)
    lookup.add_argument("--problem-class", required=True)
    lookup.add_argument("--problem-description", required=True)
    lookup.add_argument("--goal", default="")
    lookup.add_argument("--artifact-description", default="")
    lookup.add_argument("--context-text", default="")
    lookup.add_argument("--action-intent", action="append", required=True)
    lookup.add_argument("--memory-mode", default="direct_backend")
    lookup.add_argument("--output")

    fetch = subparsers.add_parser("fetch-recent-episodes", help="Fetch recent episodic records")
    fetch.add_argument("--project-id", required=True)
    fetch.add_argument("--problem-class")
    fetch.add_argument("--limit", type=int, default=10)

    append_episode = subparsers.add_parser("append-episode", help="Append an episode record from JSON input")
    append_episode.add_argument("--input", required=True)

    summary = subparsers.add_parser("write-run-summary", help="Store a run summary from JSON input")
    summary.add_argument("--input", required=True)

    pending = subparsers.add_parser("list-pending-updates", help="List pending disposition updates")
    pending.add_argument("--project-id")

    apply_updates = subparsers.add_parser("apply-approved-updates", help="Approve and apply pending updates")
    apply_updates.add_argument("--project-id")
    apply_updates.add_argument("--update-id", action="append")
    apply_updates.add_argument("--approved-by", default="user")

    get_state = subparsers.add_parser("get-project-state", help="Get compact project state")
    get_state.add_argument("--project-id", required=True)

    set_state = subparsers.add_parser("set-project-state", help="Set compact project state from JSON input")
    set_state.add_argument("--input", required=True)

    export_pack = subparsers.add_parser("export-project-pack", help="Export a project memory pack")
    export_pack.add_argument("--project-id", required=True)
    export_pack.add_argument("--output-dir", required=True)

    import_pack = subparsers.add_parser("import-project-pack", help="Import a project memory pack")
    import_pack.add_argument("--pack-dir", required=True)

    proposals = subparsers.add_parser("generate-proposals", help="Generate disposition proposals from step records")
    proposals.add_argument("--project-id", required=True)
    proposals.add_argument("--run-id", required=True)
    proposals.add_argument("--problem-class", required=True)
    proposals.add_argument("--steps", required=True)
    proposals.add_argument("--run-summary")
    proposals.add_argument("--auto-apply-small-deltas", action="store_true")

    subparsers.add_parser("export-mirrors", help="Export JSON/JSONL mirrors from the database")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    backend = MemoryBackend(args.db, mirror_dir=args.mirror_dir)

    if args.command == "init":
        print(json.dumps({"health": backend.health(), "mirrors": backend.export_mirrors()}, indent=2))
        return 0
    if args.command == "health":
        print(json.dumps(backend.health(), indent=2))
        return 0
    if args.command == "lookup-priors":
        result = backend.lookup_priors(
            project_id=args.project_id,
            problem_class=args.problem_class,
            anticipated_action_intents=args.action_intent,
            problem_description=args.problem_description,
            goal=args.goal,
            artifact_description=args.artifact_description,
            context_text=args.context_text,
            memory_mode=args.memory_mode,
            output_path=args.output,
        )
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "fetch-recent-episodes":
        print(json.dumps(backend.fetch_recent_episodes(args.project_id, args.problem_class, args.limit), indent=2))
        return 0
    if args.command == "append-episode":
        print(json.dumps(backend.append_episode(load_json(args.input)), indent=2))
        return 0
    if args.command == "write-run-summary":
        print(json.dumps(backend.write_run_summary(load_json(args.input)), indent=2))
        return 0
    if args.command == "list-pending-updates":
        print(json.dumps(backend.list_pending_disposition_updates(args.project_id), indent=2))
        return 0
    if args.command == "apply-approved-updates":
        print(
            json.dumps(
                backend.apply_approved_updates(
                    update_ids=args.update_id,
                    project_id=args.project_id,
                    approved_by=args.approved_by,
                ),
                indent=2,
            )
        )
        return 0
    if args.command == "get-project-state":
        print(json.dumps(backend.get_project_state(args.project_id), indent=2))
        return 0
    if args.command == "set-project-state":
        print(json.dumps(backend.set_project_state(load_json(args.input)), indent=2))
        return 0
    if args.command == "export-project-pack":
        print(json.dumps(backend.export_project_pack(args.project_id, args.output_dir), indent=2))
        return 0
    if args.command == "import-project-pack":
        print(json.dumps(backend.import_project_pack(args.pack_dir), indent=2))
        return 0
    if args.command == "generate-proposals":
        run_summary = load_json(args.run_summary) if args.run_summary else None
        steps = load_json(args.steps)
        print(
            json.dumps(
                backend.generate_disposition_update_proposals(
                    project_id=args.project_id,
                    run_id=args.run_id,
                    problem_class=args.problem_class,
                    step_records=steps,
                    run_summary=run_summary,
                    auto_apply_small_deltas=args.auto_apply_small_deltas,
                ),
                indent=2,
            )
        )
        return 0
    if args.command == "export-mirrors":
        print(json.dumps(backend.export_mirrors(), indent=2))
        return 0

    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

