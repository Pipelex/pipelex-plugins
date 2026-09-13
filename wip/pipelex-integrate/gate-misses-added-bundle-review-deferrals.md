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

## Round 2

Round 2 of `/rev` on the same branch (2026-09-14, profile 3, bar `defects`) ran cubic, the Codex review pass and `code-review` at level low over the branch at `252a06e`, after its rebase onto `feature/Python-builder-gaps` at `fefdf9b`. It fixed nothing. The one finding it verified — that an absolute or `..` `bundle_dir` lets both gates list a directory outside the project — was refuted: both gates exit `1` on it unless `sources` is rewritten to match, which gives the same green as a wrong directory inside the project, so it creates no wrong verdict, and the sidecar's `sources` keys have never been containment-checked either. `code-review` raised the round-1 message finding above again, unchanged. What it newly left is below.

### Deferred here, unverified

- **unverified: the two gates disagree on a bundle subdirectory the process cannot search.** Raised by cubic and by `code-review`, with different mechanisms: cubic says Python's `rglob` raises and the gate gives no verdict (`2`) where the TypeScript gate reports `stale-source` (`1`); `code-review` reproduced instead that `rglob` on Python 3.12 and 3.13 skips the unsearchable subdirectory silently, so the Python gate can exit `0` while Node's recursive `readdir` throws `EACCES` and the TypeScript gate exits `1`. Either way each gate lists the bundle exactly as its own language's call site loads it, so neither disagrees with what runs; what breaks is the promise that the two gates reach the same verdict on the same tree, and only for a bundle with an unsearchable subdirectory. The verifier of this round noticed the same difference while reproducing another finding and read it as no defect for that reason.
