# Chat-only adapter

This file defines the boundary case for running a* in a chat-only host with no
file presentation and no subprocess execution.

Use it together with:
- `references/runtime-capabilities.md`
- `runtime-profiles/chat-only.json`

---

## Intent

This adapter is intentionally classified as **unsupported** for full a*.

It exists to make the lower bound explicit:
- what breaks without files
- what breaks without subprocesses
- what can only be salvaged in a narrower prompt-only mode

If a host matches this profile, do not market it as a general a* runtime.

---

## Capability summary

Reference profile: `runtime-profiles/chat-only.json`

Operational consequences:
- onboarding can still happen in prose
- approvals can only be captured via plain chat replies
- no local files can be treated as canonical artifacts
- no HTML tools can be shown
- no external-tool verification can run

---

## Why this is unsupported

Full a* depends on:
- canonical mission artifacts
- append-only run logs
- machine-readable progress state
- real tool-based verification when requested

A chat-only host cannot provide those guarantees. Without them:
- auditability collapses
- portability claims become misleading
- external-tool and hybrid tracks become impossible

---

## Allowed narrowed mode

If you explicitly want a degraded prompt-optimisation workflow, the host may run
only this narrowed mode:
- `llm_judge` tracks
- explicit human approvals
- text-only progress summaries
- ephemeral session state only

Even then, call it a **narrowed prompt-only mode**, not full a*.

---

## User-facing runtime announcement

Before onboarding, say this plainly:

> "This host is chat-only. I can help with rubric-based iteration in-session,
> but I cannot run command-line verifiers, preserve canonical run files, or
> provide the full a* audit trail. If you want the full workflow, move to a
> subprocess-capable runtime such as Claude Code."

If the user still wants to proceed, require explicit confirmation that they are
accepting a narrowed mode.

---

## Verifier policy

Supported in narrowed mode:
- `llm_judge`
- `human_gate`

Conditionally possible:
- trivial deterministic checks that can be reasoned about directly in text

Unsupported:
- `external_tool`
- subprocess-backed `hybrid`
- file-backed progress artifacts

Do not silently replace unsupported tracks. Ask the user whether to:
1. switch runtimes
2. remove the track
3. accept a lower-confidence rubric-based substitute

---

## Artifact handling

There are no canonical local artifacts in this profile.

If the user insists on continuing:
- keep mission state as explicitly labeled markdown blocks in chat
- restate the latest canonical block after any change
- warn that persistence ends with the session

This is a compromise, not equivalent functionality.

---

## Progress and pause behavior

Human gates can still pause on the next user turn.

Progress reporting is limited to text summaries such as:

```text
Session status
- best candidate so far: version 4
- current judged score: 0.74
- limiting concern: specificity
- remaining budget: estimated manually
```

Do not claim `progress.json`, `step_log.jsonl`, or `visualiser.html` exist in
this mode unless another system is generating them externally.

---

## When to switch runtimes immediately

Switch away from this profile if the user wants:
- pytest, pyright, eslint, lighthouse, or any actual tool output
- durable run logs
- HTML visualiser flows
- reproducible machine-readable artifacts

That is the normal case for full a*.
