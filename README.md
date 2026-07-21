# pipelex-plugins

Pipelex plugins — **skills and hooks for working with MTHDS methods** (`.mthds` bundles) — packaged for **Claude Code**, **Codex**, and **Mistral Vibe**, and served through the Pipelex plugins marketplace.

This is the plugin generation that pairs with the hosted Pipelex API and the (closed-source) MCP server. Unlike the earlier `mthds-plugins`, it carries **no local-CLI dependency and no install/upgrade/env-check machinery** — install is just a marketplace add.

> **Status:** foundation in progress. See the workspace-root tracker `wip/devx/pipelex-plugins-foundations.md` for the phase plan.

## What's inside

- **Skills** — Pipelex skills for working with MTHDS bundles: `pipelex-explain` (read and explain a bundle), `pipelex-design` (design a method top-down by stepwise refinement, validated at every layer through the Pipelex MCP server), `pipelex-organize` (regroup a designed bundle's one-file-per-signature layout into coherent module files — or a single file when the method is simple — proven equivalent through the MCP validation verdict; auto-invoked at the end of `pipelex-design`), `pipelex-edit` (contract-preserving edits to an existing bundle — prompts, model references, mechanical renames — proven with a before/after MCP validation verdict; structural or contract changes route to `/pipelex-design`, which re-enters existing methods), `pipelex-inputs` (prepare an `inputs.json` for a method — placeholder template, synthetic data, user files, or a mix — from the input template the MCP server projects; when the finished inputs are hosted-runnable, it closes by offering to start the run through the MCP run tools).
- **Hooks** — a CLI-free validation hook that checks `.mthds` files on edit (Claude/Codex `PostToolUse`, Mistral Vibe `post_tool`). On every target, lint and format run locally through a bundled WASM engine (offline, no credentials — the file is also auto-formatted in place), and full semantic validation calls the hosted Pipelex API when `PIPELEX_API_KEY` is set. Everything fails open: no Node → the hook no-ops; no key / API unreachable → only the validate stage is skipped. See [docs/hooks.md](docs/hooks.md).
- **MCP server declaration** — on Claude Code and Codex the plugin declares the `pipelex-mcp` server as the **local workshop launcher** (`npx -y @pipelex/mcp@latest`, stdio; tools `mthds_validate` for bundle validation, `mthds_inputs_template` for input templates, and the `mthds_run` family for durable runs), which the MCP-backed skills require. The harness spawns it automatically at session start, and it authenticates to the Pipelex API with the key from the plugin configuration (prompted at enable time on Claude Code) or, as a fallback, `PIPELEX_API_KEY` from your session environment — the same credential the hook uses. Unlike the fail-open hook, the MCP-backed skills stop with a setup instruction when the tools are absent. The hosted console is never baked into the plugin — see [One install, one server](#one-install-one-server--workshop-vs-console) and [docs/decisions.md](docs/decisions.md).
- **Language reference** — the shared MTHDS language reference docs that ground the skills (the *language* stays MTHDS — that's the standard; Pipelex is the tooling, product, and service).

## Install

Install is a marketplace add — no `npm install -g`, no bootstrap, no PATH setup. (Requires the repo to be public.)

### Claude Code

```
claude plugin marketplace add Pipelex/pipelex-plugins
claude plugin install pipelex@pipelex-plugins
```

The `.mthds` validation hook loads automatically and needs no local toolchain beyond Node.js (which Claude Code already requires): lint runs and canonical formatting is applied locally on every `.mthds` edit, offline and credential-free.

To also get full semantic validation (bundle load, cross-file resolution, dry-run) on every edit, give the plugin an API key. When you enable the plugin, Claude prompts for it via the **plugin configuration** dialog (get a key at https://app.pipelex.com; it is stored in your OS keychain, and an optional base URL field covers self-hosted / non-default deployments). Alternatively, the session environment still works as a fallback:

```bash
export PIPELEX_API_KEY=...            # fallback channel — the plugin config dialog is preferred
export PIPELEX_BASE_URL=...           # optional — defaults to https://api.pipelex.com
```

A value set in the plugin configuration wins over the environment; an empty plugin config leaves the environment in charge. The plugin-config channel is what makes **Claude Desktop** work — GUI-launched apps carry no shell environment, so an `export` in your shell profile never reaches them.

Everything fails open: with no key (or the API unreachable) the local lint/format verdicts still apply and only the validate stage is skipped — no blocked edits, no nagging. **Privacy note:** with a key set, the `.mthds` files around the edited one are sent to the API on each validate call; leave the key unset (both channels) to keep validation fully local (lint/format only).

The plugin also declares the **`pipelex-mcp` server** as the **local workshop launcher** (`npx -y @pipelex/mcp@latest`, stdio), which the MCP-backed skills (`pipelex-design`, `pipelex-organize`, `pipelex-edit`, `pipelex-inputs`) use for validation, input templates, and runs. Claude Code spawns it automatically at session start — no extra install: Node.js is already required by the harness, and the spawned server authenticates with the same plugin-config values (falling back to `PIPELEX_API_KEY` / `PIPELEX_BASE_URL` from the session environment). Without a key the tools still connect, but validation calls return a `config` no-verdict explaining how to set one. To use a local `pipelex-mcp` checkout instead, edit the `[vars.mcp_server]` block in `targets/defaults.toml` (e.g. `command = "node"`, `args = ["/path/to/pipelex-mcp/dist/local/main.js"]`) and rebuild via the dogfood loop below.

### Codex

```
codex plugin marketplace add Pipelex/pipelex-plugins
# Restart Codex, then run /plugins to install pipelex
```

The bundled `.mthds` validation hook loads automatically — the `hooks` feature is Stable and on by default in Codex 0.141+, so there is nothing to enable. On first run, **trust** the plugin hook (Codex persists trusted hashes under `[hooks.state]`). It is CLI-free: lint/format run through the bundled WASM engine, and semantic validation uses the Pipelex API when `PIPELEX_API_KEY` is set (a network-sandboxed session simply skips the validate stage). Requires Codex 0.141+ (matured hook engine; verified in live sessions against 0.144.4). See [docs/hooks.md](docs/hooks.md).

**MCP server (automatic):** the plugin manifest declares the `pipelex-mcp` server as the **local workshop launcher** (`npx -y @pipelex/mcp@latest`, stdio), so Codex spawns it on its own — the tools reach the model as `mcp__pipelex__mthds_validate` / `mcp__pipelex__mthds_inputs_template`, and `codex mcp list` shows the `pipelex` entry. Codex spawns MCP servers with a minimal whitelist environment (the shell env is *not* passed through), so the manifest forwards `PIPELEX_API_KEY` and `PIPELEX_BASE_URL` **by name** into the spawn via `env_vars` — export them in your shell exactly as for the hook. Point sessions at a different server with a same-named override, which outranks the plugin declaration:

```toml
# ~/.codex/config.toml
[mcp_servers.pipelex]
command = "node"
args = ["/path/to/pipelex-mcp/dist/local/main.js"]   # e.g. a local checkout

[mcp_servers.pipelex.env]
PIPELEX_API_KEY = "plx_sk_..."
```

(or per invocation: `codex -c 'mcp_servers.pipelex.command="node"' …`). The MCP-backed skills stop with a setup instruction when the tools are absent.

### Mistral Vibe

Vibe loads skills via `skill_paths` and hooks via `hooks.toml`. In `~/.vibe/config.toml`:

```toml
skill_paths = ["/absolute/path/to/pipelex-vibe/skills"]
```

Then wire the generated hook from `pipelex-vibe/hooks/vibe-hooks.toml` into `~/.vibe/hooks.toml` (or a trusted project's `.vibe/hooks.toml` — a project-level entry overrides a user-level entry with the same `name`). If the hook file is not next to the generated target, set its command to the absolute script path:

```toml
[[hooks]]
name = "check-mthds"
type = "post_tool"
match = "re:^(edit|write_file)$"
command = "/absolute/path/to/pipelex-vibe/hooks/check-mthds-vibe.sh"
timeout = 15.0
strict = false
description = "Validate .mthds files after Vibe file edits."
```

Requires Mistral Vibe 2.21.0+ (stable hooks API — `post_tool`, no opt-in flag).

**MCP server (manual, for the MCP-backed skills):** Vibe has no plugin-bundled MCP mechanism here — register the local workshop launcher (`npx -y @pipelex/mcp@latest`, stdio, with `PIPELEX_API_KEY` in its environment) through Vibe's own MCP configuration if/where supported. The MCP-backed skills stop with a setup instruction when the tools are absent.

## One install, one server — workshop vs console

`pipelex-mcp` ships the same tools in two deployments: the **local workshop** (npm `@pipelex/mcp`, stdio — resolves `{ path }` files straight from your working directory) and the **hosted console** (streamable HTTP, for hosts without a filesystem). This plugin always installs the **workshop**: builder hosts edit local `.mthds` files, and submitting local files through a hosted server would mean hand-copying every file into the model's context. The hosted console is never baked into the plugin — it is a **connector** you add in a host's own UI:

| Host | Server | How to connect |
|---|---|---|
| Claude Code | Local workshop | this plugin (spawned automatically) |
| ChatGPT desktop (Codex mode) | Local workshop | this plugin (spawned automatically) |
| Mistral Vibe (TUI) | Local workshop | manual registration (see above) |
| Claude Desktop (chat mode) | Hosted console | Connector in the app UI |
| claude.ai (web + mobile) | Hosted console | Connector (custom URL) |
| ChatGPT (web) | Hosted console | Apps directory |

To reach the hosted console as a connector today, append your key to the connector URL: `https://pipelex-mcp-a3c6a115.alpic.live/mcp?api_key=plx_sk_...` — the console holds no server-side key (bring-your-own-key). **Treat that URL as a secret**: a key in a query string can end up in browser history, copied links, and proxy logs — on hosts that let you set request headers, send `Authorization: Bearer plx_sk_...` instead (the console accepts both; the `?api_key=` form is the fallback for connector UIs that only take a bare URL), and rotate the key if a URL leaks. When console OAuth ships, this passage becomes "add the connector and sign in when prompted", no key touches a URL, and nothing else in this plugin changes.

**Claude Desktop note:** GUI apps don't inherit your shell environment, so an exported `PIPELEX_API_KEY` never reaches Desktop sessions — set the key through the **plugin configuration** dialog instead (prompted when you enable the plugin); it flows to both the spawned workshop and the validation hook. The hosted-console connector remains an alternative if `node`/`npx` is unavailable on your PATH.

**Connect each host to exactly one Pipelex server.** Both deployments register identical tool names, so a host connected to both gets ambiguous routing and contradictory schemas under the same names (the workshop accepts `{ path }`, the console rejects it). The trap to know about: **a claude.ai Pipelex connector syncs into Claude Code automatically** — if you run this plugin (workshop) in Claude Code and also added a Pipelex connector on claude.ai, disable the connector for coding sessions (`/mcp` → "Show unused connectors", per-project `deniedMcpServers` in `.claude/settings.json`, or global `disableClaudeAiConnectors: true`).

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
