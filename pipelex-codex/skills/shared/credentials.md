# Connecting the Pipelex workshop, and its key

Read this when an MCP-backed skill sends you here: because one of the plugin's `mthds_*` tools is absent from the session, or because a call returned a `config`-class error about the API key. It says what to tell the user on Codex, and nothing more: whether the skill stops there or carries on without the tool is the skill's own rule, which this file changes in neither direction.

## The tool is absent

Tell the user, in one line: *"The Pipelex plugin's MCP server isn't connected — the plugin manifest spawns the local workshop (`npx -y @pipelex/mcp@latest`), so its absence usually means `node`/`npx` is unavailable or the spawn failed. Check the plugin's MCP connection."*

The Pipelex connector's `pipelex_*` tools, when the session has them, belong to a different server: their presence does not mean the plugin's server is connected, and they do not stand in for its `mthds_*` tools.

## Where the key comes from

The server authenticates to the API with **`PIPELEX_API_KEY`** from the session environment — the same variable the plugin's validation hook documents.
