---
name: autostar-claude-ai
description: >
  Claude.ai custom-skill package for a*. Uses memory in this order:
  connector-backed, project-pack, none. Never assumes subprocess access or
  unrestricted local files.
compatibility: Claude.ai custom Skills ZIP upload
---

# a* for Claude.ai

Use this package when a* is running inside Claude.ai custom Skills rather than
in a subprocess-capable coding host.

## Runtime truth

Claude.ai remains a reduced-support runtime:
- no subprocess verifiers
- no silent local-backend assumptions
- long-term memory only when a real surface is present

Memory order:
1. `connector_backed`
2. `project_pack`
3. `none`

If neither a connector nor a project pack is available, state plainly:

> "Long-term memory is unavailable in this session. a* is running with short-term memory only."

Do not replace missing tool verifiers with softer ones without explicit user approval.
Do not treat Claude's built-in memory as the source of truth for dispositions,
episodes, run summaries, or approvals.

## Read these references when needed

- `references/adapter-claude-ai.md`
- `references/runtime-capabilities.md`
- `references/memory.md`

