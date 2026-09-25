---
name: pipelex-organize
description: Reorganize a designed method bundle into a clear, browsable layout. Use when signature-driven construction left one .mthds file per refinement, when any existing layout needs regrouping into coherent modules (or one simple file), or when the user says "organize the bundle", "organize the method", "regroup the files", "clean up the bundle layout". Takes a bundle directory, or a registered method's catalog id (mt_…), which it resolves to the directory linked to it or pulls to disk first. Automatically follows converged /pipelex-design runs only when their construction-shaped layout needs it. Pure reorganization — never changes what the method does.
---

# Organize a designed MTHDS bundle

Regroup a designed library's `.mthds` files for **comprehension**, the way source code is spread across files: the root shows the contract and the top-level flow, and a reader descends into just the module they care about. Signature-driven construction leaves one file per refinement and satisfied `PipeSignature` headers behind. Direct designs are normally coherent already and skip this skill, unless the user asks or their layout genuinely needs regrouping; `/pipelex-design` auto-invokes it after converged signature-driven construction or re-entry when the layout still reflects construction history, and an already coherent direct result does not invoke it solely for process compliance.

It is a **content-preserving transformation**: the method's semantics never change, and the validation verdict before and after must be identical.

## Requirements

- **`mthds_validate`** is required: this skill never reorganizes without proving the verdict is preserved.
- **If the tool is absent from this session**, the Pipelex MCP server isn't connected: STOP, and tell the user in one line what [the connection reference](../shared/credentials.md#the-tool-is-absent) says for Codex. Do not touch the bundle files without validation available.
- **If a call returns `status: "error"` with an error of class `config`** (missing or rejected `PIPELEX_API_KEY`, unreachable API), STOP the same way and surface the error's `hint` verbatim; when it is about the key, read [where the key comes from](../shared/credentials.md#where-the-key-comes-from) before saying anything more. Never reorganize unvalidated.

## Guards

- **Change the layout, never the method.** A declaration may move to another file and be reordered, a non-root file may be renamed, a `PipeSignature` header whose code has a concrete definition anywhere in the library is dropped, and per-file `domain = "..."` lines are absorbed into the files that survive. Nothing else changes: pipe and concept codes, the `domain`, `main_pipe`, `description`, `system_prompt`; any pipe's `inputs`/`output`, `type`, prompts, steps, branches, outcomes or other body field; any concept's `description`, `refines` or structure fields.
- **An unsatisfied signature** — a `PipeSignature` with no concrete definition, a scaffold's backlog — **is kept**, deduplicated to one header per code, never dropped.
- **Keep every original file's content until the new layout is confirmed on disk.**

## Process

### Step 1 — Baseline verdict

**For a catalog id (`mt_…`) or a published address**, read [the catalog-id reference](../shared/catalog-id.md) before reading any file. **When several directories are linked to the method, ask which is the work; never choose.** **Never present a linked directory as the saved method's current content.**

Gather the bundle's files as the convention below says, read each, and call `mthds_validate` with `files` for every file. Submit every `.mthds` file beneath the bundle directory **except anything under a `runs/` directory**, where `/pipelex-run` saves a completed run's artifacts: a method that emits or echoes a `.mthds` file would otherwise have its own output submitted as part of its source. Prefer the path form `{path: <absolute path to the file>}`. The workshop refuses a path outside **its own** working directory, where the harness launched it; relaunching the harness from a directory holding the bundle cures that. Inline `{content: <file content>, uri: <path relative to the bundle dir>}` is the fallback. Record the **baseline**: `is_valid`, `is_runnable`, and the exact `pending_signatures` set. `is_valid: true` proceeds, runnable or scaffold.

### Step 2 — Plan the layout, compose the files

Map the structure from the main pipe down: the subtrees, the pipes and concepts each owns, and the shared declarations. Then decide the file set by these rules, honoring any layout the user asked for (a single file, a grouping):

- **The root is `main.mthds`** unless the user says otherwise, and a root inherited under another name is renamed. It holds the bundle header (`domain`, `description`, `main_pipe`, `system_prompt`, which reach every file of the same `domain`, so a sibling declares only `domain`), the boundary concepts and the main pipe, so reading it alone tells what the method does, what goes in and out, and the top-level steps.
- **One file per module**: each top-level subtree — a controller with the sub-pipes only it wires — or functional area gets its own `<snake_case_name>.mthds`, named after the controller heading it or the area it implements, holding its pipes in flow order (controller first) and the intermediate concepts introduced for it. A non-root file starts with `domain = "<same_domain>"` only.
- **Shared declarations go up** to the root, or to a dedicated `shared.mthds` when that surface is large, never duplicated.
- **Scale the file count to the method**: a handful of pipes belongs entirely in `main.mthds`, tens of pipes need several modules, and never one file per pipe.
- **Progressive discovery is the test**: the root plus one module file holds everything relevant to one step.
- A still-pending signature sits in the module of the controller that wires it.

State the plan in one line (`main.mthds + extract.mthds + report.mthds`) and proceed; never ask. Compose every file in memory, **copying each declaration verbatim** into its file, one declaration per concept and one entry per pipe, top-down within each file.

### Step 3 — Prove equivalence before touching disk

Call `mthds_validate` with **the composed candidate set** alone, inline, since nothing is written yet. The verdict must match the baseline exactly: `is_valid: true`, the same `is_runnable`, and an identical `pending_signatures` set. A mismatch means the composition dropped or duplicated something: fix the composition, never the semantics, and re-validate.

### Step 4 — Swap the layout

1. Write every file of the new layout; a new file may reuse an old file's name.
2. Delete every `.mthds` file that is not part of the new layout. **Delete only `.mthds` files, and never one under a `runs/` directory; leave `inputs.json`, input files and anything else alone.**
3. **Confirm on disk**: validate the bundle once more, gathered as in Step 1, since the hook may have reformatted what was written.
4. **If that confirmation fails, restore the original layout — never leave the directory unconfirmed.** On `status: "error"` or a verdict that differs from the baseline, rewrite the original files, delete the new-layout files that were not in the original set, and report the failure with the layout left as it was. The swap ends either proven equivalent or fully rolled back.

### Step 5 — Report

One short summary: the layout, one line per file saying what it holds, and the preserved verdict (runnable, or a valid scaffold with its pending list). No approval prompts.

**When invoked on its own rather than by `/pipelex-design`** (whose delivery step carries both notices), end with them, since an identical verdict still rewrote every file:

1. Search the whole project for `sources.json` files carrying `"generator": "pipelex-integrate"` — `grep -rl '"pipelex-integrate"' --include=sources.json .` — which sit beside each generated tree (`src/generated/<method>/`, `<package>/generated/<method>/`), never beside the bundle, so looking only next to the `.mthds` files finds nothing. Keep each one whose `sources` name a `.mthds` file this change rewrote, moved or removed, **or whose `bundle_dir` holds a `.mthds` file this change created** — a new file is in no `sources` map, yet the call site loads every `.mthds` file under that directory. For each, say the generated types in that directory are now stale and offer `/pipelex-integrate` to refresh them: it regenerates in place and touches the call site only if the types no longer fit it.
2. **The saved method does not have this change.** When `pipelex-method.json` sits beside the root `.mthds` file, this directory is linked to a method in the organization's catalog: name it by the link's `name` and `mt_…` id and say that what just changed here is not in the catalog, so every caller of that id goes on running whatever is saved there. **Say that and no more.** The link records no hashes, so this directory may equally be behind the catalog — a teammate may have saved since it last synced — and calling the saved copy old asserts an ordering nothing here can read. `/pipelex-catalog` is what compares the two, and what updates the saved copy. **Offer that; never do it.** A save is a deployment — a production call site included runs the new content from its next call — so it happens when the user asks for it and not as the tail of somebody else's edit. No link file beside the root means this directory is not linked and there is nothing to say. Never write or edit `pipelex-method.json`: the workshop writes it, because it is the only party that knows which API host it talks to.

## Stops

| Condition | Do this |
|---|---|
| `is_valid: false` at the baseline | never reorganize a broken library: report the verdict and point to `/pipelex-design` to fix it first |
| `status: "error"`, class `input_domain` | fix the call |
| `status: "error"`, class `runtime` | report it, and retry once before stopping |
| the candidate still differs from the baseline after two fixes of the composition | stop, leave the original layout untouched, and report the discrepancy |
| the regrouping seems to need a semantic edit (a rename, a contract fix, a missing declaration) | stop and report it: that is `/pipelex-design`'s work |
