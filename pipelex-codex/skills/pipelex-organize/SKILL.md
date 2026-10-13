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

- **Change the layout, never the method.** A declaration may move to another file and be reordered, a non-root file may be renamed, a `PipeSignature` header whose code has a concrete definition anywhere in the library is dropped, per-file `domain = "..."` lines are absorbed into the files that survive, and a `PipeDocGen` step moved to another directory has its `template_file` rewritten to reach the same file, which is layout too. Nothing else changes: pipe and concept codes, the `domain`, `main_pipe`, `description`, `system_prompt`; any pipe's `inputs`/`output`, `type`, prompts, steps, branches, outcomes or other body field; any concept's `description`, `refines` or structure fields.
- **An unsatisfied signature** — a `PipeSignature` with no concrete definition, a scaffold's backlog — **is kept**, deduplicated to one header per code, never dropped.
- **Keep every original file's content until the new layout is confirmed on disk.**

## Process

### Step 1 — Baseline verdict

**For a catalog id (`mt_…`) or a published address**, read [the catalog-id reference](../shared/catalog-id.md) before reading any file. **When several directories are linked to the method, ask which is the work; never choose.** **Never present a linked directory as the saved method's current content.**

Call `mthds_validate` on the bundle directory. Pass the bundle directory as `method_dir`, absolute: the workshop sends its `.mthds` files and the templates their steps name, listed in `files_sent`. It refuses one outside **its own** working directory, where the harness launched it; relaunching the harness from a directory holding the bundle cures that. Inline `files` (`{content, uri: <path in the bundle>}`) are the fallback for a bundle with no template file; **for a templated one, stop and ask for that relaunch**. A workshop whose tools lack `method_dir`, or answer it *Provide MTHDS files*, is older: read [the reference](../shared/writing-mthds.md#template-files) first. Read every `.mthds` file the call sent, and record the **baseline**: `is_valid`, `is_runnable`, and the exact `pending_signatures` set. `is_valid: true` proceeds, runnable or scaffold.

### Step 2 — Plan the layout, compose the files

Map the structure from the main pipe down: the subtrees, the pipes and concepts each owns, and the shared declarations. Then decide the file set by these rules, honoring any layout the user asked for (a single file, a grouping):

- **The root is `main.mthds`** unless the user says otherwise, and a root inherited under another name is renamed. It holds the bundle header (`domain`, `description`, `main_pipe`, `system_prompt`, which reach every file of the same `domain`, so a sibling declares only `domain`), the boundary concepts and the main pipe, so reading it alone tells what the method does, what goes in and out, and the top-level steps.
- **One file per module**: each top-level subtree — a controller with the sub-pipes only it wires — or functional area gets its own `<snake_case_name>.mthds`, named after the controller heading it or the area it implements, holding its pipes in flow order (controller first) and the intermediate concepts introduced for it. A non-root file starts with `domain = "<same_domain>"` only.
- **Shared declarations go up** to the root, or to a dedicated `shared.mthds` when that surface is large, never duplicated.
- **Scale the file count to the method**: a handful of pipes belongs entirely in `main.mthds`, tens of pipes need several modules, and never one file per pipe.
- **Progressive discovery is the test**: the root plus one module file holds everything relevant to one step.
- A still-pending signature sits in the module of the controller that wires it.

**A `PipeDocGen` step's template is the file its `template_file` reaches from the directory of the `.mthds` file holding the step**: record each one's real path (`realpath`) before composing, and never move or rename a template file. When the plan moves a step to a file in another directory, its `template_file` becomes the forward-slash path that reaches the same file from there; when only a path through `..` would, which the runner refuses, that step does not move.

State the plan in one line (`main.mthds + extract.mthds + report.mthds`) and proceed; never ask. Compose every file in memory, **copying each declaration verbatim** into its file, one declaration per concept and one entry per pipe, top-down within each file.

### Step 3 — Prove equivalence before touching disk

Call `mthds_validate` with **the composed candidate set** alone, inline, since nothing is written yet. The verdict must match the baseline exactly: `is_valid: true`, the same `is_runnable`, and an identical `pending_signatures` set. A mismatch means the composition dropped or duplicated something: fix the composition, never the semantics, and re-validate. **A bundle whose `PipeDocGen` steps name template files skips this proof**: a template file travels only beside `.mthds` files read from disk, so Step 4's confirmation, with its rollback, proves the layout instead.

### Step 4 — Swap the layout

1. Write every file of the new layout; a new file may reuse an old file's name.
2. Delete every `.mthds` file that is not part of the new layout. **Delete only `.mthds` files, and never one under a `runs/` directory; leave `inputs.json`, input files and anything else alone.**
3. **Confirm on disk**: validate the bundle once more, as in Step 1, since the hook may have reformatted what was written, and check that every `PipeDocGen` step's `template_file` reaches, from its new file's directory, the real path recorded for it in Step 2. A valid verdict cannot see a step that now reaches another template under the same name.
4. **If that confirmation fails, restore the original layout — never leave the directory unconfirmed.** On `status: "error"`, a verdict that differs from the baseline or a template that differs from Step 2's, rewrite the original files, delete the new-layout files that were not in the original set, and report the failure with the layout left as it was. The swap ends either proven equivalent or fully rolled back.

### Step 5 — Report

One short summary: the layout, one line per file saying what it holds, and the preserved verdict (runnable, or a valid scaffold with its pending list). No approval prompts.

**When invoked on its own rather than by `/pipelex-design`** (whose delivery step carries both notices), end with them, since an identical verdict still rewrote every file:

1. Search the whole project for `sources.json` files carrying `"generator": "pipelex-integrate"` — `grep -rl '"pipelex-integrate"' --include=sources.json .` — which sit beside each generated tree, never beside the bundle. Keep each one whose `sources` name a `.mthds` file this change rewrote, moved or removed, or whose `templates` name a template file it changed, **or whose `bundle_dir` holds a `.mthds` file this change created** — a new file is in no `sources` map, yet the call site loads every `.mthds` file under that directory. For each, say the generated types in that directory are now stale and offer `/pipelex-integrate` to refresh them: it regenerates in place and touches the call site only if the types no longer fit it.
2. **Save the linked method's draft.** A `pipelex-method.json` beside the root `.mthds` file links this directory to a saved method, which lacks this change. Once this skill's own final verdict has proven the change, call `mthds_save_method` with the validated `.mthds` files as `{ path }`, root first, and the link's `method_id`, and nothing else: **no `name`, no `expected_updated_at`, no `python`, no `link_dir`**, and no template file — the workshop sends the link's token itself. Report it by name and id, with what the tool says `mt_…@draft` and the bare id now run, and its words on a link it could not write. With a `template_file`, say the catalog stores no template file yet: the draft reports it missing and runs only from this directory. **Never publish here: a publish is `/pipelex-catalog`'s, on the user's request.** Leave the save to `/pipelex-catalog`, saying the change is not saved, when the tool is absent or refuses, a `config`-class error included, when the workshop will not read the path, or when this work changed a `PipeFunc`'s Python; never retry with a token or inline. No link file means there is nothing to save to. Never write or edit `pipelex-method.json`: it is the workshop's.

## Stops

| Condition | Do this |
|---|---|
| `is_valid: false` at the baseline | never reorganize a broken library: report the verdict and point to `/pipelex-design` to fix it first |
| `status: "error"`, class `input_domain` | fix the call |
| `status: "error"`, class `runtime` | report it, and retry once before stopping |
| the candidate still differs from the baseline after two fixes of the composition | stop, leave the original layout untouched, and report the discrepancy |
| the regrouping seems to need a semantic edit (a rename, a contract fix, a missing declaration) | stop and report it: that is `/pipelex-design`'s work |
