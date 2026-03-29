# Claude.ai adapter

This file defines the reduced-support adapter for running a* in Claude.ai.
It also applies to Claude Desktop and Claude Mobile when they expose the same
inline file-presentation profile.

Use it together with:
- `references/runtime-capabilities.md`
- `runtime-profiles/claude-ai.json`

---

## Intent

Claude.ai is a valid **reduced-support** host for a* when the goal can be
evaluated primarily through:
- LLM judge tracks
- deterministic checks the model can reason about directly
- human gates

It is **not** a full-support host for missions that depend on external CLI
verifiers or local subprocess rendering.

---

## Capability summary

Reference profile: `runtime-profiles/claude-ai.json`

Operational consequences:
- structured choices must be done in chat, not with a native chooser widget
- subprocess-based verifier tracks are unavailable
- file-backed logs may need to be represented as canonical in-chat artifacts
- inline visual outputs should be shown in-chat rather than via external browser hops

Memory consequences:
- the checked-in base profile remains conservative and does not claim long-term memory
- the effective session may gain long-term memory only through a real connector or a valid project pack
- Claude's own built-in memory remains advisory only and must not become the system of record

## Memory access modes

Claude.ai should use explicit memory modes:

1. `connector_backed`
   Preferred. A remote memory connector is configured and reachable.
2. `project_pack`
   Fallback. No connector, but project knowledge contains a valid exported memory pack.
3. `none`
   Final fallback. The run uses short-term memory only and says so plainly.

`direct_backend` exists in the global runtime contract but should not be
assumed for the base Claude.ai host profile.

---

## Phase 0: Runtime announcement

Before onboarding, tell the user exactly what is downgraded:

> "I'm running a* in a reduced-support Claude.ai profile. I can do structured
> onboarding, rubric-based judging, and human checkpoints, but I cannot run
> command-line verifiers such as pytest, pyright, or lighthouse from here.
> If you want those tracks, we need a runtime with subprocess access."

If the user requested tool-based verification, stop and ask whether to:
1. switch runtimes
2. replace the track with an LLM judge approximation
3. remove that track

Do not proceed until the user confirms.

---

## Phase 1: Onboarding mapping

### A. Structured choices

Claude.ai does not assume `ask_user`, so use explicit bounded prompts in chat.

Pattern:

```text
Choose one:
1. Hard requirement
2. Preference

Reply with the number only, or say "edit" if neither fits.
```

For multi-select:

```text
Select all that apply:
1. Readability
2. Accuracy
3. Concision
4. Something else

Reply with numbers separated by commas.
```

Rules:
- keep options short
- keep the response format explicit
- confirm the parsed selection back to the user before using it

### B. Rubric drafting and approval

For each `llm_judge` or `hybrid` track:
1. ask for 1.0 / 0.5 / 0.0 anchors in prose
2. ask for explicit failure modes
3. draft the rubric in chat
4. ask a bounded follow-up:

```text
Choose one:
1. Keep this draft and move on
2. Tighten the wording
3. Redo this track
```

After all rubric-bearing tracks are drafted:
1. show the full rubric-bearing section of `tracks.md`
2. ask for final approval of the inferred rubric set
3. only then lock the rubrics for the run

### C. Mission artifacts

When Claude.ai cannot maintain normal local files, preserve these artifacts as
canonical named markdown blocks in the conversation:
- `mission.md`
- `tracks.md`
- `constraints.md`
- `plays.md`

Every time one changes:
1. reprint the full canonical block
2. ask for confirmation if the change affects mission scope or verification

---

## Verifier policy in Claude.ai

### Supported

- `llm_judge`
- `human_gate`
- narrowly-scoped deterministic checks that can be evaluated directly from the
  artifact text without shell access

### Unsupported without explicit downgrade

- `external_tool`
- `hybrid` tracks that require a subprocess component

### Downgrade rule

If a track originally wants `external_tool` or subprocess-backed `hybrid`:
- explain the limitation
- propose an `llm_judge` replacement only if the user approves
- record the downgrade in the mission artifact and final report
- never make the downgrade silently

Recommended wording:

> "This runtime can't execute [tool]. I can replace that track with a rubric
> judge, but confidence will be lower and the score will no longer be grounded
> in the actual tool output."

---

## Phase 2: Pre-run preparation

Claude.ai adapter behavior:

- Tool availability checks: skip, because subprocess is unavailable
- Baseline run: still required
- Disposition lookup: optional; only if the effective profile reports a real memory surface
- Mission confirmation: still required, with the full canonical artifacts shown

Add this note to the mission summary when relevant:

> "Runtime downgrade: subprocess-backed verification disabled."

Add one memory note too:

> "Memory mode: connector_backed. Cross-run learning is active through the configured connector."

> "Memory mode: project_pack. Cross-run learning is available with reduced fidelity; manual sync is required after the run."

> "Memory mode: none. Long-term memory is unavailable in this session, so a* is running with short-term memory only."

---

## Phase 3: Execution loop

### Step records

Maintain step records as structured in-chat data if file append is unavailable.
At minimum, preserve:
- step id
- parameters or mutation summary
- track scores
- composite score
- rationale notes
- outcome

### Progress reporting

Preferred:
- maintain a logical `progress.json` object in session state
- surface compact progress updates after each round

Fallback text summary format:

```text
Round 2 complete.
Current composite: 0.78 (up from 0.61 baseline)
Best tracks: clarity 0.90, structure 0.84
Limiting track: factual precision 0.55
Budget used: 18 / 40 steps
Decision: worth pursuing, no pivot yet
```

### Visualiser

Preferred behavior on Claude.ai/Desktop/Mobile:
- if `runs/<run_id>/visualiser.html` exists, present it inline with `present_files`
- re-present the refreshed file after each round reflection and at completion
- do not redirect the user to an external browser when inline presentation is available

If no rendered `visualiser.html` exists and the runtime cannot run
`render_visualiser.py` itself:
- present `progress.json` or equivalent structured state inline
- include a compact textual round summary beside it when helpful

Only use text-only updates when inline file presentation is unavailable.

---

## Human gates and pause/resume

Claude.ai can support human gates through normal conversation turns.

Pattern:
1. stop mutation
2. present the artifact or relevant excerpt
3. ask for approval or score
4. do not resume until the user responds

Human gate prompts should always specify:
- what changed
- what criterion is being judged
- what response format is expected

---

## Final report behavior

The final report must include a runtime-adapter section:

```text
Runtime profile: Claude.ai (reduced support)
Downgraded features:
- external tool verification unavailable
- in-session HTML visualiser rendering unavailable
Tracks affected:
- type correctness: replaced with LLM judge
```

If no downgrades were used, state that explicitly.
If project-pack mode was used, also say that updated pack files need manual
sync back into project knowledge or GitHub.

---

## When not to use this adapter

Do not use the Claude.ai adapter when:
- the mission depends on pytest, pyright, eslint, lighthouse, or any real tool output
- the user needs append-only run logs written locally
- the run depends on generating local HTML artifacts during execution and no other runtime can render them

In those cases, move the run to a subprocess-capable host such as Claude Code.
