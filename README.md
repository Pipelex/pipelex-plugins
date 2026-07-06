# pipelex-plugins

Pipelex plugins — **skills and hooks for working with MTHDS methods** (`.mthds` bundles) — packaged for **Claude Code**, **Codex**, and **Mistral Vibe**, and served through the Pipelex plugins marketplace.

This is the plugin generation that pairs with the hosted Pipelex API and the (closed-source) MCP server. Unlike the earlier `mthds-plugins`, it carries **no local-CLI dependency and no install/upgrade/env-check machinery** — install is just a marketplace add.

> **Status:** foundation in progress. See the workspace-root tracker `wip/devx/pipelex-plugins-foundations.md` for the phase plan.

## What's inside

- **Skills** — Pipelex skills (starting with `pipelex-explain`) for reading and reasoning about MTHDS bundles.
- **Hooks** — a validation hook that checks `.mthds` files on edit (Claude/Codex `PostToolUse`, Mistral Vibe `after_tool`). When the MTHDS CLIs happen to be present locally it runs the full validation pipeline; when they're absent it passes silently (this plugin does not manage CLI installation). The iteration path swaps these for hosted-API / MCP-backed validation. See [docs/hooks.md](docs/hooks.md).
- **Language reference** — the shared MTHDS language reference docs that ground the skills (the *language* stays MTHDS — that's the standard; Pipelex is the tooling, product, and service).

## Install

Install is a marketplace add — no `npm install -g`, no bootstrap, no PATH setup. (Requires the repo to be public.)

### Claude Code

```
claude plugin marketplace add Pipelex/pipelex-plugins
claude plugin install pipelex@pipelex-plugins
```

The `.mthds` validation hook loads automatically. It runs the full validation pipeline only when the MTHDS CLIs (`plxt`, `mthds-agent`) happen to be on your `PATH`; otherwise it passes silently.

### Codex

```
codex plugin marketplace add Pipelex/pipelex-plugins
# Restart Codex, then run /plugins to install pipelex
```

To enable the bundled `.mthds` validation hook — only meaningful when the MTHDS CLIs are present — set `[features] hooks = true` in `~/.codex/config.toml` and **trust** the plugin hook on first run (Codex persists trusted hashes under `[hooks.state]`). Requires Codex 0.141+ (matured hook engine; verified against 0.142.5). See [docs/hooks.md](docs/hooks.md).

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
timeout = 30.0
strict = false
description = "Validate .mthds files after Vibe file edits."
```

Requires Mistral Vibe 2.15.0+ for `after_tool` hooks.

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
