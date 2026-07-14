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

- The canonical feature key is now **`hooks`**, marked `Stage::Stable` and **enabled by default** (`codex_hooks` is a deprecated alias). `plugin_hooks` is *not* an alias: it was an independent opt-in for plugin-bundled hooks that disabled them on Codex ≤ 0.133, removed in 0.134 and ignored since (semantics pinned down in mthds-js v0.18.0, which hard-errors on all three hook-disabling keys in its `apply-config`/`doctor` — machinery this CLI-free plugin deliberately doesn't carry).
- Native per-source **trust model**: persisted `[hooks.state]` trusted hashes; `--dangerously-bypass-hook-trust` for automation.
- `PostToolUse` officially fires for **`apply_patch` edits and MCP tool calls**, not just Bash — which de-risks the whole `.mthds`-on-edit validation hook.
- Standardized block protocol: `{"decision":"block","reason":...}` (or exit 2 + stderr); Codex replaces the tool result with the feedback and continues. This maps cleanly onto the Stage 3 domain-based block/context decision model.

Consequence: the old "enable `[features] plugin_hooks` + sandbox network access" manual step is gone entirely — hooks are on by default, so the bundled hook loads on its own and the only step is trusting it on first run. (This plugin is CLI-free, so there was never a sandbox-network step to keep anyway.) We keep `mthds-agent codex hook` as the wrapper for now (it formats Codex's hook I/O and runs the same mthds-js validation); a plain CLI-free Codex shell hook waits until API/MCP-backed validation lands.

## Build system (Phases 1–2)

The build system (`docs/build-targets.md`) was ported from `mthds-plugins` and trimmed. A few deliberate choices for anyone joining mid-way:

- **`frontmatter.md.j2` is an include-only partial.** It is `{% include %}`-d by skill templates for their YAML frontmatter but is *not* in `SHARED_TEMPLATES`, so it is never rendered standalone. (The predecessor rendered it standalone; with `min_mthds_version` dropped it would only ship a near-empty artifact.)
- **Hooks are wired (Phase 4).** `HOOK_TEMPLATES_BY_PLATFORM` renders the `.mthds` validation hooks per target (Claude `hooks.json` + `validate-mthds.sh`; Codex `codex-hooks.json`; Vibe `vibe-hooks.toml` + `validate-mthds-vibe.sh`), and `.codex-plugin/plugin-base.json` carries the `hooks` field. See [hooks.md](hooks.md).
- **Dropped from the predecessor's checker:** the stale-install-reference check and the `min_mthds_version` frontmatter check (both CLI-coupled). The Vibe hook-artifact check landed with the hooks (Phase 4).

## MCP server declaration (2026-07-14)

The plugin declares the **`pipelex-mcp`** server (streamable HTTP; tools `mthds_validate`, `mthds_inputs`) so the MCP-backed skills (`pipelex-design`, `pipelex-inputs`) can call it natively — no vendored script, no `curl` recipes.

- **Location: inline `mcpServers` in the generated Claude `plugin.json`** (not a plugin-root `.mcp.json` — both are supported by Claude Code; inline keeps everything in the one generated manifest). The build injects `{"pipelex": {"type": "http", "url": "${PIPELEX_MCP_URL:-<mcp_server_url>}"}}` for Claude-platform targets, sourced from the `mcp_server_url` template variable (`targets/defaults.toml`, overridable per target). Claude Code honors `${VAR:-default}` expansion inside plugin MCP configs and connects plugin-declared servers automatically at session start; the tools reach the model as `mcp__plugin_pipelex_pipelex__<tool>`.
- **The baked default is a placeholder** (`https://mcp.pipelex.com/mcp`) until `pipelex-mcp` has its deployed URL — always use the `PIPELEX_MCP_URL` override meanwhile (local dev: `http://localhost:3000/mcp` via `make dev` in `../pipelex-mcp`).
- **Codex / Vibe get no baked entry**: plugin-bundled MCP declarations are unverified on those platforms (same empirical-verification bar the Codex hooks got). Interim: one-time manual registration documented in the README (Codex: user-level `[mcp_servers]` in `config.toml`; Vibe: TBD).
- **Auth is server-side.** The MCP holds the upstream API key (`MTHDS_API_KEY` in its hosting env); `PIPELEX_API_KEY` is a hook-only concern and plays no role in the skills' validation path.

## MCP-unavailable posture for skills (2026-07-14)

Unlike the fail-open hook, the MCP-backed skills **require** their tools to do their job. When the tool is absent from the session (harness didn't connect the plugin MCP server) or a call returns `status: "error"` with class `config` (server unreachable / upstream misconfigured / auth), the skill **stops with a one-line setup instruction** (check the MCP connection via `/mcp`, or point `PIPELEX_MCP_URL` at a running server; surface the error's `hint`). Never silently skip validation. Related skill-level adaptations are recorded in `TODOS.md` (D3–D6): honest graph surfacing (`available_view_specs`, no `dry_run.html`), no ported CLI-era shared references, the runnable gate replacing strict validation (the MCP always validates leniently), and the whole-bundle `files[]` submission convention.

## License & distribution

**Apache 2.0**; repo made public when ready (required for easy marketplace install). Versions start at **0.1.0** (plugin and marketplace). GitHub home assumed `Pipelex/pipelex-plugins` — confirm at first push.
