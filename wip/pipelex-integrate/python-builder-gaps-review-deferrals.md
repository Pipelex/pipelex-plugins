---
status: active
item: L-260913-4091b9
---

# `feature/Python-builder-gaps` — findings the review deferred

Round 1 of `/rev` on the branch `feature/Python-builder-gaps` (2026-09-13, profile 4, bar `open`) ran cubic, the Codex review and adversarial passes, and the official `code-review` at level medium, over the Python drift gate (`L-260913-4091b9`), the scaffold's base-URL rule (`L-260913-15af9f`), the TypeScript gate's no-verdict handling (`L-260913-db5269`) and the `@pipelex/sdk` floor (`L-260913-3faa9e`). What it fixed is in the branch's commits `937aa16` and `45d73c1` and in the changelog. This file is the trace for what it deliberately left.

## Carried elsewhere

- **A `.mthds` file added to a bundle leaves both drift gates green.** Raised by the Codex adversarial pass and confirmed by the pass's verifier: the gates hash only the files the sidecar records, while both call sites load every `.mthds` under the bundle directory. It predates the branch and its fix changes the sidecar's format, refresh mode and two sibling skills, so it is its own item, `L-260913-d509aa`.

## Deferred here, unverified

These rest on a reviewer's word alone: they were sorted as real but not important at the `open` bar and were not sent to the verifier.

- **unverified: the drift-gate contract tests could live in their own module.** cubic reads `tests/unit/test_pipelex_integrate_skill.py`, now carrying Node SDK stubs, subprocess harnesses and the cross-language sidecar table beside the rendered-skill assertions, as too broad a home, and suggests a focused module for the executable gate tests. An organisation change with no behaviour behind it.
- **unverified: the scaffold's env-file execution matrix could live in its own module.** The same observation by cubic for `tests/unit/test_pipelex_scaffold_skill.py`, whose cross-shell run of the shipped env-file command sits beside the rendering assertions.
- **unverified: an existing env file with a base URL of the user's and no key gets the shell's URL appended over it.** Raised by `code-review`. On the fresh-clone shortcut `cp -n` keeps the user's `.env.local`; when it carries a URL they set and an empty key, and the shell exports a different `PIPELEX_BASE_URL`, the one command's key test fails and the URL test passes, so the appended line overrides theirs under every later-line-wins reader, and the report's wording covers only files that already carried a key. It needs a pre-existing, half-filled env file and a shell pointing elsewhere. The developer's ruling of 2026-09-13 was that the shell's URL wins whenever the skill writes the file; whether that extends to a URL the user put in their own file is the open part.

## Noticed while fixing

- **The refresh table's "Left alone" cell still lists "the tooling exclusions (verified, re-added only if missing)"**, which refresh re-checks and re-applies, so it arguably belongs in the column round 1 renamed "Re-derived and re-checked". Reported by the implementer of round 1's refresh fix; a placement in a table, with no behaviour behind it.
