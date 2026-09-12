---
status: draft
item: L-260830-344594
---

# Brief: a skill that integrates a method into a Python or TypeScript codebase

This is a brief, not a design and not a plan. It says what the skill is for, what already exists that the design must not reinvent, and which questions the design session has to settle. Everything below that reads like a decision is a *finding* — a fact about the surrounding system that constrains the design — except where it is explicitly marked as an open question.

Written from `pipelex-mcp` on 2026-08-30, the day `mthds_codegen` finished review on that repo's `feature/CodegenTool`. The tool is unreleased at the time of writing; the plugin's baked launcher is `npx -y @pipelex/mcp@latest`, so nothing here waits on a version pin moving.

## The gap

Every skill this plugin ships today acts on `.mthds` files: explain one, design one, reorganize one, edit one, fill its inputs. None of them touches the codebase that will *call* the method. So the moment a user is happy with a method, the plugin stops helping, and the last mile — turning a validated bundle into typed code an application actually runs — is left to the model's improvisation.

That last mile is not improvisation-shaped. It is deterministic, it has a known-good shape, and getting it wrong is quiet: hand-written types drift from the bundle with nothing to detect it, a formatter run breaks a trust chain nobody knew was there, two methods generated into one directory report as permanently stale. The work is exactly what a skill is for.

`mthds_codegen` is what makes it possible now. Before it, a consumer had to build its own harness: `pipelex-starter-js` wrote `scripts/codegen.mts` over `@pipelex/sdk`'s `client.codegen()`, and `pipelex-starter-python` shells out to a `pipelex` CLI that it deliberately does not depend on (`PIPELEX ?= pipelex` in its Makefile, with a comment explaining that the starter talks to the hosted API and the runtime is not its dependency). Both are per-project scaffolding that no third project can reuse. The MCP tool does the same projection from the workshop with nothing but an API key.

## What the skill does, in one paragraph

Given a method — local `.mthds` files, a catalog id, or a published address — and a codebase, the skill picks the codegen target that matches the project, writes the generated tree into the project at a location that fits its layout, makes the surrounding tooling leave that tree alone, wires the offline drift check into whatever gate the project already runs, and then writes the call site: a typed function that runs the method through `@pipelex/sdk` or `pipelex-sdk` and parses its output with the generated binder. Re-running it on a project that already has a generated tree is the common case, not the rare one.

## Read these first

Ground truth, in the order the design session should read it:

- `../pipelex-mcp/SPEC.md` → **"Codegen Scope (`mthds_codegen`)"** and its subsection **"The write arm (`output_dir`) — local workshop only"**. The full input and output shapes, the verdict discipline, the error taxonomy, the overwrite rule, the orphan rule, and the size-bounding rule. This is the contract; do not infer it from the tool description.
- `../pipelex-starter-js/docs/codegen.md`. **The whole document is the reference design for a TypeScript integration** — the tree layout, why the generated files are excluded from Prettier and ESLint but not from `tsc`, the split between the keyed regeneration action and the keyless CI check, and the two artifacts the codegen route does not produce. If the design session reads one thing beyond the SPEC, read this.
- `../pipelex-starter-python/Makefile` (the `codegen` and `codegen-check` targets) and its `CLAUDE.md` bullet "The typed models are generated, never hand-written". The Python shape, and the CLI dependency this skill is meant to remove.
- `../pipelex-starter-js/src/actions/runSummarizePdfPipeline.ts` and `src/types/generateImagePipeline.ts`. What a finished call site looks like, and what the hand-written layer *above* a generated binder is for.
- `../docs/specs/pipelex-codegen.md` → "Two axes: what to project and for whom". Why the target enum is what it is, and why there is no `language` alias.

## Findings the design has to build on

**The write arm is the whole efficiency argument.** Passing `output_dir` makes the workshop write the tree to disk and withhold every artifact byte from every stream: the structured result carries `path`, `bytes` and `written_to` per file and the summary carries no fenced blocks. Without it, a method with a handful of concepts puts tens of kilobytes through the model's context *twice*, once as `structuredContent.artifacts[].content` and again as fenced Markdown, and the model then re-emits all of it through file writes. The skill should always pass `output_dir`. The plugin only ever declares the local workshop launcher, so the arm is always available to it.

**The bytes are load-bearing and must not be touched.** Each artifact carries a stamp holding its own content hash, and `codegen.lock` holds the hash of every artifact. A reformat, a re-serialized lock, a trimmed trailing newline — any of them breaks the chain and turns the offline check red. This is why both starters exclude their generated tree from their formatters and linters while keeping it inside the type checker, and why the skill has to make that exclusion itself rather than mentioning it. The concrete edit differs per project (`.prettierignore`, an ESLint flat-config `ignores`, `[tool.ruff] exclude`, Biome, Black), which makes it a detection problem rather than a fixed patch.

**One directory per method, and it is not a style preference.** After writing, the tool walks the directory and reports any stamped file the new lock does not list as an *orphan*, and it never deletes one. Two methods generated into the same directory therefore report as permanently non-current, by design. The skill must place each method in its own directory and must not offer "clean up the orphans" as advice, because the moment a user has two methods in one place that advice deletes real files.

**Regeneration overwrites its own output and refuses everything else.** A destination that does not exist is written; a regular file carrying a codegen stamp is overwritten whether or not somebody hand-edited it; anything else — an unstamped file, a symlink whatever it points at, a directory — refuses the entire write with an `input_domain` error naming the file. So pointing `output_dir` at a directory that holds hand-written code fails loudly and leaves the tree byte-identical, which is the behaviour the skill should rely on rather than pre-checking around.

**The target is required, has no default, and its rule is about audience rather than language.** `ts-zod` emits `types.ts` (zod schemas plus inferred types, depending only on zod) and `binder.ts` (a parse/serialize pair per concept); keep both. `python-pydantic` emits `models.py`, plain `BaseModel`s, for a Python consumer with no Pipelex runtime. `python-structures` emits `structures.py`, runtime `StructuredContent` classes, and is wanted only by a Pipelex host or a `@pipe_func` implementation. The two Python targets differ by audience, not by language, so "this is a Python project" does not pick one. Field keys are wire-native snake_case in every target, TypeScript included.

**TypeScript gets a keyless drift gate for free; Python does not.** `@pipelex/sdk` exports `runCodegenCheck`, pure hashing with no engine and no network, so a TypeScript project that already depends on the SDK can add a CI check with no new dependency. `pipelex-sdk` (Python) has the `/v1/codegen` wire models and the `codegen()` call but no check at all, so a Python project's only offline gate today is the `pipelex` CLI — the runtime dependency a hosted-API consumer took the SDK to avoid. Filed as [L-260830-4e43cd](http://localhost:4747/i/L-260830-4e43cd) against `pipelex-sdk-python`. **The skill ships with the asymmetry documented rather than waiting on it**, but the design should decide what it tells a Python user in the meantime.

**The lock signs the artifacts, not their sources.** It answers "has this generated tree been tampered with", not "has the bundle changed since I generated". `pipelex-starter-js` invented a `sources.json` sidecar to close that gap — a SHA-256 per `.mthds` source in the closure, plus a second map for the artifacts it emits that the lock cannot sign. The MCP write arm produces no such sidecar. Whether the skill recreates it, relies on the user regenerating after every bundle edit, or leaves source drift undetected is an open question, and it is the one with the most direct effect on whether the integration stays honest over time.

## Open questions the design must settle

1. **Where the skill's responsibility ends.** Generating and placing the types is deterministic. Writing the call site is not: it means reading an unfamiliar codebase and matching its conventions. Does the skill write a complete typed function, a single annotated example the user adapts, or only the types plus instructions? "Properly integrate" argues for the first; the plugin's existing skills all stop at the `.mthds` boundary, so this is the largest new commitment in the proposal and it should be decided deliberately rather than by momentum.

2. **Which run source to recommend, and whether to guard its drift.** The generated types pin a `crate_fingerprint` from the closure that produced them. A run by `method_id` executes whatever the catalog holds *at run time*, so somebody editing the stored method silently invalidates the committed types with nothing to detect it. A committed bundle regenerated in lockstep, or a `method_ref` pinned at an immutable tag, keeps the two together. This is a real correctness question about the shape the skill produces, not a preference.

3. **Whether the skill can produce a contracts artifact at all.** `pipelex-starter-js` needs the pipe IO contracts and the wire input-form descriptor to gate its run inputs, and gets them from `/v1/validate` with `views: ["input_form"]`. Through MCP, both ride `_meta`, which is the view-only channel and **never reaches the model's context** — and the workshop has no views. So a workshop agent cannot see them today. Decide whether the skill needs them; if it does, that is a `pipelex-mcp` follow-up to file, not something to work around in a skill.

4. **Detecting the project, and how far to go on a guess.** Language, package layout, where generated code conventionally lives, which formatter and linter are in play, which CI gate to extend. Some of this is cheap and reliable (a `package.json`, a `pyproject.toml`); some is not (is this a Pipelex host, which decides between the two Python targets). Name the checks the skill runs and what it does when they are inconclusive — the plugin's other skills have a stop-and-ask posture worth matching.

5. **The second invocation.** Re-running against an existing generated tree is the common case: the user edited the bundle and wants the types refreshed. What the skill re-derives, what it takes from what is already on disk, and what it leaves alone are the difference between a skill that is used once and one that is used weekly.

6. **The skill's name and its place in the family.** The existing set is `pipelex-explain`, `pipelex-design`, `pipelex-organize`, `pipelex-edit`, `pipelex-inputs` — all verbs on a bundle. This one is a verb on a codebase. Whatever it is called, its description has to make a model reach for it on "use this method in my app", "generate types for this method", "call this from my code", and not on the bundle-authoring phrasings the other skills already claim.

## Constraints and scope

- Templates are the source of truth. Edit `templates/skills/<name>/SKILL.md.j2`, run `make build`, never touch the generated `pipelex*/` outputs. `templates/skills/pipelex-inputs/SKILL.md.j2` is the closest sibling to model: MCP-backed, multi-step, with Claude-only `allowed-tools` frontmatter guarded by `{% if platform == "claude" %}`.
- The skill renders to all three targets. Tool names differ per host (`mcp__plugin_pipelex_pipelex__mthds_codegen` on Claude, `mcp__pipelex__mthds_codegen` on Codex), which the existing templates already handle by referring to tools generically in prose.
- Add `mthds_codegen` to the tool lists in `CLAUDE.md` ("Key dependency") and `docs/decisions.md` when the skill lands, exactly as `mthds_prepare_inputs` was added.
- Out of scope: anything under `../pipelex-mcp/`. If the skill needs a tool change, file it against that repo rather than working around it here.
- Out of scope: changing either starter. They are the reference shape to learn from, not a deliverable.
