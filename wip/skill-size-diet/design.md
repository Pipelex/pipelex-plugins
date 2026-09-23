---
status: active
item: L-260923-a9bdfe
---

# Design — the skill size diet

**Written 2026-09-23**, for the epic `L-260923-a9bdfe`, which superseded the parked item `L-260921-7918a6` once the boxes were ratified, against `pipelex-plugins` at `fd26a2c` (the 0.7.0 release). Box N of the workspace-root `wip/plugin-skills-gaps/design.md` parked this work as a campaign of its own that starts with a design and not with an edit; this is that design. It measures the skills, answers the question the item puts first, proposes the shape a skill takes and the rules that keep it there, and ends with decision boxes for ratification. Every box was ratified on 2026-09-23 in an interview, one question per box; Louis amended box E (a template's programs live in the template, and the starters leave the scaffold skill) and, as a consequence, box I's order, and both amendments are written into their boxes. [`plan.md`](plan.md) is the implementation tracker. The neighbours are the behavioural evals parked beside this item (`L-260921-479a8e`) and the deferrals the plugin-skills-gaps campaign assigned to this one, listed in its `plan.md`. File and line references were accurate on the writing date; verify them before implementing.

## 1. The brief

From the item, in box N's words: each review finding was folded into its step as a bolded caveat with its full rationale, so the main path is hard to find. The remedy is progressive disclosure: the main path and a table of stops in `SKILL.md`, the rationale and the rare branches in `references/` files read when a branch is taken, and scaffold's shell programs shipped as scripts that CI executes.

And the question it asks first: **which sentences must a model have read before it acts, as opposed to those it needs only when a branch is taken, since a caveat moved to a reference is a caveat that may not be read.** Section 3 answers it, and every other decision follows from the answer.

## 2. What the measurement found

**Sizes, rendered for Claude on 2026-09-23.** Tokens are estimated at four characters each; section 8 asks for a calibration.

| Skill | Words | Characters | About tokens | Shipped references |
| --- | --- | --- | --- | --- |
| `pipelex-scaffold` | 10779 | 63683 | 15900 | `starters.md`, `initializers.md` |
| `pipelex-integrate` | 9739 | 60767 | 15200 | `typescript.md`, `python.md`, two gate scripts |
| `pipelex-inputs` | 6433 | 42117 | 10500 | none |
| `pipelex-design` | 4883 | 32849 | 8200 | `writing-mthds.md`, read before every write |
| `pipelex-catalog` | 3641 | 21502 | 5400 | none |
| `pipelex-run` | 3457 | 20643 | 5200 | none |
| `pipelex-explain` | 3184 | 18536 | 4600 | none |
| `pipelex-synthetic-inputs` | 2594 | 16011 | 4000 | `pdf.md`, `png.md`, `office.md` |
| `pipelex-organize` | 2567 | 15997 | 4000 | none |
| `pipelex-edit` | 2259 | 14167 | 3500 | none |

**Every skill grew in the two days since the item was filed**, and the skills the plugin-skills-gaps campaign wrote under the rule "main path in `SKILL.md`, rationale in references" ship no reference file at all: `pipelex-run`, `pipelex-catalog` and `pipelex-explain` are each over three thousand words. The rule was adopted as a sentence and not as a shape, so nothing held it. That campaign's own tracker records the same thing for `pipelex-inputs`, which was meant to shrink by a fifth and did not.

**Compaction truncates a skill, and the large ones lose what protects the user.** Claude Code's documentation, verbatim: *"When the conversation is summarized to free context, Claude Code re-attaches the most recent invocation of each skill after the summary, keeping the first 5,000 tokens of each. Re-attached skills share a combined budget of 25,000 tokens."* A skill longer than that is carried forward as its head alone, until someone re-invokes it. Measured by where roughly 16,000 to 20,000 characters fall:

- `pipelex-scaffold` keeps its branch table, its mode and its prerequisites, and is cut inside the acquisition step. Lost: the pristine commit, `make create`, the whole env-file step with its rule that a key is never printed or read back, the loopback check on the dev server, the report and the failure table.
- `pipelex-integrate` keeps its rules and steps 1 to 4 or 5. Lost: generation with its orphan handling, the sidecar, the call site, the gate, refresh mode, the harness section and the failure table.
- `pipelex-inputs` is cut inside the user-data strategy. Lost: the whole prepare procedure, its file-fidelity rule and the conditions for offering a run.
- `pipelex-design` keeps direct construction and loses re-entry and the runnable gate.

A session that designs, prepares inputs and runs before it integrates is exactly the session that compacts in the middle of `pipelex-integrate`.

**Where the words go.** In `pipelex-scaffold`, roughly two fifths of the text sits in the sections that carry a shell program — the method app's acquisition, the starter's two acquisitions, the check of who owns the repository, the env-file write, the dev-server start — and most of that is a line-by-line defence of the program: why `|| exit`, why the temporary path is resolved first, why `cp -R` and never `mv *`, why three traps. Those defences exist because the model types the program. The unit tests already extract those blocks from the template and execute them (`tests/unit/test_pipelex_scaffold_skill.py:153`), so the programs are proven; what costs is that the model re-reads their defences and retypes them on every run.

**A rule stated in several places drifts, and here it already has.** `pipelex-integrate` states what to do with orphans in its rules, in step 6, step 11, step 12, refresh mode and the failure table (`templates/skills/pipelex-integrate/SKILL.md.j2:47`, `:111`, `:179`, `:183`, `:193`, `:222`); five open ledger items are about that logic. `pipelex-inputs` contradicts itself: its prepare step leaves `inputs.json` untouched (`templates/skills/pipelex-inputs/SKILL.md.j2:314`), while its value-shapes section and two of its examples still say preparation rewrites it (`:380`, `:414`, `:460`). That ships in 0.7.0 and is filed as `L-260922-e01c73`. The plugin-skills-gaps tracker handed this campaign more of the same: the path-form rule has three sources, design and integrate each list the project markers, the stale-types notice has three wordings, the `runs/` exclusion belongs in the shared submission convention, and the rendered frontmatter carries a stray blank line.

**What the harness gives.** Claude Code loads a skill's other files only when the model reads or runs them. It substitutes `${CLAUDE_SKILL_DIR}` in a skill's body and in the Bash rules of its `allowed-tools`, and documents bundled scripts invoked by that path as the pattern for code a skill runs. It recommends keeping `SKILL.md` under 500 lines, which says little here, where a line is a paragraph. The build copies a skill's `references/` directory into every target and nothing else beside it (`scripts/gen_skill_docs.py:510`).

## 3. The question first: what a model must read before it acts

Ask of every sentence: **if the model never read it, what is the worst that happens, and what would tell it?** There are four answers, and each gives the sentence a home.

| If it is skipped | Kind | Home |
| --- | --- | --- |
| something is lost that cannot be recovered, something leaves the machine, credit is spent, or the result is wrong and nothing later says so | **guard** | `SKILL.md`, once, in one sentence, at the step it governs |
| the model does the wrong thing on a path it could have recognised before taking it | **branch** | a reference; `SKILL.md` keeps the condition and a pointer that must be followed before acting |
| a verdict, an exit code or a refusal says so | **stop** | one row of the stop table; a recovery longer than a line goes to the branch's reference |
| nothing happens; a maintainer would want to know why | **rationale** | `docs/decisions.md`, never shipped |

That is the answer to the item's worry. **A caveat moves only when the need for it announces itself**: either by a condition the model can observe before it acts, which is where the pointer sits, or by a result that tells it after an act that did no harm. **A silent caveat never moves.** The orphan rule shows the difference: "never delete an orphan" is a guard, because the deletion cannot be undone and nothing reports it, so it stays; how to report orphans is needed only when `orphans[]` comes back non-empty, which the result says, so it moves.

Four consequences.

- **A pointer is an instruction at the decision point**, never only a line in a closing list: "On a starter, read `references/starter.md` before running anything on this branch." A pointer placed after the moment it matters is a caveat that will not be read.
- **References are one level deep.** A reference never sends the model to another reference, so one read is enough to take a branch.
- **Each statement lives in one place** — a guard, a step, or a stop row — and every other place names it rather than restating it. That is what stops the drift above.
- **A half-sentence of rationale may stay** where, without it, a model would plausibly "improve" a rule into the harm it prevents. When the rule belongs to a script, that half-sentence lives in the script instead.

## 4. Decisions

### A. The read-before-act rule

The test and the four homes of section 3 are the rule every rewrite in this campaign applies, sentence by sentence, and the rule the repository keeps afterwards: `CLAUDE.md` and `docs/build-targets.md` state it for whoever writes the next skill. **Recommendation: adopt as written.**

### B. The shape of a `SKILL.md`

In this order: the frontmatter; what the skill does and what it is not, in a few lines; the requirements, in three lines (box F); the guards that span several steps, each in one sentence; the main path as numbered steps in the imperative, each carrying its own guards and the pointers of its branches; the stop table, one row per condition and one line per row; and a closing index of references, each with the condition that sends the model there. A step that needs more than a few short paragraphs is holding a branch or a rationale that belongs elsewhere. **Recommendation: adopt.**

### C. A ceiling that survives compaction

Every rendered `SKILL.md`, on every target, fits whole in the 5,000 tokens Claude Code keeps after a compaction, so no skill loses its tail. `make check` enforces it as a character ceiling on the rendered output, because characters are what a check can count exactly; the ceiling is set in phase 0 by counting the tokens of rendered skills, and **16,000 characters is the proposed starting value**, which is 4,000 tokens at four characters each and stays under 5,000 only while the Markdown averages at least 3.2 characters per token. At three it would be 5,333 tokens, and the safe value 15,000. So phase 0 derives the ceiling rather than confirming the proposal: 5,000 times the lowest characters-per-token ratio measured across every rendered `SKILL.md` on every target, less a stated margin. Every skill from `pipelex-synthetic-inputs` up in the table of section 2 is over 16,000 today, and a lower ceiling brings `pipelex-organize` in with them. The check reports without failing until the last phase brings every skill under, then fails. References carry no ceiling, but each is sized to one branch, since a branch reads its reference whole. The ceiling applies to every skill, not only the three the item names, because the rule's absence is what let the campaign's new skills grow. **Recommendation: adopt, with the value calibrated in phase 0.**

### D. Rationale lives in `docs/decisions.md`

A maintainer needs to know why the lone-`.git` rule is worded as one entry by name, and a model running the skill does not; `docs/decisions.md` already carries much of that reasoning, often twice over with the skill. The rewrite moves every rationale paragraph there, merges it with what that file already says, and ships none of it. The alternatives are a shipped `why.md` per skill, which costs nothing until read but invites a model to read it on the main path, and Jinja comments beside the rule, which keep the reason next to the text but split the record across templates. **Recommendation: `docs/decisions.md`.**

### E. A procedure whose text is its correctness ships as a script

A shell chain, a hash over files, a comparison of resolved paths: when the procedure is correct only if it runs exactly as written, the skill ships it as a script under `skills/<skill>/scripts/`, runs it by path with arguments, and never has the model retype it. Its defences become comments and tests. What a script owes the skill:

- It takes every value as an argument or from the environment, so the placeholder-quoting rules leave the skill text.
- It prints one line that opens with a stable verdict word (`created`, `refused: not-empty`, `listening`, `refused: not-loopback`), which is what the stop table keys on. The exit code is presentation, as elsewhere in this workspace.
- It never prints a secret. The env-file script reads the key from the environment and reports `filled`, `kept` or `empty`, and the plane as `production` or `other`.
- It is executed by the unit suite directly, which replaces extracting blocks from the template, so the programs stay as proven as they are today.

In scope: scaffold's chains, which are the method app's acquisition, the starter's acquisition, the repository-ownership check, the `make create` run with its log and warnings, the env-file write, and the dev-server start with its loopback and holder checks. **One behaviour changes deliberately:** the starter's two local recipes become one, the "acquire beside and copy in" form, which serves a missing, an empty and a lone-`.git` directory alike and never runs `rm -rf` under the destination. The end state is the one the default recipe reaches today. Candidates judged in their own phase against the same test, not committed here: integrate's containment check and the hashes it writes into the sidecar. The MCP-backed skills can rely on Node, since the workshop is spawned with `npx`.

The build copies `scripts/` beside `references/`, executable bits included, and the freshness check covers both. The skill names a script as `${CLAUDE_SKILL_DIR}/scripts/<name>` on Claude, and on Codex and Vibe by the directory the model read `SKILL.md` from, through one template variable; section 8 asks whether the second form works. **Recommendation: adopt, scaffold in scope, integrate's candidates decided in its phase.**

**Amended at ratification, 2026-09-23.** Louis ratified scripts, then asked whether the method app's code needs to be in the plugin at all when the template lives in `pipelex-method-apps`, and ruled on two follow-ups.

- **A program that belongs to a template lives in the template.** The method-app family publishes an initializer (`npm create pipelex-method-app@latest <dir> -- --method '<method>'`, name to be settled by its design) that acquires `webapp-js/` and runs the copy's own `make create`, and the template gains a target (`make serve`) that starts the dev server detached on loopback and proves the page answers. Scaffold's method-app path becomes those two commands, and the plugin keeps no copy of the template's layout. Filed as `L-260922-12f302` against `pipelex-method-apps`; scaffold's phase waits on it. The plugin's own scripts are what no template can own: branch B's repository test and pristine commit, and its env-file write.
- **The starters leave the skill.** Louis: "we use the method app for scaffolding now, we're not using the starter anymore". A TypeScript web app goes to the method app; every other project — Python of any shape, a TypeScript CLI, service or library — goes to the language's own initializer and then to `/pipelex-integrate`. When the family ships a Python template (`L-260922-2e3997`, filed the same day, since the family had none, and now carried by the `cli-python` campaign, epic `L-260923-71f4a9`), scaffold routes a Python CLI to it through `L-260923-7001f2`, which lands after the starter path's deletion. The starter path is deleted rather than moved to a reference, which makes the starter-recipe merge above moot.

### F. The shared blocks shrink, and the inherited deferrals land here

The `mcp-requirements` include is 300 to 450 words in each of eight skills. It becomes its two stop conditions, an absent tool and a `config`-class error surfaced verbatim, plus a pointer to a shared reference rendered per target, `shared/credentials.md`, read when that error is about the key. The deferrals the plugin-skills-gaps campaign assigned to this one land with it: one statement of the path form, one include for the project markers that design and integrate share, one wording of the stale-types notice, the `runs/` exclusion in the shared submission convention, and the frontmatter's stray blank line. **Recommendation: adopt, as the first phase.**

### G. A diet phase moves text and changes no behaviour

A reviewer must be able to read a phase as a move. So a phase changes behaviour in these ways only, each named in its pull request and its plan entry: a contradiction found while consolidating is resolved, by choosing the statement that matches the ratified design; the deferrals of box F; and, in scaffold's phase, what box E's amendment rules — the method app driven through the family's own commands, and the starter path deleted. Open ledger bugs against a skill are not folded into its phase. An urgent one lands whenever it is ready and the phase rebases onto it; the rest wait for the phase and land afterwards in the new shape, where each becomes one edit instead of several. `L-260922-e01c73` is the exception worth taking first: it is a few sentences, and it is shipped. **Recommendation: adopt.**

### H. Proving that a moved caveat is still read

Three layers, none of which needs the eval suite that `L-260921-479a8e` parks.

- **A guard registry per skill.** Each guard has a canonical sentence, and the unit suite asserts it appears exactly once in the rendered `SKILL.md` of every target, and not in a reference. That tests presence and uniqueness together, as `TestSharedSkillIncludes` already does for the shared blocks.
- **Links that resolve both ways.** `make check` fails when a pointer names a reference or a script that does not exist, and when a shipped reference or script is named by nothing.
- **Smoke sessions at the end of each phase.** A fresh Claude Code session walks the skill's main path and each of its branches, and one Codex session walks the main path; the transcript must show the reference read on its branch and not on the main path. The scenarios are written in the shape the parked eval suite will take, so they become its first scenarios.

**Recommendation: adopt; the evals stay parked and are not a prerequisite.**

### I. Scope and order

Every skill ends under the ceiling; the four largest are rewritten, and the rest are trimmed.

0. **Facts**: the questions of section 8, answered before any template moves.
1. **The shared blocks and the machinery**: box F, the ceiling check in report mode, the guard registry, the link check, and the build copying `scripts/`.
2. **`pipelex-integrate`**, the most invoked of the large skills and the one most open bugs wait on.
3. **`pipelex-inputs`**.
4. **`pipelex-design`**.
5. **`pipelex-scaffold`**, in two steps: the starter path's deletion and branch B's scripts, which wait on nothing; then the method-app path, once the family's initializer and serve target (`L-260922-12f302`) have shipped.
6. **The rest** — `pipelex-catalog`, `pipelex-run`, `pipelex-explain`, `pipelex-synthetic-inputs` — trimmed under the ceiling, which then fails instead of reporting.

The diet ships as ordinary releases, and no release waits for the whole campaign. **Recommendation: adopt this order.**

**Amended at ratification, 2026-09-23.** The first draft put scaffold second, as the pilot that would prove scripts on every target. Box E's amendment moved the method app's programs into the template family, which leaves scaffold with branch B's scripts alone and puts its method-app path behind `L-260922-12f302`, so the pilot's role passes to phase 0's facts and phase 1's machinery, and integrate leads.

## 5. What the four large skills become

A sketch for the plan to refine, not a commitment of wording.

- **`pipelex-scaffold`** keeps the two branches and how to choose between them, the method app's path as the family's own commands (the initializer, then the serve target of box E's amendment), its guards (never write into a directory that holds anything but a lone `.git`, never print or read back a key, `gh repo create` always confirms, never report a URL that did not answer, never start a server bound beyond this machine), and a stop table keyed on the verdicts those commands and its own scripts print. Branch B keeps its main path as script calls (the repository test and pristine commit, the env-file write) and moves its per-framework detail into the existing `references/initializers.md`; the GitHub forms and the version-manager activation move to their own references, each read when its condition is met; every defence of a program line goes to its script or to `docs/decisions.md`. The starter path is deleted, with `references/starters.md`.
- **`pipelex-integrate`** keeps the three selectors, its rules each stated once, steps 1 to 12 as short imperatives, the target table, the sidecar's shape and a stop table. It keeps one guard that the rule might otherwise move: a list output is narrowed through its `items` envelope, because getting it wrong type-checks, passes the gate and fails only on a real run. It moves the signature fallback when `main_pipe` is absent, refresh mode, the harness section, the report on orphans, the field-by-field account of what the returned results carry, and the long gate-failure rows to references, and the narrowing code to the language references that already hold the call-site templates.
- **`pipelex-inputs`** keeps the three target forms, the choice of strategy, the template call and its verdicts, the path rule of `inputs.json`, the core of preparation (say what leaves the machine, send absolute paths, send the exact file and never a derived one, write `inputs.prepared.json`, never rewrite `inputs.json`) and the conditions for offering a run. It moves the synthetic and user-data detail, the size-limit failure, the stale-workshop refusal met only by an address, and the worked examples to references.
- **`pipelex-design`** keeps the contract capture, the choice of mode, direct construction, the validation verdicts, the runnable gate and delivery. It moves stepwise construction and re-entry to references, since each is entered on a condition the skill decides first, and the catalog-id resolution to the include design, edit and organize already share.

## 6. Out of scope, and what stands beside this

- **Behaviour.** Box G's three exceptions aside, nothing a skill does changes; the open bugs land after their skill's phase.
- **The language references.** `pipelex-design` requires reading `references/writing-mthds.md` before every write, so that file is part of design's load in practice. Whether to split it by pipe type is a question for design's phase, not a commitment here.
- **The skill descriptions.** Every session pays for all of them in the skill listing whether a skill runs or not, which is the context-diet problem and not this one. They are worth their own item.
- **The behavioural evals** (`L-260921-479a8e`), which box H feeds and does not wait for.
- **The workshop's server instructions** and anything else outside this repository.

## 7. Where the campaign lives

In `pipelex-plugins/wip/skill-size-diet/`, since only this repository changes. The design goes to `dev` with the first phase or on its own, as Louis prefers.

## 8. Facts to verify in phase 0

These are questions a live session or a count answers, not decisions. On Codex and on Vibe: how the model learns a skill's directory, whether a relative link to `references/` resolves, and whether a script under `scripts/` can be run from where the plugin is installed — Codex runs plugins from a cache copy — with its executable bit intact. Whether either harness carries skills across its own compaction, and within what budget. The token count of every rendered skill, whose lowest characters-per-token ratio sets box C's ceiling. Whether `pipelex-integrate`'s existing instruction to copy `references/codegen-check.mjs` already works on all three targets, which would answer part of the first question.

## Decision boxes for ratification

| Box | Ruling | Ratified? |
| --- | --- | --- |
| **A — the read-before-act rule** | a sentence stays in `SKILL.md` when skipping it loses something unrecoverable, sends something off the machine, spends credit or is silently wrong; a branch moves behind a pointer placed at its condition; a stop is a row; rationale leaves the shipped text (§3, §4 A) | Yes, as written — 2026-09-23 |
| **B — the shape** | frontmatter, what it is, requirements in three lines, the guards that span steps, the main path with its own guards and pointers, the stop table, the reference index (§4 B) | Yes, as written — 2026-09-23 |
| **C — a ceiling that survives compaction** | every rendered `SKILL.md` fits in the 5,000 tokens kept after a compaction; `make check` enforces a character ceiling calibrated in phase 0, starting at 16,000; it reports until the last phase, then fails (§4 C) | Yes, as written — 2026-09-23 |
| **D — where rationale goes** | `docs/decisions.md`, merged with what it already says; nothing of it shipped (§4 D) | Yes, as written — 2026-09-23 |
| **E — scripts** | a procedure whose text is its correctness ships under `scripts/`, runs by path with arguments, prints a verdict word and never a secret, and is executed by the unit suite; scaffold's chains in scope, with the starter's two recipes merged into the safer one; integrate's candidates decided in its phase (§4 E) | Amended — 2026-09-23: a template's programs live in the template — the method-app family publishes an initializer and a serve target (`L-260922-12f302`), and the plugin scripts only what no template owns; the starters leave scaffold, every non-web-app project goes to the ecosystem's initializer until the family has a Python template (`L-260922-2e3997`) |
| **F — shared blocks first** | the requirements include shrinks to its two stops and a per-target credentials reference; the deferrals the gaps campaign assigned here land with it (§4 F) | Yes, as written — 2026-09-23 |
| **G — a phase is a move** | no behaviour changes but resolved contradictions, box F's deferrals and, in scaffold, box E's amendment; open bugs land after their skill's phase, the urgent ones whenever ready; `L-260922-e01c73` first (§4 G) | Yes, as written — 2026-09-23 |
| **H — proof** | a guard registry asserting each guard exactly once in `SKILL.md`, links checked both ways, smoke sessions per phase written as the evals' first scenarios; evals stay parked (§4 H) | Yes, as written — 2026-09-23 |
| **I — scope and order** | every skill under the ceiling; facts, shared blocks and machinery, then integrate, inputs, design, scaffold in two steps (the starter deletion and branch B, then the method-app path once `L-260922-12f302` ships), then the rest; ordinary releases along the way (§4 I) | Amended — 2026-09-23: scaffold is no longer the pilot; integrate leads, scaffold follows design in two steps |
