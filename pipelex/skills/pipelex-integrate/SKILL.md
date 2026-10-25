---
name: pipelex-integrate
description: Wire an MTHDS method into a Python or TypeScript codebase with generated, drift-proof types and one typed call site that runs it through @pipelex/sdk or pipelex-sdk. Use when the user says "use this method in my app", "call this from my code", "generate types for this method", "wire the method into my project", "typed client for this method", "refresh the generated types", "the types are stale", or wants application code that runs a .mthds method — from a local bundle, a catalog id (mt_…) or a published method_ref address. Also the refresh path after a bundle edit. Not for authoring or editing the method itself (/pipelex-design, /pipelex-edit), and not for a project that does not exist yet (/pipelex-scaffold).
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - mcp__plugin_pipelex_pipelex__mthds_validate
  - mcp__plugin_pipelex_pipelex__mthds_codegen
  - mcp__plugin_pipelex_pipelex__mthds_inputs_template
  - mcp__plugin_pipelex_pipelex__mthds_list_methods
---

# Integrate an MTHDS method into a codebase

Leave a project calling a method through one typed module, over generated types and an offline drift gate.

**Not** a runner or a design skill: it writes no tests, routes or UI, edits no business code, and **writes no client for another service before reading [fit.md](../shared/fit.md)**.

## Requirements

- **If a tool is absent from this session**, the Pipelex MCP server isn't connected: STOP, and tell the user in one line what [the connection reference](../shared/credentials.md#the-tool-is-absent) says for Claude Code.
- **If a call returns a problem in the `account` domain, or `client.unreachable`**, STOP the same way and relay its `next_step` verbatim; when it is about the key, read [where the key comes from](../shared/credentials.md#where-the-key-comes-from) before saying anything more. A **403** on `mthds_codegen` is a feature gate, not a key problem.
- **`mthds_list_methods`** is optional, for a method named without its id; never stop for it.

## Guards

Automatic unless the user asks to be walked through it; pause only for a genuinely ambiguous choice or where a step asks.

- **The write arm, always.** Every `mthds_codegen` call passes `output_dir`; a refused or failed write is a refusal, never a reason to write the returned bytes yourself.
- **Generated files are never opened for editing, never formatted, never linted**; a failure inside the tree is reported, never patched.
- **Never delete an orphan, and never offer to clean orphans up**.
- **Never generate from one source and run from another**: the call site runs the selector the sidecar records.
- **A project that owns a codegen harness keeps it**: never a second generated layout beside its own.
- **A `method_ref` is recorded exactly as it was passed, an absent tag included**, in a sidecar or a harness's manifest.
- **No `dropWireNulls` / `wireOutput` helper**.

## Process

### 1. Method, project, branch

Pass exactly one selector to every tool call:

- **Local files**: record and hash what step 2's `files_sent` lists. Pass the bundle directory as `method_dir`: the workshop sends its `.mthds` files and the templates their steps name, listed in `files_sent`. It refuses one outside **its own** working directory; relaunching the harness from a directory holding the bundle cures that. **Nothing else sends the call site's tree: a bundle out of its reach, or a workshop whose tools lack `method_dir` or answer it *Provide MTHDS files*, is a stop**; ask for that relaunch or a current workshop. A bundle outside the project is copied in first, where the language reference places it, and the user told. **A `METHODS.toml` in a parent of it, up to the one holding `.git`, is a stop.**
- **`method_ref: "github.com/<owner>/<repo>[/<selector>][@<tag>]"`**: **an address with no tag is accepted and floats** on the default branch: say so in one line, recommend the tag, and proceed.
- **`method_id: "mt_…"`**: **recommend pinning `mt_…@<n>`**, a published version, which never changes. A bare id follows each publish and `mt_…@draft` each save, so committed types can go stale: say so, and proceed with one only on the user's say-so.

**The project** is the nearest directory holding a `package.json`, a `pyproject.toml`, a `setup.py` or a `requirements.txt` at or above the working directory; several is a question, none means offering `/pipelex-scaffold`. Read its language reference now: [typescript.md](references/typescript.md) or [python.md](references/python.md).

**Check containment before writing anything**: the project root must sit at or under the directory this session was launched in, both resolved (`pwd -P`, `realpath`), or STOP: relaunch the harness from the project root. **Never write the tree into the workshop's directory and move it across.**

Before step 2, read your branch: a `codegen` script or Makefile target, or a `sources.json` with a `derived` map → [references/harness.md](references/harness.md); this method's `sources.json` (`"generator": "pipelex-integrate"`), a refresh request or an editing skill's hand-off → [references/refresh.md](references/refresh.md).

### 2. Validate

**`mthds_validate`** with the selector: integrable is `status: "ok"`, `is_valid: true`, `is_runnable: true`, `pending_signatures: []`. Anything else is a stop.

### 3. The signature

Type and run the call site against the verdict's **`main_pipe`** when it has one, never a signature derived from the source. **The run's `pipe_code` is its `pipe_ref` verbatim (`summarize.summarize_pdf`)**.

No `main_pipe` (a workshop at `@pipelex/mcp` 0.13.0 or earlier, for one) → read [references/signature-fallback.md](references/signature-fallback.md) before step 4.

### 4. Target and destination

State the target, the destination and the generator in one line. The target follows the audience:

| Project | Target |
|---|---|
| `package.json` with a TypeScript build | `ts-zod` |
| `pyproject.toml`, no `pipelex` dependency | `python-pydantic` |
| a Pipelex host: `pipelex` a dependency, code using `@pipe_func` or `StructuredContent` | `python-structures` |

The destination is one directory per method, `src/generated/<method>/` or `<package>/generated/<method>/` by default, in the language's casing. **A directory holding a `codegen.lock` is this method's only when a `sources.json` beside it names this method**: a target's methods emit the same file names, so another method's files would be silently overwritten, not orphaned. Choose another and say why, unless the user names the method it is for. This method's own interrupted run (its default destination, this target's artifacts, no sidecar) is regenerated in place. Unsure whose a tree is: ask; never relocate silently or clear it.

### 5. Tooling exclusions

Put the generated directory and the gate script step 10 copies in the formatter's and linter's ignores, per the language reference, keeping the tree type-checked and committed. **Do this before step 6**.

### 6. Generate

**`mthds_codegen`** with the selector, `target` and `output_dir`, relative to the workshop's working directory. Branch on the result:

- `status: "ok"`, `is_valid: true`, `output_dir` present → written; clean when `is_current: true` with an empty `orphans[]`.
- **`orphans[]` non-empty and `drifts[]` empty** → carry on to step 7 and read [references/orphans.md](references/orphans.md). Read it off the two lists, never from `is_current`; `drifts[]` is present only when non-empty, so no `drifts` is the empty case.
- **`client.target_exists`, a file this tool does not own** → that file is the user's: never delete, move or clear it, and never offer to; choose or ask for another directory, before the call too.
- anything else (`drifts[]` included) → the stops.

### 7. The sidecar

Write this unstamped `sources.json` beside the lock:

```json
{
  "comment": "Written by /pipelex-integrate, which refreshes it; never hand-edit.",
  "generator": "pipelex-integrate",
  "method": { "method_dir": "methods/summarize-pdf" },
  "target": "ts-zod",
  "pipe": { "pipe_ref": "summarize.summarize_pdf", "inputs": { "document": "native.Document", "context": "native.Text?" }, "output": "summarize.DocumentSummary" },
  "bundle_dir": "methods/summarize-pdf",
  "sources": { "methods/summarize-pdf/main.mthds": "<sha256>" },
  "templates": {}
}
```

`method` holds the selector as passed; paths are from the project root; `pipe` writes `Concept[]` for a list, `Concept?` for an optional. **`bundle_dir` is the call site's `BUNDLE_DIR`**, and `sources` hashes the `.mthds` files of `files_sent` with SHA-256; `templates` maps each step's `template_file` to its file's `{ "path", "sha256" }`, `{}` for none. A `method_ref` or `method_id` has no `bundle_dir` or `templates` and an empty `sources`.

### 8. Dependencies

With the project's package manager, at least: `zod`, `@pipelex/sdk` 0.48.0 (`ts-zod`); `pydantic`, `pipelex-sdk` 0.48.0 (`python-pydantic`); `pipelex` 0.79.0 (`python-structures`). Raise and report older pins.

### 9. The call site

One module per method from the language reference's template, in the project's service layer, sending **the whole `bundle_dir` as the method's tree** at call time, or running the recorded selector. **A list output (`variable`, `fixed`) arrives as `{"items": […]}`, never a bare array: narrow its `items`, as the template shows**. The module never reads credentials and never uploads (its docstring sends callers with files to `prepareInputs`). **Exactly one shared helper**, the client factory, serves every method.

### 10. The offline gate

Copy the gate from the project root with `cp`, never by rewriting it, and never format the copy. **A file already there without the line `Copied verbatim into a project by /pipelex-integrate` is the user's: ask first.**

- `ts-zod`: `mkdir -p scripts && cp "${CLAUDE_SKILL_DIR}/references/codegen-check.mjs" scripts/codegen-check.mjs`
- `python-pydantic`: `mkdir -p scripts && cp "${CLAUDE_SKILL_DIR}/references/codegen_check.py" scripts/codegen_check.py`

Wire it, or `python-structures`' `pipelex codegen check`, into the project's existing gate as the language reference shows; with none, the report says where to call it.

### 11. Verify

Format **only the files you wrote**, then run the type checker and the gate. Your code's failures are yours to fix; a gate red only over step 6's orphans is reported, not fixed.

### 12. Report

What was generated and where, the target and why, the call site's signature, the tooling changes, the gate's command, and any orphans as the orphans reference says. For an id not pinned, say what can move under the types; **for a `method_ref` with no tag, the types committed here are the ones the address resolved to on the day they were generated**, which no gate sees move. Refreshing is this skill again; then hand off to `/pipelex-inputs`.

## Stops

| Condition | Do this |
|---|---|
| invalid, unrunnable, or `pending_signatures` | STOP, nothing generated: `errors[]` to `/pipelex-design` or `/pipelex-edit`, else finish it in `/pipelex-design` |
| `domain: "input"` on `method_ref` / `method_id` | report it in the tool's words |
| `retry: "yes"`, or codegen's `client.write_failed` | retry once (codegen: same `output_dir`), then report what landed |
| `outside_workspace` at `output_dir` | step 1's containment: STOP, relaunch, say what is already written |
| `is_current: false`, not step 6's orphans case | report `drifts[]` verbatim and stop; commit nothing |
| no signature, by address or id | STOP as the fallback reference says; never guess the output concept |
| `python-structures`, its `pipelex-sdk` after step 8 unread or below the floor, templated bundle | STOP, nothing generated: [python.md](references/python.md) |
| `TS2835` | the TypeScript reference: yours in your module, the emitter's in `binder.ts` |
| a gate exits `2` | no verdict, not drift: read [references/gate-failures.md](references/gate-failures.md) |
| a `METHODS.toml` above `bundle_dir` (step 1, or a gate's `roots the tree` line) | STOP: move the bundle out from under it, or make `bundle_dir` the package root; a refresh clears neither it nor its `added` lines |
| `stale-source`: a file added, or no `bundle_dir` | [refresh mode](references/refresh.md); never add its hash to `sources` by hand |

## References

- [typescript.md](references/typescript.md), [python.md](references/python.md): step 1, by language.
- [refresh.md](references/refresh.md): refresh mode.
- [harness.md](references/harness.md): a codegen harness.
- [signature-fallback.md](references/signature-fallback.md): no `main_pipe`.
- [orphans.md](references/orphans.md): orphans, no drift.
- [gate-failures.md](references/gate-failures.md): a gate exits `2`.
- [codegen-check.mjs](references/codegen-check.mjs), [codegen_check.py](references/codegen_check.py): step 10's gates.
- [MTHDS reference](../shared/writing-mthds.md): the fallback's bundle reading.
