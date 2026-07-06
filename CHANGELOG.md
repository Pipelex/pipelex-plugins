# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repo bootstrap: multi-target build tooling (`pyproject.toml`, `Makefile`), Apache-2.0 license, and project documentation, ported and adapted from the `mthds-plugins` scaffolding without any local-CLI lifecycle machinery.
- Multi-target build system: the `scripts/gen_skill_docs.py` Jinja2 renderer and `scripts/check.py` consistency checks, `targets/` (prod, codex, mistral-vibe, and a trimmed `defaults.toml`), the shared MTHDS language reference templates, and unit tests. `frontmatter.md.j2` is an include-only partial. None of the predecessor's install/upgrade/env-check switches are carried over.
- Marketplace and manifests: Claude `.claude-plugin/` (plugin base + marketplace), Codex `.codex-plugin/` plugin base and `packaging/codex-marketplace.json` with its generated `.agents/plugins/` discovery copy, and per-target `plugin.json` generation. Marketplace/version consistency is enforced by `make check`.
- Build documentation: `docs/build-targets.md` describing the multi-target build.

## [0.1.0] — Unreleased

Initial foundation of the Pipelex plugins.
