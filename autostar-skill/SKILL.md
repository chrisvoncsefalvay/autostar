---
name: autostar
description: >
  Generalised autonomous optimisation loop — soft RLVR for any artifact a user can
  measure. Use this skill whenever a user wants to iteratively improve an artifact —
  code, prompts, documents, configs, designs, content — by running structured
  experiments, evaluating results against a multi-dimensional rubric, and learning
  from each attempt. Triggers include: "optimise this", "keep improving until it's
  good", "run experiments on", "autoresearch", "iterate on this overnight", "try
  different approaches and pick the best", or any request implying repeated
  evaluate-and-improve cycles. Also use when the user wants to improve a system
  prompt, a data pipeline, a writing style, or any artifact where quality can be
  decomposed into measurable tracks. For inference optimisation tasks (model
  latency, throughput, quantization, GPU deployment), a* delegates the
  low-level tuning to AITune while maintaining quality tracking and learning.
---

# a* (autostar)

A generalised autonomous optimisation loop — soft RLVR for the masses. The user
defines a goal; the system runs structured experiments, evaluates progress across
independent tracks, reflects at strategic checkpoints, and learns from every
attempt — including learning how to learn better the next time.

*If you can measure it, you can improve it.*

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

Before Phase 1, detect the host runtime's capabilities and map them onto the
abstract adapter contract in `references/runtime-capabilities.md`.

Use abstract capabilities first:
- `structured_choice` for bounded approvals
- `freeform_input` for open-ended elicitation
- `file_presentation` / `local_html` for rubric builder and visualiser
- `subprocess` for external-tool verifiers and render scripts
- `pause_resume` for human gates and round escalations

Claude-specific tools are examples of adapters, not the specification:
- Claude Code: `ask_user` + shell + browser/file paths
- Claude.ai: structured chat + `present_files`

If a capability is missing, follow the fallback policy in
`references/runtime-capabilities.md` before onboarding the mission.

Concrete runtime profiles and adapters live in:
- `runtime-profiles/claude-code.json`
- `runtime-profiles/codex.json`
- `runtime-profiles/gemini.json`
- `runtime-profiles/claude-ai.json`
- `runtime-profiles/pi.json`
- `runtime-profiles/chat-only.json`
- `runtime-profiles/template.json`
- `references/adapter-claude-code.md`
- `references/adapter-codex.md`
- `references/adapter-gemini.md`
- `references/adapter-claude-ai.md`
- `references/adapter-pi.md`
- `references/adapter-chat-only.md`
- `references/adapter-template.md`
- `scripts/runtime_profile.py`

Before detailed verifier/rubric work, check that the active runtime can support
the proposed mission. Use `scripts/runtime_profile.py check-mission` with the
current runtime profile and planned verifier types. If it fails, stop and
reconfigure before proceeding.

---

## Phase 1: Onboarding

**Do not begin execution until onboarding is complete and the user has approved the mission.**

Onboarding is an interactive dialogue, not a monologue. At every decision point you
must stop and ask the user rather than inferring and proceeding. Use the host
runtime's `structured_choice` capability for bounded decisions; in Claude Code
this maps to `ask_user`. Use open prose questions for genuinely open-ended inputs
(e.g. goal description, rubric wording).

The mandatory user-confirmation checkpoints are:

1. **Goal decomposition confirmed** — present inferred tracks as choices; user approves,
   removes, or adds before proceeding
2. **Required vs preferred** — for each track, explicitly ask; do not infer
3. **Verifier type per track** — present options; user selects
4. **Hard constraints confirmed** — present inferred list; user amends
5. **Budget** — present three concrete options; user selects
6. **Plays** — enabled/disabled, and approval of proposed bundles
7. **Final mission confirmation** — full summary; explicit go/no-go before any step runs

**Never skip a checkpoint.** If the user's initial message contained enough information
to pre-populate an answer, present it as a pre-selected option and ask them to confirm
or change it. Do not silently accept it.

**Rubric builder:** When configuring LLM judge tracks (onboarding checkpoint 2+),
surface the bundled rubric builder through the runtime's `local_html` or
`file_presentation` capability so the user can describe score anchors
interactively and get a generated rubric they can edit and confirm:

```bash
# Claude Code / terminal
open assets/rubric-builder.html          # macOS
xdg-open assets/rubric-builder.html     # Linux
start assets/rubric-builder.html         # Windows
```

If running in Claude.ai, use `present_files` on `assets/rubric-builder.html` instead.
If the runtime cannot surface local HTML, fall back to manual rubric elicitation as
defined in `references/runtime-capabilities.md`. The user exports a `tracks.md`
from the tool; load that as the confirmed track configuration. Only fall back to
manual elicitation for tracks the tool did not cover (external_tool,
deterministic, human_gate types do not need a rubric).

Read `references/onboarding.md` for the full dialogue flow, question wording, and
decision trees at each checkpoint. Read `references/runtime-capabilities.md`
before adapting this flow to a non-Claude host.

**Rubric builder UI:** When Phase B (verifier elicitation) reaches an `llm_judge`
or `hybrid` track, present `assets/rubric-builder.html` to the user before
configuring that track. The builder calls Claude to generate the rubric from the
user's anchor descriptions, lets them review and edit it inline, and exports
a `tracks.md` file you can use directly. Tell the user:

> "I'm opening the rubric builder for the [track name] track. Describe the score
> anchors, and it will draft the rubric for you to review and confirm."

After the user exports `tracks.md` from the builder, read it and use it as the
track configuration. Do not re-elicit rubrics that are already confirmed there.

The onboarding produces four documents, all stored in the run directory:

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
verifier types. Read `references/verification.md` for full configuration details and
examples for each type.

### 1. Deterministic programmatic
A function, script, or expression that produces a binary pass/fail or a bounded score
with no randomness. Does not require an LLM call.

**Use for:** word count, token count, regex match, JSON schema validation,
spelling/grammar (rule-based), mathematical constraints, format compliance.

```
verifier:
  type: deterministic
  fn:   word_count(artifact) <= 400
  returns: bool
```

### 2. External tool (subprocess)
A command-line tool invoked as a subprocess. The tool must be available in the
environment; the mission builder checks availability before the run starts.
Return code 0 = pass; non-zero = fail (unless score mode is configured).

**Common tools and what they verify:**

| Domain | Tool | What it checks |
|---|---|---|
| Python typing | `pyright`, `mypy` | Static type correctness |
| Python tests | `pytest` | Test suite passage |
| TypeScript | `tsc --noEmit` | Type correctness |
| JavaScript | `eslint` | Lint rules |
| Accessibility | `axe-cli`, `pa11y` | WCAG compliance |
| Web performance | `lighthouse-ci` | Perf / a11y / SEO scores |
| CSS | `stylelint` | Style rule compliance |
| Markdown | `markdownlint` | Document structure |
| OpenAPI | `vacuum` | API spec validity |
| Prose | `vale` | Style guide adherence |
| Security | `bandit`, `semgrep` | Vulnerability patterns |
| Build | `tsc`, `cargo check` | Compilation success |
| Inference perf | `aitune` | Model latency, throughput, memory (see AITune delegation below) |

```
verifier:
  type: external_tool
  command: pyright src/handler.py --outputjson
  parse_output: json_error_count   # or: exit_code, json_path, regex_capture
  returns: score  # 1.0 - (errors / lines)
  required_env: [python, pyright]
```

If a required tool is absent, the mission builder must either guide the user to
install it, or replace the track with an LLM judge approximation (lower confidence;
flagged in the run report).

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
A deterministic verifier AND an LLM judge, aggregated.

```
verifier:
  type: hybrid
  deterministic:  entity_checker(artifact, source)
  llm_judge:      factual_consistency_rubric
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

## Inference optimisation and AITune delegation

When the artifact being optimised is a **model's inference performance** —
latency, throughput, GPU memory during serving, or deployment configuration —
the mutation step should delegate to [AITune](https://github.com/ai-dynamo/aitune)
rather than blindly experimenting with inference configurations through the
a\* loop alone.

**Why this matters:** Inference optimisation has a structured search space
(backends, precision levels, compilation strategies) that AITune already
navigates well. a\*'s value here is in wrapping AITune with multi-dimensional
quality constraints (accuracy preservation, latency targets, memory budgets)
and the reflect-and-learn cycle — not in reinventing AITune's internal search.

**Detection during onboarding:** If the user's goal involves model serving
speed, inference latency, throughput, quantization for deployment, or
GPU-accelerated inference, flag this as an inference optimisation mission
during Phase 1 and suggest AITune delegation. Present it as an option:

> "This looks like an inference optimisation problem. I can delegate the
> low-level tuning (backend selection, quantization, graph optimisation) to
> AITune while keeping a\*'s quality tracking and learning loop around it.
> Would you like to use AITune for the inference tuning?"

If the user agrees, read `references/aitune.md` for the full delegation
protocol, including track templates, play design patterns, and correctness
validation setup. The key architectural point: each a\* step invokes AITune
with a parameter set; a\* evaluates the result against all tracks; the
ratchet and reflection machinery works as normal.

If AITune is not installed, offer the install command during Phase 2 tool
checks:
```bash
pip install --extra-index-url https://pypi.nvidia.com aitune
```

---

## Phase 2: Pre-run preparation

Before the first round begins:

1. **Check tool availability.** For every `external_tool` verifier, run a dry-fire
   check (`pyright --version`, `axe-cli --version`, etc.). Report any missing tools
   to the user and resolve before proceeding.

2. **Baseline run.** Execute one step with the unmodified artifact. Record baseline
   scores for all tracks. This is step `r0_l0_s0` and is never ratcheted.

3. **Query disposition library.** Retrieve relevant dispositions for this problem
   class. Surface them to the user briefly: "Based on previous runs, I know X about
   this class of problem."

4. **Propose initial plays** (if enabled). Present to user for approval or amendment.

5. **Confirm mission.** Show the user the complete `mission.md`, `tracks.md`, and
   `constraints.md` before any optimisation steps run. Do not proceed without
   explicit approval.

---

## Phase 3: Execution loop

### Progress visualisation

**VISUALIZATION POLICY: USE THE TEMPLATE — DO NOT IMPROVISE**

A prototype progress chart lives at `assets/inline-progress-chart.html`. **Use it
as a template** — do not invent your own visualisation from scratch, do not
generate random dashboards, and do not create standalone HTML files that open in a
browser. Claude Code supports inline HTML visuals in chat; use that capability.

To render the chart after each step:
1. Read `assets/inline-progress-chart.html` as a template
2. Replace the sample `STEPS`, `REFLECTIONS`, and `BUDGET` data with actual
   run data from `step_log.jsonl`, `reflections.jsonl`, and `progress.json`
3. Emit the resulting HTML inline in the conversation

**Re-render after every step** so the user always sees current state.

The chart has three visual components:

1. **Composite score chart** — staircase (step-style) curve for the winning
   trajectory (kept steps), with ghost dots for reverted alternatives. Each ghost
   dot connects back to its most recent kept ancestor via a pale bezier curve,
   showing what was tried and rejected. Reverted scores are labelled so the user
   sees what alternatives produced.

2. **Branch genealogy** — compact per-round row of kept/reverted dots grouped by
   lap, with the best score for the round.

3. **Round reflections** — structured cards for each round reflection, showing
   the three key questions (worth pursuing / ask user / pivot), reasoning,
   limiting track, budget remaining, and pace projection. **Do not** dump raw
   reflection text into the conversation — always render it through the template's
   structured card format.

**Do not** add per-track breakdowns, heatmaps, detailed step tables, or any other
visual elaboration beyond what the template provides. If the user wants more
detail, they can ask.

### Data files

The run directory contains machine-readable state for external consumption.
Keep these current but do not render them as visuals — they exist for
programmatic access, not for display.

**`runs/<run_id>/step_log.jsonl`** — one JSON record per line, one per step.
Same schema as the step record below. Appended after each step.

**`runs/<run_id>/tracks.json`** — array of track definitions:
```json
[{ "id": "type_correctness", "label": "type_correctness",
   "required": true, "weight": null }]
```
Written once at run start from the confirmed `tracks.md`.

**`runs/<run_id>/reflections.jsonl`** — one JSON record per line per round
reflection. Appended after each round.

**`runs/<run_id>/mission.json`** — run metadata:
```json
{ "run_id": "run_20260324", "budget": { "total_tokens": 120000 } }
```
Written once at run start.

**`runs/<run_id>/progress.json`** — machine-readable snapshot of current state.
Updated after every step. See `schemas/progress.schema.json` for the full
JSON Schema.

```json
{
  "run_id": "run_20260324",
  "status": "running",
  "updated_at": "2026-03-24T14:23:00Z",
  "baseline": { "composite": 0.45, "tracks": { "type_correctness": 0.80 } },
  "current":  { "composite": 0.82, "tracks": { "type_correctness": 0.95 }, "step_id": "r2_l1_s4" },
  "delta":    { "composite": 0.37, "tracks": { "type_correctness": 0.15 } },
  "budget":   { "total_steps": 80, "used_steps": 34, "remaining_pct": 57.5 },
  "rounds_completed": 2,
  "steps_completed": 34,
  "steps_kept": 18,
  "momentum": "exploiting_successfully",
  "limiting_track": "docstring_quality",
  "last_reflection": { "worth_pursuing": "yes", "pivot": "none", "pace_projection": 0.89 }
}
```

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
6. Write step record to short-term memory
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
cost:          {tokens: n, wall_s: n}
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
- Full step log
- Hypothesis stack with provenance
- Track trajectories
- Score momentum signal
- Failed hypotheses with failure modes (not just "failed" — *why*)

### Long-term memory (disposition library)
Keyed on `(problem_class, action_intent)`. Each entry is a natural-language
conditioned prior on how to approach this class of action on this class of problem.

The memory agent runs a **consolidation pass** at the end of each round:
- Does any disposition need updating based on this round's evidence?
- Did a disposition prove wrong? Flag it with a negative exemplar.
- Should a problem class be forked? (Two sub-classes behaving differently)

The memory agent may run a **meta-research step** only when the mission has
explicitly enabled external research. If research is disabled, skip this path and
continue using only local evidence, run history, user guidance, and bundled
references.

If enabled and disposition confidence is below threshold for an upcoming action class:
1. Prefer local references, bundled docs, and tool help before any network fetch
2. If external lookup is still justified, prefer vendor docs or a mission allowlist over the open web
3. Do not send artifact contents, source code, secrets, or proprietary identifiers to external services unless the user separately approved that disclosure
4. Synthesise into a candidate disposition
5. Apply on the next action
6. Observe outcome; confirm or reject the looked-up guidance
7. Record provenance: `looked_up_from_web | learned_from_run | user_specified`

---

## Phase 5: Post-run report

The final report must contain:
- Baseline vs final scores per track
- Score trajectory chart (text-based if no rendering available)
- Round reflection log (all rounds, verbatim)
- What worked (confirmed plays and dispositions)
- What didn't (refuted hypotheses, with failure modes)
- Suggested follow-up directions
- Disposition updates proposed (user can approve or reject)
- Full budget accounting

---

## Reference files

Read these when the relevant section is reached:

| File | When to read |
|---|---|
| `references/onboarding.md` | Phase 1 — building mission, tracks, constraints, plays |
| `references/verification.md` | When configuring any track verifier |
| `references/budgeting.md` | When setting or projecting budget |
| `references/memory.md` | When reading/writing disposition library |
| `references/runtime-capabilities.md` | Before adapting a* to any non-Claude runtime |
| `references/adapter-claude-code.md` | When running a* in Claude Code full-support mode |
| `references/adapter-codex.md` | When running a* in Codex full-support mode |
| `references/adapter-gemini.md` | When running a* in Gemini CLI full-support mode |
| `references/adapter-claude-ai.md` | When running a* in Claude.ai reduced-support mode |
| `references/adapter-pi.md` | When running a* in Pi full-support mode |
| `references/adapter-chat-only.md` | To understand the unsupported chat-only boundary |
| `references/adapter-template.md` | When creating a new runtime adapter |
| `references/aitune.md` | When mission involves inference optimisation (latency, throughput, quantization, GPU deployment) |

## Assets

Present these to the user at the indicated phase:

| File | Phase | Purpose |
|---|---|---|
| `assets/rubric-builder.html` | Phase 1 — Phase B verifier elicitation | Interactive rubric drafting and confirmation for LLM judge tracks |
| `assets/inline-progress-chart.html` | Phase 3 — after every step | **Template** for inline progress visualisation. Inject run data and render in chat. Do not invent your own chart — use this. |

## Scripts

| File | When to run |
|---|---|
| `scripts/runtime_profile.py list|show|select|validate` | When choosing, inspecting, or validating runtime profiles |
| `scripts/runtime_profile.py check-mission ...` | After verifier selection, before rubric/budget deepening |
