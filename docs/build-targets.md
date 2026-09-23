# Multi-Target Build System

The plugin produces platform-specific outputs from one set of Jinja2 templates. Claude and Codex targets are installable plugins; the Mistral Vibe target is a skills/hooks bundle loaded through Vibe's `skill_paths` and `hooks.toml`.

This is the **CLI-free** plugin generation. Unlike the `mthds-plugins` predecessor, it carries no install/upgrade/env-check machinery, so the build system has none of the `env_check` / `can_run_methods` / `session_start_hook` switches, no `min_mthds_version` floor, no install-command variables, and no `bin/` self-install assets.

## How it works

```
templates/                      source of truth (all .j2 files)
├── skills/*/SKILL.md.j2        skill templates
├── skills/shared/*.md.j2       shared language references + the include-only partials
├── hooks/*.j2                  per-platform hook wiring + `.mthds` validation scripts
└── mcp/vibe-mcp.toml.j2         the workshop launcher as a Vibe [[mcp_servers]] fragment
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
       +---> pipelex/hooks/{hooks.json,check-mthds.sh}  (prod target, PostToolUse hook)
       +---> pipelex/.claude-plugin/plugin.json        (generated: plugin-base.json + target overrides)
       +---> pipelex-codex/skills/*/SKILL.md           (codex target, output)
       +---> pipelex-codex/hooks/codex-hooks.json      (codex target, bundled hook config)
       +---> pipelex-codex/.codex-plugin/plugin.json   (generated: plugin-base.json + target overrides)
       +---> pipelex-vibe/skills/*/SKILL.md            (Mistral Vibe target, output — manifestless)
       +---> pipelex-vibe/hooks/{vibe-hooks.toml,check-mthds-vibe.sh}  (Vibe post_tool hook)
       +---> pipelex-vibe/mcp/vibe-mcp.toml            (Vibe [[mcp_servers]] fragment — the workshop launcher)
       +---> .agents/plugins/marketplace.json          (verbatim copy of packaging/codex-marketplace.json)
```

## Template vs output directories

**`templates/`** holds all `.j2` source files. Never edit files in `pipelex/`, `pipelex-codex/`, or `pipelex-vibe/` directly — they are generated output.

**`skills/`** at the repo root (if present) holds only static per-skill assets — `references/`, read on a branch, and `scripts/`, run by path — that are copied into every target, a script's executable bit included. Several skills use it — `pipelex-design`, `pipelex-synthetic-inputs`, `pipelex-integrate`, `pipelex-scaffold` — and a reference need not be Markdown: `pipelex-integrate` ships `codegen-check.mjs` and `codegen_check.py`, the scripts the skill copies verbatim into TypeScript and Python projects, so a reference edit is followed by `make build` and, for a script, by running it — `tests/unit/test_pipelex_integrate_skill.py` executes both, and pyright type-checks the Python one against the real `pipelex-sdk`. **`pipelex/`**, **`pipelex-codex/`**, and **`pipelex-vibe/`** are generated output directories (build artifacts checked into git).

## Target configuration

### defaults.toml

Defines the variables shared by all targets. The CLI-free posture keeps this set small:

```toml
[vars]
marketplace_name = "pipelex-plugins"
platform = "claude"
harness_name = "Claude Code"
skill_dir = "${CLAUDE_SKILL_DIR}"   # "<skill-dir>" on Codex and Mistral Vibe

[vars.mcp_server]
command = "npx"
args = ["-y", "@pipelex/mcp@latest"]
env_vars = ["PIPELEX_API_KEY", "PIPELEX_BASE_URL"]

[vars.mcp_server.user_config.api_key]
type = "string"
title = "Pipelex API key"
description = "..."
sensitive = true

[vars.mcp_server.user_config.base_url]
type = "string"
title = "Pipelex API base URL"
description = "..."
```

Reintroduce a variable only when a skill or hook actually branches on it — the `[vars.mcp_server]` table arrived with MCP registration (it feeds the `mcpServers` entry of the generated Claude and Codex manifests, and the Vibe target's `mcp/vibe-mcp.toml` fragment, as the local workshop launcher; `env_vars` lists the variable names Codex forwards into the spawn, since Codex whitelist-filters MCP spawn env — see [decisions.md](decisions.md) "Dual-MCP flip". Dev override: point `command`/`args` at a local checkout + `make build` on Claude, or a same-named `[mcp_servers.pipelex]` config entry on Codex). The `user_config` sub-tables become the Claude manifest's `userConfig` (enable-time prompt; sensitive values keychain-stored) and drive both the MCP entry's `env` block (`${user_config.*}` → `PIPELEX_*`) and the hook wrapper's `CLAUDE_PLUGIN_OPTION_*` promotion — see [decisions.md](decisions.md) "Claude credentials move to plugin userConfig". Don't port dead switches.

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

- `claude` (default): renders Claude plugin metadata and the `PostToolUse` hook (`hooks.json` + `check-mthds.sh`).
- `codex`: renders Codex plugin metadata and the bundled hook config (`codex-hooks.json`).
- `mistral-vibe`: renders skills, the Vibe `post_tool` hook files (`vibe-hooks.toml` + `check-mthds-vibe.sh`) and the workshop launcher as the `mcp/vibe-mcp.toml` config fragment, with no Claude/Codex plugin manifest.

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
├── hooks/
│   ├── hooks.json            PostToolUse wiring (Write|Edit → check-mthds.sh)
│   └── check-mthds.sh        .mthds validation script (executable; silent-pass when CLIs absent)
└── skills/
    ├── pipelex-explain/
    │   └── SKILL.md           rendered with the target's variables
    └── shared/
        ├── mthds-reference.md         rendered per target
        └── native-content-types.md    rendered per target
```

References under a skill's `references/` directory are **copied** (not symlinked) so each output directory is self-contained — a marketplace install that copies a single plugin subdir cannot follow symlinks to siblings of the plugin root.

Every rendered `SKILL.md` opens with YAML frontmatter that `make check` parses **strictly**, with PyYAML's `safe_load`, and whose `name` must be its directory. That is the parser Mistral Vibe uses, and Vibe drops a skill whose frontmatter fails it with nothing but a line in its log, while Codex repairs the same line and Claude Code tolerates it — so a `: ` inside an unquoted `description:` loses the skill on one harness only. Reword the value, or quote it.

The Mistral Vibe target is manifestless: it emits skills, the Vibe hook files (`hooks/vibe-hooks.toml` + `hooks/check-mthds-vibe.sh`) and the MCP fragment (`mcp/vibe-mcp.toml`), and is wired into Vibe with `skill_paths = ["/absolute/path/to/pipelex-vibe/skills"]`, a `hooks.toml` entry, and the fragment's `[[mcp_servers]]` entry appended to the end of `~/.vibe/config.toml`, once the `mcp_servers = []` line a new Vibe config carries is deleted, with the API key written into its `env` table (Vibe forwards no shell environment into a stdio spawn — see [decisions.md](decisions.md) "Vibe target bakes the launcher as a config fragment").

## The size of a skill

Every skill is written to one rule, the **read-before-act rule** of the size diet (`wip/skill-size-diet/design.md`, box A): of each sentence, ask what happens if the model never reads it, and what would tell it.

- A **guard** — skipping it loses something that cannot be recovered, sends something off the machine, spends credit, or leaves a result silently wrong — stays in `SKILL.md`, once, in one sentence, at the step it governs.
- A **branch** — the wrong thing done on a path the model could have recognised before taking it — goes to a reference under `skills/<skill>/references/`, and `SKILL.md` keeps the condition and a pointer to follow **before acting**, at the decision point and never only in a closing list. References are one level deep: a reference never sends the model to another.
- A **stop** — a verdict, an exit code or a refusal says so — is one row of the stop table; a recovery longer than a line goes to the branch's reference.
- **Rationale** goes to `docs/decisions.md` and ships nowhere.

A `SKILL.md` takes one shape, in this order: the frontmatter; what the skill does and what it is not, in a few lines; the requirements; the guards that span several steps; the main path as numbered steps in the imperative, each with its own guards and pointers; the stop table; and an index of references, each with the condition that sends the model there. A procedure whose text is its correctness — a shell chain, a hash, a comparison of resolved paths — ships as a script under `skills/<skill>/scripts/`, takes its values as arguments, prints one line opening with a stable verdict word, never prints a secret, and is executed by the unit suite.

These checks hold the shape:

- **The ceiling.** `make check` measures every rendered `SKILL.md` against `SKILL_CEILING_CHARS` in `scripts/check.py`, **13,000 characters**: Claude Code re-attaches an invoked skill after a compaction within 5,000 tokens, and 13,000 is that at the lowest characters-per-token ratio measured under the Claude 5 tokenizer, 2.77, less a margin (`wip/skill-size-diet/facts.md`). It reports without failing until `SKILL_CEILING_ENFORCED` is flipped at the end of the diet.
- **Links, both ways.** Every relative link in a skill, a reference or a shared file must name a file in the same target — a link that climbs out of it names a file the installed plugin does not carry — and every anchor a heading of the file it points into, slugged as GitHub does, inline code keeping its text; code, fenced or inline, is an example and never a link; every shipped reference must be linked from a `SKILL.md`, every script named by its skill or one of its references (by its `/scripts/<name>` path), and every shared file by a skill or a reference.
- **The guard registry.** `tests/unit/test_skill_guards.py` lists each skill's guards by their canonical sentence and asserts, on every target, that each appears exactly once in the rendered `SKILL.md` and in no reference or shared file. A skill phase registers its guards in the change that places them.
- **Freshness.** A copied reference or script that differs from its source, bytes or executable bit, fails `--check`.

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
| `harness_name` | `defaults.toml` (overridden per target) | every template that names the harness to the user or the model: skill text and shared partials, the hook wrappers, `launch-pipelex-mcp.sh.j2` and `mcp/vibe-mcp.toml.j2` |
| `skill_dir` | `defaults.toml` (`${CLAUDE_SKILL_DIR}`), overridden to `<skill-dir>` in `codex.toml` and `mistral-vibe.toml` | a sentence that names one of the skill's own files by path — today `pipelex-integrate`'s `cp` of its gate scripts. See below |
| `mcp_server` | `defaults.toml` (`[vars.mcp_server]` table, overridable per target) | `make_plugin_json()` — the local workshop launcher baked into the plugin-declared `pipelex-mcp` entry: Claude gets `type: stdio` pointing at the `launch-pipelex-mcp.sh` wrapper (which promotes the `PIPELEX_PLUGIN_*` user-config values to their real `PIPELEX_*` names only when non-empty, then `exec`s `command`/`args`), or `command`/`args` directly when the target declares no `user_config`; Codex gets bare `command`/`args` plus `env_vars` (variable *names* forwarded from the user's env — Codex whitelist-filters MCP spawn env; see [decisions.md](decisions.md) "Dual-MCP flip"). Dev override: point `command`/`args` at a local checkout + `make build` on Claude, or a same-named `[mcp_servers.pipelex]` entry in `~/.codex/config.toml` on Codex. `mcp/vibe-mcp.toml.j2` renders the same `command`/`args` as a Vibe `[[mcp_servers]]` stdio entry, listing every `env_vars` name as an empty `env` key the user fills in |
| `floors` | `defaults.toml` (`[vars.floors]` table) | `pipelex-integrate` and `pipelex-scaffold`, which state the minimum versions to the user. See below |
| `plugin_name` | derived from `[plugin].name` | available in all templates |

### The skill directory

A skill that copies one of its own files verbatim, or runs one of its scripts, names it by path, and the path of a skill's directory is known only at run time, differently on each harness (`wip/skill-size-diet/facts.md`, sections 2 to 5). Claude Code substitutes `${CLAUDE_SKILL_DIR}` in a skill body before the model reads it, so on Claude `skill_dir` is that token and the model reads a real path. Codex and Mistral Vibe substitute nothing, but each tells the model where a loaded `SKILL.md` lives — Codex in the `<skill>` message that injects the skill, Vibe as "Base directory for this skill" — so there `skill_dir` is the placeholder `<skill-dir>`, and the include-only partial `skill-dir.md.j2` defines it in one sentence, placed just before its first use. On Claude that partial renders nothing.

Two rules come with it. **A verbatim copy is a `cp` from `{{ skill_dir }}/references/…`, run from the user's project**, never left to the model to read the file and write it back, which is how Vibe once copied `codegen-check.mjs`: identical by luck, and capped at the size its tools can carry. **A script is run by its absolute path, from the user's project, through its interpreter** (`sh "{{ skill_dir }}/scripts/x.sh" …`), because on Codex and Vibe the model otherwise changes into the skill's directory to run it, and a script acting on a project must run where the project is.

`${CLAUDE_SKILL_DIR}` does not trip `check_skill_argument_placeholders`, which looks for the `$ARGUMENTS` and `$N` tokens Claude Code replaces with a skill's invocation arguments, and the link check finds a script named this way by its `/scripts/<name>` tail on every target. A reference named only inside a code span, as a `cp` command names it, is not a link, so the skill's reference index links it as well.

### Version floors

`[vars.floors]` in `targets/defaults.toml` carries the minimum versions the skills state to the user: the two SDKs, the workshop, Node, the Python range and the method app's port. `pipelex-integrate` and `pipelex-scaffold` read them as `{{ floors.<key> }}`, so a bump is one edit instead of a hunt through prose. Each key's comment in the table says what makes it a floor — "the first release carrying X" — because a floor without that is a preference.

These are **value substitutions**, which is why they do not contradict the trimmed-variable rule this repo inherited from `mthds-plugins`: nothing branches on a floor, it is only printed. The rule that bans dead switches bans variables a skill *reads to decide what to do*.

**One floor is stated as a ceiling and is easy to misread.** `pipelex_mcp` is the last `@pipelex/mcp` that **predates** the main-pipe signature in a validate verdict, so `pipelex-integrate` says "`{{ floors.pipelex_mcp }}` and earlier". Bumping it therefore means the signature arrived in a *later* release than the one recorded, and the sentence naming it has to be re-read rather than renumbered.

**A misspelled key fails the build.** The renderer's Jinja environment uses `StrictUndefined`, so `{{ floors.typo }}` raises with the template and the attribute named, and `_render_or_die` turns that into a clean build failure. This reaches **every** template and every variable, not only the floors, because the hazard is the mechanism rather than one table — so a variable that may legitimately be absent must now say so, with `{% if x is defined %}` or `{{ x | default(…) }}`, instead of leaning on an undefined name being falsy. Every template rendered byte-identically when it was turned on, so nothing needed migrating; the rule is for what comes next. Under Jinja's default `Undefined` it would instead render as the empty string: a sentence shipped with a hole where the version floor belongs, looking like well-formed prose, past the build, past the freshness check, past every other test. This is the `PIPELEX_BUILD_ERROR` guard's problem in another shape — a marker cannot be used here, because the value is interpolated mid-sentence rather than selected by a branch, and strict mode is the answer that needs no marker at all.

Strict mode is also the only guard that sees **every** use site. A check over the built output asks whether a floor's value is present, which a second, correctly spelled occurrence answers yes to while the misspelled one ships empty — `starters.md` states the Node floor once per template column, so that is the normal case, not a corner.

**The static references keep their literals**, because `skills/*/references/` is copied verbatim into every target and never rendered. `scripts/check.py`'s `check_version_floors` is what holds them to the table, and it guards two remaining drifts:

- **A floor that reaches no generated skill at all.** Not the misspelling any more — a table entry nothing states, or a sentence reworded until the number fell out of it. Either way the table and the skills have parted, and nothing else would say so.
- **A static reference left behind by a bump.** `VERSION_FLOOR_STATIC_REFS` pins each reference sentence to a floor key with a regex capturing the number, and every occurrence is checked, not the first — `starters.md` states the Node floor once per template column.
- **A template that spells a floor instead of reading it.** No `.j2` may contain a floor's literal value: strict rendering fires on an expression that is present and misspelled, never on one somebody replaced with its own value, and the presence check above is satisfied by any other sentence that still reads the table — so a hardcoded row renders correctly today and drifts silently at the next bump. Two rows of `pipelex-integrate`'s troubleshooting table were exactly that. The check names the template and the line, and the cure is to write `{{ floors.<key> }}`.

**The anchor list is hand-kept, so the way it fails is by omission**: a floor stated in a static file that nobody adds an entry for drifts silently on the next bump, with the whole check still green. `tests/unit/test_check.py::TestVersionFloors::test_every_static_statement_of_a_floor_is_anchored` sweeps the static tree for each floor's literal and requires every occurrence to be captured by an anchor, or listed in that test as a number meaning something else — which today is `writing-mthds.md`'s `3.14` and `png.md`'s matplotlib `3.11`. Adding a static statement of a floor means adding its anchor in the same change.

The patterns are **anchored on the prose around the number**, never on the number alone, and that is load-bearing: a bare numeric sweep reads `writing-mthds.md`'s JSON `"number"` example of `3.14` as the Python ceiling and `png.md`'s matplotlib `3.11` as the Python floor. The cost is that rewording a pinned sentence fails the check — which is the right way round. Re-anchor the pattern in the same change that rewords the sentence; a silent pass would mean nobody is holding that sentence to anything any more.

So the bump procedure is: edit `[vars.floors]`, run `make build`, run `make check` — and the check names every static reference still saying the old number.

### Shared template files

`templates/skills/shared/` holds two kinds of file, told apart by the `SHARED_TEMPLATES` list in `gen_skill_docs.py`.

**Rendered standalone.** The files listed there — the MTHDS language references, and `credentials.md`, which says how to connect the workshop and where its key comes from on each harness — are rendered per target and written to `skills/shared/`, where a skill body links to them. They are references in the size diet's sense: a skill reads one when a condition sends it there, so each is named by a pointer at that condition.

**Include-only partials.** Every other file there is `{% include %}`-d by the skill templates and never rendered on its own, so it ships as part of whichever skills include it and nowhere else. They exist so that a block several skills say word for word has one source: the credential sentence used to sit in five templates, and correcting it meant five edits and a test that asserted two of them were identical.

| Partial | What it carries | Parameters the including template sets |
| --- | --- | --- |
| `frontmatter.md.j2` | the YAML frontmatter fields shared by every skill (Claude's `allowed-tools`) | `skill_tools` (the harness-native tools the skill pre-approves; defaults to the writing set) |
| `mcp-requirements.md.j2` | the two stops an MCP-backed skill opens with — an absent tool, a `config`-class error surfaced verbatim — each pointing at `shared/credentials.md` for what to tell the user | `mcp_absent_lead` (`the tool is`, `the tools are`, `a tool is`), `mcp_absent_suffix`, `mcp_config_parenthetical`, `mcp_config_suffix`, `mcp_requirements_extra` (a bullet appended after the two stops) |
| `validate-call.md.j2` | how a local bundle is handed to the workshop: which files (every `.mthds` file beneath the bundle directory except `runs/`), the path form of `files`, and the inline fallback the hosted console needs | `validate_call_file_set` (`false` in `pipelex-integrate` alone, which states the file set its call site loads) |
| `formatting-hook.md.j2` | that the validation hook formats every `.mthds` write, so no skill hand-formats | `formatting_hook_write_clause` |
| `stale-types-notice.md.j2` | the notice that a bundle change may have outdated a generated tree, in one wording for its three call sites | none |
| `saved-copy-notice.md.j2` | the notice that the linked saved method does not have this change, offering `/pipelex-catalog` and never saving | none |
| `catalog-id-bridge.md.j2` | how a file-based skill reaches a catalog id: the search over the link files, the several-hits question, the pull, and the refusal of a published address | `catalog_id_bridge_resume` (the step the skill resumes at, interpolated mid-sentence) |
| `pipefunc-warning.md.j2` | that `PipeFunc` is experimental on the hosted plane and runs its Python in a network-blocked sandbox | none |
| `project-root.md.j2` | where a project starts — the nearest directory holding one of the project markers — for design, integrate and catalog | none |
| `skill-dir.md.j2` | on Codex and Vibe, the sentence defining the `<skill-dir>` placeholder as the directory of the `SKILL.md` the harness loaded; nothing on Claude, where `${CLAUDE_SKILL_DIR}` is substituted. Included just before the first sentence that uses `{{ skill_dir }}` | none |

Two mechanics matter when writing one. A partial that may be included **mid-sentence** strips its own trailing newline, with a `{#- -#}` comment on its last line; the including template supplies the line break. And a parameter is passed by setting it in the including template before the include — block form reads best for a sentence of Markdown, and the closing tag swallows its own newline so the assignment leaves no blank line in the output:

```jinja
{% set mcp_config_suffix %} Never silently skip validation.{% endset -%}
{% include "skills/shared/mcp-requirements.md.j2" %}
```

**The frontmatter partial is the one exception to the line-break rule.** Its fields open with their own line break and end without one, and every skill includes it with `{%- include %}` (and sets `skill_tools`, when it does, with `{%- set %}`), which strips the break before it. So a target with no fields to add renders the `description:` line straight into the closing `---`, and Claude's tool list runs straight into the MCP tools a skill appends; a blank line inside the block fails `TestRenderedFrontmatterShape`.

A parameter left unset falls back to the partial's own default, so a skill sets only what it says differently. `tests/unit/test_gen_skill_docs.py::TestSharedSkillIncludes` fails when a skill pastes one of these blocks instead of including it.

**A parameter with no default is left bare, because strict mode is the guard.** Under `StrictUndefined` an unset or misspelled name raises at render time and `_render_or_die` names the template and the variable, so a parameter with no default needs no marker for the absent case — and an `{% if x is defined %}` guard around one would suppress that failure rather than add to it, trading a precise build error for a marker caught later. What strict mode cannot see is a name that is **present and wrong**: a partial that selects one of several blocks by a parameter's value falls off the end of its chain on a misspelled value and drops the block entirely, so such a chain ends in an `{% else %}` that emits `PIPELEX_BUILD_ERROR`, which `scripts/check.py` refuses in any generated file. No partial branches on a value today — `stale_types_variant` did until the size diet unified its three wordings — and the check stays for the next one. `catalog_id_bridge_resume` is interpolated rather than branched on, so it has no wrong-value case to catch.

Hook templates (`templates/hooks/`) are rendered per target. Claude maps `.mthds` validation to `PostToolUse` over `Write|Edit`; Codex maps it to `PostToolUse` over `apply_patch`; Mistral Vibe maps the same behavior to `post_tool` over `edit|write_file` (stable hooks API, Vibe 2.21.0+). See [hooks.md](hooks.md) for the validation pipeline, the CLI-free silent-pass posture, and the Codex enablement note.
