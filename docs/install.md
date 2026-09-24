# Install the plugin, agent by agent

The README's quick start installs the Pipelex plugin in Claude Code and Codex in two commands. This page holds the rest: which Pipelex product each app takes, each agent's key and what the plugin starts there, the whole procedure for Mistral Vibe, and the Pipelex MCP that chatbots take instead.

## Which app takes what

An agent takes the Pipelex plugin, which builds and runs methods. A chatbot takes the Pipelex MCP, which runs the methods saved in your Pipelex account. An app takes one of the two, never both.

| App | Takes | How to connect |
|---|---|---|
| Claude Code, in the terminal, your editor or the Claude desktop app | The Pipelex plugin | [Claude Code](#claude-code) |
| Codex, in the terminal or the ChatGPT desktop app | The Pipelex plugin | [Codex](#codex) |
| Mistral Vibe | The Pipelex plugin | [Mistral Vibe](#mistral-vibe) |
| ChatGPT | The Pipelex MCP | Apps directory, or [by its address](#the-pipelex-mcp-for-chatbots) |
| Claude chat, on the web, on mobile and in the desktop app | The Pipelex MCP | **Add custom connector**, [by its address](#the-pipelex-mcp-for-chatbots) |

In every agent, the plugin needs Node.js on your `PATH`: the hook runs on it, and the agent starts the Pipelex tools through `npx`. The Pipelex MCP needs nothing on your machine.

Cursor takes no plugin. Registering the Pipelex tools there by hand is described in the [`pipelex-mcp` developer reference](https://github.com/Pipelex/pipelex-mcp#local-workshop-install--register).

### One app, one Pipelex product

The plugin's tools and the Pipelex MCP register the same tool names. An app connected to both has two tools under each name with contradictory schemas: the plugin's tools accept a `{ path }` to a file on disk, and the Pipelex MCP refuses one. Nothing guarantees which of the two the model calls.

You can reach that state without choosing it. **Claude Code loads what you have added to your Claude account**, so the Pipelex MCP you added on claude.ai reaches your Claude Code sessions beside the plugin. Turn it off for coding sessions in one of these places:

- In Claude Code, run `/mcp` and turn off the Pipelex entry. An entry you have not signed in to is collapsed behind the **Show unused connectors** row.
- For one project, list it under `deniedMcpServers` in `.claude/settings.json`.
- For every project, set `disableClaudeAiConnectors: true` in your user settings.

## Claude Code

```bash
claude plugin marketplace add Pipelex/pipelex-plugins
claude plugin install pipelex@pipelex-plugins
```

**The key.** When you enable the plugin, Claude Code opens the plugin configuration dialog and asks for an API key, which it stores in your OS keychain. Create the key in your console at [app.pipelex.com](https://app.pipelex.com). The dialog's optional base URL field is for a deployment other than the hosted API, which it defaults to. Both values reach the hook and the Pipelex tools.

Your session environment is the fallback:

```bash
export PIPELEX_API_KEY=plx_sk_...     # the plugin configuration dialog is preferred
```

`PIPELEX_BASE_URL` sets the base URL the same way and defaults to `https://api.pipelex.com`. A value set in the dialog wins over the environment, and an empty field leaves the environment in charge.

**Claude Code in the Claude desktop app.** An app launched from the desktop carries no shell environment, so when the plugin runs in Claude Code inside the Claude desktop app, an `export` in your shell profile never reaches it: the plugin configuration dialog is the only way the key gets there. Where Node.js is not on the desktop app's `PATH`, the plugin's tools cannot start; add the Pipelex MCP instead, [by its address](#the-pipelex-mcp-for-chatbots), and sign in.

**What loads.** The hook loads with the plugin and needs Node.js on your `PATH`: it lints and formats every `.mthds` edit on your machine, offline, and validates the whole method on the Pipelex API when a key is set. Claude Code starts the Pipelex tools at the beginning of each session, through `npx` and with the same key, so they need Node.js on your `PATH` too. Without a key the tools still connect, and every call that needs the API answers with how to set one. The skills that need the tools (`pipelex-design`, `pipelex-organize`, `pipelex-edit`, `pipelex-inputs`, `pipelex-run`, `pipelex-catalog` and `pipelex-integrate`) stop with a setup instruction when the tools are absent.

## Codex

```bash
codex plugin marketplace add Pipelex/pipelex-plugins
export PIPELEX_API_KEY=plx_sk_...     # create one in your console at app.pipelex.com
```

Restart Codex, run `/plugins` to install `pipelex`, and trust the plugin hook on first run. Requires Codex 0.141 or later. The hook and the Pipelex tools need Node.js on your `PATH`.

**The hook.** The `hooks` feature is stable and on by default from Codex 0.141, so there is nothing to enable. Codex asks you to trust the plugin hook on first run and keeps the trusted hashes under `[hooks.state]`. The hook lints and formats locally and validates on the Pipelex API when `PIPELEX_API_KEY` is set; a network-sandboxed session skips the validation. See [the validation hook](hooks.md).

**The Pipelex tools.** Codex starts them on its own. They reach the model as `mcp__pipelex__mthds_validate`, `mcp__pipelex__mthds_inputs_template` and so on, and `codex mcp list` shows the `pipelex` entry. Codex starts an MCP server with a minimal environment and does not pass your shell's through, so the plugin forwards `PIPELEX_API_KEY` and `PIPELEX_BASE_URL` by name: export them in the shell you start Codex from, as for the hook.

**Overriding the plugin's entry.** An entry of the same name in `~/.codex/config.toml` outranks the one the plugin declares. Use it to write the key into Codex's configuration rather than your shell, or to run the tools from a local build of [`pipelex-mcp`](https://github.com/Pipelex/pipelex-mcp):

```toml
# ~/.codex/config.toml
[mcp_servers.pipelex]
command = "node"
args = ["/path/to/pipelex-mcp/dist/local/main.js"]   # e.g. a local checkout

[mcp_servers.pipelex.env]
PIPELEX_API_KEY = "plx_sk_..."
```

The same override works for one invocation: `codex -c 'mcp_servers.pipelex.command="node"' …`.

## Mistral Vibe

Mistral Vibe has no plugin marketplace, so it loads the plugin from a clone of this repository. Requires Mistral Vibe 2.21.0 or later, whose stable hooks API runs `post_tool` hooks with no opt-in flag. The hook and the Pipelex tools need Node.js on your `PATH`.

```bash
git clone https://github.com/Pipelex/pipelex-plugins.git
```

The paths below are under the clone's `pipelex-vibe/` directory. To take a new release of the plugin, pull the clone.

### The skills

Vibe loads skills through `skill_paths`. In `~/.vibe/config.toml`:

```toml
skill_paths = ["/absolute/path/to/pipelex-plugins/pipelex-vibe/skills"]
```

### The hook

Wire the generated hook from `pipelex-vibe/hooks/vibe-hooks.toml` into `~/.vibe/hooks.toml`, or into a trusted project's `.vibe/hooks.toml`, where an entry overrides a user-level entry of the same `name`. Vibe runs a hook's command from the project directory, so a relative path resolves against the project rather than against `hooks.toml`: set the command to the script's absolute path.

```toml
[[hooks]]
name = "check-mthds"
type = "post_tool"
match = "re:^(edit|write_file)$"
command = "/absolute/path/to/pipelex-plugins/pipelex-vibe/hooks/check-mthds-vibe.sh"
timeout = 15.0
strict = false
description = "Validate .mthds files after Vibe file edits."
```

The hook reads your shell's environment, so export `PIPELEX_API_KEY` there for its validation.

### The Pipelex tools

Vibe has no plugin manifest, so the plugin ships the tools' entry as a config fragment, `pipelex-vibe/mcp/vibe-mcp.toml`. Install it in `~/.vibe/config.toml`, or in `$VIBE_HOME/config.toml` when you set `VIBE_HOME`:

1. Delete the `mcp_servers = []` line that Vibe writes into a new config.
2. Delete any `pipelex` server you registered by hand.
3. Append the fragment's `[[mcp_servers]]` entry to the end of the file.
4. Write your key into its `env` table.

```toml
[[mcp_servers]]
name = "pipelex"
transport = "stdio"
command = "npx"
args = ["-y", "@pipelex/mcp@latest"]
startup_timeout_sec = 60.0

[mcp_servers.env]
PIPELEX_API_KEY = "plx_sk_..."
PIPELEX_BASE_URL = ""                # optional — empty means the hosted API
```

Why each step matters:

- **The key has to be written there.** Vibe starts an MCP server with a minimal environment and expands no variables in its config, so a `PIPELEX_API_KEY` exported in your shell never reaches the tools. The hook does read your shell, so keep exporting the key there as well. Add any other variable `npx` needs to the same table, such as `HTTPS_PROXY` behind a proxy.
- **Both deletions matter**, because either leftover stops Vibe from starting: TOML cannot add a `[[mcp_servers]]` table after `mcp_servers = []`, and Vibe refuses two servers of the same name.
- **The entry goes at the end** because a TOML table header claims every plain setting below it. Pasted above `skill_paths`, the `[mcp_servers.env]` header would turn that setting into an environment variable of the tools.
- **Vibe records its whole configuration in every session log** under `~/.vibe/logs/session/`, this `env` table included, so redact the key before you share a session log.
- **The raised `startup_timeout_sec`** covers the first `npx` start, which fills the npm cache and outlasts Vibe's 10-second default.
- **Keep the name `pipelex`**, so the tools reach the model as `pipelex_mthds_validate`, `pipelex_mthds_inputs_template` and so on.

The skills that need the tools stop with a setup instruction when the tools are absent.

## The Pipelex MCP, for chatbots

A chatbot takes the Pipelex MCP rather than the plugin. Add it in the chatbot's settings by its address, which in Claude is **Add custom connector**, then sign in with your Pipelex account when asked. There is no key to paste.

```
https://mcp.pipelex.com/mcp
```

The sign-in is OAuth, and the chatbot drives it, including the choice of the organization you work in. The Pipelex MCP holds no key of its own and has no keyless mode: every call runs on your signed-in session, so the methods you see and the runs you spend are your own. When a session expires or is revoked, calls come back as a `config` no-verdict telling you to reconnect and sign in again.

> **Upgrading from an `?api_key=` address.** The Pipelex MCP stopped taking an API key in its 0.12.0 release. An entry still registered with `?api_key=plx_sk_...` in its address, or with an `Authorization: Bearer plx_sk_...` header, no longer connects at all: remove it, add it again by the plain address above, and revoke in your console at [app.pipelex.com](https://app.pipelex.com) the key it carried, since a key that sat in an address may have reached browser history, copied links and proxy logs. ChatGPT keeps the configuration it read when the entry was added, so adding it again is the only way through there.
