---
name: pipelex-inputs
description: Prepare inputs for MTHDS methods. Use when user says "prepare inputs", "create inputs", "use my files", "generate test data", "synthesize inputs", "mock inputs", "I have a PDF/image/document to use", "make sample data", or wants to create inputs.json for running a .mthds pipeline. Works from a local .mthds bundle, from a registered method's catalog id (mt_…), or from a published method's address (github.com/owner/repo, optional /selector and @tag) — also when the user names one, e.g. "prepare inputs for mt_abc123".
---

# Prepare Inputs for MTHDS methods

The one entry point for a method's inputs, through to run-ready inputs.

## Requirements

- **`mthds_inputs_template`** is required: never hand-derive the template from the `.mthds` source.
- **If the tool is absent from this session**, the Pipelex MCP server isn't connected: STOP, and tell the user in one line what [the connection reference](../shared/credentials.md#the-tool-is-absent) says for Mistral Vibe.
- **If a call returns a problem in the `account` domain, or `client.unreachable`** (missing or rejected `PIPELEX_API_KEY`, unreachable API), STOP the same way and relay its `next_step` verbatim; when it is about the key, read [where the key comes from](../shared/credentials.md#where-the-key-comes-from) before saying anything more. Never silently improvise a template.
- **`mthds_prepare_inputs`** is required at step 5, under the same two stops, except `auth.forbidden` on a call with `kind` (see Stops); never hand-fake a storage reference.
- **`mthds_list_methods`** and **`mthds_list_files`** are optional: without the first, ask for a saved method's `mt_…` id.

## Mode

**Default**: automatic — name the strategy and the assumptions it rests on in one line, then carry it through to its own end, pausing only where a wrong guess would waste work. **Go interactive** when the user asks for it ("walk me through", "let me decide"), or when the table below lands on its no-signal row and there is somebody to ask who has not said "just do it": ask what the strategy's reference lists before filling anything (at the no-signal row, first whether they have files or want synthetic data), and show the assembled set before preparing it. **Either mode can turn into the other mid-run**: a question or a correction makes the step interactive, a "go ahead" the rest automatic.

## Guards

- **The template is authoritative**: fill its values; never invent shapes it doesn't have.
- **A path in `inputs.json` resolves relative to `inputs.json` itself, never to the working directory**: write a local file's absolute path, a case's copy as `inputs/the_doc.pdf`, or a URL.
- **A share link to a private drive or workspace (Google Drive, OneDrive, SharePoint, Notion) is not a document**: a run fetches it without the user's sign-in, so download or export the file first.
- **A file is uploaded where it lies, never copied beside the method**: unless the calling skill asks for a case's copies, as `/pipelex:pipelex-lab` does, or `<output_dir>` is a lab case, `lab/<method>/cases/<case>/`, copy nothing into `<output_dir>` and write no `inputs.prepared.json`.
- **The user's own files stay out of version control**: in a git repository, `git check-ignore -q` `inputs.json` when a value holds a file's text, a case's copies before writing them and its `inputs.prepared.json` before step 5's call. For a path not ignored, add `inputs.json` or `inputs.prepared.json`, anchored with a leading `/`, to the nearest `.gitignore`, relative to that file's directory, say so, and check again: **git never ignores a tracked path, so one still not ignored is not written until the user says so.**

## Process

### 1. The target

The target takes three forms, one selector per call.

- **A local bundle**, the usual case: `<output_dir>` is its directory, usually the one holding `main.mthds`, unless the caller names another. Pass the bundle directory as `method_dir`: the workshop sends its `.mthds` files and the templates their steps name, listed in `files_sent`. It refuses one outside **its own** working directory; relaunching the harness from a directory holding the bundle cures that. Inline `files` (the bundle's `.mthds` files outside `runs/`, root file first, as `{content, uri}`) are the fallback for a bundle with no template file; **for a templated one, stop and ask for that relaunch**. A workshop whose tools lack `method_dir`, or answer it *Provide MTHDS files*, is older: read [the reference](../shared/writing-mthds.md#template-files) first.
- **A registered method**, an `mt_…` id with no local bundle in play, as `method_id`: bare, the latest published version; `@draft`, the draft; `@<n>`, version n. **Say which one the template came from** (`method_version`) and offer the run on that same form; a bare id never published is refused as `pipelex.catalog.not_published`, and `mt_…@draft` is then the target. `<output_dir>` is a directory the user names, by default a new `./<method_id>/` without the suffix.
- **A published method**, as `method_ref: "github.com/<owner>/<repo>[/<selector>][@<tag>]"`: read [published-address.md](references/published-address.md) before the first call. **An address with no tag is accepted, and it floats**: say so in one line, recommend the tag, and carry on.

### 2. The template

Call **`mthds_inputs_template`** with the selector and **`explicit: false`**, for bare values. It resolves the declared `main_pipe`; for another pipe, pass `pipe_ref` as a qualified `domain.pipe_code`. `status: "ok"` with `is_valid: true` returns the template in `inputs`, with its resolved `pipe_ref`; anything else is a stop.

### 3. The strategy

**A file fills an input only when its role is a sample input**: read [file-roles.md](../shared/file-roles.md) before matching one whose role is unsettled. Then, in order:

| Signal | Strategy |
|---|---|
| Files or folders the user gives as sample inputs | **User data**, or **Mixed** if inputs remain unfilled |
| User says "test data" / "generate inputs" / "synthesize" / "fake data" / "sample data" | **Synthetic** |
| User says "template" / "schema" / "placeholder" / "what inputs does it need?" | **Template** |
| No clear signal (e.g. right after `/pipelex:pipelex-design`, with no further context) | **Template**, then offer to populate |

- **Template**: replace each file-ish mock URL (an `https://` URL on a `.invalid` host) with `"<VARNAME-url-or-path-relative-to-this-inputs-file>"`, never `"<path-to-VARNAME>"`; save, show it with its path, and offer synthetic data or the user's files.
- **Synthetic**: read [synthetic.md](references/synthetic.md) before generating anything. **`pipelex-synthetic-inputs` is the file factory**, and makes every file input. Mistral Vibe has no cross-skill invocation, so open `../pipelex-synthetic-inputs/SKILL.md` and follow it.
- **User data**: read [user-data.md](references/user-data.md) before matching any file to an input.
- **Mixed**: the user's files first, then synthetic values for what they leave unfilled; read both references.
- **The team's files**: read [team-files.md](../shared/team-files.md) before asking for a file, or for one named but not on disk.

### 4. Save

Fill the step 2 template in place, a composite native's fields included ([natives](../shared/native-content-types.md), [concepts](../shared/writing-mthds.md)), and save it as `<output_dir>/inputs.json`. An input the signature cannot shape, such as a Dynamic one, keeps its `{concept, content}` envelope exactly as the template gives it.

### 5. Prepare the inputs for a run

`mthds_prepare_inputs` uploads each local path, `data:` URL or inline bytes at a file input to Pipelex storage. Skip the call for the Template strategy. Otherwise, for a case's copies, **first delete any `inputs.prepared.json` an earlier prepare left in `<output_dir>`**. Skip the call too **when every file-ish value is already an `http(s)` URL or a `pipelex-storage://` reference**: a run then reads `inputs.json`.

**Say what is about to leave the machine, before it does**: each file and where it goes (Pipelex storage, the user's organization, through their API key), or for a folder batch too long to list, the count and the folder; in interactive mode wait for a yes, in automatic mode state it and proceed. If the user declines, stop before the call and report that the inputs stay local and are not runnable.

**Send the exact file that was selected, generated, copied or referenced for an input — never a derived one**, whatever its type. A preflight size check may inform the report, but it is never a reason to transform, derive, or substitute the asset. Do not compress, optimize, re-encode, resize, downsample, split, truncate, extract pages or content, or convert it. Do not replace it with synthetic data, a public sample, another local file, or any derived file. The same prohibition applies after an upload failure. Never retry preparation with altered or substitute content to evade a storage limit. **An Office file's PDF export, made at matching, is the one exception**: it is the selected file from then on.

Call it with step 2's target, step 2's `pipe_ref` if it passed one, and as `inputs` the saved `inputs.json` with **every local file path resolved to an absolute path** in the request alone, and no `explicit` flag. The factory's files take `kind`: read [synthetic.md](references/synthetic.md#test-files) before the call.

On `status: "ok"`, **write the returned `inputs` over `<output_dir>/inputs.json`**, or for a case's copies **into `<output_dir>/inputs.prepared.json`, leaving `inputs.json` and the copies exactly as they are**. Either is a plain inputs object, the same keys with no envelope, no hash and no sidecar, where each file value is now `{"url": "pipelex-storage://…"}`, the run-ready form — never "simplify" it back to a string — and every other value is untouched. Report the uploads and the file written, in one line.

An address names the bytes uploaded: outside a case, a replaced file goes up again only once named again, its path back in `inputs.json`; in a case, the run's currency check misses a file moved over its copy, so **prepare again whenever a file was replaced in place.**

### 6. Offer the run

Say what is ready, or which placeholders are left. When a codebase here does not call the method yet, add that `/pipelex:pipelex-integrate` wires it in.

**Offer the run, never start it**: it spends inference credit, so the user's yes buys it, and everything past that yes is `/pipelex:pipelex-run`'s, whose `SKILL.md` sits beside this one on Mistral Vibe, which has no cross-skill invocation; never call a run tool here. Offer only when:

- no calling skill asked to stop at run-ready (a user who said not to run still gets the offer: an offer is not a run);
- no placeholder remains;
- **every input the template asked for is filled** — one the factory could not make is absent: say which input waits on the user, and why;
- the inputs are run-ready: prepare succeeded, or step 5 skipped it because nothing needed uploading.

The offer names the file the run reads — `inputs.prepared.json` where prepare wrote one, else `inputs.json` — and the target.

## Stops

| Condition | Do this |
|---|---|
| template: `is_valid: false` | report `errors[]` and the summary. A local bundle is repaired first (`/pipelex:pipelex-design` resumes it), then retried; a registered method through `/pipelex:pipelex-edit`, not here; a published one is reported as [its reference](references/published-address.md) says |
| template: `request.pipe_not_found` or `request.pipe_ambiguous` | pass an explicit `pipe_ref`. Another `domain: "input"` problem: report it in the tool's words; another organization's id reads as a miss |
| `retry: "yes"`, either call | report, and retry once |
| the factory returns no path | leave that one input unfilled, carry on with the others; report the reason and ask for the user's own file. Never fabricate a value or abandon `inputs.json` |
| prepare with `kind`: `auth.forbidden`, or a refusal naming `kind`, or `method_id` for `method_not_found`, `method_being_deleted` or `version_suffix` | read [synthetic.md](references/synthetic.md#test-files) before preparing again without `kind` |
| prepare: an `input` or `method` problem, not a refusal of `kind` | read [prepare-errors.md](references/prepare-errors.md) before replying or retrying; a storage size limit at `inputs` is terminal for this attempt |
| prepare, by address: refused at `files`, or an `account` problem | read [published-address.md](references/published-address.md) before naming a cause |

## References

- [synthetic.md](references/synthetic.md), [user-data.md](references/user-data.md): step 3, by strategy.
- [published-address.md](references/published-address.md): a `method_ref` target.
- [prepare-errors.md](references/prepare-errors.md): prepare's input and method problems.
