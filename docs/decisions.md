# pipelex-plugins — foundational decisions

This records the decisions that shaped the repo, for anyone joining later. The build-system architecture doc (`build-targets.md`) arrives with the build system itself.

## What this repo is

**Pipelex plugins** — skills and hooks for working with MTHDS methods — built with the same multi-target scaffolding as `mthds-plugins` (Jinja2 templates → per-platform outputs, served through a marketplace), but for the hosted-API / MCP generation. They ship **no local-CLI dependency and none of the install/upgrade/env-check machinery** that `mthds-plugins` carries.

`mthds-plugins` stays published and untouched. This is a new sibling repo, not a fork of it.

## Brand boundaries

The **plugins** are Pipelex's product surface: marketplace `pipelex-plugins`, plugin `pipelex`, outputs `pipelex/`, `pipelex-codex/`, `pipelex-vibe/`. The **language** stays MTHDS inside the docs — MTHDS is the standard; Pipelex is the tooling, product, and service. Skills are renamed `mthds-*` → `pipelex-*`; language-reference content keeps its MTHDS vocabulary.

## Targets

Per-platform targets: **Claude Code**, **Codex**, **Mistral Vibe**. The `dev` and `sandbox` targets from `mthds-plugins` are left behind — `dev` exists to test container-local CLI install paths (exactly what a CLI-free plugin doesn't need); `sandbox` can be added later if the app chatbot migrates.

## Hooks — CLI-free posture

The `.mthds` validation hooks ship on all targets. Their behavior differs from `mthds-plugins` in one way: when the MTHDS CLIs (`plxt` / `mthds-agent`) are **absent**, the hook **passes silently** instead of blocking with an install hint — this plugin does not manage CLI installation. When the CLIs happen to be present, the full validation pipeline runs unchanged. This is a deliberate transitional state; the iteration path swaps the CLI invocations for hosted-API / MCP calls, at which point the missing-CLI branch disappears.

## Codex hooks — verified against Codex 0.142.5 (2026-07-06)

The Codex hook engine matured across 0.139 → 0.142 (out of `Stage::UnderDevelopment`):

- The canonical feature key is now **`hooks`**, marked `Stage::Stable` and **enabled by default** (`plugin_hooks` / `codex_hooks` are deprecated aliases).
- Native per-source **trust model**: persisted `[hooks.state]` trusted hashes; `--dangerously-bypass-hook-trust` for automation.
- `PostToolUse` officially fires for **`apply_patch` edits and MCP tool calls**, not just Bash — which de-risks the whole `.mthds`-on-edit validation hook.
- Standardized block protocol: `{"decision":"block","reason":...}` (or exit 2 + stderr); Codex replaces the tool result with the feedback and continues. This maps cleanly onto the Stage 3 domain-based block/context decision model.

Consequence: the old "enable `[features] plugin_hooks` + sandbox network access" manual step is gone entirely — hooks are on by default, so the bundled hook loads on its own and the only step is trusting it on first run. (This plugin is CLI-free, so there was never a sandbox-network step to keep anyway.) We keep `mthds-agent codex hook` as the wrapper for now (it formats Codex's hook I/O and runs the same mthds-js validation); a plain CLI-free Codex shell hook waits until API/MCP-backed validation lands.

## Build system (Phases 1–2)

The build system (`docs/build-targets.md`) was ported from `mthds-plugins` and trimmed. A few deliberate choices for anyone joining mid-way:

- **`frontmatter.md.j2` is an include-only partial.** It is `{% include %}`-d by skill templates for their YAML frontmatter but is *not* in `SHARED_TEMPLATES`, so it is never rendered standalone. (The predecessor rendered it standalone; with `min_mthds_version` dropped it would only ship a near-empty artifact.)
- **Hooks are wired (Phase 4).** `HOOK_TEMPLATES_BY_PLATFORM` renders the `.mthds` validation hooks per target (Claude `hooks.json` + `validate-mthds.sh`; Codex `codex-hooks.json`; Vibe `vibe-hooks.toml` + `validate-mthds-vibe.sh`), and `.codex-plugin/plugin-base.json` carries the `hooks` field. See [hooks.md](hooks.md).
- **Dropped from the predecessor's checker:** the stale-install-reference check and the `min_mthds_version` frontmatter check (both CLI-coupled). The Vibe hook-artifact check landed with the hooks (Phase 4).

## License & distribution

**Apache 2.0**; repo made public when ready (required for easy marketplace install). Versions start at **0.1.0** (plugin and marketplace). GitHub home assumed `Pipelex/pipelex-plugins` — confirm at first push.
