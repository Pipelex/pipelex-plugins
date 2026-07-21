# Validation hooks

The plugin runs a validation hook against `.mthds` files after every edit, on all three targets — and all three are now **CLI-free**: nothing shells out to `plxt` or `mthds-agent`. The pipeline is identical everywhere (lint → format → validate, same Stage-3 decision model); only the wiring and the block/deny vocabulary differ per harness.

## The wasm+API pipeline (all targets)

Two layers ship in each target's `hooks/`:

- **A thin wrapper script** (`check-mthds.sh` on Claude, `check-mthds-codex.sh` on Codex, `check-mthds-vibe.sh` on Vibe) — fast `.mthds` pre-filter on the stdin JSON, `command -v node` guard (no Node → silent pass), then `exec node check.mjs --platform=<claude|codex|vibe>` with stdin passed through. It is the fail-open guard and the per-platform seam; it contains no validation logic.
- **`check.mjs`** — one vendored, dependency-free ~4 MB ESM bundle shared by all targets (built in `pipelex-sdk-js`, provenance header at the top; the `--platform` flag selects the input parser and the stdout dialect) holding the whole pipeline:
  1. **Local lint** via `@pipelex/tools-wasm` — the same Rust engine as `plxt lint` / `/v1/lint`, compiled to WASM and inlined into the bundle. Fully offline, no credentials. Any diagnostic **blocks** with line/col spans.
  2. **Local format** (same engine) — writes the canonical formatting back in place, exactly like `plxt fmt` did. A format failure only warns on stderr.
  3. **API validate** — `POST /v1/validate` through `@pipelex/sdk` with `allow_signatures: true`, sending the `.mthds` files gathered recursively under the edited file's parent directory (the old `-L "$PARENT_DIR/"` scope; dot-dirs and the runtime's excluded dirs are skipped; capped at 50 files / 2 MiB — on overflow the stage reads as unavailable rather than risking a false block on an under-supplied bundle). The verdict is the **200 body discriminated on `is_valid`**, never the transport:
     - `is_valid: true` → **pass**; unimplemented `PipeSignature` placeholders emit a non-blocking `additionalContext` nudge listing `pending_signatures`.
     - `is_valid: false` → **block**, forwarding the server-rendered `rendered_markdown` verbatim as the reason (falling back to a client-side rendering of `validation_errors[]` with locators).

Note the bundle scope means a broken **sibling** `.mthds` file fails the verdict too — same as the plxt-era `-L` behavior; the block reason names the offending file via its `source` attribution.

Per-platform input handling inside the bundle: Claude reads one file from `tool_input.file_path`; **Codex** parses the `apply_patch` envelope in `tool_input.command` (`*** Update File: / Add File: / Move to:` headers — one patch can touch several `.mthds` files; each runs the full pipeline and the outcomes merge, any block wins); **Vibe** reads the `post_tool` payload (`tool_status: "success"` gate, path from `tool_output.file`/`.path` or `tool_input.file_path`/`.path`, resolved against `cwd`). Output dialects: Claude/Codex `{"decision":"block",…}` + `hookSpecificOutput.additionalContext`; Vibe `{"decision":"deny",…}` + `{"decision":"allow","hook_specific_output":{"additional_context":…}}`.

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

`check.mjs` is a **static hook asset** (`templates/hooks/assets/check.mjs` — copied verbatim by the build, never rendered through Jinja). When the hook source in `pipelex-sdk-js` changes (or its `@pipelex/tools-wasm` npm dependency is bumped):

```bash
make vendor-hook   # npm run build:hook in pipelex-sdk-js + copy into templates/hooks/assets/
make build         # propagate to pipelex/hooks/check.mjs
make check         # freshness + packaging gates
```

`make vendor-hook` accepts a `SDK_JS_DIR=` override for a non-sibling checkout. The wasm engine comes from the published `@pipelex/tools-wasm` npm package; to vendor an unreleased engine build instead, set `PIPELEX_TOOLS_WASM_PATH` to a `vscode-pipelex/js/tools-wasm` checkout (with a `RELEASE=true make tools-wasm` build) before running. The provenance header (SDK version + commit, tools-wasm version + origin) identifies any vendored copy.

## Per-platform wiring

| Platform | Config | Script | Event / matcher |
|---|---|---|---|
| Claude Code | `hooks/hooks.json` (bundled, auto-loaded; 15 s timeout) | `hooks/check-mthds.sh` → `hooks/check.mjs` | `PostToolUse` over `Write\|Edit`, gated to `*.mthds` |
| Codex | `hooks/codex-hooks.json`, referenced from the manifest `hooks` field (15 s timeout) | `hooks/check-mthds-codex.sh` → `hooks/check.mjs --platform=codex` | `PostToolUse` over `apply_patch` |
| Mistral Vibe | `hooks/vibe-hooks.toml` (15 s timeout) | `hooks/check-mthds-vibe.sh` → `hooks/check.mjs --platform=vibe` | `post_tool` over `edit\|write_file` |

The Codex hook command is `${PLUGIN_ROOT}/hooks/check-mthds-codex.sh` — Codex's hook engine substitutes `${PLUGIN_ROOT}` (and honors `${CLAUDE_PLUGIN_ROOT}` for compatibility) with the installed plugin root before spawning; Codex 0.144+ also provides `${PLUGIN_DATA}` / `${CLAUDE_PLUGIN_DATA}` (per-plugin data dir), unused here. A Codex session may run network-sandboxed; the validate stage then reads as unavailable (its in-bundle 10 s ceiling keeps a blocked call from hanging the hook) while lint/format still gate locally.

## The Codex hook — loading and trust

Verified against **Codex 0.142.5**, re-verified — including **in live sessions** — against **Codex 0.144.4** (block with lint diagnostics relayed to the model, format-in-place on pass, silence on non-`.mthds` patches). The hook engine graduated out of "under development" across 0.139 → 0.142: the `hooks` feature is `Stage::Stable` and **enabled by default**, so the plugin-bundled hook is discovered from the manifest and loads on its own — there is no `[features] hooks = true` line to set (`codex_hooks` is an honored deprecated alias, still present in 0.144.4; set `hooks = false` only to disable). Note that `plugin_hooks` is **not** an alias of `hooks` — it was an independent opt-in for plugin-bundled hooks, removed in Codex 0.134 and ignored since (formally `Stage::Removed` in 0.144); a stale `plugin_hooks = false` line is a harmless leftover on supported Codex versions but should be removed. The one manual step is trust:

- On first run, **trust** the plugin hook (Codex persists trusted hashes under `[hooks.state]`). For automation, `--dangerously-bypass-hook-trust` bypasses the prompt.

`PostToolUse` officially fires for `apply_patch` edits and MCP tool calls, so the `.mthds`-on-edit hook fires reliably. The standardized block protocol (`{"decision":"block","reason":…}` or exit 2 + stderr) maps cleanly onto the stage-3 domain-based block/context decision model above. See [decisions.md](decisions.md) for the full finding, including the plugin **cache model** on 0.144.x: installed plugins run from a cache copy, so after `make build` propagate local edits with `make codex-refresh` (an idempotent `codex plugin add`).

Dev-machine note: if the CLI-era `mthds@mthds-plugins` plugin is also installed, both hooks fire on the same `.mthds` edit and Codex concatenates the block reasons — expected coexistence, not a bug.

## The Vibe hook — payload verification

Verified against **Mistral Vibe 2.21.0** (the release that shipped stable hooks): the payload contract was checked in the installed package source (`vibe/core/hooks/models.py`, `agent_loop/_loop.py`, builtin `edit.py` / `write_file.py`), and payloads serialized by Vibe's own `PostToolInvocation.model_dump_json()` were run end-to-end through the shipped `check-mthds-vibe.sh` — deny on lint errors, format write-back in place, silent pass on `tool_status: "failure"` and on valid files, relative paths resolved against the payload `cwd`. Findings, all matching what the bundle expects:

- `hook_event_name` serializes as `"post_tool"`; a successful call sends `tool_status: "success"` (`ToolStatus` is `"success" | "failure" | "cancelled"` — a cancelled tool sends `"cancelled"`, which the extractor's success gate correctly skips).
- Tool names are the snake_cased class names, so file edits are exactly `edit` and `write_file` — the `re:^(edit|write_file)$` matcher is right.
- `tool_output` is the tool result's `model_dump()`: `edit` yields `{file, message, old_string, new_string}` with `file` the **resolved absolute path**; `write_file` yields `{file_path, bytes_written, content}` — `file_path` is *not* in the extractor's `tool_output` fallback chain, so writes resolve through `tool_input.file_path` (present and identical for both tools). Both routes land on the same file.
- Hook commands run via `create_subprocess_shell` inheriting **Vibe's process cwd** (the project dir) — a relative `command` in `hooks.toml` resolves against the project, *not* the `hooks.toml` location. Hence the README instructs wiring the **absolute** script path when copying the generated `vibe-hooks.toml` into `~/.vibe/hooks.toml`.
- Response handling (`hooks/_post_tool.py`): a deny **replaces** `tool_output_text` with our `reason` (plus `additional_context` if present); an allow with `additional_context` **appends** it — matching the dialect the bundle emits.

## Checks

`scripts/check.py` enforces the Vibe hook artifacts (`check_vibe_target_artifacts`): a Mistral Vibe target must emit `hooks/vibe-hooks.toml` (`post_tool`, matching `edit|write_file`, calling `check-mthds-vibe.sh`) and an executable `hooks/check-mthds-vibe.sh`, carry no Claude/Codex plugin manifest, and contain no Claude/Codex hook artifacts (`check.mjs` is a shared asset, allowed everywhere). The renderer marks all three wrapper scripts executable, and the freshness check fails if the exec bit is lost. Static hook assets (`check.mjs`) are declared per platform in `gen_skill_docs.py` (`STATIC_HOOK_ASSETS_BY_PLATFORM`); a missing asset fails the build, and a stale vendored copy in a target fails the freshness check.
