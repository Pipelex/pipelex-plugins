# PR #1 review — deferred items

Deferred findings from SWE-agent review of [PR #1](https://github.com/Pipelex/pipelex-plugins/pull/1). Both threads below describe the same root condition — the baked `mcp_server_url` still points at the interim dev tunnel — and resolve together as one pre-publication release gate.

## Release gate: stable MCP endpoint + verified auth posture before going public

**Reporter:** greptile-apps (P1 "Public MCP Policy Is Optional" + P2 "Production Skills Depend On Dev Tunnel")
**Location:** `targets/defaults.toml:21` (`mcp_server_url`)
**Threads:** [P1 thread](https://github.com/Pipelex/pipelex-plugins/pull/1) `PRRT_kwDOTEJdYc6Rh4-F` · [P2 thread](https://github.com/Pipelex/pipelex-plugins/pull/1) `PRRT_kwDOTEJdYc6Rh4_H`

**Summary.** The URL baked into the Claude and Codex manifests is the `pipelex-mcp` Alpic dev tunnel. Two consequences flagged by review, both factually accurate:

1. **No client auth on the endpoint.** The generated declaration carries no authentication, and the MCP server implements none by explicit spec scope (per-user OAuth / bearer extraction out of scope for this increment; the server holds the upstream `PIPELEX_API_KEY` itself). Anyone with the checked-in URL can invoke the tools — including the `mthds_run` family, which spends inference credit if the server's env holds a funded key.
2. **Prod installs on a dev tunnel.** Marketplace installs inherit the tunnel literally (no env override exists on Claude desktop — deliberate, see `docs/decisions.md` amendment 2026-07-16); when the tunnel dies, all four MCP-backed skills stop at setup.

**Why deferred.** This is a known, documented interim state (defaults.toml comment, `docs/decisions.md`, `CLAUDE.md`, CHANGELOG), and the repo is INTERNAL/private with no release — the URL is not in anyone's install yet. The fix lives in deployment/hosting, not in this PR's diff.

**Release gate (hard, before the repo/marketplace goes public):**

- [x] Swap `mcp_server_url` in `targets/defaults.toml` to the stable `pipelex-mcp` production endpoint + `make build`. — RESOLVED by supersession, see below.
- [x] Verify the endpoint's inbound auth/deny posture for the `mthds_run` family — the endpoint must default-deny unauthenticated clients or otherwise gate credit-spending tools. — RESOLVED, see below.

**Interim hardening (optional, now):** confirm the Alpic dev tunnel's server env does not hold a funded `PIPELEX_API_KEY`, so leaked-URL run calls return a `config` no-verdict instead of spending credit.

## Resolution (2026-07-21, `feature/Dual-MCP`)

The Dual-MCP flip (see `TODOS.md` and `docs/decisions.md` "Dual-MCP flip" entry) closes both gate items — the root condition they shared, a baked hosted URL, no longer exists:

1. **No URL is baked anywhere anymore.** `mcp_server_url` is retired from the renderer and `targets/defaults.toml`; every generated manifest now declares the **local workshop launcher** (`npx -y @pipelex/mcp@latest`, stdio). There is no dev tunnel — or any hosted endpoint — in anyone's install, so "prod installs on a dev tunnel" is moot. The hosted console is only ever a connector users add in their host's own UI, never a plugin declaration.
2. **Auth posture is resolved on both servers.** The workshop authenticates with the *caller's* `PIPELEX_API_KEY` from the session env (forwarded by name via `env_vars` on Codex) — no shared credential exists to leak. The hosted console became bring-your-own-key in `@pipelex/mcp` 0.5.0: it holds no server-side `PIPELEX_API_KEY`, so keyless `mthds_run` calls spend nothing and return an instructive `config` no-verdict. The interim-hardening ask (no funded key in the deployed server env) is thereby satisfied structurally, not just operationally.

The pre-publication release gate is **closed**. Going public is now a product decision, not a security one.
