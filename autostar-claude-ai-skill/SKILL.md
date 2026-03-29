---
name: autostar-web
description: >
  Generalised autonomous optimisation loop — soft RLVR for any artifact a user can
  measure. Web runtime package: uses memory in this order: connector-backed,
  project-pack, none. Never assumes subprocess access or unrestricted local files.
  Use this skill whenever a user wants to iteratively improve an artifact —
  code, prompts, documents, configs, designs, content — by running structured
  experiments, evaluating results against a multi-dimensional rubric, and learning
  from each attempt. Triggers include: "optimise this", "keep improving until it's
  good", "run experiments on", "autoresearch", "iterate on this overnight", "try
  different approaches and pick the best", or any request implying repeated
  evaluate-and-improve cycles.
compatibility: Claude.ai custom Skills ZIP upload
---

# a* (autostar) — web runtime

A generalised autonomous optimisation loop — soft RLVR for the masses. The user
defines a goal; the system runs structured experiments, evaluates progress across
independent tracks, reflects at strategic checkpoints, and learns from every
attempt — including learning how to learn better the next time.

*If you can measure it, you can improve it.*

## Web runtime constraints

This package runs inside a web chat runtime with reduced capabilities:
- **No subprocess access** — `external_tool` verifiers are unavailable
- **No unrestricted local files** — file read/write is limited
- **Memory**: connector-backed > project-pack > none (see `references/memory.md`)

Do not silently downgrade `external_tool` verifiers to `llm_judge`. If the user
requests a verifier type that requires subprocess access, explain the limitation
and ask them to choose an alternative.

---

## Experimental-first principle

a\* is an experimental optimisation loop. **Do not reach for external mathematical
optimisers or solvers** (e.g. `scipy.optimize`, `cvxpy`, linear/quadratic
programming solvers, evolutionary algorithm libraries, Bayesian optimisation
frameworks, or any other off-the-shelf optimisation package) as a shortcut to
improving the artifact. The value of a\* is in the structured
explore-evaluate-reflect cycle, not in delegating the search to a solver.

If at any point during onboarding, pre-run analysis, or execution you believe the
problem is well-suited to a closed-form or mathematical optimisation approach,
**you must ask the user first** before pursuing it. Present it as an alternative:

> "This problem looks like it could be approached with a mathematical optimiser
> (e.g. [specific method]). Would you like me to try that instead of running the
> experimental loop, or would you prefer to proceed with a\*?"

Do not silently install, import, or invoke an external optimiser. Do not reframe
the a\* loop as a wrapper around a solver. If the user explicitly opts for a
mathematical approach, that is a different workflow — not an a\* run.

---

## Concepts

Before running, ensure you understand these terms precisely:

| Term | Meaning |
|---|---|
| **Step** | One execution with one parameter set. Atomic unit of work. |
| **Play** | A named bundle of parameters that move together (optional; disable with `plays: false`). |
| **Lap** | A set of steps sharing the same parameter family. Establishes statistical confidence in a direction. |
| **Round** | A set of laps. Ends with a mandatory reflection: worth pursuing? ask user? pivot? |
| **Run** | One user-initiated process. Lasts until budget is exhausted or goal is met. |
| **Track** | One independently verifiable sub-goal. Has its own verifier and ratchet. |
| **Disposition** | A learned prior on how to approach a (problem class, action intent) pair. Stored in long-term memory; conditions all significant actions. |

---

## Runtime capability contract

Before Phase 1, detect the host runtime's capabilities. The web runtime provides:
- `structured_choice: basic` — bounded approvals via chat
- `freeform_input: true` — open-ended elicitation
- `file_presentation: inline` — present files inline in chat
- `local_html: inline` — render HTML inline
- `subprocess: false` — **no subprocess access**
- `pause_resume: true` — human gates and round escalations
- `file_read_write: limited`
- `long_term_memory: false` (until an effective memory surface is probed)

If a capability is missing, follow the fallback policy in
`references/runtime-capabilities.md` before onboarding the mission.

### Memory probing

Before starting, probe memory surfaces in order:
1. **connector_backed** — check if remote memory connector tools are available
2. **project_pack** — check if project knowledge contains an exported memory pack
3. **none** — short-term memory only

If neither a connector nor a project pack is available, state plainly:

> "Long-term memory is unavailable in this session. a* is running with short-term memory only."

See `references/adapter-claude-ai.md` and `references/memory.md` for details.

---

## Phase 1: Onboarding

**Do not begin execution until onboarding is complete and the user has approved the mission.**

Onboarding is an interactive dialogue, not a monologue. At every decision point you
must stop and ask the user rather than inferring and proceeding. Use structured
choices for bounded decisions and open prose questions for genuinely open-ended
inputs (e.g. goal description, rubric wording).

The mandatory user-confirmation checkpoints are:

1. **Goal decomposition confirmed** — present inferred tracks as choices; user approves,
   removes, or adds before proceeding
2. **Required vs preferred** — for each track, explicitly ask; do not infer
3. **Verifier type per track** — present options (excluding `external_tool` which is
   unavailable in this runtime); user selects
4. **Hard constraints confirmed** — present inferred list; user amends
5. **Budget** — present three concrete options; user selects
6. **Plays** — enabled/disabled, and approval of proposed bundles
7. **Final mission confirmation** — full summary; explicit go/no-go before any step runs

**Never skip a checkpoint.** If the user's initial message contained enough information
to pre-populate an answer, present it as a pre-selected option and ask them to confirm
or change it. Do not silently accept it.

**Rubric builder:** When configuring LLM judge tracks (onboarding checkpoint 2+),
elicit score anchors interactively through the chat interface. Present the rubric
draft to the user for review and confirmation before proceeding.

The onboarding produces four documents, all maintained in conversation state:

### `mission.md`
```
GOAL:               [plain language description of success]
ARTIFACT:           [what is being mutated and where it lives]
PLAYS:              enabled | disabled
BUDGET:             [strategy + ceiling — see references/budgeting.md]
STOPPING_CRITERIA:  [score threshold | plateau_n | budget_exhausted]
REPORTING:          [what the final report must contain]
```

### `tracks.md`
One block per track. See **Verification taxonomy** below for verifier types.
```
TRACK: <name>
required:     true | false
weight:       0.0–1.0  (weights across non-required tracks must sum to 1.0)
verifier:     <see taxonomy>
threshold:    <pass/fail cutoff or target score>
ratchet:      independent | composite  (default: independent)
```

### `constraints.md`
```
HARD:   [list — violations cause immediate step rejection before scoring]
SOFT:   [list — passed to LLM judge as weighting hints]
```

### `plays.md` (if enabled)
```
PLAY: <name>
parameters:       [list of (param, from, to)]
hypothesis:       [why these move together]
tracks_targeted:  [list]
atomic_fallback:  true | false
```

---

## Verification taxonomy

This is the core of the rubric system. Every track must declare one of the following
verifier types. In this web runtime, `external_tool` is **not available**.

### 1. Deterministic programmatic
A function, script, or expression that produces a binary pass/fail or a bounded score
with no randomness. Does not require an LLM call. In this runtime, deterministic
checks are limited to what can be evaluated inline (e.g. character count, regex
match, format compliance).

```
verifier:
  type: deterministic
  fn:   word_count(artifact) <= 400
  returns: bool
```

### 2. External tool (subprocess) — NOT AVAILABLE

This verifier type requires subprocess access and is **not available** in this
runtime. Do not offer it during onboarding. If the user asks for it, explain:

> "External tool verifiers (pyright, pytest, eslint, etc.) require subprocess access
> which isn't available in this runtime. I can use an LLM judge with a rubric that
> targets the same quality dimension, or you can run those checks separately and
> report results back to me."

Do not silently substitute an LLM judge for an external tool. The user must
explicitly approve any alternative.

### 3. LLM judge
A structured LLM call with a fixed rubric. The rubric is **immutable for the duration
of the run** — it must not be modified by any agent. Temperature should be ≤ 0.2.
For high-stakes tracks, use an **ensemble** of two independent judge calls and average.

```
verifier:
  type: llm_judge
  rubric: |
    Score 0.0–1.0. Evaluate the documentation quality of the provided function.
    0.8+ requires: accurate parameter descriptions, return type explanation,
    at least one usage example, and a description of error conditions.
    Penalise: missing examples, vague descriptions, undocumented exceptions.
  temperature: 0.1
  ensemble: 2
  returns: score
```

The judge must also return a `rationale` string of 1–3 sentences. This is written
to short-term memory and feeds the round reflection.

### 4. Hybrid
A deterministic verifier AND an LLM judge, aggregated. In this runtime, the
deterministic component must be evaluable inline (no subprocess).

```
verifier:
  type: hybrid
  deterministic:  word_count(artifact) <= 400
  llm_judge:      quality_rubric
  aggregation:    min | mean | weighted
  returns: score
```

Use `min` aggregation when both components are required to pass independently
(i.e., a high LLM score cannot compensate for a failed deterministic check).

### 5. Human gate
Pauses the run and surfaces the artifact to the user for approval. Use sparingly;
counts against budget. Appropriate when a track cannot be reliably automated
(e.g., brand approval, legal sign-off, aesthetic judgement with no proxy metric).

```
verifier:
  type: human_gate
  prompt: "Does this copy meet the brand voice guidelines? Score 0–10."
  timeout_action: skip | block | auto_score(0.5)
```

### Hard constraint enforcement
Hard constraints in `constraints.md` are checked **before** any verifier runs.
A constraint violation immediately rejects the step with `outcome: rejected_constraint`
and returns zero budget cost for the verifier calls. This is important: do not waste
judge budget on an artifact that violates a hard constraint.

---

## Phase 2: Pre-run preparation

Before the first round begins:

1. **Baseline run.** Execute one step with the unmodified artifact. Record baseline
   scores for all tracks. This is step `r0_l0_s0` and is never ratcheted.

2. **Query disposition library.** If memory is available (connector or project pack),
   retrieve relevant dispositions for this problem class. Surface them to the user
   briefly: "Based on previous runs, I know X about this class of problem."

3. **Propose initial plays** (if enabled). Present to user for approval or amendment.

4. **Confirm mission.** Show the user the complete `mission.md`, `tracks.md`, and
   `constraints.md` before any optimisation steps run. Do not proceed without
   explicit approval.

---

## Phase 3: Execution loop

### Progress visualisation

After each step, render a progress summary inline in the conversation showing:

1. **Composite score trajectory** — the winning trajectory (kept steps), noting
   reverted alternatives and what they scored.

2. **Round reflections** — structured summaries for each round reflection, showing
   the three key questions (worth pursuing / ask user / pivot), reasoning,
   limiting track, budget remaining, and pace projection.

### Step execution

For each step:
```
1. Apply hard constraint check → reject immediately if violated
2. Execute the artifact mutation (play or atomic)
3. Run all track verifiers in dependency order (required tracks first)
4. Compute composite score: Σ(weight_i × score_i), gated by required tracks
5. Apply per-track ratchet:
   - independent ratchet: each track keeps/reverts its own parameter changes
   - composite ratchet: keep only if overall composite improves
6. Record step in conversation state
```

Step record schema:
```
id:            run_03_r2_l1_s4
parameters:    {param: value, ...}
play:          play_name | null
track_scores:  {track_name: score, ...}
composite:     float
judge_notes:   {track_name: rationale, ...}
constraints:   passed | rejected (+ which constraint)
cost:          {tokens: n}
outcome:       keep | revert | partial_keep | rejected_constraint
```

### Lap completion

When all steps in a lap are done:
```
score_distribution: {mean, std, max, min}
verdict:            promising | exhausted | noisy
  - promising:  mean score above lap threshold and improving
  - exhausted:  score has plateaued across steps with low variance
  - noisy:      high variance; more steps needed to confirm
hypothesis_result:  confirmed | partial | refuted
budget_used:        {tokens, steps}
```

If verdict is `noisy` and budget allows, the lap may request additional steps
before closing. The budget controller gates this.

### Round reflection

**Every round ends with a recorded reflection, without exception.**
The reflection is not optional even when nothing changes. A "no change" record
is valuable: it documents that the question was considered.

```
ROUND REFLECTION
round_id:
laps_completed:
score_trajectory:    [list of lap means]
track_trajectories:  {track: [scores]}    ← per-track view
limiting_track:      <which track is the current ceiling>

QUESTION 1 — Worth pursuing?
assessment:    yes | no | uncertain
reasoning:     [2–4 sentences]

QUESTION 2 — Ask the user?
trigger:       none | stuck | diverging_tracks | pace_risk | constraint_conflict
message:       [specific, actionable question if triggered — not "we're stuck"]

QUESTION 3 — Pivot?
decision:      none | minor | major | abandon
reasoning:     [required even if none]
next_round_strategy: [what changes, if anything]

budget_remaining:   %
pace_projection:    expected score at budget exhaustion
```

Ask-user triggers (automatic):
- Score has not improved across two consecutive rounds
- Two or more tracks are diverging (improving one reliably hurts another)
- Budget is 50% consumed with < 30% of target score achieved
- All laps in round returned `exhausted`
- A required track is consistently failing with no clear fix

When asking the user, be **specific**. Not "we're stuck" but:
> "Improving documentation quality (track score: 0.74) consistently reduces
> type correctness (track score drops from 1.0 to 0.91) because the added
> comments confuse pyright's inference. Should I relax the type correctness
> threshold, or is that a hard requirement?"

---

## Phase 4: Memory and learning

Read `references/memory.md` for the full memory architecture.

### Short-term memory (within run)
- Full step log (maintained in conversation state)
- Hypothesis stack with provenance
- Track trajectories
- Score momentum signal
- Failed hypotheses with failure modes (not just "failed" — *why*)

### Long-term memory (disposition library)
Available only when a connector or project pack is present.

Keyed on `(problem_class, action_intent)`. Each entry is a natural-language
conditioned prior on how to approach this class of action on this class of problem.

The memory agent runs a **consolidation pass** at the end of each round:
- Does any disposition need updating based on this round's evidence?
- Did a disposition prove wrong? Flag it with a negative exemplar.
- Should a problem class be forked? (Two sub-classes behaving differently)

If running in `project_pack` mode, emit updated pack files and instruct the user
to sync them back into project knowledge manually.

If running in `none` mode, skip long-term memory operations entirely and note this
in the final report.

The memory agent may run a **meta-research step** only when the mission has
explicitly enabled external research. If research is disabled, skip this path and
continue using only local evidence, run history, user guidance, and bundled
references.

---

## Phase 5: Post-run report

The final report must contain:
- Baseline vs final scores per track
- Score trajectory summary
- Round reflection log (all rounds, verbatim)
- What worked (confirmed plays and dispositions)
- What didn't (refuted hypotheses, with failure modes)
- Suggested follow-up directions
- Disposition updates proposed (user can approve or reject)
- Full budget accounting
- Memory sync instructions (if running in project_pack mode)

---

## Reference files

Read these when the relevant section is reached:

| File | When to read |
|---|---|
| `references/adapter-claude-ai.md` | Memory access modes and hard limits for this runtime |
| `references/runtime-capabilities.md` | Capability summary for this runtime |
| `references/memory.md` | Memory architecture notes for this runtime |
