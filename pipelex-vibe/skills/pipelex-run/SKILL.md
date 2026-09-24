---
name: pipelex-run
description: Run an MTHDS method on the hosted Pipelex API, and follow a run that is already going. Use when the user says "run this method", "run the pipeline", "execute the method", "run it again", "run mt_abc123", "run github.com/Pipelex/methods/documents", "how is run X going", "what's the status of that run", "is it done yet", "get the results of run X", "show me the output of that run", "do a dry run first", or "download the files from yesterday's run". Takes a local bundle directory, a registered method's catalog id (mt_…), or a published method's address (github.com/owner/repo[/selector][@tag]), with run-ready inputs from /pipelex-inputs. A run spends inference credit, so this skill never starts one nobody asked for.
---

# Run an MTHDS method

This skill owns the run lifecycle, and only that, through two entries and no third: [Start a run](#start-a-run) from a target and its inputs, and [Follow a run](#follow-a-run) from a run id alone, which stays good long after the session that started it. A dry run is not a third entry: it is Start a run's step 3, shown to the user as a numbered flow. It does not prepare inputs (`/pipelex-inputs`), repair a method (`/pipelex-edit` for a contract-preserving fix, `/pipelex-design` for a structural one), or bisect a failing pipeline pipe by pipe.

## Requirements

- **`mthds_run`**, **`mthds_run_status`** and **`mthds_run_results`** are required, and to start a run **`mthds_validate`** and **`mthds_inputs_template`** too: they keep credit from being spent on a method or inputs that cannot work.
- **If the run tools are absent from this session**, the Pipelex MCP server isn't connected: STOP, and tell the user in one line what [the connection reference](../shared/credentials.md#the-tool-is-absent) says for Mistral Vibe. Never improvise a run id, a status or an output.
- **If a call returns `status: "error"` with an error of class `config`** (missing or rejected `PIPELEX_API_KEY`, unreachable API), STOP the same way and surface the error's `hint` verbatim; when it is about the key, read [where the key comes from](../shared/credentials.md#where-the-key-comes-from) before saying anything more.
- **`mthds_download_artifacts`** and **`mthds_list_methods`** are optional: never stop for either.

## Start a run

### 1. The target and the pipe

The target is a **bundle directory**, submitted as `files`; a registered method's **`mt_…` id**, as `method_id`; or a **published method's address**, `github.com/<owner>/<repo>[/<selector>][@<tag>]`, as `method_ref`: read [published-address.md](references/published-address.md) before the first call. A saved method named without its id is resolved through `mthds_list_methods`, choosing or disambiguating by name and description, then carrying the returned id; without that tool, ask for the id. Every call in this skill takes the form settled here, and **an address pairs with nothing**, being a complete run source: `files` or a `method_id` beside it is refused before anything runs. **When an address and another target are both in hand, ask which one is meant; never pick one yourself**: a run is paid.

The pipe is the declared main pipe unless the user named another: **carry its `pipe_ref` through every call**, so the drift check and the run inspect the same contract.

### 2. The inputs

They sit beside the bundle, or for an id in the directory `/pipelex-inputs` wrote them to: the one the user named, by default `./<method_id>/`. In this order, take the first that applies:

1. **Values the user gave in the request**, laid over a current `inputs.prepared.json` where one exists: take the prepared set and replace only the keys the user named. With no prepared file, the request's values are the whole set.
2. **A current `inputs.prepared.json`**. **Current** means, key by key, every value that is not a file is equal in it and in `inputs.json`, and neither `inputs.json` nor any local file it names is newer than it. Not current is not run-ready: hand to `/pipelex-inputs`.
3. **An `inputs.json` holding no local file value**, every file-ish value already an `http(s)` URL or a `pipelex-storage://` reference.
4. **An empty object**, when the pipe declares no input at all.

Then call **`mthds_inputs_template`** once, with the same target and `explicit: false`, and check the inputs against it on **both keys and value shapes**: the key set, and per key the JSON kind and a structured value's field names. A file-ish input the template shows as a bare URL-or-path string and the prepared file holds as `{"url": "pipelex-storage://…"}` is the prepare rewrite, not drift.

Anything else — a placeholder, a local path, a `data:` URL, inline bytes, a real drift — is not run-ready, and nothing is spent: name the input at fault and how, and hand to `/pipelex-inputs`; there is no cross-skill invocation on Mistral Vibe, so open that skill's `SKILL.md` beside this one and follow it. Do not prepare inputs here.

### 3. Prove the target before spending credit

For a **bundle directory**, one `mthds_validate` call over the bundle, with the same file set step 5 submits. Submit every `.mthds` file beneath the bundle directory **except anything under a `runs/` directory**, where `/pipelex-run` saves a completed run's artifacts: a method that emits or echoes a `.mthds` file would otherwise have its own output submitted as part of its source. Prefer the path form `{path: <absolute path to the file>}` — it keeps the real path as provenance in diagnostics and spares copying whole bundles into the request; the workshop resolves a path against **its own** working directory, wherever the harness launched it, so pass an absolute one. Inline `{content: <file content>, uri: <path relative to the bundle dir>}` is the fallback, and the only form the hosted console accepts. For an **`mt_…` id**, the same call with `method_id` in place of `files`, and for an address with `method_ref`. Step 2's template call does not stand in for it: it answers `is_valid` alone, and a scaffold is a *valid* bundle.

The bar is `is_valid: true`, `is_runnable: true` and an empty `pending_signatures`. Short of it, report the verdict and route to `/pipelex-design`, or to `/pipelex-edit` when the fix is contract-preserving; an address's verdict is reported as [its reference](references/published-address.md) says. Never run a method that did not pass.

**A dry run is this step, shown.** The workshop has no mock-inference mode, so when the user asks for a dry run, a test run or anything "before spending credit", this call is it, and the graph it builds never reaches you. Show the flow as numbered text: each step, what it reads and makes, where it batches or branches, and which steps call a model. For an id or an address, give the contract from the verdict's `main_pipe` instead. Say that no model ran and nothing was spent. **Then end the turn there, even when the same request asked for the real run too**: the flow is the reply, and the paid run waits for the user's go, because a flow shown and run past in the same breath leaves the user nothing to stop.

### 4. Say what is about to run

One line before the call: the target, the pipe, where the inputs came from, and that the run spends inference credit. **On a dry-run request this step comes only after the user's go**: a paid run never starts on a dry-run request whose flow the user has not been shown.

> Running `summarize_pdf` (main pipe `summarize`) from `methods/summarize_pdf/`, with the inputs in `inputs.prepared.json`. This spends inference credit.

**When a `files` target holds a `PipeFunc`, the line says its Python does not travel**: a `files` submission carries `.mthds` only, linked or not, so a function the hosted plane has not already registered cannot resolve, and what carries it is a method saved through `/pipelex-catalog` and run here by its id alone.

The user asking for the run is the consent; there is no second confirmation. **Never start a run nobody asked for.**

### 5. `mthds_run`, and the run id first

Call `mthds_run` with the same target — the whole-bundle `files` submission, `method_id` or `method_ref` — and, as `inputs`, the values step 2 settled on, verbatim. Omit `pipe_code` to run the declared main pipe; pass a pipe's code only when step 1 targeted another.

When `pipelex-method.json` sits beside the root `.mthds` file, send its `method_id` beside the `files`: the files are what run, and the run is filed under that method in the webapp's history. **Say which method it was filed under, and do not let the filing read as the saved method having run.**

The tool returns a durable `run_id` immediately and never blocks. **Report that id the moment it returns, before anything else.** It is the only handle a later session has on this run. **For an address, give `method_provenance` beside it**: the address, the tag and the resolved commit SHA, the only record of what ran, which nothing later recovers.

### 6. Follow it to terminal

`mthds_run_status`, honouring the summary's `retry_after_seconds` hint, never in a tight loop. Terminal is any of `COMPLETED`, `FAILED`, `CANCELLED`, `TERMINATED`, `TIMED_OUT`. A run still `RUNNING` on fresh reads with no error, long after `created_at`, may be slow or may be a workflow task that failed out of sight, and nothing the status carries tells the two apart: stop waiting, report the status, the elapsed time and the run id to follow it by, and do not call it failed. **A status marked `degraded` is the last-known one, not a fresh reading: keep polling on its hint, and never call the run stuck or failed from it.**

### 7. Results, and the files

`mthds_run_results`, then report the main output. When it references stored files — an image, a PDF or a document as a `pipelex-storage://` URI — their links expire within the hour, so call `mthds_download_artifacts` with the run id and `dir: "runs/<run_id>"`, **relative to the workshop's own working directory**, never an absolute path such as `<bundle_dir>/runs/<run_id>/`. The workshop writes where the harness launched it, so **report the paths the tool returns**, never paths relative to the user's project.

### 8. A failed run is reported, then routed, never bisected

Give `failure_message` **verbatim** first, then read [failed-run.md](references/failed-run.md) before routing it; route once, and stop. When the method holds a `PipeFunc`, name it as a suspect: **`PipeFunc` is experimental on the hosted plane.** Its Python runs in a sandbox with no network access, and the feature is still in development, so a method that validates can still fail when it runs. Nothing upstream of the run could have caught it, since validation never resolves the function. Per-pipe bisection is not this skill's. Do not re-run a failed method with altered inputs to see what happens — that spends credit on a guess.

## Follow a run

A run id alone, with no method and no inputs: nothing is validated or prepared.

- **"how is run X going"** → `mthds_run_status`. Report the state and, while it is running, the retry hint rather than a guess at how long it will take. Step 6's two readings hold here as well: a status marked `degraded` is only last-known, and one still `RUNNING` long after `created_at` may be slow or stuck, which the status cannot tell apart.
- **"get the results of run X"** → `mthds_run_results`. A run that is not terminal has no results: report the state instead.
- **"download the files from run X"** → `mthds_download_artifacts`, as step 7 says; it works days after the run.

An unknown run id is reported in the tool's own words: runs are scoped to the key's organization, so another organization's run reads exactly like a miss.

## Stops

| Condition | Do this |
|---|---|
| `mthds_run`: `input_domain` at `method_id`, on a linked run | nothing was spent: read [linked-run.md](references/linked-run.md) before replying |
| `mthds_download_artifacts` absent | report the stored references as they came back and say the files were not downloaded; the run still completed |
| `mthds_download_artifacts` refuses the `dir` | call again with no `dir`, and the workshop saves where it defaults to. A refused `dir` is not a failed download |

## References

- [published-address.md](references/published-address.md): a `method_ref` target, before the first call.
- [failed-run.md](references/failed-run.md): a failed run, before routing it.
- [linked-run.md](references/linked-run.md): a linked run refused at `method_id`.
