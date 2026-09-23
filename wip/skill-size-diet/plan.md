---
status: active
item: L-260923-a9bdfe
---

# Plan — the skill size diet

The implementation tracker for [`design.md`](design.md), whose boxes were all ratified on 2026-09-23. The epic is `L-260923-a9bdfe`, which superseded the parked item `L-260921-7918a6`. Each phase below names its ledger item beside its heading once filed; the order between them is recorded as `blocked_by` on the later item. Every phase is a move in the sense of box G: it changes no behaviour beyond what box G lists, and its pull request names each exception.

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

- [ ] On Codex: how the model learns a skill's directory; whether a relative link to `references/` resolves; whether a script under `scripts/` runs from the plugin's cache copy with its executable bit intact. Answered in a live session with a throwaway script in a local build.
- [ ] The same three on Mistral Vibe.
- [ ] Whether Codex or Vibe carries an invoked skill across its own compaction, and within what budget.
- [ ] Whether `pipelex-integrate`'s instruction to copy `references/codegen-check.mjs` works on all three targets today.
- [ ] The token count of rendered skills, taken with the token-counting endpoint on at least the smallest and the largest rendered `SKILL.md`, which sets box C's character ceiling (16,000 proposed) with its margin stated.
- [ ] The template variable that names a skill's directory on each target, settled from the answers above.

## Phase 1 — the shared blocks and the machinery · `L-260923-8c296f`

- [ ] The `mcp-requirements` include shrinks to its two stops — an absent tool, a `config`-class error surfaced verbatim — and a pointer to `shared/credentials.md`, a new shared reference rendered per target and read when the error is about the key (box F). The credential sentence corrected by `L-260912-65d6fc` moves there unchanged.
- [ ] The deferrals the plugin-skills-gaps campaign assigned here (its `plan.md`, "Deferred"): one statement of the path form of `files`, replacing the sources in `pipelex-inputs` and `pipelex-integrate`; one include for the project markers design and integrate share; one wording of the stale-types notice; the `runs/` exclusion in the shared submission convention; the frontmatter's stray blank line.
- [ ] The build copies `skills/<skill>/scripts/` beside `references/`, executable bits kept, and the freshness check covers both.
- [ ] `scripts/check.py` gains the ceiling check in report mode (box C) and the link check both ways (box H), with unit tests.
- [ ] The guard registry's machinery in the unit suite: a guard's canonical sentence asserted exactly once in each target's rendered `SKILL.md` and in no reference.
- [ ] `CLAUDE.md` and `docs/build-targets.md` state the read-before-act rule and the shape, for whoever writes the next skill; `docs/decisions.md` records the campaign's decisions.
- [ ] `/rev`.

### Checkpoint 1

The machinery a skill phase relies on is on `dev`. Record the ceiling value, the skill-directory variable, the report the ceiling check prints, and any fact of phase 0 that changed a box.

## Phase 2 — `pipelex-integrate` · `L-260923-5a94e7`

- [ ] `classification-integrate.md`.
- [ ] The main path: the three selectors, the rules each stated once, steps 1 to 12 as short imperatives, the target table, the sidecar's shape, the stop table. The narrowing of a list output through its `items` envelope stays as a guard.
- [ ] References, each entered on its condition: the signature fallback when `main_pipe` is absent, refresh mode, the harness section, the report on orphans, the long gate-failure rows. What the returned results carry, and the narrowing code, go to `references/typescript.md` and `references/python.md`, which already hold the call-site templates.
- [ ] The script candidates judged against box E's test: the containment check and the sidecar's hashes. Record the ruling and why.
- [ ] Guards registered, smoke sessions run: a TypeScript project from a local bundle, a refresh, a project owning a harness, a run that meets orphans, and the Codex main path.
- [ ] `/rev`.

Waiting on this phase, to land afterwards in the new shape: `L-260913-3784bb`, `L-260913-48195f`, `L-260913-10e237`, `L-260913-7436ee`, `L-260913-0f8a89` (the orphan logic); `L-260912-dc69dc`, `L-260912-a4471f`, `L-260912-248381`, `L-260912-ac493c`, `L-260913-6cac17`, `L-260913-50b58c`, `L-260920-140727`, `L-260920-32b840`, `L-260922-65260d`, `L-260916-89e5b8`.

### Checkpoint 2

The first skill in the new shape. Before inputs and design repeat it, read the result against the design: whether the classification held, whether any moved caveat was missed in a smoke session, and whether box B's shape needs a correction. Record what changed.

## Phase 3 — `pipelex-inputs` · `L-260923-e7a655`

- [ ] `classification-inputs.md`.
- [ ] The main path: the three target forms, the choice of strategy, the template call and its verdicts, the path rule of `inputs.json`, the core of preparation (what leaves the machine, absolute paths, the exact file and never a derived one, `inputs.prepared.json` written, `inputs.json` never rewritten), the conditions for offering a run, the stop table.
- [ ] References: the synthetic and user-data detail, the size-limit failure, the stale-workshop refusal met only by an address, the worked examples.
- [ ] Guards registered, smoke sessions run: the template strategy, a user's PDF prepared and offered, a synthetic file through `pipelex-synthetic-inputs`, a published address, and the Codex main path.
- [ ] `/rev`.

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

- [ ] `pipelex-catalog`, `pipelex-run`, `pipelex-explain` and `pipelex-synthetic-inputs` trimmed under the ceiling by the same rule, each rare branch behind a pointer.
- [ ] The ceiling check flips from reporting to failing, if phase 5b has already landed; otherwise 5b flips it.
- [ ] `/rev`.

### Checkpoint 4 — the end of the campaign

Every rendered `SKILL.md` is under the ceiling on every target and `make check` fails one that is not. Record the final sizes against design section 2's table, what the smoke sessions found across the campaign, and the scenarios handed to `L-260921-479a8e`.

## Deferred

Nothing yet.
