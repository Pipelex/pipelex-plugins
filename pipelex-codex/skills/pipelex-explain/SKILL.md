---
name: pipelex-explain
description: Explain an MTHDS method in plain language — its contract, its flow, and every pipe in it. Use when the user says "what does this pipeline do?", "explain this workflow", "explain this method", "walk me through this .mthds file", "describe the flow", "how does this work?", or wants to understand an existing MTHDS method. Takes a bundle directory, a single file, a registered method's catalog id (mt_…) — whose stored source it reads — or a published method's address, explained at the level of its contract. Strictly read-only — it explains in the conversation and writes nothing.
---

# Explain an MTHDS method

Read a method and say what it does, in plain language. Reading costs nothing and changes nothing, so there is no confirmation to ask for. It takes:

- **A bundle directory**: every `.mthds` file beneath it outside `runs/`, read as one library. A single file is the same job with one file in it.
- **A registered method's catalog id** (`mt_…`): the user's own organization's method, so its stored source is read and explained exactly as a bundle on disk is.
- **A published address** (`github.com/<owner>/<repo>[/<selector>][@<tag>]`): explained at the level of its contract, through the workshop; the source stays in the repository it names. **An address with no `@<tag>` floats**: it resolves to the default branch's head, so the same question can get a different answer tomorrow. Accept it, and say so in one line.

## Requirements — the workshop is optional here

- **A bundle directory needs no tool at all**: it is explained from its source, and `mthds_validate`, when present, adds the verdict line. Never refuse to explain a local bundle because the workshop is not connected.
- **A catalog id or a published address needs the workshop**, since nothing of it is on disk. Where `mthds_get_method` is absent while the other tools answer, an id is explained at contract level, as an address is, and the explanation says which reading it is: a narrower explanation, not a stop.
- **If the workshop is absent from this session**, the Pipelex MCP server isn't connected: STOP, and tell the user in one line what [the connection reference](../shared/credentials.md#the-tool-is-absent) says for Codex. That stop is only for a target that lives on the platform — a bundle directory on disk is still explained from its source, with the verdict line left out.
- **If a call returns `status: "error"` with an error of class `config`** (missing or rejected `PIPELEX_API_KEY`, unreachable API), STOP the same way and surface the error's `hint` verbatim; when it is about the key, read [where the key comes from](../shared/credentials.md#where-the-key-comes-from) before saying anything more. Same scope: on a local bundle a `config` error costs the verdict line and nothing else — carry on and say it was not checked.

## Guards

- **This skill is strictly read-only.** It writes no file, saves no document and changes nothing in the bundle, not even when asked to "document" the method. The explanation stays in the conversation; a user who wants it written down is told that `/pipelex-design` and `/pipelex-edit` own the bundle, and the rest is theirs to paste.

## Steps

### 1. Read the whole library

For a bundle, read every `.mthds` file beneath the directory, not the root alone, and none under `runs/`, which holds a run's artifacts. They are one method: a concept declared in one file is used in another, and a pipe's implementation often sits in another file than the `PipeSignature` that declared it. **Read them all before saying anything about any of them.**

**For a catalog id or a published address, read [not-on-disk.md](references/not-on-disk.md) before the first call on it.** An id's source comes from `mthds_get_method` with the `method_id` and **no `output_dir`**: with one, the same tool writes the sources and a link file to disk, which is `/pipelex-catalog`'s gesture and never this one's. Do not pass it, not even to a temporary directory.

### 2. Resolve every signature before calling it pending

A `PipeSignature` is **pending only when no concrete pipe of the same code exists anywhere in the files you read.** A satisfied header is construction scaffolding that signature-driven design leaves behind: explain that pipe through its implementation; only an unsatisfied signature is a contract not built yet. **When the workshop answered, its `pending_signatures` is the authority**: where your reading disagrees, say so and give the tool's list, since a file was missed or a code is spelled two ways.

### 3. The verdict, when the workshop is there

One `mthds_validate` call over the same files. Submit every `.mthds` file beneath the bundle directory **except anything under a `runs/` directory**, where `/pipelex-run` saves a completed run's artifacts: a method that emits or echoes a `.mthds` file would otherwise have its own output submitted as part of its source. Prefer the path form `{path: <absolute path to the file>}`. The workshop refuses a path outside **its own** working directory, where the harness launched it; relaunching the harness from a directory holding the bundle cures that. Inline `{content: <file content>, uri: <path relative to the bundle dir>}` is the fallback. **Pass `graph_page: false`** wherever the tool lists that argument: on `{path}` files the workshop otherwise writes the method's flowchart, `method-graph.html`, beside them, and this skill writes nothing. The call adds two things and nothing else: the **verdict line** (whether it is valid, whether it is runnable, what is still pending) and, when the verdict carries a `main_pipe`, the **main pipe's typed signature**: its namespaced ref, each declared input with its concept and whether it is required, and the concept it produces.

Without the tool, explain from the source and **say the verdict was not checked**. Your own reading of the source is not a guess: the pipe types, the concepts and step 2's backlog are yours to state, saying whose reading it is. But do not present a validation verdict, a typed signature or a pending list as the workshop's when the workshop did not answer, and do not guess at validity. **On a target that is not on disk there is no such fallback.**

### 4. Open with what the method *is*

Say first whether it is **complete** or a **scaffold with a backlog**, from step 2 and the verdict when there is one. Then, in order: its **purpose**, in one sentence in the user's terms rather than the bundle's; its **inputs**, each with its concept and what it actually carries; its **output**, the concept it produces and what is in it; **the flow** (step 5); the **custom concepts** it defines, not the native ones it uses; and **the backlog**, when there is one: each unsatisfied signature, by code, with the contract it promises.

### 5. The flow: the root first, then one passage per module

**The root file gives the contract and the top-level flow**, then **one passage per module file**, each named by its file; a one-file method gets one passage, the simple case and not a missing structure. Trace the flow from the main pipe, reading the controllers in their own terms:

| Pipe | How to read it |
|---|---|
| `PipeSequence` | follow `steps` in order; a step with `batch_over` and `batch_as` runs its pipe once per item |
| `PipeBatch` | name `input_list_name` and `input_item_name`, then explain the `branch_pipe_code` pipe once |
| `PipeParallel` | list the branches and say what is combined at the end |
| `PipeCondition` | map each condition to the pipe it routes to |

Name every pipe with its type; the leaves are where the method actually does something: `PipeLLM` generates text or a structured output, `PipeExtract` pulls pages out of a document or image, `PipeSearch` searches the web, `PipeImgGen` generates images, `PipeCompose` templates or constructs an output without a model, and `PipeFunc` calls a registered Python function. Point out a `PipeCompose` by name when you meet one: it looks like a model step in a list of pipes and is not one, so a reader who assumes every leaf costs inference misjudges the method's cost and failure modes. For a **`PipeFunc`**, name the pipe and its `function_name`, and say: **`PipeFunc` is experimental on the hosted plane.** Its Python runs in a sandbox with no network access, and the feature is still in development, so a method that validates can still fail when it runs. A fix, if one is wanted, is `/pipelex-edit`'s or `/pipelex-design`'s.

Where it helps, add a compact text diagram of the execution flow, adapted to the method's shape rather than forced into a line:

```
main_sequence
  1. step_one (PipeLLM) -> intermediate_result
  2. step_two (PipeExtract) -> final_output

Inputs: input_a, input_b
Output: final_output
```

## Stops

| Condition | Do this |
|---|---|
| the user asks for the explanation in a file | explain in the conversation, say this skill writes nothing, and name the skill that does |
| the workshop is absent, on a local bundle | explain from the source and say the verdict was not checked |
| the workshop is absent, on an id or an address | stop per the Requirements: there is nothing to read |
| `mthds_get_method` is absent while the other tools answer | explain the id at contract level, say the source was not read, and name the cause [not-on-disk.md](references/not-on-disk.md) gives |
| an id's source comes back `truncated` | name the files you could not read and say the explanation is partial. Never describe a withheld file's pipes as absent. |
| an id is refused at `method_id` | give the tool's answer: an unknown id and an empty stored source are different answers, and an empty one is somebody's draft, not a wrong id |
| a selector call answers a no-verdict error | report the error and its `hint` verbatim; hosted address and id resolution is not live everywhere yet |
| a **local bundle** does not validate | explain it anyway from the source, say what the verdict was, and route a fix to `/pipelex-edit` or `/pipelex-design` |
| a **catalog id** does not validate | explain it from the source read above with `validation_errors[]` beside it, and say the fix is not on this disk |
| a published **address** does not validate | report `validation_errors[]` and stop: there is no source to explain, and the fix is upstream |
| the verdict carries no `main_pipe` | say so, and which cause the tool's message points to: the method settles no entry pipe, the contract did not come back whole, or the workshop predates the field. Do not reconstruct a signature from the input template. |
| the user wants the method changed, or a saved method's files on disk | route: `/pipelex-edit` for a contract-preserving fix, `/pipelex-design` for a structural one, `/pipelex-catalog` to bring a saved method to disk |

## References

- [not-on-disk.md](references/not-on-disk.md): a catalog id or a published address, before the first call on it.
- [MTHDS reference](../shared/writing-mthds.md): a concept definition or a syntax question.
- [Native content types](../shared/native-content-types.md): what data flows through a pipe, such as the attributes a `Page` or an `Image` carries.
