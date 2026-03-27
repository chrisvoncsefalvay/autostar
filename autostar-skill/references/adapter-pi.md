# Pi adapter

This file defines the full-support adapter for running a* in the Pi coding agent.

Use it together with:
- `references/runtime-capabilities.md`
- `runtime-profiles/pi.json`

---

## Intent

Pi coding agent is a valid **full-support** host for a* when used in its normal
coding-agent form with built-in file tools and `bash`.

It supports the core a* workflow through:
- file-backed workspace operations
- subprocess-backed verification via `bash`
- persisted session state
- skills and extensions for runtime customization

---

## Capability summary

Reference profile: `runtime-profiles/pi.json`

Operational consequences:
- bounded approvals should use explicit numbered prompts in chat unless an
  installed extension provides richer structured UI
- canonical mission and run artifacts can live as real files in the workspace
- external-tool verifiers can run through `bash`
- HTML artifacts are generally surfaced externally by path or export flow

---

## Phase 0: Runtime announcement

Before onboarding, say this plainly:

> "I'm running a* in the Pi full-support profile. I can read and modify files,
> run command-line verifiers through bash, and persist run artifacts. Approval
> checkpoints happen through explicit chat prompts unless the current Pi setup
> has a richer UI extension installed."

---

## Phase 1: Onboarding mapping

### A. Structured choices

Use bounded chat prompts for required approvals unless a Pi extension provides a
dedicated selector UI.

Rules:
- keep the response format explicit
- confirm parsed selections before updating canonical artifacts
- never infer approval from freeform prose

---

### B. Mission artifacts

Persist canonical files in the workspace or run directory:
- `mission.md`
- `tracks.md`
- `constraints.md`
- `plays.md`

Use those files, not hidden session state, as the source of truth.

---

## Verifier policy in Pi

Supported:
- `deterministic`
- `external_tool`
- `llm_judge`
- `hybrid`
- `human_gate`

Tool availability rule:
1. verify requested tools before execution
2. surface missing tools explicitly
3. require user confirmation before downgrading or removing tracks

---

## Execution behavior

- persist run artifacts under `runs/<run_id>/`
- use `bash` for tool-backed verification and visualiser rendering
- surface artifacts by path or export flow when the user needs to inspect them
- pause cleanly for human gates and resume on the next user turn

---

## Note on extensions and skills

Pi has official support for skills, extensions, and pi packages, but I did not
find a published Pi creator skill by that exact name. If you want a scaffold
specifically for Pi extensions or packages, that should likely be added as a
separate adapter reference or skill rather than inferred here.
