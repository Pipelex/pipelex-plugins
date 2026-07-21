# CLAUDE.md — pipelex-plugins

Pipelex plugins — **skills and hooks for working with MTHDS methods** (`.mthds` bundles) — packaged for Claude Code, Codex, and Mistral Vibe and served through the Pipelex plugins marketplace.

This is the hosted-API / MCP-era plugin generation. Unlike its predecessor `mthds-plugins`, it carries **no local-CLI dependency and none of the install/upgrade/env-check machinery**. Install is just a marketplace add.

> **Status:** foundation in progress. The phase-by-phase plan and cold-start context live in the workspace-root tracker `../wip/devx/pipelex-plugins-foundations.md` (in the `Pipelex` repo). Foundational decisions are recorded in `docs/decisions.md`. Parts of the structure below are produced by later build phases.

## Brand boundaries

The **plugins** are Pipelex's product surface: marketplace `pipelex-plugins`, plugin `pipelex`, outputs `pipelex/` (Claude), `pipelex-codex/`, `pipelex-vibe/`. The **language** stays MTHDS inside the docs — MTHDS is the standard; Pipelex is the tooling, product, and service. Skills are `pipelex-*`; language-reference content keeps its MTHDS vocabulary.

## Repository Structure

```
.claude-plugin/
├── plugin-base.json           # Shared plugin fields (author, repo, license)
└── marketplace.json           # Marketplace listing (marketplace: pipelex-plugins)
.codex-plugin/
└── plugin-base.json           # Shared Codex plugin manifest fields
.agents/plugins/
└── marketplace.json           # Codex-discoverable copy of packaging/codex-marketplace.json (generated)
packaging/
└── codex-marketplace.json     # Canonical Codex marketplace packaging spec
targets/
├── defaults.toml              # Shared template variable defaults (trimmed set)
├── prod.toml                  # Claude prod target config (version, identity)
├── codex.toml                 # Codex target config (version, identity)
└── mistral-vibe.toml          # Mistral Vibe target config (version, identity)
templates/                     # SOURCE OF TRUTH — all .j2 templates live here
├── skills/
│   ├── pipelex-explain/SKILL.md.j2   # Read-and-explain a bundle (no MCP dependency)
│   ├── pipelex-design/SKILL.md.j2    # Top-down design by stepwise refinement (MCP-backed)
│   ├── pipelex-organize/SKILL.md.j2  # Regroup a designed bundle into a browsable module layout (MCP-backed; auto-run at end of pipelex-design)
│   ├── pipelex-edit/SKILL.md.j2      # Contract-preserving edits to an existing bundle; routes structural changes to pipelex-design (MCP-backed)
│   ├── pipelex-inputs/SKILL.md.j2    # inputs.json preparation (MCP-backed)
│   └── shared/
│       ├── frontmatter.md.j2          # Common YAML frontmatter (included by templates)
│       ├── mthds-reference.md.j2      # MTHDS language reference (rendered per target)
│       └── native-content-types.md.j2 # Native content-type documentation
└── hooks/
    ├── hooks.json.j2                # Claude PostToolUse hook config
    ├── codex-hooks.json.j2          # Codex PostToolUse hook config (plugin-bundled)
    ├── vibe-hooks.toml.j2           # Mistral Vibe post_tool hook config
    ├── check-mthds.sh.j2            # Claude wrapper (fail-open guard → check.mjs)
    ├── check-mthds-codex.sh.j2      # Codex wrapper (apply_patch envelope → check.mjs)
    ├── check-mthds-vibe.sh.j2       # Vibe wrapper (post_tool payload → check.mjs)
    └── assets/check.mjs             # Vendored wasm+API validation bundle (static asset, built in pipelex-sdk-js)
pipelex/                       # Claude prod plugin (generated, checked in)
pipelex-codex/                 # Codex plugin (generated, checked in)
pipelex-vibe/                  # Mistral Vibe target (generated, checked in; loaded via skill_paths)
scripts/
├── gen_skill_docs.py          # Template renderer (multi-target)
└── check.py                   # Validation / freshness / packaging checks
tests/unit/                    # Unit tests for renderer + checks
docs/                          # build-targets.md + decisions.md
Makefile  pyproject.toml  uv.lock  README.md  CHANGELOG.md  LICENSE
```

## Build System

Multi-target build. Templates in `templates/` are rendered with variables from TOML config in `targets/`; each target produces a separate plugin output. Generated outputs are checked in. See `docs/build-targets.md` for full architecture.

### Key commands

```bash
make build           # Build all targets (prod + codex + mistral-vibe)
make check-shared    # Shared checks + template freshness + lint/type checks
make check-claude    # Claude marketplace consistency checks
make check-codex     # Codex packaging consistency checks
make check           # Run all of the above
make agent-check     # Full quality gate for agents (fix imports + format + lint + check)
make test            # Run unit tests
make agent-test      # Run unit tests quietly (output only on failure) — prefer this
make gen-skill-docs  # Build default target (prod); use TARGET=codex for others
```

### Editing workflow

1. Edit `.j2` files in `templates/` (never edit generated `pipelex*/` outputs directly — they're regenerated).
2. Run `make build` to regenerate all targets.
3. Run `make check` (or `make agent-check`) to validate.

### Template variables (trimmed set)

Variables are defined in `targets/defaults.toml`, overridable per-target in `targets/<name>.toml`. The CLI-free posture keeps this set small:

- `marketplace_name` — `pipelex-plugins`
- `platform` — Claude / Codex / Vibe
- `harness_name` — display name of the harness
- `mcp_server` — a table (`[vars.mcp_server]`: `command`, `args`, `env_vars`) describing the local workshop launcher the manifests bake; `env_vars` lists the variable *names* Codex forwards into the spawn (Claude passes the full shell env on its own)

Deliberately **not** carried over from `mthds-plugins`: `min_mthds_version`, `env_check`, `can_run_methods`, `session_start_hook`, and all `*_install_cmd` / `*_upgrade_cmd` variables. Reintroduce a variable only when a skill or hook actually branches on it. Don't port dead switches.

### Version management

- **Plugin version**: source of truth is `targets/prod.toml [plugin].version`; `pipelex/.claude-plugin/plugin.json` is generated by the build. Codex/Vibe versions live in their target TOMLs.
- **Marketplace version**: `.claude-plugin/marketplace.json metadata.version` — bumped on any release.
- Versions start at **0.1.0**.

## Local development with Claude Code

To dogfood local changes instead of the published GitHub plugin, point the `pipelex-plugins` marketplace at this checkout. Removing a marketplace uninstalls its plugins and re-adding does not auto-reinstall, so the `install` step is required:

```
/plugin marketplace remove pipelex-plugins
/plugin marketplace add /absolute/path/to/pipelex-plugins
/plugin install pipelex@pipelex-plugins
/reload-plugins
```

The marketplace serves the **prod** output (`pipelex/`). Iteration loop after editing any `.j2` template or `targets/*.toml`: `make build`, then `/reload-plugins`.

Session-only alternative that leaves global config untouched: `claude --plugin-dir /absolute/path/to/pipelex-plugins/pipelex`.

## PostToolUse Hook — CLI-free wasm+API pipeline

Claude Code and Codex run a `PostToolUse` hook against `.mthds` files after every edit; Mistral Vibe's equivalent is `post_tool` (stable hooks API, Vibe 2.21.0+). Nothing shells out to `plxt` or `mthds-agent`: each target ships a thin fail-open wrapper script that runs the shared vendored `check.mjs` bundle (built in `pipelex-sdk-js`) — local lint and format via the inlined `@pipelex/tools-wasm` engine (offline, format writes back in place), then the bundle verdict from `POST /v1/validate` through `@pipelex/sdk` when `PIPELEX_API_KEY` is set. Fail-open: no Node → the whole hook passes silently; no key / API unreachable → the local lint/format verdicts still apply and only the validate stage is skipped. Full details, failure-posture table, and the re-vendor procedure (`make vendor-hook`) in `docs/hooks.md`.

### Codex specifics (verified against Codex 0.144.4, incl. live sessions)

The Codex hook command is `${PLUGIN_ROOT}/hooks/check-mthds-codex.sh` — the wrapper feeds the `apply_patch` envelope to `check.mjs --platform=codex` (several `.mthds` files per patch; outcomes merged, any block wins). Engine facts that make this work:

- The canonical feature key is **`hooks`**, marked `Stage::Stable` and **enabled by default** (`codex_hooks` is a deprecated alias, still honored in 0.144.4; `plugin_hooks` is not an alias but an obsolete independent opt-in, removed in Codex 0.134 and formally `Stage::Removed` since 0.144).
- Native per-source **trust model** (`[hooks.state]` trusted hashes; `--dangerously-bypass-hook-trust` for automation).
- `PostToolUse` officially fires for `apply_patch` edits and MCP tool calls — which de-risks the `.mthds`-on-edit hook.
- Standardized block protocol (`{"decision":"block","reason":...}` or exit 2 + stderr) maps cleanly onto the Stage 3 decision model.
- Installed plugins run from a **cache copy** (`$CODEX_HOME/plugins/cache/...`), and `codex plugin marketplace upgrade` refreshes Git snapshots only — propagate local edits with `make codex-refresh` (an idempotent `codex plugin add`).

So there is nothing to enable — the bundled hook loads on its own (hooks are Stable/default-on) and only needs trusting on first run; no `[features] hooks = true` line and no `apply-config` command. See `docs/decisions.md` and `docs/hooks.md`.

## Key dependency

The plugin imports nothing and requires no install. Validation rides on the vendored `check.mjs` bundle (wasm engine + `@pipelex/sdk` → hosted API) and, for the MCP-backed skills (`pipelex-design`, `pipelex-organize`, `pipelex-edit`, `pipelex-inputs`), on the plugin-declared `pipelex-mcp` server (tools `mthds_validate` / `mthds_inputs_template`, plus the `mthds_run` family powering `pipelex-inputs`' closing offer to run; declared in the Claude and Codex manifests, manual registration on Vibe). The baked declaration is the **local workshop launcher** — `npx -y @pipelex/mcp@latest` over stdio, from the `[vars.mcp_server]` block in `targets/defaults.toml` — never a hosted URL: the hosted console is a connector users add in their host's own UI (see the README's "One install, one server" section and `docs/decisions.md`). The spawned server authenticates with `PIPELEX_API_KEY` from the session env (the hook's variable); on Codex the manifest forwards `PIPELEX_API_KEY`/`PIPELEX_BASE_URL` by name via `env_vars` because Codex whitelist-filters MCP spawn env. Dev override: point `command`/`args` at a local checkout in `targets/defaults.toml` + `make build` on Claude; a same-named `[mcp_servers.pipelex]` entry in `~/.codex/config.toml` on Codex.
