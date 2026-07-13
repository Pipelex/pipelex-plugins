# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repo bootstrap: multi-target build tooling (`pyproject.toml`, `Makefile`), Apache-2.0 license, and project documentation, ported and adapted from the `mthds-plugins` scaffolding without any local-CLI lifecycle machinery.
- Multi-target build system: the `scripts/gen_skill_docs.py` Jinja2 renderer and `scripts/check.py` consistency checks, `targets/` (prod, codex, mistral-vibe, and a trimmed `defaults.toml`), the shared MTHDS language reference templates, and unit tests. `frontmatter.md.j2` is an include-only partial. None of the predecessor's install/upgrade/env-check switches are carried over.
- Marketplace and manifests: Claude `.claude-plugin/` (plugin base + marketplace), Codex `.codex-plugin/` plugin base and `packaging/codex-marketplace.json` with its generated `.agents/plugins/` discovery copy, and per-target `plugin.json` generation. Marketplace/version consistency is enforced by `make check`.
- First skill: `pipelex-explain` (ported and stripped from `mthds-explain`) — a pure read-and-explain skill that reads an `.mthds` bundle, identifies its components, traces the execution flow, and presents a plain-language explanation with a text flow diagram. No CLI dependency: the env-check step, the validate/graph steps, and the CLI-required framing are gone. Grounded on the shared MTHDS language references. Rendered across the Claude, Codex, and Mistral Vibe targets.
- `.mthds` validation hooks on all targets (Claude `PostToolUse`, Codex `PostToolUse` over `apply_patch`, Mistral Vibe `after_tool`). On Codex and Mistral Vibe the transitional CLI pipeline runs when the CLIs are present (`plxt lint` → `plxt fmt` → `mthds-agent validate bundle` with the domain-based block/context decision model) and passes silently when `node` / `plxt` / `mthds-agent` are absent (this plugin does not manage CLI installation). The Codex hook is bundled as `hooks/codex-hooks.json` (referenced from the manifest `hooks` field) with a wrapper that exits cleanly when `mthds-agent` is missing. The build renders the hook files per target and marks the shell scripts executable; `make check` enforces the Mistral Vibe hook artifacts.
- **Claude target: CLI-free wasm+API validation hook.** `validate-mthds.sh` is now a thin fail-open wrapper that runs the vendored `hooks/check.mjs` bundle (built in `pipelex-sdk-js`, provenance header included): lint and format run **locally** via the `@pipelex/tools-wasm` engine inlined in the bundle (offline, no credentials; format writes back in place), and the full bundle verdict comes from `POST /v1/validate` through `@pipelex/sdk` (`allow_signatures: true`, `.mthds` files gathered recursively under the edited file's parent dir with caps, server-rendered Markdown forwarded verbatim as the block reason, non-blocking `pending_signatures` nudge). Fail-open: no Node → the whole hook passes silently; no `PIPELEX_API_KEY` / API unreachable / timeout / any non-2xx → the local lint/format verdicts still apply and only the validate stage is skipped. Hook timeout lowered from 30 s to 15 s (the one network call has its own 10 s ceiling). The bundle ships as a static hook asset (`templates/hooks/assets/check.mjs`, copied verbatim by the build via `STATIC_HOOK_ASSETS_BY_PLATFORM`); `make vendor-hook` re-vendors it from the sibling checkouts and `make check` fails on a missing or stale copy.
- Build documentation: `docs/build-targets.md` describing the multi-target build, and `docs/hooks.md` describing the validation pipeline, the CLI-free silent-pass posture, per-platform wiring, and the Codex hook trust note (the `hooks` feature is Stable and on by default in Codex 0.141+, so there is nothing to enable — the bundled hook loads on its own and only needs first-run trust).

## [0.1.0] — Unreleased

Initial foundation of the Pipelex plugins.
