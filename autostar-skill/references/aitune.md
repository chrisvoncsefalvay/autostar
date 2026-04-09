# AITune inference optimisation delegation

When the artifact being optimised involves **model inference performance** —
latency, throughput, memory footprint during serving, or GPU utilisation — a*
should delegate the low-level inference tuning to
[AITune](https://github.com/ai-dynamo/aitune) rather than blindly mutating
inference configurations through the experimental loop.

AITune is NVIDIA's inference optimisation toolkit. It systematically applies
compilation, quantization, and graph optimisation across multiple backends,
with built-in correctness validation. It does the heavy lifting of finding
optimal inference configurations; a* wraps it to ensure the result meets the
user's broader quality criteria (accuracy preservation, latency targets,
integration constraints).

---

## When to delegate to AITune

Delegate when the mission involves any of:

- Reducing model inference latency or improving throughput
- Optimising GPU memory usage during serving
- Applying quantization for deployment (int8, fp16, mixed precision)
- Compiling models for production serving (TensorRT, Torch-TensorRT, etc.)
- Tuning batch size / sequence length configurations for inference
- Deploying models to NVIDIA GPUs with hardware-specific optimisations

Do **not** delegate when the mission is about:

- Training optimisation (learning rate, batch size during training, loss tuning)
- Prompt optimisation or prompt engineering
- Data pipeline optimisation
- Non-NVIDIA deployment targets
- Artifacts that are not neural network models

The distinction matters because a*'s experimental loop is designed for problems
where the search space is broad and the evaluation is multi-dimensional. AITune
already has a principled search over inference backends — wrapping it in a*'s
explore-evaluate-reflect cycle adds structure around the *quality constraints*
(accuracy, latency targets, memory budgets) without reinventing AITune's
internal search.

---

## How the delegation works

### Architecture

```
a* (autostar)                         AITune
┌──────────────────────┐              ┌──────────────────────┐
│ Mission definition   │              │                      │
│ Track rubrics        │──  calls ──> │ Backend selection     │
│ Constraint checking  │              │ Quantization          │
│ Ratchet / scoring    │<── result ── │ Graph optimisation    │
│ Round reflection     │              │ Correctness checking  │
│ Disposition learning │              │ Artifact caching      │
└──────────────────────┘              └──────────────────────┘
```

a* owns the *what* (tracks, constraints, scoring, learning); AITune owns the
*how* (which backend, which precision, which graph transforms). Each a* step
invokes AITune with a parameter set and evaluates the result against all tracks.

### Step execution with AITune

Within the standard a* step loop, the mutation phase becomes an AITune
invocation instead of a direct artifact edit:

```
1. Select parameters for this step (backend, precision, batch config, etc.)
2. Invoke AITune with those parameters (see invocation patterns below)
3. AITune produces an optimised model artifact + its own validation report
4. a* runs all track verifiers against the optimised artifact
5. Composite scoring, ratchet, and memory update proceed as normal
```

The key difference from a normal a* step: the "mutation" is not a text edit
but an AITune compilation/tuning run. The artifact is the model; the
parameters are AITune configuration knobs.

---

## Installation and prerequisites

```bash
pip install --extra-index-url https://pypi.nvidia.com aitune
```

**System requirements:**
- Python 3.10+
- PyTorch 2.7+
- TensorRT 10.5.0+ (for TensorRT backend)
- Linux (Ubuntu 22.04+ recommended)
- NVIDIA GPU with appropriate CUDA support

During Phase 2 (pre-run preparation), check AITune availability:

```bash
python -c "import aitune; print(aitune.__version__)"
```

If missing, tell the user and offer the install command. Do not begin the run
without confirming the environment can support the intended backends.

---

## Supported backends

AITune supports multiple compilation backends. Each has different strengths:

| Backend | Best for | Trade-offs |
|---|---|---|
| **TensorRT** | Maximum throughput on NVIDIA GPUs | Longer compilation; static shapes preferred |
| **Torch-TensorRT** | PyTorch-native TensorRT integration | Good balance of speed and compatibility |
| **TorchAO** | Architecture-aware quantization | Flexible precision; PyTorch-native |
| **Torch Inductor** | Dynamic shapes, general compilation | Broad compatibility; less aggressive optimisation |

When constructing plays, each backend can be a parameter dimension. AITune's
own tuning logic handles the intra-backend search; a* handles the
inter-backend comparison and quality constraint checking.

---

## Tuning modes

### Ahead-of-time (AOT) tuning

The user marks specific modules for optimisation. Requires source access but
gives maximum control. The API examples below are illustrative — consult the
[AITune documentation](https://github.com/ai-dynamo/aitune) for current syntax.

```python
import aitune

# Illustrative — check AITune docs for current decorator API
@aitune.tune(backend="tensorrt")
class MyModel(nn.Module):
    ...
```

**When to use in a\*:** When the user has a specific model they want to optimise
and is willing to modify source code. The a\* mission can iterate over which
modules to mark, which backends to apply per module, and what precision to use.

### Just-in-time (JIT) tuning

AITune automatically detects optimisable modules without source modification.

```python
import aitune

# Illustrative — check AITune docs for current autotune API
model = load_my_model()
tuned_model = aitune.autotune(model, sample_input=sample)
```

**When to use in a\*:** When optimising an existing model without source changes,
or when the user wants AITune to find the best configuration automatically.
The a\* mission wraps this to validate that the auto-tuned result meets quality
constraints across all tracks.

---

## Typical track configurations for inference missions

These are starting points — adapt to the specific mission during onboarding.
The benchmark and validation scripts below are **user-provided** (a* does not
bundle them). The examples show the expected interface; the user writes or
adapts these for their model and evaluation setup. During onboarding, help the
user create or locate these scripts.

The `{artifact}` placeholder refers to the optimised model path. For accuracy
tracks, the user must also provide the path to the original (pre-optimisation)
model as a mission parameter — store it in `mission.md` as `BASELINE_MODEL`
and substitute `{baseline_model}` from there.

### Latency track (usually required)

```yaml
TRACK: inference_latency
required: true
verifier:
  type: external_tool
  command: "python scripts/bench_inference.py {artifact} --metric=p95_latency --runs=50"
  parse_output: regex_capture
  pattern: "p95_ms: ([\\d.]+)"
  formula: "max(0.0, 1.0 - (p95_ms / target_ms))"
  returns: float
  required_env: [python, aitune]
```

### Throughput track

```yaml
TRACK: throughput
required: false
weight: 0.30
verifier:
  type: external_tool
  command: "python scripts/bench_inference.py {artifact} --metric=throughput"
  parse_output: regex_capture
  pattern: "tokens_per_sec: ([\\d.]+)"
  formula: "min(1.0, tokens_per_sec / target_tps)"
  returns: float
  required_env: [python, aitune]
```

### Accuracy preservation track (usually required)

```yaml
TRACK: accuracy_preservation
required: true
verifier:
  type: external_tool
  command: "python scripts/validate_accuracy.py {artifact} --reference={baseline_model} --tolerance=0.01"
  parse_output: json_path
  path: ".accuracy_delta"
  returns: float
  normalise: "1.0 if abs(delta) < tolerance else max(0.0, 1.0 - abs(delta))"
  required_env: [python, aitune]
```

### Memory footprint track

```yaml
TRACK: gpu_memory
required: false
weight: 0.20
verifier:
  type: external_tool
  command: "python scripts/bench_inference.py {artifact} --metric=peak_memory_mb"
  parse_output: regex_capture
  pattern: "peak_mb: ([\\d.]+)"
  formula: "max(0.0, 1.0 - (peak_mb / budget_mb))"
  returns: float
  required_env: [python, aitune]
```

---

## Play design for inference missions

When plays are enabled, natural parameter bundles for inference optimisation:

```
PLAY: precision_sweep
parameters:
  - (precision, fp32, fp16, int8)
  - (backend, tensorrt, torch_inductor)
hypothesis: lower precision with TensorRT should give best latency
tracks_targeted: [inference_latency, throughput, accuracy_preservation]
atomic_fallback: true

PLAY: batch_tuning
parameters:
  - (batch_size, 1, 4, 8, 16, 32)
  - (sequence_length, 128, 512, 1024)
hypothesis: larger batches improve throughput but may hurt latency
tracks_targeted: [throughput, inference_latency, gpu_memory]
atomic_fallback: true
```

---

## Correctness validation

AITune includes built-in correctness checking — it validates that the optimised
model produces outputs within tolerance of the original. This is complementary
to a*'s track system:

- **AITune's check:** Fast, automatic, catches gross failures during compilation.
  Think of it as a hard constraint gate — if AITune's own validation fails,
  the step is rejected before a*'s verifiers even run.
- **a*'s accuracy track:** More thorough, runs on the user's actual evaluation
  data, enforces the user's tolerance threshold. This is the authoritative check.

During onboarding, set AITune's internal validation as a hard constraint:

```
HARD: AITune correctness validation must pass (aitune.validate() returns True)
```

Then use a*'s accuracy track for the scored, ratcheted evaluation.

---

## Handling AITune failures

AITune compilation can fail for reasons outside a\*'s control:

- **Unsupported operations:** Some model ops are not supported by all backends.
  TensorRT is the most restrictive; Torch Inductor the most permissive.
- **OOM during compilation:** TensorRT compilation can require significantly
  more GPU memory than inference. This is distinct from inference-time OOM.
- **Shape mismatches:** Static-shape backends may reject dynamic-shape models.

When AITune fails during a step:

1. Record the failure as `outcome: rejected_constraint` with the error details.
   Do not score the step — it produced no artifact.
2. The failure carries useful signal: if a backend consistently fails, exclude
   it from future plays in the round reflection. This is a legitimate pivot.
3. If *all* backends fail for the model, escalate to the user — the model may
   need architectural changes before inference optimisation is viable.
4. Do not retry the same configuration. Move to the next parameter set.

---

## Disposition patterns for inference optimisation

Common dispositions that emerge from inference optimisation runs:

- **TensorRT dominates for static-shape transformer inference** — but only when
  compilation time is acceptable. For rapid iteration, Torch Inductor compiles
  faster with good-enough speedup.
- **int8 quantization via TorchAO preserves accuracy better than expected** on
  most classification and generation tasks. Start with int8 + accuracy track
  rather than assuming fp16 is needed.
- **Batch size and sequence length interact non-linearly with memory** — small
  batch + long sequence can OOM where large batch + short sequence fits. The
  a* loop naturally discovers this through the ratchet mechanism.
- **JIT tuning finds 80% of the gains with 20% of the effort** — for initial
  exploration, start with `aitune.autotune()` before investing in AOT annotation.

These should be seeded into the disposition library when the problem class is
`inference_optimisation`. They will be refined by actual run evidence.
