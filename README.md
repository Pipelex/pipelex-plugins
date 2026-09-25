# pipelex-plugins

The Pipelex plugin for Claude Code and Codex: your agent builds AI methods, runs them, and puts them in your TypeScript or Python code or in a new webapp, with skills for each step, a hook that checks every edit, and the Pipelex tools.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/Pipelex/pipelex-plugins/blob/main/LICENSE)

<!-- onboarding: front-door -->
<!-- Generated from the Pipelex onboarding source; this region is replaced from https://raw.githubusercontent.com/Pipelex/.github/main/onboarding/rendered/front-door--open_source-plugin.md — do not edit it here. -->
## Quick start

Pipelex lets you build AI methods with your coding agent and run them anywhere: as an MCP for chatbots, as a webapp for people, or via API for your software.

**1. Sign up at [app.pipelex.com](https://app.pipelex.com).**

**2. Install the Pipelex plugin in your coding agent.** The plugin gives your agent the skills that build methods, run them and put them in your software, a hook that checks every edit, and the Pipelex tools.

<details open><summary><b>Claude Code</b></summary>

```bash
claude plugin marketplace add Pipelex/pipelex-plugins
claude plugin install pipelex@pipelex-plugins
```

Claude Code asks for an API key when you enable the plugin, and stores it in your OS keychain — create one in your console at [app.pipelex.com](https://app.pipelex.com). The skills, the hook that checks every edit and the Pipelex tools load with it. The plugin's hook and the Pipelex tools run on Node.js, so you need Node.js on your `PATH`.

Claude Code also loads what you have added to your Claude account, so if you added the Pipelex MCP to Claude, Claude Code has it too. An agent with the plugin does not need the Pipelex MCP, and there is nothing to turn off: when both are present, the Pipelex MCP defers to the plugin's tools.

</details>

<details open><summary><b>Codex</b></summary>

```bash
codex plugin marketplace add Pipelex/pipelex-plugins
export PIPELEX_API_KEY=plx_sk_...     # create one in your console at app.pipelex.com
```

Restart Codex, run `/plugins` to install `pipelex`, and trust the plugin hook on first run. Requires Codex 0.141 or later. The plugin's hook and the Pipelex tools run on Node.js, so you need Node.js on your `PATH`.

</details>

**3. Ask your agent for the method you want.**

> Design a method that reads an invoice PDF and returns the supplier, the total and the line items. Then run it on `~/Downloads/invoice.pdf` and save it to my Pipelex account.

`/pipelex-design` writes the method, the hook checks it on every edit, `/pipelex-run` starts it and prints a run id you can come back to, and `/pipelex-catalog` saves it to your account, where your chatbot can run it too.

**Run your methods from your chatbot.** The Pipelex MCP is a connector for your chatbot (ChatGPT, Claude): it gives it access to the Pipelex service, so it can list the methods saved in your account and run them right in the conversation. Your methods become your chatbot's tools. To build a method, use the Pipelex plugin in a coding agent such as Claude Code or Codex, as in steps 2 and 3 above.

Add the Pipelex MCP in your chatbot's settings by the address below — in Claude, that is **Add custom connector** — then sign in with your Pipelex account when asked. Nothing to install and no key: the Pipelex MCP runs on your signed-in session.

```
https://mcp.pipelex.com/mcp
```

Then ask your chatbot:

> What methods do I have?
>
> Run the invoice method on https://example.com/invoice.pdf

You get a run id straight away, and you can ask for its status, its results or the files it produced at any time.

Give the file as a URL the Pipelex MCP can reach. In ChatGPT you can attach it to the conversation instead and ask for a run on it; Claude has no way yet to hand the Pipelex MCP a file you attached.

**The other two ways, built by your agent too.** Ask it for a webapp around the method, and `/pipelex-scaffold` creates a new app from the [method-app template](https://github.com/Pipelex/pipelex-method-apps) and leaves it running on your machine. Ask it to call the method from your TypeScript or Python code, and `/pipelex-integrate` generates the method's types and one typed call that runs it, through the TypeScript SDK [`@pipelex/sdk`](https://www.npmjs.com/package/@pipelex/sdk) or the Python SDK [`pipelex-sdk`](https://pypi.org/project/pipelex-sdk/). Any other software runs a method via API through `POST /v1/start`, with any HTTP client.

**Next:** [what Pipelex is](https://go.pipelex.com/product) · [documentation](https://go.pipelex.com/docs) · [your console](https://app.pipelex.com) · [Discord](https://go.pipelex.com/discord)

This repository is the Pipelex plugin — what it holds, the other agents it installs in and how to work on it are below.
<!-- /onboarding -->

## What the plugin holds

### Skills

Your agent picks the skill your request calls for, and you can also name one yourself. Together they take a method from its first draft into your software: building it, preparing its inputs, running it, and calling it from your code.

#### Build a method

- **`/pipelex-design`** designs a method contract-first and writes it as `.mthds` files, directly when the method is simple and step by step when it is not.
- **`/pipelex-edit`** makes an edit that keeps a method's contract, such as a prompt, a model or a rename, and proves it with a validation before and after.
- **`/pipelex-organize`** regroups a method's files into a layout you can browse, without changing what the method does.
- **`/pipelex-explain`** explains a method in plain language, its contract, its flow and every pipe, and writes nothing.

#### Prepare inputs

- **`/pipelex-inputs`** prepares a method's inputs from your files, from synthetic data or from a template, ready to run.
- **`/pipelex-synthetic-inputs`** makes the test files a method needs when you have none: PDFs, images, Word and Excel files rendered from code, and photographs from an image model.

#### Run and save

- **`/pipelex-run`** runs a method on the hosted Pipelex API, prints its run id at once, and follows a run to its status, its results and its files.
- **`/pipelex-catalog`** saves a method to your Pipelex account, lists what is saved there, and pulls a saved method back to disk.
- **`/pipelex-lab`** frames a use case into candidate methods, writes each test case's answer before the first run, then runs, scores, logs and fixes the method round after round within a budget you agree.

#### Put a method in your code

- **`/pipelex-integrate`** puts a method in the TypeScript or Python code you already have: it generates the method's types and writes one typed call that runs it, through the TypeScript SDK `@pipelex/sdk` or the Python SDK `pipelex-sdk`, and refreshes the types when the method changes.
- **`/pipelex-scaffold`** starts a new project around a method when you have no code yet: a webapp from the method-app template, created in one step and left running, or any other project from its language's own initializer, which it hands to `/pipelex-integrate`.

The skills share a reference for MTHDS, the language a method is written in. [Each skill in detail, and what it needs](https://github.com/Pipelex/pipelex-plugins/blob/main/docs/skills.md).

### The hook

After every edit to a `.mthds` file, the hook lints it and formats it in place on your machine, offline, then validates the whole method on the hosted Pipelex API when a key is set. A failed check returns to your agent with the line to fix. The hook runs on Node.js, which must be on your `PATH`. [How the hook works](https://github.com/Pipelex/pipelex-plugins/blob/main/docs/hooks.md).

### The Pipelex tools

The tools the skills call to validate a method, prepare its inputs, run it, generate typed code and reach your saved methods start with your agent, which runs them through `npx`, so like the hook they need nothing installed beyond Node.js on your `PATH`. [The tools, one by one](https://github.com/Pipelex/pipelex-plugins/blob/main/docs/skills.md#the-pipelex-tools).

## Other agents

The plugin also installs in **Mistral Vibe** 2.21.0 or later, from a clone of this repository: Vibe loads the skills from a path in its config, the hook from its `hooks.toml`, and the Pipelex tools from a config entry that carries your key. [The Mistral Vibe procedure](https://github.com/Pipelex/pipelex-plugins/blob/main/docs/install.md#mistral-vibe).

**Claude Code in the Claude desktop app** does not inherit your shell environment, so an exported `PIPELEX_API_KEY` never reaches it. Set the key in the plugin configuration dialog, which opens when you enable the plugin.

Which Pipelex product each app takes, and every agent's install in detail, are in [Install the plugin, agent by agent](https://github.com/Pipelex/pipelex-plugins/blob/main/docs/install.md).

## Configuration

- **API key.** In Claude Code, enter it in the plugin configuration dialog, which stores it in your OS keychain; `PIPELEX_API_KEY` in your environment is the fallback, and a value set in the dialog wins. Codex reads `PIPELEX_API_KEY` from your shell. Create a key in your console at [app.pipelex.com](https://app.pipelex.com).
- **Base URL.** Optional, for a deployment other than the hosted API: the dialog's base URL field, or `PIPELEX_BASE_URL`. It defaults to `https://api.pipelex.com`.
- **Without a key**, the hook still lints and formats every edit and skips only the validation, and the skills that need the Pipelex tools stop and say how to set one. The hook never blocks an edit because Node.js is missing or the API is unreachable.
- **Privacy.** With a key set, each validation sends the `.mthds` files around the edited one to the Pipelex API. Leave the key unset, in the dialog and in your environment, to keep the hook's checks on your machine.

## Documentation

- [Install the plugin, agent by agent](https://github.com/Pipelex/pipelex-plugins/blob/main/docs/install.md): Claude Code, Codex and Mistral Vibe in detail, and which Pipelex product each app takes.
- [The skills and the Pipelex tools](https://github.com/Pipelex/pipelex-plugins/blob/main/docs/skills.md): what each skill does and needs, and the tools it calls.
- [The validation hook](https://github.com/Pipelex/pipelex-plugins/blob/main/docs/hooks.md): the checks it runs, on each agent, and what it does when something is missing.
- [Develop the plugin](https://github.com/Pipelex/pipelex-plugins/blob/main/docs/development.md): the build, the checks, and running your changes in your own agent.
- [The multi-target build](https://github.com/Pipelex/pipelex-plugins/blob/main/docs/build-targets.md), [continuous integration](https://github.com/Pipelex/pipelex-plugins/blob/main/docs/ci.md) and [the decisions behind the plugin](https://github.com/Pipelex/pipelex-plugins/blob/main/docs/decisions.md).
- [The Pipelex documentation](https://docs.pipelex.com/) and [the MTHDS standard](https://mthds.ai/).

## Develop

The plugin is rendered from the Jinja2 templates in `templates/` into one output per agent. Edit the templates, never the generated `pipelex/`, `pipelex-codex/` or `pipelex-vibe/` trees.

```bash
make build         # render every target
make agent-check   # fix imports, format, lint, then the checks CI runs
make agent-test    # the unit tests, quiet unless one fails
```

To run your changes in Claude Code or Codex before they are released, see [the dogfood loop](https://github.com/Pipelex/pipelex-plugins/blob/main/docs/development.md#run-your-changes-in-your-agent).

## License

Apache 2.0. See [LICENSE](https://github.com/Pipelex/pipelex-plugins/blob/main/LICENSE).
