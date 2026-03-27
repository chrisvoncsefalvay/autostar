# Adapter template

Use this file when porting a* to a new host runtime.

Pair it with:
- `references/runtime-capabilities.md`
- `runtime-profiles/template.json`

---

## Deliverables

Every new adapter should add three things:

1. A runtime profile file in `runtime-profiles/`
2. A runtime-specific reference document in `references/`
3. A README/SKILL reference so the adapter is discoverable

---

## Build sequence

### 1. Fill in the runtime profile

Start from `runtime-profiles/template.json`.

You must answer:
- Can the host do bounded user choices?
- Can it capture freeform answers?
- Can it present files?
- Can it render or open local HTML?
- Can it run subprocesses?
- Can it truly pause and resume?
- Can it persist run artifacts?
- Can it store cross-run memory?

Do not round capabilities up. Optimistic profiles create bad missions.

### 2. Classify support level

Use the rules in `references/runtime-capabilities.md`:
- full support
- reduced support
- unsupported

Write that classification at the top of the adapter doc.

### 3. Define onboarding mappings

For each onboarding checkpoint, specify:
- the host primitive used
- the exact fallback if the primitive is missing
- how explicit confirmation is captured

At minimum, cover:
- track selection
- required vs preferred
- verifier type selection
- budget selection
- final mission approval

### 4. Define verifier policy

List verifier types under:
- fully supported
- supported with downgrade
- unsupported

For every downgraded verifier type, define:
- the user-facing warning
- the replacement behavior
- where the downgrade is recorded

### 5. Define artifact handling

Explain how the runtime handles:
- `mission.md`
- `tracks.md`
- `constraints.md`
- `plays.md`
- `step_log.jsonl`
- `reflections.jsonl`
- `progress.json`

If true files are unavailable, define the in-session canonical representation.

### 6. Define progress and pause behavior

Specify:
- how round progress is shown
- whether HTML visualisation is available
- how human gates pause the run
- how the run resumes

### 7. Define final-report disclosures

Every adapter must state:
- runtime name
- support level
- downgraded capabilities used in the run
- tracks affected by downgrades

---

## Adapter doc outline

Use this structure:

```text
# <Runtime name> adapter

## Intent
## Capability summary
## Phase 0: Runtime announcement
## Phase 1: Onboarding mapping
## Verifier policy
## Phase 2: Pre-run preparation
## Phase 3: Execution loop
## Human gates and pause/resume
## Final report behavior
## When not to use this adapter
```

---

## Quality bar

An adapter is only acceptable if:
- it never skips approvals
- it never hides downgraded verification
- it never claims unsupported artifacts are available
- it tells the user when the host is the limiting factor

If you cannot meet that bar, classify the runtime as unsupported.
