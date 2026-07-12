# Validation hooks

The plugin runs a validation hook against `.mthds` files after every edit, on all three targets. The pipeline shape is identical across platforms; only the wiring and the block/deny vocabulary differ.

## What the hook does (CLIs present)

When the MTHDS CLIs are on `PATH`, each hook runs the same three stages against the edited file:

1. **`plxt lint`** — TOML/schema-level linting. Errors block the edit.
2. **`plxt fmt`** — auto-format the file in place (lint passed). A format failure only warns.
3. **`mthds-agent validate bundle … --allow-signatures --format json --error-format json`** — semantic validation. The hook reads the **structured JSON verdict**, never the exit code or a markdown grep:
   - `is_valid: true` on stdout → **pass** (even when the bundle isn't yet runnable — unimplemented `PipeSignature` placeholders ride the success envelope with a non-blocking `pending_signatures` nudge).
   - `is_valid: false` on stderr, `error_domain` **input** (or unknown/empty → default to block for safety) → **block/deny** with the validation report as the agent-actionable reason.
   - `error_domain` **config** / **runtime** → **do not block**; surface the message to the user (stderr) and the agent (`additionalContext`). This is an environment problem, not a bundle problem — the agent must not edit the file to "fix" it.

`--allow-signatures` keeps in-progress bundles (whose graph still reaches `PipeSignature` headers) from being blocked mid-construction; on a signature-free bundle, lenient ≡ strict. The two-stream `--format json --error-format json` pinning is what lets the machine read hold under any configured runner — see the workspace-root `docs/specs` and `pipelex/cli/agent_cli/CLAUDE.md` §"Output format".

## CLI-free posture (CLIs absent)

This plugin does **not** install or manage the MTHDS CLIs. So when `node`, `plxt`, or `mthds-agent` is **absent**, every hook **passes silently** (`exit 0`, no block, no deny, no install nagging) instead of blocking the edit. This is the one deliberate behavioral difference from `mthds-plugins`, whose hooks block-with-install-hint.

It is a transitional state. The iteration path swaps the CLI invocations for hosted-API / MCP calls; once API/MCP-backed validation lands, the missing-CLI branch disappears entirely and validation no longer depends on a local toolchain.

## Per-platform wiring

| Platform | Config | Script | Event / matcher |
|---|---|---|---|
| Claude Code | `hooks/hooks.json` (bundled, auto-loaded) | `hooks/validate-mthds.sh` | `PostToolUse` over `Write\|Edit`, gated to `*.mthds` |
| Codex | `hooks/codex-hooks.json`, referenced from the manifest `hooks` field | `mthds-agent codex hook` (in mthds-js) | `PostToolUse` over `apply_patch` |
| Mistral Vibe | `hooks/vibe-hooks.toml` | `hooks/validate-mthds-vibe.sh` | `after_tool` over `edit\|write_file` |

Claude and Codex use `hookSpecificOutput.additionalContext`; Vibe uses `hook_specific_output.additional_context`. Claude/Codex "block"; Vibe "deny".

The Codex command is wrapped — `bash -c 'command -v mthds-agent >/dev/null && exec mthds-agent codex hook; exit 0'` — so a missing `mthds-agent` exits cleanly instead of erroring on every `apply_patch`. The validation logic lives in the mthds-js package (versioned with the npm release), not in the plugin.

## The Codex hook — loading and trust (CLI-present environments only)

Verified against **Codex 0.142.5**. The hook engine graduated out of "under development" across 0.139 → 0.142: the `hooks` feature is now `Stage::Stable` and **enabled by default**, so the plugin-bundled hook is discovered from the manifest and loads on its own — there is no `[features] hooks = true` line to set (`codex_hooks` is an honored deprecated alias; set `hooks = false` only to disable). Note that `plugin_hooks` is **not** an alias of `hooks` — it was an independent opt-in for plugin-bundled hooks, removed in Codex 0.134 and ignored since; a stale `plugin_hooks = false` line is a harmless leftover on supported Codex versions but should be removed. The one manual step is trust:

- On first run, **trust** the plugin hook (Codex persists trusted hashes under `[hooks.state]`). For automation, `--dangerously-bypass-hook-trust` bypasses the prompt.

`PostToolUse` officially fires for `apply_patch` edits and MCP tool calls, so the `.mthds`-on-edit hook fires reliably. The standardized block protocol (`{"decision":"block","reason":…}` or exit 2 + stderr) maps cleanly onto the stage-3 domain-based block/context decision model above. See [decisions.md](decisions.md) for the full finding.

## Checks

`scripts/check.py` enforces the Vibe hook artifacts (`check_vibe_target_artifacts`): a Mistral Vibe target must emit `hooks/vibe-hooks.toml` (`after_tool`, matching `edit|write_file`, calling `validate-mthds-vibe.sh`) and an executable `hooks/validate-mthds-vibe.sh`, carry no Claude/Codex plugin manifest, and contain no Claude/Codex hook artifacts. The renderer marks `validate-mthds.sh` and `validate-mthds-vibe.sh` executable, and the freshness check fails if the exec bit is lost.
