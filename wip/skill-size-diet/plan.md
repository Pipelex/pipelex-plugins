---
status: active
item: L-260923-a9bdfe
---

# Plan — the skill size diet

The implementation tracker for [`design.md`](design.md), whose boxes were all ratified on 2026-09-23. The epic is `L-260923-a9bdfe`, which superseded the parked item `L-260921-7918a6`. Each phase below names its ledger item beside its heading once filed; the order between them is recorded as `blocked_by` on the later item. Every phase is a move in the sense of box G: it changes no behaviour beyond what box G lists, and its pull request names each exception.

## Handoff from the ratifying session — 2026-09-23

- **Done.** The design was written from a measurement at `fd26a2c` and every box ratified in an interview (box E amended, box I's order with it). The epic `L-260923-a9bdfe` superseded `L-260921-7918a6`, and the phase items below are filed under it with their order in `blocked_by`. Filed on the way: `L-260922-e01c73` (the inputs contradiction), `L-260922-2e3997` (the Python template gap, since carried by the `cli-python` epic `L-260923-71f4a9`), `L-260922-12f302` (the method-app family's initializer and serve target). `L-260923-7001f2`, which routes a Python CLI to `cli-python`, was noted with the ratified rulings and now waits on phase 5a.
- **The documents travel in PR #48** (`docs/Skill-size-diet-design`, worktree `_pipelex-plugins--skill-size-diet` at the workspace root). The design commits are `daa095a` (draft) and `832136b` (ratified, with this plan). Landing it takes a recorded `/rev` pass, then `/ledger-land`; the PR body says `Advances L-260923-a9bdfe`.
- **Next.** Louis starts phase 0 himself, in a new session: `wt add --for L-260923-75fb17`, then `ledger claim L-260923-75fb17 --renew` from inside it. If PR #48 has not landed, branch from `docs/Skill-size-diet-design` so the documents are there. `L-260922-e01c73` can land at any moment before phase 0.
- **Open questions.** None of Louis's are pending. What remains open is the facts list of phase 0 (design section 8), above all whether Codex and Vibe can locate and run a skill's `scripts/`, which box E rests on outside Claude.

## Standing rules for every phase

- **Classify before moving.** Each skill phase starts with a classification of the skill's text under box A — guard, branch, stop or rationale — written beside this plan as `classification-<skill>.md`, one row per paragraph with its destination. The pull request is reviewed against it, which is what makes a move readable as a move.
- **The shape is box B's**, and the rendered `SKILL.md` lands under the ceiling of box C on every target.
- **Rationale goes to `docs/decisions.md`** (box D), merged with what that file already says about the same rule.
- **Guards join the registry** (box H) in the same change that places them, and every pointer and reference is covered by the link check.
- **Smoke sessions close the phase** (box H): a fresh Claude Code session walks the main path and each branch, and one Codex session walks the main path. The plan records each scenario, the session id and whether the reference was read on its branch and not on the main path. Scenarios are written in the shape the parked eval suite (`L-260921-479a8e`) will take.
- **Open bugs against the skill wait for its phase** and land afterwards in the new shape; an urgent one lands whenever it is ready and the phase rebases onto it (box G).
- **Every phase ends with `/rev`**, and its release is an ordinary one.

## Before phase 0

- [ ] `L-260922-e01c73` lands: the three sentences of `pipelex-inputs` that still say preparation rewrites `inputs.json`, and the haiku example's directory. It is shipped and small, so it does not wait for the inputs phase (box G).

## Phase 0 — facts · `L-260923-75fb17`

The questions of design section 8, answered with evidence recorded here before any template moves.

- [x] On Codex: how the model learns a skill's directory; whether a relative link to `references/` resolves; whether a script under `scripts/` runs from the plugin's cache copy with its executable bit intact. Answered in a live session with a throwaway script in a local build. **Yes to all three** ([`facts.md`](facts.md) §3): the invoked skill carries its absolute path, a relative link resolves, and the script runs with its bit — with the skill's directory as its working directory.
- [x] The same three on Mistral Vibe. **Yes to all three once the skill is loaded** ([`facts.md`](facts.md) §4): Vibe states the base directory and runs skills in place; nothing is substituted in a body. Found on the way: Vibe drops `pipelex-design` and `pipelex-scaffold`, whose descriptions are not strict YAML — `L-260923-dfb8ee`, fixed on its own in #50 (`d3445f5`).
- [x] Whether Codex or Vibe carries an invoked skill across its own compaction, and within what budget. **Neither does, at any size**; both keep the path so the model can read the file again ([`facts.md`](facts.md) §3–4).
- [x] Whether `pipelex-integrate`'s instruction to copy `references/codegen-check.mjs` works on all three targets today. **On Claude and Codex, as a `cp`; on Vibe the model read and rewrote the file rather than copying it**, so the instruction must name a `cp` from the skill's directory (integrate's phase).
- [x] The token count of every rendered `SKILL.md` on every target, taken with the token-counting endpoint, which sets box C's character ceiling: 5,000 times the lowest characters-per-token ratio measured, less a stated margin. The proposed 16,000 holds only if no skill falls below 3.2 characters per token; density varies with code blocks and tables, so the smallest and the largest skill are not a sufficient sample. **Measured: 2.77 to 3.12 characters per token under the Claude 5 tokenizer, so the ceiling is 13,000 characters** ([`facts.md`](facts.md) §1). Claude Code itself measures the kept 5,000 tokens as characters divided by four, about 19,900 characters, so the ceiling holds under either reading.
- [x] The template variable that names a skill's directory on each target, settled from the answers above. **`skill_dir`**: `${CLAUDE_SKILL_DIR}` on Claude, a `<skill-dir>` placeholder defined in one sentence on Codex and Vibe; a script is run by its absolute path from the user's project, through its interpreter ([`facts.md`](facts.md) §5).

Phase 0 landed in #51 at `1e58d7e`.

## Phase 1 — the shared blocks and the machinery · `L-260923-8c296f`

- [x] The `mcp-requirements` include shrinks to its two stops — an absent tool, a `config`-class error surfaced verbatim — and a pointer to `shared/credentials.md`, a new shared reference rendered per target and read when the error is about the key (box F). The credential sentence corrected by `L-260912-65d6fc` moves there unchanged.
- [x] The deferrals the plugin-skills-gaps campaign assigned here (its `plan.md`, "Deferred"): one statement of the path form of `files`, replacing the sources in `pipelex-inputs` and `pipelex-integrate`; one include for the project markers design and integrate share; one wording of the stale-types notice; the `runs/` exclusion in the shared submission convention; the frontmatter's stray blank line.
- [x] The build copies `skills/<skill>/scripts/` beside `references/`, executable bits kept, and the freshness check covers both.
- [x] `scripts/check.py` gains the ceiling check in report mode (box C) and the link check both ways (box H), with unit tests.
- [x] The guard registry's machinery in the unit suite: a guard's canonical sentence asserted exactly once in each target's rendered `SKILL.md` and in no reference.
- [x] `CLAUDE.md` and `docs/build-targets.md` state the read-before-act rule and the shape, for whoever writes the next skill; `docs/decisions.md` records the campaign's decisions.
- [x] `/rev`: two rounds at profile 3 (cubic, Codex, code-review), each fixing what it confirmed — the link check's containment, anchors, fences and nested references, and the `runs/` exclusion carried into every gathering step. One duplication deferred below.

### Checkpoint 1

The machinery a skill phase relies on is on `dev`. Record the ceiling value, the skill-directory variable, the report the ceiling check prints, and any fact of phase 0 that changed a box.

- **The ceiling is 13,000 characters** (`SKILL_CEILING_CHARS` in `scripts/check.py`), in report mode (`SKILL_CEILING_ENFORCED = False`). At the end of phase 1 it reports every skill over it on every target, from `pipelex-scaffold` (about 63,700 characters on Claude) down to `pipelex-edit` (about 14,000). `pipelex-edit` is new to the list at this value, so phase 6 trims it with `pipelex-organize`.
- **The skill-directory variable is `skill_dir`, decided and not yet in `targets/`**: `${CLAUDE_SKILL_DIR}` on Claude, a `<skill-dir>` placeholder defined in one sentence on Codex and Vibe. It lands with the first skill that names a script or a verbatim copy — phase 2, for integrate's copy of its gate script, which Vibe performed as a read-and-rewrite until told to `cp` — because a variable nothing reads is a dead switch.
- **What phase 0 changed.** Box C's value (13,000, not 16,000). Box E holds on every target, with one addition to what a script owes the skill: it is run by its absolute path from the user's project, through its interpreter, because on Codex and Vibe the model otherwise runs it from inside the skill's directory. And one bug found on the way and fixed on its own, `L-260923-dfb8ee`: Vibe dropped two skills over their frontmatter.
- **What phase 1 changed beyond the move**, each named in its pull request: `design`, `edit`, `organize`, `explain` and `inputs` now exclude `runs/` from what they submit, through the shared convention (box F's deferral); the stale-types notice has one wording; the requirements block's recovery text moved to `shared/credentials.md`. Two items were filed from the work: `L-260923-58d533` (integrate's call site and gates load a run's `runs/` artifacts) and `L-260923-0964b0` (skills tell Codex users to type a Claude spelling of a skill).
- [x] `/rev` (the checkpoint's own review is phase 1's pass).

Phase 1 landed in #52 at `2fd7120`.

## Phase 2 — `pipelex-integrate` · `L-260923-5a94e7`

- [x] `classification-integrate.md`.
- [x] The main path: the three selectors, the rules each stated once, steps 1 to 12 as short imperatives, the target table, the sidecar's shape, the stop table. The narrowing of a list output through its `items` envelope stays as a guard.
- [x] References, each entered on its condition: the signature fallback when `main_pipe` is absent, refresh mode, the harness section, the report on orphans, the long gate-failure rows. What the returned results carry, and the narrowing code, go to `references/typescript.md` and `references/python.md`, which already hold the call-site templates.
- [x] The script candidates judged against box E's test: the containment check and the sidecar's hashes. Record the ruling and why.
- [x] Guards registered, smoke sessions run: a TypeScript project from a local bundle, a refresh, a project owning a harness, a run that meets orphans, and the Codex main path. **The guards are registered** (the `pipelex-integrate` entry of `GUARDS` in `tests/unit/test_skill_guards.py`), and **every smoke scenario passed**, recorded with its session ids in [`smoke-integrate.md`](smoke-integrate.md).
- [x] `/rev`. Two rounds at profile 4 (cubic, Codex review and adversarial, code-review). The first found that the rewrite had dropped qualifiers and remedies the classification never recorded dropping, and restored them: an interrupted run is this method's only when its artifacts are this target's, a valid but unrunnable method is finished in `/pipelex-design`, the launch directory itself passes containment, and a gate's exit `2` forbids regeneration only where the tree is not what failed. The second restored three more of the same kind — `main_pipe` "when it has one", the destination "by default", and the TypeScript bundle location — and cut one sentence of rationale `docs/decisions.md` already held to pay for them. What was deferred is under Deferred below.

- **Rendered sizes after the rewrite**: 12,948 characters on Claude, 12,806 on Codex and 12,852 on Vibe, after the review's fixes, all under the 13,000 ceiling. The Claude render was 60,753 characters before.
- **The references, each with its entry condition**, all indexed at the foot of `SKILL.md`: `refresh.md` (step 1 finds this method's `sources.json`, the user asks to refresh, or an editing skill hands off), `harness.md` (step 1 finds a `codegen` script or Makefile target, or a `sources.json` with a `derived` map), `signature-fallback.md` (step 3 finds no `main_pipe`), `orphans.md` (step 6 returns orphans and no drift), `gate-failures.md` (a gate exits `2`). `typescript.md` and `python.md` are read at step 1 by language, and now carry the list-output narrowing code and the account of what the results carry.
- **The script ruling: neither candidate became a script.** The containment check is two path resolutions and a comparison, and one of its inputs — the directory the session was launched in — is known to the model, not to a script run from the project; the tool refuses a climbing `output_dir` itself, and comparing the resolved paths answers the symlink case. The sidecar's hashes are verified by the gate step 10 installs and step 11 runs, which reports a wrong or missing hash, or a file left out, as `stale-source` before the report is written. Either becomes a candidate again if a smoke session shows a model getting it wrong. The full reasoning is in `docs/decisions.md`, under "`pipelex-integrate`'s rationale, moved out of the skill".
- **What the smoke sessions showed** ([`smoke-integrate.md`](smoke-integrate.md)): each branch reference was read on its branch and none on the main path, so no moved caveat was missed and no template changed. No session got either script candidate wrong: every sidecar's hashes passed the gate, and every session resolved the project root with `pwd -P` or `realpath` before writing. For checkpoint 2, these surfaced on the way. `typescript.md`'s known-defect note does not name a project that type-checks under `bundler` and runs its `tsc` output under plain Node, and that shape sent one Codex run into changing the project's build; the gap predates the diet, so by box G it lands after the phase. And an unattended Codex run must pre-approve `mthds_codegen` in its config, which the eval suite `L-260921-479a8e` will need.
- **The behaviour changes** are listed at the top of [`classification-integrate.md`](classification-integrate.md): the gate copy as a literal `cp` from the skill's directory, refresh mode deferring to step 4's rule on a lock without a sidecar, and the rule for reading a `codegen` script applied at step 1, where the harness branch is taken.

Waiting on this phase, to land afterwards in the new shape: `L-260913-3784bb`, `L-260913-48195f`, `L-260913-10e237`, `L-260913-7436ee`, `L-260913-0f8a89` (the orphan logic); `L-260912-dc69dc`, `L-260912-a4471f`, `L-260912-248381`, `L-260912-ac493c`, `L-260913-6cac17`, `L-260913-50b58c`, `L-260920-140727`, `L-260920-32b840`, `L-260922-65260d`, `L-260916-89e5b8`.

### Checkpoint 2

The first skill in the new shape. Before inputs and design repeat it, read the result against the design: whether the classification held, whether any moved caveat was missed in a smoke session, and whether box B's shape needs a correction. Record what changed.

- **Landed** in `pipelex-plugins#53` as `ee7abfe`, on `dev`.
- **The classification held in its placements, and leaked in its qualifiers.** Every sentence went where its row said, and no smoke session met a caveat that had moved out of its reach. But the rewrite shortened sentences as it placed them, and a shortened guard lost conditions its row never recorded dropping: the interrupted run's "the tree's artifacts are the target's", the signature's "when the verdict carries it", the destination's "by default", the launch directory itself passing containment, the unrunnable method's own remedy, the bundle's destination on TypeScript, and a blanket "never regenerate" where the old text scoped it to its rows. None was a placement error, so no smoke session could see it; the two review rounds found them all by comparing the new sentence with the old. **The correction for inputs and design**: a classification row quotes every condition, qualifier and remedy of the sentence it classifies, and the rewrite is read against those quotes before the first review, not after.
- **No moved caveat was missed in a smoke session** ([`smoke-integrate.md`](smoke-integrate.md)): each branch reference was read on its branch and none on the main path.
- **Box B's shape needs no correction, but its budget does.** The shape fitted: a main path of short imperatives, a stop table, references pointed at their conditions. The margin did not: after the review's fixes the Claude render sits 52 characters under the ceiling, so every bug waiting on this phase lands in a reference or pays for itself in `SKILL.md`. For inputs and design the target is to finish the rewrite well under the ceiling — about 12,000 characters — so the review's restorations have room.

## Phase 3 — `pipelex-inputs` · `L-260923-e7a655`

- [x] `classification-inputs.md`.
- [x] The main path: the three target forms, the choice of strategy, the template call and its verdicts, the path rule of `inputs.json`, the core of preparation (what leaves the machine, absolute paths, the exact file and never a derived one, `inputs.prepared.json` written, `inputs.json` never rewritten), the conditions for offering a run, the stop table.
- [x] References: the synthetic and user-data detail, the size-limit failure, the stale-workshop refusal met only by an address, the worked examples.
- [x] Guards registered, smoke sessions run: the template strategy, a user's PDF prepared and offered, a synthetic file through `pipelex-synthetic-inputs`, a published address, and the Codex main path. **The guards are registered** (the `pipelex-inputs` entry of `GUARDS` in `tests/unit/test_skill_guards.py`), and **every smoke scenario passed box H's test**, recorded with its session ids in [`smoke-inputs.md`](smoke-inputs.md); the one expected outcome missed, the run offer on Codex, predates the diet.
- [x] `/rev`. Two rounds at profile 4 (cubic, Codex review and adversarial, code-review). The first, whose adversarial pass approved, restored the no-signal row's interactive question the rewrite had dropped, made `user-data.md`'s report follow the skill's step 5 rather than a section number it clashed with, gave a list input's copied files distinct names, and brought the campaign records up to date. The second restored the instruction to skip preparation when every file value is already remote, which the classification had deleted as a duplicate of a sentence that only described the case, and closed a gap older than the diet: step 5 now deletes a prepared file an earlier pass left, which a skipped, declined or failed preparation would otherwise leave for `/pipelex-run` to run stale or to hand back.

- **Rendered sizes after the rewrite**: 12,792 characters on Claude, 12,695 on Codex and 12,716 on Vibe after the review's fixes, all under the 13,000 ceiling; the Claude render was 41,480 characters before. That is above the phase's target of about 12,000, and the difference is checkpoint 2's correction applied before the review rather than after it: reading the draft against the classification's quotes restored qualifiers and remedies a shorter draft had dropped — the `mthds_list_methods` fallback, the scope of a mid-run switch to interactive mode, "with no further context" on the no-signal row, "the same prohibition applies after an upload failure", "no `explicit` flag" on the prepare call, the webapp editor and "source the user does not have" on an invalid template, what the one-line prepare report says. What the rest of the render holds is the guards, the sentences the tests pin, and the fixed blocks: the frontmatter (about 990 characters), the `validate-call` include (about 750) and the requirements include (about 560).
- **The references, each with its entry condition**, all indexed at the foot of `SKILL.md`: `synthetic.md` (step 3, the Synthetic strategy, or Mixed's unfilled inputs, before generating anything), `user-data.md` (step 3, the User data strategy, or Mixed, before matching any file), `published-address.md` (step 1, a `method_ref` target, before the first call; and from the stop table when prepare refuses an address with `input_domain` at `files` or with `config`), `prepare-errors.md` (from the stop table when prepare returns `input_domain` at `inputs`, `pipe_ref`, `method_id` or `method_ref`, before replying or retrying). The worked examples went to the strategy they illustrate; the size-limit failure is the first section of `prepare-errors.md`, whose pointer line in the stop table says the limit is terminal; the stale-workshop refusal is `published-address.md`'s, beside the other address-only refusal and the rest of what makes an address unlike an id. `tests/unit/test_pipelex_inputs_skill.py` holds the shape: each reference pointed at on the line where its branch is taken, static, opening with its entry condition, one level deep, shipped byte for byte, and the render under the ceiling while the check only reports.
- **What the smoke sessions showed** ([`smoke-inputs.md`](smoke-inputs.md)): each branch reference was read on its branch before acting — `user-data.md` before any file was matched, `synthetic.md` before anything was generated, `published-address.md` before the first call on an address, whose default `<output_dir>` the session took from it — and none on the template's main path, so no moved caveat was missed and no template changed. Every session that prepared announced the upload first, sent the path absolute, wrote `inputs.prepared.json` beside an `inputs.json` left as saved, and gitignored the prepared file; no session called a run tool, which a session-only hook would have refused. Claude offered the run in every scenario that reached it; Codex never did when the prompt told it to stop short of a run, and a control run of the pre-diet skill did the same, so the gap predates the diet and, by box G, a fix lands after the phase (`L-260923-530eb0`). The skill's quoted mock URL was stale and is corrected here; that the workshop refuses a `{path}` outside its launch directory, which the shared `validate-call` include does not say, is `L-260923-019e50`. For the eval suite `L-260921-479a8e`: an unattended Codex run must pre-approve `mthds_prepare_inputs`, and `prepare-errors.md` was reached by no scenario.
- **The behaviour changes** are listed at the top of [`classification-inputs.md`](classification-inputs.md): preparation no longer said anywhere to rewrite `inputs.json` (`L-260922-e01c73`'s sentences, resolved for the prepare step's version, and the haiku example deleted with its wrong directory), the closing summary names `inputs.prepared.json` only where prepare wrote one, and the worked PDF example sends its path absolute. PR #49, `L-260922-e01c73`'s own fix, touches the same sentences in the old shape; whichever lands second resolves the conflict towards the new shape, which says the same thing.

## Phase 4 — `pipelex-design` · `L-260923-9d9b59`

- [ ] `classification-design.md`.
- [ ] The main path: contract capture, the choice of mode, direct construction, the validation verdicts, the runnable gate, delivery.
- [ ] References: stepwise construction and re-entry; the catalog-id resolution through the include design, edit and organize share.
- [ ] The question of design section 6, answered and recorded: whether `references/writing-mthds.md`, read before every write, is split by pipe type. Not a commitment.
- [ ] Guards registered, smoke sessions run: a direct design, a stepwise design, a re-entry, a re-entry by catalog id, and the Codex main path.
- [ ] `/rev`.

Waiting on this phase: none but `L-260911-3a85ca`, which is ranked urgent and lands whenever it is ready.

### Checkpoint 3

The three most invoked large skills are in the new shape. Record their sizes, what each smoke session showed, and the ceiling check's report.

## Phase 5a — `pipelex-scaffold`: the starters leave, branch B runs through scripts · `L-260923-7febe6`

- [ ] `classification-scaffold.md`.
- [ ] The starter path is deleted, with `references/starters.md` and its tests: the Python starter, the gallery, the starter's bootstrap and env-file step, the GitHub-template form and the starter half of the fresh-clone shortcut (box E's amendment). Every project that is not a TypeScript web app goes to the ecosystem's initializer and then to `/pipelex-integrate`.
- [ ] Branch B's programs become scripts: the repository test with the pristine commit, and the env-file write, which never prints a key and reports `filled`, `kept` or `empty` and the plane as `production` or `other`. The unit suite executes them directly.
- [ ] References, each entered on its condition: the version-manager activation, the GitHub form, the per-framework detail in the existing `references/initializers.md`.
- [ ] The method-app path is left as it stands; it moves in phase 5b.
- [ ] Guards registered, smoke sessions run: a Python CLI, a FastAPI service, a TypeScript library, a directory holding only `.git`, and the Codex main path.
- [ ] `/rev`.

Waiting on this phase: `L-260915-4b00fe` and `L-260912-059765`, both about branch B's env file, which its script now owns. And `L-260923-7001f2`, which routes a Python CLI to the family's `cli-python` template (epic `L-260923-71f4a9`) on top of this phase, through the family's initializer rather than a recipe of the skill's own.

## Phase 5b — `pipelex-scaffold`: the method app through the family's own commands · `L-260923-0d9cb6`

Blocked by `L-260922-12f302` (the initializer and the serve target in `pipelex-method-apps`).

- [ ] The method-app path becomes the initializer, then the serve target, and the stop table keys on the verdicts they print; the acquisition and dev-server chains leave the skill, and their tests leave with them for the family's own.
- [ ] The ceiling check flips from reporting to failing, if phase 6 has already landed.
- [ ] Smoke sessions: the method app from a local bundle, from a catalog id, and the Codex main path.
- [ ] `/rev`.

## Phase 6 — the rest, and the ceiling bites · `L-260923-6b46c8`

- [ ] `pipelex-catalog`, `pipelex-run`, `pipelex-explain` and `pipelex-synthetic-inputs` trimmed under the ceiling by the same rule, each rare branch behind a pointer, and with them any other skill the ceiling calibrated in phase 0 puts over it — `pipelex-organize` first, which sits just under 16,000.
- [ ] The ceiling check flips from reporting to failing, if phase 5b has already landed; otherwise 5b flips it.
- [ ] `/rev`.

### Checkpoint 4 — the end of the campaign

Every rendered `SKILL.md` is under the ceiling on every target and `make check` fails one that is not. Record the final sizes against design section 2's table, what the smoke sessions found across the campaign, and the scenarios handed to `L-260921-479a8e`.

## Deferred

- **From phase 2's review, round 2:** nothing checks generically that a skill using `{{ skill_dir }}` includes `shared/skill-dir.md.j2` before its first use; only `pipelex-integrate`'s own test does. Add the check (on the Codex and Vibe renders, the defining sentence precedes the first `<skill-dir>`) in the phase that gives a second skill a script, which box E says is scaffold's (phase 5a).
- **From phase 2's review, round 2 (pre-existing):** the Python list-narrowing snippet in `pipelex-integrate`'s `references/python.md` indexes `main_stuff["items"]` before validating, so a wrong shape raises `KeyError` or `TypeError` rather than a pydantic `ValidationError`; the TypeScript twin validates the envelope first. The cure is a `BaseModel` envelope with `items: list[...]`, then `.model_validate(results.main_stuff).items`, and the pinned snippet in `tests/unit/test_pipelex_integrate_skill.py` with it.
- **From phase 2's review, round 2 (pre-existing):** `pipelex-integrate`'s `references/signature-fallback.md` names the MTHDS reference in words rather than as a link, and SKILL.md links it only from its closing index. A link to `../../shared/mthds-reference.md` from the fallback passes the link check, as `pipelex-design`'s `writing-mthds.md` already does; phase 6 can settle it with the one-level rule's wording in `docs/build-targets.md`, which says both that a reference never sends the model to another and that a shared file may be named by a reference.
- **From phase 2's review, round 2 (pre-existing, filed):** step 10's `cp` and refresh's re-copy overwrite a same-named project script they do not own — L-260923-ed42a7.
- **From phase 1's review, round 2 (unverified as a defect, confirmed as a duplication):** step 1 of `pipelex-design`'s and `pipelex-organize`'s validation says "none under a `runs/` directory" beside the `validate-call` include that states the same exclusion. Word step 1 as `pipelex-catalog` does ("Gather the bundle's files as the convention below says") when phase 4 rewrites design and phase 6 rewrites organize, so the exclusion is stated once.
