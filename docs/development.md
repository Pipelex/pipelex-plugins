# Develop the plugin

How to build the plugin from its templates, check it, and run a change in your own agent before it is released. The architecture of the build is [build-targets.md](build-targets.md); what CI runs on a pull request is [ci.md](ci.md).

## The build

The plugin is rendered from the Jinja2 templates in `templates/`, with the variables in `targets/`, into one checked-in output per agent: `pipelex/` for Claude Code, `pipelex-codex/` for Codex and `pipelex-vibe/` for Mistral Vibe. Never edit a generated output directly; the next build overwrites it, and `make check` fails while it differs from its source. Nor add a file to one: the build owns those directories and removes whatever no template or source produces, a `.j2` template and a file git ignores aside, so a file added there by hand is gone after the next build.

```bash
make build           # render every target (prod, codex, mistral-vibe)
make check           # template freshness, marketplace and version consistency, lint and type checks
make agent-check     # fix unused imports, format and lint, then make check
make agent-test      # the unit tests, quiet unless one fails
make test            # the unit tests, verbose
make test-recipes    # execute the synthetic-inputs recipes (opt-in: runs uv and downloads packages)
make vendor-hook     # rebuild the hook bundle in ../pipelex-sdk-js and copy it into templates/hooks/assets/
make check-hook-fresh  # release gate: fail when the hook bundle is behind npm's engine or a rebuild in ../pipelex-sdk-js
```

`make check-shared`, `make check-claude` and `make check-codex` run the three parts of `make check` one at a time, and `make gen-skill-docs TARGET=<name>` renders a single target.

The editing loop is: edit a `.j2` file under `templates/` or a file under `targets/`, run `make build`, then run `make agent-check` and `make agent-test`. Run both before you push.

The hook bundle, `templates/hooks/assets/check.mjs`, is built in `pipelex-sdk-js` rather than here, so two guards keep it honest. `make check` refuses one whose provenance line names an unreleased engine or no SDK commit, which runs anywhere, CI included. `make check-hook-fresh` fails when the bundle is behind npm's latest `@pipelex/tools-wasm` or when a rebuild in the sibling checkout would change it; it needs that checkout on `dev` and clean, and the network, which CI does not have, so it is a release gate. `docs/hooks.md` ("Re-vendoring check.mjs") has both, and the re-vendor procedure.

## Run your changes in your agent

This is the dogfood loop: point your agent at this checkout instead of the published plugin, then rebuild and reload as you edit.

### Claude Code

Point the `pipelex-plugins` marketplace at this checkout. Removing a marketplace uninstalls its plugins and adding it again does not reinstall them, so the `install` step is required:

```
/plugin marketplace remove pipelex-plugins
/plugin marketplace add /absolute/path/to/pipelex-plugins
/plugin install pipelex@pipelex-plugins
/reload-plugins
```

The marketplace serves the prod output, `pipelex/`. After each edit, run `make build`, then `/reload-plugins`.

To try a change for one session without touching your global configuration, start Claude Code with the plugin directory instead:

```bash
claude --plugin-dir /absolute/path/to/pipelex-plugins/pipelex
```

To go back to the published plugin, remove the marketplace and add it again as `Pipelex/pipelex-plugins`, as in [the install page](install.md#claude-code).

### Codex

```bash
make codex-use-local       # point the Codex marketplace at this checkout
make codex-refresh         # after make build: re-sync the installed plugin's cache copy
make codex-use-official    # point Codex back at the published GitHub marketplace
make codex-status          # show which source the Codex marketplace uses now
```

Restart Codex after `codex-use-local` or `codex-use-official`, and trust the hook again if its configuration changed. Codex runs an installed plugin from a cache copy taken when the plugin is added, so an edit reaches a session only after `make build` and `make codex-refresh`. The cache model is recorded in [decisions.md](decisions.md), "Codex plugin lifecycle".

### Mistral Vibe

The Vibe setup in [the install page](install.md#mistral-vibe) already points at a checkout, so point it at this one and run `make build` after each edit.

## A local build of `pipelex-mcp`

`pipelex-mcp` ships two servers, each with its own tools, over one capability core: the **local workshop** (npm `@pipelex/mcp`, over stdio), whose `mthds_*` tools the skills call and which resolves `{ path }` files straight from your working directory, and the **hosted console** at `https://mcp.pipelex.com/mcp` (streamable HTTP), whose `pipelex_*` tools run saved methods for chatbots and take no files at all. No tool name is registered by both. Public text calls them the Pipelex tools and the Pipelex MCP. The plugin always declares the workshop: an agent edits local `.mthds` files, which only the workshop can read. The console is never baked into the plugin; the reasoning is in [decisions.md](decisions.md), "Dual-MCP flip".

The plugin declares the workshop as `npx -y @pipelex/mcp@latest` in the `[vars.mcp_server]` block of `targets/defaults.toml`. To run the skills against a local checkout of [`pipelex-mcp`](https://github.com/Pipelex/pipelex-mcp), first build its workshop with `make build-local` at the root of that checkout, which writes `packages/workshop/dist/main.js`. A checkout built before `pipelex-mcp` became an npm workspace still holds an older `dist/local/main.js` that nothing rebuilds any more, so never point a harness at it. Then:

- **Claude Code.** Set `command = "node"` and `args = ["/path/to/pipelex-mcp/packages/workshop/dist/main.js"]` in that block, run `make build`, and reload as above. Switch it back before you commit, since the build writes the block into every target.
- **Codex.** Leave the plugin alone and add an entry of the same name to `~/.codex/config.toml`, which outranks the plugin's; the example is in [the install page](install.md#codex).
- **Mistral Vibe.** Set the same `command` and `args` in the `pipelex` entry you appended to `~/.vibe/config.toml`, which Vibe reads instead of the fragment in this repository.

The repository's `/pipelex-mcp-source` skill, under `.claude/skills/`, makes that switch and the switch back, pins a version, and reports which version each deployment serves.
