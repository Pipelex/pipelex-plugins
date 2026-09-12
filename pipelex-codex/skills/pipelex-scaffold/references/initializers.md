# Ecosystem initializers

Branch B of `/pipelex-scaffold` runs an initializer that already exists and authors nothing of its own beyond what that initializer writes. This file lists the common ones with their non-interactive forms. Flags change between versions: when a command below prompts anyway or rejects a flag, read its `--help` and prefer its own current non-interactive form over improvising a layout by hand. An initializer with no non-interactive form is handed to the user to run in the session.

After the initializer: `git init -b main` only if it did not initialize a repository itself, one pristine commit (`Scaffold <framework or language> project`), the two-line `.env.example` (`PIPELEX_BASE_URL=https://api.pipelex.com`, `PIPELEX_API_KEY=`), `.env` gitignored and copied from it. No SDK dependency — `/pipelex-integrate` adds it.

## Python

| Want | Command | `git init`? | Where the import package lands |
|---|---|---|---|
| **Minimal (the default when no framework is named)** | `uv init --package --no-workspace <dir>` | yes (`--vcs none` to skip) | `src/<package>/` with `__init__.py` and a console-script entry in `pyproject.toml` |
| A script-style app rather than a package | `uv init --app --no-workspace <dir>` | yes | `main.py` at the root — no import package; `/pipelex-integrate` will put the generated tree under `generated/` at the root |
| FastAPI service | `uv init --package --no-workspace <dir> && (cd <dir> && uv add "fastapi[standard]")` | yes | as minimal |
| Django project | `uv init --package --no-workspace <dir> && (cd <dir> && uv add django && uv run django-admin startproject config .)` | yes (from `uv init`) | the Django project package `config/` plus `src/<package>/`; ask which one owns the Pipelex call sites |
| Typer CLI (the Python starter's shape, without the starter) | `uv init --package --no-workspace <dir> && (cd <dir> && uv add typer)` | yes | as minimal |
| An existing `pyproject.toml` layout the user prefers (poetry, pdm, hatch) | the tool the user names: `poetry new <dir>`, `pdm init --non-interactive`, `hatch new <name>` | poetry: no; pdm: no; hatch: no | per tool — `poetry new` and `hatch new` make `<package>/` or `src/<package>/` |

`uv init` refuses a directory that already holds a project; on an empty "here" directory use `uv init --package --no-workspace .` — it names the package after the directory.

**`--no-workspace` is on every `uv init` above, and it is the same hazard the `uv add` parentheses below address, one command earlier.** Run inside a directory that already holds a `pyproject.toml` — the scaffold being made inside an existing project, which is the common case — a bare `uv init --package <dir>` does not create a standalone project at all. It prints `Adding <dir> as member of workspace …`, appends a `[tool.uv.workspace]` table naming `<dir>` to **the user's own `pyproject.toml`**, and then the first `uv add` writes the lockfile at the *parent* root, so the new project has no `uv.lock` of its own and does not resolve standalone. Editing a file of the user's is exactly what this skill does not do, and a project that needs its parent to resolve is not the project the report says was handed over. `--no-workspace` leaves the parent untouched and gives `<dir>` its own lock. With no parent project it changes nothing, so it is safe to pass always, which is why it is not conditional.

**Every `uv add` above runs inside `<dir>`, and the parentheses are why.** `uv add` resolves the project from its *working* directory upwards, so run from the parent it writes the dependency into whatever project it finds there — the user's own `pyproject.toml` and lockfile, when the scaffold is being made inside an existing workspace — or fails outright when it finds none. Neither is the new project. `uv add --directory <dir>` is equivalent if you prefer a flag to a subshell.

## TypeScript / JavaScript

| Want | Command | `git init`? | Where `src/` lands |
|---|---|---|---|
| **Minimal (the default when no framework is named)** | `mkdir <dir> && cd <dir> && npm init -y && npm install --save-dev typescript @types/node && npx tsc --init --strict --module nodenext --target es2022 --rootDir src --outDir dist` then set `"type": "module"` in `package.json` | no | `src/` (create it); `/pipelex-integrate` puts the generated tree under `src/generated/` |
| Next.js app (the JS starter's shape, without the starter) | `npm create next-app@latest <dir> -- --ts --app --src-dir --eslint --use-npm --yes` | yes (`--disable-git` to skip) | `src/app/`; generated tree under `src/generated/` |
| Vite + React | `npm create vite@latest <dir> -- --template react-ts` then `(cd <dir> && npm install)` | no | `src/` |
| Hono server | `npm create hono@latest <dir> -- --template nodejs --pm npm --install` | no | `src/` |
| Express server | the minimal recipe above, then `(cd <dir> && npm install express && npm install --save-dev @types/express)` | no | `src/` |
| Node library | the minimal recipe above | no | `src/` |
| pnpm / yarn / bun instead of npm | replace `npm create` with `pnpm create` / `yarn create` / `bun create`, and the install command accordingly; `/pipelex-integrate` reads the lockfile to pick the package manager for what it adds | — | — |

`npm create <x>@latest <dir> -- <flags>`: the `--` is what passes the flags to the initializer rather than to npm. The Next.js `--yes` accepts the initializer's defaults for every prompt not covered by a flag.

**Every follow-on `npm install` above is parenthesised for the same reason every `uv add` is, and npm is the worse of the two.** `npm install` resolves the project it writes to from its *working* directory upwards, so run from the parent it adds the dependency to the user's own `package.json` and puts `node_modules/` in the user's tree — and where `uv add` at least fails outright when it finds no project nearby, npm finds the parent and silently succeeds, leaving the new project with nothing installed and no error to read. The `cd <dir>` inside the minimal recipe's own `&&` chain does not reach a follow-on issued as a separate command, because shell state does not survive from one command to the next. Use the subshell, or `npm install --prefix <dir>`.

**The minimal recipe's `--module nodenext` plus `"type": "module"` is exactly the shape that meets the ts-zod emitter's extensionless-import defect** (`pipelex-integrate`'s `references/typescript.md`, "Known defect"): the generated `binder.ts` fails the type check with `TS2835` and will not load at runtime. So say so when you hand a minimal TypeScript project to `/pipelex-integrate`, and when the user has no reason to prefer Node's own resolution, prefer a bundler-backed setup (Vite, Next.js) or `--module esnext --moduleResolution bundler`, which the defect does not touch. The two recipes also need `node_modules/` and `dist/` in a `.gitignore` before the pristine commit — neither `npm init -y` nor `tsc --init` writes one.

**And `tsc --init` writes `"types": []` as an active key, which switches `@types/node` off on the line after the recipe installed it.** That empty array is the current `tsc --init` template's own default (TypeScript 7 writes it, with `// "types": ["node"],` commented out three lines below), and it means no `@types` package is loaded at all — so the call site `/pipelex-integrate` writes next fails with `TS2591` on `node:fs/promises`, on `node:path` and on `process`, and then cascading `TS7006` implicit-any on the `readdir` callback. Nothing about the errors points at the tsconfig, so set `"types": ["node"]` as part of the recipe rather than leaving it for the integration to discover. `npm install --save-dev typescript` also resolves to TypeScript 7 now; say which major the project got, because `tsc --init`'s defaults moved with it.

## What every branch-B project shares afterwards

- One commit, the pristine scaffold, so the user's first real change is a clean diff.
- `.env.example` committed, `.env` ignored, `PIPELEX_API_KEY` filled only from the shell environment.
- Nothing else Pipelex-shaped: the SDK dependency, the `methods/` directory and the generated tree arrive with the first `/pipelex-integrate`.
