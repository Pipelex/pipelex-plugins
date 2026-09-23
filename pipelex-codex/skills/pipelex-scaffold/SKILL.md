---
name: pipelex-scaffold
description: Start a new project that calls MTHDS methods through Pipelex, in TypeScript or Python — a web app for a method from the method-app template, created in one command and left running with its URL reported, or any other project from the ecosystem's own initializer, handed to /pipelex-integrate. Use when the user says "start a new project with Pipelex", "I have a method and need an app around it", "create a Next.js app that runs my method", "build me a web app for this method", "set up a Pipelex project from scratch", "new Python CLI for this method", "bootstrap a Pipelex project", or wants a codebase where none exists yet. Also use when the user stands in a copy of the method-app template not yet made theirs. Not for adding Pipelex to code that already exists — that is /pipelex-integrate.
---

# Scaffold a project for Pipelex methods

Give a user with no project one that runs their method, or one ready for `/pipelex-integrate`. This skill has exactly two branches and carries no templates of its own:

- **The method app**, for a web app around a method in TypeScript. The `pipelex-method-apps` family's initializer writes its `webapp-js/` template, commits it as it came and runs the copy's own `make create` with the method; the copy's `make serve` then starts the app and proves the page answers. Both are the family's commands, and nothing they do is reimplemented here.
- **The ecosystem's own initializer** for every other project: Python of any shape, and TypeScript that is not a web app. You run it and never assemble a project by hand, and this skill's two scripts make its pristine commit and its env file.

**The starters are not scaffolded from**: a user who names `pipelex-starter-js` or `pipelex-starter-python` is told so and offered the method app or the initializer. This skill is not a template engine (no cookiecutter, no copier, no framework matrix of its own), a runner or a deployer, and it needs no MCP tool.

**Never print a key, and never ask for one in the conversation.** The initializer's `.env` and the method app's `.env.local` hold one, and **the value moves only through a shell that expands the variable itself, and never through you**: `write-env-file.sh` moves it on one branch and `make create` on the other. Never `env | grep PIPELEX`, never echo either value, never move one with a file-editing tool, and **no reading an env file back**: a key in the transcript is a key to rotate.

## Choosing the branch

A cheap, reliable signal decides; an inconclusive one asks one question; nothing is guessed twice.

| Question | Signals, in order | When inconclusive |
|---|---|---|
| **Language** | the user's word; the method's consumer; a framework named | ask |
| **Which branch** | a **web app people use in a browser**, in TypeScript → the method app; a **named framework** it is not (FastAPI, Django, Express, a Lambda), **"minimal"**, **"no template"**, any **CLI, script, worker, service or library** → the initializer | one question, the method app first: a page rendering the method's form and result, made in one command and left running |
| **Where** | the directory named; **"here"** when the working directory is empty; else a kebab-case name | ask |
| **GitHub** | asked for → read [references/github.md](references/github.md) before any `gh` command | local |

**An empty directory has no entry, or only `.git`. A lone `.git` is the only entry that does not make a directory non-empty, and that is a ruling about `.git` and nothing else**: `.DS_Store`, `.idea/`, `.vscode/`, `Thumbs.db` and every other entry refuse, since judging which of a user's files matter is what this rule forbids. So never write into a directory that exists and is not empty, and never offer to move, delete or merge what it holds to make room; the answer is another directory.

**The method app needs the method first**, so a user without one goes to `/pipelex-design` and comes back with it. It is a bundle (a `.mthds` file or a directory of them), a catalog id (`mt_…`) or a package address (`github.com/<owner>/<repo>[/<package>][@<tag>]`). An unnamed directory takes the method's name, kebab-cased: a bundle's `domain`, or an address's last segment without its tag; for a catalog id, ask.

**A copy of the template not yet made the user's**, whose `package.json` says `pipelex-method-webapp-js` and which still has `scripts/create.mts`, is finished and never created again: read [references/uncreated-copy.md](references/uncreated-copy.md) before running anything in it.

**Every placeholder is one shell word**: `<dir>`, `<method>` and the rest go in single quotes, with a quote inside spelled `'\''`.

## Mode

Automatic by default; an explicit signal wins ("just do it", "walk me through"). One thing always confirms, in every mode: **`gh repo create`**. A second confirms on branch B: a pristine commit into a directory that already held a repository. In interactive mode, the method app's command takes `--dry-run` first, so the user sees the plan before anything is created from it.

## Prerequisites

`git`; `node` at 22.12 or later with `npm`, for the method app and for TypeScript; `uv` for Python, or the tool the user named instead. **Never install a toolchain, and never let a version manager download one.** When `node` or `uv` is missing, or `node` is below the floor, read [references/version-managers.md](references/version-managers.md) before stopping. The initializer and `make serve` check the rest themselves.

**On Python, find an interpreter from 3.11 to 3.14 before anything is created, and create the project on it**, since `pipelex-sdk` installs into no other. `uv python find '>=3.11,<3.15'` must print one, because uv downloads a Python it lacks; `uv init` takes its version as `--python <X.Y>`.

## Branch A — the method app

### Step 1: Create

```bash
npm create --yes @pipelex/method-app@latest '<dir>' -- --method '<method>' --quiet
```

It never prompts and reads a bundle path from where it runs. **Run it in the foreground with a long timeout**: it takes minutes, and its verdict decides the next step. Pass `--name`, `--title`, `--description`, `--author-name`, `--author-email`, `--repo-url` or a `--license…` option only with a value the user gave, never an invented one, and `--pipe`, `--method-name` or `--label` to answer a refusal that names it.

**Its verdict is the last line opening with `created`, `copied`, `refused:` or `failed:`**, not npm's `npm error` lines after it; with no such line, npm itself failed, and you relay its error. Branch on the verdict's first word, never on the exit code. Above it come the git outcome (`git: …`) and `make create`'s warnings, for the report. `created` goes on to step 2; `copied`, which only `--dry-run` or `--no-create` prints, to [references/uncreated-copy.md](references/uncreated-copy.md); any other verdict is in the stop table.

### Step 2: Serve

```bash
make -C '<dir>' serve
```

It starts the dev server in the background, on loopback, and requests the page. Its verdict is its last line not opening with `make`: `serving <url> — "<title>"`, or `already-serving`. **Never report a URL that did not answer**: only those two verdicts give one. **Never start the server any other way** (`make dev`, `npm run dev`, an `APP_HOST`): its Server Actions spend the key for anyone who can reach it. Nothing is run through the method.

## Branch B — the ecosystem's initializer

1. **Read [references/initializers.md](references/initializers.md) before running any initializer**, then run the named framework's, or the language's minimal one, with its non-interactive flags. One that only runs interactively is the user's to run, and you resume after. Nothing beyond what the initializer writes is authored by this skill. **On a project `uv init` created, finish with `uv sync` from inside `<dir>`**, because `/pipelex-integrate` reads no lock file as `pip install`.
2. **When `<dir>` held a `.git` before step 1, ask before running the script**, showing `git -C <dir> status --short`, since the commit lands on the user's branch. `<skill-dir>` stands for the directory holding this `SKILL.md`, the one Codex named when it loaded the skill. Run the script, never its steps by hand:

   ```bash
   bash "<skill-dir>/scripts/commit-pristine.sh" '<dir>' 'Scaffold <framework or language> project'
   ```

   It makes `<dir>` its own repository when it is not one, keeps the dependency tree and `.env` out, and commits `<dir>` alone: the **one commit this skill makes**. `committed:` names it and lists the staged paths; `kept:` names the commit the initializer made itself.
3. Write the env file. The script prints one line and never a value, `<key> base-url=<origin> plane=<plane>`:

   ```bash
   bash "<skill-dir>/scripts/write-env-file.sh" '<dir>'
   ```

4. Add **no** SDK dependency and create **no** empty `methods/` directory: `/pipelex-integrate` adds both with the first call site.

## The report

**On the method app, the URL comes first**, with that it runs in the background on this machine alone, how the verdict says to stop it, and that `make serve` inside the project restarts it. Then say what was created and where, with its name and title; the template's version and the git outcome, which is no commit when `<dir>` sits in another repository's work tree; that `make create`'s changes are uncommitted for review; each warning with what answers it, first that `LICENSE` still names the template's holder when it does, which the user claims by editing that line; the plane of `.env.local`, `[ "${PIPELEX_BASE_URL%/}" = https://api.pipelex.com ] && echo production || echo other` or production when the shell exports none; and `make add-method METHOD=…` for a second method, `npm run codegen` after a bundle edit.

**On the initializer's project**, say what was created and where; the initializer and its version; the pristine commit and who made it; that `.env.example`, `.env` and any `.gitignore` line are uncommitted; and the env verdict in the words [references/initializers.md](references/initializers.md) gives each, never the URL. A key reported `filled` was taken from the environment **and not validated**.

Two lines close it. **The project's own instructions and skills load in a session started inside it**: `cd <dir>`, then Codex there. **`/pipelex-integrate` works from here meanwhile**, unless `node` was missing from the `PATH` and came through a version manager, whose hand-off [references/version-managers.md](references/version-managers.md) gives: `../pipelex-integrate/SKILL.md` with the method, or `/pipelex-design` first without one.

## When something goes wrong

| Condition | Do this |
|---|---|
| A toolchain piece is missing, or `refused: missing-tool` or `node-too-old` | STOP and name it, first reading [references/version-managers.md](references/version-managers.md) for `node` or `uv` |
| The directory is not empty, or `refused: not-empty` | STOP and ask for another; never delete, move or write into it, and never offer to |
| `refused: no-key` | STOP and offer two ways, running neither until the user picks: a harness restarted from a shell that exports the key, or `--no-create` and a `<dir>/.env.local` the user writes in their own editor, then [references/uncreated-copy.md](references/uncreated-copy.md) |
| `refused: inside-template-checkout`, or an `origin` at `Pipelex/pipelex-method-apps` | STOP: that is the template, not a copy |
| any other `refused:`, `failed: write` or `failed: commit` | the line says what stands and names the fix: apply it when it is a value from the conversation, else relay it and ask; a git identity is the user's to set, never yours |
| `failed: create` | read the end of the log it named, then [references/uncreated-copy.md](references/uncreated-copy.md); never substitute a base URL the user did not declare |
| `make serve` says `refused: not-loopback` | report no URL, and relay the cause it names |
| any other `make serve` verdict | relay it; when it says the server was stopped, read `<dir>/.serve/server.log`'s tail, fix the cause and run `make serve` again; one still running is the user's to stop |
| A script says `refused:` | `usage`, `no-directory` and `not-a-repository` mean a wrong `<dir>` or step 3 before step 2; `nothing-to-commit`: the initializer wrote nothing in `<dir>`; read its output and rerun it; relay the others with git's message, since a permission, a git identity or a tracked `.env` is the user's to fix |

## Reference

- [references/uncreated-copy.md](references/uncreated-copy.md) — a copy of the method app that `make create` has not run in.
- [references/initializers.md](references/initializers.md) — before running an initializer.
- [references/version-managers.md](references/version-managers.md) — `node` or `uv` missing, or `node` below the floor.
- [references/github.md](references/github.md) — the repository on GitHub, before any `gh` command.
