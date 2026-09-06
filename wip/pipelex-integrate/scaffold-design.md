---
status: active
item: L-260906-8ac105
---

# Design — `pipelex-scaffold`: the front door to a project that does not exist yet

**Written 2026-09-06**, in the design session that widened this campaign from one skill to two. The shape was decided with Louis in that session and is not re-argued here: two skills rather than one (`pipelex-integrate` for an existing codebase, this one for a project that does not exist yet); a from-scratch project comes from one of our two GitHub-template starters or from the ecosystem's own initializer, never from a cookiecutter or copier template the plugin would have to carry; `pipelex-integrate` defers to a project that owns a codegen harness (`design.md` §4.12); and the name is `pipelex-scaffold`. **Status: active** — the decision boxes at the end, which settle the procedure and the smaller calls the implementation needs, were ratified as written on 2026-09-06, the day this document was drafted. The sibling document is [`design.md`](design.md); the tracker for both skills is [`plan.md`](plan.md). Ledger item `L-260906-8ac105`. File and line references were accurate on the writing date; verify them against the code before implementing.

## 1. What the skill is

`pipelex-scaffold` gives a user who has no project yet a project that is ready for `pipelex-integrate`. It has exactly two branches and carries no templates of its own:

- **One of our starters** when the user wants the opinionated shape: `pipelex-starter-js` for a web app whose forms are rendered from the methods' own contracts, `pipelex-starter-python` for a CLI or service that runs methods in the three execution modes. The skill acquires the template, commits it once as it came, then runs the clone's own `bootstrap` skill — the rename logic stays in the starters and is never duplicated here.
- **The ecosystem's own initializer** when the user wants their framework or a minimal project: `uv init --package`, `npm create next-app@latest`, `django-admin startproject`, whatever the framework documents. The skill runs it; it never assembles a project by hand.

Both branches share a tail: the env file and the key convention, the pristine commit that makes everything after it reviewable, and the hand-off — to `/pipelex-integrate` when a method exists, to `/pipelex-design` first when none does.

**What it is not.** It is not a template engine (no cookiecutter, no copier, no framework matrix of its own), not a bootstrap (the starters own theirs), not a runner or a dev-server launcher, not a deployer, and not `create-pipelex-app` — whether a CLI front door for users who do not work through an agent is still wanted is `L-260906-84bb41`, a decision, not this skill's scope. It is **MCP-free**: git, the starters' scripts and the ecosystem's initializers are all it needs, which puts it beside `pipelex-explain` and `pipelex-synthetic-inputs` and out of the `MCP_SKILLS` tuple in the tests.

## 2. Choosing the branch

The rule from `pipelex-integrate` applies: a cheap, reliable signal decides; an inconclusive one asks one question; nothing is guessed twice.

| Question | Signals, in order | When inconclusive |
| --- | --- | --- |
| **Language** | the user's word; the language the method's consumer is written in; a framework the user named | ask |
| **Which branch** | a **named framework** the starters do not carry (FastAPI, Django, Express, Hono, Remix, a plain library, a Lambda) → the initializer; **"minimal"**, **"no demo code"**, **"just a project"** → the initializer; a **web app people use in a browser**, forms, an upload flow → the JS starter; a **CLI, script, batch job, worker or service** in Python → the Python starter | one question offering the matching starter first, saying what it brings (durable runs, forms or CLI modes, codegen wiring, CI, its own `release` skill) and what it costs (demos to keep as references or strip) |
| **Where** | the directory the user named; **"here"** when the working directory is empty; else a kebab-case directory named after the project | ask; never write into a directory that exists and is not empty |
| **GitHub or local** | the user asked for a GitHub repository → `gh repo create --template`, after confirmation; otherwise a local clone with fresh history | local |

A starter clone that is already in the working directory and has not been bootstrapped — `package.json` still says `pipelex-starter-js`, or `pyproject.toml` still says `piper` — is **branch A entered at step 3**: acquisition already happened, and the skill goes straight to running the clone's bootstrap.

## 3. Branch A — one of our starters

1. **Prerequisites.** JavaScript: Node at or above the floor the starter's `package.json` `engines` names (22.12 at writing — the SDK is ESM-only and the starter's e2e specs `require()` it), and npm. Python: `uv` (the starter's Makefile installs and locks with it) and a Python inside the starter's `requires-python` range (3.11 to 3.14 at writing) that `uv python find` can see. Both: git. The GitHub branch also needs `gh` authenticated (`gh auth status`). A missing piece **stops** the skill with the exact thing missing and the starter README's own line about it; the skill never installs a toolchain.
2. **Acquire.**
   - **Local, the default.** `git clone --depth 1 https://github.com/Pipelex/<starter>.git <dir>`; read the template's version from its `package.json` / `pyproject.toml` and its head SHA; then detach from the template — remove the clone's `.git`, `git init -b main` — so that `git status`, `git remote` and a future push belong to the user's project and not to the template. This is what GitHub's "Use this template" button produces: a copy with no history and no remote. The starters' READMEs say "don't clone it directly" to humans for exactly that reason, and the fresh history is how the skill honours it.
   - **GitHub, on request.** `gh repo create <owner>/<name> --template Pipelex/<starter> --private --clone` (visibility is the user's call, asked, default private). Creating a repository on GitHub is an outward-facing action: the skill states the exact command and confirms before running it. GitHub writes the initial commit itself; the skill continues at step 3.
   - Both take the template's **default-branch head**, and the pristine commit below records the version and SHA it came from. Pinning a release tag is not offered unless the user asks; the starters cut releases, and a user who wants one names it.
3. **Commit the pristine template — exactly once.** `git add -A && git commit -m "Start from Pipelex/<starter> <version> (<sha>)"` from inside the directory. This is the one commit the skill makes, and it is load-bearing twice over: the Python starter's bootstrap renames the package directory with `git mv`, which refuses a path git does not track, and a committed baseline is what turns the bootstrap's edits into a diff the user can read before committing them. Nothing of the user's is in this commit — it is the template as it came.
4. **Run the clone's own bootstrap.** Read `<dir>/.claude/skills/bootstrap/SKILL.md` and follow it as written, with every command run from inside the project directory (the skill's cwd is wherever the harness was launched, so commands carry `-C <dir>` or a `cd <dir> &&`). Feed it what the conversation already holds — the project name, title, description, author, repository URL, license — so that it asks once, consolidated, for whatever is left, exactly as its Step 2 says. It dry-runs, previews, runs, re-syncs the lock file, runs the project's own checks (`make all` on JS; `make agent-check` and `make agent-test` on Python), and removes itself. Its rules stand unchanged: it never commits, its edits stay unstaged for the user's review (the Python renames are staged by `git mv`, which its own skill explains), and a red check is fixed, not skipped. The plugin skill adds nothing to that procedure and reimplements none of it. If the clone carries no bootstrap skill — a future template dropped it — the skill follows the README's "manual equivalent" list and says the template changed.
5. **The env file.** `cp .env.example .env.local` on the JS starter (Next.js reads `.env.local`), `cp .env.example .env` on the Python one (`python-dotenv`). Fill `PIPELEX_API_KEY` from the shell environment when it is set there, and leave it empty otherwise, telling the user where a key comes from (`app.pipelex.com`) and that the file is where it goes. The skill never prints a key and never asks for one in the conversation. `PIPELEX_BASE_URL` stays as the example ships it. Confirm the file is gitignored (both starters ignore it) before writing a key into it.
6. **Verify and hand off.** The bootstrap's own checks are the verification; the skill does not start `make dev`. The report (§5) names the demos the starter still carries and where the README's removal checklist is, and hands the user's method to `/pipelex-integrate`, which recognizes the starter's codegen harness and defers to it (`design.md` §4.12).

## 4. Branch B — the ecosystem's initializer

1. **Prerequisites** as in branch A, for the language chosen.
2. **Run the initializer, never assemble by hand.**
   - **A named framework** uses its documented initializer with its non-interactive flags where it has them — `npm create next-app@latest <dir> --ts --app --src-dir --eslint --use-npm --yes`, `uv init --package <dir>` then `uv add fastapi`, `django-admin startproject <name> <dir>`, and so on; the skill's `references/initializers.md` carries the invocations for the common ones. An initializer that only runs interactively is handed to the user to run (`! <command>` in the prompt runs it in the session), and the skill resumes when it is done.
   - **No framework named** takes the language's own minimal initializer: Python → `uv init --package <dir>`, which gives the import package `pipelex-integrate` wants and a console-script entry; TypeScript → `npm init -y`, then `npm install --save-dev typescript @types/node` and `npx tsc --init` with strict mode, ES modules and a `src/` root. Nothing beyond what those initializers write is authored by the skill.
3. **Version control and the pristine commit.** If the initializer did not `git init` (some do), `git init -b main`; then the one commit, `"Scaffold <framework or language> project"`, for the same reason as branch A: everything the user does next is a reviewable diff against it.
4. **The env file.** Write `.env.example` with the two lines the starters share (`PIPELEX_BASE_URL=https://api.pipelex.com`, `PIPELEX_API_KEY=`), add `.env` to `.gitignore` if it is not already ignored, and copy the example to `.env` with the same key rule as branch A.
5. **Hand off.** No SDK dependency is added and no empty `methods/` directory is created: `pipelex-integrate` adds `@pipelex/sdk` / `pipelex-sdk` when it writes the first call site, and creates `methods/<name>/` when it places the first bundle. A project with nothing to integrate yet has nothing Pipelex-shaped in it beyond the env convention, which is correct.

## 5. The shared tail — the report

The report says: what was created and where; which template or initializer it came from, at which version and SHA; that the skill made exactly one commit and what it contains; what the bootstrap changed and that those changes are uncommitted for review, in the bootstrap's own words; which env file was written and whether the key was filled from the environment or left for the user; the demos the starter still carries and where the README's removal checklist is (branch A); and the hand-off — `/pipelex-integrate` for a method that exists (a bundle elsewhere on disk is copied into the project by that skill, `design.md` §4.2), `/pipelex-design` first when none does.

One line in the report is easy to forget and matters: **the project's own instructions and skills load in a session started inside it.** Its `CLAUDE.md` / `AGENTS.md` and its `release` and `bump-*` skills are not in the current session, which began elsewhere; `cd <dir> && claude` (or the host's equivalent) is how they arrive. Until then `/pipelex-integrate` still works from here, because the workshop writes anywhere under the directory the harness was launched in and the new project sits there.

## 6. Mode and questions

Automatic by default, with the plugin's usual rules: an explicit user signal wins; a genuinely ambiguous branch is one question (§2), asked once; a project with every input given up front proceeds without re-asking. Two things always confirm: `gh repo create`, because it creates a repository on GitHub, and whatever the clone's bootstrap skill confirms on its own account. The pristine commit does not — it is on a directory the skill just created, holding the template as it came, and no user content is at stake.

## 7. Failure posture

| Condition | The skill |
| --- | --- |
| A toolchain piece is missing (Node below the floor, no `uv`, no git) | STOP, name the exact missing piece and the starter README's line about it; never install a toolchain |
| The target directory exists and is not empty | STOP, ask for another; never delete or write into it |
| `git clone` fails (network, permissions) | report git's error verbatim; nothing to clean up beyond an empty directory |
| `gh` is absent or not authenticated | fall back to the local clone and say the GitHub repository can be created later with `gh repo create --source .` |
| The clone carries no `bootstrap` skill | follow the README's manual list, say the template changed |
| The bootstrap's checks are red | the bootstrap's own rule: fix the cause and re-run; never hand off on red |
| An initializer is interactive with no non-interactive form | hand the command to the user to run in the session, resume after |
| `PIPELEX_API_KEY` is not in the shell environment | leave the value empty in the env file, say where a key comes from and where it goes; never ask for it in the conversation |
| The working directory is the template's own checkout (a `Pipelex/` remote) | STOP: this is the template, not a copy of it — acquire a copy |

## 8. Name, triggers and family wiring

**`pipelex-scaffold`**, model-invocable. Its description triggers on the greenfield phrasings — "start a new project with Pipelex", "I have a method and need an app around it", "create a Next.js app that runs my method", "set up a Pipelex project from scratch", "which starter should I use", "bootstrap a Pipelex project" — and stays silent on the existing-codebase phrasings `pipelex-integrate` claims ("use this method in my app", "call this from my code", "generate types"). It says in so many words that a user already standing in a fresh starter clone is served by that clone's own `/bootstrap`, which this skill runs for them (§2, the shortcut).

Family wiring, each one sentence: `pipelex-integrate`'s step 1 offers `/pipelex-scaffold` when it finds no project at all (`design.md` §5, §7); `pipelex-design`'s delivery step forks the same way — a codebase in the workspace → `/pipelex-integrate`, none → `/pipelex-scaffold`; the README's skill list, `CLAUDE.md`'s structure block and `docs/decisions.md` gain the skill, with the note that it is the plugin's third MCP-free skill.

## 9. Follow-ups, filed or to file

| Item | Repo | Relation | Why |
| --- | --- | --- | --- |
| `L-260906-84bb41` | workspace | related, decision | whether a `create-pipelex-app` CLI front door is still wanted for users who do not work through an agent |
| `L-260906-a2cd5b` | `pipelex-starter-python` | informational | the Python starter's `make codegen` needs a `pipelex` CLI the starter does not depend on; the report on a Python starter says so honestly and points at `/pipelex-integrate`, which writes into the harness's layout meanwhile (`design.md` §4.12) |
| `L-260906-aa5083` | `pipelex-starter-python` | informational | the Python starter lacks `AGENTS.md` and `add-method`; nothing in this skill waits on it |
| *to file at release* | both starters | docs | the READMEs' "Use this template" sections should name `/pipelex-scaffold` as the agent front door beside the button and `/bootstrap` — filed when the skill ships, so the pointer never precedes the thing it points at |

## Decision boxes for ratification

| Box | Ruling | Ratified? |
| --- | --- | --- |
| **A — Two branches, no templates of its own** | Our starter or the ecosystem's initializer; MCP-free; the language defaults for branch B are `uv init --package` and `npm init` + `tsc --init` (§1, §4) | Yes, as written — 2026-09-06 |
| **B — Acquisition** | Local clone with fresh history by default, matching what the template button produces; `gh repo create --template` only on request, confirmed, visibility asked; default-branch head with version and SHA recorded (§3 step 2) | Yes, as written — 2026-09-06 |
| **C — Exactly one commit** | The pristine template or scaffold, before the bootstrap, so `git mv` works and the bootstrap's edits are a reviewable diff; everything after stays uncommitted under the bootstrap's own rules (§3 step 3, §4 step 3) | Yes, as written — 2026-09-06 |
| **D — Bootstrap is delegated** | The clone's own `bootstrap` skill, read from its `SKILL.md` and run from inside the project with the inputs already known; the README's manual list as the fallback; an un-bootstrapped clone in the working directory enters here (§2, §3 step 4) | Yes, as written — 2026-09-06 |
| **E — The env file and the key** | The starter's own env file; the key filled only from the shell environment, never printed, never asked in the conversation; the base URL untouched (§3 step 5, §4 step 4) | Yes, as written — 2026-09-06 |
| **F — Nothing Pipelex-shaped beyond the env** | No SDK dependency and no empty `methods/` from this skill; `pipelex-integrate` adds both when there is something to integrate (§4 step 5) | Yes, as written — 2026-09-06 |
| **G — The session note** | The report says the project's own instructions and skills load in a session started inside it, and that `/pipelex-integrate` works from here meanwhile (§5) | Yes, as written — 2026-09-06 |
| **H — Verification** | The bootstrap's own checks on branch A, the initializer's result and a clean `git status` after the pristine commit on branch B; the skill never starts a dev server (§3 step 6) | Yes, as written — 2026-09-06 |
| **I — Name and triggers** | `pipelex-scaffold`, model-invocable, greenfield phrasings only, with the fresh-clone shortcut named in the description (§8) | Yes, as written — 2026-09-06 |
