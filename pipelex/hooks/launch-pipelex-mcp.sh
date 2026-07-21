#!/usr/bin/env bash
# MCP launcher: spawn the local Pipelex workshop server with plugin
# user-config credentials applied.
#
# The Claude Code manifest routes the plugin-declared `pipelex` MCP
# server through this wrapper instead of spawning the workshop command
# directly. Claude Code substitutes each `userConfig` value into a
# PIPELEX_PLUGIN_* variable (see the mcpServers env block in plugin.json);
# the wrapper promotes each one to its real PIPELEX_* name ONLY when
# non-empty, so an unset option never clobbers a value inherited from the
# session environment (terminal launches keep working off the shell env).
# GUI launches (Claude Desktop) carry no shell environment at all — there
# the user-config values are the only credential channel.

set -euo pipefail

if [[ -n "${PIPELEX_PLUGIN_API_KEY:-}" ]]; then
  export PIPELEX_API_KEY="$PIPELEX_PLUGIN_API_KEY"
fi

if [[ -n "${PIPELEX_PLUGIN_BASE_URL:-}" ]]; then
  export PIPELEX_BASE_URL="$PIPELEX_PLUGIN_BASE_URL"
fi

exec npx "-y" "@pipelex/mcp@latest"
