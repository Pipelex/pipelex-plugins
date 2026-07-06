# pipelex-plugins

Pipelex plugins — **skills and hooks for working with MTHDS methods** (`.mthds` bundles) — packaged for **Claude Code**, **Codex**, and **Mistral Vibe**, and served through the Pipelex plugins marketplace.

This is the plugin generation that pairs with the hosted Pipelex API and the (closed-source) MCP server. Unlike the earlier `mthds-plugins`, it carries **no local-CLI dependency and no install/upgrade/env-check machinery** — install is just a marketplace add.

> **Status:** foundation in progress. See the workspace-root tracker `wip/devx/pipelex-plugins-foundations.md` for the phase plan.

## What's inside

- **Skills** — Pipelex skills (starting with `pipelex-explain`) for reading and reasoning about MTHDS bundles.
- **Hooks** — a `PostToolUse` validation hook that checks `.mthds` files on edit. When the MTHDS CLIs happen to be present locally it runs the full validation pipeline; when they're absent it passes silently (this plugin does not manage CLI installation). The iteration path swaps these for hosted-API / MCP-backed validation.
- **Language reference** — the shared MTHDS language reference docs that ground the skills (the *language* stays MTHDS — that's the standard; Pipelex is the tooling, product, and service).

## Install

> Full per-platform install instructions land with the first public release.

**Claude Code:**

```
claude plugin marketplace add Pipelex/pipelex-plugins
claude plugin install pipelex@pipelex-plugins
```

**Codex** and **Mistral Vibe** install via their respective marketplace-add and `skill_paths` equivalents — see `docs/`.

## Local development

The build renders every target from Jinja2 templates. Never edit generated output directly.

```
make build      # render all targets (prod + codex + mistral-vibe)
make check      # freshness + marketplace/version consistency + lint/type checks
make test       # unit tests
```

Dogfood loop with Claude Code: register this checkout as a local marketplace, then `make build` + `/reload-plugins`.

## License

[Apache 2.0](./LICENSE).
