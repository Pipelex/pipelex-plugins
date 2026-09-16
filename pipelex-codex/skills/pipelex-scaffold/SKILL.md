---
name: pipelex-scaffold
description: Start a new project that will call MTHDS methods through Pipelex, in TypeScript or Python — from a Pipelex template or from the ecosystem's own initializer. A TypeScript web app for a method comes from the method-app template, created for that method in one command and left running with its URL reported; every other project is handed to /pipelex-integrate. Use when the user says "start a new project with Pipelex", "I have a method and need an app around it", "create a Next.js app that runs my method", "build me a web app for this method", "set up a Pipelex project from scratch", "new Python CLI for this method", "which starter should I use", "bootstrap a Pipelex project", or wants a codebase where none exists yet. Also use when the user stands in a fresh copy of a Pipelex template not yet made theirs — this skill finishes it with the template's own gesture. Not for adding Pipelex to code that already exists: that is /pipelex-integrate.

---

# Scaffold a project for Pipelex methods

Give a user who has no project yet a project that runs their method, or one that is ready for `/pipelex-integrate`. This skill has exactly two branches and carries no templates of its own:

- **A Pipelex template** when the user wants the opinionated shape. For a web app around a method, in TypeScript, that is **the method app**: the `webapp-js/` directory of `pipelex-method-apps`, a Next.js app that ships no method. You copy the directory, commit it once as it came, and run the copy's **own** `make create` with the user's method, which names the project after the method, scaffolds the method's form and result view, writes the env file and runs the project's checks. For a CLI or a service in Python, it is `pipelex-starter-python`. `pipelex-starter-js`, the gallery of worked examples the method app was extracted from, is acquired only when the user names it. A starter is cloned, committed once, then renamed by the clone's **own** `bootstrap` skill. The create gesture and the rename logic live in the templates and are never reimplemented here.
- **The ecosystem's own initializer** when the user wants their framework or a minimal project: `uv init --package`, `npm create next-app@latest`, `django-admin startproject`, whatever the framework documents. You run it; you never assemble a project by hand.

Every path makes one pristine commit, which makes everything after it reviewable. **The method app ends with the app running**: the method is already in the page, so the dev server is started and the report leads with its URL. The starters and the initializer end with an env file that follows the starters' convention and the hand-off — to `/pipelex-integrate` when a method exists, to `/pipelex-design` first when none does.

**What this skill is not.** Not a template engine (no cookiecutter, no copier, no framework matrix of its own), not a bootstrap (the templates own theirs), not a runner, not a deployer. The one server it starts is the method app's own dev server, at the end of that path. It needs no MCP tool and never handles an API key itself: git, the templates' own gestures and the ecosystem's initializers are all it uses, and the method app's gesture reads the key where the user put it.

## Choosing the branch

A cheap, reliable signal decides; an inconclusive one asks one question; nothing is guessed twice.

| Question | Signals, in order | When inconclusive |
|---|---|---|
| **Language** | the user's word; the language the method's consumer is written in; a framework the user named | ask |
| **Which branch** | a **named framework** the templates do not carry (FastAPI, Django, Express, Hono, a plain library, a Lambda) → the initializer; **"minimal"**, **"just a project"**, **"no template"** → the initializer; **`pipelex-starter-js`**, "the starter", "the gallery" or "with the examples" named → the gallery; a **web app people use in a browser** in TypeScript — forms, an upload flow, "an app for my method" — → the method app, and **"no demo code"** there too, since it ships none; a **CLI, script, batch job, worker or service** in Python → the Python starter; "no demo code" in Python → the initializer | one question offering the matching template first and the initializer beside it, saying what the template brings — the method app: a page rendering the method's form and result, durable runs, codegen wiring and CI, created for the method in one command and left running; the Python starter: CLI modes, codegen wiring, CI and its own `release` skill, with demos to keep as references or to strip. **The gallery is never offered**: it is acquired only when the user names it |
| **Where** | the directory the user named; **"here"** when the working directory is empty — **and a directory whose only entry is `.git` is empty for this rule**, because `mkdir my-app && cd my-app && git init` is an ordinary way to arrive here and a repository the user made is not work of theirs to write over: branch B runs its initializer in the directory as it stands and leaves that repository alone — it does **not** re-run `git init` there, since Step 3's test finds `<dir>` is already its own repository — while branch A acquires beside it and moves in, so the repository already there goes on standing either way (Step 2); else a kebab-case directory named after the project | ask; never write into a directory that exists and is not empty, and never offer to move, delete or merge what it holds to make room — the answer is another directory. **A lone `.git` is the only entry that does not make a directory non-empty, and that is a ruling about `.git` and nothing else** — not a class of files you may decide to overlook. Every other entry still refuses, `.DS_Store`, `.idea/`, `.vscode/` and `Thumbs.db` included: judging which of a user's files matter is the thing this rule exists to forbid, and a list that grows by guesswork is how it would come back. The rule is about **a directory you are creating a project in**, which is why the fresh-clone shortcut below is not an exception to it: there the project is already there and you are finishing it, not writing over someone's work |
| **GitHub or local** | the user asked for a GitHub repository → `gh repo create`, after confirmation (Step 2 says which form); otherwise a local copy with fresh history | local |

**The method app needs the method first.** It ships no method, and `make create` is the gesture that makes a copy the user's, so a user with no method yet goes to `/pipelex-design` first and comes back with the bundle. Nothing is copied meanwhile. The method is a bundle — a `.mthds` file or a directory of them — a catalog id (`mt_…`), or a published package address (`github.com/<owner>/<repo>[/<package>][@<tag>]`).

**The method app's directory is named after the method** when the user named none: a bundle's `domain`, read from its `.mthds` file and kebab-cased, or a package address's last path segment without its tag, kebab-cased — the names `make create` gives the project. A catalog id carries no name you can read without a call, so ask.

**The fresh-clone shortcut.** A copy of a template already in the working directory that has not been made the user's is branch A entered at step 4: acquisition already happened. Do not clone again. The copy says what it is:

- **The method app**: `package.json` still says `pipelex-method-webapp-js`, and `scripts/create.mts` is still there.
- **A starter**: `package.json` still says `pipelex-starter-js`, or `pyproject.toml` still says `name = "piper"`.

**Make sure the copy is a repository of its own before reading anything from git.** A copy is often made without git (the method app's README copies the directory and runs `git init` afterwards), and a copy may sit inside another repository, whose `HEAD` and `origin` git would read instead. So test it, as branch B's step 3 does, and initialize only where the test fails:

```bash
[ "$(git -C <dir> rev-parse --show-toplevel 2>/dev/null)" = "$(cd <dir> && pwd -P)" ] || git -C <dir> init -b main
```

Then read the copy's `origin`: one pointing at `Pipelex/pipelex-method-apps` or `Pipelex/pipelex-starter-…` is the template's own checkout, which the last row of the failure table stops on. When the repository has no commit yet (`git -C <dir> rev-parse -q --verify HEAD` prints nothing), make step 3's pristine commit first, because the gesture's or the bootstrap's changes are reviewable only against it, and the Python bootstrap's `git mv` refuses a path git does not track. The directory is the user's, so that commit confirms like the one the Mode section describes.

[references/starters.md](references/starters.md) compares the templates and carries every command below; [references/initializers.md](references/initializers.md) carries the initializers.

**Every placeholder is substituted as one shell word.** `<dir>`, `<port>`, `<owner>/<name>` and the rest are typed into commands the shell reads first, so a value holding a space or a character the shell interprets goes in single quotes (`'my app'`), with a quote inside spelled `'\''`, unless the block already quotes the placeholder, as `METHOD='<method>'` does. Unquoted, `mkdir -p my app` makes two directories, and a chain goes on in the wrong one.

## Mode

Automatic by default, with the plugin's usual rules: an explicit user signal wins ("just do it" → automatic; "walk me through" → interactive); a genuinely ambiguous branch is one question, asked once; a request that gave every input up front proceeds without re-asking. Two things always confirm, in every mode: **`gh repo create`**, because it creates a repository on GitHub, and whatever the clone's bootstrap skill confirms on its own account. The pristine commit does not need confirmation **on a directory this skill created** — it holds the template as it came, and no user content is at stake. **The acquisition into a directory that already held a repository is the exception**, and it is a third thing that always confirms: there the commit lands on the user's branch, on top of their history, and `add -A -- .` records whatever their worktree was already showing along with the template (Step 3). None of the three grounds above holds, so state what will be staged and what it will land on, and ask — in every mode.

On the method app, interactive mode runs `make create` with `DRY_RUN=1` first and shows the user the identity and the plan it prints; automatic mode runs it directly, because its read-only half refuses before it changes a tracked file. Either way, the first run on a fresh copy installs the dependencies before anything else, which takes minutes, writes `node_modules/`, and lets the template's husky point the repository's `core.hooksPath` at the project's hooks. A dry run is not free, and a repository the user made gets that setting too.

## Branch A — a Pipelex template

### Step 1: Prerequisites

Check before touching anything, and **stop** on a missing piece with the exact thing missing and the template README's own line about it. Never install a toolchain — but a runtime the machine already has and only the `PATH` is missing is not a missing piece: when `node` or `uv` is absent while a version manager on the machine carries one (`nvm`, `fnm`, `volta`, `asdf`, `mise`), activate it for this work and say in the report which one you used and that the user's own shell may not have it. Stop only when no usable runtime can be reached that way.

**Activating it means resolving it to an absolute path, not sourcing a shell.** Your shell state does not survive from one command to the next — each one starts again from the user's profile, which is the profile that did not have the runtime — so `. nvm.sh` or `eval "$(fnm env)"` in one call buys nothing in the next. Resolve the binary once (`ls "$NVM_DIR"/versions/node/*/bin/node`, `volta which node`, `mise which node`, `asdf which node`, `fnm exec --using=<v> -- which node`), keep that directory, and prefix **every** later command with it — `PATH="<that dir>:$PATH" …` — the method app's `make create` and `make dev`, the clone's bootstrap and its `make all` / `make agent-check` included, because those are separate commands too. Verify the runtime answers under that prefix **before** step 2, so a machine you cannot actually reach stops while nothing has been created; discovering it at step 4 has already spent the pristine commit.

Three things this clause does not license. **A shim is not a runtime**: `asdf` and `mise` put a `node` on the `PATH` that exists and then fails with "no version set", so the test is that `node --version` *answers*, not that the binary resolves — and that case is a stop, not a manager to activate. **The floor still applies**: a manager holding Node 18 does not satisfy the template's `engines` floor, and "a runtime the machine already has" never means a version below it. And **`volta` and `mise` install on first use** — `volta run`, `mise x` and `mise use` will fetch a version they do not have — which is the toolchain install this step forbids: use only a version the manager already holds, and stop rather than let it download one. Note too that `nvm`, `fnm` and `volta` manage Node alone and can never supply `uv`.

- **JavaScript**: Node at or above the floor the template's `package.json` `engines` field names (`node --version`; 22.12 at writing — the SDK is ESM-only and the templates' e2e specs `require()` it), and `npm`. The method app also needs `make`, `curl` and `lsof`: without `lsof` the template's `port-check` passes whatever holds the port, and step 6 can neither prove where its server listens nor stop it.
- **Python**: `uv` on the PATH (the starter installs and locks with it) and a Python inside the starter's `requires-python` range that `uv python find` can see (3.11 to 3.14 at writing).
- **Both**: `git`. The GitHub form also needs `gh` authenticated — `gh auth status`.

**The method app also needs a key its gesture can read.** `make create` reads `PIPELEX_API_KEY` from the shell environment, or from an `.env.local` already in the project, and refuses without one. Test the shell before step 2 (`[ -n "${PIPELEX_API_KEY:-}" ] && echo set || echo unset`). When it is unset, say so before anything is created, and offer the two ways a key reaches the gesture without crossing the conversation: the user restarts the harness from a shell that exports it, or you carry on through step 3 and the user writes `<dir>/.env.local` themselves before you run step 4 — `cp .env.example .env.local`, then the key and the base URL of the plane that issued it, typed in their own editor. The gesture never touches an `.env.local` that already exists. The base URL follows the same path: the gesture runs against the plane the shell declares, or that file, and against production when neither declares one.

### Step 2: Acquire the template

#### The method app

The template is one directory of the `pipelex-method-apps` repository, and a project is a copy of that directory alone: the repository's root files — its own README, `VERSION`, the family's Makefile and workflows — are not part of it. So nothing is cloned into `<dir>`. The chain clones the repository shallow into a temporary path beside `<dir>`, reads the family's identity, copies `webapp-js/` in, and initializes a repository only where there is none. One chain serves a directory that does not exist, an empty one, and one whose only entry is `.git`:

```bash
mkdir -p <dir> && dir=$(cd <dir> && pwd) || exit 1
case "$(ls -A "$dir")" in ""|.git) ;; *) exit 1 ;; esac
tmp=$(mktemp -d "$(dirname "$dir")/.pipelex-method-apps-XXXXXX") || exit 1
git clone --depth 1 https://github.com/Pipelex/pipelex-method-apps.git "$tmp" || { rm -rf "$tmp"; exit 1; }
git -C "$tmp" rev-parse HEAD                     # the family SHA, for the commit message
cat "$tmp/VERSION"                               # the family version, for the commit message
[ -f "$tmp/webapp-js/package.json" ] || { echo "the default branch carries no webapp-js/" >&2; rm -rf "$tmp"; exit 1; }
case "$(ls -A "$dir")" in ""|.git) ;; *) rm -rf "$tmp"; exit 1 ;; esac
cp -R "$tmp/webapp-js"/. "$dir"/ || { rm -rf "$tmp"; exit 1; }
rm -rf "$tmp"
[ -e "$dir/.git" ] || git -C "$dir" init -b main
```

It is the starters' acquisition beside the directory, below, and the properties that make that one safe hold here for the reasons given there. The destination is resolved before its parent is taken, so a `<dir>` spelled `.` keeps the temporary path a sibling. No `rm -rf` addresses a path under `<dir>`. `cp -R "$tmp/webapp-js"/. "$dir"/` carries the entries beginning with a dot (`.gitignore`, `.env.example`, `.claude/`, `.husky/`). The directory is read once before anything is fetched and once more right before the copy, and anything but nothing or a lone `.git` stops the run with nothing copied and the temporary path removed. The chain goes out as one command. **The last line initializes only a directory with no repository of its own**, so a repository the user made goes on standing, and the pristine commit lands on their branch, as Step 3 says.

**The `webapp-js/` test is load-bearing.** The copy takes the default branch's head, and a head that does not carry the directory would otherwise copy nothing and report success. Stop there, say what the clone lacked, and do not fall back to the gallery or to another directory of the repository.

#### A starter

**Local, the default.** Clone shallow, read the template's identity, then detach from it:

```bash
git clone --depth 1 https://github.com/Pipelex/<starter>.git <dir> || exit
git -C <dir> rev-parse HEAD                      # the template SHA, for the commit message
# the template version: package.json "version" (JS) or pyproject.toml version (Python)
rm -rf <dir>/.git && git -C <dir> init -b main
```

The `|| exit` on the clone is not decoration: the line below it deletes a `.git` directory, and if the clone never ran — a network failure, or `<dir>` already existing — that `rm -rf` finds whatever `.git` is actually at that path. On a directory the skill just created it destroys nothing; on a repository of the user's it destroys their history irrecoverably. Run the destructive line only behind a clone that succeeded, and never type it on a path you have not just created.

The clone's `.git` is removed on purpose: it is the template's history and remote, and leaving it would make `git status` and a future `git push` belong to Pipelex's template rather than to the user's project. This is exactly what GitHub's "Use this template" button produces — a copy with no history and no remote — and it is why the starters' READMEs tell humans not to clone directly. Fresh history is how you honour that.

**Local, into a directory that already holds a repository.** The "Where" rule reads a directory whose only entry is `.git` as empty, and `git clone` cannot serve it: git refuses any destination already holding a `.git` and stops with `destination path '<dir>' already exists and is not an empty directory`. So acquire **beside** the directory and move in. The end state is the one the default recipe reaches — the template in `<dir>`, no template history, no Pipelex remote — and the repository the user made goes on standing instead of being replaced:

```bash
dir=$(cd <dir> && pwd) || exit 1
tmp=$(mktemp -d "$(dirname "$dir")/.pipelex-starter-XXXXXX") || exit 1
git clone --depth 1 https://github.com/Pipelex/<starter>.git "$tmp" || { rm -rf "$tmp"; exit 1; }
git -C "$tmp" rev-parse HEAD                     # the template SHA, for the commit message
# the template version: package.json "version" (JS) or pyproject.toml version (Python)
rm -rf "$tmp/.git" || { rm -rf "$tmp"; exit 1; }
[ "$(ls -A "$dir")" = ".git" ] || { rm -rf "$tmp"; exit 1; }
cp -R "$tmp"/. "$dir"/ || { rm -rf "$tmp"; exit 1; }
rm -rf "$tmp"
```

**The first line resolves the destination, and that is what keeps the temporary path a sibling rather than a child.** `<dir>` is very often `.` here: `mkdir my-app && cd my-app && git init` is the "Where" rule's own account of how a user arrives at a directory holding nothing but `.git`, and they then ask for the project *here*. `dirname .` is `.`, so deriving the parent from the spelling would put the temporary directory **inside** the destination, where the `ls -A` line below finds it sitting beside `.git` and refuses — every time, on exactly the case this section exists to serve. Resolving to an absolute path first also pins the destination for the rest of the chain, so no later line can be re-read against a working directory that has moved, and it is what lets every mention below be quoted: a name with a space reaches `cp` whole instead of arriving as two arguments.

**No `rm -rf` here ever addresses a path under `<dir>`, and that is the ordering rather than a coincidence.** The template's history is discarded while the clone is still at a path `mktemp` made for this one command, so the destructive line is spent before anything moves: the only two paths any delete is pointed at are `"$tmp/.git"` and `"$tmp"`. Compare the default recipe, where the same line runs on `<dir>` itself and `|| exit` is the whole thing standing between it and a user's history. Here there is nothing for a guard to hold, which is what makes this the form you may aim at a directory holding somebody's repository.

**`cp -R "$tmp"/. "$dir"/`, and never `mv "$tmp"/* "$dir"/`.** The glob matches no entry beginning with a dot, so the naive move leaves `.gitignore`, `.env.example`, `.github/` and `.claude/` behind, exits `0`, and the line after it deletes the temporary directory they are still sitting in — a starter arriving without its `.gitignore`, whose pristine commit then swallows `node_modules/`, reported as a success. The trailing `/.` copies the directory's *contents*, dotfiles included, with no shell globbing involved at all. Confirm it with `ls -A "$dir"` after the copy rather than trusting the form.

**The `ls -A` line is the "Where" rule read again, against the copy.** It is not the decision — the "Where" question settled that — it is the last look before anything lands, put next to the copy so nothing can change between the two. It admits exactly one entry, `.git`, which the clone has not had since the line above: a collision is therefore impossible rather than merely unlikely, and the template can only add to the directory. Anything else — `.git` beside a file of the user's, a `.DS_Store`, a `README.md` they wrote — stops here with nothing copied, the temporary path removed and the directory as it was. A discarded shallow clone is the cheap half of that trade. Nothing of the user's is overwritten, moved or deleted to make room, here or anywhere.

**The chain goes out as one command.** The guards hold only inside one shell — the same reason the `|| exit` above is load-bearing, stated in full in [references/starters.md](references/starters.md) — and split across separate calls this one loses its cleanup too, leaving the temporary directory beside the user's project with no line left to remove it.

**Nothing is initialized here.** The default recipe ends `git init -b main` because it has just deleted the only repository at that path. This one ends on the user's repository, their branch and their remote, which is the whole point of taking the long way round.

#### GitHub, on request

**A starter** is a GitHub template repository. When the user asked for a repository on GitHub:

```bash
gh repo create <owner>/<name> --template Pipelex/<starter> --private --clone
```

`--clone` takes no destination argument: it clones into `./<name>` under the current working directory, so for this form `<dir>` **is** `<name>` — either choose the repository name to match the directory the "Where" question settled, or rebind `<dir>` to `./<name>` before step 4, because every step after this one addresses `<dir>` literally. Visibility is the user's call: ask, default `--private`. Creating a repository on GitHub is outward-facing, so **state the exact command and confirm before running it**, in every mode. GitHub writes the initial commit itself — skip step 3 and continue at step 4. If `gh` is absent or not authenticated, fall back to the local clone and say the repository can be created later with `gh repo create --source .`.

**The method app** is a directory, not a template repository, so `--template` has nothing to point at. Copy it locally as above and make the pristine commit, then create the repository from the copy — `gh repo create <owner>/<name> --private --source <dir> --remote origin` — confirmed in every mode like the other form, visibility asked. It pushes nothing; the user pushes once they have committed what `make create` changed.

Every form takes the template's default-branch head. Do not offer a release tag unless the user asks for one.

### Step 3: Commit the pristine template — exactly once

```bash
git -C <dir> add -A -- . && git -C <dir> commit -m "Start from Pipelex/<template> <version> (<sha>)" -- .
```

`<template>` is `pipelex-method-apps/webapp-js`, `pipelex-starter-js` or `pipelex-starter-python`; for the method app, the version is the family's `VERSION`. This is the **one commit this skill makes**, and it is load-bearing twice over: the Python starter's bootstrap renames the package directory with `git mv`, which refuses a path git does not track, and a committed baseline is what turns `make create`'s or the bootstrap's edits into a diff the user can read before committing them. Nothing of the user's is in it — it is the template as it came. One qualification on the acquisition into a directory that already held a repository: the commit lands on the user's branch, on top of their history rather than opening a new one, and `add -A -- .` also records whatever deletion their worktree was already showing — their own pending change and not one this skill made, so name it in the report instead of undoing it. That is the commit the Mode section sends back for confirmation, and this is what to put in front of the user: `git -C <dir> status --short` before staging says what will ride along, and it is the difference between a baseline commit and a line in their history that says "Start from Pipelex/…" over a change they made.

### Step 4: Make the project the user's

#### The method app: run its create gesture

```bash
log=$(mktemp "${TMPDIR:-/tmp}/pipelex-create-XXXXXX") || exit 1
make -C <dir> create METHOD='<method>' > "$log" 2>&1; rc=$?
tail -n 40 "$log"; echo "make create exited $rc; the whole log is $log"
```

`<method>` is what the user has. A bundle, whether a `.mthds` file or a directory of them, is **given as an absolute path**, because the gesture reads a relative path from the directory make runs in, which is `<dir>` and not where the user stood; the gesture copies it into the project. A catalog id is `mt_…`, and a package address is `github.com/<owner>/<repo>[/<package>][@<tag>]`. Add `NAME='…'`, `TITLE='…'` and `DESCRIPTION='…'` only when the conversation already holds them or the user asked for something other than what the method carries, since the gesture derives all three from the method. Add `AUTHOR_NAME`, `AUTHOR_EMAIL`, `REPO_URL` and `LICENSE` only when the user gave them, because nothing is invented. `METHOD_NAME`, `PIPE` and `LABEL` answer a refusal that names them. Every value goes in single quotes, with a quote inside one spelled `'\''`, because the shell reads the line before make does.

What the gesture does is the template's to say — `<dir>/docs/create.md`, until the gesture removes that document along with itself — and none of it is reimplemented here. It fetches the method once, scaffolds its slice, runs the template's bootstrap with the values it derived, writes `.env.local` with exactly one base-URL line, re-syncs the lock file, runs `make all`, and removes the bootstrap once that is green. It commits nothing. Give the command several minutes: on a fresh copy it installs the dependencies, and it ends with a production build. The gesture names variables and never prints their values, so the log's tail is safe to read. The `.env.local` it wrote is not: the rules of the env-file step below hold for it too.

- **A refusal in its read-only half** changes no tracked file, so the gesture can run again; the dependencies it installed first stay, and the next run skips that install. Relay the message, supply a value it asks for from the conversation or by asking the user once, and re-run. A refusal naming a capability the API does not serve means the plane the gesture ran against does not serve what codegen needs yet. Say so, point at the template README's line on which plane does, and stop there: never substitute a base URL the user did not declare, because a key is refused by every plane but the one that issued it.
- **A failure after the scaffold** cannot be undone by running the gesture again, because the copy has become a project and the gesture refuses it. Fix the cause, never by editing `src/generated/`, then run the steps its message names (`npm install --package-lock-only`, `make all`, `rm -rf .claude/skills/bootstrap`). A red `make all` is fixed, never handed off.

#### A starter: run the clone's own bootstrap

Read `<dir>/.claude/skills/bootstrap/SKILL.md` and follow it as written. The project's skills are not loaded in this session — it began elsewhere — so read the file; do not look for a `/bootstrap` command. Run every command it gives from inside the project directory (`cd <dir> && …`, or `-C <dir>`), because that skill assumes it is standing in the repo root.

Feed it what the conversation already holds — the project name, title, description, author, repository URL, license — so that it asks once, consolidated, for whatever is left, exactly as its own Step 2 says. It dry-runs, previews, runs, re-syncs the lock file, runs the project's own checks (`make all` on JS; `make agent-check` and `make agent-test` on Python), and removes itself. Its rules stand unchanged: it never commits, its edits stay uncommitted for the user's review (the Python renames are staged by `git mv`, which its skill explains), and a red check is fixed, never skipped. **Add nothing to that procedure and reimplement none of it.** If the clone carries no bootstrap skill — a future template dropped it — follow the README's "manual equivalent" list and say that the template changed.

### Step 5: The env file — a starter only

The method app's gesture wrote `.env.local` in step 4, or kept the one the user wrote, so on the method app go straight to step 6. On a starter:

```bash
cp -n <dir>/.env.example <dir>/.env.local   # JS: Next.js reads .env.local
cp -n <dir>/.env.example <dir>/.env         # Python: python-dotenv reads .env
```

`-n` because this is the one step that can destroy something of the user's. On the fresh-clone shortcut the directory is one they were already working in, and a plain `cp` would overwrite an `.env.local` they had filled with their own key — the skill's whole posture is that nothing of the user's is ever cleared, and an env file is the most expensive thing in the tree to lose. An existing env file is left exactly as it is; read whether it already carries a key with the file-side test below, and say in the report that you kept theirs, base URL and all.

Fill `PIPELEX_API_KEY` **from the shell environment when it is set there**, and leave it empty otherwise, telling the user where a key comes from and that this file is where it goes — `app.pipelex.com` when the file points at production, and what the report below says when it does not. **Never print a key, and never ask for one in the conversation.** Test for it without printing it — `[ -n "${PIPELEX_API_KEY:-}" ] && echo set || echo unset`.

**`PIPELEX_BASE_URL` comes from the shell too, with a key or without one.** Whenever this step writes the env file, which it does only when the file carries no key of the user's, a `PIPELEX_BASE_URL` that is set and non-empty in the shell is copied into it whether or not the key is, tested the same way (`[ -n "${PIPELEX_BASE_URL:-}" ] && echo set || echo unset`), because a base URL the shell exports is the plane the user has declared — a keyless self-hosted runner, which the Python starter's own example documents at `http://127.0.0.1:8081`, included. Left as the example ships it, that line pairs a dev or staging key with production's URL, since a key is refused by every plane but the one that issued it, or points a keyless self-hosted project at production — which this session never notices, because the SDK reads the process environment, and which the project meets the first time something reads the file instead: `python-dotenv` in a plain run, a Makefile that includes it, a new terminal. A file that already carried a key of the user's keeps both of its lines untouched, and a shell that sets neither variable leaves the file exactly as the example shipped it.

**The value moves only through a shell that expands the variable itself, and never through you.** That holds for the base URL exactly as for the key, because the env file holds the key and every rule below is about the file. A redirection is safe precisely because the shell does the expanding and only the variables' *names* are transcribed. The whole write is one command, run once for the env file (`.env` in place of `.env.local` on Python):

```bash
grep -q '^PIPELEX_API_KEY=.\+' <dir>/.env.local || [ -z "${PIPELEX_API_KEY:-}${PIPELEX_BASE_URL:-}" ] || {
  printf '\n# Copied from the shell environment; a later line overrides an earlier one.\n' >> <dir>/.env.local &&
  { [ -z "${PIPELEX_API_KEY:-}" ] || printf 'PIPELEX_API_KEY=%s\n' "$PIPELEX_API_KEY" >> <dir>/.env.local; } &&
  { [ -z "${PIPELEX_BASE_URL:-}" ] || printf 'PIPELEX_BASE_URL=%s\n' "$PIPELEX_BASE_URL" >> <dir>/.env.local; }
}
```

**Append only when the file does not already carry a key**, which is the other half of the `-n` above. On the fresh-clone shortcut the file is one the user may have filled themselves, and an unconditional append puts a second assignment *after* theirs — every dotenv reader resolves a repeated name to the later line, so their working key is silently replaced by whatever the shell happened to export, while the report tells them you kept theirs. **The one test on the file's key decides whether anything is written, which is why both appends sit inside its braces and the command goes out whole.** The URL cannot carry a guard of its own: the example ships its line non-empty, so a presence test on the URL always finds one, and the file's key test repeated as a second command can find the key the first command just wrote and skip the URL. The test after it, on the two variables together, is empty only when the shell sets neither, and it is what keeps the comment from going out alone: the leading newline and the comment are written once, whichever of the two lines follows them, and nothing at all is appended when there is nothing to copy. The later assignment is appended rather than the example's line rewritten, because a repeated name resolving to the later line is what the key already relies on and `sed -i` takes different arguments on BSD and GNU; the leading newline keeps the new lines off the end of a file whose last line has none, and the comment tells a person reading the file why the example's URL is followed by another.

A file-editing tool is the one form that cannot be made safe, whatever it is called — it takes a **literal** string, so you would have to know the value to pass it, and a tool call's parameters are the transcript. So: no file-editing tool on the env file, no `env | grep PIPELEX`, no `echo $PIPELEX_API_KEY` and no echoing the base URL either, no command substitution in a message, and **no reading the env file back** once written — `cat .env.local`, a `grep` over it, or opening it to check your work is the reflex after writing and the first move when a later step fails, and it puts the key in the transcript just as surely. To confirm the write landed, test the file the same way you tested the environment: `grep -q '^PIPELEX_API_KEY=.\+' <dir>/.env.local && echo filled || echo empty` for the key, and, when the shell set a base URL, `grep -qxF "PIPELEX_BASE_URL=$PIPELEX_BASE_URL" <dir>/.env.local && echo copied || echo missing`. A key in the transcript is a key to rotate, and it is not yours to spend.

A value that passed the test is copied verbatim and never inspected, so say in the report that it was taken from the environment **and not validated** — a placeholder someone exported once passes a presence test and fails the first run, and this skill never calls the API, so it cannot tell the difference. **The report names the plane the file points at, without printing the URL**, and reads whether a copied URL is the example's production URL by a test rather than an echo: `[ "${PIPELEX_BASE_URL%/}" = https://api.pipelex.com ] && echo production || echo other`. When the base URL came from the environment together with the key, say so, and say whether it is production's. When the key came from the environment with no base URL beside it, or the shell set neither, say the file points at production as the example ships it. **When the base URL came from the environment without a key and is not production's, say the file points at another plane, and warn that a key from `app.pipelex.com` is production's and will be refused there — a key for that plane goes on the file's `PIPELEX_API_KEY=` line.** When it came without a key and is production's, say the file points at production and that its key comes from `app.pipelex.com`. Confirm the file is gitignored before writing a key into it — both starters ignore it, but check.

### Step 6: Start the app, or hand off

#### The method app: start the dev server and prove the page answers

`make create`'s `make all` is the verification. Then start the app. The template serves on port 4300, and its `port-check` target says whether a port is free and, when it is not, which process in which directory holds it:

```bash
make -C <dir> port-check APP_PORT=4300
```

A refusal naming another directory is another app: leave it alone, try 4301, then the next port up, and use the first one the check accepts. A refusal saying the port **is already served by this checkout** is this project's own server, not a holder to step around. When this step started it, on an attempt whose page did not answer, stop it with the report's stop command and take the same port again. When the user started it, say so and ask whether they stop it or you take the next port up. **Never start a second server while one this step started still runs**, because the report's stop command names one port.

Then start the server detached, bound to this machine alone, so that it outlives the command that started it, make one request to the page, and read where the server listens:

```bash
log=$(mktemp "${TMPDIR:-/tmp}/pipelex-dev-XXXXXX") && page=$(mktemp "${TMPDIR:-/tmp}/pipelex-page-XXXXXX") || exit 1
nohup make -C <dir> dev APP_PORT=<port> APP_HOST=127.0.0.1 > "$log" 2>&1 &
curl -sS -o "$page" -w '%{http_code}\n' --retry 60 --retry-delay 1 --retry-connrefused --retry-max-time 120 --max-time 120 "http://localhost:<port>/"
grep -o '<title>[^<]*</title>' "$page"; echo "server log: $log"
lsof -nP -iTCP:<port> -sTCP:LISTEN | awk 'NR > 1 { print "listening on " $9 }' | sort -u
```

**The server listens on this machine alone.** The page's Server Actions run the method with the key in `.env.local` and do not check who is calling, so a server reachable from the network lets anyone on it spend that key. `APP_HOST=127.0.0.1` is the template's switch for it, and the last line proves the switch took: every `listening on` line must name `127.0.0.1:<port>` or `[::1]:<port>`. A `*:<port>`, any other address, or no line at all means this copy's `make dev` ignored the switch. Stop the server at once with the report's stop command, report no URL, and say that this copy's `make dev` listens on every interface, which the template's newer versions do not.

The retries wait out the server's start and the first compilation of the page, for two minutes at most. A `200` under the project's title is the proof, since the page is the method's form. Anything else, including no answer once the retries are spent, is read from the server log's tail, fixed at the cause, and retried on the same port once the server this step started is stopped. **Never report a URL that did not answer.** Nothing is run through the method: this skill stops once the page answers.

#### A starter: hand off

The bootstrap's own checks are the verification; do not start `make dev`. Write the report (below), then hand the user's method to `/pipelex-integrate`, which recognizes the starter's codegen harness (`npm run codegen`, `make codegen`, `make add-method`) and defers to it rather than writing a second one.

## Branch B — the ecosystem's initializer

### Step 1: Prerequisites

As in branch A, for the language chosen.

### Step 2: Run the initializer — never assemble by hand

- **A named framework** uses its documented initializer with its non-interactive flags: `npm create next-app@latest <dir> -- --ts --app --src-dir --eslint --use-npm --yes`, where the `--` is what passes the flags to the initializer instead of to npm and without it `create-next-app` prompts; `uv init --package --no-workspace <dir>` then `uv add "fastapi[standard]"` **from inside `<dir>`**, because `uv add` writes to whatever project its working directory resolves to and from the parent that is the user's, not the new one; and so on — [references/initializers.md](references/initializers.md) carries the common ones. An initializer that only runs interactively is handed to the user to run, and you resume when it is done.
- **No framework named** takes the language's own minimal initializer: Python → `uv init --package --no-workspace <dir>`, which gives the import package `/pipelex-integrate` wants and a console-script entry; TypeScript → `npm init -y`, then `npm install --save-dev typescript @types/node` and `npx tsc --init` with strict mode, ES modules and a `src/` root. **Read [references/initializers.md](references/initializers.md) before running either**, and not only for the flags: it is where the two costs of the TypeScript default are written down — it is the resolution that meets the emitter's extensionless-import defect, and `tsc --init` switches off the `@types/node` the line before it installed — and both are the kind of thing the integration, not the scaffold, gets blamed for.

Nothing beyond what the initializer writes is authored by this skill: no example code, no folder layout of its own, no opinion the framework did not ship.

**On Python, finish with `uv sync` from inside `<dir>`.** `uv init` writes a `pyproject.toml` and stops: no lock file, no environment. `/pipelex-integrate` picks the package manager off the lock file and reads no lock file as `pip install` into the active environment, so a project handed over without one is a uv project installed into with pip — and `uv init` left no environment for pip to find either. The recipes that end in a `uv add` are locked by that command; the minimal and script forms, which are exactly what "no framework named" selects, are locked only by this line. [references/initializers.md](references/initializers.md) carries it with the rest of the post-initializer sequence.

### Step 3: Version control and the pristine commit

**Test whether `<dir>` is its own repository; never infer it from which initializer ran.** `git -C <dir> rev-parse --show-toplevel` must print `<dir>` itself, and when it does not, run `git init -b main` in the directory before staging anything. The list of initializers that `git init` on their own is not a substitute for that test, because membership in it is conditional: `uv init` initializes a repository when it creates a standalone project and **does not** when the parent directory already holds one, where it makes `<dir>` a workspace member of the enclosing project instead. A `<dir>` with no `.git` of its own is governed by whatever repository encloses it — the user's — and `git -C <dir>` sets git's working directory without scoping anything, so the staging below would sweep that whole worktree: the user's unrelated untracked files, wherever they sit, committed into their repository under this skill's message. That is the one outcome this step exists to prevent, and the read-back catches it only if you read the paths and not just the count.

**Then confirm there is a `.gitignore` covering the dependency tree and the build output**: `npm init -y` and `tsc --init` write none, so the minimal TypeScript recipe — and the Express and library recipes built on it — reach this step with a populated `node_modules/` and nothing excluding it, and the staging below would commit the whole dependency tree into the one commit that is supposed to be a readable baseline. Write `node_modules/`, `dist/` and `.env` into a `.gitignore` first where the initializer left none, and read back what is staged — `git -C <dir> diff --cached --name-only` over the paths themselves, not a `--stat | tail -1` whose count cannot tell a correct scaffold from a swept-up worktree — before committing. Then the one commit, for the same reason as branch A:

```bash
git -C <dir> add -A -- . && git -C <dir> commit -m "Scaffold <framework or language> project" -- .
```

The `-- .` pathspec is the second half of the guard, and it is on **both** commands for a reason: `add -A -- .` bounds what this command stages, but a bare `git commit` then commits the *whole index*, so anything the user had staged elsewhere in an enclosing repository before the session goes into the commit under this skill's message. With the pathspec on the commit too, the staging and the commit are both held to `<dir>` and below even when the repository turns out to be an enclosing one, and the user's own staged work is left staged and uncommitted where they put it.

**An initializer that commits as well as `git init`s has already made this commit.** `create-next-app` is one: it runs `git init`, stages everything and commits, so the tree is clean and the command above stops with `nothing to commit` — which is the initializer having done the job, not a failure of it. Take that commit as the pristine one, exactly as branch A takes GitHub's, and name it and its message in the report. Never force a second empty commit on top of it.

### Step 4: The env file

Write `.env.example` with the two lines the starters share, make sure `.env` is gitignored, and copy the example to `.env` under the rule of branch A's env-file step for the key and the base URL — the same one command, with `.env` in place of `.env.local`, so a base URL the shell sets is copied here too, with the key or without one:

```
PIPELEX_BASE_URL=https://api.pipelex.com
PIPELEX_API_KEY=
```

### Step 5: Hand off

Add **no** SDK dependency and create **no** empty `methods/` directory: `/pipelex-integrate` adds `@pipelex/sdk` or `pipelex-sdk` when it writes the first call site, and creates `methods/<name>/` when it places the first bundle. A project with nothing to integrate yet has nothing Pipelex-shaped in it beyond the env convention, and that is correct.

## The report

**On the method app, the URL comes first**: `http://localhost:<port>`, that the dev server runs in the background and answers on this machine alone, how to stop it (`kill $(lsof -ti tcp:<port> -sTCP:LISTEN)`), and how to start it again (`make dev APP_PORT=<port> APP_HOST=127.0.0.1` from inside the project). Then say, in this order:

- what was created and where, with the project name and title the gesture derived;
- the template it came from, `pipelex-method-apps`' `webapp-js/`, at which version and SHA;
- that this skill made exactly one commit, and what it holds;
- that `make create`'s changes are uncommitted for review (`git status`, `git diff`);
- which plane `.env.local` points at, named without printing the URL;
- how to add a second method, and how to regenerate after editing the bundle;
- the two lines below.

The plane is the one the gesture ran against. When the shell exports a base URL, it is that one, read with the plane test of branch A's env-file step and never with an echo. When the user wrote `.env.local` themselves, say it was kept, and do not read it. Otherwise it is production. A second method is `make add-method METHOD=…`, which takes a bundle path, a catalog id or an address, and renders two methods as tabs. The regeneration after editing the bundle is `npm run codegen`.

**Otherwise, say in this order**: what was created and where; which template or initializer it came from, at which version and SHA; that this skill made exactly one commit and what it holds; what the bootstrap changed and that those changes are uncommitted for review, in the bootstrap's own words (a starter); which env file was written, whether the key was filled from the environment or left for the user, and which plane the file points at, named without printing the URL as branch A's env-file step says; the demos the starter still carries and where the README's removal checklist is (a starter); and the hand-off.

Two lines are easy to forget and matter:

- **The project's own instructions and skills load in a session started inside it.** Its `CLAUDE.md` / `AGENTS.md` and its own skills (`bump-sdk` and the like, and a starter's `release`) are not in the current session; `cd <dir>`, then starting Codex there, is how they arrive.
- **`/pipelex-integrate` still works from here meanwhile**, because the Pipelex workshop writes anywhere under the directory the harness was launched in, and the new project sits there. One exception, and it is the version-manager machine of step 1: the workshop is spawned with `npx` on the **harness's** own `PATH`, which no activation of yours reaches, so a `node` only reachable through `nvm` or `fnm` means no workshop at all. Say so there instead — the hand-off needs the harness restarted from a shell where the runtime is active. Hand the method to it by opening `../pipelex-integrate/SKILL.md` and following it; a bundle that lives elsewhere on disk is copied into the project by that skill. No method yet → `/pipelex-design` first. On the method app the method is already in the page, and `/pipelex-integrate` runs the project's `make add-method` for the next one.

## When something goes wrong

| Condition | Do this |
|---|---|
| A toolchain piece is missing (Node below the floor, no `uv`, no git) | STOP, name the exact missing piece and the template README's line about it; never install a toolchain — first check a version manager the machine already has (`nvm`, `fnm`, `volta`, `asdf`, `mise`) and use its runtime, saying so |
| The target directory exists and is not empty — anything at all beyond a lone `.git` | STOP, ask for another; never delete, move or write into it, and never offer to. **A directory holding nothing but `.git` is empty here and is written into**; that exception is the one directory entry by name and not a class, so `.DS_Store`, `.idea/`, `.vscode/`, `Thumbs.db` and anything else still refuse. On branch A that directory is served by the acquisition beside it (Step 2) and never by a `git clone` into it, which git refuses outright |
| `git clone` fails (network, permissions) | report git's error verbatim; nothing to clean up beyond an empty directory, and on an acquisition beside the directory the chain removes its own temporary path and copies nothing |
| The method app's clone carries no `webapp-js/` | STOP: the chain copied nothing and removed its temporary path; say what the default branch lacked, and never fall back to the gallery or copy another directory |
| `gh` is absent or not authenticated | fall back to the local copy; say the GitHub repository can be created later with `gh repo create --source .` |
| The method app has no key for its gesture | before anything is created, say so and offer the two ways of Step 1 — a harness restarted from a shell that exports it, or an `.env.local` the user writes themselves before step 4; never ask for the key in the conversation |
| `make create` refuses in its read-only half | relay its message; supply the value it asks for from the conversation or ask the user once, then re-run; for a capability the plane does not serve, stop and say which plane the template's README names — never a base URL the user did not declare |
| `make create` fails after its scaffold | fix the cause, never by editing `src/generated/`, then run the steps its message names; never re-run the gesture, which refuses a project |
| The method app's copy has no `make create` | STOP: the template changed; say so, and never assemble the app by hand |
| A starter clone carries no `bootstrap` skill | follow the README's manual list; say the template changed |
| The bootstrap's checks are red | its own rule: fix the cause and re-run; never hand off on red |
| The dev server's port is held by another directory | `port-check` names the holder; leave it alone and take the next port |
| The port is already served by this checkout | a server this step started: stop it and take the same port again; one the user started: ask whether they stop it or you take the next port. Never leave two servers of this step's running |
| The page does not answer `200` | read the server log's tail, fix the cause, stop the server this step started, and retry on the same port; never report a URL that did not answer |
| The server listens beyond loopback, or `lsof` shows no listener | stop it at once with the report's stop command and report no URL: its Server Actions spend the key for anyone who reaches them. Say this copy's `make dev` ignores `APP_HOST` |
| An initializer is interactive with no non-interactive form | hand the command to the user to run in the session; resume after |
| `PIPELEX_API_KEY` is not in the shell environment (a starter or an initializer) | leave the value empty in the env file; say where a key comes from and where it goes; never ask for it in the conversation. A base URL the shell sets is still copied, by the same command: when it is not production's, the report says the file points at another plane and warns that a key from `app.pipelex.com` is production's and will be refused there |
| `PIPELEX_BASE_URL` is set in the shell | copy it, with the key or without one, inside the one command the file's key test guards and never as a second command after it; say the base URL came from the environment, and whether it is production's, read with a test (`[ "${PIPELEX_BASE_URL%/}" = https://api.pipelex.com ] && echo production`) and never with an echo |
| you need to know whether a key or a base URL is set | test it without printing it (`[ -n "${PIPELEX_API_KEY:-}" ] && echo set`, and the same for `PIPELEX_BASE_URL`); never `env \| grep PIPELEX`, never echo the value, never move it with a file-editing tool, never read the env file back — a key in the transcript is a key to rotate |
| The working directory is a template's own checkout (its `origin` remote points at `Pipelex/pipelex-method-apps` or `Pipelex/pipelex-starter-…`) | STOP: this is the template, not a copy of it — acquire a copy in another directory. This is what separates it from the fresh-clone shortcut, which is a copy of the template and carries somebody else's `origin` or none |

## Reference

- [references/starters.md](references/starters.md) — the method app, the gallery and the Python starter side by side: what each brings, its prerequisite floors, the acquisition commands, its env file, its create gesture or bootstrap, its demos, and the codegen harness `/pipelex-integrate` will find.
- [references/initializers.md](references/initializers.md) — per language, the minimal default and the common frameworks' non-interactive initializers, whether each runs `git init`, and where the import package or `src/` root lands.
- `/pipelex-integrate` — the skill this one hands every project to, except a method app, which already runs its method.
