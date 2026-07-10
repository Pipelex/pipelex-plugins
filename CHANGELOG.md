# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repo bootstrap: multi-target build tooling (`pyproject.toml`, `Makefile`), Apache-2.0 license, and project documentation, ported and adapted from the `mthds-plugins` scaffolding without any local-CLI lifecycle machinery.
- Multi-target build system: the `scripts/gen_skill_docs.py` Jinja2 renderer and `scripts/check.py` consistency checks, `targets/` (prod, codex, mistral-vibe, and a trimmed `defaults.toml`), the shared MTHDS language reference templates, and unit tests. `frontmatter.md.j2` is an include-only partial. None of the predecessor's install/upgrade/env-check switches are carried over.
- Marketplace and manifests: Claude `.claude-plugin/` (plugin base + marketplace), Codex `.codex-plugin/` plugin base and `packaging/codex-marketplace.json` with its generated `.agents/plugins/` discovery copy, and per-target `plugin.json` generation. Marketplace/version consistency is enforced by `make check`.
- First skill: `pipelex-explain` (ported and stripped from `mthds-explain`) — a pure read-and-explain skill that reads an `.mthds` bundle, identifies its components, traces the execution flow, and presents a plain-language explanation with a text flow diagram. No CLI dependency: the env-check step, the validate/graph steps, and the CLI-required framing are gone. Grounded on the shared MTHDS language references. Rendered across the Claude, Codex, and Mistral Vibe targets.
- `.mthds` validation hooks on all targets (Claude `PostToolUse`, Codex `PostToolUse` over `apply_patch`, Mistral Vibe `after_tool`): `plxt lint` → `plxt fmt` → `mthds-agent validate bundle` with the domain-based block/context decision model. CLI-free posture: when `node` / `plxt` / `mthds-agent` are absent the hook passes silently instead of blocking with an install hint (this plugin does not manage CLI installation). The Codex hook is bundled as `hooks/codex-hooks.json` (referenced from the manifest `hooks` field) with a wrapper that exits cleanly when `mthds-agent` is missing. The build renders the hook files per target and marks the shell scripts executable; `make check` enforces the Mistral Vibe hook artifacts.
- Build documentation: `docs/build-targets.md` describing the multi-target build, and `docs/hooks.md` describing the validation pipeline, the CLI-free silent-pass posture, per-platform wiring, and the Codex hook trust note (the `hooks` feature is Stable and on by default in Codex 0.141+, so there is nothing to enable — the bundled hook loads on its own and only needs first-run trust).

## [0.1.0] — Unreleased

Initial foundation of the Pipelex plugins.
