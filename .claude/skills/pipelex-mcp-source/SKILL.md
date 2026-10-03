---
name: pipelex-mcp-source
description: >
  Reports which workshop version npm and a local `../pipelex-mcp` build serve,
  and which version the hosted console at mcp.pipelex.com should serve, says which make
  target runs the plugin against another workshop — a local checkout or a
  pinned npm version — without touching a tracked file, and changes the
  workshop the plugin ships when that is really wanted. Use this skill
  whenever the user says "bump pipelex-mcp", "which MCP version am I using",
  "switch the MCP source", "test against my local pipelex-mcp", "pin the MCP
  version", "point the plugin at the local workshop", "go back to the
  released MCP", "is the console up to date", or mentions the hosted console /
  Alpic deployment / `@pipelex/mcp` npm package in the context of versions.
  Also use it after `pipelex-mcp` ships a release, when an MCP-backed skill
  (`pipelex-design`, `pipelex-organize`, `pipelex-edit`, `pipelex-inputs`)
  behaves unexpectedly and the server version is suspect, or before
  committing, to check that no hand-made switch leaked into the tree.
---

# pipelex-mcp source

Reports the version the workshop is actually serving, from npm or a local build, and the version the hosted console should serve, and says how to run this plugin against a workshop other than the one it ships.

## The mental model

`targets/defaults.toml` `[vars.mcp_server]` is the **single source of truth** for the workshop the plugin ships. `make build` fans it out to every generated artifact:

- `pipelex/.claude-plugin/plugin.json` and `pipelex-codex/.codex-plugin/plugin.json` — the `mcpServers.pipelex` entry the harness spawns (on Claude, through the `hooks/launch-pipelex-mcp.sh` wrapper, whose `exec` line carries the command)
- `pipelex-vibe/mcp/vibe-mcp.toml` — the `[[mcp_servers]]` fragment Vibe users copy into `~/.vibe/config.toml`, since Vibe has no manifest
- every MCP-backed `SKILL.md` across all three targets — their "server isn't connected" line renders `{{ mcp_server.command }} {{ mcp_server.args | join(" ") }}`, so the quoted launcher tracks the config automatically

That fan-out is why editing the block is never a one-file change, and why it shows up as a wide diff. Prose docs (`docs/install.md`, `docs/development.md`, `docs/decisions.md`, `docs/build-targets.md`, `CLAUDE.md`) quote the launcher too, but they describe **what ships** — see "Changing the shipped default" for the only case where they move.

**Running against another workshop never edits that block.** `make claude-local-mcp` and `make codex-local-mcp` start the agent on the workshop of a local checkout or of a pinned npm version and change no tracked file, so nothing has to be switched back and nothing can leak into a commit (`docs/development.md`, "A local build of `pipelex-mcp`"). An edit of the block that is not a change to what ships is a hand-made switch: a pinned version or an absolute local path means nothing on anyone else's machine, and it must never reach a commit.

## The three sources

All three are stdio — the renderer emits only `command`/`args`, and the hosted console is deliberately not bakeable (see "The hosted console").

| Source | `command` | `args` | How it runs |
|---|---|---|---|
| `npm-latest` | `npx` | `["-y", "@pipelex/mcp@latest"]` | **What ships.** The committed default. |
| `npm-pinned` | `npx` | `["-y", "@pipelex/mcp@X.Y.Z"]` | `make claude-local-mcp MCP_VERSION=X.Y.Z`, or `codex-local-mcp` — reproduce a released version. |
| `local` | `node` | `["<absolute>/pipelex-mcp/dist/main.js"]` | `make claude-local-mcp MCP=<checkout>`, or `codex-local-mcp` — test unreleased changes. |

`pipelex-mcp` is one npm package at its repository root, `@pipelex/mcp`, and `make build-local`, run at the root of a checkout, bundles the workshop into `dist/main.js`. **Two older paths are never rebuilt.** `packages/workshop/dist/main.js` is the output of the npm-workspace layout the repository had before, which a checkout built in that time still holds, untracked, until `make clean` there removes it; `dist/local/main.js` is older still, and the first build in the current layout deletes it. Anything still pointing at `packages/workshop/dist/main.js` — a Vibe entry, a Codex override, a hand-made switch — spawns a stale workshop without any error.

`@latest` is the shipped default on purpose: `npx` re-resolves the dist-tag per spawn, so users track releases with no plugin bump, and `docs/decisions.md` records that pinning buys no offline resilience (npx contacts the registry even for cached exact specs). Pinning is a **testing tool**, not a release posture. If the user asks to ship a pin, say that it contradicts that recorded decision and ask them to confirm before proceeding — they may have a good reason, but it should be a deliberate reversal with a `docs/decisions.md` amendment, not a side effect of this skill.

## Status — the default action

When the user invokes this skill without naming a target, report current state and stop. Gather in parallel:

1. **Declared source** — read `[vars.mcp_server]` from `targets/defaults.toml`. Anything but `npm-latest` is a hand-made switch; see "Restoring the shipped default". If its `args` name `packages/workshop/dist/main.js` or `dist/local/main.js`, say too that this is an old path, which runs a stale build.
2. **npm `latest`** — `npm view @pipelex/mcp dist-tags --json` (and `npm view @pipelex/mcp versions --json` if they need the list of published versions to pin to).
3. **Console** — the version Production should serve, and the probe that shows it is up, both as "The hosted console" says. The console has a release track of its own, so never compare it with npm `latest`.
4. **Local checkout version** — `node -p "require('../pipelex-mcp/package.json').version"`, the root manifest npm publishes as `@pipelex/mcp`. `undefined` means the checkout predates the move to one package and needs a pull before anything else. A version behind npm `latest` means the checkout needs a pull. A version equal to it is the ordinary case on `dev`, since the version moves only at a release: what the checkout has that npm lacks is listed under `## [Unreleased]` in `../pipelex-mcp/CHANGELOG.md`, and an empty section there means the local source tests nothing new.
5. **Local build** — does `../pipelex-mcp/dist/main.js` exist, and is it stale? The bundle inlines everything under `src/`, and its handshake reports the version the root manifest had at build time, so it lags whenever those sources or that manifest are newer: `find ../pipelex-mcp/src ../pipelex-mcp/package.json -type f \( -name '*.ts' -o -name package.json \) ! -name '*.test.ts' ! -name '*.e2e.ts' -newer ../pipelex-mcp/dist/main.js` printing anything means the build lags. A lagging build matters only to a running session or a Vibe entry: the make targets rebuild before they start.
6. **Leaked dev state** — `git diff --stat targets/defaults.toml` and `git status --porcelain pipelex/ pipelex-codex/ pipelex-vibe/`. If the declared source is not `npm-latest`, lead with that: the tree is carrying a hand-made switch.
7. **The local copies** — `make claude-local-mcp` renders one copy of the plugin per workshop, under `.local-mcp/<key>/pipelex/`, and the `exec` line of each copy's `hooks/launch-pipelex-mcp.sh` says which workshop it spawns. They are ignored by git and never shipped, so they are information, not dev state to clean up; deleting `.local-mcp/` while no session runs from it loses nothing.

Present it as a short table, not prose. The useful signal is usually a *mismatch* — declared source vs what npm serves vs what the local build contains — so state plainly whether they agree, and if the user is on `npm-latest` and the checkout's workshop version equals npm `latest` with nothing under `## [Unreleased]`, say there is nothing to bump.

## Running against another workshop

Name the target and let the user start it from a terminal: it starts an interactive agent in place of the make process, which a session's own shell cannot host.

- A local checkout or worktree: `make claude-local-mcp MCP=<path>` (default `../pipelex-mcp`), or `make codex-local-mcp MCP=<path>`. The target runs `make build-local` there first.
- A released version: `make claude-local-mcp MCP_VERSION=X.Y.Z`, or the Codex twin. The target refuses a version npm does not know before anything starts.
- `WORKDIR=<dir>` starts the session in a project, since the workshop resolves `{ path }` files against it; `ARGS='…'` goes to `claude` or `codex` as it is.

A headless prompt is the one form an agent can run itself, and it is how to dogfood a workshop change from inside a session: `make claude-local-mcp MCP=<path> WORKDIR=<scratch project> ARGS='-p "…" --model sonnet'`, or `make codex-local-mcp MCP=<path> WORKDIR=<scratch project> ARGS='exec "…"'`, since Codex's `-p` names a configuration profile. Each workshop gets its own rendered copy, so such a run never changes the workshop of the session it was started from. The workshop takes its key from the shell's `PIPELEX_API_KEY` in both targets, and the target warns when it is unset. On Claude Code, the rendered copy loads as `pipelex@inline` in place of an installed `pipelex@pipelex-plugins`, so its skills are this checkout's. On Codex, the skills are the installed copy's: pair the target with `make codex-use-local` to run this checkout's. Mistral Vibe has no target; `docs/development.md` says which entry to edit.

## Restoring the shipped default

Only a hand-made switch needs this. Restore `[vars.mcp_server]` to `npx` + `["-y", "@pipelex/mcp@latest"]`, then `make build` and `make check`.

Prefer `git show origin/main:targets/defaults.toml` as the reference for what actually ships rather than assuming — if the shipped default ever moves, that reads the truth instead of a stale literal. Fall back to `HEAD` when `origin/main` is unavailable, and to the literal above if both disagree with it (which would itself mean a switch got committed — worth flagging).

Read that reference, but restore by **editing the two fields back**, not by copying the whole file over `targets/defaults.toml`. Concurrent sessions may share this checkout and a whole-file copy silently discards their unrelated edits — including a `user_config` or `env_vars` change someone is mid-way through.

Verify the generated outputs came back clean: `git status --porcelain targets/defaults.toml pipelex/ pipelex-codex/ pipelex-vibe/` should be empty if the switch was the only local change. If it isn't, show what remains rather than assuming it is unrelated.

## Changing the shipped default

Rare, and the only case where prose docs move. This is a real change to the plugin — a new package name, a different launcher command, or a deliberate reversal of the `@latest` posture.

Edit only `command` and `args` in `targets/defaults.toml` `[vars.mcp_server]`, leaving `env_vars` and every `user_config` table alone, since credential delivery is orthogonal to which build gets spawned. Run `make build`, then `make check`. Then propagate to the docs that quote the launcher as *current fact*: `docs/install.md`, `docs/development.md`, `docs/decisions.md`, `docs/build-targets.md`, `CLAUDE.md`. Grep for `@pipelex/mcp@` and `npx -y @pipelex` to find them rather than trusting this list.

**Do not rewrite** the existing entries of `CHANGELOG.md` — they are a historical record of what was true at the time, and editing them destroys the record. Add a new `CHANGELOG.md` entry describing the change instead. Amend `docs/decisions.md` where the change contradicts a recorded decision, so the reasoning stays discoverable; this repo treats decisions as durable, so supersede the entry with the new rationale rather than deleting it.

## The hosted console

The console at `https://mcp.pipelex.com/mcp` is **read-only from this skill**. It is never baked into the plugin: the plugin's audience is builders editing local files, which only the workshop can read, and the console authenticates each caller by OAuth sign-in that the host drives through its own connector UI (bring-your-own-key was removed in `@pipelex/mcp` 0.12.0), which no shared plugin artifact can carry. `docs/decisions.md` records this; the renderer has no url shape to emit.

The console lives in its own repository, `../pipelex-mcp-console`, as the private package `@pipelex/mcp-console`. Up to and including 0.20.0 both servers shipped together from `pipelex-mcp` at one version; since then the console has had a release track of its own, now that repository's `package.json` version, tagged `vX.Y.Z` there, so its version and npm's `latest` move independently and a difference between them means nothing. Alpic builds Production from that repository's `main`, so what the console should serve is the version `git -C ../pipelex-mcp-console show origin/main:package.json` carries, after a `git -C ../pipelex-mcp-console fetch`.

What this skill does for the console: report that version and probe that the console is up, never more. The probe cannot read the version the console runs, since it answers no keyless handshake (see "Proving what's actually running"), so never report a version as live unless a signed-in connector session showed it. A release that did not deploy is the console's own `/promote-main` to check, since it reads the deployment from Alpic. If the console is due a release, the fix is in `../pipelex-mcp-console` — its `/release`, then `/promote-staging` and `/promote-main` — so say so and hand off rather than deploying from here.

Two things worth telling the user when the console comes up:

- **A stale version in a connector's *name* means nothing.** The name is a label typed when the connector was added; the connector resolves to the live console, which serves whatever was last deployed. Read the version Production should serve before believing a label.
- **A host may have both servers, and the workshop's tools are the ones an agent uses.** The console's tools are `pipelex_*` and the workshop's are `mthds_*`, so no name is registered twice, and both servers' instructions tell the model to use the `mthds_*` tools for all method work when both are present and never to mix the two, since each can be signed in to a different organization. A claude.ai Pipelex connector syncs into Claude Code automatically; that is harmless beside this plugin's workshop, and a user who wants a shorter tool list can still turn the connector off for coding sessions (`/mcp` → "Show unused connectors", or a per-project `deniedMcpServers` entry). Never suggest `disableClaudeAiConnectors`: it turns off every connector on the user's Claude account, Gmail and Google Drive included, which an agent needs to fetch a method's inputs and deliver its results.

## Proving what's actually running

Every deployment reports `serverInfo.version` on the MCP handshake, sourced from its own `package.json`: `pipelex-mcp`'s root manifest for the workshop, whether from npm or a checkout, and `pipelex-mcp-console`'s for the console. Read it rather than inferring from config — config says what *should* spawn, the handshake says what *did*. The console answers the handshake only for a signed-in caller, so its probe below proves less.

Local workshop, npm or checkout — swap in the command being verified, `node <absolute>/pipelex-mcp/dist/main.js` for a checkout:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' \
  | npx -y @pipelex/mcp@latest 2>/dev/null | head -c 300
```

Hosted console:

```bash
curl -si -X POST "https://mcp.pipelex.com/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' \
  | grep -i '^HTTP\|^www-authenticate'
```

The local probe needs no API key, because the workshop's handshake precedes auth. **The console probe reads no version**: OAuth is the console's only auth posture, so an unauthenticated `initialize` gets `401` with a `www-authenticate: Bearer … resource_metadata="…/.well-known/oauth-protected-resource"` header, the two lines the probe prints. They prove the console is up and signing callers in, and nothing about which version it runs; only a signed-in connector session reports that. A first-ever `npx` spawn can take ~10s while the cache populates; warm spawns are ~1s, so allow a generous timeout before calling it broken.

The session's own connected server is a separate question from either probe: it was spawned at session start, so it reflects the config as of *then*. A session started by one of the make targets runs the workshop the target named for as long as it lasts; another workshop needs a new session.

## Rules

- Running against another workshop is a make target, never an edit of `targets/defaults.toml`.
- `targets/defaults.toml` is the only file to hand-edit, and only to change what ships or to restore it. Never edit a generated `plugin.json` or a generated `SKILL.md` — `make build` overwrites them.
- Always `make build` then `make check` after touching any `[vars.mcp_server]` field. An edit that skips the build leaves the config and the manifests disagreeing, which is worse than either state alone.
- Never `git add .` or `git add -A` — other sessions may share this checkout. If the user asks to commit a **shipped-default** change, stage the specific files.
- A hand-made switch is never committed. If asked to commit while one is in the tree, stop and offer to restore first.
- Touch only `command`/`args`; leave `env_vars` and `user_config` alone.
- Report versions you have probed, not versions you have inferred. If a probe fails, say it failed rather than falling back to what config claims.
