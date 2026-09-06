# The two Pipelex starters

Both are GitHub **template repositories** under the `Pipelex` organization. Each is a real, CI-tested application against the hosted Pipelex API, not a parameterized template: the identity you see in a fresh clone (`pipelex-starter-js` / `Pipelex Starter`, or `piper` / `Piper`) is a placeholder that the starter's own `bootstrap` skill rewrites. Read the clone's `README.md` after acquiring it — the sections named below are where the details live, and they move as the starters evolve.

## Side by side

| | `pipelex-starter-js` | `pipelex-starter-python` |
|---|---|---|
| **Shape** | Next.js (App Router), React, TypeScript strict, Tailwind; a web app with one tab per method whose input form is rendered from the method's own contract by `@pipelex/mthds-form` | A Typer CLI with one command per method, printing JSON on stdout and a cost report on stderr; three execution modes (`blocking`, `attended`, `detached`) as separate sub-packages |
| **Pick it when** | people will use the methods in a browser: forms, uploads, live run status | the methods run from a terminal, a script, a batch job or a service, and the user wants Python |
| **SDK** | `@pipelex/sdk` | `pipelex-sdk` (import package `pipelex_sdk`) — the `pipelex` runtime is **not** a dependency |
| **Methods live in** | `methods/<name>/main.mthds`, or `methods/<name>/method.json` for a method that lives elsewhere (a catalog id or a published address) | `<package>/methods/<name>/main.mthds` |
| **Generated types** | `src/generated/<name>/` — `types.ts`, `binder.ts`, `contracts.ts`, `codegen.lock`, `sources.json` | `<package>/generated/<name>/` — `models.py`, `codegen.lock` |
| **Codegen harness** | `npm run codegen` (keyed, dev), `npm run codegen:check` (offline, in `make check`), `npm run codegen:verify` (keyed, semantic); `make add-method METHOD=<mt_…|github.com/…>` scaffolds a remote method end to end | `make codegen` / `make codegen-check` — **both shell out to a `pipelex` CLI the starter does not depend on** (`PIPELEX=` in the Makefile); `/pipelex-integrate` knows this and writes into the same layout when that CLI is absent |
| **Toolchain floor** | Node ≥ the `engines.node` field of `package.json` (22.12 at writing); `npm` | `uv`; a Python inside `requires-python` of `pyproject.toml` (3.11–3.14 at writing) |
| **Env file** | `.env.local`, from `.env.example`: `PIPELEX_BASE_URL`, `PIPELEX_API_KEY`, `NEXT_PUBLIC_EXECUTION_MODE` | `.env`, from `.env.example`: `PIPELEX_BASE_URL`, `PIPELEX_API_KEY` |
| **Checks the bootstrap runs** | `npm install --package-lock-only`, then `make all` (lint, format check, typecheck, unit tests, build) | `make li` (lock + sync), then `make agent-check` and `make agent-test` |
| **Agent-facing files** | `CLAUDE.md`, `AGENTS.md`; skills `bootstrap`, `release`, `bump-sdk`, `bump-mthds-form` | `CLAUDE.md`; skills `bootstrap`, `release` |
| **Docs worth reading after bootstrap** | `docs/codegen.md`, `docs/add-method.md`, `docs/input-form.md`, `docs/adopt-in-an-existing-project.md`; README → "Swap in your own pipeline" and "Remove an example" | `docs/codegen.md`, `docs/cli-architecture.md`; README → the per-command sections |
| **Demos it carries** | several demo methods, one tab each; keep them as references or strip them with the README's "Remove an example" checklist | several demo methods, one CLI command each; keep them as references or remove the command and its method directory together |

## Acquisition

Local clone with fresh history (the default — it produces what GitHub's "Use this template" button produces, a copy with no history and no remote):

```bash
git clone --depth 1 https://github.com/Pipelex/pipelex-starter-js.git <dir>
git clone --depth 1 https://github.com/Pipelex/pipelex-starter-python.git <dir>
git -C <dir> rev-parse HEAD
rm -rf <dir>/.git && git -C <dir> init -b main
git -C <dir> add -A && git -C <dir> commit -m "Start from Pipelex/<starter> <version> (<sha>)"
```

The version comes from `package.json` (`"version"`) on JS and from `pyproject.toml` (`version =`) on Python, read before the commit.

GitHub repository, on request and after confirmation (visibility asked, default private; GitHub makes the initial commit, so no pristine commit of your own):

```bash
gh auth status
gh repo create <owner>/<name> --template Pipelex/pipelex-starter-js --private --clone
gh repo create <owner>/<name> --template Pipelex/pipelex-starter-python --private --clone
```

## The bootstrap you delegate to

Both starters carry `.claude/skills/bootstrap/SKILL.md` with a bundled script (`scripts/bootstrap.mjs` / `scripts/bootstrap.py`). Read the file in the clone and follow it; the shape is the same on both:

1. **Preflight** — confirms the identity is still the template's (`package.json` name `pipelex-starter-js`; `pyproject.toml` `name = "piper"`), notes a dirty tree, and on JS makes sure `node_modules/` exists (`make install`).
2. **Collect** — the package name (kebab on JS, underscores on Python, everything else derives from it), a display title, a one-line description; optionally author name **and** email (never one without the other), the repository URL, and the license (MIT kept, proprietary, or another SPDX id; the copyright holder and year). Pass what the conversation already holds so it asks once for the rest.
3. **Dry run** — the script with `--dry-run` prints the plan; the user confirms.
4. **Run** — the same command without `--dry-run`; on Python the package directory is renamed with `git mv`, which is why the pristine commit must exist first. `--clean` strips the template-only prose; keep it unless the user wants the template charter kept.
5. **Verify** — the lock file is re-synced and the project's own checks run; red is fixed, not skipped.
6. **Self-removal** — `rm -rf .claude/skills/bootstrap`, unstaged like everything else; the user reviews with `git status` and `git diff` and commits when ready.

The starter's rules are yours while you run it: never commit on the user's behalf, always dry-run first, never touch `.github/` or the `release` skill's logic.

## What `/pipelex-integrate` finds afterwards

A bootstrapped starter is a project that **owns a codegen harness**, and `/pipelex-integrate` defers to it: on JS it drops a bundle under `methods/<name>/` and runs `npm run codegen`, or runs `make add-method METHOD=…` for a catalog or published method, then follows `docs/codegen.md` and the existing actions for the fan-out; on Python it places the bundle under `<package>/methods/<name>/` and runs `make codegen` when a `pipelex` CLI is available, writing into `<package>/generated/<name>/` through the Pipelex workshop when it is not. It never writes a second generated layout beside the starter's own.
