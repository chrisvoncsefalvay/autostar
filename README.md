# a\* (autostar)

> *If you can measure it, you can improve it.*

**Soft RLVR for the masses.** a\* is an agent skill that turns any measurable goal into a structured optimisation loop. You define what "good" looks like. a\* runs experiments, evaluates outcomes against your criteria, learns from every attempt, and converges on the best result it can find within your budget. Think of it as Andrej Karpathy's autoresearch framework for... everything. From drug discovery to cookie recipes.

It is reinforcement learning without the infrastructure. No reward model to train, no environment to build, no GPU cluster to provision. Just a goal, an evaluator, and an agent that knows how to search.

[![License: MIT](https://img.shields.io/badge/License-MIT-f59e0b.svg)](LICENSE)
[![Skill format](https://img.shields.io/badge/format-.skill-38bdf8.svg)](#installation)
[![Works with Claude Code](https://img.shields.io/badge/works%20with-Claude%20Code-a78bfa.svg)](https://claude.ai/claude-code)

---

## Fastest path

If you just want to install the skill and try it once in Claude Code:

```bash
npx skills add chrisvoncsefalvay/autostar
```

Then invoke it in Claude Code:

```text
/skill autostar
```

The skill will handle onboarding, ask you to confirm the mission, and start running experiments within the budget you approve.

---

## What this is

Most interesting artifacts live in a space where quality is real but not perfectly verifiable. Code can be type-checked but not beauty-checked. Prose can be spell-checked but not tone-checked. A system prompt can be tested against benchmarks but not against "does it feel right."

Traditional RLVR (reinforcement learning from verifiable rewards) requires rewards you can compute with certainty: math proofs, unit tests, formal verification. That covers a narrow band of what people actually want to improve.

a\* works with **verifiable-ish rewards** instead. It combines hard signals (type checkers, linters, test suites) with soft ones (LLM judges with fixed scoring criteria, human gates) into a multi-track evaluation system. Each track has its own verifier. Some are deterministic; some are stochastic. The system handles both, running enough steps per lap to get statistical confidence rather than point estimates.

The result is an optimisation loop that works on anything you can decompose into measurable dimensions: code quality, documentation, prompt engineering, writing style, API design, accessibility compliance, configuration tuning.

**This is not autoresearch.** Autoresearch optimises one thing (usually a training recipe) against one metric. a\* optimises any artifact against a multi-dimensional evaluation model with independent tracks, budget-aware exploration, and cross-run learning via dispositions (learned priors that accumulate across runs).

---
## See it in action

### Fixing this very documentation

[![asciicast](https://asciinema.org/a/875847.svg)](https://asciinema.org/a/875847)

---

## How it works

a\* runs in five phases:

### 1. Onboarding

An interactive dialogue — never skipped, never auto-inferred. The system decomposes your goal into **tracks** (independently measurable dimensions), elicits verifier types and evaluation criteria for each, establishes hard constraints, negotiates a budget, and gets explicit confirmation before any experiment runs.

### 2. Pre-run preparation

Baseline measurement, tool availability checks, disposition library query (what has the system learned from previous runs on similar problems?), and final mission confirmation.

### 3. Execution loop

The core cycle:

```
Step  → mutate artifact, evaluate all tracks, ratchet (keep/revert)
Lap   → N steps with same parameter family → statistical verdict
Round → set of laps → mandatory reflection (worth pursuing? ask user? pivot?)
```

Each round ends with a structured reflection that answers three questions: *Worth pursuing? Ask the user? Pivot?* The system escalates to the user when scores plateau, tracks diverge, or budget pace is at risk — with specific, actionable questions, not vague "we're stuck" messages.

A built-in **visualiser** renders live progress as a self-contained HTML dashboard. On Claude surfaces with inline file rendering, the skill should present that visualisation inline rather than sending the user to an external browser.

### 4. Memory and learning

Three memory stores:

| Store | Scope | Purpose |
|---|---|---|
| **Short-term** | Within run | Step log, hypothesis stack, score trajectories, momentum |
| **Episodic** | Across runs | Every round reflection verbatim; run summaries |
| **Dispositions** | Across runs | Learned priors keyed on (problem class, action intent) |

Dispositions are the long-term knowledge base. They condition future actions based on what worked before — and what didn't. When no relevant disposition exists, a\* can run an optional **meta-research step** if the mission explicitly enables external research: look up best practices, synthesise into a candidate disposition, apply it, observe the outcome, and update confidence.

### 5. Post-run report

Baseline vs. final scores, trajectory charts, full reflection log, what worked, what didn't, disposition updates proposed for user approval, and budget accounting.

---

## Verification taxonomy

Every track declares one of five verifier types:

| Type | Signal | Use when |
|---|---|---|
| **Deterministic** | Formula / regex / rule | Word count, format compliance, schema validation |
| **External tool** | CLI subprocess | `pyright`, `pytest`, `eslint`, `lighthouse`, `vale`, `bandit` |
| **LLM judge** | Structured LLM call with fixed scoring criteria | Readability, tone, documentation quality |
| **Hybrid** | Tool + LLM judge, aggregated | Factual accuracy (entity check gates quality score) |
| **Human gate** | Pause and ask the user | Brand approval, legal sign-off, aesthetics |

Verifiers are **immutable during a run**. This is the canonical failure mode of autonomous optimisation — tampering with the evaluator. a\* enforces this by design.

### External judges

LLM judge tracks can run in **self** mode (the host agent evaluates inline) or **external** mode (a separate model is invoked via subprocess). External mode provides genuine evaluator independence — the model that mutates the artifact is not the model that judges it. This also solves the safety-filter problem: if the host model's AUP policies conflict with the domain (medical, security, pharmaceutical), an external judge with different policies can evaluate the content without refusals.

The external judge contract is simple: a\* writes a JSON request file (criteria + artifact), calls your command, and parses a JSON response (score + rationale) from stdout. Bring your own model — Gemini, GPT, Ollama, anything with a CLI wrapper.

### Safety-filter resilience

When an LLM call (mutation or judgement) is refused by safety filters, a\* treats it as a recoverable fault. It detects the refusal, rephrases with context framing or clinical distancing, and retries up to twice before escalating to the user with specific options (switch to external judge, adjust scoring criteria, skip track, or abort). Every rejection is logged for the post-run report. During onboarding, a\* proactively recommends external judges for domains likely to trigger filters.

---

## Progress format

a\* writes structured, machine-readable output designed for consumption by external tools:

| File | Format | Updated |
|---|---|---|
| `step_log.jsonl` | JSONL | After every step |
| `reflections.jsonl` | JSONL | After every round |
| `tracks.json` | JSON | Once at run start |
| `mission.json` | JSON | Once at run start |
| **`progress.json`** | JSON | **After every step** |

`progress.json` is the single-file snapshot of current state — designed for dashboards, CLI tools, webhooks, and downstream agents to poll without parsing JSONL:

```json
{
  "run_id": "run_20260324",
  "status": "running",
  "updated_at": "2026-03-24T14:23:00Z",
  "baseline":  { "composite": 0.45, "tracks": { "type_correctness": 0.80 } },
  "current":   { "composite": 0.82, "tracks": { "type_correctness": 0.95 } },
  "delta":     { "composite": 0.37, "tracks": { "type_correctness": 0.15 } },
  "budget":    { "total_steps": 80, "used_steps": 34, "remaining_pct": 57.5 },
  "momentum":  "exploiting_successfully",
  "limiting_track": "docstring_quality"
}
```

JSON Schemas for all output formats are in `schemas/`.

---

## Installation

### Prerequisites

- Claude Code for the native install path shown below
- Python 3 and `pyyaml` if you want to run the local validation or packaging scripts
- `unzip` if you install from a release archive
- A browser if you want to open the bundled visualiser locally

### Claude Code

```bash
# Clone the repo
git clone https://github.com/chrisvoncsefalvay/autostar.git

# Copy the skill into your Claude Code skills directory
cp -r autostar/autostar-skill ~/.claude/skills/autostar-skill
```

Or install via `skill.sh`:

```bash
npx skills add chrisvoncsefalvay/autostar
```

Or install directly from a release:

```bash
# Download the .skill file from the latest release
curl -sL https://github.com/chrisvoncsefalvay/autostar/releases/latest/download/autostar-skill.skill -o autostar.skill

# Unzip into your skills directory
unzip autostar.skill -d ~/.claude/skills/
```

### Other agents

The `.skill` format is a ZIP archive containing a `SKILL.md` (the main instruction set) and supporting files. Other agent frameworks can consume the skill, but they should do so through a runtime adapter for the capability surface a* expects: structured user choices, file/HTML presentation, subprocess execution, pause/resume, and file-backed run state.

The portability contract for that adapter is documented in `autostar-skill/references/runtime-capabilities.md`. Without that layer, compatibility should be treated as partial rather than drop-in.

This repo now includes a full-support Claude Code adapter in `autostar-skill/references/adapter-claude-code.md`, full-support Codex, Gemini CLI, and Pi coding-agent adapters in `autostar-skill/references/adapter-codex.md`, `autostar-skill/references/adapter-gemini.md`, and `autostar-skill/references/adapter-pi.md`, a reduced-support Claude.ai adapter in `autostar-skill/references/adapter-claude-ai.md` (also applicable to Claude Desktop/Mobile when they share the same inline presentation profile), an explicit unsupported chat-only boundary in `autostar-skill/references/adapter-chat-only.md`, and reusable runtime profile/template files under `autostar-skill/runtime-profiles/`.

You can inspect or select profiles with:

```bash
python autostar-skill/scripts/runtime_profile.py list
python autostar-skill/scripts/runtime_profile.py show claude-code
python autostar-skill/scripts/runtime_profile.py select --require-subprocess --verifier external_tool
python autostar-skill/scripts/runtime_profile.py check-mission claude-code --verifier external_tool --verifier llm_judge --require-subprocess
```

### Validation

For local validation/build tooling, install the Python dependency once:

```bash
python -m pip install pyyaml
```

Then run:

```bash
python autostar-skill/scripts/quick_validate.py autostar-skill/
```

---

## Usage

Once installed, invoke the skill in Claude Code:

```
/skill autostar
```

Or trigger it naturally with phrases like:
- "Optimise this code until the type checker is happy and the docs are good"
- "Run experiments on this prompt and find the best version"
- "Iterate on this API handler — improve readability, keep tests passing"
- "Autoresearch: find the best configuration for this pipeline"

a\* will guide you through onboarding, get your approval on the mission, and then run autonomously within your budget.

---

## Repository structure

```
autostar/
  autostar-skill/              # The distributable skill
    SKILL.md                   # Main instruction set (what the agent reads)
    assets/
      visualiser-template.html # Live progress dashboard
    scripts/
      render_visualiser.py     # Injects run data into the visualiser
      package_skill.py         # Packages skill folder into .skill ZIP
      quick_validate.py        # Validates SKILL.md structure
      runtime_profile.py       # Lists, validates, and selects runtime profiles
    references/
      onboarding.md            # Phase 1 dialogue flow
      verification.md          # Verifier type specs and examples
      budgeting.md             # Budget strategies and allocation
      memory.md                # Memory architecture and dispositions
      runtime-capabilities.md  # Adapter contract for non-Claude runtimes
      adapter-claude-code.md   # Concrete full-support Claude Code adapter
      adapter-codex.md         # Concrete full-support Codex adapter
      adapter-gemini.md        # Concrete full-support Gemini CLI adapter
      adapter-claude-ai.md     # Concrete reduced-support Claude.ai adapter
      adapter-pi.md            # Concrete full-support Pi coding-agent adapter
      adapter-chat-only.md     # Explicit unsupported chat-only boundary
      adapter-template.md      # Checklist for new runtime adapters
    runtime-profiles/
      claude-code.json         # Machine-readable Claude Code capability profile
      codex.json               # Machine-readable Codex capability profile
      gemini.json              # Machine-readable Gemini CLI capability profile
      claude-ai.json           # Machine-readable Claude.ai capability profile
      pi.json                  # Machine-readable Pi coding-agent capability profile
      chat-only.json           # Machine-readable unsupported chat-only profile
      template.json            # Starting point for new runtime adapters
  schemas/                     # JSON Schemas for output formats
    progress.schema.json
    runtime-profile.schema.json
    step-record.schema.json
    reflection.schema.json
    tracks.schema.json
    mission.schema.json
  .github/workflows/
    validate.yml               # CI: validate skill structure on PR
    release.yml                # CD: build .skill on tag push
  LICENSE
  README.md
```

---

## Design philosophy

a\* is built on seven principles:

1. **No silent inference.** Every decision point requires explicit user confirmation. Pre-populate inferred values as defaults; never silently assume.

2. **Immutable evaluation.** Verifiers, scoring criteria, and scoring functions do not change during a run. The evaluator is the ground truth. Tampering with it is the canonical failure mode.

3. **Statistical confidence.** Laps run multiple steps to get distributions, not point estimates. Verdicts (promising / exhausted / noisy) emerge from distribution analysis, not single observations.

4. **Learning is bidirectional.** The system learns from success and failure equally. Failed hypotheses are recorded with their failure modes, not just marked "failed." Dispositions carry both supporting and refuting exemplars.

5. **Reflection without action.** Every round ends with a recorded reflection, even when nothing changes. "No change" is valuable data — it documents that the question was considered.

6. **User in the loop at strategic points.** Not hovering over every step, but escalating when it matters: plateaus, diverging tracks, pace risk, consistent failures. With specific questions, not vague status updates.

7. **Memory as decision-maker.** Dispositions are not curiosities — they condition every significant action. The system gets better at optimising the same class of problem over time.

These principles are not suggestions to the agent. They are hard constraints enforced by the skill's structure.

---

## Building and packaging

To create a distributable `.skill` file:

```bash
python -m pip install pyyaml
python autostar-skill/scripts/package_skill.py autostar-skill/ dist/
```

This validates the skill structure and produces `dist/autostar-skill.skill`.

---

## Contributing

Contributions are welcome. The skill's behaviour is defined entirely by `SKILL.md` and its reference files — no runtime code to compile, no models to train. If you want to improve the optimisation loop, the evaluation system, or the memory architecture, those are the files to edit.

Please open an issue before large changes to discuss the approach.

---

## Author

**[Chris von Csefalvay](https://chrisvoncsefalvay.com)** ([@epichrisis](https://x.com/epichrisis))

Author of [*The Craft of Post-Training*](https://posttraining.guide) (No Starch Press). Building tools that make post-training techniques accessible to practitioners — because the gap between "this works in a paper" and "this works in my project" is where most of the value lives.

---

## License

MIT. See [LICENSE](LICENSE).
