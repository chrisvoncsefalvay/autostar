# Runtime capability contract

This file defines the portability layer for a*. The skill is authored against
**abstract runtime capabilities**, not against Claude-specific tool names.
Claude Code / Claude.ai are reference adapters, not the specification.

If you are implementing a* in another agent framework, start here.

Concrete examples and scaffolds:
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

---

## Goals

The adapter layer exists to preserve four invariants across runtimes:

1. User approval checkpoints cannot be skipped.
2. Verifier configuration cannot silently drift during a run.
3. Human gates must actually pause optimisation.
4. Unsupported features must degrade explicitly, not fail half-hidden.

---

## Capability model

Each runtime should expose a capability profile with the following keys:

```yaml
runtime:
  name: <string>
  version: <string|null>
capabilities:
  structured_choice: full | basic | none
  freeform_input: true | false
  file_presentation: inline | external | none
  local_html: inline | external | none
  subprocess: true | false
  pause_resume: true | false
  file_read_write: full | limited | none
  long_term_memory: true | false
```

At run start, detect this profile and adapt the workflow before onboarding.
Keep the checked-in base profile conservative. If the current session can probe
an actual memory surface, emit an effective profile alongside the base profile
instead of pretending the base profile changed.

---

## Capability definitions

### 1. `structured_choice`

Used for bounded decisions: track confirmation, verifier selection, budget,
plays, and final go/no-go approval.

Contract:
- Present 2+ explicit options.
- Allow the user to choose one or more where appropriate.
- Return the selected value(s) in a machine-readable form.
- Never auto-select without an explicit user confirmation event.

Native examples:
- Claude Code: `ask_user`
- Chat UIs without forms: numbered options in markdown + explicit user reply

Fallback:
- If only `basic`, present numbered choices in plain text.
- If `none`, a* is not portable without adding an approval wrapper.

### 2. `freeform_input`

Used for open-ended goal descriptions, constraints, rubric wording, and
reflection prompts that do not fit bounded choices.

Contract:
- Preserve the user's raw text.
- Do not coerce freeform input into a prefilled structure unless the user
  confirms the transformation.

Fallback:
- If absent, the runtime is not suitable for onboarding.

### 3. `file_presentation`

Used to surface `tracks.md`, generated reports, `visualiser.html`, and any
artifact the user must review.

Contract:
- Present a file or file-derived content to the user.
- Make the exact reviewed artifact identifiable by path or stable name.

Modes:
- `inline`: the host can render or attach the file directly
- `external`: the host can only point the user to a file path or download
- `none`: no reliable way to present artifacts

Fallback:
- If `external`, tell the user exactly which file to open and why.
- If `none`, replace file presentation with pasted summaries only for
  non-binding status updates; do not use this mode for human gates.

Preference rule:
- If `inline`, prefer presenting review artifacts and rendered visualisers inline
  rather than redirecting the user to an external browser or file path.

### 4. `local_html`

Used for the live visualiser when the runtime can render local HTML.

Contract:
- Surface a local HTML artifact either inline or by opening it externally.
- Preserve the generated output file so the user and agent refer to the same
  artifact.

Modes:
- `inline`: embedded browser/file rendering
- `external`: open in system browser or provide a path to open manually
- `none`: runtime cannot surface local HTML

Fallback:
- Visualiser: fall back to text summaries plus `progress.json`.

### 5. `subprocess`

Used for external-tool verifiers, tool availability checks, and rendering the
visualiser HTML.

Contract:
- Run a command with cwd, timeout, and captured stdout/stderr.
- Return exit code and output.
- Allow preflight checks such as `tool --version`.

Fallback:
- If absent, external-tool tracks must be rejected or replaced during
  onboarding. Mark the replacement as lower-confidence in the run report.
- The visualiser must be replaced by text progress plus `progress.json`.
- Never silently convert an `external_tool` verifier into an `llm_judge`.

### 6. `pause_resume`

Used for human gates and round-level escalations where optimisation must stop
until the user responds.

Contract:
- Suspend autonomous mutation after a checkpoint is emitted.
- Resume only after a user message is received and bound to that checkpoint.

Fallback:
- If absent, the runtime must run synchronously and block on the next user
  turn. If even that is impossible, human-gate tracks are unsupported.

### 7. `file_read_write`

Used for run artifacts: `mission.md`, `tracks.md`, `constraints.md`,
`plays.md`, `step_log.jsonl`, `reflections.jsonl`, `progress.json`.

Contract:
- Read and write stable files in a run directory.
- Preserve append-only logs unless the schema explicitly says overwrite.

Fallback:
- If `limited`, a* can run in reduced mode but may lose append-only logs or
  stable run directories.
- If `none`, a* can only run in ephemeral mode and loses auditability. This is
  acceptable for demos, not for the full skill.

### 8. `long_term_memory`

Used for episodic memory and dispositions across runs.

Contract:
- Store and retrieve prior reflections and disposition records keyed by problem
  class and action intent.
- Only advertise long-term memory when a real surface exists for this session.

Memory access modes:
- `direct_backend` — runtime can reach the canonical local backend directly
- `connector_backed` — runtime uses a connector tool surface
- `project_pack` — runtime reads and writes a text-first project pack with manual sync
- `none` — no long-term memory surface is available

Fallback:
- If absent, run with short-term memory only and report that cross-run learning
  is disabled.
- Do not treat host-native memory synthesis as the system of record for
  dispositions, episodes, approvals, or run summaries.

---

## Support levels

Use these support levels when adapting a* to a host runtime:

### Full support

Required:
- `structured_choice`: `full` or `basic`
- `freeform_input`: true
- `file_presentation`: `inline` or `external`
- `subprocess`: true
- `pause_resume`: true or synchronous block equivalent
- `file_read_write`: `full`

Optional but recommended:
- `local_html`
- `long_term_memory`

### Reduced support

Allowed with explicit downgrade messaging:
- No `local_html`
- No `long_term_memory`
- `structured_choice: basic`
- `file_presentation: external`
- `file_read_write: limited`

### Unsupported

Do not claim portability if any of these are true:
- `freeform_input: false`
- `structured_choice: none`
- `file_read_write: none`
- `pause_resume: false` and no synchronous blocking alternative

---

## Required runtime shims

An adapter should expose these abstract operations:

```text
choose(prompt, options, allow_multiple=false) -> selection
ask(prompt) -> text
present(path, purpose, mode=inline|external) -> acknowledgement
run(command, cwd=null, timeout_s=30) -> {exit_code, stdout, stderr}
pause(checkpoint_id, prompt, artifacts=[]) -> user_response
read(path) -> bytes|text
write(path, content)
append(path, content)
memory_lookup(query) -> records[]
memory_store(record)
```

The exact API shape is host-specific. The behavior is not.

---

## Mapping examples

### Claude Code

```yaml
structured_choice: full
freeform_input: true
file_presentation: external
local_html: external
subprocess: true
pause_resume: true
file_read_write: full
long_term_memory: false
```

Typical mapping:
- `choose` -> `ask_user`
- `present` -> file path + browser open
- `run` -> shell tool

### Claude.ai / Claude Desktop / Claude Mobile

```yaml
structured_choice: basic
freeform_input: true
file_presentation: inline
local_html: inline
subprocess: false
pause_resume: true
file_read_write: limited
long_term_memory: false
```

Typical mapping:
- `choose` -> structured chat prompt
- `present` -> `present_files`
- `run` -> unsupported

Implication:
- External-tool tracks must be replaced or disabled.
- If `visualiser.html` already exists, present it inline rather than linking out.

### Chat-only agent with no file or command tools

```yaml
structured_choice: basic
freeform_input: true
file_presentation: none
local_html: none
subprocess: false
pause_resume: true
file_read_write: false
long_term_memory: false
```

Implication:
- Not a valid full a* host.
- Can only run a narrowed "prompt optimisation only" mode if the implementation
  explicitly removes file-backed auditing and tool-based verifiers.

Concrete profile:
- `runtime-profiles/chat-only.json`
- `references/adapter-chat-only.md`

---

## Fallback policy

When a capability is missing, degrade in this order:

1. Replace the host-specific tool with an abstract equivalent.
2. Replace the feature with a lower-fidelity but still explicit workflow.
3. Reconfigure the mission during onboarding.
4. If the invariant would be violated, stop and tell the user the runtime is
   unsupported for that track or for the whole run.

Never silently:
- turn an external-tool verifier into an LLM judge
- skip a human gate
- skip final mission approval
- pretend a file was presented when only a summary was shown

---

## Implementation guidance

When porting a* to another tool:

1. Detect capabilities before Phase 1.
2. Announce the active runtime profile to the user.
3. Apply downgrades before proposing tracks.
4. Record all downgraded features in `mission.md` and the final report.
5. Prefer portable artifacts:
   - `tracks.md` for rubric confirmation
   - `progress.json` for status
   - text-based trajectory summaries when HTML is unavailable

---

## Current portability boundary

Today, the bundled skill is **native-first for Claude environments**.
This contract exists so those assumptions can be moved behind adapters over
time instead of being hard-coded into the workflow forever.
