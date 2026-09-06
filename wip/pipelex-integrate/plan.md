---
status: active
item: L-260830-344594
---

# Plan — `pipelex-integrate`: the implementation tracker

**Written 2026-08-30** as the execution tracker for [`design.md`](design.md). It schedules; it does not re-argue — when this file and the design disagree, the design wins unless the disagreement is logged under "Deviations" below. Section references (`§N`) are to the design. Ledger item `L-260830-344594`; the phases name the follow-up items they wait on or file.

**Status: active** since 2026-08-30, when the ten decision boxes of `design.md` were ratified as written (Phase 0). Work proceeds from Phase 1.

## How to work a phase

- `ledger claim L-260830-344594` before touching code; renew the claim once you are on the working branch.
- The working branch is `feature/Codegen` (already created for this item); the PR targets `dev` and its body carries `Closes L-260830-344594`. A merged PR is landed with `/ledger-land`.
- **This checkout is shared with other sessions.** Stage the files you touched explicitly (`git add <path>`), never `git add -A`; the branch already carries uncommitted work on `pipelex-design` / `pipelex-edit` from another piece of work, and a phase here must not sweep it into its commit. Never run a formatter over files you did not author.
- Templates are the source of truth: edit `templates/skills/…/*.j2` and `skills/pipelex-integrate/references/*`, then `make build`; never edit `pipelex*/` outputs. Before pushing: `make agent-check` and `make agent-test`.
- `mthds_codegen` is **unreleased in `@pipelex/mcp`** at writing. Development and dogfood run against the local `../pipelex-mcp` checkout through the repo skill `/pipelex-mcp-source`; **switch back to `@latest` before any commit** and let that skill confirm no dev switch leaked into `targets/defaults.toml`.
- Version discipline: everything accumulates under `[Unreleased]` in `CHANGELOG.md`; the release phase cuts the heading and bumps the version through `/release`.
- At each checkpoint: tick the boxes, record the SHAs and versions outcomes landed in (never live git state), reconcile deviations into the later phases, and leave this file cold-start ready.

## Standing context for every phase

- **The write arm is the only arm the skill uses** (§4.4). If a dogfood run ever tempts a "just write the bytes from the response" fallback, that is a bug in the run, not a feature to add.
- **The generated tree is never opened for editing, formatted, or linted** — by the skill, and by the session working this plan. A dogfood run that reformats a generated file has invalidated its own verdict; regenerate and start the scenario again.
- **Two upstream items can land during this work and each deletes a piece of it.** `L-260820-ee327d` (ts-zod `.nullish()`) deletes the wire-output helper (§4.8); `L-260830-4e43cd` (Python offline check) deletes the Python asymmetry paragraph (§4.5). Phases 1 and 4 each carry a box to re-check both before proceeding, and a landed item is recorded under "Decisions taken along the way" with what was removed.
- **Ledger ids never appear in user-facing skill text or reports.** They belong in this tracker, the design, and `docs/decisions.md`; the skill's report to a user says "the Python SDK has no offline drift check yet", never the item that tracks it.

## Phase 0 — ratify, file, link

No code. Owner: the session that reads the design with Louis.

- [x] `ledger claim L-260830-344594` (2026-08-30).
- [x] Walk the ten decision boxes at the end of `design.md` with Louis; record each ruling (ratified as drafted, or amended, with the amendment written into the design's section) in the box's "Ratified?" column with the date — done 2026-08-30: all ten ratified as written, no amendments.
- [x] Flip `design.md` and this file to `status: active` in the same change that records the ratification — done 2026-08-30.
- [x] File the `pipelex-mcp` follow-up from §4.3 — filed 2026-08-30 as `L-260830-e8b2e0`: promote a compact main-pipe signature — `main_pipe_ref`, input names → concept refs, output concept ref and multiplicity — from `_meta` into `structuredContent` on a valid `mthds_validate` verdict (or on `mthds_codegen`'s valid arm), with the evidence from `pipelex-mcp/SPEC.md` → "Validation Scope" (the `_meta`-only rule and its token rationale) and the §4.3 heuristic as the consumer that needs it. Its id is recorded in §8 of the design and under "Where everything is" below.
- [x] `ledger link L-260830-344594 --related L-260820-ee327d`, `--related L-260820-2ba0f4`, `--related L-260829-563e9e` (`L-260830-4e43cd` is already discovered-from) — done 2026-08-30.
- [x] `ledger ref L-260830-344594` attached `plan:pipelex-plugins/wip/pipelex-integrate/design.md` and `plan:pipelex-plugins/wip/pipelex-integrate/plan.md` beside the existing brief ref — done 2026-08-30.
- [x] `ledger validate`, then `ledger commit` — done 2026-08-30 for the filing above; re-validated after the ratification edits (the ratification changed only these two documents, not the ledger).

## Phase 1 — the skill template and its references

Owner: `pipelex-plugins`. Everything in this phase renders into all three targets; nothing in it is platform-specific except the `allowed-tools` frontmatter and the MCP-absent message, which the shared patterns already handle.

**Pre-flight**

- [ ] Re-check `L-260820-ee327d` and `L-260830-4e43cd` (`ledger show`). If either has closed and shipped in the hosted engine / the Python SDK, strike the corresponding piece below before writing it and log the deviation.
- [ ] Confirm the static-asset mechanism works end to end before relying on it: `scripts/gen_skill_docs.py` → `setup_static_assets` copies `skills/<name>/references/` into every target; `scripts/check.py` → `check_stale_references` resolves `references/…` links from a rendered `SKILL.md`; `check_no_templates_in_output` tolerates `.mjs` / `.ts` files under `skills/`. This is the **first skill in the repo to ship references**, so a root `skills/` directory does not exist yet; create it and note in `docs/build-targets.md` (Phase 2) that the mechanism is now in use.

**The template — `templates/skills/pipelex-integrate/SKILL.md.j2`**

- [ ] Frontmatter: `name`, the description from §4.11 (codebase-phrasing triggers, silent on authoring phrasings), the shared `frontmatter.md.j2` include, and on Claude the `allowed-tools` entries for `mthds_codegen`, `mthds_inputs_template`, `mthds_validate`, `mthds_list_methods`. No `disable-model-invocation`.
- [ ] "Requirements — the Pipelex MCP tools": `mthds_codegen`, `mthds_inputs_template` and `mthds_validate` required with the plugin's standard MCP-absent STOP message (copy the exact conditional block from `pipelex-inputs`, so `TestSkillFailureDiscipline.test_absent_tools_stop_message_matches_platform` passes on every target); `mthds_list_methods` soft. The `config`-class stop, with the **403 feature-gate wording** from §6 (a 403 is not a key problem).
- [ ] Mode selection: automatic default; the interactive signals; the one-question rule from §5.
- [ ] The procedure of §3, as numbered steps, each naming its MCP call, its arguments (`explicit: true` on the template call — with the sentence saying this is the deliberate exception to the plugin's light-template pin), and its verdict branches.
- [ ] The `output_dir` rule of §4.4 spelled out for the model: compute it relative to the session's initial working directory; never absolute; never ride content; the relaunch instruction on a containment escape.
- [ ] The exclusions-before-generation ordering (§3 step 5), stated as a rule with its reason.
- [ ] The orphan rule of §4.7 in the tool's own wording; never delete.
- [ ] The sidecar section: the exact `sources.json` shape of §4.6, how hashes are computed (`shasum -a 256` / `sha256sum` / `hashlib`, raw bytes), paths relative to the project root.
- [ ] The call-site section (§4.1): what one module contains, the two shared helpers, the input-type mapping table from concept ref to language type (Text → `string`/`str`, Number → `number`/`float | int`, YesNo → `boolean`/`bool`, Date → ISO string, Image/Document → `{ url }`, structured → the generated type, `[]` → arrays, `?` → optional), the `main_stuff` narrowing, the `prepareInputs` pointer for file-bearing callers, the sync-wrapper rule for synchronous Python projects. Language detail is delegated to the two reference files.
- [ ] Refresh mode as its own section (§4.10): the taken / re-derived / left-alone table, the fingerprint comparison and the restamp-only case, the "call site edited only if it no longer type-checks or the `pipe` record moved" rule.
- [ ] The verification step (§3 step 11) and the report (§3 step 12), including the Python asymmetry sentence.
- [ ] A failure table condensed from §6.
- [ ] `## Reference`: links to `references/typescript.md`, `references/python.md`, and the two shared language references.

**The references — `skills/pipelex-integrate/references/`**

- [ ] `typescript.md`: the detection signals of §5 for a TypeScript project (project root, TS-capable build, package manager, generated root, Prettier / ESLint flat and legacy / Biome exclusion edits with the exact config keys, `tsconfig` coverage, aggregate gate, call-site location, `.gitignore`); the call-site module template with the `getPipelexClient` helper and the `wireOutput` import; the `codegen:check` npm script and how to append it to `check` / a Makefile / a workflow step.
- [ ] `python.md`: the same for Python (import package discovery, `python-pydantic` vs `python-structures` per §5, uv / poetry / pipenv / pip, `[tool.ruff]` `exclude` and `extend-exclude`, Black, isort, pyright / mypy coverage, `__init__.py` creation for the generated package and each method subpackage, setuptools `packages` / `package-data` when the project is packaged, the async call-site template plus the sync wrapper, the `pipelex codegen check` wiring for the `python-structures` audience only, the asymmetry sentence for everyone else).
- [ ] `codegen-check.mjs` (§4.5): plain ESM, Node builtins + `@pipelex/sdk` only; takes generated directories as arguments; per directory reads `codegen.lock` from disk, walks recursively (pruning `node_modules`, `.git`, `dist`, `build`, `.next`), filters with `isStampableArtifactPath`, decodes strictly, runs `runCodegenCheck`, prints drifts by category; then reads `sources.json` and compares each `sources` hash against the file on disk, reporting `stale-source` with the "run `/pipelex-integrate` to refresh" remedy; exit `0` / `1` / `2` with the precedence no-verdict > drift > current; output through `process.stdout` / `process.stderr`. Header comment names what it is and that `@pipelex/sdk` upstreaming retires it.
- [ ] `wire-output.ts` (§4.8, **skip if `L-260820-ee327d` has landed**): `wireOutput(results, schema)` and the schema-guided `dropWireNulls`, trimmed from `pipelex-starter-js/src/lib/wireOutput.ts` — objects, arrays, `z.lazy`, optional-without-default only; opaque schemas passed through; a depth cap; no `server-only` import, no Next-specific error types. Header comment states it is a workaround with an expiry and what deletes it.

**Build and tests**

- [ ] `make build`; confirm `pipelex/`, `pipelex-codex/`, `pipelex-vibe/` each carry `skills/pipelex-integrate/SKILL.md` and the `references/` directory verbatim.
- [ ] `tests/unit/test_gen_skill_docs.py`: add `"pipelex-integrate"` to `TestSkillFailureDiscipline.MCP_SKILLS`.
- [ ] New `TestPipelexIntegrateDiscipline` pinning the load-bearing sentences in the real template, rendered on all three targets: `output_dir` is always passed; content is never ridden; orphans are never deleted; one directory per method; generated files are never edited or formatted; exclusions precede generation; `explicit: true` on the template call; the `method_id` warning; refresh mode leaves the call site alone unless the types moved; the 403 wording. Plus one test that the references land in every target's output.
- [ ] `make agent-check`, `make agent-test`.

**CHECKPOINT 1** — the template and references render on every target and the tests pin their rules. Record here: the commit SHA, what was struck because an upstream item landed, and anything the template could not express without a reference file.

## Phase 2 — family wiring and documentation

Owner: `pipelex-plugins`. Small, deliberate edits; each one is one sentence or one step (§7).

- [ ] `templates/skills/pipelex-edit/SKILL.md.j2` Step 7: the `sources.json` staleness notice and the `/pipelex-integrate` offer.
- [ ] `templates/skills/pipelex-design/SKILL.md.j2`: the same notice in the re-entry delivery; the one-line hand-off in "Common runnable gate and delivery" step 4 (when a `package.json` / `pyproject.toml` is in the workspace).
- [ ] `templates/skills/pipelex-inputs/SKILL.md.j2`: the one-line hand-off in the closing report.
- [ ] `docs/decisions.md`: a dated entry — the skill's scope line (§4.1), the name ruling over `pipelex-codegen` (§4.11), the `explicit: true` exception appended to the light-template decision (§4.9), the write-arm-only and never-ride-content rule (§4.4), the sidecar (§4.6), the wire-null helper with its expiry (§4.8), the gate asymmetry (§4.5), and that this is the first skill to ship `references/`.
- [ ] `CLAUDE.md` "Key dependency": add `mthds_codegen` (the write arm, `output_dir`) beside the other tools; the structure block gains the `pipelex-integrate` template and the root `skills/` directory.
- [ ] `README.md`: the skill in "What's inside" and `mthds_codegen` in the MCP server bullet; the Claude and Codex sections' skill lists.
- [ ] `docs/build-targets.md`: the `skills/<name>/references/` mechanism is now in use, with `pipelex-integrate` as the example.
- [ ] `CHANGELOG.md` `[Unreleased]` → "Added": the skill, in the changelog's existing voice (what it does, the write arm, the sidecar, the gate asymmetry, the wire-null helper and its expiry, `explicit: true`); "Changed": the three family one-liners.
- [ ] `make build`, `make check`, `make agent-test`.

## Phase 3 — dogfood against the local workshop

Owner: `pipelex-plugins`, with `../pipelex-mcp` on a build that carries `mthds_codegen` (`feature/CodegenTool` or later). Scratch projects live in the session scratchpad, **never** in either starter (§9). Switch the launcher with `/pipelex-mcp-source` to the local checkout for the phase, and back before committing.

Two scratch projects, each created from scratch by the session so the skill meets a cold codebase: a minimal TypeScript project (`package.json`, `tsconfig.json`, Prettier and ESLint flat config, a `check` script, `src/`), and a minimal Python project (`pyproject.toml` with `[tool.ruff]` and `[tool.pyright]`, `uv.lock`, one import package). Each holds a committed `methods/<method>/main.mthds` copied from the cookbook or written with `/pipelex-design`.

- [ ] **TS-1 fresh integration, files source.** Run `/pipelex-integrate`. Verify: the tree landed under `src/generated/<method>/` with `is_current: true` and no orphans; `.prettierignore` and the ESLint `ignores` entry were added **before** the write; `zod` and `@pipelex/sdk` were added with npm; the call site, client helper, and wire-output helper exist where §5 says; `npm run check` (extended with `codegen:check`) passes; `tsc --noEmit` passes; `sources.json` matches §4.6.
- [ ] **TS-2 the bytes are untouched.** `git diff --stat` shows no change under `src/generated/` after the skill's own format run; `npm run codegen:check` exits 0.
- [ ] **TS-3 refresh after a bundle edit.** Change a concept field in `main.mthds` (through `/pipelex-edit`, which should announce the staleness — Phase 2 wiring), run the skill again: the sidecar comparison reports the changed source, the fingerprint moved, the call site is edited only if the type check demanded it, `sources.json` carries the new hash, `codegen:check` is green again. Then edit only a prompt (no concept change): the fingerprint is unchanged and the report says restamp-or-nothing.
- [ ] **TS-4 stale-source gate.** Edit the bundle and do *not* refresh: `npm run codegen:check` exits 1 with `stale-source` and the refresh remedy.
- [ ] **TS-5 `method_ref` source.** Integrate a published address at a tag (a `github.com/Pipelex/…@vX.Y.Z` package): the call site runs by `method_ref`, the sidecar's `sources` is empty, the output-concept heuristic of §4.3 either finds one candidate or asks — record which.
- [ ] **TS-6 `method_id` warning.** Integrate a catalog method by id: the one-line warning appears, the recommendation is stated, and the skill proceeds only on confirmation.
- [ ] **TS-7 orphan.** Generate a second method into the first method's directory on purpose (by naming the dir explicitly): `orphans[]` is reported by name, nothing is deleted, the fix sentence is the tool's.
- [ ] **TS-8 foreign file.** Point at a directory holding a hand-written `types.ts`: the refusal is surfaced, the file is untouched, the skill chooses or asks for another directory.
- [ ] **TS-9 containment escape.** Launch the harness from a sibling directory so the project is outside the workshop's working directory: the skill stops with the relaunch instruction and does not ride content.
- [ ] **TS-10 no key.** Unset `PIPELEX_API_KEY` in the workshop's environment: the `config` stop with the hint verbatim, nothing written.
- [ ] **PY-1 fresh integration, pydantic audience.** No `pipelex` dependency → `python-pydantic` chosen without a question; `<package>/generated/__init__.py` and the subpackage `__init__.py` created; `[tool.ruff] exclude` gains the tree; pyright still covers it; `pydantic` and `pipelex-sdk` added with uv; the async call site plus a sync wrapper if the project is synchronous; the report states the gate asymmetry; `uv run pyright` passes.
- [ ] **PY-2 structures audience.** Add `pipelex` as a dependency and a `@pipe_func` file: `python-structures` is chosen (or offered first when only the dependency is present); `pipelex codegen check <dir>` is wired into the existing gate.
- [ ] **PY-3 refresh after a bundle edit**, as TS-3, including the `/pipelex-edit` staleness notice.
- [ ] **Vibe render sanity.** Read `pipelex-vibe/skills/pipelex-integrate/SKILL.md` once for the manual-registration wording of the MCP-absent message and the absence of Claude-only frontmatter.
- [ ] Reconcile every finding into the template and references; re-run the affected scenarios; `make build`, `make agent-check`, `make agent-test`.
- [ ] `/pipelex-mcp-source` back to `@latest`; confirm the diff carries no launcher change.

**CHECKPOINT 2** — every scenario above has been run at least once against the local workshop and its finding reconciled. Record here: the `pipelex-mcp` SHA the dogfood ran against, the scenarios that exposed a template change (and the change), any scenario that could not be run and why, and the exact wording the §4.3 heuristic produced in TS-5.

## Phase 4 — release

Owner: `pipelex-plugins`. **Gate, hard:** a published `@pipelex/mcp` version that carries `mthds_codegen` with the write arm — name the version here before starting; an open `pipelex-mcp` release item is not a gate. The plugin's launcher is `@latest`, so nothing in this repo moves for it, but a plugin released before the tool is a skill that stops at "tool absent" for every user.

- [ ] Published `@pipelex/mcp` version carrying `mthds_codegen`: `__________` (fill in).
- [ ] Re-check `L-260820-ee327d` and `L-260830-4e43cd` one last time; strike or keep the helper and the asymmetry paragraph accordingly, and log it.
- [ ] One live run of TS-1 and PY-1 against the **published** `@pipelex/mcp@latest` (not the local checkout), on the prod plugin output.
- [ ] Open the PR against `dev` with `Closes L-260830-344594` in the body; work the review rounds per the workspace's tightening-bar rule; land with `/ledger-land`.
- [ ] `/release` → the next minor (`0.6.0`), which cuts the changelog heading, bumps every target TOML and the Claude marketplace, and opens the release PR against `main`.
- [ ] After the release merges: `/ledger-land` on the release PR, and this file's `status` flips to `landed` when the tooling performs it.

## Deferred and out of scope

Carried in the design's §9 and §8; repeated here only where a phase might be tempted:

- No `contracts.ts`, no watch mode, no tests / routes / UI written by the skill, no per-project write-if-changed or orphan cleanup, no hosted-console branching.
- The by-ref / by-id output-concept heuristic (§4.3) ships as designed; the exact answer arrives with the `pipelex-mcp` follow-up and is not worked around here.
- The Python offline gate waits on `L-260830-4e43cd`; the TypeScript script is retired by `L-260820-2ba0f4`; the wire-null helper by `L-260820-ee327d`. None of the three is worked from this repo.
- The call site uses `pipe_code` (bare) until the SDKs take `pipe_ref` (`L-260829-563e9e`); the sidecar already records the qualified ref so the switch is a one-line edit per call site when it comes.

## Decisions taken along the way

- **2026-08-30 — Phase 0 ratification.** Louis walked the ten decision boxes of `design.md` one at a time, each presented against its alternatives (a narrower or wider call-site scope; refusing `method_id` or accepting a floating `method_ref`; blocking by-ref / by-id on the `pipelex-mcp` follow-up or keeping a contracts artifact; a content fallback or consented pre-clearing on the write arm; a hash-only Python gate or no gates at all; dropping the sidecar's `pipe` record or LF-normalizing its hashes; fixing the emitter first or a blind null-strip; lifting the light-template pin plugin-wide or reading concepts from the bundle; `pipelex-codegen` or a user-invocable-only skill; a staleness notice alone or an auto-refresh from `pipelex-edit`). Every box was ratified as written; the design's sections stand unamended and both documents flipped to `active` in this change.
- **2026-08-30 — upstream dependencies reviewed (Louis).** None of the items the design leans on (`L-260820-ee327d`, `L-260820-2ba0f4`, `L-260830-4e43cd`, `L-260830-e8b2e0`, `L-260829-563e9e`) is a member of the build-retirement epic `L-260829-848001` or appears in its plan; they sit on the codegen trust-chain axis, not the descriptor-route axis. Two decisions: `L-260830-e8b2e0` is linked *related* to that epic (not a member), to be sequenced after `L-260829-dfaed4` once the workshop holds the input-form descriptor; and `L-260820-ee327d` is prioritized ahead of Phase 3, so the Phase 1 pre-flight re-check may strike `wire-output.ts` before it is written. The summary is `upstream-dependencies.md` beside this file.

## Deviations from the design

*(empty at writing — a deviation is logged here with its reason before the code that embodies it is committed.)*

## Where everything is

- Brief: `wip/pipelex-integrate/brief.md`. Design: `wip/pipelex-integrate/design.md`. This tracker: `wip/pipelex-integrate/plan.md`.
- The tool contract: `../pipelex-mcp/SPEC.md` → "Codegen Scope (`mthds_codegen`)" and "The write arm (`output_dir`) — local workshop only". The writer: `../pipelex-mcp/src/capabilities/codegen-writer.ts`; containment: `workspace-boundary.ts`.
- Reference integrations (read, never changed): `../pipelex-starter-js/docs/codegen.md`, `src/generated/<method>/`, `src/lib/wireOutput.ts`, `scripts/codegen-check.mts`; `../pipelex-starter-python/Makefile` (`codegen`, `codegen-check`), `docs/codegen.md`, `piper/generated/`.
- The offline check the TypeScript gate wraps: `../pipelex-sdk-js/src/codegen-check.ts` (`runCodegenCheck`, `isStampableArtifactPath`), documented in `docs/crate-routes.md` → "The offline check".
- The sibling skill to model: `templates/skills/pipelex-inputs/SKILL.md.j2`; the tests to extend: `tests/unit/test_gen_skill_docs.py` (`TestSkillFailureDiscipline`, `TestPipelexInputsSizeLimitDiscipline` as the pattern).
- The static-asset mechanism: `scripts/gen_skill_docs.py` → `setup_static_assets`; documented in `docs/build-targets.md` → "Template vs output directories".
- Ledger: this item `L-260830-344594`; discovered `L-260830-4e43cd`; related `L-260820-ee327d`, `L-260820-2ba0f4`, `L-260829-563e9e`; the `pipelex-mcp` follow-up filed in Phase 0: `L-260830-e8b2e0`.
