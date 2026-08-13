# Changelog

## [Unreleased]

### Added

- **PipeFunc authoring guide**: New shared reference `skills/shared/writing-pipe-funcs.md`, rendered per target, covering the whole surface the skills previously left undocumented — the function contract (`@pipe_func()`, the single `working_memory` parameter, the required return annotation), structure classes as return types (`from structures import <ConceptCode>`, projected by codegen and shipped in the bundle, never hand-written), the working-memory accessors, how to split the Python across files, the libraries the sandbox actually has (standard library plus `pipelex`, `pandas`, `openpyxl`), the no-network rule, why validation cannot catch any of it, and why only a registered method can run its Python.
- **Worked example** under `examples/support-digest/`: a weekly support digest built from three `PipeFunc`, two `PipeLLM`, and one `PipeSequence`, written to the new reference and then validated and executed against the `pipelex` runtime. It ships no `structures.py` — the runtime generates that module, and shipping one would override it — and its README documents the local bootstrap detour and what hosted validation will not catch.
- **Codegen as the structures path**: the guide documents generating `structures.py` through `codegen types --target python-structures` — the `pipelex codegen` CLI, its `build structures` alias, or `POST /v1/codegen` — verified byte-identical across the CLI and the deployed API. It notes that the API route reads `.mthds` only, so it generates for a bundle that already declares PipeFuncs, while the local CLI in `direct` mode cannot.
- **PipeFunc routing in the skills**: `pipelex-design` now treats a `PipeFunc` leaf as an incomplete pipe until its Python is written, `pipelex-edit` keeps the pipe entry and its function in step across renames and concept reshapes, and `pipelex-explain` reads the bundle's `.py` to explain what a `PipeFunc` step does.

### Fixed

- **Stale PipeFunc guidance**: the `PipeFunc` sections in the MTHDS language reference and in `writing-mthds.md` described the local-install registry model and gave `function_name` as a dotted import path; registration names are flat and unqualified, and the Python ships in the bundle. Both now state the real contract and link the new guide.

### Changed

- **Test fixtures derive from `SHARED_TEMPLATES`**: the template-tree and skill-tree fixtures built their shared-file sets by hand, so adding a shared reference broke unrelated tests. They now read the declared list.

## [0.5.0] - 2026-08-01

### Added

- **Behavioral unit tests**: Added `TestPipelexInputsSizeLimitDiscipline` and `TestAdaptiveDesignSkill` in `tests/unit/test_gen_skill_docs.py` to enforce file-fidelity and adaptive-design guardrails across all generated targets (Claude, Codex, Mistral Vibe).

### Changed

- **Complexity-adaptive `pipelex-design`**: Overhauled the design skill to build fully understood, shallow graphs directly into runnable bundles, reserving signature-driven stepwise refinement for deep, uncertain, or staged work. Method re-entry is likewise adaptive — direct edits for shallow regions, reopening to signatures only for nested, cross-module, or complex structural changes. (Breaking)
- **Conditional `pipelex-organize`**: The organize skill now runs only when a construction-shaped layout genuinely needs regrouping, and skips execution when a direct design result is already coherent.
- **Skill routing**: Updated `pipelex-edit` to route structural and contract changes to the adaptive `pipelex-design` flow.
- **Documentation**: Updated `README.md`, `CLAUDE.md`, and `docs/decisions.md` to reflect the complexity-adaptive design architecture, conditional organization, and strict input file-fidelity rules.

### Fixed

- **`pipelex-inputs` stops on storage size-limit failures without altering or substituting the asset.** The skill prevents unauthorized workarounds (compressing, truncating, downsampling, or substituting synthetic data), reports the exact rejection, and leaves the original file, bundle copy, and local-path `inputs.json` unchanged — neither retrying with transformed content nor offering or submitting a run. Unreadable local paths retain their separate absolute-path-only recovery.

## [0.4.0] - 2026-07-30

### Added

- **Local file uploads in `pipelex-inputs`.** A prepare step between assembling `inputs.json` and offering the run calls the new **`mthds_prepare_inputs`** tool, which uploads every file-bearing value (images, documents) to Pipelex storage and rewrites it to a `pipelex-storage://` reference — making local files runnable on the hosted API. The tool is a **required** dependency whenever a file-ish value isn't already `http(s)` or `pipelex-storage://`; an `input_domain` error splits on its `location`, recovering an unresolvable closure (`pipe_ref` / `method_id`) through `mthds_validate` / `mthds_inputs_template` and repairing an asset failure (`inputs`) from the error's own message and hint. Copies in `<output_dir>/inputs/` stay on disk for reference; only the values in `inputs.json` change, and a bare path or URL becomes the canonical `{"url": "…"}` content dict. Local paths are resolved to absolute before submission, since the workshop resolves a path against its own working directory. Preparation is the moment the user's own files leave the machine, so the skill names them and their destination **before** the call rather than only in the report afterwards — interactive mode waits for confirmation, automatic mode states it and proceeds, and a declined upload stops before the call with the inputs left local.
- **Catalog method support in `pipelex-inputs`.** `mthds_validate`, `mthds_inputs_template`, and `mthds_run` now accept a registered method's catalog id (`mt_…`) as `method_id` in place of submitted files, so the skill can prepare inputs for — and offer to run — a method with no local bundle on disk. A by-id call operates on the method's current stored content and requires an API key (the catalog is org-scoped); since methods aren't versioned, a by-id run re-checks the template for drift immediately beforehand rather than spend credit against a changed signature — on **keys and value shapes** both, since a retyped or reshaped input (`Text` → `Number`, a structured concept losing a field) leaves the key set identical while making every saved value stale; the post-prepare `{"url": …}` form of a file input is exempted, so uploading doesn't read as drift. The file-based skills stay submitted-files only.
- **Repo skill `pipelex-mcp-source`** (local tooling, not shipped in the plugin). Inspects and switches which `pipelex-mcp` build the declared MCP server spawns — npm `@latest`, a pinned version, or a local checkout — as a safe, temporary way to test unreleased changes without leaking dev state into commits.

### Changed

- **Breaking: `pipelex-inputs` offers to run local-file inputs.** The `## Offer to run` gate no longer refuses when a file-ish value is a local path — that restriction existed only because the hosted API cannot read local disk, which the prepare step above now solves. The gate is now "preparation succeeded, or had nothing to do" instead of "every file value is already a reachable `https` URL"; the remaining reasons not to offer are unfilled placeholders and a failed preparation.
- **Breaking: every `mthds_inputs_template` call pins `explicit: false`.** `pipelex-mcp` flipped the tool's `explicit` default to `true` (the ceremonial `{concept, content}` envelope per input); `pipelex-inputs`, `pipelex-design`, and `pipelex-edit` now pass the flag explicitly to keep the light shape — bare example values — that their fill strategies, value-shape tables, and examples are written around. Nothing downstream depends on the choice: `mthds_prepare_inputs` and `mthds_run` accept both shapes identically.
- **The MCP-backed skills prefer the `{path}` file form for workspace bundles.** `pipelex-inputs`, `pipelex-design`, `pipelex-edit`, and `pipelex-organize` documented only the inline `{content, uri}` submission, so an agent following them copied every `.mthds` file into every request and diagnostics lost the real path. The skills now lead with an **absolute** `{path}` — the form the local workshop's own server instructions prefer — while inline `{content, uri}` stays documented as the fallback and as the only form the hosted console accepts, since that deployment has no filesystem.
- **Documentation.** `README.md`, `CLAUDE.md`, `docs/decisions.md`, and `docs/build-targets.md` updated for `mthds_prepare_inputs`, the launcher wrapper, and the new decision entries.

### Fixed

- **An empty plugin option no longer shadows a shell-exported credential.** 0.3.1 dropped the `launch-pipelex-mcp.sh` wrapper and injected `${user_config.*}` straight into `PIPELEX_API_KEY`/`PIPELEX_BASE_URL`, on the premise that an empty option would degrade to the keyless fail-open posture. It doesn't: an absent key still sends an *unauthenticated* request, the API answers 401, and the MCP tools surface a `config`-class `PIPELEX_API_KEY — Unauthorized` that the skills' stop-on-`config` discipline turns into a hard stop — fail-open is a property of the validation hook, never of the tools. So an empty option shadowed a working shell key and stopped `pipelex-design`, `pipelex-organize`, `pipelex-edit`, and `pipelex-inputs` with a misleading error, regressing the bug 0.3.0 had fixed one release earlier. The Claude MCP entry spawns the wrapper again (generated by `gen_skill_docs.py`), receiving the options as `PIPELEX_PLUGIN_*` and promoting each to its real name **only when non-empty**. Verified in both directions: empty options with a shell key now produce a normal verdict, and a set option still overrides the session env, which is what makes Claude Desktop work. The non-empty guard is documented as load-bearing in `docs/decisions.md`, `targets/defaults.toml`, and the renderer.

## [0.3.1] - 2026-07-21

### Changed

- **Dropped the `launch-pipelex-mcp.sh` MCP wrapper.** The Claude manifest's MCP entry now spawns the workshop command directly, injecting the `userConfig` values straight into the spawn env as `PIPELEX_API_KEY`/`PIPELEX_BASE_URL` via `${user_config.*}` substitution. The wrapper's non-empty-promotion guard was needless indirection: the workshop already treats empty env values as absent, so an empty option degrades to the keyless fail-open posture. The plugin config dialog is the canonical credential channel; a shell-exported key on terminal launches may be shadowed when the plugin option is left empty.

## [0.3.0] - 2026-07-21

### Added

- **Claude plugin user configuration for API credentials.** The Claude manifest now declares `userConfig` (`api_key` sensitive + `base_url`), so Claude prompts for the Pipelex API key when the plugin is enabled and stores it in the OS keychain — the credential channel that works on Claude Desktop, where GUI-launched apps carry no shell environment and an exported `PIPELEX_API_KEY` never reaches the session (previously the spawned workshop sent unauthenticated requests and surfaced a misleading "Unauthorized — check PIPELEX_API_KEY" error). The MCP entry now spawns a `hooks/launch-pipelex-mcp.sh` wrapper that promotes the injected `${user_config.*}` values to `PIPELEX_API_KEY`/`PIPELEX_BASE_URL` only when non-empty, and the Claude hook wrapper does the same with the delivered `CLAUDE_PLUGIN_OPTION_*` variables — a set option wins over the session environment, an empty one leaves it untouched, and keyless use stays fail-open. Codex (`env_vars` name-forwarding) and Vibe (manual registration) are unchanged.

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
