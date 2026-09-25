# CLAUDE.md — pipelex-plugins

Pipelex plugins — **skills and hooks for working with MTHDS methods** (`.mthds` bundles) — packaged for Claude Code, Codex, and Mistral Vibe and served through the Pipelex plugins marketplace.

This is the hosted-API / MCP-era plugin generation. Unlike its predecessor `mthds-plugins`, it carries **no local-CLI dependency and none of the install/upgrade/env-check machinery**. Install is just a marketplace add.

Foundational decisions are recorded in `docs/decisions.md`. The README is the front page and follows the workspace's README standard (`docs/marketing/readmes.md` in the `Pipelex` repo): its quick start is an onboarding region, the text between the `<!-- onboarding: front-door -->` markers, which is generated from the workspace's onboarding source and never edited here. Everything a reader needs after the first run lives in `docs/`.

## Brand boundaries

The **plugins** are Pipelex's product surface: marketplace `pipelex-plugins`, plugin `pipelex`, outputs `pipelex/` (Claude), `pipelex-codex/`, `pipelex-vibe/`. The **language** stays MTHDS inside the docs — MTHDS is the standard; Pipelex is the tooling, product, and service. Skills are `pipelex-*`; language-reference content keeps its MTHDS vocabulary.

## Repository Structure

```
.claude-plugin/
├── plugin-base.json           # Shared plugin fields (author, repo, license)
└── marketplace.json           # Marketplace listing (marketplace: pipelex-plugins)
.codex-plugin/
└── plugin-base.json           # Shared Codex plugin manifest fields
.agents/plugins/
└── marketplace.json           # Codex-discoverable copy of packaging/codex-marketplace.json (generated)
packaging/
└── codex-marketplace.json     # Canonical Codex marketplace packaging spec
targets/
├── defaults.toml              # Shared template variable defaults (trimmed set)
├── prod.toml                  # Claude prod target config (version, identity)
├── codex.toml                 # Codex target config (version, identity)
└── mistral-vibe.toml          # Mistral Vibe target config (version, identity)
templates/                     # SOURCE OF TRUTH — all .j2 templates live here
├── skills/
│   ├── pipelex-explain/SKILL.md.j2   # Read-and-explain a bundle directory or a saved method's source; a published address at contract level; strictly read-only (workshop optional)
│   ├── pipelex-design/SKILL.md.j2    # Contract-first, complexity-adaptive top-down design (MCP-backed)
│   ├── pipelex-organize/SKILL.md.j2  # Regroup a designed bundle when its layout needs it (MCP-backed; conditional after pipelex-design)
│   ├── pipelex-edit/SKILL.md.j2      # Contract-preserving edits to an existing bundle; routes structural changes to pipelex-design (MCP-backed)
│   ├── pipelex-inputs/SKILL.md.j2    # inputs.json preparation, ending at run-ready inputs (MCP-backed)
│   ├── pipelex-run/SKILL.md.j2       # The run lifecycle: start a run, or follow one by its id (MCP-backed)
│   ├── pipelex-lab/SKILL.md.j2       # The experiment loop: frame a use case, write answer keys before the first run, then run, score, log and fix within a budget (workshop needed by the loop alone)
│   ├── pipelex-catalog/SKILL.md.j2   # The catalog: list, save a bundle directory, pull a saved method back (MCP-backed)
│   ├── pipelex-synthetic-inputs/SKILL.md.j2  # File factory: render PDFs/PNGs/Office files from code; photographs through the workshop's image generation, the one MCP use and optional
│   ├── pipelex-integrate/SKILL.md.j2 # Wire a method into a TS/Python codebase: codegen write arm, exclusions, sidecar, gate, typed call site (MCP-backed)
│   ├── pipelex-scaffold/SKILL.md.j2  # Front door to a new project: the method-app family's initializer and the template's `make serve`, left running; or the ecosystem's initializer, committed and given its env file by the skill's scripts (no MCP dependency)
│   └── shared/                       # Two kinds: rendered per target, or include-only partials
│       ├── writing-mthds.md.j2        # The one MTHDS language reference: design reads it before every write, edit, explain, inputs and integrate for a syntax question (rendered per target; includes the PipeFunc warning)
│       ├── native-content-types.md.j2 # Native content-type documentation (rendered per target)
│       ├── credentials.md.j2          # Connecting the workshop and where its key comes from, per harness (rendered per target; read when an MCP stop fires)
│       ├── catalog-id.md.j2           # A catalog id or a published address given to a file-based skill: the bridge include, whole (rendered per target; read by pipelex-design, pipelex-edit and pipelex-organize)
│       ├── frontmatter.md.j2          # Common YAML frontmatter (include-only)
│       ├── mcp-requirements.md.j2     # The MCP-backed skills' two stops, each pointing at credentials.md (include-only)
│       ├── validate-call.md.j2        # How a bundle is submitted: the file set (runs/ excluded), the path form of `files` and the workshop's refusal of a path outside its directory; the catalog's save sets what it says of the inline form (include-only)
│       ├── project-root.md.j2         # Where a project starts: the project markers design, integrate and catalog share (include-only)
│       ├── git-ignore.md.j2           # Keeping the user's data out of git before it is written: check, `.gitignore` entry, check again, tracked-path guard — inputs, lab and run (include-only)
│       ├── skill-dir.md.j2            # Codex and Vibe: defines the `<skill-dir>` placeholder a skill names its own files by; nothing on Claude (include-only)
│       ├── stale-types-notice.md.j2   # A bundle change may have outdated a generated tree, in one wording (include-only)
│       ├── saved-copy-notice.md.j2    # The linked saved method does not have this change; `/pipelex-catalog` compares the two and updates it (include-only)
│       ├── catalog-id-pointer.md.j2   # The pointer design, edit and organize place at a catalog id, with the bridge's two guards (include-only)
│       ├── catalog-id-bridge.md.j2    # How a file-based skill reaches a catalog id: the linked directory, or the pull (include-only; included by shared/catalog-id.md alone)
│       └── pipefunc-warning.md.j2     # PipeFunc is experimental on the hosted plane (include-only)
├── hooks/
│   ├── hooks.json.j2                # Claude PostToolUse hook config
│   ├── codex-hooks.json.j2          # Codex PostToolUse hook config (plugin-bundled)
│   ├── vibe-hooks.toml.j2           # Mistral Vibe post_tool hook config
│   ├── check-mthds.sh.j2            # Claude wrapper (fail-open guard → check.mjs)
│   ├── check-mthds-codex.sh.j2      # Codex wrapper (apply_patch envelope → check.mjs)
│   ├── check-mthds-vibe.sh.j2       # Vibe wrapper (post_tool payload → check.mjs)
│   └── assets/check.mjs             # Vendored wasm+API validation bundle (static asset, built in pipelex-sdk-js)
└── mcp/
    └── vibe-mcp.toml.j2             # Vibe [[mcp_servers]] fragment: the workshop launcher (Vibe has no plugin manifest)
skills/                        # SOURCE OF TRUTH for static (non-templated) skill assets — references/ and scripts/ — copied verbatim into every target, executable bits kept
├── pipelex-explain/references/                         # not-on-disk.md — a catalog id or a published address, read before the first call on one
├── pipelex-design/references/                          # stepwise.md — signature-driven construction; re-entry.md — a structural change to an existing method; each read on its condition (the language reference it reads before every write is the shared writing-mthds.md)
├── pipelex-synthetic-inputs/references/                # pdf.md, png.md, office.md — runnable recipes, executed by tests/recipes; photograph.md — a photograph generated by `gpt-image-2` through the workshop, read at step 1; venv.md — the venv rung, read when `uv` is not on PATH, its block executed by tests/recipes too
├── pipelex-inputs/references/                          # synthetic.md, user-data.md — the strategies and their worked examples; published-address.md — a method_ref target; prepare-errors.md — prepare's input_domain errors, the size limit's terminal branch included; each read on its condition
├── pipelex-run/references/                             # published-address.md — a method_ref target, read at step 1; failed-run.md — the failure routing, read before a failed run is routed; linked-run.md — a linked run refused at method_id
├── pipelex-lab/references/                             # frame.md — the questions, the capability map and a candidate's shape, read at the first move; key.md — the answer key's format, read before a key is written; log.md — the log, the regression rule and the scorecard, read before the first entry
├── pipelex-catalog/references/                         # python.md — which .py files a PipeFunc bundle sends, read at Save step 3; conflict.md — a save refused at expected_updated_at; unknown-id.md — an error at method_id, from a save or a pull; each read on its condition
├── pipelex-integrate/references/                       # typescript.md, python.md — detection, call-site templates, list narrowing, what the results carry; refresh.md, harness.md, signature-fallback.md, orphans.md, gate-failures.md — the branches, each read on its condition; codegen-check.mjs, codegen_check.py — the offline gates copied into TS and python-pydantic projects
└── pipelex-scaffold/                                   # references/: initializers.md, the ecosystem initializers and the env verdict's words; uncreated-copy.md, a method-app copy `make create` has not run in; version-managers.md and github.md; each read on its condition; scripts/: commit-pristine.sh and write-env-file.sh, the initializer branch's pristine commit and env file, run by path
pipelex/                       # Claude prod plugin (generated, checked in)
pipelex-codex/                 # Codex plugin (generated, checked in)
pipelex-vibe/                  # Mistral Vibe target (generated, checked in; loaded via skill_paths; mcp/vibe-mcp.toml copied into ~/.vibe/config.toml)
scripts/
├── gen_skill_docs.py          # Template renderer (multi-target)
├── check.py                   # Validation / freshness / packaging checks, the hook bundle's provenance guard included
├── check_hook_fresh.py        # Release gate: the vendored check.mjs against npm's latest engine and a rebuild in ../pipelex-sdk-js
└── hook_bundle.py             # Reads the hook bundle's provenance banner and compares bundles below it
tests/unit/                    # Unit tests for renderer + checks, and the hook's sweep over the corpus
tests/data/mthds-corpus/       # Vendored MTHDS Test Corpus (generated by the workspace's corpus sync; never edited here)
tests/recipes/                 # Opt-in: executes the synthetic-inputs recipes (`make test-recipes`)
.github/workflows/             # CI — see docs/ci.md
docs/                          # repo documentation (install per agent, skills and tools, hooks, development, build targets, CI, decisions)
Makefile  pyproject.toml  uv.lock  README.md  CHANGELOG.md  LICENSE
```

## Build System

Multi-target build. Templates in `templates/` are rendered with variables from TOML config in `targets/`; each target produces a separate plugin output. Generated outputs are checked in. See `docs/build-targets.md` for full architecture.

### Key commands

```bash
make build           # Build all targets (prod + codex + mistral-vibe)
make check-shared    # Shared checks + template freshness + lint/type checks
make check-claude    # Claude marketplace consistency checks
make check-codex     # Codex packaging consistency checks
make check           # Run all of the above
make agent-check     # Full quality gate for agents (fix imports + format + lint + check)
make test            # Run unit tests
make test-recipes    # Execute the shipped synthetic-inputs recipes (opt-in; runs uv, downloads packages)
make agent-test      # Run unit tests quietly (output only on failure) — prefer this
make gen-skill-docs  # Build default target (prod); use TARGET=codex for others
make vendor-hook     # Rebuild check.mjs in ../pipelex-sdk-js and copy it into templates/hooks/assets/
make check-hook-fresh  # Release gate: fail when check.mjs is behind npm's tools-wasm or a rebuild in ../pipelex-sdk-js
```

### Editing workflow

1. Edit `.j2` files in `templates/` (never edit generated `pipelex*/` outputs directly — they're regenerated).
2. Run `make build` to regenerate all targets.
3. Run `make check` (or `make agent-check`) to validate.

**A block several skills say word for word lives in one include.** The MCP requirements' two stops, the submission convention (the file set and the `files` path form), the project-root markers, the stale-types notice, the saved-copy notice, the catalog-id pointer and bridge, the PipeFunc warning and the ignore procedure that keeps the user's data out of git are include-only partials under `templates/skills/shared/`; a skill sets what it words differently with `{% set %}` and includes the rest. Never paste one of those blocks into a new skill — `tests/unit/test_gen_skill_docs.py::TestSharedSkillIncludes` fails when a block has more than one source. The partials, their parameters and the two whitespace mechanics are in `docs/build-targets.md`.

**Every skill is written to the read-before-act rule, and fits under the compaction ceiling.** Of each sentence ask what happens if the model never reads it: a **guard** (skipping it loses something unrecoverable, sends something off the machine, spends credit, or is silently wrong) stays in `SKILL.md` once, at its step, and is registered in `tests/unit/test_skill_guards.py`; a **branch** moves to `skills/<skill>/references/` behind a pointer placed at its condition, read before acting; a **stop** is one row of the stop table; **rationale** goes to `docs/decisions.md` and ships nowhere. A procedure whose text is its correctness ships as a script under `skills/<skill>/scripts/`. `make check` fails every rendered `SKILL.md` over 13,000 characters — what Claude Code keeps of a skill after a compaction — and a link that resolves to nothing or a shipped reference, script or shared file nothing names. The shape and the checks that hold it are in `docs/build-targets.md`, "The size of a skill"; the campaign that set them is `wip/skill-size-diet/`.

CI repeats the read-only half of that loop on every pull request — `make check` and `make agent-test` — with the branch-flow guard and the release-only version and changelog gates beside them. `docs/ci.md` says which workflow runs when, what each check means, and which of them is not reporting yet.

### Template variables (trimmed set)

Variables are defined in `targets/defaults.toml`, overridable per-target in `targets/<name>.toml`. The CLI-free posture keeps this set small:

- `marketplace_name` — `pipelex-plugins`
- `platform` — Claude / Codex / Vibe
- `harness_name` — display name of the harness
- `skill_dir` — where a skill's own files are, for a sentence that names one by path: `${CLAUDE_SKILL_DIR}` on Claude, which Claude Code substitutes; `<skill-dir>` on Codex and Vibe, which substitute nothing, defined in one sentence by `templates/skills/shared/skill-dir.md.j2` before its first use. A verbatim copy is a `cp "{{ skill_dir }}/references/…"` run from the user's project, never a read and a rewrite; `pipelex-integrate`'s gate copy is its first user. See `docs/build-targets.md`, "The skill directory"
- `mcp_server` — a table (`[vars.mcp_server]`: `command`, `args`, `env_vars`, plus `user_config` sub-tables) describing the local workshop launcher that the Claude and Codex manifests and the Vibe `mcp/vibe-mcp.toml` fragment bake; `env_vars` lists the variable *names* Codex forwards into the spawn, and `user_config` becomes the Claude manifest's `userConfig` (enable-time prompt for the API key / base URL, injected into the MCP spawn env as `PIPELEX_PLUGIN_*` — which the `launch-pipelex-mcp.sh` wrapper promotes to `PIPELEX_*` only when non-empty, so an unfilled option never shadows a shell-exported key — and delivered to the hook as `CLAUDE_PLUGIN_OPTION_*`)
- `floors` — a table (`[vars.floors]`) of the minimum versions the skills state to the user: `pipelex_sdk_js`, `pipelex_sdk_py`, `pipelex_mcp`, `node`, `python_min`, `python_max`. `pipelex-integrate` and `pipelex-scaffold` read them as `{{ floors.<key> }}`, so a bump is one edit. **`pipelex_mcp` is a ceiling, not a floor** — it names the last workshop release that *predates* the main-pipe signature, so bumping it means re-reading the sentence rather than renumbering it. The static references under `skills/` are copied verbatim and keep their literals; `scripts/check.py`'s `check_version_floors` holds them to the table, and **every static occurrence needs its own entry in `VERSION_FLOOR_STATIC_REFS`** — one left off the list drifts silently on the next bump, which `tests/unit/test_check.py` sweeps for. A misspelled key is the renderer's to catch: the build runs under `StrictUndefined` and fails naming the template and the attribute, rather than rendering the empty string with every gate green. **A template never spells a floor** — the check refuses a floor's literal value anywhere under `templates/`, because a hardcoded number renders right today and drifts at the next bump. Bump the table, `make build`, `make check`, and the check names what still says the old number.

Deliberately **not** carried over from `mthds-plugins`: `min_mthds_version`, `env_check`, `can_run_methods`, `session_start_hook`, and all `*_install_cmd` / `*_upgrade_cmd` variables. Reintroduce a variable only when a skill or hook actually branches on it. Don't port dead switches.

### Version management

- **Plugin version**: source of truth is `targets/prod.toml [plugin].version`; `pipelex/.claude-plugin/plugin.json` is generated by the build. Codex/Vibe versions live in their target TOMLs.
- **Marketplace version**: `.claude-plugin/marketplace.json metadata.version` — bumped on any release.
- Versions start at **0.1.0**.

## Local development with Claude Code

To dogfood local changes instead of the published GitHub plugin, point the `pipelex-plugins` marketplace at this checkout. Removing a marketplace uninstalls its plugins and re-adding does not auto-reinstall, so the `install` step is required:

```
/plugin marketplace remove pipelex-plugins
/plugin marketplace add /absolute/path/to/pipelex-plugins
/plugin install pipelex@pipelex-plugins
/reload-plugins
```

The marketplace serves the **prod** output (`pipelex/`). Iteration loop after editing any `.j2` template or `targets/*.toml`: `make build`, then `/reload-plugins`.

Session-only alternative that leaves global config untouched: `claude --plugin-dir /absolute/path/to/pipelex-plugins/pipelex`.

## PostToolUse Hook — CLI-free wasm+API pipeline

Claude Code and Codex run a `PostToolUse` hook against `.mthds` files after every edit; Mistral Vibe's equivalent is `post_tool` (stable hooks API, Vibe 2.21.0+). Nothing shells out to `plxt` or `mthds-agent`: each target ships a thin fail-open wrapper script that runs the shared vendored `check.mjs` bundle (built in `pipelex-sdk-js`) — local lint and format via the inlined `@pipelex/tools-wasm` engine (offline, format writes back in place), then the bundle verdict from `POST /v1/validate` through `@pipelex/sdk` when `PIPELEX_API_KEY` is set. Fail-open: no Node → the whole hook passes silently; no key / API unreachable → the local lint/format verdicts still apply and only the validate stage is skipped. Full details, failure-posture table, and the re-vendor procedure (`make vendor-hook`) in `docs/hooks.md`.

### Codex specifics (verified against Codex 0.144.4, incl. live sessions)

The Codex hook command is `"${PLUGIN_ROOT}"/hooks/check-mthds-codex.sh`, the root in double quotes because Codex substitutes it into the text its shell runs (every harness's hook command quotes its path, so a plugin root holding a space still works; `tests/unit/test_hook_commands.py` holds them to it). Its matcher is `^(apply_patch|Bash)$`, and the wrapper feeds the `apply_patch` envelope in `tool_input.command` to `check.mjs --platform=codex` (several `.mthds` files per patch; outcomes merged, any block wins). Engine facts that make this work:

- The canonical feature key is **`hooks`**, marked `Stage::Stable` and **enabled by default** (`codex_hooks` is a deprecated alias, still honored in 0.144.4; `plugin_hooks` is not an alias but an obsolete independent opt-in, removed in Codex 0.134 and formally `Stage::Removed` since 0.144).
- Native per-source **trust model** (`[hooks.state]` trusted hashes; `--dangerously-bypass-hook-trust` for automation).
- `PostToolUse` officially fires for `apply_patch` edits and MCP tool calls — which de-risks the `.mthds`-on-edit hook. A patch run through the shell is reported as `Bash`, which the matcher admits and the wrapper's pre-filter drops unless a patch header names a `.mthds` file and the payload names the patch program; but one Codex intercepts (exactly `apply_patch <<'EOF'`, or `cd <dir> && ` before it) emits no `PostToolUse` at all, verified on 0.153.4, and cannot be checked. The bundle reads a shell patch's relative paths from wherever the script's `cd` commands leave it, starting at the payload's `cwd`, checks such a file only when it holds the lines the patch added, and names a path it could not confirm in a non-blocking note, since the payload never carries the `workdir` a script may have run in. `docs/hooks.md`, "Patches run through the shell", says which forms reach the hook and why.
- Standardized block protocol (`{"decision":"block","reason":...}` or exit 2 + stderr) maps cleanly onto the Stage 3 decision model.
- Installed plugins run from a **cache copy** (`$CODEX_HOME/plugins/cache/...`), and `codex plugin marketplace upgrade` refreshes Git snapshots only — propagate local edits with `make codex-refresh` (an idempotent `codex plugin add`).

So there is nothing to enable — the bundled hook loads on its own (hooks are Stable/default-on) and only needs trusting on first run; no `[features] hooks = true` line and no `apply-config` command. See `docs/decisions.md` and `docs/hooks.md`.

## Key dependency

The plugin imports nothing and requires no install. Validation rides on the vendored `check.mjs` bundle (wasm engine + `@pipelex/sdk` → hosted API) and, for the MCP-backed skills (`pipelex-design`, `pipelex-organize`, `pipelex-edit`, `pipelex-inputs`, `pipelex-run`, `pipelex-catalog`, `pipelex-integrate`), on the plugin-declared `pipelex-mcp` server (tools `mthds_validate` / `mthds_inputs_template`; `mthds_codegen`, whose write arm — `output_dir`, relative to the workshop's working directory — writes `pipelex-integrate`'s generated trees to disk so no artifact byte passes through the model; `mthds_prepare_inputs`, which uploads `pipelex-inputs`' file-bearing values to Pipelex storage and rewrites them to `pipelex-storage://` references so a run can reach them; plus the `mthds_run` family, which runs a method only in `pipelex-run` — `pipelex-inputs` ends by offering the run and hands it over, and `pipelex-synthetic-inputs` calls it for one thing, the image generation that makes a photograph — and `mthds_list_methods` / `mthds_save_method` / `mthds_get_method`, which are `pipelex-catalog`'s: the last two are **workshop-only**, the save reads, validates and stores one bundle in a single call and finishes by writing the `pipelex-method.json` link that makes the next save an update, and the get brings a saved method's sources to disk. Both refuse rather than overwrite, and the link file is the workshop's to write — no skill writes one. `mthds_get_method`'s **inline** arm is `pipelex-explain`'s instead, and the split is the whole of it: called with an `output_dir` it writes a pull, which is `pipelex-catalog`'s gesture, and called without one it returns the source for a skill that writes nothing — which is why a strictly read-only skill can hold this tool at all; declared in the Claude and Codex manifests, and shipped on Vibe as the `mcp/vibe-mcp.toml` config fragment the user copies into `~/.vibe/config.toml`). The baked declaration is the **local workshop launcher** — `npx -y @pipelex/mcp@latest` over stdio, from the `[vars.mcp_server]` block in `targets/defaults.toml` — never a hosted URL: the hosted console is a connector users add in their host's own UI (see `docs/install.md`, "Which app takes what", and `docs/decisions.md`). Credential delivery: on Claude the manifest's `userConfig` prompts for the API key / base URL at enable time (keychain-stored) and the MCP entry spawns the `launch-pipelex-mcp.sh` wrapper, which receives them as `PIPELEX_PLUGIN_*` via `${user_config.*}` substitution and promotes each to `PIPELEX_API_KEY`/`PIPELEX_BASE_URL` **only when non-empty** — the canonical credential channel (required for Claude Desktop, which carries no shell env), with the non-empty guard keeping an unfilled option from shadowing a shell-exported key; injecting `PIPELEX_*` directly instead makes an empty option surface as a config-class `Unauthorized` that hard-stops every MCP-backed skill; on Codex the manifest forwards `PIPELEX_API_KEY`/`PIPELEX_BASE_URL` by name via `env_vars` because Codex whitelist-filters MCP spawn env; on Vibe the user writes the key into the fragment's `env` table, because Vibe also spawns stdio servers with a minimal environment and expands no variables in its config. Dev override: point `command`/`args` at a local checkout in `targets/defaults.toml` + `make build` on Claude; a same-named `[mcp_servers.pipelex]` entry in `~/.codex/config.toml` on Codex.

**`pipelex-synthetic-inputs` depends on none of that for code-rendered files.** Everything but a photograph is MCP-free — no tool, no key, no Pipelex service — and a photograph alone needs the workshop, whose absence stops that one file and nothing else. `pipelex-scaffold` is the other skill that declares no MCP tool: git, the method-app family's initializer and `make serve`, the ecosystem's initializers and its own two scripts are all it uses, and it leaves a method app running and hands every other project it creates to `pipelex-integrate`. For code-rendered files, the only dependency is a Python the skill can reach: `uv` with ephemeral `--with` packages on the normal rung, and a venv it creates itself under `${XDG_CACHE_HOME:-$HOME/.cache}/pipelex-plugins/synth-venv` when `uv` is absent. Swapping the runner line is the *only* difference between the two rungs, and `tests/recipes` proves it by running real recipes through both. When neither rung is reachable the skill stops with the exact missing piece and, called from `pipelex-inputs`, returns no path so that one input is left unfilled rather than aborting the flow. Keep it and `pipelex-scaffold` out of the `MCP_SKILLS` tuple in `tests/unit/test_gen_skill_docs.py`, and `pipelex-explain` and `pipelex-lab` with them — the lab frames and writes keys without the workshop and stops only before its loop. For explain, the workshop is **optional** — it adds a verdict line to a bundle on disk, reads a saved method's source in full through `mthds_get_method`'s inline arm, and is the only way to reach a catalog id or a published address at all, but its absence never stops the skill from explaining local source. A workshop older than the release that brought `mthds_get_method` answers the other tools without it, so there a catalog id falls back to contract level, which is a narrower explanation and not a stop. The tuple asserts a hard stop, which is a different contract.
