# pipelex-plugins

Pipelex plugins — **skills and hooks for working with MTHDS methods** (`.mthds` bundles) — packaged for **Claude Code**, **Codex**, and **Mistral Vibe**, and served through the Pipelex plugins marketplace.

This is the plugin generation that pairs with the hosted Pipelex API and the (closed-source) MCP server. Unlike the earlier `mthds-plugins`, it carries **no local-CLI dependency and no install/upgrade/env-check machinery** — install is just a marketplace add.

> **Status:** foundation in progress. See the workspace-root tracker `wip/devx/pipelex-plugins-foundations.md` for the phase plan.

## What's inside

- **Skills** — Pipelex skills for working with MTHDS bundles: `pipelex-explain` (read and explain a bundle), `pipelex-design` (design a method top-down by stepwise refinement, validated at every layer through the Pipelex MCP server), `pipelex-inputs` (prepare an `inputs.json` for a method — placeholder template, synthetic data, user files, or a mix — from the input template the MCP server projects).
- **Hooks** — a CLI-free validation hook that checks `.mthds` files on edit (Claude/Codex `PostToolUse`, Mistral Vibe `after_tool`). On every target, lint and format run locally through a bundled WASM engine (offline, no credentials — the file is also auto-formatted in place), and full semantic validation calls the hosted Pipelex API when `PIPELEX_API_KEY` is set. Everything fails open: no Node → the hook no-ops; no key / API unreachable → only the validate stage is skipped. See [docs/hooks.md](docs/hooks.md).
- **MCP server declaration** — the Claude plugin declares the `pipelex-mcp` server (streamable HTTP; tools `mthds_validate` for bundle validation and `mthds_inputs` for input templates), which the MCP-backed skills require. It connects automatically at session start; override the baked URL with `PIPELEX_MCP_URL` (e.g. a local dev server). Unlike the fail-open hook, the MCP-backed skills stop with a setup instruction when the server isn't reachable. See [docs/decisions.md](docs/decisions.md).
- **Language reference** — the shared MTHDS language reference docs that ground the skills (the *language* stays MTHDS — that's the standard; Pipelex is the tooling, product, and service).

## Install

Install is a marketplace add — no `npm install -g`, no bootstrap, no PATH setup. (Requires the repo to be public.)

### Claude Code

```
claude plugin marketplace add Pipelex/pipelex-plugins
claude plugin install pipelex@pipelex-plugins
```

The `.mthds` validation hook loads automatically and needs no local toolchain beyond Node.js (which Claude Code already requires): lint runs and canonical formatting is applied locally on every `.mthds` edit, offline and credential-free.

To also get full semantic validation (bundle load, cross-file resolution, dry-run) on every edit, set an API key:

```bash
export PIPELEX_API_KEY=...            # get one at https://app.pipelex.com
export PIPELEX_BASE_URL=...           # optional — defaults to https://api.pipelex.com
```

Everything fails open: with no key (or the API unreachable) the local lint/format verdicts still apply and only the validate stage is skipped — no blocked edits, no nagging. **Privacy note:** with a key set, the `.mthds` files around the edited one are sent to the API on each validate call; unset `PIPELEX_API_KEY` to keep validation fully local (lint/format only).

The plugin also declares the **`pipelex-mcp` server**, which the MCP-backed skills (`pipelex-design`, `pipelex-inputs`) use for validation and input templates; it connects automatically. The baked URL is a placeholder until the server is deployed — point the session at a running server with:

```bash
export PIPELEX_MCP_URL=http://localhost:3000/mcp   # e.g. a local pipelex-mcp dev server
```

### Codex

```
codex plugin marketplace add Pipelex/pipelex-plugins
# Restart Codex, then run /plugins to install pipelex
```

The bundled `.mthds` validation hook loads automatically — the `hooks` feature is Stable and on by default in Codex 0.141+, so there is nothing to enable. On first run, **trust** the plugin hook (Codex persists trusted hashes under `[hooks.state]`). It is CLI-free: lint/format run through the bundled WASM engine, and semantic validation uses the Pipelex API when `PIPELEX_API_KEY` is set (a network-sandboxed session simply skips the validate stage). Requires Codex 0.141+ (matured hook engine; verified in live sessions against 0.144.4). See [docs/hooks.md](docs/hooks.md).

**MCP server (automatic):** the plugin manifest declares the `pipelex-mcp` server (streamable HTTP), so Codex connects it on its own — the tools reach the model as `mcp__pipelex__mthds_validate` / `mcp__pipelex__mthds_inputs`, and `codex mcp list` shows the `pipelex` entry. The baked URL is a placeholder until the server deploys; Codex does no env expansion in MCP config, so point sessions at a running server with a same-named override, which outranks the plugin declaration:

```toml
# ~/.codex/config.toml
[mcp_servers.pipelex]
url = "http://localhost:3000/mcp"   # e.g. a local pipelex-mcp dev server
```

(or per invocation: `codex -c 'mcp_servers.pipelex.url="http://localhost:3000/mcp"' …`). The MCP-backed skills stop with a setup instruction when the tools are absent.

### Mistral Vibe

Vibe loads skills via `skill_paths` and hooks via `hooks.toml`. In `~/.vibe/config.toml`:

```toml
enable_experimental_hooks = true
skill_paths = ["/absolute/path/to/pipelex-vibe/skills"]
```

Then wire the generated hook from `pipelex-vibe/hooks/vibe-hooks.toml` into `~/.vibe/hooks.toml` (or a trusted project's `.vibe/hooks.toml`). If the hook file is not next to the generated target, set its command to the absolute script path:

```toml
[[hooks]]
name = "validate-mthds"
type = "after_tool"
match = "re:^(edit|write_file)$"
command = "/absolute/path/to/pipelex-vibe/hooks/validate-mthds-vibe.sh"
timeout = 15.0
strict = false
description = "Validate .mthds files after Vibe file edits."
```

Requires Mistral Vibe 2.15.0+ for `after_tool` hooks.

**MCP server (manual, for the MCP-backed skills):** Vibe has no plugin-bundled MCP mechanism here — register the `pipelex-mcp` server (streamable HTTP) through Vibe's own MCP configuration if/where supported. The MCP-backed skills stop with a setup instruction when the tools are absent.

## Local development

The build renders every target from Jinja2 templates. Never edit generated output directly.

```
make build      # render all targets (prod + codex + mistral-vibe)
make check      # freshness + marketplace/version consistency + lint/type checks
make test       # unit tests
```

### Dogfood loop

**Claude Code** — point the marketplace at this checkout, then iterate with `make build` + `/reload-plugins`:

```
/plugin marketplace remove pipelex-plugins
/plugin marketplace add /absolute/path/to/pipelex-plugins
/plugin install pipelex@pipelex-plugins
/reload-plugins
```

Session-only alternative that leaves global config untouched: `claude --plugin-dir /absolute/path/to/pipelex-plugins/pipelex`.

**Codex** — `make codex-use-local` points the Codex marketplace at this checkout (restart Codex to pick it up); `make codex-use-official` switches back to the published GitHub marketplace; `make codex-refresh` re-syncs the plugin cache after editing `pipelex-codex/`.

## License

[Apache 2.0](./LICENSE).
