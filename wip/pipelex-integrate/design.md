---
status: active
item: L-260830-344594
---

# Design — `pipelex-integrate`: wire an MTHDS method into a Python or TypeScript codebase

**Written 2026-08-30**, from the brief beside this file ([`brief.md`](brief.md)), against the sources it names: `pipelex-mcp/SPEC.md` → "Codegen Scope" and "The write arm", `pipelex-starter-js/docs/codegen.md`, `pipelex-starter-python/Makefile` and `docs/codegen.md`, the two starter call sites, and `docs/specs/pipelex-codegen.md`. **Status: draft — awaiting ratification.** The decision boxes at the end are what a ratification answers; the implementation tracker is [`plan.md`](plan.md) and starts after they are answered. Ledger item `L-260830-344594`. File and line references were accurate on the writing date; verify them against the code before implementing.

Everything the brief lists as a *finding* is taken as a constraint and not re-argued here. This document settles the brief's six open questions and the smaller decisions the implementation needs, in the order a reader of the skill would meet them.

## 1. What the skill is

`pipelex-integrate` takes a method — a local `.mthds` bundle, a published address (`method_ref`), or a catalog id (`method_id`) — and a Python or TypeScript codebase, and leaves the codebase able to call the method with types that cannot silently drift from it. Concretely, it:

1. picks the codegen target that matches the project's language and audience;
2. has the workshop write the generated tree into a dedicated directory per method, through `mthds_codegen`'s write arm, so no artifact byte ever passes through the model;
3. makes the project's formatters and linters leave that tree alone while its type checker keeps covering it;
4. records how the tree was generated in a small sidecar beside the lock, so the next run knows what to refresh and a bundle edit is detectable;
5. wires the offline drift check into the gate the project already runs, where one exists for the language;
6. writes one typed call-site module per method, running the method through `@pipelex/sdk` or `pipelex-sdk` and narrowing its output with the generated binder;
7. verifies the result with the project's own type checker and the drift gate it just installed.

Re-running it on a project that already carries a generated tree is **refresh mode**, the common case: the bundle changed, the types are regenerated in place, the call site is touched only if the types no longer fit it.

**What it is not.** It is not a build tool (no watch mode, no build-time hook, no per-project harness — the workshop is the harness), not a runner (it never executes the method; `/pipelex-inputs` prepares inputs and offers a run), and not a design skill (a method that does not validate or is not runnable is sent back to `/pipelex-design`). It does not write tests, wire UI routes or CLI commands, or edit existing business code; it stops at one callable module per method, and a user who wants more says so in the conversation.

## 2. The shape it produces

The target state is the reference design both starters converged on, minus the per-project scaffolding the workshop replaces.

**TypeScript** (`ts-zod`):

```
methods/<method>/main.mthds              # the source of truth, committed (files source only)
src/generated/<method>/
  types.ts                               # zod schemas + inferred types — written verbatim by the workshop
  binder.ts                              # parse<Concept> / serialize<Concept> — written verbatim by the workshop
  codegen.lock                           # the trust-chain lock — written verbatim by the workshop
  sources.json                           # the skill's sidecar: how this tree was generated (§4.6)
src/pipelex/<method>.ts                  # the call site: one typed function per method (§4.1)
src/pipelex/client.ts                    # shared: the PipelexApiClient factory, created once per project
src/pipelex/wireOutput.ts                # shared, temporary: the wire-null normalizer (§4.8)
scripts/codegen-check.mjs                # the offline gate, copied from the skill's references (§4.5)
```

**Python** (`python-pydantic`, or `python-structures` for a Pipelex host):

```
methods/<method>/main.mthds
<package>/generated/__init__.py          # the skill's: makes the trees importable (unstamped, never an artifact)
<package>/generated/<method>/
  __init__.py                            # the skill's
  models.py                              # or structures.py — written verbatim by the workshop
  codegen.lock                           # written verbatim by the workshop
  sources.json                           # the sidecar
<package>/pipelex/<method>.py            # the call site
```

Paths are the defaults; §5 says how the skill adapts them to a project that already has a convention. The directory names are the method's, in the language's casing (`summarize-pdf` in TypeScript, `summarize_pdf` in Python), derived from the bundle's root domain, the address's package name, or the catalog method's name.

Two artifacts the starter's tree carries are **deliberately absent**: `contracts.ts` (the pipe IO contracts and the input-form descriptor — §4.3) and the starter's `derived` map in `sources.json` (the skill emits no derived artifact the lock cannot sign, so there is nothing to record).

## 3. The procedure

The skill is automatic by default, with the same mode rules as `pipelex-inputs` (an explicit user signal wins; a genuinely ambiguous decision pauses for one question). Every MCP call branches on the structured verdict, never on transport, and the `config`-class stop discipline is the plugin's usual one.

1. **Identify the method and the project.** The method comes from the conversation (a bundle directory, an address, an `mt_…` id, or a name resolved through `mthds_list_methods`). The project root is the nearest directory holding a `package.json` or a `pyproject.toml` (or `setup.py` / `requirements.txt`) above the user's working area; a workspace holding several is a question, not a guess. Detection rules are in §5.
2. **Prove the method is integrable.** `mthds_validate` on the selector: `is_valid: true` **and** `is_runnable: true` with no pending signatures. A scaffold with pending signatures has a concept set but cannot run, so integrating it produces a call site that cannot succeed — route to `/pipelex-design` instead. An invalid method carries its `validation_errors[]` to `/pipelex-design` / `/pipelex-edit` the way `pipelex-inputs` does.
3. **Read the pipe's signature.** `mthds_inputs_template` with the same selector and **`explicit: true`** — the one skill call in the plugin that wants the ceremonial envelope, because it needs each input's declared concept ref to type the call site (§4.3, §4.9). Record the resolved `pipe_ref`. The main pipe's output concept and multiplicity come from the bundle for a files source, and from the heuristic in §4.3 otherwise.
4. **Choose the target** (§4.2) and **the destination** (§5). State both in one line before writing anything.
5. **Make the tooling leave the tree alone — before the tree exists.** Add the generated directory to the formatter's and linter's ignore lists per §5, confirm the type checker's include still covers it, and confirm it is not gitignored. This ordering is load-bearing: the first project-wide `format` run after generation would otherwise rewrite the stamps.
6. **Generate.** `mthds_codegen` with the selector, `target`, and `output_dir` expressed **relative to the workshop's working directory** (§4.4). Branch: `is_valid: false` → back to step 2's repair route; `status: "error"` located at `output_dir` → a foreign file or a containment escape, handled per §6; `runtime` mid-write → call again once with the same `output_dir`, as the tool's own hint says. On success, confirm `is_current: true` and an empty `orphans[]`; a non-empty `orphans[]` is reported by name and never cleaned (§4.7).
7. **Write the sidecar** `sources.json` beside the lock (§4.6).
8. **Add the dependencies the generated code needs**, with the project's own package manager: `zod` and `@pipelex/sdk` for TypeScript; `pydantic` and `pipelex-sdk` for Python (`python-structures` needs `pipelex`, which is already present by the time that target is chosen — §4.2). State what is added; interactive mode confirms first.
9. **Write the call site** and its shared helpers (§4.1, §4.8).
10. **Wire the offline gate** into the project's existing aggregate check (§4.5). TypeScript gets the lock check and the source-hash check; Python gets the sidecar only, with the asymmetry stated in the report.
11. **Verify.** Run the project's formatter on the files the skill wrote (never on the generated tree — the exclusion from step 5 is what makes a project-wide run safe), then its type checker, then the drift gate. A failure here is the skill's to fix before it reports.
12. **Report.** What was generated and where, the target and why, the call site's signature, what changed in the tooling config, how to refresh (`/pipelex-integrate` again after a bundle edit), and — for Python — that no offline drift check exists yet and refresh is the guard.

**Refresh mode** (§4.10) enters at step 1 when a sidecar for the method already exists, skips steps 5, 8 and 10 except to verify they still hold, and touches the call site only if the regenerated types no longer type-check against it.

## 4. Decisions

### 4.1 Where the skill's responsibility ends — one callable module per method (brief Q1)

**Decision: the skill writes a complete, typed, callable function per method — and stops there.** Not an annotated example, not "types plus instructions": a function the application can import and call. The brief's "properly integrate" reads that way, and the alternative leaves the last mile to improvisation, which is what the skill exists to remove.

The commitment is bounded precisely, so it does not grow into "rewrite my app":

- **One new module per method**, placed by the project's convention (§5): it exports one async function named after the method, whose parameters are the pipe's inputs typed from the explicit template (§4.9) and whose return type is the generated output type. It loads the committed bundle at call time (files source) or names the pinned address / id (§4.2), runs it through the SDK's self-healing lifecycle call (`startAndWaitForResult` / `start_and_wait`, which takes the durable path on the hosted API and the blocking path on a bare runner), and narrows `main_stuff` through the generated binder (`parse<Concept>` in TypeScript, `Model.model_validate` in Python). Credentials come from the environment through the SDK's own defaults (`PIPELEX_API_KEY`, `PIPELEX_BASE_URL`); the module never reads them itself.
- **At most two shared helpers, created once per project and reused by every later method**: a client factory (`getPipelexClient()` / a `PipelexAPIClient` construction pattern that matches how the project builds its other clients), and — TypeScript only, until `L-260820-ee327d` lands — the wire-null normalizer of §4.8. If the project already has a Pipelex client module, the skill uses it.
- **File-bearing inputs** (`Document`, `Image`) are typed as the canonical content dict `{ url }` — an `http(s)` URL or a `pipelex-storage://` reference. The module does not upload; its docstring points at the SDK's `prepareInputs` for callers holding local files or bytes, which is the SDK's own signature-driven upload and not something to hand-roll per method.
- **Not written:** tests, routes, UI, CLI commands, error-model integration beyond letting the SDK's typed errors propagate, retries, caching. In interactive mode the user can ask for any of these and the skill does them as ordinary coding work in the conversation; they are not part of the skill's contract.

The call site follows the project's conventions where it can see them (module style, quoting, error handling, sync versus async) and the SDK's defaults where it cannot. Python projects that are synchronous throughout get a thin sync wrapper around the async function; async-native projects (FastAPI, an existing async codebase) get the async function alone.

### 4.2 Which run source the call site uses, and the guard on its drift (brief Q2)

**Decision: the call site runs the method from the same source the types were generated from, the sidecar records that source, and the skill never mixes sources.** The shape depends on the selector:

| Types generated from | The call site runs | Drift guard |
| --- | --- | --- |
| **Local files** (the recommended shape) | the committed bundle, read at call time as `mthds_contents` | the sidecar's source hashes: a bundle edit without a regeneration is detectable offline (TypeScript gate) and by the next skill run (both languages), and `pipelex-edit` / `pipelex-design` announce it at edit time (§7) |
| **`method_ref@tag`** | `method_ref` at the **same pinned tag** | the tag is the pin: a tag is immutable in practice, and the run ack carries the fetched `commit_sha` as provenance; a `method_ref` with no tag is refused for a committed integration (the address would float) |
| **`method_id`** | `method_id` | **none offline** — the catalog is unversioned, so an edit to the stored method invalidates the committed types with nothing to detect it; the skill says so in one line, recommends committing the source or publishing an address, and proceeds only on the user's say-so, recording the id so refresh mode is at least the guard |

The rule that matters is the negative one: **never generate from one source and run from another.** Types from a local bundle over a call site that runs by `method_id` is the shape that drifts silently, because the two halves have no relation the tooling can see. If the user wants the call site to run a catalog method, the types are generated from that id too, with the warning above.

A bundle that is outside the project root (a `pipelex-wip/` directory elsewhere on disk) is copied into the project under `methods/<method>/` first — the call site loads it at runtime and the sources must be versioned with the code — and the user is told. A bundle already inside the project stays where it is; the sidecar records its paths.

### 4.3 The contracts artifact, and where the pipe signature comes from (brief Q3)

**Decision: the skill does not produce a contracts artifact.** `pipelex-starter-js` needs `PIPE_IO_CONTRACTS` and `INPUT_FORM` to drive a form kernel and gate run inputs in a Server Action; a typed function has neither concern — its parameter types *are* the input gate, and the SDK validates the run request. Nothing in the skill's scope consumes the descriptor.

What the skill does need is the **pipe's signature**: input names with their concept refs, and the main pipe's output concept with its multiplicity. Today this reaches the model through two channels and one gap:

- **Inputs** — `mthds_inputs_template` with `explicit: true` returns each input as `{concept, content}` in `structuredContent`; the concept ref is exactly what types the parameter. This is why the skill departs from the plugin's `explicit: false` pin (§4.9).
- **Output, files source** — read from the bundle: the root's `main_pipe` and that pipe's `output` declaration, multiplicity included. The model can read the files; no tool call is needed.
- **Output, `method_ref` / `method_id` source — the gap.** `mthds_validate` carries `main_pipe_ref` and `pipe_io_contracts` on the view-only `_meta` channel, which never reaches the model, and the workshop has no views. So for a method whose source is not on disk, no in-context channel names the output concept. **v1 heuristic:** after generation, the candidate output concepts are the generated types minus the input concepts minus natives; exactly one candidate is taken and stated as an assumption; several is one question to the user, listing them; multiplicity is assumed single unless the user says otherwise. For a public `method_ref` the model may additionally read the package's `.mthds` at the tag from the repository to answer exactly.
- **The follow-up.** The heuristic is a stopgap. The correct fix is in `pipelex-mcp`: a compact main-pipe signature — `main_pipe_ref`, input names → concept refs, output concept ref and multiplicity — promoted from `_meta` to `structuredContent` on a valid `mthds_validate` verdict (or on `mthds_codegen`'s valid arm). It is small where the full descriptor is not, and it is what any integrating agent needs. Filed against `pipelex-mcp` as `L-260830-e8b2e0`, discovered from this item; when it lands, the heuristic and its question are deleted.

### 4.4 The write arm is mandatory, and the model never writes an artifact (brief finding)

**Decision: every `mthds_codegen` call passes `output_dir`; a refused or failed write is handled as a refusal, never by re-calling without `output_dir` and writing the bytes from the conversation.** The brief's efficiency argument decides the first half. The second half is a correctness rule: an artifact re-emitted through the model is one trailing newline away from a broken stamp, and the whole point of the trust chain is that the tree on disk is byte-identical to what the engine emitted. The tool's own posture ("a refused or failed write is a no-verdict, never a fallback to riding the content") is the skill's posture too.

Three consequences the skill has to carry:

- **`output_dir` is relative to the workshop's working directory, which is the directory the harness was launched in** — the host spawns the server there (`process.cwd()` in `pipelex-mcp/src/local/server.ts`), the launcher wrapper does not `cd`, and containment is real-path-checked against it (`workspace-boundary.ts`, `resolveSaveDir`). The skill computes the generated directory's path relative to the session's initial working directory and passes that. **A project root outside that directory cannot be written to**, and the skill stops with the instruction to relaunch the harness from the project (or, on Vibe, to register the workshop with that working directory) — it does not fall back to riding content.
- **The generated files are never opened for editing and never formatted.** Step 5 of §3 precedes step 6 for this reason, and step 11 formats only the files the skill authored.
- **A destination that refuses is a destination that was wrong.** The writer refuses any unstamped file, symlink, or directory at an artifact path and leaves the tree byte-identical; the skill treats that as "this is not a dedicated generated directory", picks or asks for one that is, and never pre-clears anything.

### 4.5 The offline drift gate — one line for TypeScript, an honest gap for Python (brief finding)

**Decision, TypeScript:** the skill installs a small **plain-ESM script** (`scripts/codegen-check.mjs`, copied verbatim from the skill's `references/`) that walks each generated directory the caller names, runs `@pipelex/sdk`'s `runCodegenCheck` over it with the lock read from disk, and compares the sidecar's source hashes against the committed `.mthds` files; it prints drifts by category and exits `0` current / `1` drift or stale source / `2` no verdict, the exit contract the starter established. It is `.mjs` rather than `.ts` so it runs under plain `node` in any project regardless of its TypeScript build setup; it imports nothing but `@pipelex/sdk` and Node builtins; and it writes through `process.stdout` / `process.stderr` so a `no-console` lint rule does not fire on it. The skill registers it as an npm script (`codegen:check`) and **extends the project's existing aggregate gate** — a `check` / `ci` / `validate` script, a Makefile `check` target, or the obvious lint/test step in an existing GitHub workflow — rather than inventing a new one; a project with no aggregate gate gets the script and a sentence in the report saying where to call it.

The script exists because `@pipelex/sdk` ships the check as a pure function and no CLI; `L-260820-2ba0f4` (upstream the walk/write/sidecar workflow into the SDK as a CLI or exported functions) is the item that retires it, at which point the gate becomes a one-line invocation and the skill stops copying a script into projects. The skill's reference script is written so that swap is mechanical.

**Decision, Python:** no gate is installed. `pipelex-sdk` has no offline check (`L-260830-4e43cd`), and the only one that exists — `pipelex codegen check` — needs the `pipelex` runtime, which a `python-pydantic` consumer deliberately does not have. The skill does **not** add `pipelex` as a dependency to get a gate; that would reverse the decision the target expresses. It writes the sidecar anyway (refresh mode and the editing skills' staleness notice both read it — §7), and the report states the asymmetry plainly: the generated tree is protected by its stamps and lock, but nothing in CI proves it current; refresh with `/pipelex-integrate` after every bundle edit. The one exception is the `python-structures` audience, whose project already depends on `pipelex`: there, `pipelex codegen check <dir>` is wired into the existing gate exactly as `pipelex-starter-python` does. When `L-260830-4e43cd` lands, the Python branch gains its one-line gate and the asymmetry paragraph is deleted.

### 4.6 The sidecar — `sources.json`, the skill's own memory (brief finding, Q5)

**Decision: the skill writes an unstamped `sources.json` beside every lock it causes to exist**, and it is the only state the skill keeps. The lock signs the artifacts, not their sources, and the write arm produces no sidecar; without one, the second invocation has to re-derive the selector, the target, and the destination from the conversation every time, and a bundle edit is undetectable except by regenerating and diffing.

The file keeps the starter's name and the starter's `sources` map, deliberately: `@pipelex/sdk` documents `sources.json` as the sidecar its orphan rule is designed to tolerate (an unstamped `.json` is never an artifact and never an orphan), and `L-260820-2ba0f4` plans to upstream a sidecar under that name, so converging now costs nothing and a later engine-owned sidecar can subsume this one. The shape:

```json
{
  "comment": "Written by /pipelex-integrate. `method` and `target` are how this tree was generated — re-run the skill to refresh it. `sources` is the SHA-256 of each local .mthds source, so a bundle edit that was never regenerated is detectable. Not part of the codegen lock; do not hand-edit.",
  "generator": "pipelex-integrate",
  "method": { "files": ["methods/summarize-pdf/main.mthds"] },
  "target": "ts-zod",
  "pipe": {
    "pipe_ref": "summarize.summarize_pdf",
    "inputs": { "document": "native.Document", "context": "native.Text" },
    "output": "summarize.DocumentSummary"
  },
  "sources": { "methods/summarize-pdf/main.mthds": "<sha256 of the file's bytes>" }
}
```

`method` is exactly one of `{files}`, `{method_ref}`, `{method_id}` — the selector as it was passed. Paths are relative to the project root, not to the workshop's working directory, so the file survives a relaunch from elsewhere. `pipe` records what the call site was typed against, so refresh mode can tell a signature change from a body change without re-reading the call site. `sources` is empty for a `method_ref` / `method_id` source; the `output` string uses the language's multiplicity notation (`Concept[]`) when the pipe produces a list. Hashes are over raw bytes; a CRLF checkout therefore reads as stale, and the remedy is a regeneration that changes nothing — the starter normalizes line endings and the upstreamed sidecar should too, but a false stale whose fix is a no-op is acceptable in the skill for the sake of a hash the model can compute with `shasum` / `sha256sum` / `hashlib`.

### 4.7 One directory per method, orphans reported and never deleted (brief finding)

**Decision: the skill always writes each method to its own directory, and when `orphans[]` is non-empty it names them, says what they are, and does nothing else.** The tool never deletes an orphan and neither does the skill: the moment two methods share a directory, "clean up the orphans" deletes real files. A non-empty `orphans[]` on a fresh integration means the chosen directory was not fresh — an earlier generation, a different target, or an engine rename — and the report says a dedicated directory per generation is the fix, in the tool's own words. On a refresh into the method's own directory, an orphan can only be an artifact the engine stopped emitting; the report names it and leaves the decision to the user.

A directory that already holds a `codegen.lock` is refresh mode only if its sidecar names the same method; otherwise the skill chooses a different directory name and says why.

### 4.8 The wire-`null` mismatch — a shared helper with an expiry (finding surfaced in design)

The ts-zod emitter projects a non-required field as `.optional()` (`pipelex/pipelex/codegen/emitters/ts_zod.py`, `_field` modifier), which in zod means `| undefined` and rejects `null` — but the runtime serializes an unset optional field as an explicit `null` (`WorkingMemory.dump_for_transport` is a `model_dump(serialize_as_any=True)` with no `exclude_none`). `pipelex-starter-js` confirmed this against a live hosted run and carries `dropWireNulls` as a schema-guided workaround; the defect is tracked as `L-260820-ee327d` (P1, `pipelex`). Python is unaffected: the pydantic projection emits `str | None = None`.

**Decision: until `L-260820-ee327d` lands, the TypeScript call site parses through a shared `wireOutput(results, schema)` helper, copied once per project from the skill's `references/`, that drops a `null` only where the concept's own zod schema says the field is optional with no default, descends declared objects and arrays, and passes anything opaque (`z.unknown()`, `z.record()` keys, unions) through untouched.** A blind deep null-strip is rejected for the reason the starter's design note gives: inside a `z.record()` a `null` is data. The helper's header names the item it waits on and says the file is deleted, not maintained, when the emitter projects `.nullish()`; the plan carries a checkpoint to re-check the item before shipping, since it may land first — in which case the helper is never written and the call site parses `main_stuff` directly.

### 4.9 The template shape — `explicit: true`, the plugin's one exception

The plugin's standing rule pins every `mthds_inputs_template` call to `explicit: false` (`docs/decisions.md`, "the light template stays pinned"), because the three existing call sites only show or key-compare the template. This skill is different in kind: it needs **each input's declared concept ref** to write a typed parameter, and the light shape carries values without concepts. **Decision: `pipelex-integrate` passes `explicit: true`, and the decisions record gains a sentence naming it as the exception and why.** The rule's rationale (the envelope is an authoring aid the other skills do not need) is unchanged; a fourth call site with a need for concept identity is exactly the case the rule said would justify it.

### 4.10 The second invocation — refresh mode (brief Q5)

**Decision: refresh mode re-derives nothing the sidecar already records, regenerates in place, and leaves alone everything the regeneration did not invalidate.**

Entered when: the user asks to refresh, regenerate, or update the types; `pipelex-edit` or `pipelex-design` hand off after editing a bundle a sidecar names (§7); or the skill finds a sidecar for the method it was asked to integrate.

| Taken from disk | Re-derived | Left alone |
| --- | --- | --- |
| the selector, target, destination, and pipe record — from the sidecar; the previous `crate_fingerprint` — from the lock | the source hashes (files source), compared before regenerating so the report can say whether the bundle actually changed; the pipe signature, through `mthds_inputs_template` again, compared to the sidecar's `pipe` record | the tooling exclusions (verified, re-added only if missing), the dependencies, the client and wire-output helpers, the gate wiring, tests, other methods' trees |

The regeneration is one `mthds_codegen` call with the recorded arguments. Its `crate_fingerprint` against the old lock's says what happened: unchanged means a restamp at most (an engine bump rewrites every stamp with no semantic change — reported as such, with the diff left to the user's commit); changed means the concept set moved. Then the project's type checker runs. **The call site is edited only if it no longer type-checks or the sidecar's `pipe` record no longer matches the template** — a renamed input, a reshaped output — and the edit is the minimal one, stated in the report. The sidecar is rewritten last, with the new hashes and pipe record.

### 4.11 The name and its place in the family (brief Q6)

**Decision: `pipelex-integrate`.** `pipelex-codegen` — the name the `pipelex-mcp` codegen design floated (`wip/mcp-codegen/design.md`, "not filed, recorded so it is not rediscovered") — is rejected because it is the tool's name in skill clothing, which the plugin's naming convention forbids: tools are the contract and skills are the manual, named after user tasks. The task is integrating a method into an application; codegen is one step of it.

The description is written to trigger on the codebase phrasings — "use this method in my app", "call this from my code", "generate types for this method", "wire the method into", "typed client", "refresh the generated types", "regenerate the types" — and to stay silent on the authoring phrasings the other skills claim ("design", "edit", "explain", "prepare inputs"). It is model-invocable, like every skill in the plugin since `pipelex-design` lost its flag; the consent gate is inside (the one-line statement of target and destination before writing).

Its place: it is the skill after the method is done. `pipelex-design` and `pipelex-inputs` close by pointing at it when there is a codebase in the workspace (§7).

## 5. Detecting the project

The rule: **a cheap, reliable signal decides; an inconclusive one asks one question; the Python audience is never guessed when `pipelex` is a dependency.** The language-specific detail lives in the skill's `references/typescript.md` and `references/python.md`; this is the contract those files implement.

| Question | Signals, in order | When inconclusive |
| --- | --- | --- |
| **Which project?** | the user named it; else the nearest `package.json` / `pyproject.toml` (or `setup.py`, `requirements.txt`) above the working area; a workspace with several (a monorepo, a full-stack repo) | ask which app; never pick one |
| **Language → target** | `package.json` → `ts-zod` (a JavaScript project with no TypeScript build — no `tsconfig.json`, no bundler or runtime that strips types — is asked, because `types.ts` needs one); `pyproject.toml` → Python | both present at one root: ask |
| **Python audience → target** | `pipelex` **not** among the project's dependencies → `python-pydantic`, no question (`python-structures` imports the runtime and would not even load); `pipelex` present → `python-structures` if `@pipe_func` or `StructuredContent` appear in the code, else one question with `python-structures` offered first | the user's explicit request wins over all of this |
| **Package manager** | the lockfile: `package-lock.json` → npm, `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lock*` → bun; `uv.lock` → uv, `poetry.lock` → poetry, `Pipfile.lock` → pipenv | none: npm / `pip install` into the active environment, stated |
| **Generated-tree root** | an existing directory already holding generated code (`generated/`, `gen/`, `__generated__/`) → beside it; else `src/generated/` if `src/` exists, else `generated/`; Python: `<import package>/generated/` where the package is the one `[project].name` or the setuptools `packages` list names, or the top-level directory holding `__init__.py` | ask |
| **Formatter and linter exclusions** | Prettier (`.prettierrc*` or a `prettier` dev dependency) → `.prettierignore` entry; ESLint flat config (`eslint.config.*`) → `globalIgnores` / `ignores` entry, legacy `.eslintrc*` → `.eslintignore`; Biome (`biome.json*`) → the files-ignore key its version uses; Ruff (`[tool.ruff]`) → `exclude` / `extend-exclude`; Black → `extend-exclude`; isort → `skip` / `extend_skip_glob` | a tool the table does not name: read its config, add the equivalent, say so |
| **Type checker still covers the tree** | `tsconfig.json` `include` / `exclude`; `[tool.pyright]` `include`; `[tool.mypy]` `packages` / `files` | an exclusion that would drop the tree is *not* added; the report says which check covers it |
| **Aggregate gate to extend** | `package.json` `scripts.check` / `ci` / `validate` / `verify`; a Makefile `check` target; a `.github/workflows` job with a lint or test step; `.pre-commit-config.yaml` | none: the script alone, and a sentence in the report |
| **Call-site location** | the project's existing service / action / client layer (`src/actions/`, `src/services/`, `src/lib/`, a `services/` or `clients/` package) → beside it; else `src/pipelex/` / `<package>/pipelex/` | — |
| **Not gitignored** | the generated root and the sidecar must be committable; a `.gitignore` pattern that swallows them is reported, and the path is un-ignored on confirmation | — |

## 6. Failure posture

| Condition | The skill |
| --- | --- |
| `mthds_codegen` or `mthds_inputs_template` or `mthds_validate` absent | STOP with the plugin's one-line MCP-connection message (the platform-specific wording every MCP-backed skill renders) |
| `status: "error"`, class `config` — including the hosted `FF_PLAYGROUND` **403**, which is a feature gate and not a key problem | STOP, surface `hint` verbatim; never say "check your key" for a 403 |
| `status: "error"`, class `config`, `kind: "paywall"` | STOP, surface the plan-limit message |
| `is_valid: false` | route the `validation_errors[]` to `/pipelex-design` or `/pipelex-edit`; a by-id method's stored content is broken where it is edited, not here |
| validate says not runnable / pending signatures | STOP: finish the method with `/pipelex-design`; nothing generated |
| `input_domain` at `output_dir`: containment escape | STOP: the project is outside the workshop's working directory — relaunch the harness from the project root; never ride content |
| `input_domain` at `output_dir`: foreign file named | the directory is not a dedicated generated directory — choose another or ask; never delete or move the named file |
| `input_domain` at `method_ref` / `method_id` | report the selector failure as the tool words it (unknown or foreign-org id, unfetchable address, the structures refusal, a registry-form ref) |
| `runtime` after a partial write | call again once with the same `output_dir` (the writer overwrites its own stamped files); then report what landed, in the tool's words |
| success with `orphans[]` non-empty | report by name, never delete (§4.7) |
| success with `is_current: false` | a write the check disowns — report the `drifts[]` verbatim and stop; do not commit a tree the check rejects |
| `orphans_truncated: true` | say orphan detection was partial rather than reporting a clean tree |
| the project's type check fails after the call site is written | the skill's to fix (its own code), then re-run; a failure inside the generated tree is reported, not patched |
| `mthds_list_methods` absent | integrate by id or files only; never stop for it (soft dependency) |

## 7. Family wiring

Three small edits to the existing skills, each one sentence or one step:

- **`pipelex-edit` Step 7 (Report) and `pipelex-design`'s re-entry delivery:** after a successful edit to a bundle, look for `sources.json` files carrying `"generator": "pipelex-integrate"` whose `sources` name a file that changed; for each, say the generated types in that directory are now stale and offer `/pipelex-integrate` to refresh them. This is the plugin-native forgetting-guard, and it is language-agnostic — it is what gives the Python side a guard at all until `L-260830-4e43cd`.
- **`pipelex-design`'s delivery step 4 and `pipelex-inputs`' closing report:** one line — when the workspace holds a `package.json` or `pyproject.toml`, `/pipelex-integrate` wires the method into that code.
- **The `MCP_SKILLS` tuple in the tests, the README's skill list and MCP tool list, `CLAUDE.md`'s "Key dependency", and `docs/decisions.md`** gain the skill and `mthds_codegen`, exactly as `mthds_prepare_inputs` was added.

## 8. Follow-ups, filed or linked

| Item | Repo | Relation | Why |
| --- | --- | --- | --- |
| `L-260820-ee327d` | `pipelex` | related — the §4.8 helper waits on it | ts-zod `.optional()` rejects the runtime's explicit `null`; when it lands, the wire-output helper is deleted from the skill's references and the call site parses directly |
| `L-260820-2ba0f4` | `pipelex-sdk-js` | related — retires the §4.5 script | upstream the walk / write / sidecar workflow into `@pipelex/sdk` as a CLI or exported functions; the skill's gate becomes one line |
| `L-260830-4e43cd` | `pipelex-sdk-python` | discovered-from (already) | the Python offline check; when it lands, the Python branch gains its gate and the asymmetry paragraph goes |
| `L-260830-e8b2e0` | `pipelex-mcp` | discovered-from this item (filed 2026-08-30) | promote a compact main-pipe signature (`main_pipe_ref`, inputs → concept refs, output concept + multiplicity) from `_meta` into `structuredContent`, so a by-ref / by-id integration is typed exactly instead of by the §4.3 heuristic |
| `L-260829-563e9e` | workspace | related, informational | the pipe-selector campaign adds `pipe_ref` to the run request; the sidecar already records the qualified ref, and the call site moves from `pipe_code` to `pipe_ref` when the SDKs take it |

## 9. Out of scope, stated so it is not rediscovered

No change to `pipelex-mcp` from this repo (the follow-up above is filed, not worked around); no change to either starter (they are the reference, not a deliverable); no JSON Schema target until the engine serves one (`L-260829-7b7917` → `L-260829-263b9e` → `L-260829-68c7cf`); no watch mode or build-time regeneration; no per-project reimplementation of write-if-changed or orphan cleanup (the writer overwrites and reports; the SDK upstreaming owns the rest); no `contracts.ts`; no tests, routes, or UI; no hosted-console branching (the plugin only ever declares the workshop, so the write arm is always available to it).

## Decision boxes for ratification

| Box | Ruling | Ratified? |
| --- | --- | --- |
| **1 — Scope of the call site** | One complete typed callable module per method plus at most two shared helpers; no tests, routes, or UI (§4.1) | Yes, as written — 2026-08-30 |
| **2 — Run source** | The call site runs from the source the types came from; `method_id` allowed with a one-line warning; never mixed (§4.2) | Yes, as written — 2026-08-30 |
| **3 — No contracts artifact** | Signature from `explicit: true` template + bundle read; heuristic for by-ref / by-id until the `pipelex-mcp` follow-up lands (§4.3) | Yes, as written — 2026-08-30 |
| **4 — Write arm only** | Always `output_dir`, relative to the harness's launch directory; never ride content; stop on containment escape (§4.4) | Yes, as written — 2026-08-30 |
| **5 — Gate asymmetry** | TypeScript: reference `codegen-check.mjs` into the existing gate; Python: no gate, sidecar plus refresh, stated in the report (§4.5) | Yes, as written — 2026-08-30 |
| **6 — Sidecar** | `sources.json`, starter-compatible `sources` map plus `generator` / `method` / `target` / `pipe` (§4.6) | Yes, as written — 2026-08-30 |
| **7 — Wire-null helper** | Shared schema-guided `wireOutput` per TypeScript project until `L-260820-ee327d`, with a pre-ship re-check (§4.8) | Yes, as written — 2026-08-30 |
| **8 — `explicit: true`** | The plugin's one exception to the light-template pin, recorded in `docs/decisions.md` (§4.9) | Yes, as written — 2026-08-30 |
| **9 — Name** | `pipelex-integrate`, model-invocable, codebase-phrasing triggers (§4.11) | Yes, as written — 2026-08-30 |
| **10 — Family wiring** | Staleness notice in `pipelex-edit` / `pipelex-design`; one-line hand-off in `pipelex-design` / `pipelex-inputs` (§7) | Yes, as written — 2026-08-30 |
