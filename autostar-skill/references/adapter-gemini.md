# Gemini CLI adapter

This file defines the full-support adapter for running a* in Gemini CLI-style
hosts with shell access and file-backed workspace state.

Use it together with:
- `references/runtime-capabilities.md`
- `runtime-profiles/gemini.json`

---

## Intent

Gemini CLI is a valid **full-support** host for a* when it exposes:
- workspace file access
- subprocess execution
- conversational pause/resume behavior

The main ergonomic limitation relative to Claude Code is the lack of a native
structured chooser widget.

---

## Capability summary

Reference profile: `runtime-profiles/gemini.json`

Operational consequences:
- bounded approvals should use explicit numbered or labeled prompts in chat
- external-tool verifiers are available through shell/subprocess execution
- mission and run artifacts should be persisted as real files
- rendered HTML artifacts should be surfaced by file path or external open flow

---

## Phase 0: Runtime announcement

Before onboarding, state the active profile briefly:

> "I'm running a* in the Gemini CLI full-support profile. I can use file-backed
> artifacts and command-line verifiers, but approvals happen through explicit
> chat prompts rather than a native chooser UI."

---

## Phase 1: Onboarding mapping

### A. Structured choices

Use bounded chat prompts for all required approvals.

Pattern:

```text
Choose one:
1. Keep this track required
2. Downgrade it to preferred
3. Remove it

Reply with the number only.
```

Rules:
- keep the response format explicit
- confirm the parsed answer before updating mission files
- do not continue on ambiguous replies

### B. Freeform input

Use normal chat turns for:
- goal description
- evaluation criteria
- constraints
- budget negotiation

Reflect interpreted freeform input back before committing canonical artifacts.

### C. Mission artifacts

Persist canonical mission files in the workspace:
- `mission.md`
- `tracks.md`
- `constraints.md`
- `plays.md`

Use the persisted files, not hidden session state, as the run source of truth.

---

## Verifier policy in Gemini CLI

Supported:
- `deterministic`
- `external_tool`
- `llm_judge`
- `hybrid`
- `human_gate`

Tool availability rule:
1. check each requested external tool before the run
2. surface missing tools explicitly
3. require user confirmation before replacing or removing any affected track

---

## Execution behavior

- Persist `step_log.jsonl`, `progress.json`, `reflections.jsonl`, `tracks.json`, and `mission.json`
- Re-render `visualiser.html` after each round reflection and on completion
- Present artifacts by path when inline rendering is unavailable
- Pause cleanly for human gates and wait for the next user reply

---

## When to downgrade

Downgrade only when the concrete Gemini host lacks one of the required runtime
capabilities, such as disabled shell access or restricted workspace writes. In
that case, record the downgrade explicitly in the mission summary and final
report.
