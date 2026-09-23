# Classification — `pipelex-integrate`

Phase 2 of the size diet ([`plan.md`](plan.md), [`design.md`](design.md) box A). Every paragraph, bullet and table-row group of `templates/skills/pipelex-integrate/SKILL.md.j2` as it stood at `0883b2e` (the phase 1 tip this phase is stacked on), with its kind under the read-before-act rule and where it went. Line numbers are that version's. Read the rewrite against this table as a move: a row whose destination is the new `SKILL.md` names the section it landed in, a row that moved names the reference, and a row that left the shipped text names `docs/decisions.md` or the statement it duplicated.

The kinds are the design's — **guard**, **branch**, **stop**, **rationale** — plus **main path** for the steps themselves. "Duplicate" means the statement already lived in the named place, which now holds it alone.

## Behaviour changes

Box G allows a phase to change behaviour only by resolving a contradiction found while consolidating, and, in this phase, by the `cp` wording of the gate copy. These are all of them.

1. **The gate copy is a literal `cp` from the skill's directory, run from the project root.** Step 10 used to say to copy the linked `references/codegen-check.mjs` **verbatim** to `scripts/codegen-check.mjs`, which Mistral Vibe performed by reading the file and writing it back through the model's own output (phase 0's `facts.md`, section 4). It now reads `mkdir -p scripts && cp "{{ skill_dir }}/references/codegen-check.mjs" scripts/codegen-check.mjs`, and the same for `codegen_check.py`, with `skill_dir` rendering as `${CLAUDE_SKILL_DIR}` on Claude and as a `<skill-dir>` placeholder, defined in one sentence by the new `skill-dir.md.j2` partial, on Codex and Vibe. The `mkdir -p` is new: a `cp` into a missing `scripts/` fails, where the old wording left the model to create the directory.
2. **Refresh mode no longer contradicts step 4 about a lock with no sidecar.** Refresh mode said flatly that a directory holding a `codegen.lock` with no sidecar naming the method "is not this method's (step 4)", while step 4 itself carved out this method's own interrupted run, which leaves exactly that state. Stating each rule once resolved it for step 4's version: `references/refresh.md` now says such a directory "is governed by step 4's rule, with its exception for this method's own interrupted run".
3. **The rule that a `codegen` script must be read before it is believed is now met where the harness branch is taken.** Step 1 said "either of the first two [signals] decides", and `references/typescript.md`'s detection row — which the old skill pointed at from step 4, after step 1 had already decided — said to read a `package.json` `codegen` script before believing it, since `graphql-codegen` or a protobuf generator satisfies the name. The rule moved, unchanged in scope (a `package.json` script), into `references/harness.md`, read at step 1 before the branch is taken, and left the TypeScript row, which now points at the branch.

Not behaviour changes, but worth a reviewer's eye:

- **The language reference is read at step 1**, where it used to be pointed at from step 4 ("detection detail") and step 9 ("module templates"). Step 1 is where a bundle is placed, and where a packaged Python project wants it is the Python reference's to say, so the pointer moved to the moment it is first needed. Every run read the reference anyway.
- **The containment check sits at step 1.** The old step 6 already said "both inputs are known as soon as step 1 names the project, so do this reading there"; the rewrite puts the check where its own text said it belonged.

## The table

| Old lines | What it says | Kind | Destination |
| --- | --- | --- | --- |
| 1–11 | Frontmatter: name, description, the Claude tool list | main path | `SKILL.md` frontmatter, unchanged |
| 13 | The title | main path | `SKILL.md`, unchanged |
| 15 | What the skill does, and its selector forms | main path | `SKILL.md` opening line; the selector forms to step 1 |
| 17–23 | A numbered overview of the process | main path | deleted as a duplicate of steps 4 to 11 |
| 25 | Refresh mode is the common case; a project owning a harness keeps it | branch | the branch pointers of step 1 ("Before step 2, read your branch") |
| 27 | What this skill is not; one module per method plus one shared helper | main path | the "Not" line; the helper budget to step 9, where it is stated once; "no watch mode, no per-project harness" and "a user who wants more says so" deleted as implied by the scope |
| 29–31 | The tools required; never hand-write a generated file; never derive a signature from source when the verdict carries it | main path, guard | tool names deleted (each step names its tool); the first guard is a duplicate of the write-arm guard; the second is step 3's "never a signature derived from the source" |
| 33–36 | The shared MCP requirements, with the codegen 403 and the paywall | stop | the include, unchanged; the 403 kept in its suffix as "not a key problem"; what the 403's hint says to `docs/decisions.md`; the paywall deleted as a duplicate of the include's `config` stop, which surfaces every hint verbatim |
| 37 | `mthds_list_methods` is optional and resolves a named method | stop | the Requirements bullet |
| 41 | Mode: automatic, interactive confirms edits, pause only when ambiguous; state target, destination and generator in one line; branch on the structured verdict | main path | the Guards preamble; the one-line statement to step 4; the examples of ambiguity to step 1 (the monorepo question, the catalog id's say-so) and the Python reference's audience row; "never on transport" deleted as a duplicate of each step's "branch on the result" |
| 45 | The write arm, always; never write returned bytes yourself; why | guard, rationale | Guards; the reason is `docs/decisions.md`, "The method reaches the code" |
| 46 | Generated files are never edited, formatted or linted; why the exclusions come first | guard, rationale | Guards; the ordering to step 5 ("Do this before step 6"); the stamp reason is `docs/decisions.md` |
| 47 | One directory per method; the workshop reports orphans and never deletes; never delete or offer to clean up an orphan | guard, rationale | the orphan guard in Guards; one directory per method to step 4; what an orphan is to `references/orphans.md`; "non-current by design" is `docs/decisions.md`, "Orphans alone do not end the run" |
| 48 | Never generate from one source and run from another | guard | Guards |
| 49 | A project that owns a harness keeps it | guard | Guards |
| 50 | No wire-null helper; why | guard, rationale | Guards, with a half-sentence of reason; the rest is `docs/decisions.md`, "No wire-null helper" |
| 56 | Exactly one selector per tool call | main path | step 1 |
| 58 | Local files: every `.mthds` file beneath the directory; the path form; a bundle outside the project copied in and the user told; a packaged project's bundle moved into the package with `git mv` | main path, branch, rationale | step 1, with the shared `validate-call` include unchanged; why it is copied to `docs/decisions.md`; the packaged-project move to `references/python.md`'s "Packaged for distribution" row, read at step 1 |
| 59 | A published address; the tag is the pin; an untagged one is accepted and floats — say so, recommend the tag, proceed; why the gate cannot see it | main path, rationale | step 1; the reason is `docs/decisions.md`, "A published address without a tag" |
| 60 | A catalog id: unversioned, say so, recommend the source or an address, proceed only on the user's say-so; names resolve through `mthds_list_methods` | guard | step 1; the name resolution to the Requirements bullet |
| 62 | The project: the shared markers; several is a question; none offers scaffold | main path | step 1, with the `project-root` include unchanged |
| 64 | Harness detection: the signals, which decide and which corroborate | branch | the deciding signals and the pointer to step 1; the full list to `references/harness.md`, "Recognising one" |
| 66 | A sidecar naming the method means refresh mode | branch | the refresh pointer of step 1 |
| 70–72 | Call `mthds_validate`; the integrable verdict | main path | step 2 |
| 73 | Valid but not runnable, or pending signatures: STOP to `/pipelex-design`; why | stop, rationale | the stop table's first row; the reason deleted, the row says it |
| 74 | `is_valid: false` routes to design or edit; a by-id method is fixed where it is edited | stop | the stop table's first row; the by-id aside deleted as implied by the routing |
| 75 | Error classes: `config` per the requirements; `input_domain` at a selector in the tool's words, another org's id reading as a miss; `runtime` retried once | stop | `config` is the include; the selector error and `runtime` are stop rows; the org-scope aside deleted (the tool's own words are reported) |
| 79 (first half) | What `main_pipe` carries; record it | main path | step 3, condensed (the sidecar example shows what is recorded) |
| 79 (middle) | `pipe_ref` is namespaced and the run's `pipe_code` is not; nothing catches the confusion | guard, rationale | step 3, with a half-sentence of reason; the rest to `docs/decisions.md` |
| 79 (last) | Type and run against `main_pipe.pipe_ref`, which for a package is its `METHODS.toml` entry | main path, rationale | step 3 ("against the verdict's `main_pipe`"); the reason is `docs/decisions.md`, "What the integrate and scaffold dogfood changed" |
| 81 | The fallback when `main_pipe` is absent: its causes, the text summary as a second channel, the files source's `inputs_template` call, the by-ref and by-id stop | branch | `references/signature-fallback.md`; step 3 keeps the condition, the `pipelex_mcp` floor (which must reach a rendered skill) and the pointer; the stop table keeps "never guess the output concept" |
| 85 | State the target, destination and generator in one line; the target follows the audience | main path | step 4 |
| 87–91 | The target table | main path | step 4's table; its "Emits" column deleted as a duplicate of each language reference's "The generated tree" |
| 93 (a) | `pipelex` present with neither signal is one question; a JavaScript project without TypeScript is asked; field keys are snake_case | branch | duplicates of `references/python.md`'s audience row and `references/typescript.md`'s build row and generated-tree section, deleted |
| 93 (b) | The destination: one directory per method, the defaults, beside existing generated code, in the language's casing | main path | step 4; "beside existing generated code" is the language references' "Generated root" rows |
| 93 (c) | A directory holding a lock is this method's only when a sidecar names it; choose another, say why, the user overrules by naming the method | guard | step 4 |
| 93 (d) | The lock-without-sidecar left by this method's own interrupted run is regenerated in place; why | guard, rationale | step 4, in one sentence; the reason to `docs/decisions.md` |
| 93 (e) | Unsure whose a tree is: ask, never relocate silently, never clear it | guard | step 4 |
| 93 (f) | A harness-owned layout is a further exception; the generator is the write arm or the harness; detection detail in the references | branch | `references/harness.md`; the generator is stated in step 4's one line; the references' pointer moved to step 1 |
| 97 | The exclusions, the gate scripts, the type checker still covering the tree, not gitignored, before step 6, and why the script's entry goes in early | main path, guard, rationale | step 5; the script names to step 10 and the references; the reason for the script's early entry is a duplicate of both language references, deleted here |
| 101 (a) | Call `mthds_codegen` with `output_dir` relative to the workshop, never absolute | main path | step 6 |
| 101 (b) | Check containment before the call, resolving both sides; do it at step 1; say what is already written if met late; STOP and relaunch, on Vibe or register the workshop; never ride content, never a climbing path; never write into the workshop and move the tree across | guard, stop, rationale | the check and its guards to step 1; "met late" to the stop table's containment row; the lexical, symlink and macOS reasons and the reason against moving the tree to `docs/decisions.md`; "never ride content" is the write-arm guard; a climbing path is refused by the tool and reaches the same stop row |
| 105 | Written: `is_current: true`, empty `orphans[]`; artifacts carry `written_to`, never `content` | main path | step 6's first bullet; the `written_to` sentence deleted as covered by the write-arm guard |
| 106 | `is_valid: false` after step 2 | stop | the stop table's first row |
| 108 | A file the tool does not own: never delete, move or clear it, never offer to; choose another directory, before the call too | guard | step 6's third bullet; "the tree is byte-identical" deleted, the refusal says it |
| 109 | The containment hint | stop | the stop table's containment row |
| 110 | A partial write: once more with the same `output_dir`, then report | stop | the stop table's `runtime` row |
| 111 | Orphans non-empty and drifts empty: carry on; read off the two lists, never `is_current`; `drifts` present only when non-empty; never delete; the report's content; never claim an overwrite; truncated detection; why the asymmetry | main path, branch, guard, rationale | the condition, its reading and "carry on" to step 6's second bullet, stated once; never delete is the orphan guard; the report, the causes, the red gate, truncation and the overwrite denial to `references/orphans.md`; the asymmetry's reason is `docs/decisions.md`, "Orphans alone do not end the run" |
| 112 | Any other non-current result: report `drifts[]` verbatim and stop; never commit it | stop | the stop table's drift row |
| 116 | Write the unstamped sidecar beside the lock, the only state kept; why | main path, rationale | step 7; the reason is `docs/decisions.md`, "The method reaches the code" |
| 118–132 | The sidecar's JSON | main path | step 7, the `comment` text unchanged, the `pipe` object on one line and the hash placeholder shortened |
| 134 (a) | `method` as passed; paths from the project root; the `pipe` notation; `bundle_dir` is the call site's directory; `sources` hashes every file under it; why the directory is recorded; a by-ref source records neither | main path, rationale | step 7; the reason is `docs/decisions.md`, "The method reaches the code" |
| 134 (b) | A `method_ref` is recorded exactly as passed, absent tag included; why | guard, rationale | Guards, widened in the same sentence to cover a harness's manifest (old line 200); the reason is `docs/decisions.md`, "A published address without a tag" |
| 134 (c) | Hash the raw bytes, with a command per platform | main path | step 7, with `shasum -a 256`; the other commands deleted as equivalents |
| 138 | Dependencies and their floors, an older pin raised and reported; what each floor carries; `python-structures` already has `pipelex`; state and confirm | main path, rationale | step 8; the floors' meaning is the comments of `[vars.floors]`, pointed at from `docs/decisions.md`; the `python-structures` aside deleted (step 8 adds nothing for it); confirmation to the Guards preamble |
| 142 (a) | One module per method, where the project keeps its layer; its shape; it loads every `.mthds` file from `bundle_dir`; the selector; the lifecycle call; narrowing through the binder or model | main path, guard | step 9 keeps the placement and the whole-bundle load; the shape, the lifecycle call and the narrowing are the language references' templates, already there |
| 142 (b) | Narrow by multiplicity: a list output arrives in its `items` envelope; the code; nothing in the tree names it; `fixed`'s `item_count`; the type checker cannot catch it | guard, branch | step 9 keeps the guard with a half-sentence of reason; the code, the unnamed envelope, `item_count` and the type checker to "A list output is narrowed through its envelope" in both language references |
| 142 (c) | Credentials come from the SDK's defaults; the module never reads them | guard | step 9 |
| 144 | Why the whole results come back; name the fields the method produces | branch | both language references' results sections; "name the fields the method actually produces" added there |
| 146 | Where the SDK's pages are published, which address to write down, those pages and no others | branch | duplicate of `references/typescript.md`, "Where those pages are", which gained "those pages and no others"; the Python half is `references/python.md` |
| 148–152 | What each results field carries | branch | duplicates of `references/typescript.md`, "What the results carry", deleted |
| 154 | The Python twins, and the report naming them from the Python pages | branch | duplicate of `references/python.md`, which gained the report sentence |
| 156–165 | The parameter-type table | branch | duplicate of both references' "Parameter types from the signature", deleted |
| 167 (a) | Exactly one shared helper, the client factory, or the project's own; no second one, and why | guard, rationale | step 9, stated once; reusing an existing client is the references'; the struck helper's reason to `docs/decisions.md` |
| 167 (b) | The module does not upload; its docstring points at `prepareInputs` with the SDK's warning | guard | step 9; the warning's text is the templates' |
| 167 (c) | Sync wrapper for a synchronous Python project; follow conventions; let typed errors propagate | branch | `references/python.md` (wrapper, typed errors); "follow the project's conventions" added to both references |
| 171 | The TypeScript gate: copy verbatim, never format, register `codegen:check`, extend the existing gate, what it checks and its exit codes, no verdict never drift, where it runs | main path, stop | step 10's `cp` line (behaviour change 1) and its wiring sentence; the rest is `references/typescript.md`, "The offline gate", already there |
| 172 | The Python gate: the same, in the project's own environment, never adding `pipelex` | main path | step 10's `cp` line and wiring sentence; the rest is `references/python.md`, "The offline gate", already there |
| 173 | `python-structures`: `pipelex codegen check` | main path | step 10's wiring sentence; the detail is `references/python.md` |
| 175 | No gate refuses an untagged address or sees it move | rationale | `docs/decisions.md`, "A published address without a tag"; step 12 keeps "which no gate sees move" |
| 179 | Format only your files; type checker; the gate; your failures are yours, the tree's are reported; a gate red over orphans is not yours to fix; deleting one is forbidden; a dedicated directory is the fix | main path, guard | step 11; the tree's failures are the Guards' second bullet; the orphan clause names the orphan guard and `references/orphans.md`, which carries the fix |
| 183 | The report: what, where, target, signature, tooling, orphans, the gate, the catalog's and the floating address's caveats, how to refresh, the hand-off | main path | step 12; the orphans' content to `references/orphans.md`; the address's record is the Guards' `method_ref` bullet |
| 187 | Refresh mode's entry and principle | branch | `references/refresh.md`, opening |
| 189–191 | Refresh mode's table | branch | `references/refresh.md`, verbatim |
| 193 (a) | One call; read content hashes, not the fingerprint; a pure restamp | branch | `references/refresh.md`, "The regeneration" |
| 193 (b) | Orphans do not end a refresh, restated with its report | branch | `references/refresh.md` names step 6's branching; the restatement deleted as a duplicate of step 6 and `references/orphans.md` |
| 193 (c) | Any other non-current result ends the refresh | branch | `references/refresh.md` |
| 193 (d) | The call site's triggers, the callers, the second type check, the breaking-change report | branch | `references/refresh.md`, "The call site and its callers", verbatim |
| 193 (e) | The sidecar rewritten last | branch | `references/refresh.md` |
| 193 (f) | A lock with no sidecar naming the method is not this method's | branch | `references/refresh.md`, now naming step 4's rule with its exception (behaviour change 2) |
| 193 (g) | A harness-owned layout keeps no sidecar | branch | `references/refresh.md`, pointing at the harness branch |
| 197 | Which projects own a harness, and why the skill defers | branch | `references/harness.md`, opening |
| 199–204 | The harness path: `make add-method` with a bundle, placing the method, the manifest's address as passed, the generator, the call site, the skipped steps, refresh | branch, guard | `references/harness.md`, "What changes"; the manifest's guard is the Guards' `method_ref` bullet, which the reference names |
| 206 | The harness's generator cannot run: write into its own layout; the one destination step 4 does not govern | branch, guard | `references/harness.md`, "When the harness's generator cannot run"; "never a second layout" is the Guards' harness bullet |
| 212 | A required tool is absent | stop | duplicate of the include, deleted |
| 213–214 | `config`, the 403, the paywall | stop | the include and its suffix (see lines 33–36) |
| 215–216 | Invalid; not runnable | stop | the stop table's first row, merged |
| 217 | Containment escape at `output_dir` | stop | the stop table's containment row |
| 218 | The project outside the workshop, before generating | guard | duplicate of step 1's containment guard, deleted |
| 219 | A file the tool does not own | guard | duplicate of step 6's third bullet, deleted |
| 220 | `input_domain` at a selector | stop | the stop table |
| 221 | `runtime`, retryable | stop | the stop table's `runtime` row, merged with step 2's retry |
| 222 | Orphans and no drift | main path | duplicate of step 6's second bullet and `references/orphans.md`, deleted |
| 223 | Any other non-current result | stop | the stop table's drift row |
| 224 | No `main_pipe` on a by-ref or by-id source: the text summary first, the causes and their remedies | stop, branch | the stop table's signature row; the reading and the remedies to `references/signature-fallback.md` |
| 225 | The type check fails in your code | stop | duplicate of step 11, deleted |
| 226 | The TypeScript gate exits 2 over its SDK | stop | `references/gate-failures.md`, the floor stated as "step 8's floor" rather than a number |
| 227 | A gate exits 2 because a check threw | stop | `references/gate-failures.md` |
| 228 | The Python gate exits 2 over its SDK, or while loading | stop | `references/gate-failures.md`, a row per cause, with "never swap for `pipelex codegen check`" |
| 229 | `stale-source` for an added file or a missing `bundle_dir`: refresh; never add a hash by hand | stop, guard | the stop table's `stale-source` row, with a half-sentence of reason |
| 230 | `TS2835` in your own module | stop | the stop table's `TS2835` row; the detail is `references/typescript.md`, already there |
| 231 | `TS2835` in the generated `binder.ts`: the emitter's defect, never patched, never dropped from the type checker, the report says it cannot execute, `moduleResolution` is the user's | stop, guard | the stop table's `TS2835` row; the detail merged into `references/typescript.md`'s "Known defect"; never patching it is the Guards' second bullet |
| 232 | `mthds_list_methods` absent | stop | duplicate of the Requirements bullet, deleted |
| 236–240 | The reference list | main path | the References index, each entry with the condition that sends the model there |

## What the rewrite adds

Nothing a reviewer should read as new behaviour beyond the changes above: the pointers at each decision point, the "Stops" and "Guards" headings of box B's shape, the `skill-dir.md.j2` include before step 10's first use of `{{ skill_dir }}`, and, in each new reference, an opening sentence naming the condition that sends the model there.
