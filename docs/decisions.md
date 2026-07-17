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

## Codex hooks — verified against Codex 0.142.5 (2026-07-06), re-verified in-session on 0.144.4 (2026-07-14)

The Codex hook engine matured across 0.139 → 0.142 (out of `Stage::UnderDevelopment`):

- The canonical feature key is now **`hooks`**, marked `Stage::Stable` and **enabled by default** (`codex_hooks` is a deprecated alias — still honored on 0.144.4, confirmed from the source's legacy-feature map after binary strings suggested it might be gone). `plugin_hooks` is *not* an alias: it was an independent opt-in for plugin-bundled hooks that disabled them on Codex ≤ 0.133, removed in 0.134, ignored since, and formally `Stage::Removed` in 0.144 (semantics pinned down in mthds-js v0.18.0, which hard-errors on all three hook-disabling keys in its `apply-config`/`doctor` — machinery this CLI-free plugin deliberately doesn't carry).
- Native per-source **trust model**: persisted `[hooks.state]` trusted hashes; `--dangerously-bypass-hook-trust` for automation. Trust keys are per plugin hook config (`pipelex@pipelex-plugins:hooks/codex-hooks.json:post_tool_use:0:0`) and survive plugin re-installs as long as the hook config's hash is unchanged.
- `PostToolUse` officially fires for **`apply_patch` edits and MCP tool calls**, not just Bash — which de-risks the whole `.mthds`-on-edit validation hook.
- Standardized block protocol: `{"decision":"block","reason":...}` (or exit 2 + stderr); Codex replaces the tool result with the feedback and continues. This maps cleanly onto the Stage 3 domain-based block/context decision model.
- Hook commands get `${PLUGIN_ROOT}` / `${CLAUDE_PLUGIN_ROOT}` substituted with the installed plugin root; 0.144 adds `${PLUGIN_DATA}` / `${CLAUDE_PLUGIN_DATA}` (a per-plugin data dir under `$CODEX_HOME/plugins/data/`). Substitution is a plain string replace — no `${VAR:-default}` form.

Consequence: the old "enable `[features] plugin_hooks` + sandbox network access" manual step is gone entirely — hooks are on by default, so the bundled hook loads on its own and the only step is trusting it on first run. (This plugin is CLI-free, so there was never a sandbox-network step to keep anyway.)

**In-session verification (Codex 0.144.4, 2026-07-14):** the shipped wasm+API hook was exercised in live headless Codex sessions (`codex exec --dangerously-bypass-hook-trust`): an `apply_patch` writing a broken `.mthds` was **blocked** and the hook's lint diagnostics (line/col spans) reached the model verbatim as the replaced tool result; a valid-but-non-canonical `.mthds` write **passed** and was canonically formatted in place; non-`.mthds` patches stayed silent. On a dev machine with the CLI-era `mthds@mthds-plugins` plugin also installed, both hooks fire on the same edit and Codex concatenates the block reasons — expected coexistence, not a bug; disable one side per-invocation with `-c 'plugins."mthds@mthds-plugins".enabled=false'` when isolating.

## Codex plugin lifecycle — cache model on 0.144.x (2026-07-14)

Installed plugins run from a **cache copy** (`$CODEX_HOME/plugins/cache/<marketplace>/<plugin>/<version>/`) taken at `codex plugin add` time — `codex plugin list`'s PATH column shows the marketplace *source*, not the runtime copy, which is misleading when dogfooding a local checkout. `codex plugin marketplace upgrade` now refreshes **Git marketplace snapshots only** and errors on a local-path marketplace; the way to propagate local edits is an idempotent re-`add` (`codex plugin add pipelex@pipelex-plugins`), which re-copies the cache. `make codex-refresh` and both `make codex-use-*` targets do exactly that.

## Build system (Phases 1–2)

The build system (`docs/build-targets.md`) was ported from `mthds-plugins` and trimmed. A few deliberate choices for anyone joining mid-way:

- **`frontmatter.md.j2` is an include-only partial.** It is `{% include %}`-d by skill templates for their YAML frontmatter but is *not* in `SHARED_TEMPLATES`, so it is never rendered standalone. (The predecessor rendered it standalone; with `min_mthds_version` dropped it would only ship a near-empty artifact.)
- **Hooks are wired (Phase 4).** `HOOK_TEMPLATES_BY_PLATFORM` renders the `.mthds` validation hooks per target (Claude `hooks.json` + `check-mthds.sh`; Codex `codex-hooks.json`; Vibe `vibe-hooks.toml` + `check-mthds-vibe.sh`), and `.codex-plugin/plugin-base.json` carries the `hooks` field. See [hooks.md](hooks.md).
- **Dropped from the predecessor's checker:** the stale-install-reference check and the `min_mthds_version` frontmatter check (both CLI-coupled). The Vibe hook-artifact check landed with the hooks (Phase 4).

## MCP server declaration (2026-07-14)

The plugin declares the **`pipelex-mcp`** server (streamable HTTP; tools `mthds_validate`, `mthds_inputs_template`, and the `mthds_run` family) so the MCP-backed skills (`pipelex-design`, `pipelex-organize`, `pipelex-edit`, `pipelex-inputs`) can call it natively — no vendored script, no `curl` recipes.

- **Location: inline `mcpServers` in the generated Claude `plugin.json`** (not a plugin-root `.mcp.json` — both are supported by Claude Code; inline keeps everything in the one generated manifest). The build injects `{"pipelex": {"type": "http", "url": "<mcp_server_url>"}}` for Claude-platform targets, sourced from the `mcp_server_url` template variable (`targets/defaults.toml`, overridable per target). Claude Code connects plugin-declared servers automatically at session start; the tools reach the model as `mcp__plugin_pipelex_pipelex__<tool>`.
- **The URL is literal — no `${PIPELEX_MCP_URL:-<url>}` wrapper (amended 2026-07-16).** The original design wrapped the URL so a session-start env var switched dev/prod without a rebuild, and the Claude Code CLI does expand `${VAR:-default}` in plugin MCP config (verified in the Phase 3 live sessions). But the **Claude desktop app performs no such expansion** (open upstream bugs — the server receives the wrapper string verbatim and the connection breaks), and desktop sessions can't set env vars anyway, so the wrapper could never help there and actively broke the primary install target. Dev override on Claude is now the local-marketplace dogfood loop: edit `mcp_server_url` in `targets/defaults.toml` + `make build` (local dev server: `http://localhost:3000/mcp` via `make dev` in `../pipelex-mcp`).
- **The baked default is currently the `pipelex-mcp` Alpic dev tunnel** — an interim so marketplace installs reach a live server; switch it to the stable URL when `pipelex-mcp` deploys.
- **Codex gets a baked entry too** since the 0.144.4 verification (see the dedicated section below); its manifest carries the literal URL because Codex does no env expansion in MCP config. **Vibe still gets no entry**: plugin-bundled MCP declarations remain unverified there (same empirical-verification bar). Interim for Vibe: manual registration, TBD in the README.
- **Auth is server-side.** The MCP holds the upstream API key (`MTHDS_API_KEY` in its hosting env); `PIPELEX_API_KEY` is a hook-only concern and plays no role in the skills' validation path.

## Codex plugin-bundled MCP declaration — verified against Codex 0.144.4 (2026-07-14)

Codex 0.144.x loads MCP servers from installed plugins; verified both from the `rust-v0.144.4` source and hands-on with the installed plugin (server listed by `codex mcp list`, and a live session round-tripped `mthds_validate` against a running `pipelex-mcp`). The wiring decision:

- **Shape: inline camelCase `mcpServers` object in `.codex-plugin/plugin.json`** — same one-manifest posture as Claude (D1). Codex accepts either this inline object or a plugin-root `.mcp.json` file referenced as `"mcpServers": "./.mcp.json"` (both verified working); inline avoids a second generated artifact. The build injects `{"pipelex": {"url": "<mcp_server_url>"}}` for Codex-platform targets. No `type` field: Codex picks the streamable-HTTP transport structurally from the bare `url` (a `type` key is Claude-compat-tolerated but stripped).
- **The URL is literal — Codex performs no `${VAR}` / `${VAR:-default}` expansion anywhere in MCP config** (its only `${…}` substitution is hook-command-only). The dev/prod switch instead relies on precedence: a same-named user entry (`[mcp_servers.pipelex]` in `~/.codex/config.toml`, or `-c 'mcp_servers.pipelex.url="http://localhost:3000/mcp"'` per invocation) **outranks the plugin declaration** (config tier beats plugin tier in Codex's MCP catalog; verified empirically). The baked URL carries the same interim-dev-tunnel caveat as Claude's until `pipelex-mcp` deploys.
- **Tool naming:** Codex exposes plugin MCP tools as `mcp__<server>__<tool>` — `mcp__pipelex__mthds_validate` / `mcp__pipelex__mthds_inputs_template` (no plugin-name nesting, unlike Claude Code). The skills' generic "the `mthds_validate` tool" phrasing works unchanged; the Claude-only `allowed-tools` frontmatter doesn't apply to Codex.
- **No trust gate:** unlike hooks, plugin MCP servers have no trusted-hash/approval step — the server connects when the plugin is installed and enabled (per-server `enabled` defaults to true). `codex mcp list` shows plugin-declared servers, which makes registration verifiable without a session.
- If auth lands on the hosted MCP later, Codex's server config supports `bearer_token_env_var` and `http_headers`/`env_http_headers` (a raw `bearer_token` is rejected for HTTP transports) — env indirection exists for auth even though URL templating doesn't.

## MCP-unavailable posture for skills (2026-07-14)

Unlike the fail-open hook, the MCP-backed skills **require** their tools to do their job. When the tool is absent from the session (harness didn't connect the plugin MCP server) or a call returns `status: "error"` with class `config` (server unreachable / upstream misconfigured / auth), the skill **stops with a one-line setup instruction** (check the MCP connection via `/mcp`; the plugin manifest must point at a running server; surface the error's `hint`). Never silently skip validation. Related skill-level adaptations are recorded in `TODOS.md` (D3–D6): honest graph surfacing (`available_view_specs`, no `dry_run.html`), no ported CLI-era shared references, the runnable gate replacing strict validation (the MCP always validates leniently), and the whole-bundle `files[]` submission convention.

One refinement (2026-07-16): the stop-posture applies to a skill's **required** tools only. Tools that power a convenience are soft dependencies — `pipelex-inputs`' closing offer-to-run needs the `mthds_run` family, and when those tools are absent the skill finishes without the offer instead of stopping. A skill must state which of its tools are which.

## Edit vs design — who owns method modification (2026-07-16)

The CLI-era plugin had `mthds-edit` next to `mthds-build`. The port splits that ground along the **contract line** instead of recreating a monolithic edit skill:

- **`pipelex-edit`** is the modification entry point and the model-invocable half — it owns the natural-language triggers ("change this pipe", "rename this concept"). It handles contract-preserving edits itself (prompts, descriptions, model refs, operator settings, mechanical renames) under a baseline-verdict discipline: whole-bundle `mthds_validate` before and after, never edit on a broken baseline, inputs-refresh check when a rename touches the client-facing template.
- **`pipelex-design`** owns structural and contract changes via its "Editing an existing method" re-entry section (reopen the affected pipes to same-contract signatures, re-refine with the standard loop, re-organize at the end). It stays `disable-model-invocation: true` — a design run is a commitment the user opts into explicitly — so `pipelex-edit` routes by *telling the user* to run `/pipelex-design`, never by invoking it.
- **Why the split:** the routing surface and the methodology have different homes. Edit intent must auto-trigger from natural phrases, which design deliberately cannot (explicit-invoke only); the propagating-change discipline (contract identity, concept shapes, backlog draining) must live in exactly one skill or it drifts. The hook is not a substitute for either: its semantic-validation stage is fail-open (skipped without `PIPELEX_API_KEY`), so `pipelex-edit` always takes the whole-bundle MCP verdict as the authoritative check.

## MCP tool vs skill naming convention (2026-07-16)

Settled with `../pipelex-mcp` before anything ships, while every name is still free to change. The principle: **tools are the contract, skills are the manual** — their names follow their consumers.

- **Tools** (owned by `pipelex-mcp`): `mthds_<stem>`, snake_case — operations on MTHDS-language artifacts. Tool names and descriptions are self-sufficient and never reference the plugin skills, because many consumers (ChatGPT, claude.ai connectors, raw MCP hosts) never see them. Lifecycle families share a stem prefix (`mthds_run`, `mthds_run_status`, `mthds_run_results`) so they sort adjacently in tool lists. A noun-only name must state the artifact it returns — hence the rename `mthds_inputs` → **`mthds_inputs_template`** (2026-07-16, before any deploy). The server key stays `pipelex` (the product brand; the `mthds_` prefix on tools avoids a `pipelex` stutter in flattened names and keeps bare tool names collision-proof across servers). The server-side record is `../pipelex-mcp/SPEC.md` → "Naming Conventions".
- **Skills** (this repo): `pipelex-<stem>`, kebab-case — named after user tasks (product surface, per the brand-boundaries decision above), never 1:1 wrappers of tools. Several skills may use one tool (`pipelex-design` and `pipelex-organize` both call `mthds_validate`); a naming rule that forced skill↔tool symmetry would push toward the wrong granularity.
- **The shared stem is the join key** where a skill is the manual for one tool: `pipelex-inputs` ↔ `mthds_inputs_template`. Skills reference tool names verbatim (frontmatter `allowed-tools`, prose); the dependency is strictly one-way — skills know tools, tools never know skills.

## License & distribution

**Apache 2.0**; repo made public when ready (required for easy marketplace install). Versions start at **0.1.0** (plugin and marketplace). GitHub home assumed `Pipelex/pipelex-plugins` — confirm at first push.
