---
name: pipelex-run
description: Run an MTHDS method on the hosted Pipelex API, and follow a run that is already going. Use when the user says "run this method", "run the pipeline", "execute the method", "run mt_abc123", "run the draft", "run github.com/Pipelex/methods/documents", "how is run X going", "what's the status of that run", "get the results of run X", "do a dry run first", or "download the files from yesterday's run". Takes a bundle directory, a catalog id (mt_…) or a published address (github.com/owner/repo, optional /selector and @tag), with run-ready inputs from /pipelex-inputs. A run spends inference credit, so this skill never starts one nobody asked for.
---

# Run an MTHDS method

This skill owns the run lifecycle: Start a run from a target and its inputs, or Follow a run from a run id alone; a dry run is step 2, shown.

## Requirements

- **`mthds_run`**, **`mthds_run_status`** and **`mthds_run_results`** are required, and to start a run **`mthds_validate`** and **`mthds_inputs_template`** too: they keep credit from being spent on a method or inputs that cannot work.
- **If the run tools are absent from this session**, the Pipelex MCP server isn't connected: STOP, and tell the user in one line what [the connection reference](../shared/credentials.md#the-tool-is-absent) says for Codex. Never improvise a run id, a status or an output.
- **If a call returns `status: "error"` with an error of class `config`** (missing or rejected `PIPELEX_API_KEY`, unreachable API), STOP the same way and surface the error's `hint` verbatim; when it is about the key, read [where the key comes from](../shared/credentials.md#where-the-key-comes-from) before saying anything more.
- **`mthds_download_artifacts`**, **`mthds_list_methods`**, **`mthds_list_files`**: optional, never stop for one.

## Start a run

### 1. The target and the pipe

The target is a **bundle directory**, submitted as `method_dir`; a registered method's **`mt_…` id**, as `method_id`: read [by-id.md](references/by-id.md) before the first call; or a **published method's address**, `github.com/<owner>/<repo>[/<selector>][@<tag>]`, as `method_ref`: read [published-address.md](references/published-address.md) before the first call. A saved method named without its id is resolved through `mthds_list_methods`, choosing by name and description and asking when several fit; without that tool, ask for it. **When an address and another target are both in hand, ask which one is meant; never pick one yourself**: a run is paid.

The pipe is the declared main pipe unless the user named another: **carry its `pipe_ref` through every call**, the code qualified by its own file's domain.

### 2. Prove the target before spending credit

For a **bundle directory**, **first write a `.gitignore` holding `*` into each `runs/` in it that lacks one and whose folders hold `main_stuff.json`; add `*` to the `.gitignore` of each `inputs/` beside an `inputs.json`, and `/inputs.prepared.json` to the one beside that file, wherever the line is missing**, saying so, then one `mthds_validate` call on it. Pass the bundle directory as `method_dir`: the workshop sends its `.mthds` files and the templates their steps name, listed in `files_sent`. It refuses one outside **its own** working directory; relaunching the harness from a directory holding the bundle cures that. Inline `files` (the bundle's `.mthds` files outside `runs/`, root file first, as `{content, uri}`) are the fallback for a bundle with no template file; **for a templated one, stop and ask for that relaunch**. A workshop whose tools lack `method_dir`, or answer it *Provide MTHDS files*, is older: read [the reference](../shared/writing-mthds.md#template-files) first. For an **`mt_…` id**, the same call with `method_id` in place of `method_dir`; for an address, `method_ref`.

The bar is `is_valid: true`, `is_runnable: true` and an empty `pending_signatures`. Short of it, report the verdict and route to `/pipelex-design`, or to `/pipelex-edit` when the fix is contract-preserving; an address's verdict is reported as [its reference](references/published-address.md) says. Never run a method that did not pass. **Report a valid verdict's `warnings`**, and read [template files](../shared/writing-mthds.md#template-files) before acting on a `template_check_warning`.

**A dry run is this step, shown.** A run on test files is a real run. **When the verdict carries `graph_page.written: true`, give the page's `path` before the text flow**, for a browser to open. Pass on a new page's note that a project under git may want to ignore it. A `graph_page.error` gets one line, and the verdict stands. Show the flow as numbered text: each step, what it reads and makes, where it batches or branches, and which steps call a model. For an id or an address, give the contract from the verdict's `main_pipe` instead. Say that no model ran and nothing was spent. **Then end the turn there, even when the same request asked for the real run too**: the flow is the reply, and the paid run waits for the user's go.

### 3. The inputs

They sit beside the bundle unless the caller named another directory. For an id, in the one the user named, else where [by-id.md](references/by-id.md) says: take the one holding an `inputs.json`, and say which. **When several do, ask which; never choose.** In this order, take the first that applies:

1. **Values the user gave in the request**, laid over a current `inputs.prepared.json` in a lab case, `lab/<method>/cases/<case>/`, else over `inputs.json`: replace only the keys the user named and keep every other. With neither file, the request's values are the whole set. For a file named but not on disk, read [team-files.md](../shared/team-files.md) before asking for it.
2. **A lab case's current `inputs.prepared.json`**. **Current** means, key by key, every value that is not a file is equal in it and in `inputs.json`, and neither `inputs.json` nor any local file it names is newer than it. Not current is not run-ready: hand to `/pipelex-inputs`.
3. **An `inputs.json` whose every file-ish value is an `http(s)` URL or a `pipelex-storage://` reference.**
4. **An empty object**, when the pipe declares no input at all.

Then call **`mthds_inputs_template`** once, with the same target and `explicit: false`, and check the inputs against it on **both keys and value shapes**: the key set, where a key the inputs lack is fine when the run is on the main pipe and step 2's verdict marks it `required: false`, and per key the JSON kind and a structured value's field names. A `{concept, content}` envelope the template does not show is checked by its `content`, a one-field `{"text": …}` standing for a bare value, and a file input held as `{"url": "pipelex-storage://…"}` where the template shows a string is the prepare rewrite; neither is drift.

Anything else — a placeholder, a local path, a `data:` URL, inline bytes, a real drift — is not run-ready, and nothing is spent: name the input at fault and how, and hand to `/pipelex-inputs`; there is no cross-skill invocation on Codex, so open that skill's `SKILL.md` beside this one and follow it. Do not prepare inputs here.

### 4. Say what is about to run

One line before the call: the target, the pipe, where the inputs came from and which keys the request replaced, and that the run spends inference credit. **On a dry-run request this step comes only after the user's go**: a paid run never starts on a dry-run request whose flow the user has not been shown.

> Running the main pipe `summarize.summarize_pdf` from `summarize_pdf/`, with the inputs in `inputs.json`. This spends inference credit.

**When a bundle directory holds a `PipeFunc`, the line says its Python does not travel**, and that a method saved through `/pipelex-catalog` and run as `mt_…@draft` carries it.

The user asking for the run is the consent; there is no second confirmation. **Never start a run nobody asked for.** A `/pipelex-lab` case is the exception: its runs wait for the user's go on its keys, even when the request asked for them.

### 5. `mthds_run`, and the run id first

Call `mthds_run` with the same target and, as `inputs`, the values step 3 settled on, verbatim. Omit `pipe_code` to run the declared main pipe; for another pipe, pass step 1's `pipe_ref` as `pipe_code`.

When `pipelex-method.json` sits beside the root `.mthds` file, send its `method_id` beside step 2's source: the bundle runs, and the run is filed under that method in the webapp's history. **Say which method it was filed under, and do not let the filing read as the saved method having run.**

It returns a durable `run_id` at once. **Report that id the moment it returns, before anything else.** **For an id, say which version ran** (`method_version`); **for an address, give `method_provenance` beside it**: the address, the tag and the resolved commit SHA.

### 6. Follow it to terminal

`mthds_run_status`, on the summary's `retry_after_seconds` hint. Terminal is any of `COMPLETED`, `FAILED`, `CANCELLED`, `TERMINATED`, `TIMED_OUT`. A run still `RUNNING` on fresh reads with no error long after `created_at` may be slow or a workflow task that failed out of sight, which the status cannot tell: stop waiting, report the status, the elapsed time and the run id to follow it by, and do not call it failed. **A status marked `degraded` is the last-known one, not a fresh reading: keep polling on its hint, and never call the run stuck or failed from it.**

### 7. Results, and the saved run

**A saved run stays out of version control**: in a git repository, `git check-ignore -q` `runs/<run_id>/` before saving, not for a `dir` the user named. For a path not ignored, add the workshop's `runs/`, anchored (`/runs/`, or `/app/runs/` for a workshop in `app/`), to the nearest `.gitignore`, relative to that file's directory, say so, and check again: **git never ignores a tracked path, so one still not ignored is not written until the user says so.**

`mthds_run_results`, then report the main output, **with the inputs' source and the keys the request replaced**, and save the run, file or no file: `mthds_download_artifacts` with the run id alone writes the output as `main_stuff.json`, beside each stored file it references, into `runs/<run_id>/` under the workshop's working directory. Pass `dir` only for a folder the user named, relative to that directory. Either way, **report the paths the tool returns**, never paths relative to the user's project.

When the inputs came from a lab case and the lab did not start this run, offer `/pipelex-lab` to score and log it.

### 8. A failed run is reported, then routed, never bisected

Give `failure_message` **verbatim** first, then read [failed-run.md](references/failed-run.md) before routing it; route once, and stop. When the method holds a `PipeFunc`, name it as a suspect: **`PipeFunc` is experimental on the hosted plane.** Its Python runs in a sandbox with no network access, and the feature is still in development, so a method that validates can still fail when it runs. Per-pipe bisection is not this skill's. Do not re-run a failed method with altered inputs to see what happens — that spends credit on a guess.

## Follow a run

A run id alone: nothing is validated or prepared.

- **"how is run X going"** → `mthds_run_status`. Report the state and, while it runs, the retry hint, never a guessed duration. Step 6's readings of `degraded` and of a long `RUNNING` hold here as well.
- **"get the results of run X"** → `mthds_run_results`. A run that is not terminal has no results: report the state instead.
- **"save run X"**, or its files → `mthds_download_artifacts`, as step 7 says.

An unknown run id is reported in the tool's own words.

## Stops

| Condition | Do this |
|---|---|
| `mthds_run`: `input_domain` at `method_id`, on a linked run | nothing was spent: read [linked-run.md](references/linked-run.md) before replying |
| `mthds_download_artifacts` absent | say nothing was saved to disk and report the stored references as they came back; the run still completed |
| `mthds_download_artifacts` refuses a `dir` the user named | take step 7's ignore check, then call again without it, which saves into `runs/<run_id>/`, and say so. A refused `dir` is not a failed save |

## References

- [by-id.md](references/by-id.md), [published-address.md](references/published-address.md): an `mt_…` or a `method_ref` target, before the first call.
- [failed-run.md](references/failed-run.md): a failed run, before routing it.
- [linked-run.md](references/linked-run.md): a linked run refused at `method_id`.
