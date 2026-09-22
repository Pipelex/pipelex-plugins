---
status: active
item: L-260918-4bbf1f
---

# The call site returning `{ output, results }` — findings the review confirmed and did not fix

Round 2 of `/rev` on `feature/Call-site-returns-results` ran at profile 2, bar `defects`, with cubic and the official `code-review` at level `low`. What it fixed is in the pull request and the changelog. This file is the trace for what it left, so neither finding is one that merely evaporated.

## The `@pipelex/sdk` 0.18.0 floor names a version npm does not carry

- **Reporter:** cubic (P2), `skills/pipelex-integrate/references/codegen-check.mjs` `SDK_MINIMUM`.
- **Verified.** `npm view @pipelex/sdk versions` ends at `0.17.0` and `dist-tags.latest` is `0.17.0`; `pipelex-sdk-js/package.json` carries `0.17.0` and its changelog keeps `collectArtifacts`, the artifact operations, `summarizeUsage` and `RunResults.working_memory` under `[Unreleased]`. Five sites on this branch name 0.18.0: step 8, step 10's TypeScript bullet and the troubleshooting row of `templates/skills/pipelex-integrate/SKILL.md.j2`, the offline-gate section of `skills/pipelex-integrate/references/typescript.md`, and `SDK_MINIMUM` in `skills/pipelex-integrate/references/codegen-check.mjs`. A release of this repo ahead of that SDK release would leave step 8 asking the registry for a version that does not exist.
- **Why deferred.** The reporter's premise — that nothing enforces the ordering — does not hold. `L-260918-4bbf1f` is `blocked_by` the four items that compose the SDK release, and sprint `L-260918-19c2fe` places `pipelex-sdk-js` upstream of `pipelex-plugins` on its route, so the release train is the enforcement. The remedy cubic implies, a registry probe inside `make check`, is new machinery rather than a defect fix, and it would make an offline gate need the network. `upstream-dependencies.md` already records the constraint and the five sites that move together if the SDK ships under another number.
- **What closes it.** The SDK release landing on npm. Nothing to do here; if the number is not 0.18.0, the five sites move together.

## The `{ output, results }` shape is pinned in one place of the five that state it

- **Reporter:** cubic (P3), `tests/unit/test_pipelex_integrate_skill.py`.
- **Not verified.** It sorted as an improvement under the `defects` bar, so no verifier read it. What follows is the reporter's claim alone.
- **Claim.** The return shape now appears in step 9 of the skill body, in both reference call sites, in the refresh trigger and in the changelog, and only the refresh trigger carries an assertion — where the skill's other cross-file invariants (the SDK floor, the bundle-dir sidecar, the gate exclusions) are each test-pinned. A later edit to one call-site example could drift from the skill body without a test saying so.
- **Why deferred.** Added coverage is an improvement, and the bar admits none. Worth taking up whenever the skill's test module is next opened for another reason.
