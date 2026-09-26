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

The plugin declares the workshop as `npx -y @pipelex/mcp@latest` in the `[vars.mcp_server]` block of `targets/defaults.toml`. To run the skills against another workshop, a local checkout of [`pipelex-mcp`](https://github.com/Pipelex/pipelex-mcp) or a published version, start your agent with one make target. Neither target changes a tracked file, so there is nothing to switch back before you commit.

```bash
make claude-local-mcp                                  # Claude Code, with the workshop of ../pipelex-mcp
make claude-local-mcp MCP=../_pipelex-mcp--my-topic    # any checkout or worktree of pipelex-mcp
make claude-local-mcp MCP_VERSION=0.19.0               # a published version or dist-tag, to reproduce it
make codex-local-mcp                                   # Codex, the same way, with the same variables
make claude-local-mcp WORKDIR=~/my-methods ARGS='--model sonnet'
```

A target given `MCP` first builds that checkout's workshop with its own `make build-local`, which writes `packages/workshop/dist/main.js`, and the agent then spawns it by absolute path. `MCP` defaults to `../pipelex-mcp`. A target given `MCP_VERSION` builds nothing: it asks npm which version that names and spawns exactly that one through `npx`, so a version npm does not know is refused before the agent starts. `WORKDIR` is where the session starts, which matters because the workshop resolves a `{ path }` file against it; it defaults to this checkout. `ARGS` goes to `claude` or `codex` as it is, so `ARGS='-p "…"'` runs one headless prompt. Start either target from a terminal, not from inside an agent's session.

- **Claude Code.** The target renders the Claude plugin from this checkout's templates, with the build's own renderer and the launcher pointed at the chosen workshop, into a directory of that workshop's own under `.local-mcp/`, which git ignores. It then starts `claude --plugin-dir` on that copy. A session reads the copy's launcher again whenever it restarts the Pipelex tools, so each workshop has its own copy, and starting another workshop never changes the one a running session uses; starting the same workshop again renders its copy afresh from this checkout's templates. Delete `.local-mcp/` whenever no session runs from it. The copy loads as `pipelex@inline` and takes the place of an installed `pipelex@pipelex-plugins` for that session only, so the skills you run are this checkout's too. Its plugin options arrive empty, since the key saved for the installed plugin is not the copy's, so the workshop takes the key exported in your shell as `PIPELEX_API_KEY`, and the target warns when there is none.
- **Codex.** The target renders nothing: it starts `codex` with `-c` overrides of the `mcp_servers.pipelex` entry. An entry given that way replaces the plugin's whole, so the overrides forward `PIPELEX_API_KEY` and `PIPELEX_BASE_URL` by name as the plugin does, and the workshop takes the key from your shell. The skills are whichever copy of the plugin Codex has installed: the published one, or this checkout after `make codex-use-local`.
- **Mistral Vibe.** There is no target. Set `command = "node"` and `args = ["/path/to/pipelex-mcp/packages/workshop/dist/main.js"]` in the `pipelex` entry you appended to `~/.vibe/config.toml`, which Vibe reads instead of the fragment in this repository, after `make build-local` in that checkout. A checkout built before `pipelex-mcp` became an npm workspace still holds an older `dist/local/main.js` that nothing rebuilds any more, so never point Vibe at it.

The repository's `/pipelex-mcp-source` skill, under `.claude/skills/`, reports which version npm, the hosted console and a local build serve, and says which target runs the one you want. Why these are make targets rather than a skill, and how their behaviour was verified, is in [decisions.md](decisions.md), "A local workshop is one make target".
