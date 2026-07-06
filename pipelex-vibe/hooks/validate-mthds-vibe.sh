#!/usr/bin/env bash
# Mistral Vibe after_tool hook: lint, format, and validate .mthds files after
# edit/write_file tool use. Reads AfterToolInvocation JSON on stdin.
# Emits Vibe hook JSON: decision/reason plus hook_specific_output.additional_context.
# CLI-free posture: passes silently (allow, no deny) when node / plxt / mthds-agent
# are absent — this plugin does not manage CLI installation, so a missing toolchain
# no-ops instead of denying every edit. When the CLIs ARE present the full pipeline runs.

set -euo pipefail

INPUT=$(cat)

# Cheap pre-filter: ignore tool calls unrelated to .mthds files before requiring
# Node.js or the MTHDS toolchain.
if ! [[ "$INPUT" =~ \.mthds ]]; then
  exit 0
fi

# Node.js is required for JSON parsing; without it, silently pass (CLI-free posture).
if ! command -v node &>/dev/null; then
  exit 0
fi

# Extract a value from JSON. $1=json_string, $2=trusted JS expression using `d`.
_jv() { node -e "let d;try{d=JSON.parse(process.argv[1])}catch{d=null};const r=d?($2):undefined;process.stdout.write(r==null?'':String(r))" "$1"; }

_deny() {
  node -e "process.stdout.write(JSON.stringify({decision:'deny',reason:process.argv[1]})+'\n')" "$1" \
    || printf '{"decision":"deny","reason":"Hook error: could not format denial reason"}\n'
}

_context() {
  node -e '
    process.stdout.write(JSON.stringify({
      decision: "allow",
      hook_specific_output: { additional_context: process.argv[1] }
    }) + "\n");
  ' "$1" || true
}

STATUS=$(_jv "$INPUT" "d.tool_status") || STATUS=""
if [[ "$STATUS" != "success" ]]; then
  exit 0
fi

RAW_FILE_PATH=$(_jv "$INPUT" "d.tool_output?.file || d.tool_output?.path || d.tool_input?.file_path || d.tool_input?.path") || {
  _deny "Failed to parse Vibe hook input JSON (Node.js error)"
  exit 0
}

if [[ -z "$RAW_FILE_PATH" ]]; then
  exit 0
fi

CWD=$(_jv "$INPUT" "d.cwd || process.cwd()") || CWD="$PWD"
FILE_PATH=$(node -e '
  const path = require("path");
  const raw = process.argv[1];
  const cwd = process.argv[2] || process.cwd();
  process.stdout.write(path.resolve(cwd, raw));
' "$RAW_FILE_PATH" "$CWD") || {
  _deny "Failed to resolve edited file path: $RAW_FILE_PATH"
  exit 0
}

if [[ -z "$FILE_PATH" || "$FILE_PATH" != *.mthds || ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# plxt and mthds-agent required; without them, silently pass (CLI-free posture:
# this plugin does not install or manage the mthds CLIs). When API/MCP-backed
# validation lands, this branch disappears entirely.
if ! command -v plxt &>/dev/null || ! command -v mthds-agent &>/dev/null; then
  exit 0
fi

TMPOUT=$(mktemp)
TMPERR=$(mktemp)
trap 'rm -f "$TMPOUT" "$TMPERR"' EXIT

LINT_EXIT=0
plxt lint --quiet "$FILE_PATH" >"$TMPOUT" 2>"$TMPERR" || LINT_EXIT=$?
if [[ "$LINT_EXIT" -ne 0 ]]; then
  LINT_OUTPUT=$(cat "$TMPERR")
  [[ -z "$LINT_OUTPUT" ]] && LINT_OUTPUT=$(cat "$TMPOUT")
  [[ -z "$LINT_OUTPUT" ]] && LINT_OUTPUT="lint exited with code $LINT_EXIT (no output)"
  _deny "TOML/schema lint errors in $FILE_PATH:
$LINT_OUTPUT"
  exit 0
fi

FMT_EXIT=0
plxt fmt "$FILE_PATH" >"$TMPOUT" 2>"$TMPERR" || FMT_EXIT=$?
if [[ "$FMT_EXIT" -ne 0 ]]; then
  FMT_ERR=$(cat "$TMPERR")
  printf '[mthds-vibe-hook] Warning: plxt fmt failed (exit %s): %s\n' "$FMT_EXIT" "${FMT_ERR:-no output}" >&2
fi

PARENT_DIR=$(dirname "$FILE_PATH")

EXIT_CODE=0
mthds-agent validate bundle "$FILE_PATH" -L "$PARENT_DIR/" --allow-signatures --format json --error-format json >"$TMPOUT" 2>"$TMPERR" || EXIT_CODE=$?

if [[ "$(_jv "$(cat "$TMPOUT")" "d.is_valid === true ? 'y' : ''")" == "y" ]]; then
  PENDING=$(_jv "$(cat "$TMPOUT")" "Array.isArray(d.pending_signatures)?d.pending_signatures.join(', '):''") || PENDING=""
  if [[ -n "$PENDING" ]]; then
    _context "Bundle is valid but not yet runnable. Signatures still unimplemented (PipeSignature placeholders): $PENDING. They mock their output on dry-run; implement them before running the method for real."
  fi
  exit 0
fi

if [[ "$EXIT_CODE" -eq 0 ]]; then
  _deny "Validation failed for $FILE_PATH (mthds-agent exited 0 with no structured success envelope - is_valid:true not found on stdout; if this persists, upgrade mthds-agent)"
  exit 0
fi

ERR_JSON=$(cat "$TMPERR")

if [[ -z "$(_jv "$ERR_JSON" "(d.error === true || d.is_valid === false) ? 'y' : ''")" ]]; then
  _deny "Validation failed for $FILE_PATH (mthds-agent exited $EXIT_CODE with no structured error envelope)"
  exit 0
fi

DOMAIN=$(_jv "$ERR_JSON" "(d.error_domain ?? '').trim()") || DOMAIN=""

case "$DOMAIN" in
  config|runtime)
    MSG=$(_jv "$ERR_JSON" "d.message || '(no message)'") || MSG="(no message)"
    printf '[mthds-vibe-hook] Validation warning (domain=%s) for %s: %s\n' "$DOMAIN" "$FILE_PATH" "$MSG" >&2
    CONTEXT=$(node -e '
      let env; try { env = JSON.parse(process.argv[1]); } catch { env = {}; }
      const file = process.argv[2];
      const domain = process.argv[3];
      const MAX = 9500;
      const body = String(env.message || "(no message)");
      const trimmed = body.length > MAX
        ? body.slice(0, MAX) + "\n\n[truncated, " + (body.length - MAX) + " chars omitted]"
        : body;
      const header = "Validation warning for " + file + " (" + domain + " domain - environment issue, do not edit the file):\n\n";
      process.stdout.write(header + trimmed);
    ' "$ERR_JSON" "$FILE_PATH" "$DOMAIN") || CONTEXT="Validation warning for $FILE_PATH ($DOMAIN domain)"
    _context "$CONTEXT"
    exit 0
    ;;
  *)
    REASON=$(node -e '
      let env; try { env = JSON.parse(process.argv[1]); } catch { env = {}; }
      const file = process.argv[2];
      const lines = ["Validation failed for " + file + ":", "", String(env.message || "Bundle is invalid.")];
      const errs = Array.isArray(env.validation_errors) ? env.validation_errors : [];
      if (errs.length) {
        lines.push("");
        for (const e of errs) {
          const loc = [
            e.pipe_code && ("pipe " + e.pipe_code),
            e.concept_code && ("concept " + e.concept_code),
            e.field_name && ("field " + e.field_name),
            e.source && ("source " + e.source),
          ].filter(Boolean).join(", ");
          lines.push("- [" + (e.category || "error") + "] " + String(e.message || "") + (loc ? " (" + loc + ")" : ""));
        }
      }
      const MAX = 9500;
      const out = lines.join("\n");
      process.stdout.write(out.length > MAX ? out.slice(0, MAX) + "\n\n[truncated, " + (out.length - MAX) + " chars omitted]" : out);
    ' "$ERR_JSON" "$FILE_PATH" 2>/dev/null) || REASON=""
    [[ -z "$REASON" ]] && REASON="Validation failed for $FILE_PATH"
    _deny "$REASON"
    exit 0
    ;;
esac
