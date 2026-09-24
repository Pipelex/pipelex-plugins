#!/usr/bin/env bash
# Codex PostToolUse(apply_patch|Bash) hook: lint, format, and validate .mthds
# files touched by an apply_patch call, or named by absolute path in a patch
# run through the shell that Codex reports as Bash (docs/hooks.md says which
# shell forms it does, and why a relative path there goes unchecked).
#
# Two-layer design: this thin wrapper is the fail-open guard; ALL validation
# logic lives in the vendored check.mjs bundle beside it (built in
# pipelex-sdk-js — see docs/hooks.md), invoked with --platform=codex so it
# parses the apply_patch envelope in tool_input.command (possibly several
# .mthds files per call — outcomes merged, any block wins) and emits Codex's
# block / hookSpecificOutput protocol:
#   1. local lint   (@pipelex/tools-wasm — offline, no credentials) → block on errors
#   2. local format (same engine) → write back in place when changed
#   3. API validate (POST /v1/validate via @pipelex/sdk, allow_signatures)
#      → block on an invalid verdict; non-blocking context on pending signatures
#
# Fail-open posture (Codex, CLI-free): no Node on PATH → the whole
# hook passes silently (exit 0, no block); no PIPELEX_API_KEY / API unreachable
# (including a network-sandboxed Codex session — the in-bundle 10s ceiling
# keeps a blocked call from hanging the hook) → check.mjs skips only the
# validate stage while the local lint/format verdicts still apply. Nothing
# here shells out to plxt or mthds-agent.

set -euo pipefail

# --- Read stdin (PostToolUse JSON with the patch in tool_input.command) once ---
INPUT=$(cat)

# Cheap pre-filter, before spawning a Node process: go on only when a patch
# header line names a .mthds file, which is all check.mjs reads. Every other
# Bash command, one that merely mentions a .mthds file included, ends here.
# The input is JSON, so the header's line ends at an escaped \n.
MTHDS_PATCH_HEADER='\*\*\* (Update File|Add File|Move to):([^"\\]|\\[^n])*\.mthds'
if ! [[ "$INPUT" =~ $MTHDS_PATCH_HEADER ]]; then
  exit 0
fi

# --- Node.js is required to run the bundle; without it, silently pass ---
if ! command -v node &>/dev/null; then
  exit 0
fi

# Resolve the bundle beside this script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK_MJS="$SCRIPT_DIR/check.mjs"

# Missing bundle = broken install — fail open rather than block every patch.
if [[ ! -f "$CHECK_MJS" ]]; then
  echo "[mthds-codex-hook] check.mjs not found beside check-mthds-codex.sh — passing (reinstall the plugin)" >&2
  exit 0
fi

# check.mjs resolves a relative patch path against its working directory,
# which Codex sets to the session's directory. The patch tool applies its
# patch there, so its call keeps that directory. A patch run through the
# shell may have run anywhere (a `workdir` the payload does not carry, a `cd`
# in the script), so any other call runs from this script's directory, which
# holds no .mthds file: a relative path names no file there and goes
# unchecked, rather than checking and reformatting a same-named file in the
# session's directory, while an absolute path is still checked. Quotes inside
# the command are escaped in the JSON, so the command cannot spoof the name.
# A stopgap: the bundle of L-260924-bdb054 reads the payload's cwd instead,
# and removing this once it is vendored is L-260924-dd7bf2.
PATCH_TOOL='"tool_name"[[:space:]]*:[[:space:]]*"apply_patch"'
if ! [[ "$INPUT" =~ $PATCH_TOOL ]]; then
  cd "$SCRIPT_DIR" || exit 0
fi

exec node "$CHECK_MJS" --platform=codex <<<"$INPUT"
