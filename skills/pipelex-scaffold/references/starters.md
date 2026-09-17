# The Pipelex templates

Three templates, all under the `Pipelex` organization, and each a real, CI-tested application against the hosted Pipelex API rather than a parameterized template:

- **The method app** is the `webapp-js/` directory of the `pipelex-method-apps` repository, which holds one template per shape and language. It ships no method. `make create` turns a copy into the app for one method, and it is the TypeScript branch's default.
- **`pipelex-starter-js`** is the gallery the method app was extracted from. It carries several demo methods, one tab each, and is the docs' worked example and the place a person browses what the pattern can do. The skill acquires it only when the user names it.
- **`pipelex-starter-python`** is the Python starter: a CLI with one command per method.

The two starters are GitHub template repositories, and the identity in a fresh clone (`pipelex-starter-js` / `Pipelex Starter`, or `piper` / `Piper`) is a placeholder that the starter's own `bootstrap` skill rewrites. The method app's placeholder is `pipelex-method-webapp-js` / `Pipelex Method App`, and its `make create` rewrites it from the method. Read the copy's `README.md` after acquiring it: the sections named below are where the details live, and they move as the templates evolve.

## Side by side

| | The method app (`pipelex-method-apps/webapp-js`) | `pipelex-starter-js` (the gallery) | `pipelex-starter-python` |
|---|---|---|---|
| **Shape** | Next.js (App Router), React, TypeScript strict, Tailwind; a web app that ships no method — one method is the whole page, several are tabs — whose input form and result view are rendered from each method's own contract by `@pipelex/mthds-form` | Next.js (App Router), React, TypeScript strict, Tailwind; a web app with one tab per demo method whose input form is rendered from the method's own contract by `@pipelex/mthds-form` | A Typer CLI with one command per method, printing JSON on stdout and a cost report on stderr; three execution modes (`blocking`, `attended`, `detached`) as separate sub-packages |
| **Pick it when** | people will use the user's method in a browser: forms, uploads, live run status — the TypeScript default | the user names it: to read worked examples, or to follow the docs | the methods run from a terminal, a script, a batch job or a service, and the user wants Python |
| **SDK** | `@pipelex/sdk` | `@pipelex/sdk` | `pipelex-sdk` (import package `pipelex_sdk`) — the `pipelex` runtime is **not** a dependency |
| **Methods live in** | `methods/<name>/`, holding the bundle's `.mthds` files (every one of them is sent with a run), or `methods/<name>/method.json` for a method that lives elsewhere (a catalog id or a published address) | `methods/<name>/main.mthds`, or `methods/<name>/method.json` for a method that lives elsewhere (a catalog id or a published address) | `<package>/methods/<name>/main.mthds`, or `<package>/methods/<name>/method.json` naming exactly one of `method_id` / `method_ref` for a method that lives elsewhere; a directory holds one kind, never both |
| **Generated types** | `src/generated/<name>/` — `types.ts`, `binder.ts`, `contracts.ts`, `codegen.lock`, `sources.json` | `src/generated/<name>/` — `types.ts`, `binder.ts`, `contracts.ts`, `codegen.lock`, `sources.json` | `<package>/generated/<module>/`, `<module>` being the method directory's name with its dashes turned into underscores — `models.py`, `codegen.lock` |
| **Codegen harness** | `npm run codegen` (keyed, dev), `npm run codegen:check` (offline, in `make check`), `npm run codegen:verify` (keyed, semantic); `make add-method METHOD=<path to a bundle \| mt_… \| github.com/…>` scaffolds any method end to end — the slice, the Server Actions, the narrower, the form and the registry entry — a bundle path included | `npm run codegen` (keyed, dev), `npm run codegen:check` (offline, in `make check`), `npm run codegen:verify` (keyed, semantic); `make add-method METHOD=<mt_…\|github.com/…>` scaffolds a remote method end to end | `make codegen` (keyed: `PIPELEX_API_KEY` from `.env` or the shell, through `pipelex-sdk` and the hosted `/v1/codegen`, no `pipelex` install), regenerating both source kinds; `make codegen-check` (offline) is the one target still shelling out to a `pipelex` CLI the starter does not depend on (`PIPELEX=` in the Makefile), and the test suite runs `pipelex-sdk`'s own check over every tree, so `make agent-test` gates them without it; `make add-method METHOD=<mt_…\|github.com/…>` scaffolds a remote method end to end — the manifest, the tree and one Typer command |
| **Toolchain floor** | Node ≥ the `engines.node` field of `package.json` (22.12 at writing); `npm`; `make` | Node ≥ the `engines.node` field of `package.json` (22.12 at writing); `npm` | `uv`; a Python inside `requires-python` of `pyproject.toml` (3.11–3.14 at writing) |
| **Env file** | `.env.local`, written by `make create`: exactly one `PIPELEX_BASE_URL` line, the one the gesture ran against, and the key when the shell exports one; an existing `.env.local` is kept | `.env.local`, from `.env.example`: `PIPELEX_BASE_URL`, `PIPELEX_API_KEY`, `NEXT_PUBLIC_EXECUTION_MODE` | `.env`, from `.env.example`: `PIPELEX_BASE_URL`, `PIPELEX_API_KEY` |
| **Made the user's by** | `make create METHOD=…`: the identity derived from the method, the bootstrap run non-interactively, `.env.local` written, `npm install --package-lock-only`, `make all`, then the bootstrap removed | the clone's `bootstrap` skill: `npm install --package-lock-only`, then `make all` | the clone's `bootstrap` skill: `make li` (lock + sync), then `make agent-check` and `make agent-test` |
| **Agent-facing files** | `CLAUDE.md`, `AGENTS.md`; skills `bump-sdk`, `bump-mthds-form` (`bootstrap` until `make create` removes it) | `CLAUDE.md`, `AGENTS.md`; skills `bootstrap`, `release`, `bump-sdk`, `bump-mthds-form` | `CLAUDE.md`, `AGENTS.md`; skills `bootstrap`, `release` |
| **Docs worth reading afterwards** | `docs/add-method.md`, `docs/codegen.md`, `docs/input-form.md`, `docs/ci.md`; `docs/create.md` until the gesture removes it | `docs/codegen.md`, `docs/add-method.md`, `docs/input-form.md`, `docs/adopt-in-an-existing-project.md`; README → "Swap in your own pipeline" and "Remove an example" | `docs/codegen.md`, `docs/add-method.md`, `docs/cli-architecture.md`; README → "Swap in your own method" and the per-command sections. There is deliberately no adopt doc: `AGENTS.md` says why and what to read instead |
| **Demos it carries** | none | several demo methods, one tab each; keep them as references or strip them with the README's "Remove an example" checklist | several demo methods, one CLI command each; keep them as references or remove the command and its method directory together |

**The method app runs its gesture against a live plane.** `make create` fetches the method through the hosted API, so it needs the key, and a base URL whose plane serves the input and output form views codegen asks for — and `method_ref`, for an address. The template's README says which plane that is while production catches up; a gesture pointed at a plane without them refuses in its read-only half, naming the missing capability.

**The env file's two Pipelex lines name one plane.** Both starters' examples ship `PIPELEX_BASE_URL=https://api.pipelex.com` beside an empty `PIPELEX_API_KEY`, and a key is refused by every plane but the one that issued it. So when `/pipelex-scaffold` writes a starter's env file it copies a base URL the shell sets whether or not the shell also sets a key — an exported base URL is the plane the user has declared, and the Python starter's example itself documents a keyless self-hosted runner — and copies the key only when the shell sets it; a shell that sets neither leaves the example as it came, and an env file that already carries a key keeps both lines as they are. The command, its one guard and the report's wording for the plane the file points at are in the skill's env-file step. The method app's gesture writes its own `.env.local` by the same principle, one base-URL line naming the plane it ran against.

## Acquisition

### The method app

A project is a copy of `webapp-js/` alone, so the repository is cloned shallow beside the destination and the directory is copied out of it. One chain serves a destination that does not exist, an empty one, and one whose only entry is `.git`:

```bash
mkdir -p <dir> && dir=$(cd <dir> && pwd) || exit 1
case "$(ls -A "$dir")" in ""|.git) ;; *) exit 1 ;; esac
tmp=$(mktemp -d "$(dirname "$dir")/.pipelex-method-apps-XXXXXX") || exit 1
trap 'rm -rf "$tmp"' EXIT; trap 'exit 130' INT; trap 'exit 143' TERM
git clone --depth 1 https://github.com/Pipelex/pipelex-method-apps.git "$tmp" || exit 1
git -C "$tmp" rev-parse HEAD                     # the family SHA, for the commit message
cat "$tmp/VERSION"                               # the family version, for the commit message
[ -f "$tmp/webapp-js/package.json" ] || { echo "the default branch carries no webapp-js/" >&2; exit 1; }
case "$(ls -A "$dir")" in ""|.git) ;; *) exit 1 ;; esac
cp -R "$tmp/webapp-js"/. "$dir"/ || exit 1
[ -e "$dir/.git" ] || git -C "$dir" init -b main
```

The properties that make the starters' acquisition beside a repository safe, below, hold for this chain for the same reasons. Git never clones into the destination, so there is no template history to discard in it, and only `webapp-js/` crosses; the repository's own root files stay behind. **The `webapp-js/` test stops a default-branch head that does not carry the directory**, which would otherwise copy nothing and exit `0`. **The last line initializes only a destination with no repository of its own**, so a repository the user made goes on standing.

The pristine commit is a command of its own, because on a repository the user made it lands on their branch, and `/pipelex-scaffold` confirms that first:

```bash
git -C <dir> add -A -- . && git -C <dir> commit -m "Start from Pipelex/pipelex-method-apps/webapp-js <version> (<sha>)" -- .
```

Then, from inside the copy, `make create METHOD=<method>` with a bundle given as an absolute path, and `make dev APP_PORT=<port> APP_HOST=127.0.0.1` once it is green, so the server, whose Server Actions spend the key for whoever calls them, answers on this machine alone. `/pipelex-scaffold` starts it only on a copy whose `package.json` dev script names the host (`next dev -H ${APP_HOST:-127.0.0.1} …`), because without that `next dev` listens on every interface whatever `APP_HOST` says, and it checks where the server listens before the first request. Neither step is reimplemented here: `docs/create.md` in the copy is the reference.

A GitHub repository, on request, is created from the local copy after the pristine commit — the method app is a directory, not a template repository, so `--template` has nothing to point at — and confirmed first, visibility asked:

```bash
gh repo create <owner>/<name> --private --source <dir> --remote origin
```

### A starter

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
trap 'rm -rf "$tmp"' EXIT; trap 'exit 130' INT; trap 'exit 143' TERM
git clone --depth 1 https://github.com/Pipelex/<starter>.git "$tmp" || exit 1
git -C "$tmp" rev-parse HEAD
rm -rf "$tmp/.git" || exit 1
[ "$(ls -A "$dir")" = ".git" ] || exit 1
cp -R "$tmp"/. "$dir"/ || exit 1
```

Every part of that chain is load-bearing, and `/pipelex-scaffold`'s Step 2 gives each in full. **The first line resolves `<dir>` to an absolute path before the parent is computed from it**, without which a destination spelled `.` — the ordinary spelling, since the user is usually standing in the directory they just `git init`-ed — puts the temporary directory inside the destination and the `ls -A` line then refuses every time. **No `rm -rf` in it addresses a path under `<dir>`**: the template's history is discarded while the clone is still at a path `mktemp` made for this command, before anything moves, so the guarded-deletion problem above does not arise here at all. **`cp -R "$tmp"/. "$dir"/` carries the entries beginning with a dot** — `.gitignore`, `.env.example`, `.github/`, `.claude/` — every one of which `mv "$tmp"/* "$dir"/` leaves behind while exiting `0`. And **the `ls -A` line admits exactly one entry**, `.git`, which the clone no longer has, so the template can only add to the directory and anything else stops the run with nothing copied and the temporary path removed. **The trap on the line after `mktemp` removes the temporary path however the command ends**, a Ctrl-C or a harness's `TERM` included, which the `INT` and `TERM` traps turn into an ordinary exit because zsh and dash do not run an `EXIT` trap when a signal kills them. It is one chain and goes out as one command, for the reason the paragraph above gives.

GitHub repository, on request and after confirmation (visibility asked, default private; GitHub makes the initial commit, so no pristine commit of your own):

```bash
gh auth status
gh repo create <owner>/<name> --template Pipelex/<starter> --private --clone
```

## What makes a copy the user's

**The method app: `make create`.** It is the template's own script, one-shot and non-interactive: a value it cannot derive is a refusal naming the flag, never a prompt. It fetches the method once and derives the package name, the title and the description from it (`NAME=`, `TITLE=`, `DESCRIPTION=` override them); author, repository URL and license are never invented. It then scaffolds the method, runs the bootstrap with the derived values and `--clean`, writes `.env.local`, re-syncs the lock file and runs `make all`, and removes the bootstrap once that is green. Nothing is committed, so the whole result is a diff against the pristine commit. `DRY_RUN=1` prints the plan and changes no tracked file; like every run on a fresh copy, it installs the dependencies first, which writes `node_modules/` and lets husky set the repository's `core.hooksPath`. A failure after the scaffold is finished by hand with the steps its message names, because the gesture refuses a copy that is already a project. Its own warnings print as `! …` and the bootstrap's as `warning: …`, all before `make all`. Without `LICENSE_HOLDER=` (and optionally `LICENSE_YEAR=`), an MIT project's `LICENSE` keeps the template's copyright line, and the bootstrap warns about it.

**A starter: the clone's `bootstrap` skill.** Both starters carry `.claude/skills/bootstrap/SKILL.md` with a bundled script (`scripts/bootstrap.mjs` / `scripts/bootstrap.py`). Read the file in the clone and follow it; the shape is the same on both:

1. **Preflight** — confirms the identity is still the template's (`package.json` name `pipelex-starter-js`; `pyproject.toml` `name = "piper"`), notes a dirty tree, and on JS makes sure `node_modules/` exists (`make install`).
2. **Collect** — the package name (kebab on JS, underscores on Python, everything else derives from it), a display title, a one-line description; optionally author name **and** email (never one without the other), the repository URL, and the license (MIT kept, proprietary, or another SPDX id; the copyright holder and year). Pass what the conversation already holds so it asks once for the rest.
3. **Dry run** — the script with `--dry-run` prints the plan; the user confirms.
4. **Run** — the same command without `--dry-run`; on Python the package directory is renamed with `git mv`, which is why the pristine commit must exist first. `--clean` strips the template-only prose; keep it unless the user wants the template charter kept.
5. **Verify** — the lock file is re-synced and the project's own checks run; red is fixed, not skipped.
6. **Self-removal** — `rm -rf .claude/skills/bootstrap`, unstaged like everything else; the user reviews with `git status` and `git diff` and commits when ready.

The starter's rules are yours while you run it: never commit on the user's behalf, always dry-run first, never touch `.github/` or the `release` skill's logic.

## What `/pipelex-integrate` finds afterwards

A project made from any of the three **owns a codegen harness**, and `/pipelex-integrate` defers to it. On the method app, and on any project whose `make add-method` usage names a bundle path (`make help` prints it), every method is one command, a local bundle included: `make add-method METHOD=<path to the bundle>`, then the project's `make all`. On the gallery, whose `make add-method` takes only a catalog id or an address, a local bundle goes under `methods/<name>/` followed by `npm run codegen`, with the fan-out following `docs/codegen.md` and the existing actions; a catalog or published method is `make add-method METHOD=…`. On the Python starter, a bundle goes under `<package>/methods/<name>/` followed by `make codegen`, or `make add-method METHOD=…` runs for a catalog or published method; when that refuses an input it cannot spell on a command line, the skill writes the `method.json` itself and runs `make codegen`. Only when no `PIPELEX_API_KEY` reaches the project does it write into the starter's generated directory for that method, `<package>/generated/` plus the method directory's name with its dashes turned into underscores, through the Pipelex workshop instead. It never writes a second generated layout beside the starter's own.
