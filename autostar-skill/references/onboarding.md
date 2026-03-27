# Onboarding reference

Onboarding is a structured interview, not a form fill. Work through the four
phases below in order. At every checkpoint marked **[ASK]**, you must stop
and use the `ask_user` tool before proceeding. Do not infer and continue.

If the user's initial message already answers a question, present that answer
as a pre-selected option and ask them to confirm or change it. Never silently
accept an inferred value.

---

## Phase A: Goal decomposition

### A1. Open goal description

If the user has not already described their goal in detail, ask in prose
(not ask_user — this is genuinely open-ended):

> "Before we configure anything, describe what a perfect output looks like.
> Don't worry about measurability — just tell me what 'good' means here.
> What would make you look at the result and say 'yes, that's it'?"

Read their answer carefully. Identify the distinct qualities they mentioned.
A good goal description usually contains 2–6 separable dimensions. Name them.

### A2. Track candidates [ASK]

Present your inferred tracks as a multi-select. Introduce the widget with prose:

> "From your description I can see a few distinct qualities we could track
> and optimise independently. Select the ones that matter — and tell me
> below the widget if I've missed any."

```
ask_user(
  question: "Which of these dimensions should we track and optimise?",
  type: multi_select,
  options: [<inferred track 1>, <inferred track 2>, ..., "Something else"]
)
```

If they select "Something else", follow up in prose. Add it to the list
and loop back to confirm the full set before moving on.

**Example (Python API handler):**
User said: "I want it cleaner, faster, and safer."
Inferred tracks to present: Code readability, Docstring quality,
Response latency, Type correctness, No security vulnerabilities.

### A3. Required vs preferred [ASK]

For each confirmed track, ask explicitly. Do not assume. Run one widget
per track — batch them so the user sees all in one go:

> "Some tracks are absolute requirements — the output fails if they don't
> pass, regardless of everything else. Others are preferences where a lower
> score is acceptable. For each track, which is it?"

```
ask_user(
  question: "Is '[track name]' a hard requirement or a preference?",
  type: single_select,
  options: ["Hard requirement — failure if not met", "Preference — weighted in the score"]
)
```

Repeat for each track. If the user marks everything as required, probe gently:

> "If all tracks are required, the optimiser has very little room to work.
> Are any of these more 'it would be nice' than truly mandatory?"

### A4. Relative importance of preferences [ASK]

For tracks marked as preferences only:

```
ask_user(
  question: "Rank these tracks by importance (top = most important):",
  type: rank_priorities,
  options: [<preference tracks>]
)
```

Convert the ranking to weights and reflect them back in prose:
> "So type correctness (0.35) counts for more than documentation quality
> (0.20) in the composite score. Does that feel right?"

Ask for verbal confirmation before committing the weights.

---

## Phase B: Verifier elicitation

For each track, determine how it will be evaluated. Work through required
tracks first, then preferences in priority order.

### Runtime gate

As soon as the verifier types are known for the mission, run a runtime
compatibility check before spending time on detailed rubric/budget work.

Use:

```bash
python scripts/runtime_profile.py check-mission <runtime-profile> \
  --verifier <type> \
  --verifier <type> \
  --require-file-read-write full
```

Add flags when needed:
- `--require-subprocess` if any track needs `external_tool` or subprocess-backed `hybrid`
- `--require-local-html` only if the user explicitly requires the rendered visualiser UI
- `--require-long-term-memory` if cross-run memory is required rather than optional

If the command fails:
1. stop onboarding
2. tell the user exactly which mission requirement the runtime cannot satisfy
3. ask whether to switch runtimes, remove the track, or accept a downgrade

Do this before deep rubric elicitation so unsupported verifier mixes are
rejected early.

### B1. Verifier type per track [ASK]

```
ask_user(
  question: "How should '[track name]' be evaluated?",
  type: single_select,
  options: [
    "Run a command-line tool automatically (pyright, pytest, axe, lighthouse, vale...)",
    "Check a precise rule or formula (word count, regex, schema validation...)",
    "AI judge with a scoring rubric I define",
    "Combination: a tool check AND an AI judge",
    "Pause and ask me each time (human gate)"
  ]
)
```

**If "command-line tool":**
Ask which tool in prose, or offer common options for the domain. Then confirm
availability:

> "I'll need [tool] installed and on PATH. Can you confirm it's available,
> or shall I suggest how to install it? If it's not available, I can use an
> AI judge as a fallback — lower confidence, but it'll work."

**If "AI judge" or "combination":**
Proceed to rubric elicitation (B2) before moving to the next track.

**If "human gate":**
Ask why it can't be automated — sometimes this reveals a rubric that can be.
If they confirm it genuinely needs human judgement, accept it and note that
it will pause the run and consume budget.

### B2. Rubric elicitation for LLM judge tracks

Claude drafts the rubric, but only from user-supplied anchors. Do not invent the
intent of the rubric yourself.

**Anchor the extremes** (prose):
> "For the '[track name]' judge:
> What does a perfect score — 1.0 — look like? Be specific.
> What does complete failure — 0.0 — look like?"

**Anchor the midpoint** (prose):
> "What does a middling result — roughly 0.5, neither good nor bad —
> look like for this track?"

**Name the failure modes** (prose):
> "What specific things should push the score down? What should the judge
> actively penalise?"

Draft the rubric from their answers and show it back. Then use a bounded approval:

```
ask_user(
  question: "For '[track name]', what should I do with this drafted rubric?",
  type: single_select,
  options: [
    "Keep this draft and move on",
    "Tighten the wording but keep the same intent",
    "Redo this track from my description"
  ]
)
```

If they choose "Tighten the wording", revise the draft and ask again.
If they choose "Redo this track", re-elicit the anchors.

Mark each accepted draft as **provisional** until all rubric-bearing tracks have
been drafted.

### B3. Final rubric review [ASK]

After all `llm_judge` and `hybrid` tracks have provisional drafts, show the full
rubric-bearing section of `tracks.md` back to the user. Make it explicit that
approval here locks the rubrics for the run.

```
ask_user(
  question: "Are these inferred rubrics correct and ready to lock for this run?",
  type: single_select,
  options: [
    "Yes — lock these rubrics",
    "Edit one specific track",
    "No — rework the rubric set"
  ]
)
```

If they choose "Edit one specific track", ask which track and loop back to B2 for
that track only. If they choose "No", ask which rubrics are off and revise only the
relevant drafts.

The rubrics are not committed until the user selects "Yes — lock these rubrics".
Once committed, they do not change during the run.

### B4. Runtime compatibility confirmation

Once all verifier types are selected, run the runtime gate immediately. If you
already ran it earlier in Phase B, summarise the result again here before moving on:

> "I've checked this mission against the active runtime profile. [It is compatible / It is not compatible because ...]."

If incompatible, do not proceed to constraints/budget until the user has
resolved the mismatch.

---

## Phase C: Constraint elicitation

### C1. Hard constraints [ASK]

Open with prose:
> "Are there things the output absolutely cannot do — things that would
> make the result unacceptable regardless of score? For example: must not
> exceed a certain length, must not change a function signature, must not
> introduce new dependencies."

After their answer, reflect the list back and ask for confirmation:

```
ask_user(
  question: "I've noted these as hard constraints. Anything to add or remove?",
  type: multi_select,
  options: [<inferred constraints from their answer> + "Add another" + "Remove one"]
)
```

### C2. Soft constraints

Ask in prose — soft constraints are usually idiosyncratic and don't benefit
from a widget:

> "Any stylistic or conventional preferences that should guide mutations,
> even if they're not deal-breakers? For example: prefer a certain naming
> convention, avoid a certain pattern, use a specific style guide."

### C3. External research policy [ASK]

Ask explicitly whether the run may use any external research beyond local files,
bundled references, installed tool help, and prior run memory.

```
ask_user(
  question: "May this run use external research if local guidance is insufficient?",
  type: single_select,
  options: [
    "No — local evidence only",
    "Yes — vendor docs / allowlisted sources only",
    "Yes — open web allowed with approval gates"
  ]
)
```

Rules:
- Default to `No — local evidence only` unless the user explicitly opts in
- If the user picks an external option, ask whether artifact text/code may be quoted externally; default to no
- If they want allowlisted sources only, ask them to name the allowed domains or source classes
- Reflect the resulting policy into `mission.json` / `mission.md` before execution
- If the user does not opt in, do not perform web search, documentation fetch, or remote best-practice lookup during the run

Summarise back and ask for verbal confirmation. No widget needed here.

---

## Phase D: Budget and plays

### D1. Budget ceiling [ASK]

Estimate cost per step based on the verifier types configured. Then present
three concrete options with real numbers, not vague descriptions. Fill in
the actual estimates before showing:

```
ask_user(
  question: "How thorough should this run be? (Each step costs ~[X] tokens / ~[Y]s)",
  type: single_select,
  options: [
    "Quick — ~30 steps, ~[N] tokens. Sense-check the space in [time].",
    "Standard — ~80 steps, ~[N] tokens. Proper exploration in [time]. Recommended.",
    "Thorough — ~150 steps, ~[N] tokens. Deep map of the space in [time].",
    "I'll set my own ceiling"
  ]
)
```

If they choose "I'll set my own ceiling", ask:

```
ask_user(
  question: "Which dimension do you want to cap?",
  type: single_select,
  options: ["Maximum steps", "Maximum tokens", "Maximum cost (USD)", "Maximum wall time"]
)
```

Then ask for the value in prose.

### D2. Budget allocation strategy [ASK]

```
ask_user(
  question: "How should budget be spread across experiments?",
  type: single_select,
  options: [
    "Front-loaded — explore widely early, converge later (good for novel problems)",
    "Track-priority — spend more on whichever track is furthest from target",
    "Confidence-weighted — spend more where results are noisy and uncertain",
    "Let me decide round by round — flag me when strategy should change"
  ]
)
```

### D3. Plays [ASK]

```
ask_user(
  question: "How should I handle parameter changes?",
  type: single_select,
  options: [
    "Group related parameters into coordinated plays (I'll propose bundles for approval)",
    "Change one parameter at a time — strictly atomic (cleaner attribution)",
    "Mix — use plays when parameters seem linked, atomic otherwise"
  ]
)
```

If plays are enabled, propose initial bundles in prose: name each one,
state which parameters it bundles, and the hypothesis behind it. Then:

```
ask_user(
  question: "Which of these proposed plays should I use?",
  type: multi_select,
  options: [<play name: one-line hypothesis> + "None — I'll describe my own" + "Skip plays for now"]
)
```

---

## Phase E: Final confirmation [ASK]

Before any step runs, show the complete mission summary in prose. Be explicit:

> "Here's the full configuration. Please read through before I begin anything."

Show:
- Tracks table: name | verifier type | required or weighted | weight
- Hard constraints: bulleted list
- Soft constraints: bulleted list
- Budget: ceiling, strategy
- Plays: enabled/disabled, list of approved plays

Then ask a single binary question:

```
ask_user(
  question: "Ready to begin the run?",
  type: single_select,
  options: [
    "Yes — run the baseline step and start",
    "No — I want to change something first"
  ]
)
```

If "No", ask in prose what they want to change and navigate directly to the
relevant phase. Do not restart the whole onboarding from the top.

Only proceed to Phase 2 of the main skill on explicit "Yes".
