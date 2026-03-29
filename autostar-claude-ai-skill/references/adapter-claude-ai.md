# Claude.ai adapter for the custom-skill package

This package assumes the checked-in base Claude.ai runtime profile stays
conservative. Session memory is enabled only through an effective-profile
overlay after probing a real memory surface.

## Memory access modes

1. `connector_backed`
   Preferred. Use the remote memory connector tools:
   - `lookup_priors`
   - `fetch_recent_episodes`
   - `append_episode`
   - `write_run_summary`
   - `list_pending_disposition_updates`
   - `apply_approved_updates`
   - `get_project_state`
   - `set_project_state`

2. `project_pack`
   Fallback when no connector is present but project knowledge contains the
   exported memory pack. Read from the pack, run the mission, emit updated pack
   files, and tell the user that manual sync back into project knowledge or
   GitHub is required.

3. `none`
   Final fallback. Run with short-term memory only and say so explicitly.

## Hard limits

- `external_tool` verifiers stay unavailable without subprocess access
- no automatic downgrade from `external_tool` to `llm_judge`
- Claude built-in memory is advisory only

