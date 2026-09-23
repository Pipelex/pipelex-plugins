#!/usr/bin/env bash
# The pristine commit of /pipelex-scaffold's initializer branch: the repository test, a
# .gitignore that keeps the dependency tree out, the staging and the one commit, all held to
# the project directory.
#
# Usage: commit-pristine.sh <dir> <message>
#
# The first line printed is the verdict, and the stop table keys on it:
#   committed: <sha> <subject>   this script made the commit; the staged paths follow, one per line
#   kept: <sha> <subject>        nothing was left to stage, because the initializer committed the
#                                tree itself (create-next-app does); that commit is the pristine one
#   refused: <reason>            nothing was committed, and <reason> is one of usage, no-git,
#                                no-directory, init-failed, stage-failed, nothing-to-commit,
#                                commit-failed; git's own message, if any, goes to stderr
# The exit code is presentation: 0 for committed and kept, 1 for refused.

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

# The repository test, never inferred from which initializer ran. <dir> must be the root of a
# repository of its own: with no .git of its own it is governed by whatever repository encloses
# it, which is the user's, and `git -C` sets git's working directory without scoping anything,
# so the staging below would sweep the user's worktree into this commit. `uv init` initializes a
# repository only when no enclosing one exists, so the list of initializers that `git init` is
# not a substitute. `--show-prefix` prints nothing at a repository's root, which needs no path
# comparison and so survives symlinks and letter case.
if ! prefix=$(git -C "$dir" rev-parse --show-prefix 2> /dev/null) || [ -n "$prefix" ]; then
  error=$(git -C "$dir" init -q -b main 2>&1) || refuse init-failed "$error"
fi

# Ignored by a .gitignore the project carries. This machine's global excludes file and the
# repository's info/exclude never travel with a clone, so a teammate's `git add` would take what
# only this machine ignores.
ignored_by_the_project() {
  git -C "$dir" -c core.excludesFile=/dev/null check-ignore -q -- "$1" || return 1
  source=$(git -C "$dir" -c core.excludesFile=/dev/null check-ignore -v -- "$1")
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
    printf '__pycache__/\n*.egg-info/\nbuild/\ndist/\n.venv/\n.env\n' > "$dir/.gitignore"
  else
    printf 'node_modules/\ndist/\n.env\n' > "$dir/.gitignore"
  fi
fi
if [ -d "$dir/node_modules" ] && ! ignored_by_the_project node_modules; then
  printf '\nnode_modules/\n' >> "$dir/.gitignore"
fi
[ ! -e "$dir/.env" ] || ignored_by_the_project .env || printf '\n.env\n' >> "$dir/.gitignore"

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
