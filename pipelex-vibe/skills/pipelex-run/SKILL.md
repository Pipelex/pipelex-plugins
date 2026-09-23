---
name: pipelex-run
description: Run an MTHDS method on the hosted Pipelex API, and follow a run that is already going. Use when the user says "run this method", "run the pipeline", "execute the method", "run it again", "run mt_abc123", "run github.com/Pipelex/methods/documents", "how is run X going", "what's the status of that run", "is it done yet", "get the results of run X", "show me the output of that run", or "download the files from yesterday's run". Takes a local bundle directory, a registered method's catalog id (mt_…), or a published method's address (github.com/owner/repo[/selector][@tag]), with run-ready inputs from /pipelex-inputs. A run spends inference credit, so this skill never starts one nobody asked for.
---

# Run an MTHDS method

This skill owns the run lifecycle, and only that. It has two entries and no third:

- **[Start a run](#start-a-run)** — a target and inputs. The target is a **bundle directory** (its `.mthds` files, submitted as `files`), a **registered method** from the Pipelex catalog (its `mt_…` id, passed as `method_id`), or a **published method** at its address (`method_ref`, e.g. `github.com/Pipelex/methods/documents@v0.1.0`).
- **[Follow a run](#follow-a-run)** — a **run id** alone, with no method in hand: its status, its results, or the files it produced. A run id stays good long after the session that started it, so yesterday's run is a normal target here.

What it does not do: prepare inputs (`/pipelex-inputs`), repair a method (`/pipelex-edit` for a contract-preserving fix, `/pipelex-design` for a structural one), or bisect a failing pipeline pipe by pipe.

## Requirements — the Pipelex MCP tools

This skill runs through **`mthds_run`**, **`mthds_run_status`** and **`mthds_run_results`**, served by the plugin's `pipelex` MCP server. They are required: never report a run id, a status or a result that did not come from them.

- **If the run tools are absent from this session**, the Pipelex MCP server isn't connected: STOP, and tell the user in one line what [the connection reference](../shared/credentials.md#the-tool-is-absent) says for Mistral Vibe. Never improvise a run id, a status or an output.
- **If a call returns `status: "error"` with an error of class `config`** (missing or rejected `PIPELEX_API_KEY`, unreachable API), STOP the same way and surface the error's `hint` verbatim; when it is about the key, read [where the key comes from](../shared/credentials.md#where-the-key-comes-from) before saying anything more.
- **`mthds_validate`** and **`mthds_inputs_template`** are required for [Start a run](#start-a-run) — they are what keeps this skill from spending credit on a method or an input set that cannot work. [Follow a run](#follow-a-run) uses neither.
- **`mthds_download_artifacts`** is optional, and it is the one that goes missing on its own: it is absent wherever the workshop has no working directory to save into, which is the hosted console. Without it, report the run's stored references as they came back and say the files were not downloaded — never stop a run that has already completed.
- **`mthds_list_methods`** is optional: it resolves a saved method the user names without its `mt_…` id. When it is absent, run by id or by files; never stop for it.

## Mode

Automatic. The user asking for the run is the consent, and step 4 states what is about to happen rather than asking again. The only questions this skill asks are the stops in the table at the end.

---

## Start a run

### Step 1 — Identify the target and the pipe

A bundle directory, an `mt_…` id, or a published method's address — `github.com/<owner>/<repo>[/<selector>][@<tag>]`. A saved method the user names without its id is resolved through `mthds_list_methods` when the tool is present — choose or disambiguate by name and description, then carry the returned id. Never stop for that tool's absence: ask for the id instead.

Whichever form step 1 settles on is the one every call in this skill takes, and **an address pairs with nothing**: `files` beside a `method_ref` and a `method_id` beside it are both refused before anything runs, because an address is a complete run source carrying its own provenance. Where two of them are in hand, ask which one is meant: a run is paid, so picking one yourself risks spending it on a method the user did not name. **An address with no tag is accepted and it floats** — it resolves to the default branch at its head, so what runs is whatever that branch holds at the moment of the call, and a run tomorrow can execute different content under the same address. Say that in one line, recommend the tag, and start the run; step 5 is what records which content actually ran.

The pipe is the method's declared main pipe unless the user named another, in which case carry that `pipe_ref` through every call in this skill — the drift check and the run must inspect the same contract.

### Step 2 — Find the inputs

**Where they live, for a target that is not a bundle directory.** A registered method and a published address have no bundle beside them, so the inputs are in the directory `/pipelex-inputs` wrote them to: the one the user named, defaulting to `./<method_id>/` for a saved method and to the address's last path segment with its tag dropped for a published one. Read *beside the bundle* below as *in that directory* for those two.

In this order, taking the first that applies:

1. **Values the user gave in the request**, laid over a current `inputs.prepared.json` where one exists: take the prepared set and replace only the keys the user named. Restating one input of a filled set is an ordinary thing to say, and it must not cost the whole set. Where no prepared file is beside the bundle, the request's values are the whole set.
2. **A current `inputs.prepared.json`** beside the bundle — a plain inputs object whose file values are already `pipelex-storage://` references. **Current** means, key by key, every value that is not a file is equal in both files, and neither `inputs.json` nor any local file it names is newer than `inputs.prepared.json`. Not current is not run-ready: hand to `/pipelex-inputs`.
3. **An `inputs.json` holding no local file value** — every file-ish value already an `http(s)` URL or a `pipelex-storage://` reference. It is run-ready as it stands.
4. **An empty object**, when the pipe declares no input at all.

Then call **`mthds_inputs_template`** once, with the same target and `explicit: false`, and check the inputs against it on **both keys and value shapes**. This answers "which inputs does the pipe declare" and catches drift in one call, for every target: a bundle edited after its `inputs.json` was written drifts exactly as a saved method does, since a run by id executes the method's **current stored content** and a run by an untagged address executes whatever its default branch holds at that moment. A renamed, added or dropped input changes the key set; a retyped or reshaped one does not, so also check per key that the JSON kind still matches and that a structured value's field names still match the template's.

**One difference is expected and is not drift**: a file-ish input arrives in the template as a bare URL-or-path string while a prepared value is the content dict `{"url": "pipelex-storage://…"}`. That is the prepare rewrite, not a signature change.

Anything else — a placeholder, a local path, a `data:` URL, inline bytes, a real drift — is not run-ready. Say which input is at fault and hand to `/pipelex-inputs`; there is no cross-skill invocation on Mistral Vibe, so open that skill's `SKILL.md` beside this one and follow it. Do not prepare inputs here.

### Step 3 — Prove the target before spending credit

For a **bundle directory**, one `mthds_validate` call over the bundle, and the same file set for the `files` submission in step 5. Submit every `.mthds` file beneath the bundle directory **except anything under a `runs/` directory**, where `/pipelex-run` saves a completed run's artifacts: a method that emits or echoes a `.mthds` file would otherwise have its own output submitted as part of its source. Prefer the path form `{path: <absolute path to the file>}` — it keeps the real path as provenance in diagnostics and spares copying whole bundles into the request; the workshop resolves a path against **its own** working directory, wherever the harness launched it, so pass an absolute one. Inline `{content: <file content>, uri: <path relative to the bundle dir>}` is the fallback, and the only form the hosted console accepts. The bar is `is_valid: true`, `is_runnable: true` and an empty `pending_signatures`:

- valid and runnable → go on;
- `is_valid: false`, or a non-empty `pending_signatures` (a scaffold has nothing to run yet) → report the verdict and route to `/pipelex-design`, or `/pipelex-edit` when the fix is contract-preserving. Never run a method that did not pass.

For a **published address**, the same call with `method_ref` in place of `files`, against the same bar — and the routing differs in exactly one way: the method belongs to whoever published it, so a verdict that fails is reported with the address and its tag and is not routed to `/pipelex-design` or `/pipelex-edit`. Another tag, or the publisher, is the fix.

For an **`mt_…` id**, the same call with `method_id` in place of `files`, against the same bar. Step 2's template call does not stand in for it: `mthds_inputs_template` answers `is_valid` and nothing else, and a scaffold is a *valid* bundle — so a stored method with pending signatures passes the template call and would reach the run, spending credit on its implemented pipes before it stops at the one that is not. The routing is the same as for a bundle directory.

### Step 4 — Say what is about to run, then run it

One line before the call: the target, the pipe, where the inputs came from, and that the run spends inference credit.

> Running `summarize_pdf` (main pipe `summarize`) from `methods/summarize_pdf/`, with the inputs in `inputs.prepared.json`. This spends inference credit.

The user asking for the run is the consent; there is no second confirmation. **Never start a run nobody asked for.**

### Step 5 — `mthds_run`, and print the run id first

Call `mthds_run` with the same target as step 2 — the whole-bundle `files` submission, `method_id`, or `method_ref` — and `inputs` set to the values step 2 settled on, verbatim. Omit `pipe_code` to run the declared main pipe; pass a pipe's code only when step 1 targeted another. For an address the declared main pipe is the published package's manifest's, which can differ from the bundle's own declaration; `pipe_code` overrides it there exactly as it does anywhere else.

**A bundle directory that is linked to a saved method passes its id too.** When `pipelex-method.json` sits beside the root `.mthds` file, read its `method_id` and send it beside the `files`. That pair is legal and means one thing only: the files are what run, and the id is recorded on the run so that it is filed under that method in the webapp's history — the same thing the webapp does when it runs the editor's unsaved buffer. **Say which method it was filed under, and do not let the filing read as the saved method having run**: what ran is the directory, which may differ from the stored content in either direction. This applies to the bundle-directory arm alone — an `mt_…` target *is* the id and carries no files, and an address pairs with nothing.

**The linked id does not fetch anything, and that matters for a custom `PipeFunc`.** A caller-supplied source takes precedence over the stored method, which is read only when no `files` were sent at all — so a linked run gains the history entry and nothing else, the stored `.py` files included. Since a `files` submission carries `.mthds` only, a bundle whose `PipeFunc` names a function the hosted plane does not already have registered has **no channel for its Python on any files run**, linked or not. The path that carries it is `/pipelex-catalog`: a saved method run by its id alone has its `.mthds` and `.py` assembled into the run bundle server-side.

The tool returns a durable `run_id` immediately and never blocks. **Report that id the moment it returns, before anything else.** It is the only handle a later session has on this run, and the whole of [Follow a run](#follow-a-run) rests on it.

**A linkage id the plane does not know refuses the run, and nothing is spent.** The failure is an `input_domain` error located at **`method_id`** — and on a run that sent files beside the id, that location is the discriminator rather than a coincidence: a rejected payload or a refused execution locus locates at `files`, so only the unknown-method arm lands at `method_id`, and its hint says the id is not visible to the API key's organization. The catalog is org-scoped, so a link made with another organization's key, or against another plane, reads exactly like a deleted method. Report it **with the `api_host` the link file records** — that is what makes it diagnosable — and offer the same run **without** the id: it runs the very same bundle and loses only the history filing. Do not go looking for the bundle; the bundle was never in question.

**For an address, report what was fetched in the same breath.** The acknowledgement carries `method_provenance` — the address, the tag and the **resolved commit SHA** — and that SHA is the only record of what actually ran: an untagged address floats, and even a tag can be moved. Nothing later recovers it, so it goes beside the run id rather than into the final report.

### Step 6 — Follow it to terminal

`mthds_run_status`, honouring the summary's `retry_after_seconds` hint — never poll in a tight loop. Terminal is any of `COMPLETED`, `FAILED`, `CANCELLED`, `TERMINATED`, `TIMED_OUT`.

### Step 7 — Results, and the files

`mthds_run_results`, then report the main output. When the output references stored files — an image, a PDF or a document carried as a `pipelex-storage://` URI — call `mthds_download_artifacts` with the same run id, because the links beside those references are presigned and expire within the hour.

`dir` is **relative to the workshop's own working directory**, and an absolute path is refused before the run is read at all — so pass **`runs/<run_id>`**, never the absolute `<bundle_dir>/runs/<run_id>/` form every other call in this skill takes. A refused `dir` is not a failed download: call again with no `dir` and let the workshop save where it defaults to. Either way, **report the paths the tool returns** rather than paths relative to the user's project: the workshop writes where the harness launched it, which is not necessarily where the user is standing.

### Step 8 — A failed run is reported, then routed, never bisected

Give `failure_message` **verbatim** first. Then route once, and stop:

| What the failure says | Where it goes |
|---|---|
| an input is missing, malformed or unreadable | `/pipelex-inputs` |
| a pipe's prompt, model or operator settings are at fault | `/pipelex-edit` |
| the method's structure or a contract is at fault | `/pipelex-design` |
| the method holds a `PipeFunc` | name it as a suspect, for the reason stated under this table |
| the run stays `RUNNING` with no error and no progress | say what it is: a workflow task that failed out of sight. It is not a slow run |

**`PipeFunc` is experimental on the hosted plane.** Its Python runs in a sandbox with no network access, and the feature is still in development, so a method that validates can still fail when it runs. That is why a `PipeFunc` is named as a suspect on a failure rather than cleared: nothing upstream of the run could have caught it, because validation never resolves the function.

**On a `files` run the suspicion sharpens, but only when the failure says so.** Per step 5, no `.py` file travels with a `files` submission, so a `PipeFunc` naming a function the plane does not already have registered could not have resolved. Where `failure_message` implicates resolving or registering that function, say that as the cause rather than offering it as one candidate among several, and give the cure: `/pipelex-catalog` saves the bundle with its Python, and the method run by its id alone gets both. **Where it says anything else, route on what it says** — a missing input, a model or prompt fault, a failure upstream of the custom pipe — and leave the `PipeFunc` a suspect rather than promoting it: a bundle holding one is not evidence that it is what failed, and a save is a deployment, which is not somewhere to send anybody for an unrelated fault.

**For a published address, only the first row routes.** The method is not the user's to repair, so every row below the inputs one is reported rather than routed — the prompt-or-model row and the structure row included, which is where an address would otherwise be sent to `/pipelex-edit` for source the user does not have: give the failure and step 5's provenance, and say the fix is upstream or another tag. The `PipeFunc` row and the stuck-`RUNNING` row still say exactly what they say; they name a cause and send nobody anywhere. Per-pipe bisection is not this skill's: it belongs to a debug-run skill that does not exist yet. Do not re-run a failed method with altered inputs to see what happens — that spends credit on a guess.

---

## Follow a run

A run id alone, with no method and no inputs. Nothing is validated and nothing is prepared here.

- **"how is run X going"** → `mthds_run_status`. Report the state and, while it is running, the retry hint rather than a guess at how long it will take.
- **"get the results of run X"** → `mthds_run_results`. A run that is not terminal has no results: report the state instead.
- **"download the files from run X"** → `mthds_download_artifacts`, per step 7. This works days after the run, which is why the entry exists.

An unknown run id is reported in the tool's own words. Runs are scoped to the key's organization, so another organization's run reads exactly like a miss.

---

## Where this skill stops

| Situation | What it does |
|---|---|
| the run tools are absent, or a `config`-class error | stops per the Requirements above |
| the inputs are not run-ready | names the input at fault, hands to `/pipelex-inputs`, spends nothing |
| `inputs.prepared.json` is not current | same — the prepare step is `/pipelex-inputs`' |
| the bundle does not validate, or is a scaffold | reports the verdict, routes to `/pipelex-design` or `/pipelex-edit` |
| the inputs drifted from the method's template | reports which and how, hands to `/pipelex-inputs`, spends nothing |
| the run failed | reports `failure_message` verbatim, routes once, never bisects |
| the failing method is a published address | reports the failure with the address, the tag and the resolved commit SHA; never routes it to `/pipelex-design` or `/pipelex-edit` |
| a `files` submission or a `method_id` is in hand beside an address | asks which target is meant and spends nothing — a run is paid, and picking one is not the skill's to do |
| the linked directory's `method_id` is unknown to the plane | reports it with the link's `api_host` and offers the same run without the id; nothing was spent, and the bundle was never in question |
| a `files` run fails on resolving a custom `PipeFunc` | says the Python did not travel and names `/pipelex-catalog` as the path that carries it; a files run has no channel for it. A failure saying anything else routes on what it says |
| `mthds_download_artifacts` is absent | reports the stored references as they came back; the run still completed |
| `mthds_download_artifacts` refuses the `dir` | calls again with no `dir`; a refused directory is not a failed download |
