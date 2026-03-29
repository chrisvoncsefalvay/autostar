# Memory reference

---

## Architecture overview

One canonical persistent backend. One run-scoped append-only store. Human-readable
JSON and JSONL files are exported mirrors or project-pack views, not the primary
database.

```
CANONICAL LONG-TERM BACKEND (persistent, source of truth)
  SQLite-backed store
    episodes                — append-only episodic memory
    run_summaries           — one summary per completed run
    dispositions            — current disposition records
    disposition_versions    — auditable version history
    disposition_updates     — pending/applied proposals
    project_state           — compact project-scoped state

EXPORTED MIRRORS / PROJECT PACKS (derived from backend)
  dispositions.json
  episodes.jsonl
  run-summaries.jsonl
  project-state.json
  latest-relevant-priors.json

SHORT-TERM (run-scoped, append-only where stated)
  step_log.jsonl          — append-only; every step record
  reflections.jsonl       — append-only; every round reflection
  hypothesis_stack.json   — current queue with provenance
  track_trajectories.json — per-track score history
  momentum.json           — slope and acceleration of composite score
```

If a derived snapshot and an append-only run log disagree, the append-only log wins.

---

## Short-term memory

### `step_log.jsonl`
Append-only. One JSON object per line. Schema matches the step record
in the main SKILL.md. Never truncated during a run.

Key fields for orchestrator consumption:
- `outcome` — keep/revert/partial_keep/rejected_constraint
- `judge_notes` — per-track rationale strings
- `play` — which play was attempted (or null)
- `composite` — the score that determines the ratchet

### `hypothesis_stack.json`
An ordered list of mutation hypotheses the orchestrator intends to try,
with provenance for each:

```json
[
  {
    "hypothesis": "Adding explicit return type annotations may improve pyright score",
    "source": "disposition:type_correctness:python_typing",
    "confidence": 0.74,
    "play": "annotation_bundle",
    "priority": 1
  },
  {
    "hypothesis": "Extracting nested conditionals into helper functions may improve readability",
    "source": "orchestrator_reasoning:round_2_reflection",
    "confidence": 0.55,
    "play": null,
    "priority": 2
  }
]
```

The orchestrator pops from the top and may re-insert refined hypotheses
based on step outcomes.

### `momentum.json`
```json
{
  "window": 5,
  "composite_slope": 0.012,
  "composite_acceleration": -0.003,
  "per_track": {
    "type_correctness": {"slope": 0.0, "plateau": true},
    "docstring_quality": {"slope": 0.024, "plateau": false}
  },
  "signal": "exploiting_successfully | plateau | diverging | recovering"
}
```

The `signal` field feeds the round reflection's worth-pursuing assessment.

---

## Long-term episodic store

`episodes.jsonl` is the exported mirror of the canonical episodic store. The
SQLite backend is the source of truth; the mirror exists for inspection,
packaging, and Claude.ai project-pack workflows.

Each entry is a round reflection record (verbatim from the round reflection
output, plus run metadata). This store is the raw historical record.
It is queried at run start to retrieve relevant prior round reflections
for similar problem classes.

`run_summaries.jsonl` is the exported mirror of the canonical run-summary table.
One entry per completed run:
```json
{
  "run_id": "run_20260324",
  "problem_class": "python_api_optimisation",
  "artifact_description": "FastAPI handler for user authentication",
  "baseline_scores": {...},
  "final_scores": {...},
  "rounds_completed": 4,
  "pivots": ["minor pivot at round 2: switched to contrastive_negation strategy"],
  "what_worked": ["annotation_bundle play: +0.22 type_correctness"],
  "what_failed": ["docstring_length increase: no significant effect"],
  "disposition_updates_proposed": [...]
}
```

---

## Disposition library

### Schema
```json
{
  "problem_class": "python_api_optimisation",
  "action_intent": "improve_type_correctness",
  "version": 3,
  "prior": "When improving type correctness in Python API handlers, prioritise
    return type annotations before parameter annotations — pyright errors
    on return types more frequently than on parameters. Use TypeAlias for
    complex union types rather than inline. Avoid annotating *args and
    **kwargs unless the function is part of a public interface.",
  "confidence": 0.81,
  "n_supporting": 14,
  "n_refuting": 2,
  "exemplars_supporting": ["run_20260310_r2_l1", "run_20260318_r1_l3"],
  "exemplars_refuting": ["run_20260301_r3_l2"],
  "provenance": "learned_from_run",
  "source": null,
  "override_conditions": "Suspend when the codebase uses Pydantic v1 (type
    inference rules differ significantly from standard mypy/pyright).",
  "last_updated": "2026-03-22",
  "policy_version_at_creation": 2
}
```

### Keying and retrieval

Dispositions are keyed on `(problem_class, action_intent)` but retrieved
by **semantic similarity with exact-key boosts**, not exact match alone. At run start:

1. Build a deterministic hashed word-and-character n-gram vector from the run's problem description, goal, artifact description, and each anticipated action intent
2. Query the disposition library with cosine similarity over those vectors
3. Boost exact matches on `problem_class` and `action_intent`
3. Return top-3 dispositions per action class with confidence ≥ 0.4
4. Inject retrieved dispositions into the orchestrator's context as:
   > "Based on prior experience with similar problems, when attempting
   > [action_intent], note: [prior text] (confidence: X, n=Y)"

If confidence < 0.4, flag as weak prior and consider triggering
meta-research.

### Updating dispositions

The memory agent proposes updates after each round. Updates are not applied
automatically — they are queued as proposals in the canonical backend and
applied only when the run completes and the user approves (or auto-approved if
confidence delta is small and policy allows it).

**Update types:**

**Reinforce:** A disposition was retrieved and the action it conditioned
produced a better-than-average outcome. Increase confidence, add exemplar.

**Weaken:** A disposition was retrieved and the action produced worse-than-
expected outcome. Decrease confidence, add refuting exemplar.

**Extend:** New override condition discovered (orchestrator flagged a case
where the disposition didn't apply). Add to `override_conditions`.

**Fork:** Evidence suggests the problem class should be split into two
sub-classes with different dispositions. Propose fork; user approves.

**Create:** No relevant disposition existed; a new one is proposed from
run experience.

**Retire:** Confidence has fallen below 0.2 with n > 10. Mark as retired;
do not retrieve for new runs.

### Meta-research step

Triggered when: no relevant disposition exists, OR confidence < 0.4 for
a critical action class.

Protocol:
1. Identify the action class and problem class in plain language
2. Check the mission's `research_policy`
3. If `research_policy.enabled` is false, abort the meta-research step
4. Formulate a best-practice query that avoids sending source artifacts or secrets
5. Prefer local references, bundled docs, and installed tool help first
6. If external lookup is allowed, prefer allowlisted/vendor documentation before general web search
7. Only include artifact/code excerpts in an external query if `artifact_sharing` was explicitly approved
8. Synthesise the retrieved content into a candidate disposition prior
9. Record provenance as `looked_up_from_web` with source URL
10. Apply the candidate on the next relevant action
11. Observe outcome; update confidence accordingly

The meta-research step costs budget. Gate it:
- Do not trigger if budget_remaining < 20%
- Do not trigger more than once per round per action class
- Record the query and source in `step_log.jsonl` as a special
  `meta_research` entry
- Record whether the step used `local_only`, `allowlisted_external`, or `open_web`

Default policy:
- External research is disabled unless the user explicitly enabled it during onboarding
- Artifact sharing to external services is disabled unless separately approved

---

## Claude.ai access paths

Claude.ai should never treat native Claude memory as the authoritative store for
a* learning. Use one of these explicit paths instead:

1. `connector_backed`
   Preferred. A remote connector exposes narrow memory tools over a user-scoped,
   auditable surface.
2. `project_pack`
   Fallback. Export a text-first project pack from the canonical backend, add it
   to project knowledge, and manually sync updated pack files back after the run.
3. `none`
   Final fallback. Run with short-term memory only and say so plainly.

## Memory agent responsibilities

The memory agent runs:

1. **After every step:** append step record to `step_log.jsonl`;
   update `track_trajectories.json` and `momentum.json`

2. **After every lap:** update hypothesis stack (remove tested, add
   refinements based on outcomes)

3. **After every round reflection:** append to `episodes.jsonl`;
   identify disposition update proposals; check for meta-research triggers

4. **After run completion:** write `run_summaries.jsonl` entry;
   apply approved disposition updates to library; write final report
