---
status: active
item: L-260913-d509aa
---

# `feature/Gate-misses-added-bundle` — findings the review deferred

Round 1 of `/rev` on the branch `feature/Gate-misses-added-bundle` (2026-09-14, profile 4, bar `open`) ran cubic, the Codex review and adversarial passes, and the official `code-review` at level medium over pull request #23 against `feature/Python-builder-gaps`, at `017ba86`. It covered the sidecar's `bundle_dir`, both drift gates' listing of it, refresh mode's re-read of the file set, and the sibling skills' staleness notices. It fixed the stale Node advice in `references/typescript.md`'s call-site template, which invited a Node below `@pipelex/sdk`'s floor and, followed, would make the gate disagree with a hand-walked call site. This file is the trace for what it deliberately left.

## Deferred here, unverified

These rest on a reviewer's word alone: they were sorted as real but not important at the `open` bar and were not sent to the verifier.

- **unverified: the gate-listing tests pin source expressions rather than behaviour.** cubic reads the assertions in `tests/unit/test_pipelex_integrate_skill.py` that require the exact `rglob`, `readdir` and `filter` expressions in the gate scripts and the call-site templates as coupling the tests to implementation, since the end-to-end filesystem scenarios beside them already exercise recursive `.mthds` discovery. Those assertions may also be deliberate, pinning the promise that each gate lists `bundle_dir` exactly as its language's call site does; which reading holds is the open part.
- **unverified: a sidecar with `bundle_dir` and no `sources` key is told "`sources` is not an object".** Raised by `code-review`'s own reading, beside the skill's findings. Both gates exit `1` on it and agree with each other, so only the message is off: the field is missing rather than wrongly shaped. The input `{"bundle_dir": "methods/m"}` is already among the tests' sidecar cases.
