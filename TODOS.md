# TODOS — Dual-MCP: bake the local workshop launcher

Tracker for flipping the plugin-declared `pipelex-mcp` server from the baked hosted URL to the **local workshop launcher** (`npx -y @pipelex/mcp@latest`, stdio), per the revised dual-deployment design. Branch: `feature/Dual-MCP`. Use the checkboxes; update the checkpoint notes at each phase boundary so a fresh session picks up cleanly. The previous tracker (Mistral Vibe stable-hooks migration, completed 2026-07-19) is archived at `wip/vibe-stable-hooks-migration.md`.

## Context (read this on cold start)

**What shipped upstream.** `pipelex-mcp` ships two servers from one capability core (see its `SPEC.md`/`CLAUDE.md`/`README.md`): the hosted **Skybridge console** on Alpic (`https://pipelex-mcp-a3c6a115.alpic.live/mcp`) and the npm-distributed **local workshop** (`@pipelex/mcp`, bin `pipelex-mcp`, stdio; resolves `{ path }` items from disk with cwd containment). Both register identical tool names (`mthds_validate`, `mthds_inputs_template`, the `mthds_run` family) under server key `pipelex`. Since `@pipelex/mcp` 0.5.0 the console is **bring-your-own-key**: it holds no server-side `PIPELEX_API_KEY`; callers supply a per-request `plx_sk_` key (`Authorization: Bearer` header or `?api_key=` on the connector URL), and keyless calls get an instructive `config` no-verdict. The workshop authenticates with `PIPELEX_API_KEY` from its process env — the same export this plugin's hook README already documents.

**Why the flip.** Full rationale: `../pipelex-mcp/wip/plugin-reconciliation.md` §8 (revision 2026-07-21) — read it before changing course. Short version: a plugin bakes a *literal* URL into a shared artifact (no env expansion on Claude Desktop — `docs/decisions.md` amendment 2026-07-16), so there is no channel for a per-user key → under BYOK the baked hosted URL produces verdicts for no one. Meanwhile the builder hosts the plugin actually serves (Claude Code, Codex — terminal, node present, shell env inherited) are exactly where the launcher works, and the workshop was always their *intended* server: submitting local files through the hosted console pays the LLM hand-copy penalty, which no auth mechanism fixes. The flip is therefore **definitive, not a BYOK workaround** — console OAuth (due in weeks) changes only connector-connection prose in the README, zero manifests, zero build mechanics.

## Decisions (settled 2026-07-21; fold into `docs/decisions.md` as dated amendments in Phase 3)

- **Every baked plugin MCP declaration is the local workshop launcher; the hosted console is never a plugin declaration.** Consumers who want the console add it as a connector in their host's own UI (`?api_key=` now; sign-in once console OAuth ships). The old "builder opt-in to local" inverts into this consumer pointer.
- **Launcher: `npx -y @pipelex/mcp@latest`.** The plugin pins nothing (the hosted API stays the compatibility anchor). `@latest` is explicit because bare `npx -y @pipelex/mcp` reuses the cached install without checking for updates; `@latest` re-resolves the dist-tag per spawn. Fallback if V-P4 finds session-start latency unacceptable: pin the exact version and bump it per plugin release.
- **Server key stays `pipelex` in every shape** → flattened tool names unchanged (`mcp__plugin_pipelex_pipelex__<tool>` on Claude Code, `mcp__pipelex__<tool>` on Codex) → skills keep their tool references verbatim.
- **The renderer goes command-only.** `mcp_server_url` is retired, replaced by a `[vars.mcp_server]` command/args block. The url shape is *not* carried speculatively ("don't port dead switches") — it returns the day a consumer-facing target actually wants a baked hosted entry, which is a post-OAuth question.
- **Vibe target unchanged:** no manifest declaration; docs point at manual registration of the launcher.
- **The skills' "No API key is needed on your side" line is retired** — it described the key-holding dev-tunnel server. The workshop uses the caller's `PIPELEX_API_KEY`; the skills surface the `config`-class error `hint` when it's missing or rejected, exactly as they already do for an unreachable server.

## Phase 0 — verifications (record answers inline; probe with hand-edited generated manifests before wiring the build)

- [ ] **V-P1 Claude command-shape manifest.** Hand-edit `pipelex/.claude-plugin/plugin.json` to declare `mcpServers.pipelex` as a stdio command (expected shape `{"type": "stdio", "command": "npx", "args": ["-y", "@pipelex/mcp@latest"]}`; pin the exact accepted shape) and verify via the local-marketplace dogfood loop: server connects at session start, `/mcp` lists it, tools reach the model as `mcp__plugin_pipelex_pipelex__*`, and `PIPELEX_API_KEY` from the launching shell reaches the spawned server (a `mthds_validate` call must produce a verdict, not a `config` no-verdict).
- [ ] **V-P2 Codex command shape.** Same declaration inline in `.codex-plugin/plugin.json` (check whether Codex wants bare `command`+`args` or tolerates a `type` key, as it did for `url`); verify `codex mcp list` shows it, a live call round-trips, env inheritance holds, and a same-named `[mcp_servers.pipelex]` in `~/.codex/config.toml` still outranks the plugin entry (the dev override we document).
- [ ] **V-P3 Claude Desktop failure UX.** Install the marketplace plugin in the Desktop app and record what a non-spawnable command server looks like there (silent skip vs error toast; GUI apps don't inherit shell env, and node may be absent). Decides how loud the Desktop caveat in the README/marketplace listing must be. Not a blocker for the flip — the worst case is a noisy failure the docs explain, against a baseline where the hosted URL couldn't produce verdicts either.
- [ ] **V-P4 `@latest` spawn latency.** Measure session-start cost of the per-spawn dist-tag re-resolution (warm vs cold npx cache, offline behavior). If unacceptable, switch to the pinned-and-bumped fallback and amend Decisions.

**Checkpoint A** — verifications recorded above; the exact manifest shapes for Claude and Codex are pinned; the `@latest` decision confirmed or amended. Hand off with: both shapes, env-inheritance results, the Desktop failure mode, and any surprise that touches the plan below.

## Phase 1 — build mechanics

- [ ] `targets/defaults.toml`: delete `mcp_server_url`; add the `[vars.mcp_server]` block (`command = "npx"`, `args = ["-y", "@pipelex/mcp@latest"]`) with a comment giving the one-line rationale (workshop launcher is definitive; hosted console is a connector path, never baked — key rides `PIPELEX_API_KEY` in the session env) and pointing at doc 5 §8.
- [ ] `scripts/gen_skill_docs.py` (`make_plugin_json`): inject the stdio shape per platform (the V-P1/V-P2 shapes); rewrite the explanatory comment — the literal-URL/env-expansion story becomes the launcher story (env key rides the spawned process; dev override = point `command`/`args` at a local checkout, e.g. `node ../pipelex-mcp/dist/local/main.js`, + `make build` on Claude; same-named `[mcp_servers.pipelex]` config entry on Codex); skip when the target defines no `mcp_server` block (Vibe).
- [ ] Tests: update fixtures in `tests/unit/test_gen_skill_docs.py` (`mcp_server_url` scalar → the `[vars.mcp_server]` block); keep/adapt the "no block → no `mcpServers` key" test.
- [ ] `make build` (regenerates all targets), `make agent-check`, `make agent-test`.

## Phase 2 — skill templates

- [ ] Sweep the MCP-backed skill templates (`pipelex-design`, `pipelex-organize`, `pipelex-edit`, `pipelex-inputs`): retire "No API key is needed on your side — the MCP server authenticates to the API itself"; replace with the workshop reality (the server authenticates with `PIPELEX_API_KEY` from the session env — the same variable the hook documents; a `config`-class error usually means a missing/rejected key or an unreachable API — surface the error's `hint` verbatim and stop).
- [ ] Update the absent-tools STOP wording ("the plugin manifest must point at a running `pipelex-mcp` server") → the manifest *spawns* the local workshop (`npx @pipelex/mcp`), so absence usually means node/npx unavailable or the spawn failed; keep the `/mcp` pointer on Claude.
- [ ] `make build` + `make agent-check` + `make agent-test`.

**Checkpoint B** — manifests bake the launcher on Claude + Codex, skills tell the truth about auth, all checks green. Record: any V-P1/V-P2 surprise that changed the shapes, and one live dogfood round-trip per platform (`mthds_validate` against the published `@pipelex/mcp` with a real key).

## Phase 3 — docs

- [ ] `README.md`: rewrite the MCP-declaration passages per host (Claude Code: automatic workshop spawn, key via the already-documented `PIPELEX_API_KEY`, node already required by the harness; Codex: same + the config.toml override; Vibe: manual launcher registration). Add the **host→server matrix**, the **one-install-one-server rule**, and the **connector-sync warning**, mirrored from `../pipelex-mcp/README.md`. Add the consumer pointer: the hosted console is reached as a connector in the host's UI with `?api_key=plx_sk_...` — flag this as the BYOK-era wording that swaps to "sign in when prompted" at console-OAuth cutover (the only passage that changes then). Update the dev-override/dogfood instructions.
- [ ] `CLAUDE.md`: the Key dependency section (baked launcher, no more dev-tunnel URL) + the template-variables section (`mcp_server_url` → `mcp_server` block).
- [ ] `docs/decisions.md`: dated amendments on the MCP-declaration decisions (inline `mcpServers` location stands; the http-URL shape and the literal-URL amendment stay as history with a superseded note) + a new decision entry importing the Decisions list above, including the definitive-vs-contingent split.
- [ ] `docs/build-targets.md`: variable table row + prose mention (`mcp_server_url` → `mcp_server`).
- [ ] `CHANGELOG.md`: unreleased entry — breaking: the plugin-declared MCP server is now the local workshop launcher (`npx -y @pipelex/mcp@latest`, stdio) on Claude and Codex; the baked hosted URL is gone; the hosted console is a documented connector path.

## Phase 4 — close-out

- [ ] `wip/pr-1-review-notes.md`: resolve the pre-publication release gate — item 1 (dev-tunnel URL in prod installs) is moot: no URL is baked anywhere anymore; item 2 (endpoint auth posture) is resolved by BYOK (the deployed console holds no funded key — keyless `mthds_run` calls spend nothing) plus workshop-on-caller's-key. Record the resolution in the file.
- [ ] Cross-repo companions in `../pipelex-mcp` (separate change there): the README host→server matrix "Claude Code — How to connect" cell gains the marketplace plugin as a connection channel (it spawns the workshop); doc 5 §8 and the wip/README item 6 amendment were written 2026-07-21 alongside this plan.
- [ ] Decide the release: bump the plugin + marketplace versions, and rule on whether the repo/marketplace goes public now that the pr-1 release gate is closed.

**Checkpoint C** — docs merged, gate closed, release decision recorded. State what shipped and what stayed open.

## Open questions

- **Cursor**: docs-only `.cursor/mcp.json` snippet or a real target? Carried from doc 5 §6 — unchanged by the flip; leaning docs-only (the launcher command is one line either way).
- **Vibe's MCP registration mechanics** (URL, command, or none) — carried; blocks nothing here, the Vibe target ships no declaration.
- **V-P3's outcome**: how loud must the Claude Desktop caveat be in the README/marketplace listing?
- **OAuth cutover reminder**: when console OAuth ships, swap the README's `?api_key=` consumer-pointer passage for the sign-in wording. Nothing else in this repo changes.

## Carried over from the previous tracker (archived at `wip/vibe-stable-hooks-migration.md`)

- **`pre_tool` / `post_agent` hook opportunities** — revisit-only; nothing needed today.
- **`mthds-plugins` Vibe support** — deferred 2026-07-19, out of scope.
