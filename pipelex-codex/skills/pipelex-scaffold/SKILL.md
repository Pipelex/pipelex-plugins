---
name: pipelex-scaffold
description: Start a new project that will call MTHDS methods through Pipelex, in TypeScript or Python — from a Pipelex template or from the ecosystem's own initializer. A TypeScript web app for a method comes from the method-app template, created for that method in one command and left running with its URL reported; every other project is handed to /pipelex-integrate. Use when the user says "start a new project with Pipelex", "I have a method and need an app around it", "create a Next.js app that runs my method", "build me a web app for this method", "set up a Pipelex project from scratch", "new Python CLI for this method", "bootstrap a Pipelex project", or wants a codebase where none exists yet. Also use when the user stands in a fresh copy of a Pipelex template not yet made theirs — this skill finishes it with the template's own gesture. Not for adding Pipelex to code that already exists — that is /pipelex-integrate.
---

# Scaffold a project for Pipelex methods

Give a user who has no project yet a project that runs their method, or one that is ready for `/pipelex-integrate`. This skill has exactly two branches and carries no templates of its own:

- **The method app** for a web app around a method, in TypeScript: the `webapp-js/` directory of `pipelex-method-apps`, a Next.js app that ships no method. You copy the directory, commit it once as it came, and run the copy's **own** `make create` with the user's method, which names the project after the method, scaffolds the method's form and result view, writes the env file and runs the project's checks. The create gesture lives in the template and is never reimplemented here.
- **The ecosystem's own initializer** for every other project — Python of any shape, a TypeScript CLI, service or library, a framework the user named, or a minimal project: `uv init --package`, `npm create next-app@latest`, `django-admin startproject`, whatever the framework documents. You run it; you never assemble a project by hand.

**The starters are not scaffolded from.** `pipelex-starter-js` and `pipelex-starter-python` still exist, but a user who names one is told this skill no longer starts from them, and is offered the method app or the initializer.

Every path makes one pristine commit, which makes everything after it reviewable. **The method app ends with the app running**: the method is already in the page, so the dev server is started and the report leads with its URL. The initializer ends with an env file carrying the two Pipelex lines and the hand-off — to `/pipelex-integrate` when a method exists, to `/pipelex-design` first when none does.

**What this skill is not.** Not a template engine (no cookiecutter, no copier, no framework matrix of its own), not a bootstrap (the method app owns its own), not a runner, not a deployer. The one server it starts is the method app's own dev server, at the end of that path. It needs no MCP tool and never handles an API key itself: git, the method app's own gesture, the ecosystem's initializers and its own two scripts are all it uses, and the method app's gesture reads the key where the user put it.

**A key never crosses the conversation.** **Never print a key, and never ask for one in the conversation.** An env file this skill writes or meets holds one — the initializer's `.env`, the method app's `.env.local` — and **the value moves only through a shell that expands the variable itself, and never through you**: `write-env-file.sh` moves it for the initializer's project, and the method app's gesture for its own. Test whether a key or a base URL is set without printing it (`[ -n "${PIPELEX_API_KEY:-}" ] && echo set || echo unset`, the same for `PIPELEX_BASE_URL`). Never `env | grep PIPELEX`, never echo either value, never move one with a file-editing tool, whose parameters are the transcript, and **no reading an env file back** — `cat`, a `grep` over it, or opening it to check your work: a key in the transcript is a key to rotate.

## Choosing the branch

A cheap, reliable signal decides; an inconclusive one asks one question; nothing is guessed twice.

| Question | Signals, in order | When inconclusive |
|---|---|---|
| **Language** | the user's word; the language the method's consumer is written in; a framework the user named | ask |
| **Which branch** | a **web app people use in a browser** in TypeScript — forms, an upload flow, "an app for my method" — → the method app, and **"no demo code"** there too, since it ships none; everything else → the initializer: a **named framework** the method app is not (FastAPI, Django, Express, Hono, a plain library, a Lambda), **"minimal"**, **"just a project"**, **"no template"**, and any **CLI, script, batch job, worker, service or library**, in Python or in TypeScript | one question offering the method app first and the initializer beside it, saying what the method app brings: a page rendering the method's form and result, durable runs, codegen wiring and CI, created for the method in one command and left running |
| **Where** | the directory the user named; **"here"** when the working directory is empty — **and a directory whose only entry is `.git` is empty for this rule**, because `mkdir my-app && cd my-app && git init` is an ordinary way to arrive here and a repository the user made is not work of theirs to write over: branch B runs its initializer in the directory as it stands and leaves that repository alone — it does **not** re-run `git init` there, since its pristine-commit script finds `<dir>` is already its own repository — while branch A acquires beside it and moves in, so the repository already there goes on standing either way (Step 2); else a kebab-case directory named after the project | ask; never write into a directory that exists and is not empty, and never offer to move, delete or merge what it holds to make room — the answer is another directory. **A lone `.git` is the only entry that does not make a directory non-empty, and that is a ruling about `.git` and nothing else** — not a class of files you may decide to overlook. Every other entry still refuses, `.DS_Store`, `.idea/`, `.vscode/` and `Thumbs.db` included: judging which of a user's files matter is the thing this rule exists to forbid, and a list that grows by guesswork is how it would come back. The rule is about **a directory you are creating a project in**, which is why the fresh-clone shortcut below is not an exception to it: there the project is already there and you are finishing it, not writing over someone's work |
| **GitHub or local** | the user asked for a GitHub repository → `gh repo create`, after confirmation: read [references/github.md](references/github.md) before running any `gh` command; otherwise a local project with fresh history | local |

**The method app needs the method first.** It ships no method, and `make create` is the gesture that makes a copy the user's, so a user with no method yet goes to `/pipelex-design` first and comes back with the bundle. Nothing is copied meanwhile. The method is a bundle — a `.mthds` file or a directory of them — a catalog id (`mt_…`), or a published package address (`github.com/<owner>/<repo>[/<package>][@<tag>]`).

**The method app's directory is named after the method** when the user named none: a bundle's `domain`, read from its `.mthds` file and kebab-cased, or a package address's last path segment without its tag, kebab-cased — the names `make create` gives the project. A catalog id carries no name you can read without a call, so ask.

**The fresh-clone shortcut.** A copy of a template already in the working directory that has not been made the user's is branch A entered at step 4: acquisition already happened. Do not clone again. The copy says what it is: its `package.json` still says `pipelex-method-webapp-js`, and `scripts/create.mts` is still there.

**Read git before initializing anything.** A copy is often made without git (the method app's README copies the directory and runs `git init` afterwards), and a copy may sit inside another repository. That repository may be the user's, or the template's own: the method app is a directory of `pipelex-method-apps`, so git places its checkout inside the family repository, where it passes every test above. One command tells the cases apart, and initializes only a copy that no repository tracks:

```bash
case "$(git -C <dir> remote get-url origin 2>/dev/null)" in
  */Pipelex/pipelex-method-apps*|*:Pipelex/pipelex-method-apps*)
    echo "this is a template's own checkout, not a copy of it" >&2; exit 1 ;;
esac
prefix=$(git -C <dir> rev-parse --show-prefix 2>/dev/null) || prefix=outside
case "$prefix" in
  "") ;;
  outside) git -C <dir> init -b main ;;
  *) if git -C <dir> ls-files -- . | grep -q .; then echo "an enclosing repository already tracks this directory" >&2; exit 1; fi
     git -C <dir> init -b main ;;
esac
```

The `origin` it reads belongs to whichever repository holds the directory, and it is read before anything is initialized, so a template's own checkout stops here (the last row of the failure table) whether the directory is its repository's root or a directory inside it. `--show-prefix` prints nothing when the directory is its repository's root, which needs no path comparison and so survives symlinks and letter case. **A directory another repository already tracks is not a fresh copy**, whoever owns that repository, a fork of the family under another name included: stop and ask the user what they meant, rather than planting a second repository inside theirs. A copy that nothing tracks gets a repository of its own, whether it stands alone or sits untracked inside the user's repository, as branch B's step 3 does. When that repository has no commit yet (`git -C <dir> rev-parse -q --verify HEAD` prints nothing), make step 3's pristine commit first, because the gesture's changes are reviewable only against it. The directory is the user's, so that commit confirms like the one the Mode section describes.

**Every placeholder is substituted as one shell word.** `<dir>`, `<port>`, `<owner>/<name>` and the rest are typed into commands the shell reads first, so a value holding a space or a character the shell interprets goes in single quotes (`'my app'`), with a quote inside spelled `'\''`, unless the block already quotes the placeholder, as `METHOD='<method>'` does. Unquoted, `mkdir -p my app` makes two directories, and a chain goes on in the wrong one.

## Mode

Automatic by default, with the plugin's usual rules: an explicit user signal wins ("just do it" → automatic; "walk me through" → interactive); a genuinely ambiguous branch is one question, asked once; a request that gave every input up front proceeds without re-asking. One thing always confirms, in every mode: **`gh repo create`**, because it creates a repository on GitHub. The pristine commit does not need confirmation **on a directory this skill created** — it holds the template as it came, and no user content is at stake. **A pristine commit into a directory that already held a repository is the exception**, on either branch, and it is a second thing that always confirms: there the commit lands on the user's branch, on top of their history, and `add -A -- .` records whatever their worktree was already showing along with what this skill put there (each branch's Step 3). None of the three grounds above holds, so state what will be staged and what it will land on, and ask — in every mode.

On the method app, interactive mode runs `make create` with `DRY_RUN=1` first and shows the user the identity and the plan it prints; automatic mode runs it directly, because its read-only half refuses before it changes a tracked file. Either way, the first run on a fresh copy installs the dependencies before anything else, which takes minutes, writes `node_modules/`, and lets the template's husky point the repository's `core.hooksPath` at the project's hooks. A dry run is not free, and a repository the user made gets that setting too.

## Branch A — the method app

### Step 1: Prerequisites

Check before touching anything, and **stop** on a missing piece with the exact thing missing and the template README's own line about it. **Never install a toolchain, and never let a version manager download one.** When `node` is missing or below the floor, read [references/version-managers.md](references/version-managers.md) before stopping: a runtime a version manager on the machine already holds is not a missing piece.

- Node at or above the floor the template's `package.json` `engines` field names (`node --version`; 22.12 at writing — the SDK is ESM-only and the template's e2e specs `require()` it), and `npm`. The method app also needs `make`, `curl`, `lsof` and `pgrep`: without `lsof` the template's `port-check` passes whatever holds the port, and step 5 can neither prove where its server listens nor stop it; without `pgrep` step 5 cannot stop a server that has not opened its port in time.
- `git`. The GitHub form also needs `gh`, which [references/github.md](references/github.md) covers.

**The method app also needs a key its gesture can read.** `make create` reads `PIPELEX_API_KEY` from the shell environment, or from an `.env.local` already in the project, and refuses without one. Test the shell before step 2 (`[ -n "${PIPELEX_API_KEY:-}" ] && echo set || echo unset`). When it is unset, say so before anything is created, and offer the two ways a key reaches the gesture without crossing the conversation: the user restarts the harness from a shell that exports it, or you carry on through step 3 and the user writes `<dir>/.env.local` themselves before you run step 4 — `cp .env.example .env.local`, then the key and the base URL of the plane that issued it, typed in their own editor. The gesture never touches an `.env.local` that already exists. The base URL follows the same path: the gesture runs against the plane the shell declares, or that file, and against production when neither declares one.

### Step 2: Acquire the template

The template is one directory of the `pipelex-method-apps` repository, and a project is a copy of that directory alone: the repository's root files — its own README, `VERSION`, the family's Makefile and workflows — are not part of it. So nothing is cloned into `<dir>`. The chain clones the repository shallow into a temporary path beside `<dir>`, reads the family's identity, copies `webapp-js/` in, and initializes a repository only where there is none. One chain serves a directory that does not exist, an empty one, and one whose only entry is `.git`:

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

The destination is resolved before its parent is taken, so a `<dir>` spelled `.` keeps the temporary path a sibling. One trap removes the temporary path however the command ends, an interruption included. No `rm -rf` addresses a path under `<dir>`. `cp -R "$tmp/webapp-js"/. "$dir"/` carries the entries beginning with a dot (`.gitignore`, `.env.example`, `.claude/`, `.husky/`). The directory is read once before anything is fetched and once more right before the copy, and anything but nothing or a lone `.git` stops the run with nothing copied and the temporary path removed. The chain goes out as one command. **The last line initializes only a directory with no repository of its own**, so a repository the user made goes on standing, and the pristine commit lands on their branch, as Step 3 says.

**The `webapp-js/` test is load-bearing.** The copy takes the default branch's head, and a head that does not carry the directory would otherwise copy nothing and report success. Stop there, say what the clone lacked, and do not fall back to the gallery or to another directory of the repository.

The copy takes the template's default-branch head. Do not offer a release tag unless the user asks for one.

### Step 3: Commit the pristine template — exactly once

```bash
git -C <dir> add -A -- . && git -C <dir> commit -m "Start from Pipelex/pipelex-method-apps/webapp-js <version> (<sha>)" -- .
```

The version is the family's `VERSION` and the SHA the clone's head, both read by step 2. This is the **one commit this skill makes**, and it is load-bearing: a committed baseline is what turns `make create`'s edits into a diff the user can read before committing them. Nothing of the user's is in it — it is the template as it came. One qualification on the acquisition into a directory that already held a repository: the commit lands on the user's branch, on top of their history rather than opening a new one, and `add -A -- .` also records whatever deletion their worktree was already showing — their own pending change and not one this skill made, so name it in the report instead of undoing it. That is the commit the Mode section sends back for confirmation, and this is what to put in front of the user: `git -C <dir> status --short` before staging says what will ride along, and it is the difference between a baseline commit and a line in their history that says "Start from Pipelex/…" over a change they made.

### Step 4: Make the project the user's: run its create gesture

```bash
log=$(mktemp "${TMPDIR:-/tmp}/pipelex-create-XXXXXX") || exit 1
make -C <dir> create METHOD='<method>' > "$log" 2>&1; rc=$?
tail -n 40 "$log"; echo "make create exited $rc; the whole log is $log"
echo "its warnings:"; grep -E '^(warning: |! )' "$log" | LC_ALL=C sort -u | grep . || echo "none"
```

`<method>` is what the user has. A bundle, whether a `.mthds` file or a directory of them, is **given as an absolute path**, because the gesture reads a relative path from the directory make runs in, which is `<dir>` and not where the user stood; the gesture copies it into the project. A catalog id is `mt_…`, and a package address is `github.com/<owner>/<repo>[/<package>][@<tag>]`. Add `NAME='…'`, `TITLE='…'` and `DESCRIPTION='…'` only when the conversation already holds them or the user asked for something other than what the method carries, since the gesture derives all three from the method. Add `AUTHOR_NAME`, `AUTHOR_EMAIL`, `REPO_URL`, `LICENSE`, `LICENSE_HOLDER` and `LICENSE_YEAR` only when the user gave them, because nothing is invented. `METHOD_NAME`, `PIPE` and `LABEL` answer a refusal that names them. Every value goes in single quotes, with a quote inside one spelled `'\''`, because the shell reads the line before make does.

What the gesture does is the template's to say — `<dir>/docs/create.md`, until the gesture removes that document along with itself — and none of it is reimplemented here. It fetches the method once, scaffolds its slice, runs the template's bootstrap with the values it derived, writes `.env.local` with exactly one base-URL line, re-syncs the lock file, runs `make all`, and removes the bootstrap once that is green. It commits nothing. Give the command several minutes: on a fresh copy it installs the dependencies, and it ends with a production build. The gesture names variables and never prints their values, so the log's tail is safe to read. The `.env.local` it wrote is not: the key guard above holds for it.

**The gesture's warnings are read from the whole log, not from its tail.** `make create` prints its own warnings as `! …` and the bootstrap's as `warning: …`, all before `make all`, whose output fills the tail. It also runs the bootstrap twice, a dry run and then the write, so the block's last line lists each distinct warning once. Every one goes into the report with what answers it. An MIT project whose user named no copyright holder always gets this one: `warning: LICENSE copyright line left untouched — pass --license-holder to claim it.` It means the project's `LICENSE` still names the template's copyright holder. The gesture refuses to run on a project it has already made, so after the run the answer is an edit of that line in `LICENSE`, by the user, or by you with the holder they name. In interactive mode the dry run shows the warning before anything is written, so a holder the user gives then goes into the real run as `LICENSE_HOLDER='…'`.

- **A refusal in its read-only half** changes no tracked file, so the gesture can run again; the dependencies it installed first stay, and the next run skips that install. Relay the message, supply a value it asks for from the conversation or by asking the user once, and re-run. A refusal naming a capability the API does not serve means the plane the gesture ran against does not serve what codegen needs yet. Say so, point at the template README's line on which plane does, and stop there: never substitute a base URL the user did not declare, because a key is refused by every plane but the one that issued it.
- **A failure after the scaffold** cannot be undone by running the gesture again, because the copy has become a project and the gesture refuses it. Fix the cause, never by editing `src/generated/`, then run the steps its message names (`npm install --package-lock-only`, `make all`, `rm -rf .claude/skills/bootstrap`). A red `make all` is fixed, never handed off.

### Step 5: Start the dev server and prove the page answers

`make create`'s `make all` is the verification. Then start the app. The template serves on port 4300, and its `port-check` target says whether a port is free and, when it is not, which process in which directory holds it:

```bash
make -C <dir> port-check APP_PORT=4300
```

A refusal naming another directory is another app: leave it alone, try the next port up (4301), then the one after that, and use the first one the check accepts. A refusal saying the port **is already served by this checkout** is this project's own server, not a holder to step around. When this step started it, on an attempt whose page did not answer, stop it with the report's stop command and take the same port again. When the user started it, say so and ask whether they stop it or you take the next port up. **Never start a second server while one this step started still runs**, because the report's stop command names one port.

**The server listens on this machine alone, and a copy that cannot promise it is not started.** The page's Server Actions run the method with the key in `.env.local` and do not check who is calling, so a server reachable from the network lets anyone on it spend that key, from the moment the port opens, which is before the first page compiles. `next dev` listens on every interface unless its command line names a host, and no environment variable changes that. So before anything starts, read the dev script the copy's `make dev` runs:

```bash
node -e 'const dev = JSON.parse(require("fs").readFileSync(process.argv[1], "utf8")).scripts?.dev ?? ""; process.exit(/(^|\s)(-H|--hostname)(\s+|=)("?)(\$\{APP_HOST:-127\.0\.0\.1\}|127\.0\.0\.1|localhost|::1)\4(\s|$)/.test(dev) ? 0 : 1)' <dir>/package.json || { echo "this copy's dev server would listen on every interface" >&2; exit 1; }
```

The template names the host `-H ${APP_HOST:-127.0.0.1}`, and a script naming a loopback address itself passes too. On a refusal, start nothing and report no URL. Say that this copy's dev script does not bind the server to this machine, so this skill does not start it, and that the user can start it bound by hand with `npx next dev -H 127.0.0.1 -p <port>` from inside the project.

Then start the server detached, so that it outlives the command that started it. The same command waits for the port to open, stops everything it launched when the port has not opened by the end of the wait, checks who holds the port and where it listens, stops a server of this project's that listens beyond this machine before any page can compile, and only then requests the page. The directory is resolved by the external `pwd`, because the one built into bash and sh keeps the letter case the path was typed in, while `lsof` reports the case on disk:

```bash
dir=$(cd <dir> && env pwd -P) || exit 1
log=$(mktemp "${TMPDIR:-/tmp}/pipelex-dev-XXXXXX") && page=$(mktemp "${TMPDIR:-/tmp}/pipelex-page-XXXXXX") || exit 1
nohup make -C "$dir" dev APP_PORT=<port> APP_HOST=127.0.0.1 > "$log" 2>&1 &
launcher=$!
stop_tree() { local p; for p; do kill -STOP "$p" 2>/dev/null || continue; stop_tree $(pgrep -P "$p"); kill -TERM "$p" 2>/dev/null; kill -CONT "$p" 2>/dev/null; done; }
n=0; until lsof -ti tcp:<port> -sTCP:LISTEN > /dev/null 2>&1 || ! kill -0 "$launcher" 2>/dev/null || [ "$n" -ge 300 ]; do sleep 0.2; n=$((n + 1)); done
if ! lsof -ti tcp:<port> -sTCP:LISTEN > /dev/null 2>&1; then
  if kill -0 "$launcher" 2>/dev/null; then stop_tree "$launcher"; echo "nothing listens on port <port> yet, so the server this command started was stopped; server log: $log" >&2; exit 1; fi
  echo "nothing listens on port <port>: the server exited; server log: $log" >&2; exit 1
fi
for pid in $(lsof -ti tcp:<port> -sTCP:LISTEN); do
  [ "$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1)" = "$dir" ] || { echo "port <port> is held by pid $pid, which is not this project; server log: $log" >&2; exit 1; }
  if lsof -nP -a -p "$pid" -iTCP:<port> -sTCP:LISTEN -Fn | sed -n 's/^n//p' | grep -Evq '^(127\.0\.0\.1|\[::1\]):<port>$'; then
    kill "$pid"; echo "the server listened beyond this machine and was stopped; server log: $log" >&2; exit 1
  fi
done
curl -sS -o "$page" -w '%{http_code}\n' --retry 60 --retry-delay 1 --retry-connrefused --retry-max-time 120 --max-time 120 "http://localhost:<port>/"
grep -o '<title>[^<]*</title>' "$page"; echo "listening on this machine alone; server log: $log"
```

Each refusal names its cause, and each has one reading:

- **Nothing listens** means the server did not start. Either it exited before opening the port, or it had not opened the port by the end of the wait. In that second case the command stops the process it launched and every process under it, suspending each one before stopping its children so that none can start another. Either way, nothing this step started is still running: read the log's tail, fix the cause, and retry on the same port.
- **A holder that is not this project** means another process took the port after `port-check` passed, and the `port-check` inside `make dev` refused. Leave that process alone and take the next port up.
- **A server that listened beyond this machine** has already been stopped by the command itself. Report no URL and say that this copy's `make dev` does not bind the server to this machine, which the dev-script check above should have caught.

The retries wait out the first compilation of the page, for two minutes at most. A `200` under the project's title is the proof, since the page is the method's form. Anything else, including no answer once the retries are spent, is read from the server log's tail, fixed at the cause, and retried on the same port once the server this step started is stopped. **Never report a URL that did not answer.** Nothing is run through the method: this skill stops once the page answers.

## Branch B — the ecosystem's initializer

### Step 1: Prerequisites

As in branch A, for the language chosen: `uv` for Python, which runs the initializer and writes the lock; Node and `npm` for TypeScript; `git` for both. Never install a toolchain, and read [references/version-managers.md](references/version-managers.md) before stopping on a missing `node` or `uv`, as branch A does.

### Step 2: Run the initializer — never assemble by hand

**Read [references/initializers.md](references/initializers.md) before running any initializer.** It carries each one's non-interactive form, the directory every follow-on command must run from, and the two costs of the TypeScript default. A named framework uses its documented initializer with its non-interactive flags; no framework named takes the language's own minimal initializer. An initializer that only runs interactively is handed to the user to run, and you resume when it is done.

Nothing beyond what the initializer writes is authored by this skill: no example code, no folder layout of its own, no opinion the framework did not ship.

**On Python, finish with `uv sync` from inside `<dir>`.** `uv init` writes a `pyproject.toml` and stops: no lock file, no environment. `/pipelex-integrate` picks the package manager off the lock file and reads no lock file as `pip install` into the active environment, so a project handed over without one is a uv project installed into with pip.

### Step 3: The pristine commit

`<skill-dir>` stands for the directory holding this `SKILL.md`, the one Codex named when it loaded the skill. Run the script, never its steps by hand:

```bash
bash "<skill-dir>/scripts/commit-pristine.sh" '<dir>' 'Scaffold <framework or language> project'
```

It makes `<dir>` a repository of its own when it is not one, whichever initializer ran, keeps the dependency tree out with a `.gitignore`, and commits `<dir>` alone. Its first line is the verdict. `committed:` names the commit and lists the staged paths after it; `kept:` names a commit the initializer made itself, which is the pristine one. Read the paths, and name the commit in the report. A `refused:` line is in the stop table. **When `<dir>` held a `.git` before step 2**, the commit lands on the user's branch, so it confirms first, as the Mode section says: show `git -C <dir> status --short`, and ask.

### Step 4: The env file

```bash
bash "<skill-dir>/scripts/write-env-file.sh" '<dir>'
```

It writes `.env.example` with the two Pipelex lines, makes sure `.env` is ignored, and copies the example to `.env`, filled from the shell: the key when the shell sets one, and a base URL the shell sets, with a key or without one. A `.env` that already carries a key is left untouched. It prints one line and never a value, `<key> base-url=<origin> plane=<plane>`, which the report turns into words.

### Step 5: Hand off

Add **no** SDK dependency and create **no** empty `methods/` directory: `/pipelex-integrate` adds `@pipelex/sdk` or `pipelex-sdk` when it writes the first call site, and creates `methods/<name>/` when it places the first bundle. A project with nothing to integrate yet has nothing Pipelex-shaped in it beyond the env convention, and that is correct.

## The report

**On the method app, the URL comes first**: `http://localhost:<port>`, that the dev server runs in the background and answers on this machine alone, how to stop it (`for pid in $(lsof -ti tcp:<port> -sTCP:LISTEN); do kill "$pid"; done`), and how to start it again (`make dev APP_PORT=<port> APP_HOST=127.0.0.1` from inside the project). Then say, in this order:

- what was created and where, with the project name and title the gesture derived;
- the template it came from, `pipelex-method-apps`' `webapp-js/`, at which version and SHA;
- that this skill made exactly one commit, and what it holds;
- that `make create`'s changes are uncommitted for review (`git status`, `git diff`);
- every warning the gesture printed, each with what answers it, and first, when the gesture left it in place, that `LICENSE` still names the template's copyright holder and that editing that line is how the user claims it;
- which plane `.env.local` points at, named without printing the URL;
- how to add a second method, and how to regenerate after editing the bundle;
- the two lines below.

The plane is the one the gesture ran against. When the shell exports a base URL, it is that one, read with a test, `[ "${PIPELEX_BASE_URL%/}" = https://api.pipelex.com ] && echo production || echo other`, and never with an echo. When the user wrote `.env.local` themselves, say it was kept, and do not read it. Otherwise it is production. A second method is `make add-method METHOD=…`, which takes a bundle path, a catalog id or an address, and renders two methods as tabs. The regeneration after editing the bundle is `npm run codegen`.

**On the initializer's project, say in this order**: what was created and where; which initializer it came from, at which version; the pristine commit with its message, and whether this skill made it or the initializer did; that `.env.example`, `.env` and any line added to `.gitignore` are uncommitted for review; what `write-env-file.sh` reported, in words; and the hand-off.

The env file's verdict becomes words this way, and the URL is never printed:

- **`filled`**: the key was taken from the environment **and not validated**. A placeholder someone exported once passes a presence test and fails the first run, and this skill never calls the API.
- **`kept`**: `.env` already carried a key, and both of its lines were left as they were.
- **`empty`**: say where a key comes from and that `.env`'s `PIPELEX_API_KEY=` line is where it goes: `app.pipelex.com` issues production's keys.
- **`base-url=copied`**: the base URL came from the environment. Name the plane from `plane`. **When it came without a key and the plane is `other`, say the file points at another plane, and warn that a key from `app.pipelex.com` is production's and will be refused there**: a key for that plane goes on the file's `PIPELEX_API_KEY=` line.
- **`base-url=file`**: the file points where the example or the user left it, and `plane` names which.

Two lines are easy to forget and matter:

- **The project's own instructions and skills load in a session started inside it.** Its `CLAUDE.md` / `AGENTS.md` and its own skills (`bump-sdk` and the like) are not in the current session; `cd <dir>`, then starting Codex there, is how they arrive.
- **`/pipelex-integrate` still works from here meanwhile**, because the Pipelex workshop writes anywhere under the directory the harness was launched in, and the new project sits there. The one exception is a machine where `node` was missing from the `PATH` and step 1 reached it through a version manager, whose hand-off [references/version-managers.md](references/version-managers.md) describes. Hand the method to it by opening `../pipelex-integrate/SKILL.md` and following it; a bundle that lives elsewhere on disk is copied into the project by that skill. No method yet → `/pipelex-design` first. On the method app the method is already in the page, and `/pipelex-integrate` runs the project's `make add-method` for the next one.

## When something goes wrong

| Condition | Do this |
|---|---|
| A toolchain piece is missing (Node below the floor, no `uv`, no git) | STOP, name the exact missing piece and the template README's line about it; never install a toolchain — first read [references/version-managers.md](references/version-managers.md), since a runtime a version manager already holds is not missing |
| The target directory exists and is not empty — anything at all beyond a lone `.git` | STOP, ask for another; never delete, move or write into it, and never offer to. **A directory holding nothing but `.git` is empty here and is written into**; that exception is the one directory entry by name and not a class, so `.DS_Store`, `.idea/`, `.vscode/`, `Thumbs.db` and anything else still refuse. On branch A that directory is served by the acquisition beside it (Step 2) and never by a `git clone` into it, which git refuses outright |
| The method app's `git clone` fails (network, permissions) | report git's error verbatim; the chain removes its own temporary path and copies nothing |
| A `.pipelex-method-apps-…` directory already sits beside the destination | an earlier run was killed before its trap could run. Leave it: this run's `mktemp` makes a path of its own and touches no other. Name it in the report so the user can remove it |
| The method app's clone carries no `webapp-js/` | STOP: the chain copied nothing and removed its temporary path; say what the default branch lacked, and never fall back to the gallery or copy another directory |
| `gh` is absent or not authenticated | keep the local project; say the GitHub repository can be created later with `gh repo create --source .` |
| The method app has no key for its gesture | before anything is created, say so and offer the two ways of Step 1 — a harness restarted from a shell that exports it, or an `.env.local` the user writes themselves before step 4; never ask for the key in the conversation |
| `make create` refuses in its read-only half | relay its message; supply the value it asks for from the conversation or ask the user once, then re-run; for a capability the plane does not serve, stop and say which plane the template's README names — never a base URL the user did not declare |
| `make create` fails after its scaffold | fix the cause, never by editing `src/generated/`, then run the steps its message names; never re-run the gesture, which refuses a project |
| The method app's copy has no `make create` | STOP: the template changed; say so, and never assemble the app by hand |
| The dev server's port is held by another directory | `port-check` names the holder; leave it alone and take the next port |
| The port is already served by this checkout | a server this step started: stop it and take the same port again; one the user started: ask whether they stop it or you take the next port. Never leave two servers of this step's running |
| The copy's dev script names no loopback host | start nothing and report no URL: its Server Actions would spend the key for anyone on the network. Say the user can start it bound by hand with `npx next dev -H 127.0.0.1 -p <port>` |
| Nothing listens on the port | the server did not start: it exited, or it had not opened the port by the end of the wait and the command stopped everything it had launched. Read the log's tail, fix the cause and retry on the same port |
| The port is held by a process that is not this project, after `port-check` passed | another process took it in between; leave it alone and take the next port |
| The page does not answer `200` | read the server log's tail, fix the cause, stop the server this step started, and retry on the same port; never report a URL that did not answer |
| The server listened beyond loopback | the start command has already stopped it; report no URL and say this copy's `make dev` does not bind the server to this machine |
| An initializer is interactive with no non-interactive form | hand the command to the user to run in the session; resume after |
| `commit-pristine.sh` or `write-env-file.sh` says `refused: usage` or `refused: no-directory` | the command was typed wrong: check `<dir>` and its quoting, and run it again |
| `commit-pristine.sh` says `refused: nothing-to-commit` | the initializer wrote nothing: read its output and run it again; never commit an empty directory |
| `commit-pristine.sh` says `refused: init-failed`, `stage-failed` or `commit-failed` | relay git's message from its standard error verbatim; a missing `user.name` or `user.email` is the user's to set, never yours |
| `write-env-file.sh` says `refused: not-ignored` | no key was written: `.env` is still not ignored after the script added it to `.gitignore`, most often because git already tracks it. Say so, and leave the file for the user |
| `write-env-file.sh` says `empty` | leave the key for the user: say where a key comes from and where it goes; never ask for it in the conversation |
| The working directory is a template's own checkout (its `origin` remote points at `Pipelex/pipelex-method-apps`) | STOP: this is the template, not a copy of it — acquire a copy in another directory. This is what separates it from the fresh-clone shortcut, which is a copy of the template and carries somebody else's `origin` or none |

## Reference

- [references/initializers.md](references/initializers.md) — per language, the minimal default and the common frameworks' non-interactive initializers, whether each runs `git init`, and where the import package or `src/` root lands.
- [references/version-managers.md](references/version-managers.md) — `node` or `uv` missing from the `PATH`, or `node` below the floor, before stopping on it: a version manager the machine already has may hold one.
- [references/github.md](references/github.md) — the repository on GitHub, before any `gh` command.
- `/pipelex-integrate` — the skill this one hands every project to, except a method app, which already runs its method.
