# Ecosystem initializers

Branch B of `/pipelex-scaffold` runs an initializer that already exists and authors nothing of its own beyond what that initializer writes. This file lists the common ones with their non-interactive forms. Flags change between versions: when a command below prompts anyway or rejects a flag, read its `--help` and prefer its own current non-interactive form over improvising a layout by hand. An initializer with no non-interactive form is handed to the user to run in the session.

After the initializer: `git init -b main` only if it did not initialize a repository itself, one pristine commit (`Scaffold <framework or language> project`), the two-line `.env.example` (`PIPELEX_BASE_URL=https://api.pipelex.com`, `PIPELEX_API_KEY=`), `.env` gitignored and copied from it. No SDK dependency — `/pipelex-integrate` adds it.

## Python

| Want | Command | `git init`? | Where the import package lands |
|---|---|---|---|
| **Minimal (the default when no framework is named)** | `uv init --package <dir>` | yes (`--vcs none` to skip) | `src/<package>/` with `__init__.py` and a console-script entry in `pyproject.toml` |
| A script-style app rather than a package | `uv init --app <dir>` | yes | `main.py` at the root — no import package; `/pipelex-integrate` will put the generated tree under `generated/` at the root |
| FastAPI service | `uv init --package <dir> && uv add "fastapi[standard]"` | yes | as minimal |
| Django project | `uv init --package <dir> && uv add django && (cd <dir> && uv run django-admin startproject config .)` | yes (from `uv init`) | the Django project package `config/` plus `src/<package>/`; ask which one owns the Pipelex call sites |
| Typer CLI (the Python starter's shape, without the starter) | `uv init --package <dir> && uv add typer` | yes | as minimal |
| An existing `pyproject.toml` layout the user prefers (poetry, pdm, hatch) | the tool the user names: `poetry new <dir>`, `pdm init --non-interactive`, `hatch new <name>` | poetry: no; pdm: no; hatch: no | per tool — `poetry new` and `hatch new` make `<package>/` or `src/<package>/` |

`uv init` refuses a directory that already holds a project; on an empty "here" directory use `uv init --package .` — it names the package after the directory.

## TypeScript / JavaScript

| Want | Command | `git init`? | Where `src/` lands |
|---|---|---|---|
| **Minimal (the default when no framework is named)** | `mkdir <dir> && cd <dir> && npm init -y && npm install --save-dev typescript @types/node && npx tsc --init --strict --module nodenext --target es2022 --rootDir src --outDir dist` then set `"type": "module"` in `package.json` | no | `src/` (create it); `/pipelex-integrate` puts the generated tree under `src/generated/` |
| Next.js app (the JS starter's shape, without the starter) | `npm create next-app@latest <dir> -- --ts --app --src-dir --eslint --use-npm --yes` | yes (`--disable-git` to skip) | `src/app/`; generated tree under `src/generated/` |
| Vite + React | `npm create vite@latest <dir> -- --template react-ts` then `npm install` | no | `src/` |
| Hono server | `npm create hono@latest <dir> -- --template nodejs --pm npm --install` | no | `src/` |
| Express server | the minimal recipe above, then `npm install express && npm install --save-dev @types/express` | no | `src/` |
| Node library | the minimal recipe above | no | `src/` |
| pnpm / yarn / bun instead of npm | replace `npm create` with `pnpm create` / `yarn create` / `bun create`, and the install command accordingly; `/pipelex-integrate` reads the lockfile to pick the package manager for what it adds | — | — |

`npm create <x>@latest <dir> -- <flags>`: the `--` is what passes the flags to the initializer rather than to npm. The Next.js `--yes` accepts the initializer's defaults for every prompt not covered by a flag.

## What every branch-B project shares afterwards

- One commit, the pristine scaffold, so the user's first real change is a clean diff.
- `.env.example` committed, `.env` ignored, `PIPELEX_API_KEY` filled only from the shell environment.
- Nothing else Pipelex-shaped: the SDK dependency, the `methods/` directory and the generated tree arrive with the first `/pipelex-integrate`.
