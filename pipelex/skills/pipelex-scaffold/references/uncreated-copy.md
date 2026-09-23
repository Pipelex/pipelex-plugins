# A copy of the method app that `make create` has not run in

Read this when a copy of the method-app template stands and has not been made the user's, before running anything in it: the user stands in one (its `package.json` still says `pipelex-method-webapp-js`, and `scripts/create.mts` is still there), or the family's initializer printed `copied` (after `--dry-run` or `--no-create`) or `failed: create`. What makes the copy the user's is its own `make create`, which this file runs directly; `/pipelex-scaffold` then goes on at branch A's step 2, `make serve`. None of `make create`'s work is reimplemented here: the copy's `docs/create.md` says what it does, until the gesture removes that document along with itself.

## After the initializer

The copy and its pristine commit stand, so go straight to [Run `make create`](#run-make-create), with the values the verdict's `next:` line spells.

- **`copied` after `--dry-run`**, in interactive mode: first show the user the identity and the plan `make create` printed, with its warnings. They are in the log whose path the initializer printed, under `--quiet`. A license holder the user gives now goes into the real run as `LICENSE_HOLDER='…'`. The dry run was not free: it installed the dependencies, which write `node_modules/` and let the template's husky point the repository's `core.hooksPath` at the project's hooks.
- **`copied` after `--no-create`**, because the shell had no key: the user writes `<dir>/.env.local` themselves, in their own editor — `cp .env.example .env.local`, then the key and the base URL of the plane that issued it. `make create` reads that file and never touches an `.env.local` that already exists. Nothing reads it back, and the report says it was kept.
- **`failed: create`**: the end of the log the initializer named says which of two cases it is.
  - **A refusal before `make create` wrote anything** changed no tracked file, so it can run again; the dependencies it installed stay, and the next run skips that install. Relay the message, supply a value it asks for from the conversation or by asking the user once, and run it again. A refusal naming a capability the API does not serve means the plane it ran against does not serve what codegen needs yet: say so, point at the template README's line on which plane does, and stop there.
  - **A failure after the scaffold** cannot be undone by running `make create` again, because the copy has become a project and the gesture refuses it. Fix the cause, never by editing `src/generated/`, then run the steps its message names (`npm install --package-lock-only`, `make all`, `rm -rf .claude/skills/bootstrap`). A red `make all` is fixed, never handed off.

## A copy the initializer did not make

A copy made by hand is often made without git, and it may sit inside another repository. That repository may be the user's, or the template's own: the method app is a directory of `pipelex-method-apps`, so git places its checkout inside the family repository, where it passes every other test. Read git before initializing anything. One command tells the cases apart, and initializes only a copy that no repository tracks:

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

The `origin` it reads belongs to whichever repository holds the directory, and it is read before anything is initialized, so a template's own checkout stops here, the skill's template-checkout stop, whether the directory is its repository's root or a directory inside it. `--show-prefix` prints nothing when the directory is its repository's root, which needs no path comparison and so survives symlinks and letter case. **A directory another repository already tracks is not a fresh copy**, whoever owns that repository, a fork of the family under another name included: stop and ask the user what they meant, rather than planting a second repository inside theirs. A copy that nothing tracks gets a repository of its own, whether it stands alone or sits untracked inside the user's repository.

When that repository has no commit yet (`git -C <dir> rev-parse -q --verify HEAD` prints nothing), make the pristine commit before `make create`, because the gesture's changes are reviewable only against it. The directory is the user's, so this commit confirms in every mode: show `git -C <dir> status --short` and say what it will land on. `<version>` is the copy's `package.json` version, the family's:

```bash
git -C <dir> add -A -- . && git -C <dir> commit -m "Start from Pipelex/pipelex-method-apps/webapp-js <version>" -- .
```

The pathspec is on both commands, because `git -C` sets git's working directory and scopes nothing, and a commit without one commits the whole index. It is the one commit the skill makes on this path. A copy with no `make create` target is not this template any more: stop, say so, and never assemble the app by hand.

## Run `make create`

```bash
log=$(mktemp "${TMPDIR:-/tmp}/pipelex-create-XXXXXX") || exit 1
make -C <dir> create METHOD='<method>' > "$log" 2>&1; rc=$?
tail -n 40 "$log"; echo "make create exited $rc; the whole log is $log"
echo "its warnings:"; grep -E '^(warning: |! )' "$log" | LC_ALL=C sort -u | grep . || echo "none"
```

`<method>` is what the user has. A bundle, a `.mthds` file or a directory of them, is **given as an absolute path**, because the gesture reads a relative path from the directory make runs in, which is `<dir>` and not where the user stood. A catalog id is `mt_…`, and a package address is `github.com/<owner>/<repo>[/<package>][@<tag>]`. Add `NAME`, `TITLE`, `DESCRIPTION`, `AUTHOR_NAME`, `AUTHOR_EMAIL`, `REPO_URL`, `LICENSE`, `LICENSE_HOLDER` and `LICENSE_YEAR` only with a value the user gave, and `METHOD_NAME`, `PIPE` and `LABEL` to answer a refusal that names them. Every value goes in single quotes, with a quote inside one spelled `'\''`, because the shell reads the line before make does.

`make create` reads `PIPELEX_API_KEY` from the shell environment, or from an `.env.local` already in the project, and refuses without one. Give it several minutes: on a fresh copy it installs the dependencies, and it ends with a production build. It commits nothing. It names variables and never prints their values, so the log's tail is safe to read; the `.env.local` it wrote is not.

**The gesture's warnings are read from the whole log, not from its tail.** `make create` prints its own warnings as `! …` and the bootstrap's as `warning: …`, all before `make all`, whose output fills the tail, and it runs the bootstrap twice, so the block's last line lists each distinct warning once. Every one goes into the report with what answers it. An MIT project whose user named no copyright holder always gets `warning: LICENSE copyright line left untouched — pass --license-holder to claim it.`: the project's `LICENSE` still names the template's copyright holder, and since the gesture refuses a project it has already made, the answer is now an edit of that line, by the user, or by you with the holder they name.

A non-zero exit is one of the two cases under [After the initializer](#after-the-initializer). On `0`, go on to `make serve`. The report is the method app's, and its git outcome is the pristine commit you made or found.
