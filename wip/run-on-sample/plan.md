---
status: active
item: L-260927-87d267
---

# Plan — running a method on its own sample

The implementation tracker for [`design.md`](design.md), whose boxes were all ratified as written on 2026-09-27. The epic is `L-260927-87d267`, and its children are the four bugs the fix closes: `L-260927-235a99`, `L-260927-d7c594`, `L-260927-7f577e` and `L-260927-0e6ba4`. The work is one pull request, so the plan has one phase and no ledger item of its own: the PR closes the children and the epic.

## Handoff from the ratifying session — 2026-09-27

- **Done.** Both requested bugs were verified against `dev` at `5bb83dd`, and `L-260927-0e6ba4`, the envelope read as drift, was found and filed on the way. The epic `L-260927-87d267` was filed to carry the campaign, with all four bugs as its children and `plan:` refs to both documents. Every box was ratified as written, in an interview of one question per box: box A brought the two neighbours in, and box E swaps steps 2 and 3.
- **The documents travel on `docs/Run-on-sample-design`**, in the worktree `_pipelex-plugins--run-on-sample` at the workspace root. Landing them takes a recorded `/rev` pass, then `/ledger-land`; the PR body says `Advances L-260927-87d267`.
- **Next.** The implementation starts in a new session, as phase 1 says. If the design PR has not landed by then, branch from `docs/Run-on-sample-design` so the documents are there.
- **Open questions.** One, which the design's third review round confirmed and deferred: whether the envelope clause's one-field reading should widen to a native scalar's content that carries optional fields beside the required one, such as a Date with `time` or a Document with `title` (design 4.3). The runtime accepts that content, and no sample the tools write carries it. Read as drift, it is handed to `/pipelex-inputs`, which rewrites it to the template's bare string and drops the optional field, and which can reach `L-260923-c8f18e`'s overwrite. Widening the reading to "an object holding the template's field" changes a ratified box and spends characters the ceiling has 14 of, so it is Louis's call. Until he makes it, the implementation ships the ratified wording.

## Before the fix

- [x] The boxes ratified and recorded in `design.md`, both documents `active`.
- [x] `L-260927-7f577e` and `L-260927-0e6ba4` joined the epic as children.
- [x] `plan:` refs to both documents attached to the epic.
- [ ] The design documents land on `dev`.

## Phase 1 — `/pipelex-run` runs on the sample

Worktree `wt add --for L-260927-87d267 run-on-sample-fix --branch fix/Run-on-sample`, then `ledger claim L-260927-87d267 --renew` from inside it.

The template and its reference, as design 4.5 gives them:

- [ ] `templates/skills/pipelex-run/SKILL.md.j2`: steps 2 and 3 swapped, validation first; "A dry-run request goes to step 3 first" and "Step 2's template call does not stand in for it" removed, since the order now makes both true.
- [ ] The same template, the inputs step: the id's candidate directories and the ask (4.2); rule 1 laid over the sample (4.1); the check paragraph's optional-key and envelope clauses (4.3, 4.4).
- [ ] The same template, the room under the ceiling: step 4's clause naming the replaced keys; step 4's `PipeFunc` sentence cut to its guard and cure; step 1's address sentence removed.
- [ ] The same template, the renumbering: the intro's "a dry run is Start a run's step 3" becomes step 2, and step 5's "the values step 2 settled on" becomes step 3.
- [ ] `skills/pipelex-run/references/published-address.md`: gains step 1's address sentence, and "A verdict that fails at step 3" becomes step 2.

The tests and the documentation:

- [ ] `tests/unit/test_gen_skill_docs.py`: `test_user_values_are_laid_over_a_prepared_set` asserts the `inputs.json` fallback and that "With no prepared file, the request's values are the whole set" is gone; new tests pin the id's candidate directories and the ask, the envelope clause with its one-field reading and its limit to an envelope the template does not show, the optional-key clause and its limit to the main pipe, and the order (validation before the inputs); the address-reference test checks the moved sentence.
- [ ] `tests/unit/test_skill_guards.py`: "When several do, ask which; never choose." joins `pipelex-run`'s guards, and "**A dry-run request goes to step 3 first.**" leaves with its sentence.
- [ ] `docs/skills.md`, the `pipelex-run` paragraph: a sentence on the overlay and on where a run by id finds its inputs.
- [ ] `docs/decisions.md`: why the overlay's base is the sample, why the id's candidates are peers with an ask rather than a ranking, why the directory lends only its inputs, why `/pipelex-inputs` keeps `./<method_id>/`, why an enveloped input is checked by its content and how that content maps onto the light template's three shapes, and why validation moved ahead of the inputs.
- [ ] `CHANGELOG.md`, `[Unreleased]` → `### Fixed`: one bullet for the run on the sample, in the release-facing voice, with no ledger id.

The gates:

- [ ] `make build`, `make check` (the ceiling on every target; the design measured about 12,986 characters on Claude, 14 under), `make agent-test`.
- [ ] The smoke sessions of design section 6, each recorded below with its session id and verdict.
- [ ] `/rev`, at the profile `ledger review-profile` derives.
- [ ] The PR, titled `fix/Run-on-sample · L-260927-87d267`, with `Closes` for the epic and each of the four children.

### Smoke sessions

| Scenario | Harness | Session | Verdict |
|---|---|---|---|
| "…prove it on the sample with the question asked in French" from `./document-qa` | Claude Code | | |
| "Run mt_… on its sample." with `document-qa/` linked | Claude Code | | |
| The same, with a second `inputs.json` in `./mt_…/` | Claude Code | | |
| A dry run by id, which must end before any input is read | Claude Code | | |
| "Run mt_… on its sample." with `document-qa/` linked | Codex | | |

### Checkpoint 1

Record the rendered sizes on every target, the SHA the PR squashed into, the smoke verdicts, and anything the review deferred and where it went. The checklist ends with `/rev` above; a deferral goes to the ledger or to this directory.

## After the fix

- [ ] `/ledger-land` on the merged PR closes the children and the epic, and flips both documents to `landed`.
- [ ] The fix reaches users with the next plugin release, cut by `/release` like any other; this campaign adds nothing to it.
