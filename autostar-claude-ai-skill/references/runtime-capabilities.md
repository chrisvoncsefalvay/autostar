# Claude.ai capability summary

Base Claude.ai profile:
- `structured_choice: basic`
- `freeform_input: true`
- `file_presentation: inline`
- `local_html: inline`
- `subprocess: false`
- `pause_resume: true`
- `file_read_write: limited`
- `long_term_memory: false`

Effective memory is overlaid only after probing one of:
- direct backend
- connector-backed memory
- project-pack memory
- none

For Claude.ai, expect `connector_backed`, `project_pack`, or `none`.

