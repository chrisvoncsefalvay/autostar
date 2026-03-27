# Claude Code adapter

This file defines the full-support adapter for running a* in Claude Code.

Use it together with:
- `references/runtime-capabilities.md`
- `runtime-profiles/claude-code.json`

---

## Intent

Claude Code is the reference **full-support** host for a*.

It supports the complete workflow:
- structured onboarding
- local file-backed mission artifacts
- subprocess verifiers
- rendered local HTML artifacts
- human gates with pause/resume behavior

This is the adapter to copy when implementing a* in another tool with comparable
capabilities.

---

## Capability summary

Reference profile: `runtime-profiles/claude-code.json`

Operational consequences:
- bounded decisions should use `ask_user`
- external-tool verifiers are available through shell/subprocess execution
- mission and run artifacts should be persisted as real files
- the rendered visualiser can be opened in the local browser when useful

---

## Phase 0: Runtime announcement

Before onboarding, state the active runtime profile briefly:

> "I'm running a* in the Claude Code full-support profile, so I can use
> structured approval steps, local run artifacts, command-line verifiers,
> and the rendered visualiser."

If the environment is missing a required CLI tool for a requested verifier,
surface that as a **tool availability issue**, not as a runtime downgrade.

---

## Phase 1: Onboarding mapping

### A. Structured choices

Use `ask_user` for every bounded checkpoint.

Required checkpoints:
- track selection
- required vs preferred
- verifier type selection
- hard constraint confirmation
- budget selection
- plays enabled/disabled and play approval
- final mission approval

Rules:
- prefill inferred answers as defaults when possible
- never infer and continue without confirmation
- if the user chooses "other", loop back and reconfirm the updated set

### B. Freeform input

Use normal chat turns for:
- open goal description
- rubric anchor descriptions
- soft constraints
- custom budget ceilings

When converting freeform input into canonical artifacts, reflect it back before
committing the file.

### C. Rubric drafting and approval

For each `llm_judge` or `hybrid` track:
1. ask for the 1.0, 0.5, and 0.0 anchors in normal chat
2. ask what explicit penalties should reduce the score
3. draft the rubric in chat
4. use `ask_user` to decide whether to keep it, tighten it, or redo that track

After all rubric-bearing tracks have provisional drafts:
1. show the rubric-bearing portion of `tracks.md`
2. use `ask_user` for final rubric approval
3. do not lock the rubrics until the user approves the full inferred set

### D. Mission artifacts

Persist the following as real files in the run directory:
- `mission.md`
- `tracks.md`
- `constraints.md`
- `plays.md`

Rules:
- regenerate the full artifact on each confirmed update
- do not keep hidden in-memory variants that differ from the files
- use the file versions as the source of truth during execution

---

## Verifier policy in Claude Code

### Supported

- `deterministic`
- `external_tool`
- `llm_judge`
- `hybrid`
- `human_gate`

### Tool availability rule

For every `external_tool` verifier:
1. run a dry-fire check such as `tool --version`
2. if missing, tell the user exactly which tool is unavailable
3. ask whether to install it, replace the track, or remove the track

Do not silently replace a missing tool with an LLM judge.

### Hybrid tracks

If both tool and judge components are available, keep both.
Use the aggregation mode defined in the track configuration.

---

## Phase 2: Pre-run preparation

Claude Code adapter behavior:

- Tool availability checks: required for all `external_tool` verifiers
- Baseline run: required
- Disposition lookup: use if available in the host setup
- Mission confirmation: required, based on the persisted run artifacts

Before execution begins, show the user a concise summary of:
- approved tracks
- required tools
- budget
- stopping criteria

---

## Phase 3: Execution loop

### Step records

Persist step records to `runs/<run_id>/step_log.jsonl`.

Each record must include:
- step id
- parameters
- play name or null
- per-track scores
- composite score
- rationale/judge notes
- constraint outcome
- budget cost
- keep/revert verdict

### Progress reporting

Maintain:
- `runs/<run_id>/progress.json`
- `runs/<run_id>/reflections.jsonl`
- `runs/<run_id>/tracks.json`
- `runs/<run_id>/mission.json`

Round updates to the user should reference these artifacts rather than inventing
a separate reporting format.

### Visualiser

Preferred path:

```bash
python scripts/render_visualiser.py runs/<run_id> --open --status running
```

Re-render after each round reflection and on completion:

```bash
python scripts/render_visualiser.py runs/<run_id> --status completed
```

If browser opening fails, keep rendering `visualiser.html` and tell the user the
file path to open manually. The render step is still required.

---

## Human gates and pause/resume

Claude Code supports human gates by pausing autonomous progress until the user
responds in the next turn.

Pattern:
1. stop mutation after the current checkpoint
2. present the artifact or file path under review
3. ask a bounded approval/scoring question
4. do not continue until the user replies

Human gates should cite:
- the track being judged
- the artifact under review
- the response format expected

---

## Final report behavior

The final report should include:
- baseline vs final scores
- track-by-track outcome
- reflection log summary
- approved disposition updates
- budget accounting

Runtime section:

```text
Runtime profile: Claude Code (full support)
Tool availability issues encountered:
- none
Runtime downgrades:
- none
```

If a requested tool was unavailable and the user approved a replacement,
that belongs under tool availability issues, not under runtime capability.

---

## When not to use this adapter

Do not use the Claude Code adapter only if the local environment itself blocks
required capabilities for the mission, for example:
- the needed verifier tools are not installed and cannot be added
- the filesystem is unavailable for run artifact persistence
- browser/file presentation is blocked and the mission depends on HTML tools

In those cases, adapt the mission or switch environments before starting.
