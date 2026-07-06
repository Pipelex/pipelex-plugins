# Multi-Target Build System

The plugin produces platform-specific outputs from one set of Jinja2 templates. Claude and Codex targets are installable plugins; the Mistral Vibe target is a skills/hooks bundle loaded through Vibe's `skill_paths` and `hooks.toml`.

This is the **CLI-free** plugin generation. Unlike the `mthds-plugins` predecessor, it carries no install/upgrade/env-check machinery, so the build system has none of the `env_check` / `can_run_methods` / `session_start_hook` switches, no `min_mthds_version` floor, no install-command variables, and no `bin/` self-install assets.

## How it works

```
templates/                      source of truth (all .j2 files)
├── skills/*/SKILL.md.j2        skill templates
├── skills/shared/*.md.j2       shared language references (+ the include-only frontmatter partial)
└── hooks/*.j2                  hook templates (added when hooks are ported)
       |
       v
targets/defaults.toml          common variable defaults
       |
       v
targets/<name>.toml             per-target plugin identity + variable overrides + skill filter
       |
       v
scripts/gen_skill_docs.py       renders .j2 templates with merged variables
       |
       +---> pipelex/skills/*/SKILL.md                 (prod target, output)
       +---> pipelex/skills/shared/*.md                (prod target, output)
       +---> pipelex/.claude-plugin/plugin.json        (generated: plugin-base.json + target overrides)
       +---> pipelex-codex/skills/*/SKILL.md           (codex target, output)
       +---> pipelex-codex/.codex-plugin/plugin.json   (generated: plugin-base.json + target overrides)
       +---> pipelex-vibe/skills/*/SKILL.md            (Mistral Vibe target, output — manifestless)
       +---> .agents/plugins/marketplace.json          (verbatim copy of packaging/codex-marketplace.json)
```

## Template vs output directories

**`templates/`** holds all `.j2` source files. Never edit files in `pipelex/`, `pipelex-codex/`, or `pipelex-vibe/` directly — they are generated output.

**`skills/`** at the repo root (if present) holds only static per-skill assets (`references/` subdirectories) that are copied into every target. **`pipelex/`**, **`pipelex-codex/`**, and **`pipelex-vibe/`** are generated output directories (build artifacts checked into git).

## Target configuration

### defaults.toml

Defines the variables shared by all targets. The CLI-free posture keeps this set small:

```toml
[vars]
marketplace_name = "pipelex-plugins"
platform = "claude"
harness_name = "Claude Code"
```

Reintroduce a variable only when a skill or hook actually branches on it (e.g. an `mcp_server_url`-style variable would arrive with MCP registration). Don't port dead switches.

### Per-target files (prod.toml, codex.toml, mistral-vibe.toml)

Each target defines plugin identity and can override any default variable:

```toml
[plugin]
name = "pipelex"
version = "0.1.0"
description = "Skills and hooks for working with AI methods following the MTHDS standard."
source = "pipelex/"     # output directory

[vars]
# Override any default variable here.

[skills]
# Optional: build only a subset of skills. Omit for all skills.
# include = ["pipelex-explain"]
```

The target platform is selected with `[vars].platform`:

- `claude` (default): renders Claude plugin metadata (and, once ported, `PostToolUse` hooks).
- `codex`: renders Codex plugin metadata (and, once ported, the bundled hook config).
- `mistral-vibe`: renders skills (and, once ported, Vibe `after_tool` hook files), with no Claude/Codex plugin manifest.

### Variable resolution

Variables are resolved in this order (last wins):

1. `defaults.toml[vars]` — shared defaults
2. `<target>.toml[vars]` — per-target overrides
3. `plugin_name` — derived automatically from `[plugin].name`

All variables are available in all `.j2` templates as `{{ variable_name }}`.

## Output directories

Each target specifies a `source` directory where its output is written. Claude/Codex targets produce complete plugin directories:

```
pipelex/                       (prod target)
├── .claude-plugin/
│   └── plugin.json           generated (inherits author/repo/license from plugin-base.json)
└── skills/
    ├── pipelex-explain/
    │   └── SKILL.md           rendered with the target's variables
    └── shared/
        ├── mthds-reference.md         rendered per target
        └── native-content-types.md    rendered per target
```

References under a skill's `references/` directory are **copied** (not symlinked) so each output directory is self-contained — a marketplace install that copies a single plugin subdir cannot follow symlinks to siblings of the plugin root.

The Mistral Vibe target is manifestless: it emits skills (and, once ported, the Vibe hook files) and is wired into Vibe with `skill_paths = ["/absolute/path/to/pipelex-vibe/skills"]` plus a `hooks.toml` entry.

## Codex marketplace discovery

Codex resolves `codex plugin marketplace add Pipelex/pipelex-plugins` by scanning `.agents/plugins/marketplace.json` (preferred) or `.claude-plugin/marketplace.json`. The canonical Codex packaging spec is `packaging/codex-marketplace.json`; the build syncs a byte-identical copy to `.agents/plugins/marketplace.json` on every run. The freshness check fails if the copy drifts from the canonical source.

## Per-target skill overlays

A skill can carry **target-only content** without touching its shared `SKILL.md.j2`. Drop a `SKILL.<target>.md.j2` file next to a skill's `SKILL.md.j2` (where `<target>` is the stem of the target's `.toml`). When that target is built, the overlay is rendered with the same variables and **appended** to the skill's output; every other target stays byte-identical because the shared template is never modified.

Overlays are append-only, so they add or override behavior (a later instruction in the rendered skill wins) but cannot delete earlier content. Because overlays render in the same Jinja environment, they may use template variables and `{% include %}` shared partials.

The mechanism is implemented in `render_templates()` (`scripts/gen_skill_docs.py`, `target_name` parameter).

## Commands

```bash
make build                       # build all targets
make gen-skill-docs              # build default target (prod)
make gen-skill-docs TARGET=codex # build a specific target

# Validation
make check-shared            # shared repo checks + freshness + lint/type checks
make check-claude            # Claude marketplace checks
make check-codex             # Codex packaging checks
make check                   # aggregate target
```

The underlying script accepts:

```bash
python scripts/gen_skill_docs.py --target prod        # one target
python scripts/gen_skill_docs.py --target all         # all targets
python scripts/gen_skill_docs.py --target prod --check # freshness check
```

## Adding a new target

1. Create `targets/<name>.toml` with a `[plugin]` section (name, version, description, source).
2. Set `[vars].platform` when the target is not Claude.
3. Add Claude targets to `.claude-plugin/marketplace.json`; add Codex targets to `packaging/codex-marketplace.json`; do not add Mistral Vibe targets to either marketplace.
4. Run `make build` — the output directory is created with rendered files and copied static assets.
5. Run `make check` — validates shared, Claude, and Codex consistency.

## Version management

All targets share the same version string in lockstep — `make check` fails on drift between `targets/*.toml`.

- **Plugin version**: `targets/prod.toml [plugin].version` is the source of truth; `pipelex/.claude-plugin/plugin.json` is generated by the build. Codex/Vibe versions live in their own target TOMLs and must match.
- **Marketplace version**: `.claude-plugin/marketplace.json metadata.version` is bumped on any release; `make check-claude` fails if it lags behind the highest Claude target version.
- Versions start at **0.1.0**.

## Template variables

| Variable | Defined in | Used in |
|----------|-----------|---------|
| `marketplace_name` | `defaults.toml` | reserved for skills/hooks that reference the marketplace |
| `platform` | `defaults.toml` (overridden per target) | `frontmatter.md.j2` (Claude-only `allowed-tools`) |
| `harness_name` | `defaults.toml` (overridden per target) | reserved for skills that name the harness |
| `plugin_name` | derived from `[plugin].name` | available in all templates |

### Shared template files

The files in `templates/skills/shared/` listed in `SHARED_TEMPLATES` (`gen_skill_docs.py`) — the MTHDS language references — are rendered per target and written to `skills/shared/`. `frontmatter.md.j2` is a deliberate exception: it is an **include-only partial** ({% include %}-d by skill templates for their YAML frontmatter), so it is not listed in `SHARED_TEMPLATES` and is never rendered standalone.

Hook templates (`templates/hooks/`) are rendered per target when the hooks are ported. Claude maps `.mthds` validation to `PostToolUse` over `Write|Edit`; Codex maps it to `PostToolUse` over `apply_patch`; Mistral Vibe maps the same behavior to `after_tool` over `edit|write_file`.
