---
status: active
item: L-260927-87d267
---

# Design — running a method on its own sample

**Written 2026-09-27**, for the epic `L-260927-87d267`, against `pipelex-plugins` at `5bb83dd` (`dev`, after #91). It answers two bugs filed from the cookbook's copy-and-change recipe, `L-260927-235a99` and `L-260927-d7c594`, verifies both, and designs their fix. Verifying them turned up two neighbours in the same paragraph of the same step that fail the same sample, `L-260927-7f577e` (filed with the other two) and `L-260927-0e6ba4` (filed by this session). Every box was ratified as written on 2026-09-27, in an interview of one question per box: all four bugs are fixed in one pull request, and steps 2 and 3 swap. The design's review on the same day limited box E's optional-key allowance to a run on the main pipe (4.4). [`plan.md`](plan.md) is the tracker. File and line references were accurate on the writing date; verify them before implementing.

## 1. The two bugs

The cookbook's `recipes/yours/copy-and-change/` asks an agent for two runs of `answer_from_documents@v0.20.0`, whose `inputs.json` carries a document and a question:

1. "Copy github.com/Pipelex/pipelex-cookbook/answer_from_documents@v0.20.0 into ./document-qa, have it answer in the language of the question, **prove it on the sample with the question asked in French**, and save it to my Pipelex account as "document-qa"."
2. After the save, which linked `document-qa/` to the new method with a `pipelex-method.json`: "**Run mt_… on its sample.**"

Both runs happened on 2026-09-27 (`run_4187c0b7-0eca-40f7-af3f-26d84644fc89` and `run_31673a6e-35e5-497f-8a60-f402523704c1`), and both times the agent went against a literal reading of `/pipelex-run`'s step 2 to do what the user asked.

**`L-260927-235a99` — the request's values replace the sample.** Rule 1 of step 2 (`templates/skills/pipelex-run/SKILL.md.j2:42`) lays the request's values over a current `inputs.prepared.json`, and says "With no prepared file, the request's values are the whole set." The sample needs no preparation, since its document is an `https` URL, so no prepared file exists, and the French question alone becomes the set.

**`L-260927-d7c594` — a saved id's sample is not looked for.** For an id, step 2 looks for the inputs "in the one the user named, by default `./<method_id>/`" (`SKILL.md.j2:40`). Nothing names a directory in the second request, `./mt_…/` does not exist, and `document-qa/`, whose `pipelex-method.json` names the id and whose `inputs.json` is the sample, is never looked at.

## 2. Verification

Both are **confirmed** against `dev` at `5bb83dd`: the two sentences are unchanged in the template and render identically on all three targets.

One detail of `L-260927-235a99` is overstated. The item says the run then goes ahead "on the question alone". On a literal reading it does not: the template check that follows the rules compares the key set, finds the required `documents` missing, and hands the run to `/pipelex-inputs` as drift. A model that skipped the check would not spend credit either, since the hosted API refuses a start with a missing required input as a 422 (`pipelex-mcp/SPEC.md:386`). The bug is real, but what it costs is a needless detour through `/pipelex-inputs`, which may then write over the sample (`L-260923-c8f18e`), not a wasted run.

For `L-260927-d7c594`, the linked directory is the only place the sample can be. A save sends `.mthds` and `.py` files alone, and a pull writes only those and the link (`pipelex-mcp/SPEC.md:1171`), so the catalog never holds an `inputs.json`. A saved method's sample exists only in a directory on disk, and the one the link names is the directory the method was saved from or pulled into.

### Two neighbours that fail the same sample

Reading step 2 against this sample turned up two more literal failures, in the check that runs after the rules.

**`L-260927-7f577e` — a missing optional input reads as drift.** The check compares "the key set" with the light template, which lists every declared input and does not mark the optional ones. `answer_from_documents` declares an optional `context` that its sample leaves out, so the sample fails the key-set comparison. Only `mthds_validate`'s `main_pipe` says which inputs are optional (`required: boolean`, `pipelex-mcp/SPEC.md:159`); `mthds_inputs_template` does not carry it (`SPEC.md:941`), and step 3 calls validate only after step 2 has already handed the inputs off.

**`L-260927-0e6ba4` — an input written in the envelope reads as drift.** The check compares each key's JSON kind and field names with the light template, excusing only the prepare rewrite. Every `inputs.json` under `methods/` in the cookbook at `v0.20.0` writes every input in the explicit `{concept, content}` envelope, so `"question": {"concept": "native.Text", "content": {"text": "…"}}` is an object where the template shows `"question": "text_value"`. The envelope is a first-class form. The runtime detects it key by key (`pipelex/core/memory/input_shaper.py:164`, `_is_explicit` at `:644`), `mthds_prepare_inputs` accepts it and keeps it in the prepared file (`SPEC.md:1048`), and it is what `mthds_inputs_template` returns by default.

So on a literal reading, the recipe's first request fails three ways and its second four ways. Fixing only the two bugs leaves the recipe failing on the sample it names.

## 3. The ceiling

The rendered Claude `pipelex-run/SKILL.md` is 12,987 characters at `5bb83dd`, 13 under the 13,000 compaction ceiling that `make check` enforces; Codex renders 12,662 and Vibe 12,676. Every fix below adds text, so the design has to find the room. Following the size diet's read-before-act rule, the room comes from rationale and from branches whose condition is visible, never from a guard:

- **Step 4's `PipeFunc` sentence keeps its guard and loses its rationale.** The bold clause stays, and so does the cure in a few words. The explanation (a `files` submission carries `.mthds` only, so an unregistered function cannot resolve) is already in `references/failed-run.md` and `docs/decisions.md`. This saves about 140 characters.
- **Step 1's "an address pairs with nothing" moves to `references/published-address.md`.** The model reads that reference before the first call on an address, which is the only time the sentence applies, and ignoring it costs nothing: the tool refuses `files` or a `method_id` beside an address with an `input_domain` error, before anything runs. This saves about 135 characters.
- **With the neighbours, the order swap of box E removes two sentences** that the new order makes true by construction: "A dry-run request goes to step 3 first" and "Step 2's template call does not stand in for it". This saves about 225 characters.

Measured by applying the proposed text of section 4 to the rendered files at `5bb83dd`:

| Scope | Claude | Codex | Vibe |
|---|---|---|---|
| Today | 12,987 | 12,662 | 12,676 |
| The two bugs, with both trims | 12,924 | 12,599 | 12,613 |
| All four, with both trims and the swap | 12,903 | 12,578 | 12,592 |

The last row includes the 32 characters that the review's main-pipe limit added to the check paragraph (4.4), which render identically on every target.

## 4. The fix

### 4.1 The request is laid over the sample (`L-260927-235a99`)

The base the request's values are laid over is the sample: a current `inputs.prepared.json`, else `inputs.json`. The request replaces the keys the user named, whole, and every other key is kept. The request's values are the whole set only when neither file exists. The result then goes through the same checks as any other set, which is what keeps this safe:

- If the prepared file is stale, the base is `inputs.json`. A local file path in a key the request did not replace is still not run-ready, and goes to `/pipelex-inputs` as it does today.
- A replaced key may be written in the light form over a sample written in the envelope. The runtime reads each key's form separately, so a mixed set is legal, and nothing needs re-wrapping.
- "Keys" means top-level inputs. A change to one field of a structured input ("the same invoice in euros") is the model editing a value, not something this rule has to describe.

Step 4's line already says "where the inputs came from"; it gains "and which keys the request replaced", so the paid run announces the overlay before it starts.

### 4.2 Where an id's inputs sit (`L-260927-d7c594`)

For an id, the inputs sit in the directory the user named. Otherwise the candidates are `./<method_id>/`, which is what `/pipelex-inputs` writes for an id, and every directory below the working directory whose `pipelex-method.json` names the id. The skill takes the one candidate holding an `inputs.json` and says which it took. When several hold one, it asks which, and never chooses, because a run on the wrong sample is paid.

Three points follow from this:

- **The directory lends its inputs, never its files.** The target stays the id, so the saved method runs, and a linked directory's local edits do not. Step 1 already says so ("Every call in this skill takes the form settled here"); the rationale goes to `docs/decisions.md`, and the skill does not repeat it.
- **A linked directory that has drifted from the catalog is caught.** Step 2's template check runs against the id's own template, so a sample written for a local signature the saved method does not have reads as drift and goes to `/pipelex-inputs`, as it should.
- **A hand-off from `/pipelex-inputs` names its directory.** Its offer names the file the run reads, so a run it hands over never searches, and the "ask when several" rule only comes up for a cold request.

The search is written as a sentence, "a directory below the working directory whose `pipelex-method.json` names the id", not as the catalog-id bridge's `grep` command. The bridge needs its exact command because the result chooses the directory design and edit will write into. The run only reads, and naming the file and what it must contain is enough, in fewer characters, without a second source for the bridge's command.

### 4.3 An enveloped input is checked by its content (`L-260927-0e6ba4`)

In the check paragraph: "A value in the `{concept, content}` envelope is checked by its `content`". The existing exemption for the prepare rewrite then applies to that content. The `concept` annotation is left to the runtime, which checks it for compatibility at start (`input_shaper.py`, `_shape_explicit`); the skill does not duplicate that check.

### 4.4 A missing optional input is not drift (`L-260927-7f577e`)

The key-set comparison accepts a key the inputs lack when the validate verdict's `main_pipe` marks it `required: false`. That verdict has to exist before the check, so validation moves ahead of the inputs, which box E decides.

The allowance holds only when the run is on the main pipe. `mthds_validate` takes no pipe selector, and its `main_pipe` is always the entry pipe's signature (`pipelex-mcp/SPEC.md:149`), while step 1 lets the user name another pipe and carries its `pipe_ref` through every call. On another pipe, the verdict's `required` flags belong to the wrong signature. Read literally, they would excuse a key the named pipe requires whenever the main pipe declares one of the same name optional, and they could never excuse an optional input that only the named pipe declares. So for a named pipe, a missing key stays drift, as it is today. Lifting the limit needs `mthds_validate` to take a `pipe_ref`, which is `L-260927-0f5a2e` in `pipelex-mcp`.

### 4.5 The text, as proposed

Step 2 and step 3 after the swap of box E, rendered for Claude, with changes in bold where they are not already bold in the skill. Everything not shown is unchanged.

> **### 2. Prove the target before spending credit** *(today's step 3, without "Step 2's template call does not stand in for it: it answers `is_valid` alone, and a scaffold is a *valid* bundle.")*
>
> **### 3. The inputs** *(today's step 2, without its opening "A dry-run request goes to step 3 first." paragraph)*
>
> They sit beside the bundle unless the caller named another directory. **For an id, in the one the user named, else in `./<method_id>/` or a directory below the working directory whose `pipelex-method.json` names the id: take the one holding an `inputs.json`, and say which. When several do, ask which; never choose.** In this order, take the first that applies:
>
> 1. **Values the user gave in the request**, laid over a current `inputs.prepared.json`, **else over `inputs.json`: replace only the keys the user named and keep every other. With neither file**, the request's values are the whole set.
>
> Then call `mthds_inputs_template` once, … and check the inputs against it on both keys and value shapes: the key set, **where a key the inputs lack is fine when the run is on the main pipe and step 2's verdict marks it `required: false`**, and per key the JSON kind and a structured value's field names. **A value in the `{concept, content}` envelope is checked by its `content`, and** a file-ish input the template shows as a bare URL-or-path string and the prepared file holds as `{"url": "pipelex-storage://…"}` is the prepare rewrite**; neither is drift.**

Step 4: "One line before the call: the target, the pipe, where the inputs came from **and which keys the request replaced**, and that the run spends inference credit." Step 4's `PipeFunc` sentence: "**When a `files` target holds a `PipeFunc`, the line says its Python does not travel**, and that a method saved through `/pipelex-catalog` and run by its id alone carries it."

The rest of the swap is renumbering. The intro's "a dry run is Start a run's step 3, shown" becomes step 2. "the values step 2 settled on" in step 5 becomes step 3. `references/published-address.md:17`, "A verdict that fails at step 3", becomes step 2, and the same reference gains the address sentence moved out of step 1.

### 4.6 What stays as it is

**`/pipelex-inputs` keeps writing an id's inputs to `./<method_id>/`.** Pointing it at the linked directory instead would make the sample the default target of a Template save, which is the overwrite `L-260923-c8f18e` describes. With the fix, the run looks in both places, so nothing depends on the two skills agreeing on a single directory.

**A published address keeps its own rule**, in `references/published-address.md` ("the one the user named, by default the address's last path segment"). A copy of an address, such as `./document-qa` before its save, is a bundle directory, and its inputs sit beside it.

## 5. Interactions

- **`L-260923-c8f18e` (P1, open).** A hand-off to `/pipelex-inputs` with a filled `inputs.json` can land on the Template row and save placeholders over it. This fix removes one path to that hand-off (rule 1 no longer throws the sample away), and adds none: a linked directory handed to `/pipelex-inputs` is exposed exactly as a bundle directory is today. The two can land in either order.
- **`L-260924-afcd06`.** The search runs from the model's shell, whose directory need not be the workshop's, which is the same assumption that item records for the ignore check. The words "below the working directory" say what the bridge's "from the working directory down" says, and inherit whatever that item decides.
- **`L-260927-0f5a2e` (`pipelex-mcp`).** Once `mthds_validate` takes a `pipe_ref`, the main-pipe limit of 4.4 can go. The same item covers an older instance of this assumption, outside this fix: today's dry run gives an id's or an address's contract "from the verdict's `main_pipe`" (`SKILL.md.j2:57`), which is the entry pipe's contract even when the user named another pipe.
- **The cookbook recipe** already describes the fixed behaviour ("The agent finds the sample in `document-qa/inputs.json`, beside the bundle that `pipelex-method.json` links to the id"), so it needs no change.

## 6. Proof

The unit suite holds the words. `test_user_values_are_laid_over_a_prepared_set` gains the `inputs.json` fallback. New assertions cover the id's candidate directories, the envelope clause and the optional-key clause. The new guard, "When several do, ask which; never choose.", joins `tests/unit/test_skill_guards.py`; with box E, the dry-run detour's entry leaves the registry along with its sentence. `make check` holds the ceiling and the links.

Smoke sessions hold the behaviour, and cost nothing. In a scratch directory holding a copy of `answer_from_documents@v0.20.0` saved to a test organization, a fresh Claude Code session on the local build (`claude --plugin-dir …/pipelex`) is asked each of the recipe's two requests, reworded to stop short of spending: "…show me the target and the exact inputs you would send, and do not start the run". A pass is the right target and inputs for each request: the sample's document with the French question, then the sample as written by the id, with no hand-off to `/pipelex-inputs`. A third session places an `inputs.json` in `./mt_…/` as well and must ask which. One Codex session repeats the second request. A paid replay of the recipe, about $0.75 at the 2026-09-27 costs, happens only on Louis's go.

## 7. Decision boxes for ratification

| Box | Question | Recommendation | Ruling |
|---|---|---|---|
| A | Scope: the two bugs alone, or with `L-260927-7f577e` and `L-260927-0e6ba4`? | **All four in one pull request.** They edit one paragraph, share one character budget, and the recipe fails on the sample until all four are fixed. The two neighbours join the epic as children. | Yes, as written — 2026-09-27 |
| B | What base does the request's value land on? | **A current `inputs.prepared.json`, else `inputs.json`; the named keys replaced whole, every other kept; the usual checks on the result** (4.1). The alternative, overlaying only when the request says "sample", depends on the user's wording, and a request naming one input of a filled set means the same thing whether or not it says "sample". | Yes, as written — 2026-09-27 |
| C | Where does a run by id look for its inputs? | **The named directory; else, among `./<method_id>/` and the linked directories, the one holding an `inputs.json`, named; ask when several do** (4.2). The alternatives rank the two kinds of directory, `./<method_id>/` first or the linked directory first, and either one silently picks one sample over another. | Yes, as written — 2026-09-27 |
| D | Does `/pipelex-inputs` change its default directory for an id? | **No** (4.6). The run finds both, and making the linked directory the default would expose the sample to the Template overwrite of `L-260923-c8f18e`. | Yes, as written — 2026-09-27 |
| E | *(If A takes `L-260927-7f577e`.)* Where does step 2 learn which inputs are optional? | **Swap steps 2 and 3, so validation runs before the inputs and the check reads `required` from its verdict** (4.4, 4.5). It needs no upstream change for the main pipe (a named pipe waits on `L-260927-0f5a2e`, 4.4), it removes two sentences, and a dry run then stops before any input is read, simply because of the order. The alternatives are a second validate call inside step 2, which duplicates a call and a paragraph, or a `required` mark on `mthds_inputs_template`'s output, which is a change in `pipelex-mcp` that this fix would have to wait for. | Yes, as written — 2026-09-27 |
| F | Where does the room under the ceiling come from? | **Step 4's `PipeFunc` rationale, and step 1's address sentence moved into `references/published-address.md`** (section 3). Neither is a guard, and both are already written where the reader who needs them will look. The alternative, moving the id's directory rule into a reference of its own, puts a paid choice behind a pointer, and a static reference cannot share the bridge's text. | Yes, as written — 2026-09-27 |
