# A project that owns a codegen harness

Read this at step 1, before step 2, when the project shows a codegen harness. A project made from the method app (`pipelex-method-apps`' `webapp-js/`), `pipelex-starter-js` or `pipelex-starter-python`, or one that adopted their pattern, regenerates every method in one place, checks them in one place, and keeps its own sidecar. Writing the skill's tree beside that would leave two regeneration paths, two sidecar dialects and files the workshop never emits. The language reference read at step 1 has a harness section of its own, with that language's commands.

## Recognising one

The signals are a `codegen` script in `package.json` or a `codegen` Makefile target; a `sources.json` carrying a `derived` map; `docs/codegen.md` or `docs/add-method.md`; a `methods/` directory beside `src/generated/` or `<package>/generated/`. Either of the first two decides; the rest only corroborate.

**A `codegen` script in `package.json` decides only once you have read it.** `"codegen": "graphql-codegen"` or a protobuf generator satisfies the name and generates no MTHDS types, and deferring to it would skip the dependencies, the exclusions, the sidecar and the gate while generating nothing. Pipelex-specific evidence — it calls `mthds_codegen`, a `pipelex` CLI, or reads `methods/` — is what makes it this method's harness. Without that, go back to the skill's main path and leave the unrelated harness alone.

## What changes

Steps 1 to 3 run as the skill says, and so does step 12. In place of steps 4 to 11:

- **A local bundle is one command when the project's `make add-method` takes a bundle path**, which its usage in `make help` says, as the method app's does: `make add-method METHOD=<path to the bundle>` copies the bundle into `methods/<name>/` and writes the whole slice, call site included, so nothing below is done by hand except the verification.
- **Otherwise, place the method where the project keeps them**: `methods/<name>/main.mthds`, or the project's manifest form for a catalog or published method. The address goes into that manifest as it was passed, by the skill's guard on a `method_ref`: here it is written by hand, where no tool is there to stop a floating address being resolved into the tag it landed on.
- **Run the project's generator**: `make add-method METHOD=…` when the project has it and the method is remote, its `codegen` script or Makefile target otherwise.
- **Write the call site the way the project's docs and existing methods do** (`docs/codegen.md`, `docs/add-method.md`, the existing actions or CLI commands), not the shape of step 9.
- **Skip steps 5, 7, 8 and 10**: the exclusions, dependencies, sidecar and gate already exist. Verify with the project's own aggregate gate (`make check`, `make all`).
- **Refresh is the project's `codegen` script**, and you say so instead of calling `mthds_codegen`.

## When the harness's generator cannot run

The harness owns the layout and the check; its generator is preferred, not mandatory. When it cannot run — the Python starter's `make codegen` stops when no `PIPELEX_API_KEY` reaches the project, although the workshop holds a key of its own — call `mthds_codegen` with `output_dir` set to **the harness's own layout** (`<package>/generated/<module>/`, `<module>` being the method directory's name with its dashes turned into underscores, as the Python reference spells out). The result is byte-identical there: same engine, same stamps, same lock, and that starter keeps no sidecar. Say the project's `make codegen` is the refresh once its prerequisite is met.

**This is the one destination step 4's sidecar rule does not govern.** The harness owns the directory and deliberately keeps no `sources.json`, so on every run after the first it holds a lock with no sidecar, which step 4 would otherwise read as another generation's. This branch is entered at step 1, before that rule applies: write into the layout again rather than inventing a second directory name, which is the thing this whole branch exists to prevent.
