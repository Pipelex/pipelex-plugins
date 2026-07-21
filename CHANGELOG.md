# Changelog

## [0.2.0] - 2026-07-21

### Changed

- **Breaking: the plugin-declared MCP server is now the local workshop launcher.** On Claude Code and Codex the `pipelex` MCP entry spawns `npx -y @pipelex/mcp@latest` over stdio instead of pointing at a baked hosted URL; the baked URL is gone (the `mcp_server_url` build variable is replaced by the `[vars.mcp_server]` command block). The spawned workshop authenticates with `PIPELEX_API_KEY` from the session environment — the same variable the validation hook documents — and on Codex the manifest forwards `PIPELEX_API_KEY`/`PIPELEX_BASE_URL` into the spawn by name (`env_vars`), since Codex whitelist-filters MCP spawn env. The hosted console remains available as a documented connector path in the host's own UI, never as a plugin declaration. The MCP-backed skills now state the workshop auth reality (the "no API key is needed on your side" line is retired) and their absent-tools guidance reflects the spawn model.

- **Breaking (Mistral Vibe): migrated the Vibe hook to the stable hooks API.** The hook type is renamed `after_tool` → `post_tool` (Vibe 2.21.0+ stable hooks; the `enable_experimental_hooks` opt-in flag no longer exists). Vibe users must update their `hooks.toml` copy to the new `type` and drop the obsolete flag from `~/.vibe/config.toml`.

- **`pipelex-design` writing-mthds reference: whole-stuff copies in PipeCompose construct.** The construct section now documents that `{ from = "..." }` accepts a whole input variable, not just a dotted path — a whole native stuff (`Text`, `Number`, `YesNo`, `Date`, or a list of them) converts automatically into a native-typed target field, required or optional — with a worked example. Matches the conversion fixes shipped in pipelex v0.39.2.

## [0.1.0] - 2026-07-17

Initial release — Pipelex plugins (skills + hooks for working with `.mthds` bundles) for Claude Code, Codex, and Mistral Vibe, packaged through the `pipelex-plugins` marketplace. This is the hosted-API / MCP-era generation: no local-CLI dependency and none of the install/upgrade/env-check machinery of its `mthds-plugins` predecessor.

### Added

- **Multi-target build system.** Jinja2 renderer (`scripts/gen_skill_docs.py`) + consistency checks (`scripts/check.py`) render `templates/` against per-target configs in `targets/` (prod, codex, mistral-vibe, and a trimmed `defaults.toml`) into checked-in `pipelex*/` outputs, with unit tests. None of the predecessor's install/upgrade/env-check switches carried over.
- **Marketplace and manifests.** Claude `.claude-plugin/`, Codex `.codex-plugin/` + `packaging/codex-marketplace.json` with its generated discovery copy, and per-target `plugin.json` generation. Version/marketplace consistency enforced by `make check`.
- **Skills** (all rendered across the three targets):
  - `pipelex-explain` — read-and-explain a bundle: identifies components, traces execution flow, presents a plain-language explanation with a text flow diagram. No CLI or MCP dependency.
  - `pipelex-design` — top-down design by stepwise refinement (ported from `mthds-recursive`). Captures a job as one `PipeSignature` and refines one signature at a time; validation via the `mthds_validate` MCP tool, finalize gated on the runnable verdict. Includes an "Editing an existing method" re-entry section for structural/contract changes, and ships the `writing-mthds.md` reference.
  - `pipelex-organize` — regroups a designed bundle into a browsable module layout (`main.mthds` entry point + per-area module files, shared declarations lifted, satisfied headers dropped). Strictly content-preserving: proves the `mthds_validate` verdict is preserved on the in-memory candidate before touching disk. Auto-invoked by `pipelex-design`'s Deliver phase on a runnable verdict.
  - `pipelex-edit` — model-invocable modification entry point for existing bundles. Applies contract-preserving edits (text, model refs, operator settings, mechanical renames) under a baseline-verdict discipline; routes structural/contract changes to `pipelex-design`.
  - `pipelex-inputs` — prepares a method's `inputs.json` (placeholder template, synthetic data, user files, or a mix) via the `mthds_inputs_template` MCP tool, using the light template shape. Closes with an optional offer to run the method through the `mthds_run` tool family when present.
- **CLI-free wasm+API validation hooks** on all targets (Claude/Codex `PostToolUse`, Vibe `after_tool`). A thin fail-open wrapper per target runs the shared vendored `hooks/check.mjs` bundle (built in `pipelex-sdk-js`): lint + format run locally via the inlined `@pipelex/tools-wasm` engine (offline; format writes back in place), and the bundle verdict comes from `POST /v1/validate` through `@pipelex/sdk` when `PIPELEX_API_KEY` is set. Fail-open everywhere — no Node passes the whole hook silently; a missing key / unreachable API skips only the validate stage. `make vendor-hook` re-vendors the bundle; `make check` fails on a stale copy.
- **Plugin-declared MCP server.** Claude and Codex manifests carry an inline `pipelex-mcp` entry (streamable HTTP; tools `mthds_validate`, `mthds_inputs_template`, and the `mthds_run` family) from the `mcp_server_url` variable, baked as a **literal** URL (neither harness expands `${VAR}` in plugin MCP config). Default points at the `pipelex-mcp` Alpic dev tunnel until the stable deploy. Vibe uses documented manual registration.
- **Documentation.** `docs/build-targets.md` (multi-target build), `docs/hooks.md` (validation pipeline, fail-open posture, per-platform wiring, Codex trust note), and `docs/decisions.md`.
- **Repo tooling.** A local `/release` skill that automates cutting a release: `make check`, version lockstep across every `targets/*.toml` + the Claude marketplace, CHANGELOG finalization, `make build`, and a `release/vX.Y.Z` PR to `main`.

Codex specifics verified against 0.144.4 (live sessions): the hook loads on its own (the `hooks` feature is Stable and on by default) and only needs first-run trust; `make codex-refresh` propagates local edits through the plugin cache model.
