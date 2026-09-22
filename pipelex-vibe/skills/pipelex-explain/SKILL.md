---
name: pipelex-explain
description: Explain an MTHDS method in plain language — its contract, its flow, and every pipe in it. Use when the user says "what does this pipeline do?", "explain this workflow", "explain this method", "walk me through this .mthds file", "describe the flow", "how does this work?", or wants to understand an existing MTHDS method. Takes a bundle directory, a single file, a registered method's catalog id (mt_…) — whose source it reads in full — or a published method's address, explained at the level of its contract. Strictly read-only — it explains in the conversation and writes nothing.

---

# Explain an MTHDS method

Read a method and say what it does, in plain language.

**This skill is strictly read-only.** It writes no file, saves no document and changes nothing in the bundle — not even when asked to "document" the method. The explanation belongs in the conversation, where the user can read it, correct it and keep what they want of it. A user who wants it written down is told which skill writes: `/pipelex-design` and `/pipelex-edit` own the bundle, and the rest is theirs to paste.

## What it takes

- **A bundle directory** — every `.mthds` file beneath it, read as one library. A single file is the same job with one file in it, and is the normal shape of a simple method.
- **A registered method's catalog id** (`mt_…`) — the source belongs to the user's own organization, so explaining it means reading it: the workshop hands back the stored files and they are explained exactly as a bundle on disk is, without a byte of them being written anywhere. See [step 8](#step-8--a-method-that-is-not-on-disk).
- **A published address** (`github.com/<owner>/<repo>[/<selector>][@<tag>]`) — explained at the level of its contract, through the workshop; the source stays in the repository it names. **An address with no `@<tag>` floats**: it resolves to the default branch at its head, so the contract you explain is the one that happens to be there now and the same question can get a different answer tomorrow. Accept it, and say so in one line.

## Requirements — the workshop is optional here

**A bundle directory needs no tool at all.** The source is on disk, so this skill explains it from the source. When `mthds_validate` is present, one call adds the verdict; when it is absent, the explanation is the same minus that line. Never refuse to explain a local bundle because the workshop is not connected.

A **catalog id** and a **published address** are the opposite case: nothing is on disk, so the workshop is the only way to learn anything about them at all.

**`mthds_get_method` is the local workshop's alone**, and it is what turns a catalog id from a contract into a readable method. Where it is absent while the other tools answer — the hosted console, which reads no files and therefore serves neither catalog-write tool — a catalog id is explained at contract level, exactly as an address is, and the explanation says which of the two readings it is. That is a narrower explanation, not a stop.

- **If the workshop is absent from this session** (the MCP server isn't connected), STOP and tell the user in one line: *"The Pipelex MCP server isn't connected — on Mistral Vibe the local workshop (`npx -y @pipelex/mcp@latest`) is not auto-spawned: append the `[[mcp_servers]]` entry from `mcp/vibe-mcp.toml` in the `pipelex-vibe` bundle (beside its `skills/` directory) to the end of `~/.vibe/config.toml`, after deleting any `mcp_servers = []` line and any hand-registered `pipelex` entry there, write your `PIPELEX_API_KEY` into its `env` table, then retry."* That stop is only for a target that lives on the platform — a bundle directory on disk is still explained from its source, with the verdict line left out.
- **If a call returns `status: "error"` with an error of class `config`** (missing or rejected `PIPELEX_API_KEY`, unreachable API), STOP the same way and surface the error's `hint` verbatim. Same scope: on a local bundle a `config` error costs the verdict line and nothing else — carry on and say it was not checked.
- The server authenticates to the API with **`PIPELEX_API_KEY`** from its `env` table in `~/.vibe/config.toml`, never from the session environment: Mistral Vibe passes no shell variables to a stdio MCP server, so an exported key reaches the plugin's validation hook but not the server.

## Mode

Automatic. Reading and explaining costs nothing and changes nothing, so there is no confirmation to ask for. The stops in the table at the end are the only questions.

---

## Step 1 — Read the whole library, then judge it

Every `.mthds` file beneath the directory, not the root alone. They are **one method**: a concept declared in one file is referenced from another, and a pipe's implementation routinely sits in a different file from the `PipeSignature` that declared it. Read them all before saying anything about any of them — an explanation written from the root file alone reports gaps that the file next to it fills.

## Step 2 — Resolve every signature before calling it pending

A `PipeSignature` is **pending only when no concrete pipe of the same code exists anywhere in the files you read.**

This is the rule that decides whether the method is finished, so it is worth knowing why it is not obvious. Signature-driven design is deliberately additive: each refinement adds a file and leaves the satisfied signature header behind in the file that declared it. So a header sitting beside its own implementation is construction scaffolding, not a gap — the same judgement `/pipelex-organize` uses when it drops one. Resolve each signature against the whole set: a satisfied one is simply the declaration of a pipe that you explain through its implementation, and only an unsatisfied one is a contract that is not built yet.

**When the workshop answered, its `pending_signatures` is the authority** and your reading must agree with it. Where the two disagree, say so and give the tool's list — a disagreement means a file was missed or a code is spelled two ways, and that is worth more to the user than a tidy explanation.

## Step 3 — The verdict, when the workshop is there

One `mthds_validate` call over the same files. Prefer the path form `{path: <absolute path to the file>}` — it keeps the real path as provenance in diagnostics and spares copying whole bundles into the request; the workshop resolves a path against **its own** working directory, so pass an absolute one. Inline `{content: <file content>, uri: <path relative to the bundle dir>}` is the fallback, and the only form the hosted console accepts. It adds two things and nothing else:

- **the verdict line** — whether the method is valid, whether it is runnable, and what is still pending;
- **the main pipe's typed signature**, from the verdict's `main_pipe`: its namespaced ref, each declared input with its concept and whether it is required, and the concept it produces.

Without the tool, explain from the source and **say the verdict was not checked**. Your own reading of the source is not a guess, and it is exactly what that path runs on — the pipe types, the concepts, and the backlog step 2 resolved are all yours to state. What must never happen is a tool answer being invented: do not present a validation verdict, a typed signature or a pending list as the workshop's when the workshop did not answer, and do not guess at validity. Say whose reading it is, and the distinction stays visible.

**On a target that is not on disk there is no such fallback.** There is no source to read, so a missing tool answer leaves nothing to say in its place — see step 8.

## Step 4 — Open with what the method *is*

The first thing the explanation says is whether the method is **complete** or a **scaffold with a backlog**, on the basis of step 2 and of the verdict when there is one. A user who asked what a method does, and got a confident walkthrough of a half-built one without being told it was half-built, has been misinformed by an accurate description.

Then, in this order:

1. **Purpose** — one sentence, in the user's terms rather than the bundle's.
2. **Inputs** — each with its concept and what it actually carries.
3. **Output** — the concept it produces and what is in it.
4. **The flow** — step 5.
5. **Custom concepts** — the ones this method defines, not the native ones it uses.
6. **The backlog**, when there is one: each unsatisfied signature, by code, with the contract it promises.

## Step 5 — Follow the layout: the root first, then one passage per module

The explanation follows the shape of the library, which is the shape `/pipelex-organize` produces and which a reader discovers progressively: **the root file gives the contract and the top-level flow**, then **one passage per module file**, each named by its file. A method that fits in one file gets one passage — that is the simple case, not a missing structure.

Trace the flow from the main pipe, and take the controllers in their own terms:

| Pipe | How to read it |
|---|---|
| `PipeSequence` | follow `steps` in order |
| `PipeBatch` | name `batch_over` and `batch_as`, then explain the inner pipe once |
| `PipeParallel` | list the branches and say what is combined at the end |
| `PipeCondition` | map each condition to the pipe it routes to |

## Step 6 — Name every pipe by its type

Every pipe is named with its type, and the leaves are where the method actually does something: `PipeLLM` generates text or a structured output, `PipeExtract` pulls pages out of a document or image, `PipeSearch` searches the web, `PipeImgGen` generates images, `PipeCompose` templates or constructs an output without a model, and `PipeFunc` calls a registered Python function.

`PipeCompose` is worth pointing out by name when you meet one: it looks like a model step in a list of pipes and is not one, so a reader who assumes every leaf costs inference will misjudge both the cost and the failure modes of the method.

For a **`PipeFunc`**, say one thing more, because reading the method is where a user learns it: **`PipeFunc` is experimental on the hosted plane.** Its Python runs in a sandbox with no network access, and the feature is still in development, so a method that validates can still fail when it runs. Name the pipe and its `function_name`. This skill reads and never edits, so it stops there — the fix, if one is wanted, is `/pipelex-edit` or `/pipelex-design`.

## Step 7 — A diagram, when it helps

A compact text diagram of the execution flow, adapted to the method's shape rather than forced into a line:

```
main_sequence
  1. step_one (PipeLLM) -> intermediate_result
  2. step_two (PipeExtract) -> final_output

Inputs: input_a, input_b
Output: final_output
```

## Step 8 — A method that is not on disk

The two remote targets part company here, and the reason is ownership rather than convenience. **A catalog id names the user's own organization's method**, so its source is theirs to read and this skill reads it. **A published address names somebody else's package**, and its internals ride a channel only views see, so it is described by its contract alone.

Exactly one selector per call: files, an address, or an id, never two.

### A catalog id — read it in full

`mthds_get_method` with the `method_id` and **no `output_dir`**. Omitting that argument is what keeps this skill read-only: the same tool with an `output_dir` writes the sources and a link file to disk, which is `/pipelex-catalog`'s gesture and never this one's. Do not pass it, not even to a temporary directory.

The `files` it returns are explained **exactly as a bundle on disk is** — steps 1 to 7 as written, with the returned contents standing in for the files you would have read. The verdict of step 3 is one `mthds_validate` call with the same `method_id`, and step 2's rule is unchanged: its `pending_signatures` is the authority over your own reading of the returned source.

Three things about the returned set are worth knowing before you describe it:

- **The read is bounded, and a bounded read is not a complete library.** When `truncated` is true, files come back carrying their name and byte size with **no content**. That is the one case where step 1's hazard is unavoidable — an explanation written from part of a library reports gaps the missing files would have filled — so name the files you could not read and say the explanation is partial. Never describe a withheld file's pipes as absent.
- **The stored Python comes back beside the sources.** A custom `PipeFunc`'s function is a registry key and no bundle file names its module, so this is the one reading where you can actually say which stored `.py` file defines it. Say it when it is clear from the code, and leave it at the pipe's `function_name` when it is not.
- **A method saved before the webapp's editor existed carries no file names.** It arrives as one unnamed file; explain it as a single-file method, which is what it is.

### A published address — its contract

- `mthds_validate` with `method_ref` in place of `files` gives the verdict and, **when the verdict carries one**, the `main_pipe` signature.
- `mthds_inputs_template` with the same selector and `explicit: true` gives the input shapes.
- Say plainly that the internals are not readable from here, so that the user knows they are getting the contract rather than a walkthrough and can ask the publisher for the bundle if they need one.

An id explained at contract level — the hosted console, where `mthds_get_method` is not served — reads the same way, with `method_id` as the selector, and says that the source was not read rather than implying there was none to read.

**Two verdicts leave nothing to explain, and both are said rather than filled in.** A local bundle always has its source to fall back on, and a catalog id read in full now has one too; a published address has none, so neither case is worked around here.

- **The verdict is positive but carries no `main_pipe`.** The method settles no entry pipe, the contract did not come back whole, or the workshop predates the field — the same three causes `/pipelex-integrate` names, and the one-line signature in the text summary is missing in all three. Say the verdict was positive and that it carries no signature to describe the contract with, and name which of the three the tool's own message points to. Do not reconstruct a signature from the input template.
- **The verdict is `is_valid: false`.** There is no `main_pipe` on an invalid verdict and `mthds_inputs_template` answers with `validation_errors[]` rather than shapes, so nothing about the method is readable **from the verdict** — though for a catalog id the source read above still is, and an invalid stored method is worth explaining from its source with the errors beside it. Report the errors as they came back. **Do not route a remote target to `/pipelex-edit` or `/pipelex-design`**: a stored method is fixed where it is edited — `/pipelex-catalog` is what brings it to disk first — and a published address is fixed in the repository it names.
- **The id is refused rather than read.** An unknown id and a method whose stored source is empty are **different answers** and both arrive as `input_domain` at `method_id`: the first says no such method is visible to the API key's organization, which a method from another organization reads exactly like; the second says the row exists and holds no source yet. Give the one the tool gave, and never turn the second into the first — a method with nothing saved in it is somebody's draft, not a wrong id.

---

## Where this skill stops

| Situation | What it does |
|---|---|
| the user asks for the explanation in a file | explains in the conversation and says it writes nothing; naming the skill that does |
| the workshop is absent, on a local bundle | explains from the source and says the verdict was not checked |
| the workshop is absent, on an id or an address | stops per the Requirements above — there is nothing to read |
| `mthds_get_method` is absent while the other tools answer | explains the id at contract level and says the source was not read; the hosted console serves no catalog read |
| a catalog id's source comes back `truncated` | names the files it could not read and says the explanation is partial; never reads a withheld file's pipes as absent |
| a catalog id holds no stored source | gives that answer, which is not the unknown-id answer |
| the user wants the saved method's files on disk | names `/pipelex-catalog`; this skill reads the source and writes none of it |
| a selector call answers a no-verdict error | reports the error and its `hint` verbatim; hosted address and id resolution is not live everywhere yet |
| the reading and `pending_signatures` disagree | reports both and gives the tool's list as the authority |
| a **local bundle** does not validate | explains it anyway from the source, says what the verdict was, and routes a fix to `/pipelex-edit` or `/pipelex-design` |
| an **id or address** does not validate | reports `validation_errors[]` and stops — there is no source to explain and the fix is not on this disk |
| the verdict carries no `main_pipe` | says the contract could not be described and which of the three causes the tool points to; never reconstructs one |
| the user wants the method changed | routes: `/pipelex-edit` for a contract-preserving fix, `/pipelex-design` for a structural one |

## Reference

- [MTHDS Language Reference](../shared/mthds-reference.md) — read for concept definitions and syntax
- [Native Content Types](../shared/native-content-types.md) — read when explaining what data flows through pipes (e.g., what attributes Page or Image content carries)
