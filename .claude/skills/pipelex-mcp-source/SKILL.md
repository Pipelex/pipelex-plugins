---
name: pipelex-mcp-source
description: >
  Inspects and switches which `pipelex-mcp` build the plugin's declared MCP
  server spawns — npm `@latest`, a pinned npm version, or a local
  `../pipelex-mcp` checkout — and reports which version each deployment
  actually serves (npm, the local build, and the hosted Alpic console). Use this
  skill whenever the user says "bump pipelex-mcp", "which MCP version am I
  using", "switch the MCP source", "test against my local pipelex-mcp", "pin the
  MCP version", "point the plugin at the local workshop", "go back to the
  released MCP", "is the console up to date", or mentions the hosted console /
  Alpic deployment / `@pipelex/mcp` npm package in the context of versions. Also
  use it after `pipelex-mcp` ships a release, when an MCP-backed skill
  (`pipelex-design`, `pipelex-organize`, `pipelex-edit`, `pipelex-inputs`)
  behaves unexpectedly and the server version is suspect, or before committing,
  to check that no temporary dev switch leaked into the tree.
---

# pipelex-mcp source switcher

Controls which `pipelex-mcp` build this plugin's declared MCP server spawns, and reports the version every deployment is actually serving.

## The mental model

`targets/defaults.toml` `[vars.mcp_server]` is the **single source of truth**. `make build` fans it out to every generated artifact:

- `pipelex/.claude-plugin/plugin.json` and `pipelex-codex/.codex-plugin/plugin.json` — the `mcpServers.pipelex` entry the harness spawns
- `pipelex-vibe/mcp/vibe-mcp.toml` — the `[[mcp_servers]]` fragment Vibe users copy into `~/.vibe/config.toml`, since Vibe has no manifest
- every MCP-backed `SKILL.md` across all three targets — their "server isn't connected" line renders `{{ mcp_server.command }} {{ mcp_server.args | join(" ") }}`, so the quoted launcher tracks the config automatically

That fan-out is why a switch is never a one-file edit, and why it shows up as a wide diff. Prose docs (`docs/install.md`, `docs/development.md`, `docs/decisions.md`, `docs/build-targets.md`, `CLAUDE.md`) quote the launcher too, but they describe **what ships** — see "Changing the shipped default" for the only case where they move.

The critical distinction this skill exists to protect: **a dev switch is temporary local state, not a change to the plugin.** It dirties generated files across every target, and a pinned version or an absolute local path is meaningless on anyone else's machine. It must never reach a commit.

## The three sources

All three are stdio — the renderer emits only `command`/`args`, and the hosted console is deliberately not bakeable (see "The hosted console").

| Source | `command` | `args` | Status |
|---|---|---|---|
| `npm-latest` | `npx` | `["-y", "@pipelex/mcp@latest"]` | **What ships.** The committed default. |
| `npm-pinned` | `npx` | `["-y", "@pipelex/mcp@X.Y.Z"]` | Dev only — reproduce a specific released version. |
| `local` | `node` | `["<absolute>/pipelex-mcp/packages/workshop/dist/main.js"]` | Dev only — test unreleased changes. |

`pipelex-mcp` is an npm workspace: the workshop is its `packages/workshop` member, and `make build-local`, run at the root of that checkout, bundles it into `packages/workshop/dist/main.js` with the shared capability core in `packages/core` inlined. **The old path, `dist/local/main.js`, predates the workspace split and is never rebuilt.** A checkout that built before the split still carries that file, and `make clean` there no longer removes it, so a switch still pointing at it spawns a stale workshop without any error.

`@latest` is the shipped default on purpose: `npx` re-resolves the dist-tag per spawn, so users track releases with no plugin bump, and `docs/decisions.md` records that pinning buys no offline resilience (npx contacts the registry even for cached exact specs). Pinning here is a **testing tool**, not a release posture. If the user asks to ship a pin, say that it contradicts that recorded decision and ask them to confirm before proceeding — they may have a good reason, but it should be a deliberate reversal with a `docs/decisions.md` amendment, not a side effect of this skill.

## Status — the default action

When the user invokes this skill without naming a target, report current state and stop. Gather in parallel:

1. **Declared source** — read `[vars.mcp_server]` from `targets/defaults.toml`. If its `args` name `dist/local/main.js`, say that this is the pre-split path, which runs a stale build, and offer to switch it to `packages/workshop/dist/main.js`.
2. **npm `latest`** — `npm view @pipelex/mcp dist-tags --json` (and `npm view @pipelex/mcp versions --json` if they need the list of published versions to pin to).
3. **Console live version** — the probe in "Proving what's actually running". The console has a release track of its own, so compare it as "The hosted console" says, never with npm `latest`.
4. **Local checkout version** — `node -p "require('../pipelex-mcp/packages/workshop/package.json').version"`. That manifest is the one npm publishes as `@pipelex/mcp`. Never read the root `package.json`, which carries no version since the workspace split, nor `packages/console/package.json`, which versions the console on a track npm never sees. A version behind npm `latest` means the checkout needs a pull. A version equal to it is the ordinary case on `dev`, since the version moves only at a release: what the checkout has that npm lacks is listed under `## [Unreleased]` in `../pipelex-mcp/packages/workshop/CHANGELOG.md`, and an empty section there means the local source tests nothing new.
5. **Local build** — does `../pipelex-mcp/packages/workshop/dist/main.js` exist, and is it stale? The bundle inlines the capability core, and its handshake reports the version the workshop's manifest had at build time, so it lags whenever either package's sources or that manifest are newer: `find ../pipelex-mcp/packages/core/src ../pipelex-mcp/packages/workshop/src ../pipelex-mcp/packages/workshop/package.json -type f \( -name '*.ts' -o -name package.json \) ! -name '*.test.ts' ! -name '*.e2e.ts' -newer ../pipelex-mcp/packages/workshop/dist/main.js` printing anything means the build lags; offer `make build-local` at the root of `../pipelex-mcp`.
6. **Leaked dev state** — `git diff --stat targets/defaults.toml` and `git status --porcelain pipelex/ pipelex-codex/ pipelex-vibe/`. If the declared source is not `npm-latest`, lead with that: the tree is carrying a dev switch.

Present it as a short table, not prose. The useful signal is usually a *mismatch* — declared source vs what npm serves vs what the local build contains — so state plainly whether they agree, and if the user is on `npm-latest` and the checkout's workshop version equals npm `latest` with nothing under `## [Unreleased]`, say there is nothing to bump.

## Switching to a dev source

1. **Confirm the target** with the user if ambiguous. For a pin, validate the version exists (`npm view @pipelex/mcp versions --json`) — a typo'd pin fails at spawn time with a confusing npx error, long after this skill has finished.
2. For `local`, verify `packages/workshop/dist/main.js` exists and is not stale (Status, step 5); run `make build-local` at the root of `../pipelex-mcp` if it is missing or stale. Use an **absolute** path — the server spawns with the *host's* working directory, not the plugin's, so a relative path resolves somewhere unintended.
3. Edit only `command` and `args` in `targets/defaults.toml` `[vars.mcp_server]`. Leave `env_vars` and every `user_config` table alone — credential delivery is orthogonal to which build gets spawned, and the local workshop needs the same key.
4. Run `make build`, then `make check`.
5. Tell the user to `/reload-plugins` (Claude Code). On Codex add `make codex-refresh` — installed plugins run from a cache copy, so a rebuild alone does not reach the running harness. Vibe has no manifest: `make build` regenerates `pipelex-vibe/mcp/vibe-mcp.toml` and the launcher quoted in Vibe's skill prose, but a running Vibe keeps whatever entry the user copied into `~/.vibe/config.toml` until they replace that entry with the new one. Adding the new entry beside the old one stops Vibe from starting, because Vibe refuses two servers of the same name.
6. **Close with the revert reminder** and name the dirtied paths. This is the step that keeps a dev switch from shipping.

## Restoring the shipped default

Restore `[vars.mcp_server]` to `npx` + `["-y", "@pipelex/mcp@latest"]`, then `make build` and `make check`.

Prefer `git show origin/main:targets/defaults.toml` as the reference for what actually ships rather than assuming — if the shipped default ever moves, that reads the truth instead of a stale literal. Fall back to `HEAD` when `origin/main` is unavailable, and to the literal above if both disagree with it (which would itself mean a dev switch got committed — worth flagging).

Read that reference, but restore by **editing the two fields back**, not by copying the whole file over `targets/defaults.toml`. Concurrent sessions may share this checkout and a whole-file copy silently discards their unrelated edits — including a `user_config` or `env_vars` change someone is mid-way through.

Verify the generated outputs came back clean: `git status --porcelain targets/defaults.toml pipelex/ pipelex-codex/ pipelex-vibe/` should be empty if the switch was the only local change. If it isn't, show what remains rather than assuming it is unrelated.

## Changing the shipped default

Rare, and the only case where prose docs move. This is a real change to the plugin — a new package name, a different launcher command, or a deliberate reversal of the `@latest` posture.

Do the switch steps above, then propagate to the docs that quote the launcher as *current fact*: `docs/install.md`, `docs/development.md`, `docs/decisions.md`, `docs/build-targets.md`, `CLAUDE.md`. Grep for `@pipelex/mcp@` and `npx -y @pipelex` to find them rather than trusting this list.

**Do not rewrite** `CHANGELOG.md`, `TODOS.md`, or anything under `wip/` — those are historical records of what was true at the time, and editing them destroys the record. Add a new `CHANGELOG.md` entry describing the change instead. Amend `docs/decisions.md` where the change contradicts a recorded decision, so the reasoning stays discoverable; this repo treats decisions as durable, so supersede the entry with the new rationale rather than deleting it.

## The hosted console

The console at `https://pipelex-mcp-a3c6a115.alpic.live/mcp` is **read-only from this skill**. It is never baked into the plugin: the plugin's audience is builders editing local files, which only the workshop can read, and the console authenticates each caller by OAuth sign-in that the host drives through its own connector UI (bring-your-own-key was removed in `@pipelex/mcp` 0.12.0), which no shared plugin artifact can carry. `docs/decisions.md` records this; the renderer has no url shape to emit.

What this skill does for the console: probe it, report the version it serves, and compare it with the console's own release track, never with npm `latest`. Up to and including 0.20.0 both servers shipped together at one version; after it, the console is versioned by `packages/console/package.json`, released on `release/console-vX.Y.Z` branches and tagged `console-vX.Y.Z`, so its version and npm's `latest` move independently and a difference between them means nothing. Read what the console should be serving with `pipelex-mcp`'s own script, which knows each track's manifest and falls back to the single root manifest on a commit from before the split: `(cd ../pipelex-mcp && bash .github/scripts/track-version.sh console origin/main)`, after a `git -C ../pipelex-mcp fetch` if `origin/main` may be behind. If the console lags that version, the fix is a console release in `../pipelex-mcp`, whose merge into `main` deploys it — say so and hand off rather than deploying from here.

Two things worth telling the user when the console comes up:

- **A stale version in a connector's *name* means nothing.** The name is a label typed when the connector was added; the connector resolves to the live console, which serves whatever was last deployed. Probe before believing a label.
- **A host may have both servers, and the workshop's tools are the ones an agent uses.** The console's tools are `pipelex_*` and the workshop's are `mthds_*`, so no name is registered twice, and both servers' instructions tell the model to use the `mthds_*` tools for all method work when both are present and never to mix the two, since each can be signed in to a different organization. A claude.ai Pipelex connector syncs into Claude Code automatically; that is harmless beside this plugin's workshop, and a user who wants a shorter tool list can still turn the connector off for coding sessions (`/mcp` → "Show unused connectors", per-project `deniedMcpServers`, or `disableClaudeAiConnectors: true`).

## Proving what's actually running

Every deployment reports `serverInfo.version` on the MCP handshake, sourced from its own package's `package.json`: `packages/workshop/package.json` for the workshop, whether from npm or a checkout, and `packages/console/package.json` for the console. Read it rather than inferring from config — config says what *should* spawn, the handshake says what *did*.

Local workshop, npm or checkout — swap in the command being verified, `node <absolute>/pipelex-mcp/packages/workshop/dist/main.js` for a checkout:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' \
  | npx -y @pipelex/mcp@latest 2>/dev/null | head -c 300
```

Hosted console:

```bash
curl -s -X POST "https://pipelex-mcp-a3c6a115.alpic.live/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' \
  | head -c 300
```

The local probe needs no API key, because the workshop's handshake precedes auth. **The console probe no longer answers keyless**: since console OAuth became its only auth posture, an unauthenticated `initialize` gets `401` with a `www-authenticate: Bearer … resource_metadata="…/.well-known/oauth-protected-resource"` header. That response still proves the console is up and signing callers in, but it carries no `serverInfo.version`; read the console's version from a signed-in connector session instead. A first-ever `npx` spawn can take ~10s while the cache populates; warm spawns are ~1s, so allow a generous timeout before calling it broken.

The session's own connected server is a separate question from either probe: it was spawned at session start, so it reflects the config as of *then*. After a switch, the running server is still the old one until the harness reloads — which is why the reload step is not optional.

## Rules

- `targets/defaults.toml` is the only file to hand-edit. Never edit a generated `plugin.json` or a generated `SKILL.md` — `make build` overwrites them.
- Always `make build` then `make check` after touching any `[vars.mcp_server]` field. A switch that skips the build leaves the config and the manifests disagreeing, which is worse than either state alone.
- Never `git add .` or `git add -A` — other sessions may share this checkout. If the user asks to commit a **shipped-default** change, stage the specific files.
- A dev switch is never committed. If asked to commit while one is active, stop and offer to restore first.
- Touch only `command`/`args`; leave `env_vars` and `user_config` alone.
- Report versions you have probed, not versions you have inferred. If a probe fails, say it failed rather than falling back to what config claims.
