# Claude.ai memory notes

The canonical source of truth is the local SQLite backend used outside
Claude.ai. Claude.ai sees that memory through either:

- a connector-backed tool surface, or
- a text-first project memory pack

Within a run, append-only `step_log.jsonl` and `reflections.jsonl` remain the
source of truth. Derived snapshots such as `hypothesis_stack.json`,
`track_trajectories.json`, and `momentum.json` can be regenerated from those
logs when they disagree.

Project-pack mode is reduced fidelity and requires manual sync.

