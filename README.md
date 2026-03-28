# a\* (autostar)

> *If you can measure it, you can improve it.*

**Soft RLVR for the masses.** a\* turns any measurable goal into a structured optimisation loop. You define what "good" looks like. a\* runs experiments, scores the results, learns from every attempt, and converges on the best version within your budget.

No reward model to train. No environment to build. No GPU cluster to provision. Just a goal, an evaluator, and an agent that knows how to search.

[![License: MIT](https://img.shields.io/badge/License-MIT-f59e0b.svg)](LICENSE)
[![Skill format](https://img.shields.io/badge/format-.skill-38bdf8.svg)](#installation)
[![Works with Claude Code](https://img.shields.io/badge/works%20with-Claude%20Code-a78bfa.svg)](https://claude.ai/claude-code)

---

## Fastest path

If you just want to install the skill and try it once in Claude Code:

```bash
git clone https://github.com/chrisvoncsefalvay/autostar.git
cp -r autostar/autostar-skill ~/.claude/skills/autostar-skill
```

Then invoke it in Claude Code:

```text
/skill autostar
```

The skill handles onboarding, confirms the mission with you, and runs experiments within your approved budget.

---

## What this is

Most artifacts live where quality is real but hard to verify fully. Code can be type-checked but not beauty-checked. Prose can be spell-checked but not tone-checked.

Traditional RLVR (reinforcement learning from verifiable rewards) needs rewards you can compute with certainty: math proofs, unit tests, formal proofs. That covers a narrow slice of what people want to improve.

a\* uses **verifiable-ish rewards** instead. It combines hard signals (type checkers, linters, test suites) with soft ones (LLM judges, human gates). Each track has its own verifier. The system runs enough steps per lap to build statistical confidence.

The result: an optimisation loop for anything you can split into measurable dimensions. Code quality, documentation, prompt engineering, writing style, API design, accessibility.

**This is not autoresearch.** Autoresearch optimises one prompt against one metric. a\* optimises any artifact against multiple tracks, with budget-aware search and cross-run learning.

---

## How it works

a\* runs in five phases:

### 1. Onboarding

An interactive dialogue — never skipped, never auto-inferred. The system breaks your goal into **tracks** (measurable dimensions), sets up verifiers, sets constraints, agrees a budget, and gets your approval before running.

### 2. Pre-run preparation

Baseline measurement, tool checks, disposition library query, and final mission confirmation.

### 3. Execution loop

The core cycle:

```
Step  → mutate artifact, evaluate all tracks, ratchet (keep/revert)
Lap   → N steps with same parameter family → statistical verdict
Round → set of laps → mandatory reflection (worth pursuing? ask user? pivot?)
```

Each round ends with a structured reflection: *Worth pursuing? Ask the user? Pivot?* The system escalates when scores plateau, tracks diverge, or budget pace is at risk — always with specific questions, not vague updates.

A built-in **visualiser** renders live progress as an inline HTML dashboard.

### 4. Memory and learning

Three memory stores:

| Store | Scope | Purpose |
|---|---|---|
| **Short-term** | Within run | Step log, hypothesis stack, score trajectories, momentum |
| **Episodic** | Across runs | Round reflections verbatim; run summaries |
| **Dispositions** | Across runs | Learned priors keyed on (problem class, action intent) |

Dispositions are the long-term knowledge base. They shape future actions based on what worked and what didn't.

### 5. Post-run report

Baseline vs. final scores, trajectory charts, reflection log, what worked, what didn't, and budget accounting.

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

Verifiers are **immutable during a run**. Changing the evaluator mid-run is the main failure mode of autonomous optimisation — a\* prevents it by design.

### External judges

LLM judge tracks run in **self** mode (host agent judges inline) or **external** mode (separate model via subprocess). External mode keeps mutator and judge independent, and handles safety-filter conflicts: sensitive domains can use a judge that won't refuse to score legitimate content.

The contract: a\* writes a JSON request, calls your command, and reads a JSON response (score + rationale) from stdout. Bring any model with a CLI wrapper.

### Safety-filter resilience

When a safety filter refuses an LLM call, a\* rephrases and retries up to twice. If retries fail, it offers the user specific options: switch to an external judge, adjust criteria, skip the track, or abort. All rejections are logged.

---

## Progress format

a\* writes structured, machine-readable output for external tools:

| File | Format | Updated |
|---|---|---|
| `step_log.jsonl` | JSONL | After every step |
| `reflections.jsonl` | JSONL | After every round |
| `tracks.json` | JSON | Once at run start |
| `mission.json` | JSON | Once at run start |
| **`progress.json`** | JSON | **After every step** |

`progress.json` is the single-file state snapshot. Poll it from dashboards, CLI tools, or downstream agents without parsing JSONL. Schemas for all formats are in `schemas/`.

---

## Installation

### Prerequisites

- Claude Code (for the native install path below)
- Python 3 + `pyyaml` (for validation/packaging scripts)
- `unzip` (if installing from a release archive)

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

The `.skill` format is a ZIP archive with `SKILL.md` and supporting files. Other agent frameworks can use it through a runtime adapter — see `autostar-skill/references/runtime-capabilities.md`. Without that layer, treat compatibility as partial.

Bundled adapters: Claude Code, Codex, Gemini CLI, Pi (full support); Claude.ai (reduced support); chat-only (unsupported boundary). Profiles and a template for new adapters live in `autostar-skill/runtime-profiles/`.

Inspect or select profiles with:

```bash
python autostar-skill/scripts/runtime_profile.py list
python autostar-skill/scripts/runtime_profile.py show claude-code
python autostar-skill/scripts/runtime_profile.py check-mission claude-code --verifier external_tool --verifier llm_judge
```

### Validation

```bash
python -m pip install pyyaml
python autostar-skill/scripts/quick_validate.py autostar-skill/
```

---

## Usage

Invoke the skill in Claude Code:

```
/skill autostar
```

Or trigger it with natural language:
- "Optimise this code until the type checker is happy and the docs are good"
- "Iterate on this API handler — improve readability, keep tests passing"
- "Find the best configuration for this pipeline"

a\* guides you through onboarding, gets your approval, and runs within your budget.

---

## Repository structure

```
autostar/
  autostar-skill/              # The distributable skill
    SKILL.md                   # Main instruction set
    assets/                    # Visualiser template
    scripts/                   # Packaging, validation, runtime profile tools
    references/                # Onboarding, verification, budgeting, memory,
                               #   runtime adapters (Claude Code, Codex, Gemini,
                               #   Pi, Claude.ai, chat-only, template)
    runtime-profiles/          # Machine-readable capability profiles per runtime
  schemas/                     # JSON Schemas for output formats
  .github/workflows/           # CI: validate on PR; CD: build .skill on tag
  LICENSE
  README.md
```

---

## Design philosophy

a\* is built on seven principles:

1. **No silent inference.** Every decision requires explicit user confirmation. Inferred values are defaults, never silent assumptions.

2. **Immutable evaluation.** Verifiers and scoring rules do not change during a run. The evaluator is the ground truth.

3. **Statistical confidence.** Laps run multiple steps to get distributions, not point estimates. Verdicts emerge from the data, not single observations.

4. **Bidirectional learning.** The system learns from success and failure equally. Failed attempts record their failure modes, not just "failed."

5. **Reflection without action.** Every round ends with a recorded reflection, even when nothing changes.

6. **User in the loop at key moments.** The system escalates on plateaus, diverging tracks, pace risk, and repeated failures — with specific questions, not vague updates.

7. **Memory as decision-maker.** Dispositions shape every major action. The system gets better at the same class of problem over time.

These are hard constraints enforced by the skill's structure, not suggestions.

---

## Building and packaging

```bash
python -m pip install pyyaml
python autostar-skill/scripts/package_skill.py autostar-skill/ dist/
```

Validates the skill and produces `dist/autostar-skill.skill`.

---

## Contributing

Contributions are welcome. The skill's behaviour lives entirely in `SKILL.md` and its reference files — no runtime code to compile, no models to train.

Please open an issue before large changes.

---

## Author

**[Chris von Csefalvay](https://chrisvoncsefalvay.com)** ([@epichrisis](https://x.com/epichrisis))

Author of [*The Craft of Post-Training*](https://posttraining.guide) (No Starch Press).

---

## License

MIT. See [LICENSE](LICENSE).
