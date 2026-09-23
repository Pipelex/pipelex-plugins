---
name: pipelex-inputs
description: Prepare inputs for MTHDS methods. Use when user says "prepare inputs", "create inputs", "use my files", "generate test data", "synthesize inputs", "mock inputs", "I have a PDF/image/document to use", "make sample data", or wants to create inputs.json for running a .mthds pipeline. Works from a local .mthds bundle, from a registered method's catalog id (mt_…), or from a published method's address (github.com/owner/repo[/selector][@tag]) — also use when the user names one of those, e.g. "prepare inputs for mt_abc123" or "prepare inputs for github.com/Pipelex/methods/documents". Handles user-provided files, synthetic data generation, placeholder templates, and mixed approaches. Defaults to automatic mode.
---

# Prepare Inputs for MTHDS methods

The one entry point for a method's inputs — placeholders, synthetic data, the user's files, or a mix — through to run-ready inputs. **Not** a runner: that is `/pipelex-run`, which this skill ends by offering.

## Requirements

- **`mthds_inputs_template`** is required: never hand-derive the template from the `.mthds` source.
- **If the tool is absent from this session**, the Pipelex MCP server isn't connected: STOP, and tell the user in one line what [the connection reference](../shared/credentials.md#the-tool-is-absent) says for Mistral Vibe.
- **If a call returns `status: "error"` with an error of class `config`** (missing or rejected `PIPELEX_API_KEY`, unreachable API), STOP the same way and surface the error's `hint` verbatim; when it is about the key, read [where the key comes from](../shared/credentials.md#where-the-key-comes-from) before saying anything more. Never silently improvise a template.
- **`mthds_prepare_inputs`** is required at step 5, under the same two stops; never hand-fake a storage reference.
- **`mthds_list_methods`** is optional: it resolves a saved method named without its `mt_…` id. When it is absent, work from a bundle or an id the user gives; never stop for it.

## Mode

**Default**: automatic — name the strategy and the assumptions it rests on in one line, then carry the chosen strategy through to its own end without stopping, pausing only where a wrong guess would waste work. **Go interactive** when the user asks for it ("walk me through", "step by step", "let me decide"), or when the table below lands on its no-signal row and there is somebody to ask who has not said "just do it" or "don't ask": ask what the strategy's reference lists before filling anything (at the no-signal row, first whether they have files or want synthetic data), and show the assembled set before preparing it. **Either mode can turn into the other mid-run**: a question or a correction makes the current step interactive, and "looks good, go ahead" makes the rest automatic.

## Guards

- **The template is authoritative**: fill its values; never invent shapes it doesn't have.
- **A path in `inputs.json` resolves relative to `inputs.json` itself, never to the working directory**: copy a local file into `<output_dir>/inputs/` and write `inputs/the_doc.pdf` (preferred), or write a URL or an absolute path.

## Process

### 1. The target

The target takes three forms, and every call takes exactly one selector; a second is refused at the extra field.

- **A local bundle**, the usual case, as `files`: `<output_dir>` is its directory, usually the one holding `main.mthds`. Submit every `.mthds` file beneath the bundle directory **except anything under a `runs/` directory**, where `/pipelex-run` saves a completed run's artifacts: a method that emits or echoes a `.mthds` file would otherwise have its own output submitted as part of its source. Prefer the path form `{path: <absolute path to the file>}` — it keeps the real path as provenance in diagnostics and spares copying whole bundles into the request; the workshop resolves a path against **its own** working directory, wherever the harness launched it, so pass an absolute one. Inline `{content: <file content>, uri: <path relative to the bundle dir>}` is the fallback, and the only form the hosted console accepts.
- **A registered method**, an `mt_…` id with no local bundle in play, as `method_id`: its current stored content, which needs the API key. `<output_dir>` is a directory the user names, by default a new `./<method_id>/`.
- **A published method**, as `method_ref: "github.com/<owner>/<repo>[/<selector>][@<tag>]"`: read [references/published-address.md](references/published-address.md) before the first call. **An address with no tag is accepted, and it floats**: say so in one line, recommend the tag, and carry on.

`inputs.json` goes in `<output_dir>`, data files in `<output_dir>/inputs/`, created only when there are files to store.

### 2. The template

Call **`mthds_inputs_template`** with the selector and **`explicit: false`**: the tool defaults to the `{concept, content}` envelope, and this skill works in the light shape. It resolves the declared `main_pipe`; for another pipe, pass `pipe_ref` as a qualified `domain.pipe_code`. Branch on the structured verdict, never on transport: `status: "ok"` with `is_valid: true` returns the template in `inputs`, with its resolved `pipe_ref`. Anything else is a stop.

### 3. The strategy

Evaluated in order:

| Signal | Strategy |
|---|---|
| User gives file or folder paths, or says "my data" / "this file" / "use these images" / "here's my PDF" | **User data**, or **Mixed** if inputs remain unfilled |
| User says "test data" / "generate inputs" / "synthesize" / "fake data" / "sample data" | **Synthetic** |
| User says "template" / "schema" / "placeholder" / "what inputs does it need?" | **Template** |
| No clear signal (e.g. right after `/pipelex-design`, with no further context) | **Template**, then offer to populate |

- **Template**: replace each file-ish mock URL (an `https://` URL on a `.invalid` host) with `"<VARNAME-url-or-path-relative-to-this-inputs-file>"`, never `"<path-to-VARNAME>"`; save, show it with its path, and offer synthetic data or the user's files.
- **Synthetic**: read [references/synthetic.md](references/synthetic.md) before generating anything. **`pipelex-synthetic-inputs` is the file factory**, and makes every file input. Mistral Vibe has no cross-skill invocation, so open `../pipelex-synthetic-inputs/SKILL.md` and follow it.
- **User data**: read [references/user-data.md](references/user-data.md) before matching any file to an input.
- **Mixed**: the user's files first, then synthetic values for what they leave unfilled; read both references.

### 4. Save

Fill the step 2 template in place, a composite native's fields included ([what they mean](../shared/native-content-types.md)), and save it as `<output_dir>/inputs.json`. An input the signature cannot shape, such as a Dynamic one, keeps its `{concept, content}` envelope exactly as the template gives it.

### 5. Prepare the inputs for a run

A run on the hosted API cannot read this disk, so `mthds_prepare_inputs` uploads every file-ish value (Image, Document) that is a local path, a `data:` URL or inline bytes to Pipelex storage, as a `pipelex-storage://` reference. Skip the call for the Template strategy, whose placeholders are not assets. Otherwise **first delete any `inputs.prepared.json` an earlier prepare left in `<output_dir>`**: a skipped, declined or failed prepare writes none, and a run would read the old one. Skip the call too **when every file-ish value is already an `http(s)` URL or a `pipelex-storage://` reference**: a run then reads `inputs.json`.

**Say what is about to leave the machine, before it does**: each file and where it goes (Pipelex storage, the user's organization, through their API key), or for a folder batch too long to list, the count and the folder; in interactive mode wait for a yes, in automatic mode state it and proceed. If the user declines, stop before the call and report that the inputs stay local and are not runnable.

**Send the exact file that was selected, generated, copied or referenced for an input — never a derived one**, whatever its type. A preflight size check may inform the report, but it is never a reason to transform, derive, or substitute the asset. Do not compress, optimize, re-encode, resize, downsample, split, truncate, extract pages or content, or convert it. Do not replace it with synthetic data, a public sample, another local file, or any derived file. The same prohibition applies after an upload failure. Never retry preparation with altered or substitute content to evade a storage limit.

Call it with step 2's target, step 2's `pipe_ref` if it passed one (the signature decides which values are assets), and as `inputs` the saved `inputs.json` with **every local file path resolved to an absolute path** in the request alone, as for `files`, and no `explicit` flag.

On `status: "ok"`, **write `<output_dir>/inputs.prepared.json` with the returned `inputs`, and leave `inputs.json` exactly as it is**: it is the source, and prepare never rewrites it. The prepared file is a plain inputs object, the same keys with no envelope, no hash and no sidecar, where each file value is now `{"url": "pipelex-storage://…"}`, the run-ready form — never "simplify" it back to a string — and every other value is untouched. Leave the copies in `<output_dir>/inputs/` alone. When `<output_dir>` is in a git repository whose ignore rules do not cover it, add `inputs.prepared.json` to the nearest `.gitignore` and say so. Report it in one line: the files uploaded, and `inputs.prepared.json` written beside an unchanged `inputs.json`.

`/pipelex-run` judges whether a prepared file is current, but a file moved over the original keeps its old timestamp and escapes it: **prepare again whenever a file was replaced in place.**

### 6. Offer the run

Say what is ready: the source values in `inputs.json`, the run-ready form in `inputs.prepared.json` where prepare wrote one, or the Template strategy's placeholders still to fill. When the workspace holds a codebase (a `package.json` or a `pyproject.toml`) the method is not wired into, add that `/pipelex-integrate` gives it generated types and a typed call site.

**Offer the run, never start it**: it spends inference credit, so the user's yes buys it, and everything past that yes is `/pipelex-run`'s, whose `SKILL.md` sits beside this one on Mistral Vibe, which has no cross-skill invocation; never call a run tool here. Offer only when:

- no placeholder remains;
- **every input the template asked for is filled** — one the factory could not make is absent, passes every other check and guarantees a failed run: say which input waits on the user, and why;
- the inputs are run-ready: prepare wrote `inputs.prepared.json`, or step 5 skipped it because nothing needed uploading. If prepare failed, report that and what fixing it takes.

The offer names the file the run reads — `inputs.prepared.json` where prepare wrote one, `inputs.json` where prepare was skipped — and the target: the bundle, or the id or the address itself.

## Stops

| Condition | Do this |
|---|---|
| template: `is_valid: false` | report `validation_errors[]` and the summary. A local bundle is repaired first (`/pipelex-design` resumes it), then retried; a registered method is fixed where it is edited (the webapp editor), not here; a published one is reported as [its reference](references/published-address.md) says |
| template: `input_domain` | an unknown `pipe_ref` or unresolvable `main_pipe`: pass an explicit `pipe_ref`. At `method_id` or `method_ref`, report it in the tool's words; another organization's id reads as a miss |
| `runtime`, either call | report, and retry once |
| the factory returns no path | leave that one input unfilled, carry on with the others; report the reason and ask for the user's own file. Never fabricate a value or abandon `inputs.json` |
| prepare: `input_domain` at `inputs`, `pipe_ref`, `method_id` or `method_ref` | read [references/prepare-errors.md](references/prepare-errors.md) before replying or retrying; a storage size limit at `inputs` is terminal for this attempt |
| prepare, by address: `input_domain` at `files`, or `config` (the credential first, as the requirements say) | read [references/published-address.md](references/published-address.md) before naming a cause |

## References

- [synthetic.md](references/synthetic.md), [user-data.md](references/user-data.md): step 3, by strategy; both for Mixed.
- [published-address.md](references/published-address.md): a `method_ref` target.
- [prepare-errors.md](references/prepare-errors.md): prepare's `input_domain` errors.
- [Native content types](../shared/native-content-types.md), [MTHDS reference](../shared/mthds-reference.md): natives' fields, concepts.
