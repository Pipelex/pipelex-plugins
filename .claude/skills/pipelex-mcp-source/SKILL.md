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
- every MCP-backed `SKILL.md` across all three targets — their "server isn't connected" line renders `{{ mcp_server.command }} {{ mcp_server.args | join(" ") }}`, so the quoted launcher tracks the config automatically

That fan-out is why a switch is never a one-file edit, and why it shows up as a wide diff. Prose docs (`README.md`, `docs/decisions.md`, `docs/build-targets.md`, `CLAUDE.md`) quote the launcher too, but they describe **what ships** — see "Changing the shipped default" for the only case where they move.

The critical distinction this skill exists to protect: **a dev switch is temporary local state, not a change to the plugin.** It dirties generated files across every target, and a pinned version or an absolute local path is meaningless on anyone else's machine. It must never reach a commit.

## The three sources

All three are stdio — the renderer emits only `command`/`args`, and the hosted console is deliberately not bakeable (see "The hosted console").

| Source | `command` | `args` | Status |
|---|---|---|---|
| `npm-latest` | `npx` | `["-y", "@pipelex/mcp@latest"]` | **What ships.** The committed default. |
| `npm-pinned` | `npx` | `["-y", "@pipelex/mcp@X.Y.Z"]` | Dev only — reproduce a specific released version. |
| `local` | `node` | `["<absolute>/pipelex-mcp/dist/local/main.js"]` | Dev only — test unreleased changes. |

`@latest` is the shipped default on purpose: `npx` re-resolves the dist-tag per spawn, so users track releases with no plugin bump, and `docs/decisions.md` records that pinning buys no offline resilience (npx contacts the registry even for cached exact specs). Pinning here is a **testing tool**, not a release posture. If the user asks to ship a pin, say that it contradicts that recorded decision and ask them to confirm before proceeding — they may have a good reason, but it should be a deliberate reversal with a `docs/decisions.md` amendment, not a side effect of this skill.

## Status — the default action

When the user invokes this skill without naming a target, report current state and stop. Gather in parallel:

1. **Declared source** — read `[vars.mcp_server]` from `targets/defaults.toml`.
2. **npm `latest`** — `npm view @pipelex/mcp dist-tags --json` (and `npm view @pipelex/mcp versions --json` if they need the list of published versions to pin to).
3. **Console live version** — the probe in "Proving what's actually running".
4. **Local checkout** — does `../pipelex-mcp/dist/local/main.js` exist, and is it stale? `find ../pipelex-mcp/src -name '*.ts' -newer ../pipelex-mcp/dist/local/main.js` printing anything means the build lags its sources; offer `make build-local` in `../pipelex-mcp`.
5. **Leaked dev state** — `git diff --stat targets/defaults.toml` and `git status --porcelain pipelex/ pipelex-codex/ pipelex-vibe/`. If the declared source is not `npm-latest`, lead with that: the tree is carrying a dev switch.

Present it as a short table, not prose. The useful signal is usually a *mismatch* — declared source vs what npm serves vs what the local build contains — so state plainly whether they agree, and if the user is on `npm-latest` and npm `latest` matches the console, say there is nothing to bump.

## Switching to a dev source

1. **Confirm the target** with the user if ambiguous. For a pin, validate the version exists (`npm view @pipelex/mcp versions --json`) — a typo'd pin fails at spawn time with a confusing npx error, long after this skill has finished.
2. For `local`, verify `dist/local/main.js` exists and is not stale; run `make build-local` in `../pipelex-mcp` if it is. Use an **absolute** path — the server spawns with the *host's* working directory, not the plugin's, so a relative path resolves somewhere unintended.
3. Edit only `command` and `args` in `targets/defaults.toml` `[vars.mcp_server]`. Leave `env_vars` and every `user_config` table alone — credential delivery is orthogonal to which build gets spawned, and the local workshop needs the same key.
4. Run `make build`, then `make check`.
5. Tell the user to `/reload-plugins` (Claude Code). On Codex add `make codex-refresh` — installed plugins run from a cache copy, so a rebuild alone does not reach the running harness. Vibe registers its server manually, so a switch there is a change the user makes in Vibe's own MCP config; `make build` only updates the launcher string quoted in Vibe's skill prose.
6. **Close with the revert reminder** and name the dirtied paths. This is the step that keeps a dev switch from shipping.

## Restoring the shipped default

Restore `[vars.mcp_server]` to `npx` + `["-y", "@pipelex/mcp@latest"]`, then `make build` and `make check`.

Prefer `git show origin/main:targets/defaults.toml` as the reference for what actually ships rather than assuming — if the shipped default ever moves, that reads the truth instead of a stale literal. Fall back to `HEAD` when `origin/main` is unavailable, and to the literal above if both disagree with it (which would itself mean a dev switch got committed — worth flagging).

Read that reference, but restore by **editing the two fields back**, not by copying the whole file over `targets/defaults.toml`. Concurrent sessions may share this checkout and a whole-file copy silently discards their unrelated edits — including a `user_config` or `env_vars` change someone is mid-way through.

Verify the generated outputs came back clean: `git status --porcelain targets/defaults.toml pipelex/ pipelex-codex/ pipelex-vibe/` should be empty if the switch was the only local change. If it isn't, show what remains rather than assuming it is unrelated.

## Changing the shipped default

Rare, and the only case where prose docs move. This is a real change to the plugin — a new package name, a different launcher command, or a deliberate reversal of the `@latest` posture.

Do the switch steps above, then propagate to the docs that quote the launcher as *current fact*: `README.md`, `docs/decisions.md`, `docs/build-targets.md`, `CLAUDE.md`. Grep for `@pipelex/mcp@` and `npx -y @pipelex` to find them rather than trusting this list.

**Do not rewrite** `CHANGELOG.md`, `TODOS.md`, or anything under `wip/` — those are historical records of what was true at the time, and editing them destroys the record. Add a new `CHANGELOG.md` entry describing the change instead. Amend `docs/decisions.md` where the change contradicts a recorded decision, so the reasoning stays discoverable; this repo treats decisions as durable, so supersede the entry with the new rationale rather than deleting it.

## The hosted console

The console at `https://pipelex-mcp-a3c6a115.alpic.live/mcp` is **read-only from this skill**. It is never baked into the plugin: a plugin manifest is a shared literal artifact with no channel for a per-user key, and the console is bring-your-own-key since `@pipelex/mcp` 0.5.0, so a baked URL produces verdicts for no one. `docs/decisions.md` records this; the renderer has no url shape to emit.

What this skill does for the console: probe it, report the version it serves, and compare against npm `latest`. If it lags, the fix lives in `../pipelex-mcp` (`make deploy`, from a clean `main`) — say so and hand off rather than deploying from here.

Two things worth telling the user when the console comes up:

- **A stale version in a connector's *name* means nothing.** The name is a label typed when the connector was added; the connector resolves to the live console, which serves whatever was last deployed. Probe before believing a label.
- **Connect each host to exactly one Pipelex server.** Both deployments register identical tool names, so a host connected to both gets ambiguous routing and contradictory schemas (the workshop accepts `{ path }`, the console rejects it). A claude.ai Pipelex connector syncs into Claude Code automatically — if this plugin's workshop is running there too, disable the connector for coding sessions (`/mcp` → "Show unused connectors", per-project `deniedMcpServers`, or `disableClaudeAiConnectors: true`).

## Proving what's actually running

Every deployment reports `serverInfo.version` on the MCP handshake, sourced from `package.json`. Read it rather than inferring from config — config says what *should* spawn, the handshake says what *did*.

Local workshop, npm or checkout — swap in the command being verified:

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

Both need no API key — the handshake precedes auth. A first-ever `npx` spawn can take ~10s while the cache populates; warm spawns are ~1s, so allow a generous timeout before calling it broken.

The session's own connected server is a separate question from either probe: it was spawned at session start, so it reflects the config as of *then*. After a switch, the running server is still the old one until the harness reloads — which is why the reload step is not optional.

## Rules

- `targets/defaults.toml` is the only file to hand-edit. Never edit a generated `plugin.json` or a generated `SKILL.md` — `make build` overwrites them.
- Always `make build` then `make check` after touching any `[vars.mcp_server]` field. A switch that skips the build leaves the config and the manifests disagreeing, which is worse than either state alone.
- Never `git add .` or `git add -A` — other sessions may share this checkout. If the user asks to commit a **shipped-default** change, stage the specific files.
- A dev switch is never committed. If asked to commit while one is active, stop and offer to restore first.
- Touch only `command`/`args`; leave `env_vars` and `user_config` alone.
- Report versions you have probed, not versions you have inferred. If a probe fails, say it failed rather than falling back to what config claims.
