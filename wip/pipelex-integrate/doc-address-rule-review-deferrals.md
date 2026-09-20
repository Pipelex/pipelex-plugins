---
status: active
item: L-260920-384e9c
---

# The documentation-address rule — what the review confirmed and did not fix

Round 2 of `/rev` on `feature/Skills-doc-refs-bare` ran at profile 1, bar `defects`, with cubic and Codex. Three confirmed findings were fixed on the branch and are in the pull request. This file is the trace for the one the bar deferred, so it is not a finding that merely evaporated.

## The prose invariant is stated in three places and nothing holds them in agreement

cubic raised it against `tests/unit/test_pipelex_integrate_skill.py`, outside the reviewed diff, and the bar deferred it as an improvement rather than a defect. It is recorded unverified: no verifier read it, because a deferral this repo owns is traced rather than verified.

The rule that a reference to an SDK documentation page carries the published URL, never a `node_modules` path, is now written in three files with three scopings of its own reach: `templates/skills/pipelex-integrate/SKILL.md.j2` names the three `@pipelex/sdk` pages explicitly, `skills/pipelex-integrate/references/typescript.md` scopes itself to its own section, and `skills/pipelex-integrate/references/python.md` states the Python SDK's URL in every position. Nothing asserts the three stay in agreement, and this branch's own round-2 findings were exactly that drift class: the template's rule scoped itself with the word "below" and so excluded `docs/run-results.md`, named above it, while the TypeScript twin's "here" included it.

The repo already guards a comparable multi-site invariant. `test_the_typescript_sdk_floor_is_one_number_everywhere` exists so that a floor bump updating one site and missing another fails the suite — and it earned its keep during this very round, catching a version number the fix had introduced into a region the test requires to name the floor alone. A guard of the same shape over the address rule is what this deferral asks for: that every site naming an SDK documentation page names it with the published URL, and that no site claims a reach the others do not.

What makes it an improvement rather than a defect is that the three statements agree today. The guard would hold them there.
