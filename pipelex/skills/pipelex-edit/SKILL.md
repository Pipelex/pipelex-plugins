---
name: pipelex-edit
description: Edit an existing MTHDS method bundle (.mthds files). Use when the user says "change this pipe", "update the prompt", "rename this concept", "rename this pipe", "change the model", "tweak the instructions", "modify the method", "edit mt_abc123", or wants any modification to an existing .mthds bundle. Takes a bundle directory, or a registered method's catalog id (mt_…), which it resolves to the directory linked to it or pulls to disk first. Applies contract-preserving edits directly and routes structural or contract changes to /pipelex-design.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - mcp__plugin_pipelex_pipelex__mthds_validate
  - mcp__plugin_pipelex_pipelex__mthds_inputs_template
---

# Edit a MTHDS bundle

Modify an existing MTHDS method bundle. There are two classes of change; this skill applies the first and routes the second:

- **Contract-preserving edits** (this skill): prompt and instruction text, `description` and `system_prompt` wording, model references, operator settings, and mechanical renames of pipes, concepts, or input variables. The method's structure — which pipes exist, how they wire, what each one takes and produces — stays the same.
- **Structural or contract changes** (route to `/pipelex-design`): adding, removing, or rewiring steps; changing any pipe's `inputs`/`output` beyond a pure rename; reshaping a concept's structure; refactoring the flow. These propagate — the parent wiring, concept shapes, and contracts all move together — so they are design work: say in one line which pipe(s) the change touches, then invoke `/pipelex-design` — it re-enters existing methods adaptively (a direct coherent edit for a fully understood shallow region, or signature-driven reopening for nested, uncertain, cross-module, or staged work). Never attempt a partial structural edit here.

## Requirements — the Pipelex MCP tools

This skill proves every edit with the **`mthds_validate`** tool, served by the plugin's `pipelex` MCP server. It is required — never declare an edit done on the hook's silence alone: the hook's semantic-validation stage is fail-open (it is skipped without an API key), so the MCP verdict is the authoritative check.

- **If the tool is absent from this session**, the Pipelex MCP server isn't connected: STOP, and tell the user in one line what [the connection reference](../shared/credentials.md#the-tool-is-absent) says for Claude Code.
- **If a call returns `status: "error"` with an error of class `config`** (missing or rejected `PIPELEX_API_KEY`, unreachable API), STOP the same way and surface the error's `hint` verbatim; when it is about the key, read [where the key comes from](../shared/credentials.md#where-the-key-comes-from) before saying anything more.
- **`mthds_inputs_template`** is needed only for the inputs-refresh check (Step 6) — when the edit cannot have touched the input template, it goes unused.

**Formatting is automatic.** Every write of a `.mthds` file triggers the plugin's validation hook: it lints, rewrites the file in canonical formatting, and blocks on syntax errors. Just write the files — don't hand-format, and re-read a file before editing it again after the hook reformatted it.

## The target — a bundle directory, or a catalog id

This skill works on files, so a **catalog id** (`mt_…`) is not a target it can act on directly: it is resolved to a directory on disk first, and everything after that is the ordinary file-based flow.

1. **Look for a directory already linked to that method.** One search over the link files, from the working directory down: `grep -rl '<the mt_… id>' --include=pipelex-method.json .`. Exactly one hit is the directory to work in — say which one, and go to **Step 1** below.
2. **Several hits are the user's choice, never yours.** More than one directory can legitimately hold the same link: `/pipelex-catalog`'s conflict path tells the user to pull a comparison copy into a sibling directory, and that copy carries the same link and is meant for reading, not for editing. Name the directories and ask which one is the work.
3. **No hit — hand the pull to `/pipelex-catalog`**. It brings the method's sources to disk and the workshop writes the link beside them; then carry on with that directory. The search only sees the working directory and below, so a bundle linked somewhere else reads as no hit — if the user knows where it is, ask for the path rather than pulling a second copy.

**What the search proves, and what it does not.** It answers where this method lives locally and nothing else. A linked directory can be behind the catalog, ahead of it, or both at once, and the link records no hashes to tell them apart — so do not present the local files as the saved method's current content. `/pipelex-catalog` is what compares the two, and it is also the only way the work done here reaches the saved copy.

**A published address is not a target for this skill.** `github.com/<owner>/<repo>[/<selector>][@<tag>]` names somebody else's published package: nothing of it is on disk, and there is nowhere to write a change back. Say so and point at `/pipelex-explain`, which reads such an address at the level of its contract.

## Mode Selection

**Default**: automatic for clear, specific changes; interactive for ambiguous or multi-part modifications.

| Signal | Mode |
|--------|------|
| "Rename X to Y" | automatic |
| "Update the prompt in pipe Z" with new text provided | automatic |
| "Add a step to do X" (open-ended) | structural → route to `/pipelex-design` |
| "Refactor this pipeline" (subjective) | structural → route to `/pipelex-design` |
| Multiple changes requested at once | interactive (confirm the plan first) |

In interactive mode, present the planned edits and ask "Does this plan look right?" before applying. In automatic mode, state the planned edits in one line and proceed.

## Process

### Step 1: Read the bundle

Locate the bundle directory and read **every** `.mthds` file in it (the root — usually `main.mthds` — carries the `domain` header, `description`, and `main_pipe`; module files carry the pipes and concepts). Understand where the change lands before touching anything.

### Step 2: Classify the change

Check the requested change against the scope split at the top. Structural or contract-changing → hand off to `/pipelex-design` now, before any files change. Everything else proceeds to the baseline.

Classification reads the bundle you already have and calls no tool, so it comes before the baseline verdict on purpose: `/pipelex-design` validates its own baseline when it re-enters, and a request routed there from here would otherwise have paid for two identical verdicts.

### Step 3: Baseline verdict

Validate the whole bundle **before editing**: call `mthds_validate` with `files` for every file, and branch on the structured verdict, never on transport. Submit every `.mthds` file beneath the bundle directory **except anything under a `runs/` directory**, where `/pipelex-run` saves a completed run's artifacts: a method that emits or echoes a `.mthds` file would otherwise have its own output submitted as part of its source. Prefer the path form `{path: <absolute path to the file>}` — it keeps the real path as provenance in diagnostics and spares copying whole bundles into the request; the workshop resolves a path against **its own** working directory, wherever the harness launched it, so pass an absolute one. Inline `{content: <file content>, uri: <path relative to the bundle dir>}` is the fallback, and the only form the hosted console accepts.

- `is_valid: true` → record whether it is runnable or a scaffold (non-empty `pending_signatures`). That same state must hold after your edits.
- `is_valid: false` → the bundle is broken **before** your change. Surface the `validation_errors[]` and the Markdown summary, and offer to repair first — never edit on a broken baseline, or your regressions and the pre-existing errors become indistinguishable.
- `status: "error"` → no verdict: class `config` → stop per the Requirements above; class `input_domain` → fix the call; class `runtime` → report and retry once.

### Step 4: Apply the edits

Use the Edit tool on the affected files. For renames, the edit is only done when **no stale reference remains** — grep the whole bundle for the old code:

- **Rename a pipe**: the `[pipe.<code>]` table header, every step/branch reference in controllers, and `main_pipe` in the root if it names this pipe.
- **Rename a concept**: the concept declaration, every `inputs`/`output` mention, `refines` references, `concept` fields inside structures, and field-reads in prompts (`$var.field` stays keyed to the *variable*, but construct `from` paths and concept-typed fields name the concept).
- **Rename an input variable**: the pipe's `inputs` key and every `$var` / `@var` reference in its prompts. If the variable belongs to the **main pipe**, the client-facing template keys change — Step 6 is mandatory.
- **Update a prompt**: the `$var` / `@var` references are contract, the prose around them is free — every variable referenced must still exist in the pipe's `inputs`.
- **Change a model reference**: the `model` field is optional — omit it to use defaults. See the language reference for accepted forms.

### Step 5: Re-validate

Same whole-bundle `mthds_validate` call as Step 3. The bar is the **baseline verdict restored**: `is_valid: true`, and the runnable/scaffold state unchanged (a renamed pending signature legitimately renames its backlog entry — anything else in the pending set should be untouched). On `is_valid: false`, the failure is in your edit: use the summary's locators, fix, re-validate. If the same construct fails twice, pause and show the user instead of thrashing. On `status: "error"` (no verdict — e.g. the MCP connection dropped after the write), the edit is applied but **unproven** — never report it as done: tell the user it is on disk but could not be validated, and offer to restore the pre-edit content you still hold from Step 1 or to retry validation once the server is reachable again.

### Step 6: Inputs refresh check

When the edit could have changed the input template — a renamed main-pipe input variable, a renamed boundary concept — re-project it: call `mthds_inputs_template` with the whole-bundle `files` submission plus `explicit: false`, so the fresh template arrives in the same light shape `/pipelex-inputs` writes into `inputs.json` (the tool's own default is the ceremonial `{concept, content}` envelope). If an `inputs.json` exists next to the bundle, compare its keys with the fresh template: pure key renames may be applied in place; anything beyond that goes to `/pipelex-inputs`. No `inputs.json`, or an edit that cannot touch the template → skip this step.

### Step 7: Report

State what changed (files and constructs), give the verdict line from the summary, and where the host renders MCP views, point to the method graph that accompanied the valid verdict. If inputs were refreshed or invalidated, say so. Suggest `/pipelex-inputs` when the user wants to prepare inputs, `/pipelex-run` when they want to run the method, and `/pipelex-catalog` when the edit should reach the saved method this directory is linked to.

**Generated types may now be stale.** Search the whole project for `sources.json` files carrying `"generator": "pipelex-integrate"` — `grep -rl '"pipelex-integrate"' --include=sources.json .` — which sit beside each generated tree (`src/generated/<method>/`, `<package>/generated/<method>/`), never beside the bundle, so looking only next to the `.mthds` files finds nothing. Keep each one whose `sources` name a `.mthds` file this change rewrote, moved or removed, **or whose `bundle_dir` holds a `.mthds` file this change created** — a new file is in no `sources` map, yet the call site loads every `.mthds` file under that directory. For each, say the generated types in that directory are now stale and offer `/pipelex-integrate` to refresh them: it regenerates in place and touches the call site only if the types no longer fit it.

**The saved method does not have this change.** When `pipelex-method.json` sits beside the root `.mthds` file, this directory is linked to a method in the organization's catalog: name it by the link's `name` and `mt_…` id and say that what just changed here is not in the catalog, so every caller of that id goes on running whatever is saved there. **Say that and no more.** The link records no hashes, so this directory may equally be behind the catalog — a teammate may have saved since it last synced — and calling the saved copy old asserts an ordering nothing here can read. `/pipelex-catalog` is what compares the two, and what updates the saved copy. **Offer that; never do it.** A save is a deployment — a production call site included runs the new content from its next call — so it happens when the user asks for it and not as the tail of somebody else's edit. No link file beside the root means this directory is not linked and there is nothing to say. Never write or edit `pipelex-method.json`: the workshop writes it, because it is the only party that knows which API host it talks to.

## Reference

- [MTHDS Language Reference](../shared/mthds-reference.md) — read for concept definitions and syntax before editing constructs you haven't touched recently
- [Native Content Types](../shared/native-content-types.md) — read when editing prompts or construct paths that field-read native concepts (`Image.url`, `Page.text_and_images`, ...)
