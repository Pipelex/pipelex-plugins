---
name: pipelex-design
description: Design a MTHDS method bundle (.mthds files) top-down, contract-first. Use when the user says "design a method", "create a pipeline", "build a .mthds", "write a method that does X", "turn this workflow into MTHDS", or asks for a structural or contract change to an existing bundle — "add a step", "rewire this pipeline", "change what this pipe takes or produces", "reshape this concept", "refactor the flow", "add a step to mt_abc123". A re-entry takes a bundle directory, or a registered method's catalog id (mt_…), which it resolves to the directory linked to it or pulls to disk first. Construction is complexity-adaptive — a fully understood shallow graph is written directly as a coherent runnable bundle, while deep, uncertain, staged, or resumable work goes through validated signature-driven stepwise refinement. Re-enters existing methods with the same adaptive choice.
---

# Design a MTHDS bundle top-down at the right depth

Design a `.mthds` method **contract-first**, directly or stepwise (step 3). A structural change to an existing method is a [re-entry](#re-entry); a contract-preserving tweak is `/pipelex-edit`'s.

## Requirements

- **`mthds_validate`** and **`mthds_inputs_template`** are required: this skill never guesses at validity.
- **If the tools are absent from this session**, the Pipelex MCP server isn't connected: STOP, and tell the user in one line what [the connection reference](../shared/credentials.md#the-tool-is-absent) says for Mistral Vibe. Do not write `.mthds` files without validation available.
- **If a call returns `status: "error"` with an error of class `config`** (missing or rejected `PIPELEX_API_KEY`, unreachable API), STOP the same way and surface the error's `hint` verbatim; when it is about the key, read [where the key comes from](../shared/credentials.md#where-the-key-comes-from) before saying anything more. Never silently skip validation.

## Guards

- **Every claimed checkpoint or completion state comes from `mthds_validate` over all bundle files.**
- **Never write `inputs.json`.** When the user provides files or paths, or wants to run with real data, invoke `/pipelex-inputs`.
- **This skill never runs a method**: a run needs inputs and spends inference credit.

## Process

### 1. Capture the contract

Read [writing-mthds.md](references/writing-mthds.md) **before writing**: it is the syntax source of truth. For what it does not cover (`dict` field types, `PipeStructure`, inline `templating_style` blocks, other advanced features), write the closest in-scope equivalent and call out the deviation.

Fix the **input concept(s)**, the **output concept** and the **description**, precise enough to implement against, and specify every boundary concept fully now. Shape each concept from all its known consumers: it must be structured if any consumer field-reads it (`$x.field`, a construct `from = "x.field"`), and can stay simple otherwise. Declare each concept exactly once, complete, owned by the root boundary or by the controller that introduces it.

**Announce the captured contract in one line** (inputs → output, one-sentence semantics), with the bundle home resolved below in the same line, before writing, so the user can interject without blocking progress. **If the design will emit a `PipeFunc`, say so in that same line**, warning rather than refusing: **`PipeFunc` is experimental on the hosted plane.** Its Python runs in a sandbox with no network access, and the feature is still in development, so a method that validates can still fail when it runs. Discuss only genuine ambiguity, or when the user asks to collaborate.

### 2. Resolve the bundle home before writing

**A path the user named** wins over the rest, which apply in order: `<package>/methods/<name>/` in a packaged Python project, or a Python project that owns a codegen harness; `<project root>/methods/<name>/` in any other project, TypeScript harness projects included, the project being the nearest directory holding a `package.json`, a `pyproject.toml`, a `setup.py` or a `requirements.txt` at or above the working directory; otherwise `./methods/<name>/`. `<name>` is the `domain` in the project language's casing — `summarize-pdf` in TypeScript, `summarize_pdf` in Python and where there is no project — a dot becoming that separator, never a nested directory or a literal dot. **On a method app, ask first**: its `make add-method` never overwrites and also writes the action trio, narrower and registry entry a plain write leaves out; let the user choose. A bundle that already lives elsewhere stays there.

### 3. Infer the construction mode

**Never ask the user to choose the workflow.**

- **Direct** when the complete graph can be authored without placeholders or speculative contracts: the graph is one concrete operator; or one top-level controller whose children are concrete leaf operators; no child is a controller unless the whole nested graph and every contract is fixed and a direct layout is still clearly safer; every branch, iteration, mapping and intermediate owner is decided; every concept shape can be fixed from its consumers; every pipe can be concrete in the first coherent artifact. One controller is a strong fast-path signal, not a rule. Pipe count is secondary: cross-branch concept dependencies, uncertain ownership, or unresolved child contracts make even a lone controller stepwise.
- **Stepwise** otherwise, and even where direct holds, for a large graph that benefits from independently valid review checkpoints or on an explicit request for a scaffold, partial design, staged work, or a resumable intermediate result: read [stepwise.md](references/stepwise.md) before writing any file.

When borderline, take the simplest path that can be written **completely** and validated confidently.

### 4. Direct construction

Design the whole graph in memory, then write `main.mthds` in the bundle home, top-down — metadata, concepts, the concrete main pipe, its leaves — with concept codes checked library-wide and explicit `inputs` and `output` on every pipe. More than one file only at a natural module boundary, never one per pipe. Include **no temporary `PipeSignature` declarations**. **If the design would need a placeholder or a guessed contract, or writing or validation exposes an unresolved structural boundary**, stop extending the draft and read [stepwise.md](references/stepwise.md) before changing any file.

### 5. Validate

Gather the bundle's files as the convention below says, the whole library, and call `mthds_validate` with `files` for every file. Submit every `.mthds` file beneath the bundle directory **except anything under a `runs/` directory**, where `/pipelex-run` saves a completed run's artifacts: a method that emits or echoes a `.mthds` file would otherwise have its own output submitted as part of its source. Prefer the path form `{path: <absolute path to the file>}` — it keeps the real path as provenance in diagnostics and spares copying whole bundles into the request; the workshop resolves a path against **its own** working directory, wherever the harness launched it, so pass an absolute one. Inline `{content: <file content>, uri: <path relative to the bundle dir>}` is the fallback, and the only form the hosted console accepts.

Branch on the **structured verdict** from its Markdown summary, never on transport: `is_valid: true` is complete with `is_runnable: true` and nothing pending, and otherwise a scaffold whose backlog is the summary's `## Pending signatures`; on `is_valid: false`, fix from `validation_errors[]` and the summary's locators, which name the offending file, then re-validate.

### 6. The runnable gate and delivery

For a completed method, re-gather the whole bundle and confirm **`is_valid: true`, `is_runnable: true`, and an empty `pending_signatures`**: this verdict is the runnable gate, so fix and re-validate until it passes. A re-entry restores at least its baseline verdict instead. Then:

1. **Organize only when the layout needs it.** A converged stepwise construction or signature-driven re-entry normally invokes `/pipelex-organize`; a result already coherent in either mode skips it.
2. **Project the input schema**: `mthds_inputs_template` with the final whole-bundle `files` and `explicit: false`; show the compact template.
3. **Present the flow**: the interactive method graph where the host rendered it, else a concise text flow.
4. **Warn again for a `PipeFunc`**, naming its pipes: **`PipeFunc` is experimental on the hosted plane.** Its Python runs in a sandbox with no network access, and the feature is still in development, so a method that validates can still fail when it runs.
5. **Hand off**: `/pipelex-inputs` prepares the user's files, or test files with planted facts, then `/pipelex-run` runs the method; `/pipelex-catalog` saves it under an `mt_…` id anything can call; `/pipelex-integrate` wires it into a codebase (a `package.json` or a `pyproject.toml`), and with none, `/pipelex-scaffold` creates an application around it if the user wants one.
6. Search the whole project for `sources.json` files carrying `"generator": "pipelex-integrate"` — `grep -rl '"pipelex-integrate"' --include=sources.json .` — which sit beside each generated tree (`src/generated/<method>/`, `<package>/generated/<method>/`), never beside the bundle, so looking only next to the `.mthds` files finds nothing. Keep each one whose `sources` name a `.mthds` file this change rewrote, moved or removed, **or whose `bundle_dir` holds a `.mthds` file this change created** — a new file is in no `sources` map, yet the call site loads every `.mthds` file under that directory. For each, say the generated types in that directory are now stale and offer `/pipelex-integrate` to refresh them: it regenerates in place and touches the call site only if the types no longer fit it.

**The saved method does not have this change.** When `pipelex-method.json` sits beside the root `.mthds` file, this directory is linked to a method in the organization's catalog: name it by the link's `name` and `mt_…` id and say that what just changed here is not in the catalog, so every caller of that id goes on running whatever is saved there. **Say that and no more.** The link records no hashes, so this directory may equally be behind the catalog — a teammate may have saved since it last synced — and calling the saved copy old asserts an ordering nothing here can read. `/pipelex-catalog` is what compares the two, and what updates the saved copy. **Offer that; never do it.** A save is a deployment — a production call site included runs the new content from its next call — so it happens when the user asks for it and not as the tail of somebody else's edit. No link file beside the root means this directory is not linked and there is nothing to say. Never write or edit `pipelex-method.json`: the workshop writes it, because it is the only party that knows which API host it talks to.

## Re-entry

**For a catalog id (`mt_…`) or a published address**, read [the catalog-id reference](../shared/catalog-id.md) before reading any file. **When several directories are linked to the method, ask which is the work; never choose.** **Never present a linked directory as the saved method's current content.**

**The baseline, before every edit**: read every `.mthds` file outside `runs/`, validate the whole bundle, and record whether it is runnable or a scaffold, with its exact pending set. Then read [re-entry.md](references/re-entry.md) before editing any file, [writing-mthds.md](references/writing-mthds.md) before writing one, and [stepwise.md](references/stepwise.md) too for a signature-driven re-entry. **Never redesign on a broken baseline**: repair it first. **Retain the original contents until the final verdict is restored.** **If a post-edit call returns no verdict, or the edited region cannot be made valid after two focused fixes, restore the retained baseline contents and report the failure**; otherwise deliver as step 6 says.

## Stops

| Condition | Do this |
|---|---|
| `status: "error"`, class `input_domain` | the submission is malformed: fix the call |
| `status: "error"`, class `runtime` | report it, and retry once before stopping |
| validation fails twice on the same construct, or the client contract itself looks wrong | pause and show the user |

## References

- [writing-mthds.md](references/writing-mthds.md): before writing any `.mthds` file.
- [stepwise.md](references/stepwise.md): stepwise at step 3 or 4, or a signature-driven re-entry.
- [re-entry.md](references/re-entry.md): a structural change to an existing method.
- [Native content types](../shared/native-content-types.md): a native's fields, for `$var.field` and `from`.
