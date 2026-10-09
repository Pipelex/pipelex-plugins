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
make vendor-hook     # rebuild the hook bundle in ../pipelex-sdk/js and copy it into templates/hooks/assets/
make check-hook-fresh  # release gate: fail when the hook bundle is behind npm's engine or a rebuild in ../pipelex-sdk/js
```

`make check-shared`, `make check-claude` and `make check-codex` run the three parts of `make check` one at a time, and `make gen-skill-docs TARGET=<name>` renders a single target.

The editing loop is: edit a `.j2` file under `templates/` or a file under `targets/`, run `make build`, then run `make agent-check` and `make agent-test`. Run both before you push.

The hook bundle, `templates/hooks/assets/check.mjs`, is built in the `js/` directory of `pipelex-sdk` rather than here, so two guards keep it honest. `make check` refuses one whose provenance line names an unreleased engine or no SDK commit, which runs anywhere, CI included. `make check-hook-fresh` fails when the bundle is behind npm's latest `@pipelex/tools-wasm` or when a rebuild in the sibling checkout would change it; it needs that checkout on `dev` and clean, and the network, which CI does not have, so it is a release gate. `docs/hooks.md` ("Re-vendoring check.mjs") has both, and the re-vendor procedure.

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

`pipelex-mcp` is the **local workshop** (npm `@pipelex/mcp`, over stdio), whose `mthds_*` tools the skills call and which resolves `{ path }` files straight from your working directory. The **hosted console** at `https://mcp.pipelex.com/mcp` (streamable HTTP), whose `pipelex_*` tools run saved methods for chatbots and take no files at all, is a separate server with a repository of its own. No tool name is registered by both. Public text calls them the Pipelex tools and the Pipelex MCP. The plugin always declares the workshop: an agent edits local `.mthds` files, which only the workshop can read. The console is never baked into the plugin; the reasoning is in [decisions.md](decisions.md), "Dual-MCP flip".

The plugin declares the workshop as `npx -y @pipelex/mcp@latest` in the `[vars.mcp_server]` block of `targets/defaults.toml`. To run the skills against another workshop, a local checkout of [`pipelex-mcp`](https://github.com/Pipelex/pipelex-mcp) or a published version, start your agent with one make target. Neither target changes a tracked file, so there is nothing to switch back before you commit.

```bash
make claude-local-mcp                                  # Claude Code, with the workshop of ../pipelex-mcp
make claude-local-mcp MCP=../_pipelex-mcp--my-topic    # any checkout or worktree of pipelex-mcp
make claude-local-mcp MCP_VERSION=0.19.0               # a published version or dist-tag, to reproduce it
make codex-local-mcp                                   # Codex, the same way, with the same variables
make claude-local-mcp WORKDIR=~/my-methods ARGS='--model sonnet'
```

A target given `MCP` first builds that checkout's workshop with its own `make build-local`, which writes `dist/main.js` at the checkout's root, and the agent then spawns it by absolute path. `MCP` defaults to `../pipelex-mcp`. The targets read `MCP`, `MCP_VERSION`, `WORKDIR` and `ARGS` from make's command line alone, so a variable of one of those names that your shell exports for another tool is neither taken by a target nor removed from the session it starts. A target given `MCP_VERSION` builds nothing: it asks npm which version that names and spawns exactly that one through `npx`, so a version npm does not know is refused before the agent starts. `WORKDIR` is where the session starts, which matters because the workshop resolves a `{ path }` file against it; it defaults to this checkout. `ARGS` goes to `claude` or `codex` as it is. An interactive session takes the place of the make process, so start one from a terminal of its own. A headless prompt runs to its end and returns, so an agent can also run one from its own shell to try a workshop change: `ARGS='-p "…"'` on Claude Code, and `ARGS='exec "…"'` on Codex, where `-p` names a configuration profile instead.

- **Claude Code.** The target renders the Claude plugin from this checkout's templates, with the build's own renderer and the launcher pointed at the chosen workshop, into a directory of that workshop's own under `.local-mcp/`, which git ignores. It then starts `claude --plugin-dir` on that copy. A session reads the copy's launcher again whenever it restarts the Pipelex tools, so each workshop has its own copy, and starting another workshop never changes the one a running session uses; starting the same workshop again renders its copy afresh from this checkout's templates. Delete `.local-mcp/` whenever no session runs from it. The copy loads as `pipelex@inline` and takes the place of an installed `pipelex@pipelex-plugins` for that session only, so the skills you run are this checkout's too. Its plugin options arrive empty, since the key saved for the installed plugin is not the copy's, so the workshop takes the key exported in your shell as `PIPELEX_API_KEY`, and the target warns when there is none.
- **Codex.** The target renders nothing: it starts `codex` with `-c` overrides of the `mcp_servers.pipelex` entry. An entry given that way replaces the plugin's whole, so the overrides forward `PIPELEX_API_KEY` and `PIPELEX_BASE_URL` by name as the plugin does, and the workshop takes the key from your shell. The skills are whichever copy of the plugin Codex has installed: the published one, or this checkout after `make codex-use-local`.
- **Mistral Vibe.** There is no target. Set `command = "node"` and `args = ["/path/to/pipelex-mcp/dist/main.js"]` in the `pipelex` entry you appended to `~/.vibe/config.toml`, which Vibe reads instead of the fragment in this repository, after `make build-local` in that checkout. A checkout built while `pipelex-mcp` was an npm workspace still holds that layout's `packages/workshop/dist/main.js`, which nothing rebuilds any more and only `make clean` there removes, so never point Vibe at it.

The repository's `/pipelex-mcp-source` skill, under `.claude/skills/`, reports which version npm and a local build serve and which version the hosted console should serve, and says which target runs the one you want. Why these are make targets rather than a skill, and how their behaviour was verified, is in [decisions.md](decisions.md), "A local workshop is one make target".

## Rendering for an outside target

A repository that keeps skills of its own renders this plugin's skills with them through the `pipelex-plugins-render` console command, from a target file and templates that never enter this public repository. What a target file holds and what the render refuses are in [build-targets.md](build-targets.md), "Outside targets"; this section is how a consumer runs the command and keeps its declarations current.

**Run it at a pin.** uv builds the command from a git ref into an environment of its own, so the consumer needs uv and nothing else:

```bash
uvx --from git+https://github.com/Pipelex/pipelex-plugins@<ref> pipelex-plugins-render path/to/target.toml           # render into the target's output
uvx --from git+https://github.com/Pipelex/pipelex-plugins@<ref> pipelex-plugins-render path/to/target.toml --check   # compare the output with a fresh rendering; write nothing
```

The ref is the pin: the package carries the templates, static assets and targets of that commit inside itself, so the consumer's rendering changes only when it moves the ref. A release tag is the ref to pin; `@dev` follows the development branch, for trying a change before it is released. Run it through `uvx` rather than installing it into a project's environment: the package installs a top-level `scripts` package, a name another distribution may also use ([decisions.md](decisions.md), "The outside render ships in the tooling package").

**A declaration's hash** is the SHA-256 of the upstream file's bytes at the pin, written `sha256:` and the 64 hex digits. Compute it from a checkout of this repository at that ref, or straight from GitHub:

```bash
shasum -a 256 templates/skills/shared/saved-copy-notice.md.j2                     # in a checkout at the ref
curl -sL https://raw.githubusercontent.com/Pipelex/pipelex-plugins/<ref>/templates/skills/shared/saved-copy-notice.md.j2 | shasum -a 256
```

When the pin moves past a change to a declared file, the render refuses and names the file and both hashes. Read the upstream change, carry what applies into the replacement, then write the new hash.

**Try a change here against a consumer** before it is pushed: `uvx --from /path/to/this/checkout pipelex-plugins-render path/to/target.toml`. uv builds the package from the checkout's files, committed or not, leaving out what git ignores, and rebuilds it whenever one of them changes (`[tool.uv] cache-keys` in `pyproject.toml`), so each run reads the checkout as it is. From this checkout itself, `python -m scripts.outside_render` takes the same arguments without a build.

**This repository checks the command itself** with a smoke fixture, `tests/data/outside-target-smoke/`, whose rendering is committed beside it. `make check-outside-smoke` builds the package and runs the installed command's `--check` on a copy of it outside the checkout, as CI does on every pull request ([ci.md](ci.md)); `make render-outside-smoke` re-renders the committed output after a change to the one upstream partial its skill includes.
