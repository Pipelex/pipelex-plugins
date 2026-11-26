# A copy of the method app that `npm run create` has not run in

Read this when a copy of the method-app template stands and has not been made the user's, before running anything in it: the user stands in one (its `package.json` still says `pipelex-method-webapp-js`, and `scripts/create.mts` is still there), or the family's initializer printed `copied` (after `--dry-run` or `--no-create`) or `failed: create`. What makes the copy the user's is its own `npm run create`, which this file runs directly; `/pipelex-scaffold` then goes on at branch A's step 2, `npm run serve`. **Never run `npm run serve` on a copy whose `npm run create` failed** until that failure is fixed as below: it would serve a copy that is not finished. None of `npm run create`'s work is reimplemented here: the copy's `docs/create.md` says what it does, until the gesture removes that document along with itself.

This file runs two scripts of the skill, each through `node` by its absolute path, where `<skill-dir>` is the directory holding the skill's `SKILL.md`, the parent of the directory holding this file. Run them, never their steps by hand: they read git and run the gesture the same way in every shell.

## After the initializer

The copy stands, with its pristine commit unless the `git:` line said it sits in another repository's work tree that does not ignore it, where the initializer made neither a repository nor a commit. Either way, go straight to [Run `npm run create`](#run-npm-run-create), with the values the verdict's `next:` line spells.

- **`copied` after `--dry-run`**, in interactive mode: first show the user the identity and the plan `npm run create` printed, with its warnings. They are in the log whose path the initializer printed, under `--quiet`. A license holder the user gives now goes into the real run as `--license-holder '…'`. The dry run was not free: it installed the dependencies, which write `node_modules/` and let the template's husky point the repository's `core.hooksPath` at the project's hooks.
- **`copied` after `--no-create`**, because the shell had no key: the user writes `<dir>/.env.local` themselves, in their own editor, from a copy of `.env.example`, then the key and the base URL of the plane that issued it. `npm run create` reads that file and never touches an `.env.local` that already exists. Nothing reads it back, and the report says it was kept, in place of telling the user where their key goes, since they wrote it there, and names its plane only from a `PIPELEX_BASE_URL` the shell exports, never production by default: the file may name another plane, and reading it is not allowed.
- **`failed: create`**: the end of the log the initializer named says which of two cases it is.
  - **A refusal before `npm run create` wrote anything** changed no tracked file, so it can run again; the dependencies it installed stay, and the next run skips that install. Relay the message, supply a value it asks for from the conversation or by asking the user once, and run it again. A refusal naming a capability the API does not serve means the plane it ran against does not serve what codegen needs yet: say so, point at the template README's line on which plane does, and stop there.
  - **A failure after the scaffold** cannot be undone by running `npm run create` again, because the copy has become a project and the gesture refuses it. Fix the cause, never by editing `src/generated/`, then run the steps its message names, each on its own: `npm --prefix '<dir>' install --package-lock-only`, `npm --prefix '<dir>' run all`, and the removal of the copy's `.claude/skills/bootstrap/` directory, `node -e "fs.rmSync(process.argv[1], { recursive: true })" '<dir>/.claude/skills/bootstrap'`. A red `npm run all` is fixed, never handed off, but for the one cause below.

**A cause the harness's own sandbox imposes is the user's to lift, never yours to work around**, in either case: a denied `ps`, which the template's tests and `npm run serve` both need, or an npm cache the sandbox will not let npm write. Nothing in the copy fixes it. Name it, say that the user lifts the sandbox or runs the steps the failure named, then `npm run serve`, in a terminal of their own, and stop.

## Where the copy stands in git

**A copy the user stands in is one of these when its own repository already holds the pristine commit**, whose subject opens `Start from Pipelex/pipelex-sdk/method-apps/webapp-js`, as the one this file makes by hand does too, or `Start from Pipelex/pipelex-method-apps/webapp-js` on a copy made before the template moved into `pipelex-sdk`. Read git before anything else, since the user seldom says who made the copy, and before initializing anything:

```bash
node "<skill-dir>/scripts/read-copy-git.mjs" '<dir>'
```

It prints one line, the verdict:

- **`pristine: <commit> <subject>`**: the copy is its repository's root and that repository holds the pristine commit. The report names it as found; go straight to [Run `npm run create`](#run-npm-run-create), with the method the user gave.
- **`no-commit: <dir>`**: the copy is its own repository's root and that repository has no commit yet, either one the user made or one the script made on `main` just now, which the line then says. Make the pristine commit below before `npm run create`.
- **`history: <dir>`**: the copy is its own repository's root, with commits and no pristine one. The user committed it themselves: go on to [Run `npm run create`](#run-npm-run-create) with no commit of yours.
- **`inside: <root>`**: the copy sits untracked inside the work tree of `<root>`, which does not ignore it, so it gets no repository and no commit.
- **`refused: template-checkout`**: the directory is in a checkout of the template's own repository, `pipelex-sdk`, or `pipelex-method-apps` before the move; the skill's template-checkout stop.
- **`refused: tracked <root>`**: `<root>` already tracks the directory.
- **`refused: usage`**, **`no-directory`**, **`no-git`** or **`init-failed`**: a wrong `<dir>`, no git on the `PATH`, or a `git init` git refused, with git's message; relay it.

The `origin` it reads belongs to whichever repository holds the directory, and it is read before anything is initialized, so a template's own checkout stops here, whether the directory is its repository's root or a directory inside it. **A directory another repository already tracks is not a fresh copy**, whoever owns that repository, a fork of the family under another name included: stop and ask the user what they meant: a copy they committed there themselves goes on to [Run `npm run create`](#run-npm-run-create) with no commit of yours, and anything else stops. A copy outside every repository gets one of its own, and so does one the enclosing repository ignores, as the initializer gives it one: that repository never sees a repository there, and without one the copy would have no baseline. The directory is asked about from its parent, where it physically is. **A copy that sits untracked inside another repository's work tree that does not ignore it gets no repository and no commit**, just as the initializer gives it none, because a second repository planted inside the user's is what the family refuses: go straight to [Run `npm run create`](#run-npm-run-create), whose changes the user reviews there as new files.

On `no-commit:`, make the pristine commit before `npm run create`, because the gesture's changes are reviewable only against it. The directory is the user's, so this commit confirms in every mode: show `git -C <dir> status --short` and say what it will land on. `<version>` is the copy's `package.json` version, the family's. Run the two commands one after the other, the second only once the first succeeded:

```bash
git -C <dir> add -A -- .
git -C <dir> commit -m "Start from Pipelex/pipelex-sdk/method-apps/webapp-js <version>" -- .
```

The pathspec is on both commands, because `git -C` sets git's working directory and scopes nothing, and a commit without one commits the whole index. It is the one commit the skill makes on this path. A copy with no `create` script in its `package.json` is not this template any more: stop, say so, and never assemble the app by hand.

## Run `npm run create`

```bash
node "<skill-dir>/scripts/run-create.mjs" '<dir>' '<method>'
```

The script runs the copy's own `npm run create` with the method, writes everything it prints to a log in the system's temporary directory, and prints the log's last lines, then `warnings:` followed by each distinct warning, or `warnings: none`, then its last line, `npm run create exited <code>; the whole log is <path>`. A `refused: usage` or `refused: no-directory` line means a wrong `<dir>`, `failed: npm` that npm could not be started, and `failed: log` that the log could not be written, each with its message.

`<method>` is what the user has. A bundle, a `.mthds` file or a directory of them, is read from the directory the script runs in, which is where the user stood. A catalog id is `mt_…`, and a package address is `github.com/<owner>/<repo>[/<package>][@<tag>]`. After the method, add `--name`, `--title`, `--description`, `--author-name`, `--author-email`, `--repo-url`, `--license`, `--license-holder` and `--license-year`, each followed by its value, only with a value the user gave, and `--method-name`, `--pipe` and `--label` to answer a refusal that names them. Every value goes in single quotes, with a quote inside one spelled `'\''`, because the shell reads the line first.

`npm run create` reads `PIPELEX_API_KEY` from the shell environment, or from an env file already in the project, `.env.local` or `.env`, and refuses without one. **Run the script in the foreground with a long timeout**, never in the background: on a fresh copy it installs the dependencies and ends with a production build, which takes minutes, and its exit decides what comes next. It commits nothing. It names variables and never prints their values, so the log's tail is safe to read, and no env file is.

**The gesture's warnings are read from the whole log, not from its tail.** `npm run create` prints its own warnings as `! …` and the bootstrap's as `warning: …`, all before `npm run all`, whose output fills the tail, and it runs the bootstrap twice, so the script lists each distinct warning once. Every one goes into the report with what answers it. An MIT project whose user named no copyright holder always gets `warning: LICENSE copyright line left untouched — pass --license-holder to claim it.`: the project's `LICENSE` still names the template's copyright holder, and since the gesture refuses a project it has already made, the answer is now an edit of that line, by the user, or by you with the holder they name.

A non-zero exit is one of the two cases under [After the initializer](#after-the-initializer), and `npm run serve` waits until it is fixed. On `0`, go on to `npm run serve`. The report is the method app's, and its git outcome is the pristine commit you made or found, or no commit for a copy inside another repository's work tree that does not ignore it.
