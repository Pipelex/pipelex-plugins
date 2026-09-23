---
name: pipelex-edit
description: Edit an existing MTHDS method bundle (.mthds files). Use when the user says "change this pipe", "update the prompt", "rename this concept", "rename this pipe", "change the model", "tweak the instructions", "modify the method", "edit mt_abc123", or wants any modification to an existing .mthds bundle. Takes a bundle directory, or a registered method's catalog id (mt_…), which it resolves to the directory linked to it or pulls to disk first. Applies contract-preserving edits directly and routes structural or contract changes to /pipelex-design.
---

# Edit a MTHDS bundle

Modify an existing MTHDS method bundle. There are two classes of change; this skill applies the first and routes the second:

- **Contract-preserving edits** (this skill): prompt and instruction text, `description` and `system_prompt` wording, model references, operator settings, and mechanical renames of pipes, concepts or input variables. The method's structure — which pipes exist, how they wire, what each one takes and produces — stays the same.
- **Structural or contract changes** (route to `/pipelex-design`): adding, removing, or rewiring steps; changing any pipe's `inputs`/`output` beyond a pure rename; reshaping a concept's structure; refactoring the flow. These are design work: say in one line which pipe(s) the change touches, then invoke `/pipelex-design`, which re-enters existing methods adaptively. Never attempt a partial structural edit here.

## Requirements

- **`mthds_validate`** is required: it proves every edit. **Never declare an edit done on the hook's silence alone**: its semantic stage is skipped without an API key.
- **If the tool is absent from this session**, the Pipelex MCP server isn't connected: STOP, and tell the user in one line what [the connection reference](../shared/credentials.md#the-tool-is-absent) says for Mistral Vibe.
- **If a call returns `status: "error"` with an error of class `config`** (missing or rejected `PIPELEX_API_KEY`, unreachable API), STOP the same way and surface the error's `hint` verbatim; when it is about the key, read [where the key comes from](../shared/credentials.md#where-the-key-comes-from) before saying anything more.
- **`mthds_inputs_template`** is needed only by Step 6, when the edit could have touched the input template.

## Mode Selection

Automatic for clear, specific changes: state the planned edits in one line and proceed. Interactive for ambiguous or multi-part ones: present the planned edits and ask "Does this plan look right?" before applying.

| Signal | Mode |
|--------|------|
| "Rename X to Y" | automatic |
| "Update the prompt in pipe Z" with new text provided | automatic |
| "Add a step to do X" (open-ended) | structural → route to `/pipelex-design` |
| "Refactor this pipeline" (subjective) | structural → route to `/pipelex-design` |
| Multiple changes requested at once | interactive (confirm the plan first) |

## Process

### Step 1: Read the bundle

**For a catalog id (`mt_…`) or a published address**, read [the catalog-id reference](../shared/catalog-id.md) before reading any file. **When several directories are linked to the method, ask which is the work; never choose.** **Never present a linked directory as the saved method's current content.**

Read **every** `.mthds` file of the bundle directory outside `runs/` — the root, usually `main.mthds`, carries the `domain` header, `description` and `main_pipe`; module files carry the pipes and concepts — and find where the change lands.

### Step 2: Classify the change

Check the requested change against the scope split at the top. Structural or contract-changing → hand off to `/pipelex-design` now, before any files change. Everything else proceeds to the baseline. Classification calls no tool, so it comes before the baseline verdict on purpose.

### Step 3: Baseline verdict

Validate the whole bundle **before editing**: call `mthds_validate` with `files` for every file, and branch on the structured verdict, never on transport. Submit every `.mthds` file beneath the bundle directory **except anything under a `runs/` directory**, where `/pipelex-run` saves a completed run's artifacts: a method that emits or echoes a `.mthds` file would otherwise have its own output submitted as part of its source. Prefer the path form `{path: <absolute path to the file>}` — it keeps the real path as provenance in diagnostics and spares copying whole bundles into the request; the workshop resolves a path against **its own** working directory, wherever the harness launched it, so pass an absolute one. Inline `{content: <file content>, uri: <path relative to the bundle dir>}` is the fallback, and the only form the hosted console accepts.

- `is_valid: true` → record whether it is runnable or a scaffold (non-empty `pending_signatures`). That same state must hold after your edits.
- `is_valid: false` → the bundle is broken **before** your change: surface the `validation_errors[]` and the Markdown summary, and offer to repair first. **Never edit on a broken baseline.**

### Step 4: Apply the edits

Before editing a construct you have not touched recently, read [the MTHDS reference](../shared/mthds-reference.md). A rename is done only when **no stale reference remains**: grep the whole bundle for the old code.

- **Rename a pipe**: the `[pipe.<code>]` table header, every step or branch reference in controllers, and `main_pipe` in the root if it names this pipe.
- **Rename a concept**: the declaration, every `inputs`/`output` mention, `refines` references, `concept` fields inside structures, and field-reads in prompts (a `$var.field` stays keyed to the *variable*, but construct `from` paths and concept-typed fields name the concept).
- **Rename an input variable**: the pipe's `inputs` key and every `$var` / `@var` in its prompts. On the **main pipe** the client-facing template keys change, so Step 6 is mandatory.
- **Update a prompt**: the prose is free, but every `$var` / `@var` it references must still exist in the pipe's `inputs`.
- **Change a model reference**: the `model` field is optional; omit it to use defaults.

### Step 5: Re-validate

Same whole-bundle `mthds_validate` call as Step 3. The bar is the **baseline verdict restored**: `is_valid: true`, and the runnable or scaffold state unchanged (a renamed pending signature renames its backlog entry; nothing else in the pending set moves). On `is_valid: false` the failure is in your edit: use the summary's locators, fix, re-validate. On `status: "error"` the edit is applied but **unproven** — never report it as done: tell the user it is on disk but could not be validated, and offer to restore the pre-edit content you still hold from Step 1, or to retry once the server is reachable again.

### Step 6: Inputs refresh check

When the edit could have changed the input template (a renamed main-pipe input variable, a renamed boundary concept) and an `inputs.json` sits next to the bundle, re-project it: call `mthds_inputs_template` with the whole-bundle `files` and `explicit: false`, and compare its keys with `inputs.json`. Pure key renames may be applied in place; anything beyond that goes to `/pipelex-inputs`. Otherwise skip this step.

### Step 7: Report

State what changed (files and constructs), give the verdict line from the summary, and where the host renders MCP views, point to the method graph that accompanied the valid verdict. If inputs were refreshed or invalidated, say so. Suggest `/pipelex-inputs` when the user wants to prepare inputs, `/pipelex-run` when they want to run the method, and `/pipelex-catalog` when the edit should reach the saved method this directory is linked to.

**Generated types may now be stale.** Search the whole project for `sources.json` files carrying `"generator": "pipelex-integrate"` — `grep -rl '"pipelex-integrate"' --include=sources.json .` — which sit beside each generated tree (`src/generated/<method>/`, `<package>/generated/<method>/`), never beside the bundle, so looking only next to the `.mthds` files finds nothing. Keep each one whose `sources` name a `.mthds` file this change rewrote, moved or removed, **or whose `bundle_dir` holds a `.mthds` file this change created** — a new file is in no `sources` map, yet the call site loads every `.mthds` file under that directory. For each, say the generated types in that directory are now stale and offer `/pipelex-integrate` to refresh them: it regenerates in place and touches the call site only if the types no longer fit it.

**The saved method does not have this change.** When `pipelex-method.json` sits beside the root `.mthds` file, this directory is linked to a method in the organization's catalog: name it by the link's `name` and `mt_…` id and say that what just changed here is not in the catalog, so every caller of that id goes on running whatever is saved there. **Say that and no more.** The link records no hashes, so this directory may equally be behind the catalog — a teammate may have saved since it last synced — and calling the saved copy old asserts an ordering nothing here can read. `/pipelex-catalog` is what compares the two, and what updates the saved copy. **Offer that; never do it.** A save is a deployment — a production call site included runs the new content from its next call — so it happens when the user asks for it and not as the tail of somebody else's edit. No link file beside the root means this directory is not linked and there is nothing to say. Never write or edit `pipelex-method.json`: the workshop writes it, because it is the only party that knows which API host it talks to.

## Stops

| Condition | Do this |
|---|---|
| `status: "error"`, class `input_domain` | fix the call |
| `status: "error"`, class `runtime` | report it, and retry once before stopping |
| the same construct fails twice after your edit | pause and show the user instead of thrashing |

## References

- [MTHDS reference](../shared/mthds-reference.md): before editing a construct you have not touched recently.
- [Native content types](../shared/native-content-types.md): editing a prompt or construct path that field-reads a native concept (`Image.url`, `Page.text_and_images`, …).
