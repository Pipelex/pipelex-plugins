# Connecting the Pipelex workshop, and its key

Read this when an MCP-backed skill sends you here: because a Pipelex MCP tool is absent from the session, or because a call returned a `config`-class error about the API key. It says what to tell the user on Claude Code, and nothing more: whether the skill stops there or carries on without the tool is the skill's own rule, which this file changes in neither direction.

## The tool is absent

Tell the user, in one line: *"The Pipelex MCP server isn't connected — the plugin manifest spawns the local workshop (`npx -y @pipelex/mcp@latest`), so its absence usually means `node`/`npx` is unavailable or the spawn failed. Check the plugin's MCP connection (`/mcp`)."*

## Where the key comes from

The server authenticates to the API with **`PIPELEX_API_KEY`** from the **plugin configuration**: the key entered when the plugin was enabled, kept in the OS keychain and handed to the launcher, which exports it for the server. That is the canonical channel — and on Claude Desktop the only one, since a GUI launch carries no shell environment — while a `PIPELEX_API_KEY` exported in your shell is the fallback, read only when the plugin's key field is left empty. So a `config`-class authentication error is answered by setting the key in the plugin's configuration, never by telling the user to export a shell variable.
