# Install the plugin, agent by agent

The README's quick start installs the Pipelex plugin in Claude Code and Codex in two commands. This page holds the rest: which Pipelex product each app takes, the key and where each agent takes it from, what the plugin starts there, the whole procedure for Mistral Vibe, and the Pipelex MCP that chatbots take instead.

## Which app takes what

An agent takes the Pipelex plugin, which builds and runs methods. A chatbot takes the Pipelex MCP, which runs the methods saved in your Pipelex account. An app needs only one of the two, and an agent that has both works too.

| App | Takes | How to connect |
|---|---|---|
| Claude Code, in the terminal, your editor or the Claude desktop app | The Pipelex plugin | [Claude Code](#claude-code) |
| Codex, in the terminal or the ChatGPT desktop app | The Pipelex plugin | [Codex](#codex) |
| Mistral Vibe | The Pipelex plugin | [Mistral Vibe](#mistral-vibe) |
| ChatGPT | The Pipelex MCP | Apps directory, or [by its address](#the-pipelex-mcp-for-chatbots) |
| Claude chat, on the web, on mobile and in the desktop app | The Pipelex MCP | **Add custom connector**, [by its address](#the-pipelex-mcp-for-chatbots) |

In every agent, the plugin needs Node.js on your `PATH`: the hook runs on it, and the agent starts the Pipelex tools through `npx`. The Pipelex MCP needs nothing on your machine.

### The key

One command sets up the key for the Pipelex tools in every agent:

```bash
npx -y @pipelex/mcp@latest login
```

It opens [app.pipelex.com](https://app.pipelex.com) in your browser, creates a key for your account's current organization and saves it in `~/.pipelex/.env`, or in the `.env` of `PIPELEX_HOME` when that is set. On a machine with no browser, `npx -y @pipelex/mcp@latest login --paste` reads a key you created in your console instead. The Pipelex tools read that file afresh on every call, so a key saved while a session runs is used from its next call. The pipelex CLI's `pipelex login` saves to the same file, so a key it saved works too.

The tools take a key from the agent first, and the saved one only when the agent hands them none: a key you give the agent, as its section below describes, wins over the login's. **The hook reads no file.** It validates a method against the API only with a key the agent hands it, and without one it still lints and formats every edit on your machine.

Cursor takes no plugin. Registering the Pipelex tools there by hand is described in [`pipelex-mcp`'s host registration page](https://github.com/Pipelex/pipelex-mcp/blob/main/docs/hosts.md#cursor).

### An agent with both

The plugin's tools and the Pipelex MCP's have different names: the plugin's start with `mthds_`, and the Pipelex MCP's with `pipelex_`. An app connected to both therefore sees two separate sets of tools, never two tools under one name.

You can have both without choosing it. **Claude Code loads what you have added to your Claude account**, so the Pipelex MCP you added on claude.ai reaches your Claude Code sessions beside the plugin. You can leave it there. When both are present, the agent uses the plugin's `mthds_*` tools: the skills call them, they read your files on disk, and both servers' instructions tell the agent to use them for all method work and never to mix the two servers, because each can be signed in to a different organization — the plugin with your API key, the Pipelex MCP with your Pipelex sign-in.

Having both is harmless, but the Pipelex MCP adds nothing a coding session needs and lengthens the agent's tool list, so you can turn it off for coding sessions in one of these places:

- In Claude Code, run `/mcp` and turn off the Pipelex entry. An entry you have not signed in to is collapsed behind the **Show unused connectors** row.
- For one project, list it under `deniedMcpServers` in `.claude/settings.json`.

Avoid `disableClaudeAiConnectors: true` for this. It removes the Pipelex MCP, but also every other connector on your Claude account, such as Gmail, Google Drive and Calendar, and those are what the agent uses to fetch a method's inputs from your mail or files and to deliver its results.

## Claude Code

```bash
claude plugin marketplace add Pipelex/pipelex-plugins
claude plugin install pipelex@pipelex-plugins
```

**The key.** Run the login, [above](#the-key), in a terminal. When you enable the plugin, Claude Code also opens the plugin configuration dialog, which asks for an API key and stores it in your OS keychain: leave the field empty to use the login's key, or fill it to give the plugin a key of its own, which then wins over the login's and reaches the hook too, so the hook validates as well as lints. The dialog's optional base URL field is for a deployment other than the hosted API, which it defaults to.

Your session environment is the last place the plugin looks before the login's file:

```bash
export PIPELEX_API_KEY=plx_sk_...
```

`PIPELEX_BASE_URL` sets the base URL the same way and defaults to `https://api.pipelex.com`. A value set in the dialog wins over the environment, and an empty field leaves the environment in charge.

**Claude Code in the Claude desktop app.** An app launched from the desktop carries no shell environment, so when the plugin runs in Claude Code inside the Claude desktop app, an `export` in your shell profile never reaches it: the tools find the login's key, and the hook validates only with a key in the plugin configuration dialog. Where Node.js is not on the desktop app's `PATH`, the plugin's tools cannot start; add the Pipelex MCP instead, [by its address](#the-pipelex-mcp-for-chatbots), and sign in.

**What loads.** The hook loads with the plugin and needs Node.js on your `PATH`: it lints and formats every `.mthds` edit on your machine, offline, and validates the whole method on the Pipelex API when a key is set. Claude Code starts the Pipelex tools at the beginning of each session, through `npx` and with the same key, so they need Node.js on your `PATH` too. Without a key the tools still connect, and every call that needs the API answers with how to set one. The skills that need the tools (`pipelex-design`, `pipelex-organize`, `pipelex-edit`, `pipelex-inputs`, `pipelex-run`, `pipelex-catalog` and `pipelex-integrate`) stop with a setup instruction when the tools are absent.

## Codex

```bash
codex plugin marketplace add Pipelex/pipelex-plugins
npx -y @pipelex/mcp@latest login     # the key, saved for the Pipelex tools
```

Restart Codex, run `/plugins` to install `pipelex`, then start Codex once more and trust the plugin hook when it asks. Requires Codex 0.141 or later. The hook and the Pipelex tools need Node.js on your `PATH`. For the hook's validation, also export the key in the shell you start Codex from (`export PIPELEX_API_KEY=plx_sk_...`).

**The hook.** The `hooks` feature is stable and on by default from Codex 0.141, so there is nothing to enable. The hook does not run in the session where `/plugins` installs the plugin, although the skills and the Pipelex tools work there at once: Codex asks you to trust it when the next session starts, keeps the trusted hashes under `[hooks.state]`, and runs it on every edit from then on. So start Codex once more after the install and trust the hook before your first method. The hook lints and formats locally and validates on the Pipelex API when `PIPELEX_API_KEY` is exported; a network-sandboxed session skips the validation. See [the validation hook](hooks.md).

**The Pipelex tools.** Codex starts them on its own. They reach the model as `mcp__pipelex__mthds_validate`, `mcp__pipelex__mthds_inputs_template` and so on, and `codex mcp list` shows the `pipelex` entry. Codex starts an MCP server with a minimal environment and does not pass your shell's through, so the plugin forwards `PIPELEX_API_KEY`, `PIPELEX_BASE_URL` and `PIPELEX_HOME` by name. A key exported in the shell you start Codex from wins over the login's; with none, the tools read the login's file, the one in `PIPELEX_HOME` when you set that.

**Overriding the plugin's entry.** An entry of the same name in `~/.codex/config.toml` outranks the one the plugin declares. Use it to write the key into Codex's configuration rather than your shell, or to run the tools from a local build of [`pipelex-mcp`](https://github.com/Pipelex/pipelex-mcp):

```toml
# ~/.codex/config.toml
[mcp_servers.pipelex]
command = "node"
args = ["/path/to/pipelex-mcp/dist/main.js"]   # e.g. a local checkout, built by `make build-local`

[mcp_servers.pipelex.env]
PIPELEX_API_KEY = "plx_sk_..."
```

An entry of your own replaces the plugin's whole, including the names it forwards, so it passes the key on only when it says so: with an `env` table as above, or with `env_vars = ["PIPELEX_API_KEY", "PIPELEX_BASE_URL", "PIPELEX_HOME"]` to keep taking them from your shell. The same override works for one invocation, and needs the names just as much: `codex -c 'mcp_servers.pipelex.command="node"' -c 'mcp_servers.pipelex.args=["/path/to/pipelex-mcp/dist/main.js"]' -c 'mcp_servers.pipelex.env_vars=["PIPELEX_API_KEY", "PIPELEX_BASE_URL", "PIPELEX_HOME"]'`. In a clone of this repository, `make codex-local-mcp` builds a local checkout's workshop and starts Codex that way; see [the development page](development.md#a-local-build-of-pipelex-mcp).

## Mistral Vibe

Mistral Vibe loads the plugin from a clone of this repository, linked into its plugins directory, since it has no marketplace to install from. Requires Mistral Vibe 2.26.1 or later, the release the plugin is built and checked against. The hook and the Pipelex tools need Node.js on your `PATH`.

```bash
git clone https://github.com/Pipelex/pipelex-plugins.git ~/.local/share/pipelex-plugins
mkdir -p "${VIBE_HOME:-$HOME/.vibe}/plugins"
ln -s ~/.local/share/pipelex-plugins/pipelex-vibe "${VIBE_HOME:-$HOME/.vibe}/plugins/pipelex"
npx -y @pipelex/mcp@latest login
```

That brings the skills, which Vibe names after the plugin (`/pipelex:pipelex-design`, `/pipelex:pipelex-run` and so on). `/plugins` lists what a session loads. Vibe reads its plugins when a session starts, so to take a new release, pull the clone, then start a new session or run `/reload-plugins` in an open one. The last line is the login, [above](#the-key).

Two pieces the plugin cannot carry are entries in your own Vibe files, each shipped ready to append: the Pipelex tools and the hook. Keep the link named `pipelex`, since the hook's entry finds its script through it.

### The Pipelex tools

Vibe starts an MCP server that a plugin declares in the plugin's own directory, and the Pipelex tools read and write only inside the directory they start in, so a plugin-declared server would refuse every file of your project. The tools are therefore one entry in your Vibe configuration, which Vibe starts in your project, and the plugin ships that entry as `pipelex-vibe/mcp/vibe-mcp.toml`. Before appending it, open `~/.vibe/config.toml`, or `$VIBE_HOME/config.toml` when `VIBE_HOME` is set, and clear two things: delete the `mcp_servers = []` line that a new configuration holds, or rewrite a list of servers written on one `mcp_servers = [...]` line as `[[mcp_servers]]` tables; and delete any `pipelex` server already there, such as the entry an earlier version of this page had you write. Then append the entry to the end of the file and start a new Vibe session:

```bash
cat ~/.local/share/pipelex-plugins/pipelex-vibe/mcp/vibe-mcp.toml >> "${VIBE_HOME:-$HOME/.vibe}/config.toml"
```

The entry it adds:

```toml
[[mcp_servers]]
name = "pipelex"
transport = "stdio"
command = ["npx"]
args = ["-y", "@pipelex/mcp@latest"]
startup_timeout_sec = 60.0
```

Why each step matters:

- **Both deletions matter**, because either leftover stops Vibe from starting: TOML cannot add a `[[mcp_servers]]` table to an array already written inline, and Vibe refuses two servers of the same name.
- **The entry goes at the end** because a TOML table header claims every plain setting below it. Appended to the end, it stays after every top-level setting.
- **One file is enough.** Vibe merges a trusted project's `.vibe/config.toml` with yours server by server, so the entry reaches every project.
- **There is no key in it.** Vibe hands a stdio server no variable of your shell but `HOME`, and expands no variable in its configuration, so the tools find the login's key through `HOME`. When you set `PIPELEX_HOME`, or need `HTTPS_PROXY` behind a proxy, add an `[mcp_servers.env]` table right below the entry holding it. A `PIPELEX_API_KEY` written there works too, and wins over the login's, but Vibe copies its configuration into its session logs under `~/.vibe/logs/session/`, so the login keeps the key out of them.
- **`command` is a list**, which Vibe never splits, so a launcher path holding a space stays one word.
- **The raised `startup_timeout_sec`** covers the first `npx` start, which fills the npm cache and outlasts Vibe's 10-second default.
- **Keep the name `pipelex`**: it is the name the tools are grouped under.

The skills that need the tools stop with this setup instruction when the tools are absent.

### The hook

Vibe 2.26.1 does not yet run the hooks a plugin declares, so the hook that lints, formats and validates each `.mthds` file Vibe edits is one entry in your hooks file, and the plugin ships that entry as `pipelex-vibe/hooks/vibe-hooks.toml`. First delete any `check-mthds` hook already in that file, such as the entry an earlier version of this page had you write, since Vibe skips a second hook of the same name and would keep running the old one; and delete it from any trusted project's `.vibe/hooks.toml` that page let you put it in, where it overrides the entry in yours. Then append the entry and start a new Vibe session:

```bash
cat ~/.local/share/pipelex-plugins/pipelex-vibe/hooks/vibe-hooks.toml >> "${VIBE_HOME:-$HOME/.vibe}/hooks.toml"
```

The entry it adds:

```toml
[[hooks]]
name = "check-mthds"
type = "post_tool"
match = "re:^(edit|write_file)$"
command = '"${VIBE_HOME:-$HOME/.vibe}/plugins/pipelex/hooks/check-mthds-vibe.sh"'
timeout = 15.0
strict = false
description = "Validate .mthds files after Vibe file edits."
```

Its command names no path of yours: Vibe runs a hook through the shell, which finds the script through the link you made, so a pull of the clone updates the hook with no edit here. The hook runs with Vibe's own environment, so it validates a method against the API only with `PIPELEX_API_KEY` exported in the shell you start Vibe from. Without it, it still lints and formats every edit.

### Leaving the setup of earlier releases

Earlier releases had you make three hand edits instead. Remove the `skill_paths` entry naming `pipelex-vibe/skills`, which loads every skill a second time under its bare name; replace the `check-mthds` hook, which names the script by an absolute path, by the hook's entry above, and delete it from any trusted project's `.vibe/hooks.toml` you put it in, where it would override that entry; and replace the old `pipelex` server, with its `env` table, by the tools' entry above.

## The Pipelex MCP, for chatbots

A chatbot takes the Pipelex MCP rather than the plugin. Add it in the chatbot's settings by its address, which in Claude is **Add custom connector**, then sign in with your Pipelex account when asked. There is no key to paste.

```
https://mcp.pipelex.com/mcp
```

The sign-in is OAuth, and the chatbot drives it, including the choice of the organization you work in. The Pipelex MCP holds no key of its own and has no keyless mode: every call runs on your signed-in session, so the methods you see and the runs you spend are your own. When a session expires or is revoked, calls come back as a `config` no-verdict telling you to reconnect and sign in again.

> **Upgrading from an `?api_key=` address.** The Pipelex MCP stopped taking an API key in its 0.12.0 release. An entry still registered with `?api_key=plx_sk_...` in its address, or with an `Authorization: Bearer plx_sk_...` header, no longer connects at all: remove it, add it again by the plain address above, and revoke in your console at [app.pipelex.com](https://app.pipelex.com) the key it carried, since a key that sat in an address may have reached browser history, copied links and proxy logs. ChatGPT keeps the configuration it read when the entry was added, so adding it again is the only way through there.
