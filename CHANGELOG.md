# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-03-29

### Added

- Persistent memory backend (`memory_backend.py`) with full CRUD for episodes, dispositions, run summaries, and project state
- Memory connector (`memory_connector.py`) for bridging skill memory to external stores
- Memory CLI (`memory_cli.py`) for command-line memory pack operations
- Schema tools (`schema_tools.py`) for programmatic schema bundling
- Claude.ai-specific skill variant (`autostar-claude-ai-skill/`) with tailored adapter and runtime profile
- New JSON schemas: `disposition.schema.json`, `disposition-update.schema.json`, `episode.schema.json`, `hypothesis-stack.schema.json`, `memory-pack-manifest.schema.json`, `momentum.schema.json`, `project-state.schema.json`, `retrieved-dispositions.schema.json`, `run-summary.schema.json`, `track-trajectories.schema.json`
- Test suite: `test_memory_backend.py`, `test_packaging.py`, `test_runtime_profile.py`, `test_schema_bundle.py` with shared fixtures in `conftest.py`
- Runtime capabilities reference for Claude.ai adapter

### Changed

- Expanded `step-record.schema.json` with additional fields
- Updated `memory.md` reference with persistent backend documentation
- Updated `adapter-claude-ai.md` with Claude.ai-specific fallback guidance
- Revised packaging script to support Claude.ai skill variant
- Updated CI workflows (`release.yml`, `validate.yml`)
- Refreshed README

## [0.1.1] - 2026-03-26

### Added

- Runtime profiles for Codex, Gemini, and Pi adapters (`codex.json`, `gemini.json`, `pi.json`)
- Adapter references for Codex, Gemini, and Pi runtimes
- Onboarding reference document
- `mission.schema.json` for structured mission definitions
- Runtime capabilities reference

### Changed

- Improved README with clearer installation and usage instructions
- Refined SKILL.md with updated onboarding flow
- Tightened memory reference documentation

## [0.1.0] - 2026-03-26

### Added

- Initial release of a\* (autostar) skill package
- Core SKILL.md defining the structured optimisation loop
- Runtime profile system with profiles for Claude Code, Claude.ai, chat-only, and template
- Adapter references for Claude Code, Claude.ai, chat-only, and template runtimes
- Reference documents: budgeting, memory, onboarding, runtime capabilities, verification
- Inline progress chart HTML asset
- JSON schemas: `mission`, `progress`, `reflection`, `runtime-profile`, `step-record`, `tracks`
- Packaging script (`package_skill.py`) and quick validation script (`quick_validate.py`)
- Runtime profile loader (`runtime_profile.py`)
- GitHub Actions workflows for validation and release
- MIT license

[Unreleased]: https://github.com/chrisvoncsefalvay/autostar/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/chrisvoncsefalvay/autostar/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/chrisvoncsefalvay/autostar/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/chrisvoncsefalvay/autostar/releases/tag/v0.1.0
