# Install the plugin, agent by agent

The README's quick start installs the Pipelex plugin in Claude Code and Codex in two commands. This page holds the rest: which Pipelex product each app takes, the key and where each agent takes it from, what the plugin starts there, Claude Code on Windows, the whole procedure for Mistral Vibe, and the Pipelex MCP that chatbots take instead.

## Which app takes what

An agent takes the Pipelex plugin, which builds and runs methods. A chatbot takes the Pipelex MCP, which runs the methods saved in your Pipelex account. An app needs only one of the two, and an agent that has both works too.

| App | Takes | How to connect |
|---|---|---|
| Claude Code, in the terminal, your editor or the Claude desktop app | The Pipelex plugin | [Claude Code](#claude-code) |
| Codex, in the terminal or the ChatGPT desktop app | The Pipelex plugin | [Codex](#codex) |
| Mistral Vibe | The Pipelex plugin | [Mistral Vibe](#mistral-vibe) |
| ChatGPT | The Pipelex MCP | Apps directory, or [by its address](#the-pipelex-mcp-for-chatbots) |
| Claude chat, on the web, on mobile and in the desktop app | The Pipelex MCP | **Add custom connector**, [by its address](#the-pipelex-mcp-for-chatbots) |

In every agent, the plugin needs Node.js 24.14.1 or later on your `PATH`: the hook runs on it, and the agent starts the Pipelex tools through `npx`. The tools, published as `@pipelex/mcp`, declare that version; the hook's own floor, 22.12, is below it. Run `node --version` to see yours. The Pipelex MCP needs nothing on your machine.

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

Requires Claude Code 2.1.139 or later, the first release that runs a hook in the exec form the plugin's hook uses, and Node.js on your `PATH`, on macOS, Linux and Windows alike: Claude Code starts both the hook and the Pipelex tools as `node` running a script of the plugin, with no shell, so neither needs bash. Run `claude --version` to see yours. Windows has [its own section below](#claude-code-on-windows).

**The key.** Run the login, [above](#the-key), in a terminal. When you enable the plugin, Claude Code also opens the plugin configuration dialog, which asks for an API key and stores it in your OS keychain: leave the field empty to use the login's key, or fill it to give the plugin a key of its own, which then wins over the login's and reaches the hook too, so the hook validates as well as lints. The dialog asks for nothing else: the plugin uses the hosted API, `https://api.pipelex.com`.

Your session environment is the last place the plugin looks before the login's file:

```bash
export PIPELEX_API_KEY=plx_sk_...
```

A key set in the dialog wins over the environment, and an empty field leaves the environment in charge.

**Another deployment.** The plugin never asks for the API's address. To reach a deployment other than the hosted API, export `PIPELEX_BASE_URL` the same way; the tools and the hook both read it. Where no shell environment reaches the plugin, run the login with it set, `PIPELEX_BASE_URL=<api origin> PIPELEX_APP_URL=<app origin> npx -y @pipelex/mcp@latest login`, which signs in to that deployment's app, since the login takes its app from `PIPELEX_APP_URL` alone, and saves the API's address beside the key in `~/.pipelex/.env`; with a key created in that deployment's app, `PIPELEX_BASE_URL=<api origin> npx -y @pipelex/mcp@latest login --paste` does the same. Then leave the dialog's key field empty and `PIPELEX_API_KEY` unset: the tools take the file's base URL only together with the file's key. The hook reads neither the file's key nor its address, so it lints and formats there without validating.

**Claude Code in the Claude desktop app.** An app launched from the desktop carries no shell environment, so when the plugin runs in Claude Code inside the Claude desktop app, an `export` in your shell profile never reaches it: the tools find the login's key, and the hook validates only with a key in the plugin configuration dialog, against the hosted API alone. Where Node.js is not on the desktop app's `PATH`, the plugin's tools cannot start; add the Pipelex MCP instead, [by its address](#the-pipelex-mcp-for-chatbots), and sign in.

**What loads.** The hook loads with the plugin and needs Node.js on your `PATH`: it lints and formats every `.mthds` edit on your machine, offline, and validates the whole method on the Pipelex API when a key is set. Claude Code starts the Pipelex tools at the beginning of each session, through Node, which fetches them with `npx`, and with the same key. Without Node.js the hook cannot start, and Claude Code reports a hook error while the edit stands. Without a key the tools still connect, and every call that needs the API answers with how to set one. The skills that need the tools (`pipelex-design`, `pipelex-organize`, `pipelex-edit`, `pipelex-inputs`, `pipelex-run`, `pipelex-catalog` and `pipelex-integrate`) stop with a setup instruction when the tools are absent.

### Claude Code on Windows

The plugin runs in Claude Code on Windows with PowerShell alone, in the terminal and in the Claude desktop app. Claude Code starts the hook and the Pipelex tools as `node` running a script of the plugin, with no shell, so neither needs bash, Git Bash or WSL. Codex and Mistral Vibe on Windows are not covered yet: their hooks are still bash scripts, and their manifests start the Pipelex tools as `npx`, which Windows cannot start without a shell.

**What you need.**

- **Node.js 24.14.1 or later**, from the official installer at [nodejs.org](https://nodejs.org/). The installer puts `node`, `npm` and `npx` on your `PATH`. Open a new PowerShell window afterwards and run `node --version`: a window, an editor or an app started before the install keeps the `PATH` it started with. A Node.js installed with winget, Chocolatey, nvm-windows, Volta or Scoop works the same way: each ships npm beside `node.exe`, which is where the plugin finds `npx`, and puts `node` on the Windows `PATH` that every app starts with. fnm ships npm the same way but puts `node` on the `PATH` only in a terminal whose profile runs `fnm env`, so it serves Claude Code in that terminal and not in the Claude desktop app, which loads no shell profile and needs `node` on the persistent Windows `PATH`.
- **Claude Code 2.1.139 or later.** Run `claude --version` to see yours.
- **git on your `PATH`**, which [Git for Windows](https://git-scm.com/download/win) provides, because Claude Code installs a plugin by cloning its marketplace's repository with git.

**Git Bash is not required.** Whether Claude Code runs the agent's own commands in Git Bash or, when it finds none, in PowerShell, the plugin works the same way: the hook and the tools start with no shell at all, and every command every skill gives the agent runs as written in Windows PowerShell 5.1 and PowerShell 7 as it does in bash, `pipelex-scaffold`'s included: it makes and serves a new method app through the template's npm scripts, with no `make`, and hands every value you give it, a title or an author's name with an apostrophe included, to its scripts in a file rather than on a command line.

**Install from the marketplace.** In PowerShell:

```powershell
claude plugin marketplace add Pipelex/pipelex-plugins
claude plugin install pipelex@pipelex-plugins
npx -y @pipelex/mcp@latest login
```

The last line is the login, [above](#the-key), which saves the key in `%USERPROFILE%\.pipelex\.env`, the Windows spelling of `~/.pipelex/.env`. If PowerShell answers that running scripts is disabled on this system, it picked npm's `npx.ps1`; run `npx.cmd -y @pipelex/mcp@latest login` instead. The plugin's own start of the tools does not go through `npx.ps1`: it runs npm's `npx-cli.js` with the `node` that runs the launcher.

When you enable the plugin, the configuration dialog asks for an API key, as on every system: leave it empty to use the login's key, or fill it so the hook validates as well as lints. In PowerShell, `$env:PIPELEX_API_KEY = "plx_sk_..."` sets the key for the Claude Code you start from that window, as `export` does in bash, and `$env:PIPELEX_BASE_URL` likewise names another deployment.

If you added the marketplace on Windows before this release, run `/plugin marketplace remove pipelex-plugins` in Claude Code and add the marketplace and the plugin again: git does not rewrite a file an update leaves unchanged, so an earlier clone can keep scripts with Windows line endings.

**Install from a clone, for development.** The repository holds the built plugin, `pipelex/`, checked in, so a clone runs as it is, with no build; that matters on Windows, which has no `make` to run `make build`. In a Claude Code session, point the marketplace at the clone, the first line only when the published marketplace is already added:

```
/plugin marketplace remove pipelex-plugins
/plugin marketplace add C:\path\to\pipelex-plugins
/plugin install pipelex@pipelex-plugins
/reload-plugins
```

For one session, without touching your configuration, start Claude Code with the plugin directory instead, in quotes so that a path holding a space stays one argument:

```powershell
claude --plugin-dir "C:\path\to\pipelex-plugins\pipelex"
```

A plugin path holding a space or backslashes reaches the hook and the tools intact, since Claude Code hands it to `node` as one argument. [The development page](development.md#claude-code) has the rest of the loop.

**What a working install looks like.**

1. **The tools connect.** In PowerShell, in your project, `claude mcp list` lists the plugin's server as `plugin:pipelex:pipelex` and reports it connected. The first start takes longer, while `npx` fetches the tools into its cache.
2. **The hook blocks a lint error.** In a session, ask the agent to write this method as `hello.mthds`, whose pipe holds a field no pipe takes:

    ```toml
    domain = "demo"
    description = "Demo"
    main_pipe = "say_hello"

    [pipe.say_hello]
    type = "PipeLLM"
    description = "Say hello"
    output = "Text"
    prompt = "Say hello."
    not_a_field = 3
    ```

    The hook refuses the write with `MTHDS lint errors in` the file's path, naming `not_a_field`, and the agent fixes the file. Once the field is gone, the hook passes the edit and formats the file in place, and with a key in the configuration dialog it also validates the whole method on the Pipelex API.
3. **The key reaches the tools.** Ask the agent to validate `hello.mthds`: it calls `mthds_validate` and reports the verdict, where a missing key would get an answer saying how to set one.

**In the Claude desktop app.** Claude Code in the desktop app starts the hook and the tools the same way, as `node` with no shell, and finds `node` on the `PATH` the desktop app started with: after installing Node.js, quit the desktop app fully and start it again. The desktop app carries no PowerShell window's variables, so a `$env:PIPELEX_API_KEY` never reaches it: the tools read the login's key from `%USERPROFILE%\.pipelex\.env`, and the hook validates only with the key in the plugin configuration dialog.

**WSL.** Inside WSL the plugin behaves as on Linux, with the steps above this section, provided Claude Code runs inside WSL and Node.js 24.14.1 or later is installed inside WSL too: a Node.js installed on Windows does not serve it. Run the login inside WSL as well, since it saves the key in the WSL home, `~/.pipelex/.env`, which is not the Windows one.

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

Mistral Vibe loads the plugin from a clone of this repository, linked into its plugins directory, since it has no marketplace to install from. Requires Mistral Vibe 3.0.4 or later, the first release that runs the hook a plugin ships; the plugin is checked against 3.1.2. Run `vibe --version` to see yours. The hook and the Pipelex tools need Node.js on your `PATH`, and the hook needs `bash`, which macOS and Linux provide.

```bash
git clone https://github.com/Pipelex/pipelex-plugins.git ~/.local/share/pipelex-plugins
mkdir -p "${VIBE_HOME:-$HOME/.vibe}/plugins"
ln -s ~/.local/share/pipelex-plugins/pipelex-vibe "${VIBE_HOME:-$HOME/.vibe}/plugins/pipelex"
npx -y @pipelex/mcp@latest login
```

That brings the skills, which Vibe names after the plugin (`/pipelex:pipelex-design`, `/pipelex:pipelex-run` and so on), and [the hook](#the-hook). `/plugins` lists what a session loads. The last line is the login, [above](#the-key). Keep the link named `pipelex`, the plugin's own name.

**A pull reaches the next session, never the one running.** Each session runs from a read-only copy of the plugin that Vibe makes when the session starts, which lets a session outlive an upgrade. To take a new release, pull the clone, then start a new session or run `/reload-plugins` in an open one.

One piece the plugin cannot carry is an entry in your own Vibe configuration, shipped ready to append: the Pipelex tools.

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
- **There is no key in it.** Vibe hands a stdio server only a few basic variables of your shell, such as `HOME` and `PATH`, none of your `PIPELEX_` ones, and expands no variable in its configuration, so the tools find the login's key through `HOME`. When you set `PIPELEX_HOME`, or need `HTTPS_PROXY` behind a proxy, add an `[mcp_servers.env]` table right below the entry holding it. A `PIPELEX_API_KEY` written there works too, and wins over the login's, but Vibe copies its configuration into its session logs under `~/.vibe/logs/session/`, so the login keeps the key out of them.
- **`command` is a list**, which Vibe never splits, so a launcher path holding a space stays one word.
- **The raised `startup_timeout_sec`** covers the first `npx` start, which fills the npm cache and outlasts Vibe's 10-second default.
- **Keep the name `pipelex`**: it is the name the tools are grouped under.

The skills that need the tools stop with this setup instruction when the tools are absent.

### The hook

The hook that lints, formats and validates each `.mthds` file Vibe edits or writes ships in the plugin, as `pipelex-vibe/ai.mistral.vibe/hooks.toml`, so there is nothing to append. Vibe lists it as `pipelex:check-mthds` and runs it after every `edit` and `write_file` call, from the session's copy of the plugin. Its command is `bash "${PLUGIN_ROOT}"/hooks/check-mthds-vibe.sh --plugin-hook`: Vibe sets `PLUGIN_ROOT` to that copy, and the command names `bash` because Vibe rebuilds the copy without the files' executable bits.

When the hook refuses an edit, the model reads the lint or validation errors in place of the tool's result and fixes the file. The hook runs with Vibe's own environment, so it validates a method against the API only with `PIPELEX_API_KEY` exported in the shell you start Vibe from. Without it, it still lints and formats every edit.

When the hook itself fails, because `bash` is missing or the hook runs past its 15-second timeout, the edit stands and Vibe shows a warning line naming `pipelex:check-mthds` with the hook's error, which the model never sees. Without Node.js on your `PATH` the hook passes every edit silently, as it does in every agent. On native Windows, Vibe runs a hook in Git Bash, or in PowerShell when Git Bash is absent; under PowerShell the command cannot find its script yet, so every edit passes unchecked.

### Leaving the setup of earlier releases

Earlier releases had you append the hook to your own hooks file. Delete that `check-mthds` hook from `~/.vibe/hooks.toml`, or from `$VIBE_HOME/hooks.toml` when `VIBE_HOME` is set, and from any trusted project's `.vibe/hooks.toml` you put it in. Vibe runs the hooks in those files beside the plugin's, under another name, so the entry would check every edit a second time; since this release the script it calls exits at once when anything but the plugin's hook calls it, so the leftover entry is harmless, and deleting it is tidiness.

Releases before that had you make three hand edits. Remove the `skill_paths` entry naming `pipelex-vibe/skills`, which loads every skill a second time under its bare name; delete the `check-mthds` hook that names the script by an absolute path, as above; and replace the old `pipelex` server, with its `env` table, by the tools' entry above.

## The Pipelex MCP, for chatbots

A chatbot takes the Pipelex MCP rather than the plugin. Add it in the chatbot's settings by its address, which in Claude is **Add custom connector**, then sign in with your Pipelex account when asked. There is no key to paste.

```
https://mcp.pipelex.com/mcp
```

The sign-in is OAuth, and the chatbot drives it, including the choice of the organization you work in. The Pipelex MCP holds no key of its own and has no keyless mode: every call runs on your signed-in session, so the methods you see and the runs you spend are your own. When a session expires or is revoked, calls come back with an error telling you to reconnect and sign in again.

> **Upgrading from an `?api_key=` address.** The Pipelex MCP stopped taking an API key in its 0.12.0 release. An entry still registered with `?api_key=plx_sk_...` in its address, or with an `Authorization: Bearer plx_sk_...` header, no longer connects at all: remove it, add it again by the plain address above, and revoke in your console at [app.pipelex.com](https://app.pipelex.com) the key it carried, since a key that sat in an address may have reached browser history, copied links and proxy logs. ChatGPT keeps the configuration it read when the entry was added, so adding it again is the only way through there.
