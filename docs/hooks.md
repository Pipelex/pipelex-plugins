# Validation hooks

The plugin runs a validation hook against `.mthds` files after every edit, on all three targets. The pipeline shape is identical everywhere: lint → format → validate, with block/context decisions mirroring the same Stage-3 model. The **Claude target** now runs the CLI-free wasm+API pipeline (below); Codex and Mistral Vibe still run the transitional CLI pipeline and move over next (see the networked-hook plan in the workspace `wip/hooks/`).

## Claude target — wasm-local lint/format + API-backed validate

Two layers ship in `pipelex/hooks/`:

- **`validate-mthds.sh`** — a thin wrapper: fast `.mthds` pre-filter on the stdin JSON, `command -v node` guard (no Node → silent pass), then `exec node check.mjs` with stdin passed through. It is the fail-open guard and the per-platform seam; it contains no validation logic.
- **`check.mjs`** — a vendored, dependency-free ~4 MB ESM bundle (built in `pipelex-sdk-js`, provenance header at the top) holding the whole pipeline:
  1. **Local lint** via `@pipelex/tools-wasm` — the same Rust engine as `plxt lint` / `/v1/lint`, compiled to WASM and inlined into the bundle. Fully offline, no credentials. Any diagnostic **blocks** with line/col spans.
  2. **Local format** (same engine) — writes the canonical formatting back in place, exactly like `plxt fmt` did. A format failure only warns on stderr.
  3. **API validate** — `POST /v1/validate` through `@pipelex/sdk` with `allow_signatures: true`, sending the `.mthds` files gathered recursively under the edited file's parent directory (the old `-L "$PARENT_DIR/"` scope; dot-dirs and the runtime's excluded dirs are skipped; capped at 50 files / 2 MiB — on overflow the stage reads as unavailable rather than risking a false block on an under-supplied bundle). The verdict is the **200 body discriminated on `is_valid`**, never the transport:
     - `is_valid: true` → **pass**; unimplemented `PipeSignature` placeholders emit a non-blocking `additionalContext` nudge listing `pending_signatures`.
     - `is_valid: false` → **block**, forwarding the server-rendered `rendered_markdown` verbatim as the reason (falling back to a client-side rendering of `validation_errors[]` with locators).

Note the bundle scope means a broken **sibling** `.mthds` file fails the verdict too — same as the plxt-era `-L` behavior; the block reason names the offending file via its `source` attribution.

### Failure posture (fail-open)

| Condition | Behavior |
|---|---|
| Not a `.mthds` edit / unparseable stdin | silent pass (wrapper pre-filter) |
| No `node` on PATH | silent pass (wrapper) |
| `check.mjs` missing beside the wrapper | silent pass + stderr note (broken install) |
| WASM engine fails to load | silent pass (whole hook unavailable) |
| No `PIPELEX_API_KEY` | lint/format verdicts apply; **validate stage skipped silently** |
| API unreachable / timeout (10 s) / any non-2xx | same — local verdicts apply, validate skipped |

A machine consumer branches on the structured verdict, never on transport — an invalid bundle is a produced verdict on a 200; a non-2xx means *no verdict*, which for a write gate degrades to the local stages.

### Environment

- `PIPELEX_API_KEY` — required **for the validate stage only**; lint/format work offline with no key. Without it the hook is a local lint+format gate.
- `PIPELEX_BASE_URL` — optional; defaults to the hosted `https://api.pipelex.com`. Point it at a local `pipelex-api` (`http://localhost:8081`) to validate against your own runner.

**Privacy note:** with a key set, the gathered bundle contents leave the machine on every validate call — something the plxt-era hook never did. Unset `PIPELEX_API_KEY` to keep everything local.

**Schema pinning:** the WASM engine embeds the MTHDS schema frozen at `@pipelex/tools-wasm` build time, so plugin releases are the local schema update cadence; the server-side validate is the authoritative verdict when the two skew.

### Re-vendoring check.mjs

`check.mjs` is a **static hook asset** (`templates/hooks/assets/check.mjs` — copied verbatim by the build, never rendered through Jinja). When the hook source in `pipelex-sdk-js` (or the wasm engine in `vscode-pipelex`) changes:

```bash
make vendor-hook   # RELEASE=true wasm build + npm run build:hook + copy into templates/hooks/assets/
make build         # propagate to pipelex/hooks/check.mjs
make check         # freshness + packaging gates
```

`make vendor-hook` accepts `SDK_JS_DIR=` / `TOOLS_WASM_DIR=` overrides for non-sibling checkouts. The provenance header (SDK + tools-wasm versions and commits) identifies any vendored copy.

## Codex & Mistral Vibe targets — transitional CLI pipeline

These still shell out to the MTHDS CLIs **only when present**: `plxt lint` → `plxt fmt` → `mthds-agent validate bundle … --allow-signatures --format json --error-format json`, reading the structured JSON verdict (`is_valid`, `error_domain`, `validation_errors[]`) — never the exit code. `error_domain` **input** (or unknown) blocks; **config**/**runtime** surface as context without blocking. When `node`, `plxt`, or `mthds-agent` is absent they pass silently — this plugin does not install or manage CLIs.

## Per-platform wiring

| Platform | Config | Script | Event / matcher |
|---|---|---|---|
| Claude Code | `hooks/hooks.json` (bundled, auto-loaded; 15 s timeout) | `hooks/validate-mthds.sh` → `hooks/check.mjs` | `PostToolUse` over `Write\|Edit`, gated to `*.mthds` |
| Codex | `hooks/codex-hooks.json`, referenced from the manifest `hooks` field | `mthds-agent codex hook` (in mthds-js) | `PostToolUse` over `apply_patch` |
| Mistral Vibe | `hooks/vibe-hooks.toml` | `hooks/validate-mthds-vibe.sh` | `after_tool` over `edit\|write_file` |

Claude and Codex use `hookSpecificOutput.additionalContext`; Vibe uses `hook_specific_output.additional_context`. Claude/Codex "block"; Vibe "deny".

The Codex command is wrapped — `bash -c 'command -v mthds-agent >/dev/null && exec mthds-agent codex hook; exit 0'` — so a missing `mthds-agent` exits cleanly instead of erroring on every `apply_patch`. The validation logic lives in the mthds-js package (versioned with the npm release), not in the plugin.

## The Codex hook — loading and trust (CLI-present environments only)

Verified against **Codex 0.142.5**. The hook engine graduated out of "under development" across 0.139 → 0.142: the `hooks` feature is now `Stage::Stable` and **enabled by default**, so the plugin-bundled hook is discovered from the manifest and loads on its own — there is no `[features] hooks = true` line to set (`codex_hooks` is an honored deprecated alias; set `hooks = false` only to disable). Note that `plugin_hooks` is **not** an alias of `hooks` — it was an independent opt-in for plugin-bundled hooks, removed in Codex 0.134 and ignored since; a stale `plugin_hooks = false` line is a harmless leftover on supported Codex versions but should be removed. The one manual step is trust:

- On first run, **trust** the plugin hook (Codex persists trusted hashes under `[hooks.state]`). For automation, `--dangerously-bypass-hook-trust` bypasses the prompt.

`PostToolUse` officially fires for `apply_patch` edits and MCP tool calls, so the `.mthds`-on-edit hook fires reliably. The standardized block protocol (`{"decision":"block","reason":…}` or exit 2 + stderr) maps cleanly onto the stage-3 domain-based block/context decision model above. See [decisions.md](decisions.md) for the full finding.

## Checks

`scripts/check.py` enforces the Vibe hook artifacts (`check_vibe_target_artifacts`): a Mistral Vibe target must emit `hooks/vibe-hooks.toml` (`after_tool`, matching `edit|write_file`, calling `validate-mthds-vibe.sh`) and an executable `hooks/validate-mthds-vibe.sh`, carry no Claude/Codex plugin manifest, and contain no Claude/Codex hook artifacts. The renderer marks `validate-mthds.sh` and `validate-mthds-vibe.sh` executable, and the freshness check fails if the exec bit is lost. Static hook assets (`check.mjs`) are declared per platform in `gen_skill_docs.py` (`STATIC_HOOK_ASSETS_BY_PLATFORM`); a missing asset fails the build, and a stale vendored copy in a target fails the freshness check.
