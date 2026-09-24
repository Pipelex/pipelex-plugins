#!/usr/bin/env bash
# The pristine commit of /pipelex-scaffold's initializer branch: the repository test, a
# .gitignore that keeps the dependency tree out, the staging and the one commit, all held to
# the project directory. Inside another repository's work tree, ignored there or not, it writes
# the .gitignore alone.
#
# Usage: commit-pristine.sh <dir> <message>
#
# The first line printed is the verdict, and the stop table keys on it:
#   committed: <sha> <subject>   this script made the commit; the staged paths follow, one per line
#   kept: <sha> <subject>        nothing was left to stage, because the initializer committed the
#                                tree itself (create-next-app does); that commit is the pristine one
#   inside: <root>               <dir> lies in the work tree of the repository at <root> and is not
#                                its root: nothing was initialized, staged or committed, and the
#                                project is new files of that repository, as the method app's is
#   ignored: <root>              <dir> lies in the work tree of the repository at <root>, which
#                                ignores it: nothing was initialized, staged or committed, and no
#                                repository versions the project
#   refused: <reason>            nothing was committed, and <reason> is one of usage, no-git,
#                                no-directory, init-failed, write-failed, stage-failed,
#                                nothing-to-commit, commit-failed; git's own message, if any,
#                                goes to stderr
# The exit code is presentation: 0 for committed, kept, inside and ignored, 1 for refused.

set -u

refuse() {
  printf 'refused: %s\n' "$1"
  [ -n "${2:-}" ] && printf '%s\n' "$2" >&2
  exit 1
}

[ $# -eq 2 ] && [ -n "$2" ] || refuse usage "usage: commit-pristine.sh <dir> <message>"
command -v git > /dev/null 2>&1 || refuse no-git
dir=$(CDPATH= cd -- "$1" 2> /dev/null && pwd) || refuse no-directory "no directory at $1"
message=$2

# An initializer that wrote nothing leaves nothing to commit, and a commit of the .gitignore
# below alone would read as a scaffold. A lone .git is the user's repository, not a scaffold.
[ -n "$(ls -A "$dir" | grep -vx '\.git')" ] || refuse nothing-to-commit

# The repository test, never inferred from which initializer ran: `uv init` and create-next-app
# initialize a repository only when no enclosing one exists, so the list of initializers that
# `git init` is not a substitute. `--show-prefix` prints nothing at a repository's root, which
# needs no path comparison and so survives symlinks and letter case. Three outcomes:
#   - outside every work tree, <dir> becomes a repository of its own, and the commit follows;
#   - at a repository's root, the one the initializer made or the user's lone .git, the commit
#     lands there (the skill asks first when the repository was the user's);
#   - inside another repository's work tree, <dir> gets no repository and no commit, as the method
#     app's initializer gives it none: a repository planted there is one the enclosing repository
#     sees as embedded, and `git -C` sets git's working directory without scoping anything, so a
#     staging there would sweep the user's worktree into this commit. The project is new files of
#     that repository, left for the user to review and commit, and its index and HEAD are never
#     touched: only the .gitignore below is written, so that the user's own `git add` never takes
#     the dependency tree or a `.env`.
# The last case splits in two. When the enclosing repository ignores <dir> (an ignored tmp/, a
# dotfiles repository ignoring `*`), no `git add` of the user's takes the project, which then
# prints `ignored:` rather than `inside:`, and still gets no repository: whether to make it one is
# the user's choice.
enclosing=
own_rules=
no_index=
if prefix=$(git -C "$dir" rev-parse --show-prefix 2> /dev/null); then
  if [ -n "$prefix" ]; then
    enclosing=$(git -C "$dir" rev-parse --show-toplevel)
    if git -C "$dir" check-ignore -q .; then
      own_rules=$(git -C "$dir" rev-parse --absolute-git-dir)
      no_index=--no-index
    fi
  fi
else
  error=$(git -C "$dir" init -q -b main 2>&1) || refuse init-failed "$error"
fi

# An ignore rule reaches only untracked paths, so a `.env` or a node_modules/ an initializer had
# already staged would ride into the commit past the lines written below. Unstage what the index
# holds of either and HEAD does not, before those lines are read: a path the user committed is
# theirs, and stays tracked. `-f` because a file rewritten since it was staged, as `npm install`
# rewrites node_modules/.package-lock.json, is otherwise refused; `--cached` leaves the file itself.
# An enclosing repository's index is the user's, and is left alone.
if [ -z "$enclosing" ]; then
  for staged_early in .env node_modules; do
    [ -n "$(git -C "$dir" ls-files --cached -- "$staged_early")" ] || continue
    git -C "$dir" rev-parse -q --verify "HEAD:$staged_early" > /dev/null 2>&1 && continue
    error=$(git -C "$dir" rm -r -q -f --cached -- "$staged_early" 2>&1) || refuse stage-failed "$error"
  done
fi

# git over <dir> as its ignore rules are judged. In a subtree the enclosing repository ignores,
# that repository's rule hides every .gitignore below it and no clone carries the project, so the
# rules judged are <dir>'s own, which a repository made there later reads: the enclosing git
# directory takes <dir> as its work tree, and `$no_index` keeps its index, whose paths are not
# <dir>'s, out of `check-ignore`.
project_git() {
  if [ -n "$own_rules" ]; then
    git -C "$dir" --git-dir="$own_rules" --work-tree="$dir" "$@"
  else
    git -C "$dir" "$@"
  fi
}

# Ignored by a .gitignore the project carries. This machine's global excludes file and the
# repository's info/exclude never travel with a clone, so a teammate's `git add` would take what
# only this machine ignores.
ignored_by_the_project() {
  project_git -c core.excludesFile=/dev/null check-ignore $no_index -q -- "$1" || return 1
  source=$(project_git -c core.excludesFile=/dev/null check-ignore $no_index -v -- "$1")
  case ${source%%:*} in .gitignore | */.gitignore) return 0 ;; esac
  return 1
}

# `npm init -y` and `tsc --init` write no .gitignore, so the staging would commit the whole
# dependency tree into the commit that is meant to be a readable baseline, and `uv init` writes
# none inside an enclosing repository. A Python project gets Python's lines and any other gets
# Node's. An initializer's own .gitignore is kept, and gains only what it does not ignore of what
# is there: a node_modules/, whatever the language, and a `.env` the initializer wrote, so that it
# never reaches the commit.
if [ ! -e "$dir/.gitignore" ]; then
  if [ -e "$dir/pyproject.toml" ]; then
    printf '__pycache__/\n*.egg-info/\nbuild/\ndist/\n.venv/\n.env\n' > "$dir/.gitignore" || refuse write-failed
  else
    printf 'node_modules/\ndist/\n.env\n' > "$dir/.gitignore" || refuse write-failed
  fi
fi
if [ -d "$dir/node_modules" ] && ! ignored_by_the_project node_modules; then
  printf '\nnode_modules/\n' >> "$dir/.gitignore" || refuse write-failed
fi
[ ! -e "$dir/.env" ] || ignored_by_the_project .env || printf '\n.env\n' >> "$dir/.gitignore" || refuse write-failed

if [ -n "$enclosing" ]; then
  if [ -n "$own_rules" ]; then
    printf 'ignored: %s\n' "$enclosing"
  else
    printf 'inside: %s\n' "$enclosing"
  fi
  exit 0
fi

# The pathspec is on both commands. `add -A -- .` bounds what is staged, and a commit without
# one would commit the whole index, anything the user had staged included.
error=$(git -C "$dir" add -A -- . 2>&1) || refuse stage-failed "$error"
staged=$(git -C "$dir" diff --cached --name-only -- .)

if [ -z "$staged" ]; then
  # An initializer that commits as well as `git init`s has already made this commit. It is
  # taken as the pristine one, and a second, empty commit is never forced on top of it.
  git -C "$dir" rev-parse -q --verify HEAD > /dev/null || refuse nothing-to-commit
  printf 'kept: %s\n' "$(git -C "$dir" log -1 --format='%h %s')"
  exit 0
fi

error=$(git -C "$dir" commit -q -m "$message" -- . 2>&1) || refuse commit-failed "$error"
printf 'committed: %s\n' "$(git -C "$dir" log -1 --format='%h %s')"
printf '%s\n' "$staged"
