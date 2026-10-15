# Connecting the Pipelex workshop, and its key

Read this when an MCP-backed skill sends you here: because one of the plugin's `mthds_*` tools is absent from the session, or because a call returned a `config`-class error about the API key. It says what to tell the user on Mistral Vibe, and nothing more: whether the skill stops there or carries on without the tool is the skill's own rule, which this file changes in neither direction.

## The tool is absent

Tell the user, in one line: *"The Pipelex plugin's MCP server isn't connected — on Mistral Vibe the plugin cannot start the local workshop (`npx -y @pipelex/mcp@latest`) itself, so it is one entry in your configuration. First, in `~/.vibe/config.toml`, or `$VIBE_HOME/config.toml` when `VIBE_HOME` is set, delete the `mcp_servers = []` line a new configuration holds, or rewrite a list on one `mcp_servers = [...]` line as `[[mcp_servers]]` tables, and delete any `pipelex` server already there, since either leftover stops Mistral Vibe from starting. Then append the plugin's `mcp/vibe-mcp.toml` to the end of that file (`cat "${VIBE_HOME:-$HOME/.vibe}/plugins/pipelex/mcp/vibe-mcp.toml" >> "${VIBE_HOME:-$HOME/.vibe}/config.toml"`) and start a new Mistral Vibe session."*

The Pipelex connector's `pipelex_*` tools, when the session has them, belong to a different server: their presence does not mean the plugin's server is connected, and they do not stand in for its `mthds_*` tools.

## Where the key comes from

The server authenticates to the API with **`PIPELEX_API_KEY`**. It uses the key its host hands it, which on Mistral Vibe is only one written into the `env` table of its `[[mcp_servers]]` entry, since Mistral Vibe passes a stdio MCP server no variable of your shell but `HOME`. When the host hands it none, it reads the key saved in `~/.pipelex/.env`, or in the `.env` of `PIPELEX_HOME` when that variable reaches it, which on Mistral Vibe also takes the entry's `env` table, afresh on every call, so a key saved while the session runs is used from the next call with no restart.

So a `config`-class error about the key is answered by the workshop's login, which the user runs themselves in a terminal: **`npx -y @pipelex/mcp@latest login`** opens the browser on app.pipelex.com, mints a key for the account's current organization and saves it in that file (`--paste` reads one created in the app instead, for a machine with no browser). The pipelex CLI's `pipelex login` saves to the same file, so a key it saved counts too. When the error's hint says the host's own key was refused, the saved one is never consulted until that key is removed or replaced in the entry's `env` table. Never read that file or print a key yourself.

The plugin's validation hook reads `PIPELEX_API_KEY` from Mistral Vibe's environment alone, never from that file, so with only a saved key it still lints and formats each edit but skips validating it against the API: exporting `PIPELEX_API_KEY` in the shell Mistral Vibe starts from restores that stage.
