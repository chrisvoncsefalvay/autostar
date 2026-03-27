# Verification reference

Full configuration details and worked examples for each verifier type.
The main SKILL.md has the taxonomy summary; this file has the specifics.

---

## General principles

**Immutability:** No verifier, rubric, or scoring function may be modified
by any agent during a run. If a verifier is broken, the run must pause and
the user must be consulted. The evaluator is the ground truth; tampering
with it is the canonical failure mode of autonomous optimisation.

**Hard constraint gate:** Hard constraints are evaluated before any verifier
runs. A constraint violation costs nothing (no verifier calls) and records
`outcome: rejected_constraint`. This is deliberate — do not score artifacts
that violate hard requirements.

**Track evaluation order:** Evaluate required tracks first. If a required
track fails, skip non-required track evaluation for that step. This
preserves judge budget.

**Score normalisation:** All track scores must be normalised to [0.0, 1.0]
before composite calculation. The verifier configuration specifies how.

---

## 1. Deterministic programmatic

### Configuration
```yaml
verifier:
  type: deterministic
  expression: <python expression | shell expression>
  returns: bool | float
  normalise: <formula if float, e.g. "1.0 - (count / max_count)">
```

### Common patterns

**Boolean (pass/fail):**
```yaml
expression: "word_count(artifact) <= 400"
returns: bool
```
Score: 1.0 if true, 0.0 if false. Usually used for required tracks.

**Count-based score:**
```yaml
expression: "grep -c 'TODO' artifact.py"
returns: float
normalise: "max(0.0, 1.0 - (count / 10))"  # 0 TODOs = 1.0; 10+ TODOs = 0.0
```

**Regex presence:**
```yaml
expression: "re.search(r'GDPR-\\d+', artifact)"
returns: bool
```

**Format compliance (JSON schema):**
```yaml
expression: "jsonschema.validate(artifact, schema)"
returns: bool  # raises on failure; catch and return 0.0
```

### Notes
- Keep expressions simple. Complex logic belongs in a helper script
  (then call the script as an external_tool).
- Deterministic verifiers should be fast (< 1 second). If slower,
  consider whether it's really a subprocess call.

---

## 2. External tool (subprocess)

### Configuration
```yaml
verifier:
  type: external_tool
  command: <shell command with {artifact} placeholder>
  parse_output: exit_code | json_error_count | json_path | regex_capture | custom
  returns: bool | float
  normalise: <if float>
  required_env: [list of executables that must be present]
  timeout_s: 30  # default; increase for slow tools
```

### Parse modes

**exit_code:** Pass if return code is 0, fail otherwise. Simplest mode.
```yaml
command: "tsc --noEmit {artifact}"
parse_output: exit_code
returns: bool
```

**json_error_count:** Tool outputs JSON; count error-level entries.
```yaml
command: "pyright {artifact} --outputjson"
parse_output: json_error_count
returns: float
normalise: "1.0 - min(1.0, error_count / 20)"
```

**json_path:** Extract a specific value from JSON output.
```yaml
command: "lighthouse-ci {url} --output=json"
parse_output: json_path
path: ".categories.accessibility.score"
returns: float  # already 0.0–1.0 from Lighthouse
```

**regex_capture:** Capture a value from stdout with a regex.
```yaml
command: "pytest {artifact} -v --tb=no -q"
parse_output: regex_capture
pattern: "(\\d+) passed, (\\d+) failed"
formula: "passed / (passed + failed)"
returns: float
```

**custom:** For tools with non-standard output, provide a parse script.
```yaml
command: "vale --output=JSON {artifact}"
parse_output: custom
parse_script: "scripts/parse_vale.py"
returns: float
```

### Worked examples by domain

**Python type checking (pyright):**
```yaml
TRACK: type_correctness
required: true
weight: null  # required; not weighted
verifier:
  type: external_tool
  command: "pyright {artifact} --outputjson"
  parse_output: json_error_count
  json_path: ".summary.errorCount"
  returns: float
  normalise: "1.0 if errors == 0 else 0.0"  # treat as binary for required track
  required_env: [pyright]
  timeout_s: 15
```

**Python tests (pytest):**
```yaml
TRACK: test_passage
required: true
verifier:
  type: external_tool
  command: "pytest tests/ -x --tb=short -q"
  parse_output: regex_capture
  pattern: "(\\d+) passed"
  formula: "passed / total_tests"  # total_tests read from separate count step
  returns: float
  required_env: [pytest]
  timeout_s: 60
```

**TypeScript (tsc):**
```yaml
TRACK: ts_type_correctness
required: true
verifier:
  type: external_tool
  command: "tsc --noEmit --strict"
  parse_output: exit_code
  returns: bool
  required_env: [tsc]
```

**Accessibility (axe-cli):**
```yaml
TRACK: wcag_compliance
required: false
weight: 0.30
verifier:
  type: external_tool
  command: "axe {url} --reporter=json"
  parse_output: json_path
  path: ".violations.length"
  returns: float
  normalise: "max(0.0, 1.0 - (violations / 10))"
  required_env: [axe]
```

**Web performance (Lighthouse):**
```yaml
TRACK: performance_score
required: false
weight: 0.25
verifier:
  type: external_tool
  command: "lighthouse-ci {url} --output=json --quiet"
  parse_output: json_path
  path: ".categories.performance.score"
  returns: float  # Lighthouse already returns 0.0–1.0
  required_env: [lighthouse-ci]
```

**Prose style (Vale):**
```yaml
TRACK: style_compliance
required: false
weight: 0.20
verifier:
  type: external_tool
  command: "vale --output=JSON {artifact}"
  parse_output: custom
  parse_script: "scripts/parse_vale_score.py"
  returns: float
  required_env: [vale]
```

**Security (Bandit):**
```yaml
TRACK: no_vulnerabilities
required: true
verifier:
  type: external_tool
  command: "bandit -r {artifact} -f json -ll"
  parse_output: json_path
  path: ".results | length"
  returns: float
  normalise: "1.0 if high_severity == 0 else 0.0"
  required_env: [bandit]
```

**Latency benchmark:**
```yaml
TRACK: response_latency
required: false
weight: 0.25
verifier:
  type: external_tool
  command: "python scripts/bench_latency.py {artifact} --runs=10"
  parse_output: regex_capture
  pattern: "p95_ms: ([\\d.]+)"
  formula: "max(0.0, 1.0 - (p95_ms / target_ms))"
  target_ms: 200
  returns: float
  required_env: [python]
```

### Environment check protocol
Before the run starts, fire `{tool} --version` or equivalent for every
`required_env` entry. Collect results and report:

```
Tool availability:
  [OK] pyright 1.1.390
  [OK] pytest 8.3.2
  [MISSING] axe-cli  NOT FOUND
```

For any missing tool:
1. Tell the user and offer installation command
2. Offer to replace the track with an llm_judge approximation
3. Do not begin the run until resolved

---

## 3. LLM judge

### Configuration

**Self mode** (default — host agent evaluates inline):
```yaml
verifier:
  type: llm_judge
  judge: self
  rubric: <text>
  temperature: 0.1  # always low; judge must be stable
  ensemble: 1 | 2  # 2 for high-stakes tracks
  returns: float  # 0.0–1.0
  rationale: required  # always; feeds round reflection
  rejection_fallback: skip_step  # skip_step | score_zero | auto_rephrase_and_continue
```

**External mode** (separate model via subprocess):
```yaml
verifier:
  type: llm_judge
  judge: external
  command: "python scripts/judge_gemini.py {request_file}"
  rubric: <text>
  ensemble: 1
  returns: float
  rationale: required
  timeout_s: 30
  rejection_fallback: skip_step
```

### External judge contract

The system writes a JSON request file and the command must print JSON to stdout.

**Request file** (written by a* to a temp path, passed as `{request_file}`):
```json
{
  "rubric": "Score 0.0–1.0. Evaluate the readability of ...",
  "artifact": "def hello():\n    print('world')\n",
  "track_name": "readability",
  "temperature": 0.1,
  "context": "Python API handler for a healthcare data pipeline"
}
```

**Expected stdout** (JSON):
```json
{
  "score": 0.78,
  "rationale": "Function names are clear but nesting depth exceeds 3 levels."
}
```

If the external judge returns a non-zero exit code or unparseable output,
treat as a rejection and follow the rephrase-and-retry protocol.

### Example external judge commands

**Gemini via Google AI CLI:**
```bash
python scripts/judge_gemini.py {request_file}
# Reads request, calls Gemini API, writes {"score", "rationale"} to stdout
# Requires GEMINI_API_KEY env var
```

**OpenAI-compatible API:**
```bash
python scripts/judge_openai.py {request_file} --model gpt-4o-mini
# Requires OPENAI_API_KEY env var
```

**Local model via Ollama:**
```bash
python scripts/judge_ollama.py {request_file} --model llama3.1
# Requires ollama running locally
```

**Any model via LiteLLM:**
```bash
python scripts/judge_litellm.py {request_file} --model gemini/gemini-2.0-flash
# Uses LiteLLM's unified interface; key env vars per provider
```

a* does not bundle these scripts. The user provides or writes their own.
The contract is: read the request JSON, call your model, print the response JSON.

### When to use external judges

- **Sensitive domains:** Medical, legal, security, pharmaceutical — where the
  host model's safety filters may refuse to evaluate legitimate content.
- **Evaluator independence:** When you want the mutator and the judge to be
  genuinely separate models to avoid self-evaluation bias.
- **Cost optimisation:** Use a cheaper model (e.g., Gemini Flash, GPT-4o-mini)
  for judge calls while keeping the expensive model for mutations.
- **Specialised capability:** Vision models for UI evaluation, code-specialised
  models for code review, domain-fine-tuned models for niche rubrics.

### Rubric writing guidelines

A good rubric specifies:
1. **What is being judged** (the specific quality, not the whole artifact)
2. **What 0.0 looks like** (concrete failure)
3. **What 1.0 looks like** (concrete excellence)
4. **What the midpoint looks like** (anchors the scale)
5. **What to penalise explicitly** (common failure modes)
6. **What not to consider** (scope boundaries)

Do not write vague rubrics like "Is this good? Score 0–1." The judge will
exploit ambiguity. Be specific.

### Example rubrics

**Code readability:**
```
Score 0.0–1.0. Evaluate the readability of the provided Python function,
considering only the code structure and naming — not its correctness or
documentation.

1.0: Function names and variable names are self-documenting. Logic flow
is immediately clear without mental simulation. Complexity is appropriately
decomposed. No magic numbers. Consistent style throughout.

0.5: Names are adequate but not precise. Some logic requires re-reading.
Minor inconsistencies in style or decomposition.

0.0: Names are generic or misleading. Logic flow is tangled. Significant
mental effort needed to understand purpose. Magic numbers present.

Penalise: inconsistent naming conventions, deeply nested conditionals
without extraction, single-letter variable names outside of well-established
conventions (loop indices, mathematical expressions).

Do not consider: correctness, performance, documentation.
```

**Tone appropriateness (customer communication):**
```
Score 0.0–1.0. Evaluate whether the tone of this customer-facing message
is appropriate for a professional services firm communicating about a
service disruption.

1.0: Warm but not effusive. Acknowledges the customer's inconvenience
without over-apologising. Active voice. Concrete about what happened and
what is being done. Does not use corporate jargon or deflecting language.

0.5: Either too formal (distant, bureaucratic) or too casual (overly
familiar). Apology present but vague. Some jargon.

0.0: Cold, defensive, or liability-driven language. Passive constructions
that obscure responsibility. Hollow phrases ("We apologise for any
inconvenience"). No concrete information.

Penalise: "any inconvenience caused", "as per", "please be advised",
excessive exclamation marks, unverifiable promises.
```

### Ensemble protocol
When `ensemble: 2`, make two independent judge calls with different seeds
(or shuffled prompt order). Average the scores. If the two scores differ
by more than 0.2, flag the step as `high_judge_variance` and record both
rationales. High variance indicates rubric ambiguity — consider refining
the rubric between rounds.

### Stability note
LLM judge scores have inherent variance. This is why laps run multiple
steps: to get a distribution, not a point estimate. Do not over-index on
a single step's judge score.

---

## 4. Hybrid

### Configuration
```yaml
verifier:
  type: hybrid
  components:
    - type: external_tool
      command: <...>
      weight: 0.4  # or: role: gate
    - type: llm_judge
      rubric: <...>
      weight: 0.6
  aggregation: min | mean | weighted | gate+score
```

### Aggregation modes

**min:** The more conservative score. Use when both checks must pass
independently (a high LLM score cannot compensate for a failed tool check).

**mean / weighted:** Standard average or weighted combination.

**gate+score:** The deterministic component is a binary gate. If it fails,
the composite is 0.0 regardless of the LLM score. If it passes, the LLM
score becomes the track score.

```yaml
# Example: factual accuracy
# Must pass entity check (required gate), then scored on coherence
components:
  - type: deterministic
    expression: "entity_checker(artifact, source_doc)"
    role: gate  # binary; failure = track score 0.0
  - type: llm_judge
    rubric: "factual_consistency_rubric"
    role: score
aggregation: gate+score
```

---

## 5. Human gate

Use sparingly. Budget cost is high (human time, not just tokens). The system
pauses and awaits input.

```yaml
verifier:
  type: human_gate
  prompt: <what you are asking the human to evaluate>
  scale: 0-10 | 0-100 | pass/fail | free_text
  normalise: <if numeric scale>
  timeout_action: skip | block | auto_score(value)
  timeout_s: 300
```

**When to use:**
- Legal or regulatory approval that cannot be automated
- Brand or aesthetic judgement where no proxy metric exists
- First run in a new domain where the automated rubric is untested

**When NOT to use:**
- Instead of writing a proper LLM judge rubric (laziness is not a reason)
- For tracks that can be approximated deterministically
- More than once per round (use the round reflection user escalation instead)
