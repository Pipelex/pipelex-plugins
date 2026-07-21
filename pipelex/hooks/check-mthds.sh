#!/usr/bin/env bash
# PostToolUse hook: lint, format, and validate .mthds files after Write/Edit.
#
# Two-layer design: this thin wrapper is the fail-open guard and the
# per-platform seam; ALL validation logic lives in the vendored check.mjs
# bundle beside it (built in pipelex-sdk-js — see docs/hooks.md):
#   1. local lint   (@pipelex/tools-wasm — offline, no credentials) → block on errors
#   2. local format (same engine) → write back in place when changed
#   3. API validate (POST /v1/validate via @pipelex/sdk, allow_signatures)
#      → block on an invalid verdict; non-blocking nudge on pending signatures
#
# Fail-open posture (Claude Code, CLI-free): no Node on PATH → the whole
# hook passes silently (exit 0, no block); no PIPELEX_API_KEY / API unreachable
# → check.mjs skips only the validate stage while the local lint/format
# verdicts still apply. Nothing here shells out to plxt or mthds-agent.

set -euo pipefail

# --- Read stdin (PostToolUse JSON) once; re-fed to check.mjs below ---
INPUT=$(cat)

# Fast pre-filter: this hook only cares about .mthds files. Exit silently for
# everything else — no Node process spawned for unrelated edits.
if ! [[ "$INPUT" =~ \"file_path\"[[:space:]]*:[[:space:]]*\"[^\"]*\.mthds\" ]]; then
  exit 0
fi

# --- Node.js is required to run the bundle; without it, silently pass ---
if ! command -v node &>/dev/null; then
  exit 0
fi

# Plugin user-config credentials: Claude Code exports each `userConfig`
# value to hook processes as CLAUDE_PLUGIN_OPTION_<KEY>. Promote them to the
# real PIPELEX_* variables when non-empty — GUI launches (Claude Desktop)
# carry no shell environment, so these are the only credential channel there.
# A set option wins over inherited session env (same precedence as the MCP
# launcher); an empty one leaves the session env untouched.
if [[ -n "${CLAUDE_PLUGIN_OPTION_API_KEY:-}" ]]; then
  export PIPELEX_API_KEY="$CLAUDE_PLUGIN_OPTION_API_KEY"
fi
if [[ -n "${CLAUDE_PLUGIN_OPTION_BASE_URL:-}" ]]; then
  export PIPELEX_BASE_URL="$CLAUDE_PLUGIN_OPTION_BASE_URL"
fi

# Resolve the bundle beside this script (works with or without
# CLAUDE_PLUGIN_ROOT in the environment).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK_MJS="$SCRIPT_DIR/check.mjs"

# Missing bundle = broken install — fail open rather than block every edit.
if [[ ! -f "$CHECK_MJS" ]]; then
  echo "[mthds-hook] check.mjs not found beside check-mthds.sh — passing (reinstall the plugin)" >&2
  exit 0
fi

exec node "$CHECK_MJS" <<<"$INPUT"
