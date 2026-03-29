#!/usr/bin/env python3
"""
Canonical persistent memory backend for autostar.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from schema_tools import validate_instance
except ModuleNotFoundError:  # pragma: no cover - direct execution fallback
    from .schema_tools import validate_instance


GRAM_DIMENSIONS = 512
WORD_PATTERN = re.compile(r"[a-z0-9]+")
PROJECT_PACK_VERSION = "1.0"
SHORT_TERM_ONLY_MESSAGE = "Long-term memory unavailable; running with short-term memory only."


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def stable_hash(text: str, prefix: str) -> str:
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()
    return f"{prefix}_{digest}"


def dump_json(data: Any, path: Path) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def normalize_text(text: str) -> str:
    return " ".join(WORD_PATTERN.findall(text.lower()))


def iter_grams(text: str) -> Iterable[tuple[str, float]]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    tokens = normalized.split()
    grams: list[tuple[str, float]] = []
    for token in tokens:
        grams.append((f"w:{token}", 1.0))
    for left, right in zip(tokens, tokens[1:]):
        grams.append((f"wb:{left}_{right}", 1.35))
    compact = normalized.replace(" ", "_")
    for size, weight in ((3, 0.45), (4, 0.3)):
        if len(compact) < size:
            continue
        for index in range(len(compact) - size + 1):
            grams.append((f"c{size}:{compact[index:index + size]}", weight))
    return grams


def vectorize(text: str, dimensions: int = GRAM_DIMENSIONS) -> dict[int, float]:
    buckets: dict[int, float] = defaultdict(float)
    for gram, weight in iter_grams(text):
        digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        buckets[bucket] += weight
    norm = math.sqrt(sum(value * value for value in buckets.values()))
    if norm == 0:
        return {}
    return {bucket: value / norm for bucket, value in buckets.items()}


def cosine_similarity(left: dict[int, float], right: dict[int, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(bucket, 0.0) for bucket, value in left.items())


def unique_items(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


@dataclass(frozen=True)
class MemoryProbeResult:
    mode: str
    available: bool
    reason: str
    manual_sync_required: bool = False
    backend_path: str | None = None
    connector_url: str | None = None
    project_pack: str | None = None
    project_memory_id: str | None = None


class MemoryBackend:
    """
    SQLite-backed source of truth for long-term autostar memory.
    """

    def __init__(self, db_path: str | Path, mirror_dir: str | Path | None = None, auto_sync: bool = True):
        self.db_path = Path(db_path)
        self.mirror_dir = Path(mirror_dir) if mirror_dir else self.db_path.parent / "mirror"
        self.auto_sync = auto_sync
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.mirror_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS episodes (
                    episode_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    round_id TEXT NOT NULL,
                    problem_class TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_episodes_lookup
                    ON episodes(project_id, problem_class, recorded_at DESC);

                CREATE TABLE IF NOT EXISTS run_summaries (
                    run_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    problem_class TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_run_summaries_lookup
                    ON run_summaries(project_id, problem_class, completed_at DESC);

                CREATE TABLE IF NOT EXISTS dispositions (
                    disposition_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    problem_class TEXT NOT NULL,
                    action_intent TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_version INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    last_updated TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_dispositions_key
                    ON dispositions(project_id, problem_class, action_intent);

                CREATE TABLE IF NOT EXISTS disposition_versions (
                    disposition_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    project_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY(disposition_id, version)
                );

                CREATE TABLE IF NOT EXISTS disposition_updates (
                    update_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    problem_class TEXT NOT NULL,
                    action_intent TEXT NOT NULL,
                    disposition_id TEXT,
                    proposal_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    applied_at TEXT,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pending_updates
                    ON disposition_updates(project_id, status, created_at DESC);

                CREATE TABLE IF NOT EXISTS project_state (
                    project_id TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                ("schema_version", PROJECT_PACK_VERSION),
            )

    @classmethod
    def probe_local_backend(cls, db_path: str | Path) -> MemoryProbeResult:
        try:
            backend = cls(db_path, auto_sync=False)
            backend.health()
        except Exception as exc:
            return MemoryProbeResult(
                mode="none",
                available=False,
                reason=f"local backend unavailable: {exc}",
            )
        return MemoryProbeResult(
            mode="direct_backend",
            available=True,
            reason="local SQLite backend is available",
            backend_path=str(Path(db_path)),
        )

    def health(self) -> dict[str, Any]:
        with self._connect() as connection:
            version = connection.execute(
                "SELECT value FROM metadata WHERE key = ?",
                ("schema_version",),
            ).fetchone()
        return {
            "ok": True,
            "db_path": str(self.db_path),
            "mirror_dir": str(self.mirror_dir),
            "schema_version": version["value"] if version else None,
        }

    def _sync_if_needed(self) -> None:
        if self.auto_sync:
            self.export_mirrors()

    def _row_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        return json.loads(row["payload_json"])

    def _upsert_disposition(self, connection: sqlite3.Connection, disposition: dict[str, Any]) -> None:
        validate_instance(disposition, "disposition")
        connection.execute(
            """
            INSERT OR REPLACE INTO dispositions(
                disposition_id, project_id, problem_class, action_intent, status,
                current_version, confidence, last_updated, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                disposition["disposition_id"],
                disposition["project_id"],
                disposition["problem_class"],
                disposition["action_intent"],
                disposition["status"],
                disposition["version"],
                disposition["confidence"],
                disposition["last_updated"],
                json.dumps(disposition, sort_keys=True),
            ),
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO disposition_versions(
                disposition_id, version, project_id, updated_at, payload_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                disposition["disposition_id"],
                disposition["version"],
                disposition["project_id"],
                disposition["last_updated"],
                json.dumps(disposition, sort_keys=True),
            ),
        )

    def list_dispositions(self, project_id: str, include_retired: bool = False) -> list[dict[str, Any]]:
        query = "SELECT payload_json FROM dispositions WHERE project_id = ?"
        params: list[Any] = [project_id]
        if not include_retired:
            query += " AND status != 'retired'"
        query += " ORDER BY problem_class, action_intent"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def get_disposition(self, project_id: str, problem_class: str, action_intent: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM dispositions
                WHERE project_id = ? AND problem_class = ? AND action_intent = ?
                """,
                (project_id, problem_class, action_intent),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def put_disposition(self, disposition: dict[str, Any]) -> dict[str, Any]:
        if "schema_version" not in disposition:
            disposition["schema_version"] = PROJECT_PACK_VERSION
        if "created_at" not in disposition:
            disposition["created_at"] = utc_now()
        if "last_updated" not in disposition:
            disposition["last_updated"] = utc_now()
        with self._connect() as connection:
            self._upsert_disposition(connection, disposition)
        self._sync_if_needed()
        return disposition

    def append_episode(self, episode: dict[str, Any]) -> dict[str, Any]:
        if "schema_version" not in episode:
            episode["schema_version"] = PROJECT_PACK_VERSION
        if "episode_id" not in episode:
            episode["episode_id"] = stable_hash(
                "::".join(
                    [
                        episode["project_id"],
                        episode["run_id"],
                        episode["round_id"],
                        episode.get("problem_class", ""),
                    ]
                ),
                "episode",
            )
        if "recorded_at" not in episode:
            episode["recorded_at"] = utc_now()
        validate_instance(episode, "episode")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO episodes(
                    episode_id, project_id, run_id, round_id,
                    problem_class, recorded_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode["episode_id"],
                    episode["project_id"],
                    episode["run_id"],
                    episode["round_id"],
                    episode["problem_class"],
                    episode["recorded_at"],
                    json.dumps(episode, sort_keys=True),
                ),
            )
        self._sync_if_needed()
        return episode

    def fetch_recent_episodes(
        self,
        project_id: str,
        problem_class: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        query = "SELECT payload_json FROM episodes WHERE project_id = ?"
        params: list[Any] = [project_id]
        if problem_class:
            query += " AND problem_class = ?"
            params.append(problem_class)
        query += " ORDER BY recorded_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def write_run_summary(self, run_summary: dict[str, Any]) -> dict[str, Any]:
        if "schema_version" not in run_summary:
            run_summary["schema_version"] = PROJECT_PACK_VERSION
        if "completed_at" not in run_summary:
            run_summary["completed_at"] = utc_now()
        validate_instance(run_summary, "run-summary")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO run_summaries(
                    run_id, project_id, problem_class, completed_at, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_summary["run_id"],
                    run_summary["project_id"],
                    run_summary["problem_class"],
                    run_summary["completed_at"],
                    json.dumps(run_summary, sort_keys=True),
                ),
            )
        self._sync_if_needed()
        return run_summary

    def list_run_summaries(self, project_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        query = "SELECT payload_json FROM run_summaries WHERE project_id = ? ORDER BY completed_at DESC"
        params: list[Any] = [project_id]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def get_project_state(self, project_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM project_state WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def set_project_state(self, state: dict[str, Any]) -> dict[str, Any]:
        if "schema_version" not in state:
            state["schema_version"] = PROJECT_PACK_VERSION
        if "updated_at" not in state:
            state["updated_at"] = utc_now()
        validate_instance(state, "project-state")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO project_state(project_id, updated_at, payload_json)
                VALUES (?, ?, ?)
                """,
                (
                    state["project_id"],
                    state["updated_at"],
                    json.dumps(state, sort_keys=True),
                ),
            )
        self._sync_if_needed()
        return state

    def lookup_priors(
        self,
        *,
        project_id: str,
        problem_class: str,
        anticipated_action_intents: list[str],
        problem_description: str,
        goal: str = "",
        artifact_description: str = "",
        context_text: str = "",
        top_k: int = 3,
        min_confidence: float = 0.4,
        memory_mode: str = "direct_backend",
        output_path: str | Path | None = None,
    ) -> dict[str, Any]:
        dispositions = self.list_dispositions(project_id)
        items_by_intent: dict[str, list[dict[str, Any]]] = {}
        for action_intent in anticipated_action_intents:
            query_text = " ".join(
                part
                for part in (
                    problem_class,
                    action_intent,
                    problem_description,
                    goal,
                    artifact_description,
                    context_text,
                )
                if part
            )
            query_vector = vectorize(query_text)
            scored: list[dict[str, Any]] = []
            for disposition in dispositions:
                if disposition["confidence"] < min_confidence:
                    continue
                candidate_text = " ".join(
                    part
                    for part in (
                        disposition["problem_class"],
                        disposition["action_intent"],
                        disposition["prior"],
                        disposition.get("override_conditions") or "",
                        disposition.get("source") or "",
                    )
                    if part
                )
                semantic = cosine_similarity(query_vector, vectorize(candidate_text))
                exact_match_boost = 0.0
                if disposition["problem_class"] == problem_class:
                    exact_match_boost += 0.25
                elif problem_class in disposition["problem_class"] or disposition["problem_class"] in problem_class:
                    exact_match_boost += 0.1
                if disposition["action_intent"] == action_intent:
                    exact_match_boost += 0.3
                retrieval_score = clamp((semantic * 0.6) + exact_match_boost + (disposition["confidence"] * 0.1))
                scored.append(
                    {
                        "disposition_id": disposition["disposition_id"],
                        "problem_class": disposition["problem_class"],
                        "action_intent": disposition["action_intent"],
                        "version": disposition["version"],
                        "retrieval_score": round(retrieval_score, 6),
                        "semantic_similarity": round(clamp(semantic), 6),
                        "exact_match_boost": round(exact_match_boost, 6),
                        "confidence": disposition["confidence"],
                        "prior": disposition["prior"],
                        "override_conditions": disposition.get("override_conditions"),
                    }
                )
            ranked = sorted(scored, key=lambda item: item["retrieval_score"], reverse=True)[:top_k]
            items_by_intent[action_intent] = ranked
        snapshot = {
            "schema_version": PROJECT_PACK_VERSION,
            "run_id": stable_hash(f"{project_id}:{problem_class}:{utc_now()}", "retrieval"),
            "project_id": project_id,
            "problem_class": problem_class,
            "memory_mode": memory_mode,
            "retrieved_at": utc_now(),
            "anticipated_action_intents": anticipated_action_intents,
            "items_by_action_intent": items_by_intent,
        }
        validate_instance(snapshot, "retrieved-dispositions")
        if output_path is not None:
            dump_json(snapshot, Path(output_path))
        return snapshot

    def queue_disposition_update(self, proposal: dict[str, Any]) -> dict[str, Any]:
        if "schema_version" not in proposal:
            proposal["schema_version"] = PROJECT_PACK_VERSION
        if "created_at" not in proposal:
            proposal["created_at"] = utc_now()
        if "status" not in proposal:
            proposal["status"] = "pending"
        validate_instance(proposal, "disposition-update")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO disposition_updates(
                    update_id, project_id, run_id, problem_class, action_intent,
                    disposition_id, proposal_type, status, created_at, applied_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal["update_id"],
                    proposal["project_id"],
                    proposal["run_id"],
                    proposal["problem_class"],
                    proposal["action_intent"],
                    proposal.get("disposition_id"),
                    proposal["proposal_type"],
                    proposal["status"],
                    proposal["created_at"],
                    proposal.get("applied_at"),
                    json.dumps(proposal, sort_keys=True),
                ),
            )
        self._sync_if_needed()
        return proposal

    def list_pending_disposition_updates(self, project_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT payload_json FROM disposition_updates WHERE status = 'pending'"
        params: list[Any] = []
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def generate_disposition_update_proposals(
        self,
        *,
        project_id: str,
        run_id: str,
        problem_class: str,
        step_records: list[dict[str, Any]],
        run_summary: dict[str, Any] | None = None,
        auto_apply_small_deltas: bool = False,
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for step in step_records:
            intent = step.get("action_intent")
            if not intent:
                continue
            grouped[intent].append(step)

        created: list[dict[str, Any]] = []
        for action_intent, records in grouped.items():
            evidence_steps = [record for record in records if record.get("step_kind") != "memory_update"]
            if not evidence_steps:
                continue
            source_refs = [
                source
                for record in evidence_steps
                for source in record.get("source_dispositions", [])
            ]
            deltas = [self._step_delta(record, run_summary) for record in evidence_steps]
            avg_delta = sum(deltas) / len(deltas)
            positive = sum(1 for delta in deltas if delta > 0)
            negative = sum(1 for delta in deltas if delta <= 0)
            if source_refs:
                source_by_id = {source["disposition_id"]: source for source in source_refs}
                for disposition_id, source in source_by_id.items():
                    existing = self.get_disposition(project_id, source["problem_class"], source["action_intent"])
                    if existing is None:
                        continue
                    proposal = None
                    if any(record.get("override_condition") for record in evidence_steps):
                        proposal = self._build_extend_proposal(existing, run_id, evidence_steps)
                    elif avg_delta > 0.03 and positive >= negative:
                        proposal = self._build_reinforce_proposal(existing, run_id, evidence_steps, avg_delta)
                    elif avg_delta < 0.0 or negative > positive:
                        proposal = self._build_weaken_proposal(existing, run_id, evidence_steps, avg_delta)
                    if proposal:
                        if proposal["proposal_type"] in {"reinforce", "weaken"} and auto_apply_small_deltas:
                            proposal["requires_approval"] = abs(proposal.get("confidence_delta", 0.0)) >= 0.05
                        self.queue_disposition_update(proposal)
                        created.append(proposal)
                        if auto_apply_small_deltas and not proposal["requires_approval"]:
                            self.apply_approved_updates(update_ids=[proposal["update_id"]], approved_by="auto")
                        if proposal["proposal_type"] == "weaken":
                            projected = clamp(existing["confidence"] + proposal.get("confidence_delta", 0.0))
                            if projected < 0.2 and (existing["n_supporting"] + existing["n_refuting"]) >= 10:
                                retire = self._build_retire_proposal(existing, run_id, evidence_steps)
                                self.queue_disposition_update(retire)
                                created.append(retire)
            else:
                successful = [record for record, delta in zip(evidence_steps, deltas) if delta > 0]
                if successful:
                    proposal = self._build_create_proposal(
                        project_id=project_id,
                        problem_class=problem_class,
                        action_intent=action_intent,
                        run_id=run_id,
                        evidence_steps=successful,
                        run_summary=run_summary,
                    )
                    self.queue_disposition_update(proposal)
                    created.append(proposal)

            for record in evidence_steps:
                if record.get("fork_problem_class") or record.get("fork_action_intent"):
                    fork = self._build_fork_proposal(
                        project_id=project_id,
                        problem_class=problem_class,
                        action_intent=action_intent,
                        run_id=run_id,
                        record=record,
                    )
                    self.queue_disposition_update(fork)
                    created.append(fork)
        return created

    def _step_delta(self, record: dict[str, Any], run_summary: dict[str, Any] | None) -> float:
        if "composite_delta" in record and record["composite_delta"] is not None:
            return float(record["composite_delta"])
        baseline = 0.0
        if run_summary:
            baseline_scores = run_summary.get("baseline_scores", {})
            baseline = float(baseline_scores.get("composite", 0.0))
        composite = record.get("composite")
        if composite is None:
            return 0.0
        return float(composite) - baseline

    def _build_reinforce_proposal(
        self,
        existing: dict[str, Any],
        run_id: str,
        evidence_steps: list[dict[str, Any]],
        avg_delta: float,
    ) -> dict[str, Any]:
        delta = round(min(0.04, max(0.01, avg_delta / 2)), 4)
        exemplars = unique_items(
            existing["exemplars_supporting"] + [step["id"] for step in evidence_steps if step.get("id")]
        )
        proposed = dict(existing)
        proposed["version"] = existing["version"] + 1
        proposed["confidence"] = round(clamp(existing["confidence"] + delta), 4)
        proposed["n_supporting"] = existing["n_supporting"] + len(evidence_steps)
        proposed["exemplars_supporting"] = exemplars
        proposed["last_updated"] = utc_now()
        return {
            "schema_version": PROJECT_PACK_VERSION,
            "update_id": stable_hash(f"{existing['disposition_id']}:{run_id}:reinforce", "upd"),
            "project_id": existing["project_id"],
            "run_id": run_id,
            "problem_class": existing["problem_class"],
            "action_intent": existing["action_intent"],
            "disposition_id": existing["disposition_id"],
            "proposal_type": "reinforce",
            "status": "pending",
            "created_at": utc_now(),
            "applied_at": None,
            "requires_approval": True,
            "confidence_delta": delta,
            "rationale": f"Retrieved prior outperformed baseline by {avg_delta:.3f} on average across {len(evidence_steps)} steps.",
            "source_exemplars": [step["id"] for step in evidence_steps if step.get("id")],
            "refuting_exemplars": [],
            "target_version": proposed["version"],
            "approved_by": None,
            "proposed_record": proposed,
        }

    def _build_weaken_proposal(
        self,
        existing: dict[str, Any],
        run_id: str,
        evidence_steps: list[dict[str, Any]],
        avg_delta: float,
    ) -> dict[str, Any]:
        delta = round(max(-0.04, min(-0.01, avg_delta / 2 if avg_delta else -0.02)), 4)
        exemplars = unique_items(
            existing["exemplars_refuting"] + [step["id"] for step in evidence_steps if step.get("id")]
        )
        proposed = dict(existing)
        proposed["version"] = existing["version"] + 1
        proposed["confidence"] = round(clamp(existing["confidence"] + delta), 4)
        proposed["n_refuting"] = existing["n_refuting"] + len(evidence_steps)
        proposed["exemplars_refuting"] = exemplars
        proposed["last_updated"] = utc_now()
        return {
            "schema_version": PROJECT_PACK_VERSION,
            "update_id": stable_hash(f"{existing['disposition_id']}:{run_id}:weaken", "upd"),
            "project_id": existing["project_id"],
            "run_id": run_id,
            "problem_class": existing["problem_class"],
            "action_intent": existing["action_intent"],
            "disposition_id": existing["disposition_id"],
            "proposal_type": "weaken",
            "status": "pending",
            "created_at": utc_now(),
            "applied_at": None,
            "requires_approval": True,
            "confidence_delta": delta,
            "rationale": f"Retrieved prior underperformed baseline by {avg_delta:.3f} on average across {len(evidence_steps)} steps.",
            "source_exemplars": [],
            "refuting_exemplars": [step["id"] for step in evidence_steps if step.get("id")],
            "target_version": proposed["version"],
            "approved_by": None,
            "proposed_record": proposed,
        }

    def _build_extend_proposal(
        self,
        existing: dict[str, Any],
        run_id: str,
        evidence_steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        conditions = unique_items(
            [existing.get("override_conditions") or ""]
            + [record.get("override_condition", "") for record in evidence_steps]
        )
        proposed = dict(existing)
        proposed["version"] = existing["version"] + 1
        proposed["override_conditions"] = "; ".join(condition for condition in conditions if condition) or None
        proposed["last_updated"] = utc_now()
        return {
            "schema_version": PROJECT_PACK_VERSION,
            "update_id": stable_hash(f"{existing['disposition_id']}:{run_id}:extend", "upd"),
            "project_id": existing["project_id"],
            "run_id": run_id,
            "problem_class": existing["problem_class"],
            "action_intent": existing["action_intent"],
            "disposition_id": existing["disposition_id"],
            "proposal_type": "extend",
            "status": "pending",
            "created_at": utc_now(),
            "applied_at": None,
            "requires_approval": True,
            "confidence_delta": 0.0,
            "rationale": "Observed an override condition not captured by the current disposition.",
            "source_exemplars": [step["id"] for step in evidence_steps if step.get("override_condition")],
            "refuting_exemplars": [],
            "target_version": proposed["version"],
            "approved_by": None,
            "proposed_record": proposed,
        }

    def _build_retire_proposal(
        self,
        existing: dict[str, Any],
        run_id: str,
        evidence_steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        proposed = dict(existing)
        proposed["version"] = existing["version"] + 1
        proposed["status"] = "retired"
        proposed["last_updated"] = utc_now()
        return {
            "schema_version": PROJECT_PACK_VERSION,
            "update_id": stable_hash(f"{existing['disposition_id']}:{run_id}:retire", "upd"),
            "project_id": existing["project_id"],
            "run_id": run_id,
            "problem_class": existing["problem_class"],
            "action_intent": existing["action_intent"],
            "disposition_id": existing["disposition_id"],
            "proposal_type": "retire",
            "status": "pending",
            "created_at": utc_now(),
            "applied_at": None,
            "requires_approval": True,
            "confidence_delta": 0.0,
            "rationale": "Disposition confidence fell below retirement threshold after repeated refutation.",
            "source_exemplars": [],
            "refuting_exemplars": [step["id"] for step in evidence_steps if step.get("id")],
            "target_version": proposed["version"],
            "approved_by": None,
            "proposed_record": proposed,
        }

    def _build_create_proposal(
        self,
        *,
        project_id: str,
        problem_class: str,
        action_intent: str,
        run_id: str,
        evidence_steps: list[dict[str, Any]],
        run_summary: dict[str, Any] | None,
    ) -> dict[str, Any]:
        prior = next(
            (
                step.get("hypothesis")
                for step in evidence_steps
                if step.get("hypothesis")
            ),
            None,
        )
        if prior is None and run_summary:
            prior = next(iter(run_summary.get("what_worked", [])), None)
        prior = prior or f"Successful pattern observed for {problem_class} / {action_intent}."
        disposition_id = stable_hash(f"{project_id}:{problem_class}:{action_intent}", "disp")
        proposed_record = {
            "schema_version": PROJECT_PACK_VERSION,
            "disposition_id": disposition_id,
            "project_id": project_id,
            "problem_class": problem_class,
            "action_intent": action_intent,
            "version": 1,
            "status": "active",
            "prior": prior,
            "confidence": 0.55,
            "n_supporting": len(evidence_steps),
            "n_refuting": 0,
            "exemplars_supporting": [step["id"] for step in evidence_steps if step.get("id")],
            "exemplars_refuting": [],
            "provenance": "learned_from_run",
            "source": None,
            "override_conditions": None,
            "created_at": utc_now(),
            "last_updated": utc_now(),
            "policy_version_at_creation": 1,
            "evidence_summary": f"Created from {len(evidence_steps)} successful step(s) in {run_id}.",
        }
        return {
            "schema_version": PROJECT_PACK_VERSION,
            "update_id": stable_hash(f"{disposition_id}:{run_id}:create", "upd"),
            "project_id": project_id,
            "run_id": run_id,
            "problem_class": problem_class,
            "action_intent": action_intent,
            "disposition_id": None,
            "proposal_type": "create",
            "status": "pending",
            "created_at": utc_now(),
            "applied_at": None,
            "requires_approval": True,
            "confidence_delta": 0.0,
            "rationale": "No relevant prior existed; observed successful pattern worth encoding as a new disposition.",
            "source_exemplars": [step["id"] for step in evidence_steps if step.get("id")],
            "refuting_exemplars": [],
            "target_version": 1,
            "approved_by": None,
            "proposed_record": proposed_record,
        }

    def _build_fork_proposal(
        self,
        *,
        project_id: str,
        problem_class: str,
        action_intent: str,
        run_id: str,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        fork_problem_class = record.get("fork_problem_class") or f"{problem_class}_fork"
        fork_action_intent = record.get("fork_action_intent") or action_intent
        disposition_id = stable_hash(f"{project_id}:{fork_problem_class}:{fork_action_intent}", "disp")
        proposed_record = {
            "schema_version": PROJECT_PACK_VERSION,
            "disposition_id": disposition_id,
            "project_id": project_id,
            "problem_class": fork_problem_class,
            "action_intent": fork_action_intent,
            "version": 1,
            "status": "active",
            "prior": record.get("fork_prior") or record.get("hypothesis") or "Forked disposition proposal.",
            "confidence": 0.5,
            "n_supporting": 1,
            "n_refuting": 0,
            "exemplars_supporting": [record.get("id")] if record.get("id") else [],
            "exemplars_refuting": [],
            "provenance": "learned_from_run",
            "source": None,
            "override_conditions": None,
            "created_at": utc_now(),
            "last_updated": utc_now(),
            "policy_version_at_creation": 1,
            "evidence_summary": "Fork created from explicit divergence evidence.",
        }
        return {
            "schema_version": PROJECT_PACK_VERSION,
            "update_id": stable_hash(f"{disposition_id}:{run_id}:fork", "upd"),
            "project_id": project_id,
            "run_id": run_id,
            "problem_class": problem_class,
            "action_intent": action_intent,
            "disposition_id": None,
            "proposal_type": "fork",
            "status": "pending",
            "created_at": utc_now(),
            "applied_at": None,
            "requires_approval": True,
            "confidence_delta": 0.0,
            "rationale": "Evidence suggests the current problem class should be split into a forked sub-class.",
            "source_exemplars": [record["id"]] if record.get("id") else [],
            "refuting_exemplars": [],
            "target_version": 1,
            "approved_by": None,
            "proposed_record": proposed_record,
        }

    def apply_approved_updates(
        self,
        *,
        update_ids: list[str] | None = None,
        project_id: str | None = None,
        approved_by: str = "user",
    ) -> list[dict[str, Any]]:
        query = "SELECT payload_json FROM disposition_updates WHERE status IN ('approved', 'pending')"
        params: list[Any] = []
        if update_ids:
            placeholders = ", ".join("?" for _ in update_ids)
            query += f" AND update_id IN ({placeholders})"
            params.extend(update_ids)
        elif project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
            proposals = [json.loads(row["payload_json"]) for row in rows]
            applied: list[dict[str, Any]] = []
            for proposal in proposals:
                proposal["status"] = "approved"
                proposal["approved_by"] = approved_by
                proposal["applied_at"] = utc_now()
                if proposal["proposal_type"] in {"create", "fork"}:
                    self._upsert_disposition(connection, proposal["proposed_record"])
                elif proposal["proposal_type"] in {"reinforce", "weaken", "extend", "retire"}:
                    self._upsert_disposition(connection, proposal["proposed_record"])
                proposal["status"] = "applied"
                connection.execute(
                    """
                    INSERT OR REPLACE INTO disposition_updates(
                        update_id, project_id, run_id, problem_class, action_intent,
                        disposition_id, proposal_type, status, created_at, applied_at, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        proposal["update_id"],
                        proposal["project_id"],
                        proposal["run_id"],
                        proposal["problem_class"],
                        proposal["action_intent"],
                        proposal.get("disposition_id"),
                        proposal["proposal_type"],
                        proposal["status"],
                        proposal["created_at"],
                        proposal["applied_at"],
                        json.dumps(proposal, sort_keys=True),
                    ),
                )
                applied.append(proposal)
        self._sync_if_needed()
        return applied

    def build_latest_relevant_priors(self, project_id: str, limit: int = 25) -> dict[str, Any]:
        dispositions = self.list_dispositions(project_id)
        ranked = sorted(
            dispositions,
            key=lambda item: (
                item["confidence"] * (item["n_supporting"] + 1) / (item["n_supporting"] + item["n_refuting"] + 1)
            ),
            reverse=True,
        )[:limit]
        return {
            "schema_version": PROJECT_PACK_VERSION,
            "project_id": project_id,
            "generated_at": utc_now(),
            "items": ranked,
        }

    def export_project_pack(self, project_id: str, pack_dir: str | Path) -> dict[str, Any]:
        directory = Path(pack_dir)
        directory.mkdir(parents=True, exist_ok=True)
        dispositions = self.list_dispositions(project_id, include_retired=True)
        episodes = self.fetch_recent_episodes(project_id, limit=1000)
        run_summaries = self.list_run_summaries(project_id)
        state = self.get_project_state(project_id) or {
            "schema_version": PROJECT_PACK_VERSION,
            "project_id": project_id,
            "updated_at": utc_now(),
            "compact_state": None,
            "memory_scope": None,
            "project_memory_id": project_id,
            "current_problem_classes": unique_items(summary["problem_class"] for summary in run_summaries),
            "recent_run_ids": [summary["run_id"] for summary in run_summaries[:10]],
            "pending_disposition_update_ids": [],
            "last_pack_export_at": None,
            "last_pack_import_at": None,
        }
        latest_relevant = self.build_latest_relevant_priors(project_id)
        pending_updates = self.list_pending_disposition_updates(project_id)
        state["last_pack_export_at"] = utc_now()
        state["pending_disposition_update_ids"] = [item["update_id"] for item in pending_updates]
        self.set_project_state(state)

        dispositions_path = directory / "dispositions.json"
        episodes_path = directory / "episodes.jsonl"
        run_summaries_path = directory / "run-summaries.jsonl"
        state_path = directory / "project-state.json"
        latest_path = directory / "latest-relevant-priors.json"
        pending_path = directory / "pending-disposition-updates.json"

        dump_json(
            {
                "schema_version": PROJECT_PACK_VERSION,
                "project_id": project_id,
                "items": dispositions,
            },
            dispositions_path,
        )
        write_jsonl(episodes_path, episodes)
        write_jsonl(run_summaries_path, run_summaries)
        dump_json(state, state_path)
        dump_json(latest_relevant, latest_path)
        dump_json(
            {
                "schema_version": PROJECT_PACK_VERSION,
                "project_id": project_id,
                "items": pending_updates,
            },
            pending_path,
        )

        manifest = {
            "schema_version": PROJECT_PACK_VERSION,
            "pack_id": str(uuid.uuid4()),
            "project_id": project_id,
            "generated_at": utc_now(),
            "manual_sync_required": True,
            "source_of_truth": "sqlite3",
            "source_backend": {"path": str(self.db_path)},
            "files": [
                {"path": "manifest.json", "kind": "manifest", "format": "json", "description": "Pack manifest"},
                {"path": "dispositions.json", "kind": "dispositions", "format": "json", "description": "Current disposition library snapshot"},
                {"path": "episodes.jsonl", "kind": "episodes", "format": "jsonl", "description": "Episode log"},
                {"path": "run-summaries.jsonl", "kind": "run_summaries", "format": "jsonl", "description": "Completed-run summaries"},
                {"path": "project-state.json", "kind": "project_state", "format": "json", "description": "Compact project state"},
                {"path": "latest-relevant-priors.json", "kind": "latest_relevant_priors", "format": "json", "description": "Compact prior cache for Claude.ai loading"},
                {"path": "pending-disposition-updates.json", "kind": "pending_updates", "format": "json", "description": "Pending update proposals"},
            ],
        }
        validate_instance(manifest, "memory-pack-manifest")
        dump_json(manifest, directory / "manifest.json")
        return manifest

    def import_project_pack(self, pack_dir: str | Path) -> dict[str, Any]:
        directory = Path(pack_dir)
        manifest = load_json(directory / "manifest.json")
        validate_instance(manifest, "memory-pack-manifest")
        project_id = manifest["project_id"]
        dispositions_payload = load_json(directory / "dispositions.json")
        for disposition in dispositions_payload.get("items", []):
            self.put_disposition(disposition)
        for episode in load_jsonl(directory / "episodes.jsonl"):
            self.append_episode(episode)
        for summary in load_jsonl(directory / "run-summaries.jsonl"):
            self.write_run_summary(summary)
        state = load_json(directory / "project-state.json")
        state["last_pack_import_at"] = utc_now()
        self.set_project_state(state)
        pending_path = directory / "pending-disposition-updates.json"
        if pending_path.exists():
            pending_payload = load_json(pending_path)
            for proposal in pending_payload.get("items", []):
                self.queue_disposition_update(proposal)
        self._sync_if_needed()
        return {"project_id": project_id, "imported_at": utc_now(), "manual_sync_required": True}

    def export_mirrors(self) -> dict[str, str]:
        with self._connect() as connection:
            dispositions = [
                json.loads(row["payload_json"])
                for row in connection.execute(
                    "SELECT payload_json FROM dispositions ORDER BY project_id, problem_class, action_intent"
                ).fetchall()
            ]
            episodes = [
                json.loads(row["payload_json"])
                for row in connection.execute(
                    "SELECT payload_json FROM episodes ORDER BY recorded_at"
                ).fetchall()
            ]
            run_summaries = [
                json.loads(row["payload_json"])
                for row in connection.execute(
                    "SELECT payload_json FROM run_summaries ORDER BY completed_at"
                ).fetchall()
            ]
            project_states = [
                json.loads(row["payload_json"])
                for row in connection.execute(
                    "SELECT payload_json FROM project_state ORDER BY project_id"
                ).fetchall()
            ]
            updates = [
                json.loads(row["payload_json"])
                for row in connection.execute(
                    "SELECT payload_json FROM disposition_updates ORDER BY created_at"
                ).fetchall()
            ]

        dump_json({"schema_version": PROJECT_PACK_VERSION, "items": dispositions}, self.mirror_dir / "dispositions.json")
        write_jsonl(self.mirror_dir / "episodes.jsonl", episodes)
        write_jsonl(self.mirror_dir / "run-summaries.jsonl", run_summaries)
        dump_json({"schema_version": PROJECT_PACK_VERSION, "items": project_states}, self.mirror_dir / "project-states.json")
        dump_json({"schema_version": PROJECT_PACK_VERSION, "items": updates}, self.mirror_dir / "pending-disposition-updates.json")
        return {
            "dispositions": str(self.mirror_dir / "dispositions.json"),
            "episodes": str(self.mirror_dir / "episodes.jsonl"),
            "run_summaries": str(self.mirror_dir / "run-summaries.jsonl"),
            "project_states": str(self.mirror_dir / "project-states.json"),
            "pending_updates": str(self.mirror_dir / "pending-disposition-updates.json"),
        }
