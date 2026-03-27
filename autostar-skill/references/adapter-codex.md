# Codex adapter

This file defines the full-support adapter for running a* in OpenAI Codex
CLI-style coding hosts with shell access and file-backed workspace state.

Use it together with:
- `references/runtime-capabilities.md`
- `runtime-profiles/codex.json`

---

## Intent

OpenAI Codex CLI is a valid **full-support** host for a* when it has:
- workspace file access
- subprocess execution
- normal pause/resume conversation flow

It differs from Claude Code mainly in interaction ergonomics, not in core
capability coverage.

---

## Capability summary

Reference profile: `runtime-profiles/codex.json`

Operational consequences:
- bounded approvals should use explicit numbered or labeled prompts in chat
- external-tool verifiers are available through shell/subprocess execution
- mission and run artifacts should be persisted as real files
- rendered HTML artifacts should be surfaced by file path or external open flow

---

## Phase 0: Runtime announcement

Before onboarding, state the active profile briefly:

> "I'm running a* in the Codex full-support profile. I can use file-backed run
> artifacts and command-line verifiers, but bounded approvals happen through
> explicit chat prompts rather than a native chooser UI."

---

## Phase 1: Onboarding mapping

### A. Structured choices

Use bounded chat prompts for every checkpoint that needs explicit approval.

Pattern:

```text
Choose one:
1. Hard requirement
2. Preference

Reply with the number only, or say "edit" if neither fits.
```

Rules:
- keep options short and mutually distinct
- restate the parsed answer before writing canonical artifacts
- never infer a choice from surrounding prose without confirmation

### B. Freeform input

Use normal chat turns for:
- mission description
- evaluation criteria
- soft constraints
- custom budgets

Reflect transformed prose back to the user before locking it into mission files.

### C. Mission artifacts

Persist the following as real files in the run directory:
- `mission.md`
- `tracks.md`
- `constraints.md`
- `plays.md`

Use those files as the source of truth during execution.

---

## Verifier policy in Codex

Supported:
- `deterministic`
- `external_tool`
- `llm_judge`
- `hybrid`
- `human_gate`

Tool availability rule:
1. dry-run each requested external verifier before execution
2. if a tool is missing, surface it as an environment/tooling issue
3. ask whether to install it, replace the track, or remove the track

Do not silently downgrade a missing tool-backed track.

---

## Execution behavior

- Persist step records and progress artifacts as normal files under `runs/<run_id>/`
- Re-render `visualiser.html` after round reflections and on completion
- Present review artifacts by path when inline rendering is unavailable
- Pause on human gates until the user responds in the next turn

---

## When to downgrade

Downgrade only when the live Codex environment is missing one of the declared
capabilities, such as disabled shell access or blocked filesystem writes.
Treat those as environment-specific constraints, not as changes to the profile
contract itself.
