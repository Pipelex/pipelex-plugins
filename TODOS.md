# TODOS — port the design & inputs skills to pipelex-plugins (CLI-free, MCP-backed)

**Kickoff:** `../wip/plugins/pipelex-plugins-build-skills-kickoff.md` (workspace root). This doc is the phased implementation plan that kickoff requires; it is the cold-start tracker — keep it current at every checkpoint (completed phases, decisions taken, open questions, code state).

**Branch:** `feature/Build` in `pipelex-plugins/`. Never modify `mthds-plugins/`.

## Mission (one paragraph)

Port two skills from `mthds-plugins` into this repo, adapted to the CLI-free posture: `mthds-recursive` → **`pipelex-design`** (retire the "recursive" vocabulary for design-oriented wording everywhere — name, prose, headings, reference filename; methodology unchanged) and `mthds-inputs` → **`pipelex-inputs`** (the input-preparation companion `pipelex-design`'s Deliver phase hands off to). Nothing else. The skills must need no local CLI at any step: lint/format is enforced by the plugin's existing PostToolUse hook (vendored `check.mjs`); validation and input-template extraction go through the plugin-declared **`pipelex-mcp`** server's tools `mthds_validate` and `mthds_inputs`. The port is done only when `pipelex-design` works end-to-end in a real session against a running `pipelex-mcp`, including the Deliver-phase handoff into `pipelex-inputs`.

## Read first (cold start)

- `../wip/plugins/pipelex-plugins-build-skills-kickoff.md` — the mission, settled decisions, porting rules, gates (source of truth for scope).
- This repo: `CLAUDE.md`, `docs/build-targets.md`, `docs/hooks.md`, `docs/decisions.md`.
- Source skills (reference only, never modify): `../mthds-plugins/templates/skills/mthds-recursive/SKILL.md.j2`, `../mthds-plugins/templates/skills/mthds-inputs/SKILL.md.j2`, `../mthds-plugins/skills/mthds-recursive/references/recursive-cheat-sheet.md`.
- MCP server contract: `../pipelex-mcp/{README.md,SPEC.md,CLAUDE.md}` — tool input/output shapes, verdict discipline, dev commands.
- Trackers: `../wip/devx/pipelex-plugins-foundations.md` (repo history), `../wip/plugins/networked-hook.md` (how check.mjs is built/vendored).

## Facts established during planning (verified 2026-07-14)

- **Claude plugin MCP declaration:** `.claude-plugin/plugin.json` supports an inline `mcpServers` object; `${VAR:-default}` env expansion is honored in the `url` field of plugin MCP configs; plugin servers auto-connect at session start (no approval step for plugin-bundled servers). Tools appear to the model as `mcp__plugin_<plugin>_<server>__<tool>` — for plugin `pipelex`, server `pipelex`: `mcp__plugin_pipelex_pipelex__mthds_validate`. (Docs: code.claude.com/docs/en/plugins-reference, .../mcp.)
- **MCP tool contracts** (from `../pipelex-mcp/SPEC.md`): both tools take `files: [{content, uri?}]`. `mthds_validate` adds `include_graph?` (default true) and returns `{status, is_valid, is_runnable, pending_signatures[], available_view_specs[], validation_errors?, errors?}` in `structuredContent` + a Markdown summary in `content` (the API's `rendered_markdown`, incl. the `## Pending signatures` backlog). `mthds_inputs` adds `pipe_ref?` (qualified `domain.pipe_code`, defaults server-side to the closure's `main_pipe`), `explicit?` (default false = light shape), `format?` (default json) and returns `{status, is_valid, pipe_ref?, inputs?/inputs_toml?, validation_errors?, errors?}` + a summary that repeats the template fenced. Verdict discipline: produced verdict = `status:"ok"` discriminated on `is_valid`; `status:"error"` + `errors[]` (classes `input_domain`/`config`/`runtime`, each with optional `hint`) = no verdict.
- **The MCP always validates leniently** (`allow_signatures: true` server-side). There is no strict-validation call. The finalize gate is a produced verdict with `is_runnable: true` and empty `pending_signatures` — equivalent to the old strict pass.
- **Light template shape** (canonical `inputs.json` format, settled 2026-07-14; implementation: `../pipelex/pipelex/core/pipes/inputs/input_renderer.py`): Text-refining input → bare string; Number → bare number; YesNo → bare boolean; Date → bare date string; Image/Document → bare URL/path string; structured concept → its content dict (fields directly, no envelope); declared-multiple → the same wrapped in a list; only Dynamic/out-of-matrix inputs keep the ceremonial `{concept, content}` envelope. The tool's returned template is authoritative — skills fill it in, never hand-invent shapes.
- **Static skill references** live in `<repo>/skills/<skill>/references/` and are copied verbatim into every target output by `setup_static_assets()` (no Jinja, so keep them platform-neutral). This repo has no `skills/` dir yet — create it for `pipelex-design`.

## Design decisions (settled here — record D1–D4 in `docs/decisions.md` during implementation)

- **D1 — MCP config location: inline `mcpServers` in the generated Claude `plugin.json`.** `make_plugin_json()` injects, for Claude-platform targets only: `{"mcpServers": {"pipelex": {"type": "http", "url": "${PIPELEX_MCP_URL:-<mcp_server_url>}"}}}`, sourced from a new `mcp_server_url` template var in `targets/defaults.toml` (overridable per target). Rationale: one manifest file, no extra generated artifact; env expansion makes dev/prod switching rebuild-free. The baked default is a **placeholder** (`https://mcp.pipelex.com/mcp`) until `pipelex-mcp` has its deployed Alpic URL — until then always use the `PIPELEX_MCP_URL` override. Codex/Vibe manifests get **no** MCP entry (plugin-bundled MCP support unverified there); their one-time manual registration is documented in the README (Codex: user-level `[mcp_servers]` in `config.toml`; Vibe: TBD).
- **D2 — MCP-unavailable posture: stop, never silently skip.** Unlike the fail-open hook, these skills *require* their MCP tools. If the tool is absent from the session (harness didn't connect the plugin MCP server) or a call returns `status: "error"` with class `config` (server unreachable / upstream misconfigured / auth), the skill **stops** with a one-line setup instruction: check the plugin's MCP server connection (`/mcp` in Claude Code), or point `PIPELEX_MCP_URL` at a running server; surface the error's `hint` when present. `PIPELEX_API_KEY` is NOT a client-side concern — the MCP holds the upstream key server-side (`MTHDS_API_KEY` in its hosting env).
- **D3 — graph steps adapted honestly.** `dry_run.html` is gone. On a valid verdict `mthds_validate` reports `available_view_specs: ["dry_run_graph"]`; only view-capable hosts (claude.ai, ChatGPT) render the interactive graph — Claude Code's terminal does not. The skills mention the graph conditionally ("where your host renders MCP views, an interactive method graph accompanies valid verdicts") and never promise a visible artifact in the terminal. The review surface in terminal hosts is the validation Markdown summary (verdict + pending-signatures backlog).
- **D4 — no ported CLI-era shared references.** `error-handling.md`, `mthds-agent-guide.md`, `python-execution.md` stay behind. The MCP tools are self-describing (schemas + verdict discipline travel with the server); error recovery is covered inline in each skill in a few lines (branch on `status`/`is_valid`; `validation_errors[]` on the invalid arm; `errors[].hint` on the no-verdict arm; class `config` → D2 stop). Shared links go to the two references this repo already ships: `../shared/mthds-reference.md`, `../shared/native-content-types.md`.
- **D5 — finalize gate without strict validation.** `pipelex-design` Step 3 becomes: re-validate via `mthds_validate` and confirm `is_valid: true`, `is_runnable: true`, `pending_signatures: []`. Same guarantee as the old strict pass (see Facts).
- **D6 — bundle submission convention.** Every validate/inputs call submits the whole library: all `.mthds` files in the bundle directory, `content` from disk, `uri` = path relative to the bundle dir. (Mirrors the hook's `-L`-parity gather; a broken sibling fails the verdict and the summary names it via `uri`.)

## Porting rules (from the kickoff — don't relitigate)

Templates in `templates/skills/` are the only source of truth (`.j2`); generated `pipelex*/` outputs are never hand-edited; `make build` renders all three targets. Drop dead conditionals (`env_check`, `can_run_methods`, `remote_storage_inputs`, Step 0 preambles) and cross-references to skills that don't exist here (`/mthds-runner-setup`, `/mthds-build`); `/mthds-inputs` refs become `/pipelex-inputs`. `SKILL.sandbox.md.j2` overlay stays behind. Reintroduce a template variable only if something branches on it (`mcp_server_url` does — D1). Brand rule: skills are `pipelex-*`; language content stays MTHDS-branded. Examples use the light template shape everywhere — never the `{concept, content}` envelope (legacy, `explicit: true` only).

## Gates (before every commit)

`make build` + `make agent-check` + `make agent-test` green; `docs/` and `CHANGELOG.md` updated in the same change; this plan updated at checkpoints.

---

## Phase 0 — MCP server wiring in the build system

- [x] Add `mcp_server_url` to `targets/defaults.toml` (placeholder `https://mcp.pipelex.com/mcp`; per D1) with a comment marking it a placeholder until the Alpic deploy.
- [x] Extend `make_plugin_json()` in `scripts/gen_skill_docs.py`: for Claude-platform targets, inject the `mcpServers` entry per D1 (URL wrapped as `${PIPELEX_MCP_URL:-<mcp_server_url>}`). Codex/Vibe unchanged.
- [x] Unit tests: Claude plugin.json carries the mcpServers entry with the env-default wrapper; Codex plugin.json does not.
- [x] `docs/decisions.md`: record D1 + D2 (and D3–D6 pointers); `docs/build-targets.md`: add `mcp_server_url` to the variables table.
- [x] `make build` + gates green.

## Phase 1 — `pipelex-design` (from `mthds-recursive`)

- [ ] `templates/skills/pipelex-design/SKILL.md.j2` — port with:
  - [ ] Rename + de-recursive the vocabulary everywhere (name `pipelex-design`, "design"/"top-down design"/"stepwise refinement" wording; frontmatter description rewritten; keep `disable-model-invocation: true` for non-codex platforms and the shared frontmatter include).
  - [ ] Drop Step 0 env-check block, the "CLI is required" framing, the backend-setup note, and `can_run_methods` branches. Files are written normally; note the plugin's PostToolUse hook lint/formats every `.mthds` edit (no `plxt` instructions).
  - [ ] Replace every `mthds-agent validate … --allow-signatures --graph` step with an `mthds_validate` call per D6; read the backlog from the Markdown summary's `## Pending signatures` (mirrored in `pending_signatures[]`); branch per the verdict discipline; D2 stop on missing tool / config error.
  - [ ] Step 3 Finalize per D5; Step 4 Deliver: input schema via `mthds_inputs` (show the light template, do NOT save `inputs.json`), graph note per D3, handoff to `/pipelex-inputs`.
  - [ ] Fix reference links: `references/design-cheat-sheet.md`, `../shared/native-content-types.md`; drop error-handling/mthds-agent-guide links (D4).
- [ ] `skills/pipelex-design/references/design-cheat-sheet.md` — port `recursive-cheat-sheet.md` renamed and de-recursived; §6 PipeSignature: replace the lenient/strict `mthds-agent` bash block with the MCP validation semantics (always-lenient tool; runnable gate per D5).
- [ ] `make build`; verify rendering across all three targets; gates green.
- [ ] CHANGELOG + docs touched in the same change; commit.

**CHECKPOINT 1** — `pipelex-design` renders on all targets, gates green. Update this doc (status, deviations, open questions) before moving on.

## Phase 2 — `pipelex-inputs` (from `mthds-inputs`)

- [ ] `templates/skills/pipelex-inputs/SKILL.md.j2` — port with:
  - [ ] Keep: mode selection, strategy detection heuristics, the four strategies (template/synthetic/user-data/mixed), file-type → concept mapping tables, matching rules, worked examples (rewritten to light shape).
  - [ ] Step 2 collapses to: call `mthds_inputs` per D6 (defaults: no `explicit`, no `format`), branch on `is_valid`; D2 stop on missing tool / config error. The returned template is authoritative.
  - [ ] Rewrite ALL examples and the strategy steps around the **light shape** (bare string / number / boolean / URL-or-path string; structured → content dict; lists of those). Placeholder rule for file-ish inputs stays (`<VARNAME-url-or-path-relative-to-this-inputs-file>`), now as the bare string value.
  - [ ] Drop: `remote_storage_inputs` branches (`mthds-agent inputs upload` — no storage tool yet), `can_run_methods` image-synthesis section, the "Validate & Run" offer-to-run tail, Step 0/preamble, error-handling/mthds-agent-guide references.
  - [ ] Replace `"$(uv tool dir)/pipelex/bin/python"` reportlab invocations with environment-neutral ones (`uv run --with reportlab python`, plain `python3` fallback); keep the docx/xlsx skill-or-python fallbacks (already environment-neutral).
  - [ ] Don't duplicate "Native Concept Content Structures" — link `../shared/native-content-types.md` and keep only a short light-shape mapping note.
  - [ ] Path-resolution rule (relative to `inputs.json`) and `<output_dir>/inputs/` copying convention stay.
- [ ] `make build`; all targets render; gates green; CHANGELOG; commit.

**CHECKPOINT 2** — both skills exist and render on all targets, Deliver-phase handoff wired both ways, gates green. Update this doc before live verification.

## Phase 3 — end-to-end verification (live session)

Setup: `cd ../pipelex-api && make run` (serves `:8081`) · `cd ../pipelex-mcp` with `MTHDS_BASE_URL=http://localhost:8081` in `.env`, `make dev` (MCP at `http://localhost:3000/mcp`) · this repo installed as local marketplace (see `CLAUDE.md` § Local development) · launch `PIPELEX_MCP_URL=http://localhost:3000/mcp claude`.

- [ ] Plugin MCP server connects from the plugin declaration; `${PIPELEX_MCP_URL:-…}` env expansion behaves as designed (baked default overridden).
- [ ] `/pipelex-design` builds a small method end-to-end: Layer-0 signature → refinement rounds draining the backlog via `mthds_validate` → finalize gate (`is_runnable: true`, empty `pending_signatures`) → Deliver shows the light input template via `mthds_inputs`.
- [ ] PostToolUse hook coexistence: `.mthds` writes get lint/format from the hook while the skill validates via MCP.
- [ ] Deliver handoff into `/pipelex-inputs`: produces a light-shape `inputs.json` next to the bundle.
- [ ] D2 posture in practice: with the MCP down (or a config-class error), the skill stops with the one-line instruction, no silent skip.
- [ ] Update this doc; close out.

**CHECKPOINT 3 (close)** — port verified end-to-end; plan complete. Record the verification matrix and any environment caveats here.

## Left for later (out of scope here)

- Deployed Alpic URL → set `mcp_server_url` in target TOMLs, `make build` (D1 placeholder swap). Blocked upstream: `pipelex-mcp` must publish/re-pin its `file:`-linked deps before `alpic deploy`.
- Codex/Vibe MCP registration verification (empirical, like the Codex hooks got); until then README documents manual registration.
- Runtime-side acceptance of light-shape `inputs.json` (separate workstream).
- Migration of the MCP's upstream from local `pipelex-api` to the hosted API.
