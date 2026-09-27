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
- [x] The design documents land on `dev`, in pipelex-plugins#92 (`83b2d84`).

## Phase 1 — `/pipelex-run` runs on the sample

Worktree `wt add --for L-260927-87d267 run-on-sample-fix --branch fix/Run-on-sample`, then `ledger claim L-260927-87d267 --renew` from inside it.

The template and its reference, as design 4.5 gives them:

- [x] `templates/skills/pipelex-run/SKILL.md.j2`: steps 2 and 3 swapped, validation first; "A dry-run request goes to step 3 first" and "Step 2's template call does not stand in for it" removed, since the order now makes both true.
- [x] The same template, the inputs step: the id's candidate directories and the ask (4.2); rule 1 laid over the sample (4.1); the check paragraph's optional-key and envelope clauses (4.3, 4.4).
- [x] The same template, the room under the ceiling: step 4's clause naming the replaced keys; step 4's `PipeFunc` sentence cut to its guard and cure; step 1's address sentence removed.
- [x] The same template, the renumbering: the intro's "a dry run is Start a run's step 3" becomes step 2, and step 5's "the values step 2 settled on" becomes step 3.
- [x] `skills/pipelex-run/references/published-address.md`: gains step 1's address sentence, and "A verdict that fails at step 3" becomes step 2.

The tests and the documentation:

- [x] `tests/unit/test_gen_skill_docs.py`: `test_user_values_are_laid_over_a_prepared_set` asserts the `inputs.json` fallback and that "With no prepared file, the request's values are the whole set" is gone; new tests pin the id's candidate directories and the ask, the envelope clause with its one-field reading and its limit to an envelope the template does not show, the optional-key clause and its limit to the main pipe, and the order (validation before the inputs); the address-reference test checks the moved sentence.
- [x] `tests/unit/test_skill_guards.py`: "When several do, ask which; never choose." joins `pipelex-run`'s guards, and "**A dry-run request goes to step 3 first.**" leaves with its sentence.
- [x] `docs/skills.md`, the `pipelex-run` paragraph: a sentence on the overlay and on where a run by id finds its inputs.
- [x] `docs/decisions.md`: why the overlay's base is the sample, why the id's candidates are peers with an ask rather than a ranking, why the directory lends only its inputs, why `/pipelex-inputs` keeps `./<method_id>/`, why an enveloped input is checked by its content and how that content maps onto the light template's three shapes, and why validation moved ahead of the inputs.
- [x] `CHANGELOG.md`, `[Unreleased]` → `### Fixed`: one bullet for the run on the sample, in the release-facing voice, with no ledger id.

The gates:

- [x] `make build`, `make check` (the ceiling on every target; the design measured about 12,986 characters on Claude, 14 under), `make agent-test`.
- [x] The smoke sessions of design section 6, each recorded below with its session id and verdict.
- [x] `/rev`, at the profile `ledger review-profile` derives.
- [ ] The PR, titled `fix/Run-on-sample · L-260927-87d267`, with `Closes` for the epic and each of the four children.

### Smoke sessions

| Scenario | Harness | Session | Verdict |
|---|---|---|---|
| "…prove it on the sample with the question asked in French" from `./document-qa` | Claude Code | `2aa562c4-3c7f-4929-b270-2d767aef5869` | Pass. `files` target; the sample's document kept and only `question` replaced by the French text, both in the envelope; the missing optional `context` accepted from the verdict; no hand-off. No line before the call (`L-260927-17ca4a`). |
| "Run mt_… on its sample." with `document-qa/` linked | Claude Code | `e2491f40-f439-4235-a371-6b91f4017259` | Pass. `method_id` alone; the sample found through `document-qa/pipelex-method.json` and sent verbatim; no hand-off. No line before the call (`L-260927-17ca4a`). |
| The same, with a second `inputs.json` in `./mt_…/` | Claude Code | `3cce870f-c9b1-47e3-85cc-6d14a2bd57ef` | Pass. Named both samples with their questions, asked which, started nothing. It asked before validating, which spends nothing. |
| A dry run by id, which must end before any input is read | Claude Code | `79ef27ea-ff02-4c9f-8a59-67df88a4bbdf` | Pass. "Do a dry run of mt_… first.": one `mthds_validate`, the contract from `main_pipe`, no input read, the turn ended on the go. |
| "Run mt_… on its sample." with `document-qa/` linked | Codex | `01a0e3ac-449d-7173-956f-b3a96b249a05` | Pass. Validated, found the linked sample, checked it against the template, said the line with the credit notice, then called `mthds_run` by `method_id` with the sample verbatim. |

**How the sessions were run.** Each ran headless (`claude -p`, Opus 5.5, `--plugin-dir` on this branch's `pipelex/` at `4261cda`; `codex exec`, Codex 0.156.1 with `gpt-6-sol`, from a `CODEX_HOME` of its own whose marketplace pointed at the worktree) in a scratch directory holding a copy of the saved method `mt_2bc0cc9a-ebf9-41e7-bf01-9ae503fc1c5e` (document-qa, prod) and the cookbook's `answer_from_documents@v0.20.0` sample. The requests were the recipe's own, not reworded: a PreToolUse hook refused `mthds_run` and the other writing tools and recorded the exact payload, so the paid call was attempted and its target and inputs read from the record, and nothing was spent. A canary on each harness proved the hook refused the plugin's tool before a scenario ran. A second dry run, "Do a dry run of mt_… on its sample." (`31408f95-b6ec-49fc-979f-81222d4defb7`), made no template call and spent nothing, but read the sample's `inputs.json` to describe it, which the request's words invited; no hand-off followed.

**Settled before the first session: the dry run stays at step 2, and the scenarios keep the recipe's words.** Codex's fourth-round reading was that once validation runs first, a request worded "…show me the target and the exact inputs you would send, and do not start the run" may be taken as a dry run and never reach the inputs. Box E ratified a dry run that stops before any input is read, so the scenarios changed instead of the skill: they send the recipe's real requests, and the harness refuses the paid call and records it, as above. The dry-run paragraph's closing report dropped "and what the inputs still need", since a dry run reads none, which also gave back 30 characters.

### Checkpoint 1

Record the rendered sizes on every target, the SHA the PR squashed into, the smoke verdicts, and anything the review deferred and where it went. The checklist ends with `/rev` above; a deferral goes to the ledger or to this directory.

- **Rendered sizes** of `pipelex-run/SKILL.md` at `4261cda`: 12,953 characters on Claude, 12,628 on Codex, 12,642 on Vibe, against the 13,000 ceiling. Claude came out 33 under the design's estimate, because the dry run's closing clause went.
- **The smoke verdicts** are in the table above: every scenario passed.
- **The review** was `/rev` at the derived profile 2, round 1, on `21bc25f`: Codex's review and the official `code-review` at `low` each reported no findings, so the pass was recorded clean and the round converged. Nothing was deferred.
- **Filed on the way.** The design's open question, whether the envelope reading widens to a scalar's content carrying optional fields, is the decision `L-260927-f04ede`, filed so it outlives this campaign; the implementation ships the ratified wording. The line before a paid run, skipped by Claude Code in both headless sessions that reached the call, is `L-260927-17ca4a`; it predates this fix, and the request is still the consent.

## After the fix

- [ ] `/ledger-land` on the merged PR closes the children and the epic, and flips both documents to `landed`.
- [ ] The fix reaches users with the next plugin release, cut by `/release` like any other; this campaign adds nothing to it.
