# Budgeting reference

---

## Budget dimensions

Budget can be set along any combination of these axes:

| Dimension | Unit | Hard ceiling |
|---|---|---|
| Steps | count | Yes |
| Tokens | approximate count | Yes |
| Cost | USD | Yes |
| Wall time | minutes | Yes |
| Rounds | count | Yes |

A run stops when **any** hard ceiling is reached. Recommend setting at
least two dimensions: one primary (steps or cost) and one safety
(wall time). This prevents runaway costs from slow tools or unexpected
token inflation.

**Meta budget:** Reserve 10–15% of total token/cost budget for
infrastructure: round reflections, user queries, memory consolidation,
and the final report. This reservation is protected and cannot be
consumed by experiment steps. Set at run start; do not adjust during run.

---

## Allocation strategies

### 1. Front-loaded exploration
Spend more budget in early rounds on wide exploration (more laps, larger
parameter ranges). Converge aggressively in later rounds.

**Budget split example (100 steps):**
```
Round 1: 40 steps — 5 laps × 8 steps, wide parameter ranges
Round 2: 35 steps — 4 laps × 8-9 steps, narrowed to promising families
Round 3: 25 steps — 3 laps × 8 steps, exploit best directions
```

**When to use:** Novel problem class; no strong prior dispositions; first
run on this artifact type.

### 2. Track-priority allocation
Allocate more steps to tracks on the critical path; fewer to tracks
already passing comfortably.

At the start of each round, compute:
```
track_budget_share[t] = (1.0 - track_score[t]) × track_weight[t]
normalise to sum to 1.0
```

Laps that primarily affect a high-deficit track get more steps.

**When to use:** Multiple tracks with uneven baselines; one track is
clearly the bottleneck.

### 3. Confidence-weighted
Allocate more steps to laps where the score distribution shows high
variance (the `noisy` verdict). Fewer steps to laps with clear verdicts.

Each lap requests a step count based on its current variance estimate:
```
if std > 0.10: request 2 additional steps
if std > 0.20: request 4 additional steps
cap at lap_max_steps
```

**When to use:** Stochastic generators or LLM judge variance is high;
need reliable evidence before advancing the ratchet.

### 4. Pace-aware
The budget controller maintains a running projection:

```
steps_remaining = (budget_remaining) / (avg_step_cost)
improvement_rate = regression over last N steps
projected_score = current_score + (steps_remaining × improvement_rate)

if projected_score < target × 0.85: → pace_risk flag
if projected_score > target × 1.10: → budget_slack flag
```

`pace_risk` feeds into the round reflection's "ask user" trigger.
`budget_slack` gives the orchestrator permission to explore rather
than exploit in the next round.

**Use this strategy always, in combination with others.** It is a
monitoring overlay, not a standalone allocation strategy.

### 5. Reserve-and-release
Hold back 20% of each round's budget as reserve. Release it if:
- The round's best lap is `promising` and additional steps would likely confirm
- A play has shown strong preliminary results across 2+ steps

Forfeit the reserve if:
- All laps returned `exhausted` by the halfway point
- The round is clearly plateau'd

**When to use:** When you want to be aggressive on strong signals while
not wasting budget on weak directions.

---

## Budget negotiation dialogue

Present the user with a concrete proposal:

> "Based on your tracks (N required, M weighted) and the verifier types,
> a single step will cost approximately X tokens. Here are three options:
>
> **Quick pass (30 steps):** ~Y tokens / ~$Z. Gives you a rough sense of
> the improvement space. 2–3 rounds, limited exploration.
>
> **Standard run (80 steps):** ~Y tokens / ~$Z. Proper exploration +
> exploitation. 3–4 rounds with reflections. Recommended for most tasks.
>
> **Thorough run (150+ steps):** ~Y tokens / ~$Z. Deep map of the parameter
> space. 5+ rounds. Best for critical artifacts or novel problem classes.
>
> You can also set a hard cost ceiling and let me work within it."

Adjust estimates based on actual verifier costs (external tool calls are
cheap; LLM judge ensemble calls are expensive).

---

## Budget controller: decision table

The budget controller evaluates at the end of every lap:

| Condition | Action |
|---|---|
| Budget > 80% remaining | No action |
| Budget 50–80% remaining, pace on target | No action |
| Budget 50–80% remaining, pace_risk flag | Note in round reflection |
| Budget 30–50% remaining, pace_risk flag | Trigger "ask user" in next round reflection |
| Budget < 30% remaining | Switch to exploit-only strategy (no exploration) |
| Budget < 15% remaining | Final round; write post-run report after completion |
| Meta budget < 5% remaining | Stop experiments immediately; run final report |
| Any hard ceiling reached | Graceful shutdown; run final report |

---

## Cost estimation by verifier type

Rough guidance for budget estimation:

| Verifier type | Cost per step |
|---|---|
| Deterministic | Negligible |
| External tool (fast: pyright, tsc) | Negligible |
| External tool (slow: lighthouse, pytest with coverage) | 5–30 seconds wall time |
| LLM judge (ensemble: 1) | ~800–1500 tokens |
| LLM judge (ensemble: 2) | ~1600–3000 tokens |
| Mutation agent call | ~1000–2000 tokens |
| Orchestrator reasoning step | ~500–1000 tokens |
| Round reflection | ~1500–2500 tokens |

For a step with 2 required external tools + 3 LLM judge tracks (ensemble 1):
approximate cost ≈ 3500–5500 tokens + tool wall time.
