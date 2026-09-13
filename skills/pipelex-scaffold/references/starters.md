# The two Pipelex starters

Both are GitHub **template repositories** under the `Pipelex` organization. Each is a real, CI-tested application against the hosted Pipelex API, not a parameterized template: the identity you see in a fresh clone (`pipelex-starter-js` / `Pipelex Starter`, or `piper` / `Piper`) is a placeholder that the starter's own `bootstrap` skill rewrites. Read the clone's `README.md` after acquiring it — the sections named below are where the details live, and they move as the starters evolve.

## Side by side

| | `pipelex-starter-js` | `pipelex-starter-python` |
|---|---|---|
| **Shape** | Next.js (App Router), React, TypeScript strict, Tailwind; a web app with one tab per method whose input form is rendered from the method's own contract by `@pipelex/mthds-form` | A Typer CLI with one command per method, printing JSON on stdout and a cost report on stderr; three execution modes (`blocking`, `attended`, `detached`) as separate sub-packages |
| **Pick it when** | people will use the methods in a browser: forms, uploads, live run status | the methods run from a terminal, a script, a batch job or a service, and the user wants Python |
| **SDK** | `@pipelex/sdk` | `pipelex-sdk` (import package `pipelex_sdk`) — the `pipelex` runtime is **not** a dependency |
| **Methods live in** | `methods/<name>/main.mthds`, or `methods/<name>/method.json` for a method that lives elsewhere (a catalog id or a published address) | `<package>/methods/<name>/main.mthds`, or `<package>/methods/<name>/method.json` naming exactly one of `method_id` / `method_ref` for a method that lives elsewhere; a directory holds one kind, never both |
| **Generated types** | `src/generated/<name>/` — `types.ts`, `binder.ts`, `contracts.ts`, `codegen.lock`, `sources.json` | `<package>/generated/<module>/`, `<module>` being the method directory's name with its dashes turned into underscores — `models.py`, `codegen.lock` |
| **Codegen harness** | `npm run codegen` (keyed, dev), `npm run codegen:check` (offline, in `make check`), `npm run codegen:verify` (keyed, semantic); `make add-method METHOD=<mt_…|github.com/…>` scaffolds a remote method end to end | `make codegen` (keyed: `PIPELEX_API_KEY` from `.env` or the shell, through `pipelex-sdk` and the hosted `/v1/codegen`, no `pipelex` install), regenerating both source kinds; `make codegen-check` (offline) is the one target still shelling out to a `pipelex` CLI the starter does not depend on (`PIPELEX=` in the Makefile), and the test suite runs `pipelex-sdk`'s own check over every tree, so `make agent-test` gates them without it; `make add-method METHOD=<mt_…|github.com/…>` scaffolds a remote method end to end — the manifest, the tree and one Typer command |
| **Toolchain floor** | Node ≥ the `engines.node` field of `package.json` (22.12 at writing); `npm` | `uv`; a Python inside `requires-python` of `pyproject.toml` (3.11–3.14 at writing) |
| **Env file** | `.env.local`, from `.env.example`: `PIPELEX_BASE_URL`, `PIPELEX_API_KEY`, `NEXT_PUBLIC_EXECUTION_MODE` | `.env`, from `.env.example`: `PIPELEX_BASE_URL`, `PIPELEX_API_KEY` |
| **Checks the bootstrap runs** | `npm install --package-lock-only`, then `make all` (lint, format check, typecheck, unit tests, build) | `make li` (lock + sync), then `make agent-check` and `make agent-test` |
| **Agent-facing files** | `CLAUDE.md`, `AGENTS.md`; skills `bootstrap`, `release`, `bump-sdk`, `bump-mthds-form` | `CLAUDE.md`, `AGENTS.md`; skills `bootstrap`, `release` |
| **Docs worth reading after bootstrap** | `docs/codegen.md`, `docs/add-method.md`, `docs/input-form.md`, `docs/adopt-in-an-existing-project.md`; README → "Swap in your own pipeline" and "Remove an example" | `docs/codegen.md`, `docs/add-method.md`, `docs/cli-architecture.md`; README → "Swap in your own method" and the per-command sections. There is deliberately no adopt doc: `AGENTS.md` says why and what to read instead |
| **Demos it carries** | several demo methods, one tab each; keep them as references or strip them with the README's "Remove an example" checklist | several demo methods, one CLI command each; keep them as references or remove the command and its method directory together |

**The env file's two Pipelex lines name one plane.** Both examples ship `PIPELEX_BASE_URL=https://api.pipelex.com` beside an empty `PIPELEX_API_KEY`, and a key is refused by every plane but the one that issued it. So when `/pipelex-scaffold` writes the env file it copies a base URL the shell sets whether or not the shell also sets a key — an exported base URL is the plane the user has declared, and the Python starter's example itself documents a keyless self-hosted runner — and copies the key only when the shell sets it; a shell that sets neither leaves the example as it came, and an env file that already carries a key keeps both lines as they are. The command, its one guard and the report's wording for the plane the file points at are in the skill's env-file step.

## Acquisition

`<starter>` below is the one the choice above settled — `pipelex-starter-js` or `pipelex-starter-python` — and each block is a single chain for that one starter, never a menu to run top to bottom.

Local clone with fresh history (the default — it produces what GitHub's "Use this template" button produces, a copy with no history and no remote):

```bash
git clone --depth 1 https://github.com/Pipelex/<starter>.git <dir> || exit
git -C <dir> rev-parse HEAD
rm -rf <dir>/.git && git -C <dir> init -b main
git -C <dir> add -A -- . && git -C <dir> commit -m "Start from Pipelex/<starter> <version> (<sha>)" -- .
```

The version comes from `package.json` (`"version"`) on JS and from `pyproject.toml` (`version =`) on Python, read before the commit. **The `-- .` pathspec is on the commit as well as on the staging**, for the reason `/pipelex-scaffold`'s Step 3 gives in full: `add -A -- .` bounds what is staged, but a bare `git commit` then commits the whole index, so anything the user had staged elsewhere in an enclosing repository rides along under this skill's message.

**The `|| exit` on the clone is load-bearing and is not decoration**, for the reason `/pipelex-scaffold`'s Step 2 gives in full: the line below it deletes a `.git` directory, and a clone that never ran — a network failure, or `<dir>` already existing — leaves that `rm -rf` to find whatever `.git` is actually at that path, destroying a repository of the user's irrecoverably. The guard only holds inside one shell, so when the two lines go out as separate commands, check the clone's exit status yourself before typing the `rm -rf`, and never type it on a path you have not just created.

Into a directory whose only entry is `.git` — the one shape the "Where" rule reads as empty and `git clone` still refuses — acquire beside it and move in, so the user's own repository stands and the end state is the same as above:

```bash
dir=$(cd <dir> && pwd) || exit 1
tmp=$(mktemp -d "$(dirname "$dir")/.pipelex-starter-XXXXXX") || exit 1
git clone --depth 1 https://github.com/Pipelex/<starter>.git "$tmp" || { rm -rf "$tmp"; exit 1; }
git -C "$tmp" rev-parse HEAD
rm -rf "$tmp/.git" || { rm -rf "$tmp"; exit 1; }
[ "$(ls -A "$dir")" = ".git" ] || { rm -rf "$tmp"; exit 1; }
cp -R "$tmp"/. "$dir"/ || { rm -rf "$tmp"; exit 1; }
rm -rf "$tmp"
```

Every part of that chain is load-bearing, and `/pipelex-scaffold`'s Step 2 gives each in full. **The first line resolves `<dir>` to an absolute path before the parent is computed from it**, without which a destination spelled `.` — the ordinary spelling, since the user is usually standing in the directory they just `git init`-ed — puts the temporary directory inside the destination and the `ls -A` line then refuses every time. **No `rm -rf` in it addresses a path under `<dir>`**: the template's history is discarded while the clone is still at a path `mktemp` made for this command, before anything moves, so the guarded-deletion problem above does not arise here at all. **`cp -R "$tmp"/. "$dir"/` carries the entries beginning with a dot** — `.gitignore`, `.env.example`, `.github/`, `.claude/` — every one of which `mv "$tmp"/* "$dir"/` leaves behind while exiting `0`. And **the `ls -A` line admits exactly one entry**, `.git`, which the clone no longer has, so the template can only add to the directory and anything else stops the run with nothing copied and the temporary path removed. It is one chain and goes out as one command, for the reason the paragraph above gives.

GitHub repository, on request and after confirmation (visibility asked, default private; GitHub makes the initial commit, so no pristine commit of your own):

```bash
gh auth status
gh repo create <owner>/<name> --template Pipelex/<starter> --private --clone
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

A bootstrapped starter is a project that **owns a codegen harness**, and `/pipelex-integrate` defers to it: on JS it drops a bundle under `methods/<name>/` and runs `npm run codegen`, or runs `make add-method METHOD=…` for a catalog or published method, then follows `docs/codegen.md` and the existing actions for the fan-out; on Python it places a bundle under `<package>/methods/<name>/` and runs `make codegen`, or runs `make add-method METHOD=…` for a catalog or published method and, when that refuses an input it cannot spell on a command line, writes the `method.json` itself and runs `make codegen`; only when no `PIPELEX_API_KEY` reaches the project does it write into the starter's generated directory for that method, `<package>/generated/` plus the method directory's name with its dashes turned into underscores, through the Pipelex workshop instead. It never writes a second generated layout beside the starter's own.
