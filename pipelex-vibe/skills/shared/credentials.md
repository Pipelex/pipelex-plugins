# Connecting the Pipelex workshop, and its key

Read this when an MCP-backed skill sends you here: because one of the plugin's `mthds_*` tools is absent from the session, or because a call returned a `config`-class error about the API key. It says what to tell the user on Mistral Vibe, and nothing more: whether the skill stops there or carries on without the tool is the skill's own rule, which this file changes in neither direction.

## The tool is absent

Tell the user, in one line: *"The Pipelex plugin's MCP server isn't connected — on Mistral Vibe the local workshop (`npx -y @pipelex/mcp@latest`) is not auto-spawned: append the `[[mcp_servers]]` entry from `mcp/vibe-mcp.toml` in the `pipelex-vibe` bundle (beside its `skills/` directory) to the end of `~/.vibe/config.toml`, after deleting any `mcp_servers = []` line and any hand-registered `pipelex` entry there, write your `PIPELEX_API_KEY` into its `env` table, then retry."*

The Pipelex connector's `pipelex_*` tools, when the session has them, belong to a different server: their presence does not mean the plugin's server is connected, and they do not stand in for its `mthds_*` tools.

## Where the key comes from

The server authenticates to the API with **`PIPELEX_API_KEY`** from its `env` table in `~/.vibe/config.toml`, never from the session environment: Mistral Vibe passes no shell variables to a stdio MCP server, so an exported key reaches the plugin's validation hook but not the server.

A key the user saved with the pipelex CLI's `pipelex login` does not count: that command writes it to `~/.pipelex/.env`, or to the `.env` of `PIPELEX_HOME` when that is set, a file only pipelex itself loads, when its Python package is imported, so it reaches neither the server nor the hook. Ask the user to give the server a key in that `env` table: a new one from app.pipelex.com, or the `PIPELEX_API_KEY` value in that file, which they copy themselves. Never read that file or print a key yourself.
