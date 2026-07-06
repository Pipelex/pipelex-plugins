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
│   ├── pipelex-explain/SKILL.md.j2   # First skill (pure read-and-explain)
│   └── shared/
│       ├── frontmatter.md.j2          # Common YAML frontmatter (included by templates)
│       ├── mthds-reference.md.j2      # MTHDS language reference (rendered per target)
│       └── native-content-types.md.j2 # Native content-type documentation
└── hooks/
    ├── hooks.json.j2              # Claude PostToolUse hook config
    ├── codex-hooks.json.j2        # Codex PostToolUse hook config (plugin-bundled)
    ├── vibe-hooks.toml.j2         # Mistral Vibe after_tool hook config
    ├── validate-mthds.sh.j2       # Claude .mthds file validator (silent-pass when CLIs absent)
    └── validate-mthds-vibe.sh.j2  # Vibe .mthds file validator
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

Deliberately **not** carried over from `mthds-plugins`: `min_mthds_version`, `env_check`, `can_run_methods`, `session_start_hook`, and all `*_install_cmd` / `*_upgrade_cmd` variables. Reintroduce a variable only when a skill or hook actually branches on it (e.g. an `mcp_server_url`-style variable arrives with MCP registration). Don't port dead switches.

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

## PostToolUse Hook — CLI-free posture

Claude Code and Codex run a `PostToolUse` hook against `.mthds` files after every edit; Mistral Vibe's equivalent is `after_tool`. The validation pipeline is the same shape across all three targets (`plxt lint` → `plxt fmt` → `validate`, with the Stage 3 domain-based block/context decision model).

The one behavioral difference from `mthds-plugins`:

- **CLIs present** (dev machines that installed the mthds stack for other reasons): the full validation pipeline runs unchanged, including `--format json --error-format json --allow-signatures` pinning.
- **CLIs absent** (the CLI-free environments this plugin targets): the hook detects the missing binaries and **passes silently** — no block, no install nagging, because this plugin does not manage CLI installation.

This is transitional. The iteration path swaps the CLI invocations for hosted-API / MCP calls, at which point the missing-CLI branch disappears entirely.

### Codex specifics (verified against Codex 0.142.5)

The Codex hook command is `mthds-agent codex hook` (validation logic lives in mthds-js), wrapped so a missing `mthds-agent` exits cleanly rather than erroring on every patch. Since Codex 0.141 the hook engine matured out of "under development":

- The canonical feature key is **`hooks`** (`plugin_hooks` / `codex_hooks` are deprecated aliases). Use `hooks`.
- Native per-source **trust model** (`[hooks.state]` trusted hashes; `--dangerously-bypass-hook-trust` for automation).
- `PostToolUse` officially fires for `apply_patch` edits and MCP tool calls — which de-risks the `.mthds`-on-edit hook.
- Standardized block protocol (`{"decision":"block","reason":...}` or exit 2 + stderr) maps cleanly onto the Stage 3 decision model.

So enabling the Codex hook in a CLI-present environment is a single documented `[features] hooks = true` line plus trusting the plugin hook on first run — no `apply-config` command needed. See `docs/decisions.md` and (at Phase 4) the Codex hooks doc.

## Key dependency (transitional)

Today the hooks and any run-capable skills shell out to the MTHDS CLIs (`plxt`, `mthds-agent`) **only when present** — the plugin itself imports nothing and requires no install. As MCP capabilities land, these invocations move to hosted-API / MCP tool calls and the CLI branch is removed.
