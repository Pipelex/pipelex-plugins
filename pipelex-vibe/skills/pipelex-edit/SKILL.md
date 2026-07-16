---
name: pipelex-edit
description: Edit an existing MTHDS method bundle (.mthds files). Use when the user says "change this pipe", "update the prompt", "rename this concept", "rename this pipe", "change the model", "tweak the instructions", "modify the method", "add a step", "remove this pipe", "refactor this pipeline", or wants any modification to an existing .mthds bundle. Applies contract-preserving edits directly and routes structural or contract changes to /pipelex-design.

---

# Edit a MTHDS bundle

Modify an existing MTHDS method bundle. There are two classes of change; this skill applies the first and routes the second:

- **Contract-preserving edits** (this skill): prompt and instruction text, `description` and `system_prompt` wording, model references, operator settings, and mechanical renames of pipes, concepts, or input variables. The method's structure — which pipes exist, how they wire, what each one takes and produces — stays the same.
- **Structural or contract changes** (route to `/pipelex-design`): adding, removing, or rewiring steps; changing any pipe's `inputs`/`output` beyond a pure rename; reshaping a concept's structure; refactoring the flow. These propagate — the parent wiring, concept shapes, and contracts all move together — so they are design work: tell the user which pipe(s) the change touches and that `/pipelex-design` re-enters existing methods (its "Editing an existing method" section), and stop. Never attempt a partial structural edit here.

## Requirements — the Pipelex MCP tools

This skill proves every edit with the **`mthds_validate`** tool, served by the plugin's `pipelex` MCP server. It is required — never declare an edit done on the hook's silence alone: the hook's semantic-validation stage is fail-open (it is skipped without an API key), so the MCP verdict is the authoritative check.

- **If the tool is absent from this session** (the MCP server isn't connected), STOP and tell the user in one line: *"The Pipelex MCP server isn't connected — check the plugin's MCP connection, or launch with `PIPELEX_MCP_URL` pointing at a running `pipelex-mcp` server."*
- **If a call returns `status: "error"` with an error of class `config`** (server unreachable, upstream API misconfigured, auth), STOP the same way and surface the error's `hint`.
- **`mthds_inputs_template`** is needed only for the inputs-refresh check (Step 6) — when the edit cannot have touched the input template, it goes unused.
- No API key is needed on your side — the MCP server authenticates to the API itself.

**Formatting is automatic.** Every write of a `.mthds` file triggers the plugin's validation hook: it lints, rewrites the file in canonical formatting, and blocks on syntax errors. Just write the files — don't hand-format, and re-read a file before editing it again after the hook reformatted it.

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

### Step 2: Baseline verdict

Validate the whole bundle **before editing**: call `mthds_validate` with `files: [{content: <file content>, uri: <path relative to the bundle dir>}]` for every file, and branch on the structured verdict, never on transport.

- `is_valid: true` → record whether it is runnable or a scaffold (non-empty `pending_signatures`). That same state must hold after your edits.
- `is_valid: false` → the bundle is broken **before** your change. Surface the `validation_errors[]` and the Markdown summary, and offer to repair first — never edit on a broken baseline, or your regressions and the pre-existing errors become indistinguishable.
- `status: "error"` → no verdict: class `config` → stop per the Requirements above; class `input_domain` → fix the call; class `runtime` → report and retry once.

### Step 3: Classify the change

Check the requested change against the scope split at the top. Structural or contract-changing → route to `/pipelex-design` now, before any files change. Everything else proceeds.

### Step 4: Apply the edits

Use the Edit tool on the affected files. For renames, the edit is only done when **no stale reference remains** — grep the whole bundle for the old code:

- **Rename a pipe**: the `[pipe.<code>]` table header, every step/branch reference in controllers, and `main_pipe` in the root if it names this pipe.
- **Rename a concept**: the concept declaration, every `inputs`/`output` mention, `refines` references, `concept` fields inside structures, and field-reads in prompts (`$var.field` stays keyed to the *variable*, but construct `from` paths and concept-typed fields name the concept).
- **Rename an input variable**: the pipe's `inputs` key and every `$var` / `@var` reference in its prompts. If the variable belongs to the **main pipe**, the client-facing template keys change — Step 6 is mandatory.
- **Update a prompt**: the `$var` / `@var` references are contract, the prose around them is free — every variable referenced must still exist in the pipe's `inputs`.
- **Change a model reference**: the `model` field is optional — omit it to use defaults. See the language reference for accepted forms.

### Step 5: Re-validate

Same whole-bundle `mthds_validate` call as Step 2. The bar is the **baseline verdict restored**: `is_valid: true`, and the runnable/scaffold state unchanged (a renamed pending signature legitimately renames its backlog entry — anything else in the pending set should be untouched). On `is_valid: false`, the failure is in your edit: use the summary's locators, fix, re-validate. If the same construct fails twice, pause and show the user instead of thrashing.

### Step 6: Inputs refresh check

When the edit could have changed the input template — a renamed main-pipe input variable, a renamed boundary concept — re-project it: call `mthds_inputs_template` with the whole-bundle `files` submission (defaults only). If an `inputs.json` exists next to the bundle, compare its keys with the fresh template: pure key renames may be applied in place; anything beyond that goes to `/pipelex-inputs`. No `inputs.json`, or an edit that cannot touch the template → skip this step.

### Step 7: Report

State what changed (files and constructs), give the verdict line from the summary, and where the host renders MCP views, point to the method graph that accompanied the valid verdict. If inputs were refreshed or invalidated, say so. Suggest `/pipelex-inputs` when the user wants to prepare inputs or run the method.

## Reference

- [MTHDS Language Reference](../shared/mthds-reference.md) — read for concept definitions and syntax before editing constructs you haven't touched recently
- [Native Content Types](../shared/native-content-types.md) — read when editing prompts or construct paths that field-read native concepts (`Image.url`, `Page.text_and_images`, ...)
