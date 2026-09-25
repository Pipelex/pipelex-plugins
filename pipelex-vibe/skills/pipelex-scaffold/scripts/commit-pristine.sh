#!/usr/bin/env bash
# The pristine commit of /pipelex-scaffold's initializer branch: the repository test, a
# .gitignore that keeps the dependency tree out, the staging and the one commit, all held to
# the project directory. Inside another repository's work tree that does not ignore <dir>, and
# in a repository planted there, it writes the .gitignore alone.
#
# Usage: commit-pristine.sh <dir> <message>
#
# The first line printed is the verdict, and the stop table keys on it:
#   committed: <sha> <subject>   this script made the commit; the staged paths follow, one per line
#   kept: <sha> <subject>        nothing was left to stage, because the initializer committed the
#                                tree itself (create-next-app does); that commit is the pristine one
#   inside: <root>               <dir> lies in the work tree of the repository at <root>, which does
#                                not ignore it, and is not its root: nothing was initialized, staged
#                                or committed, and the project is new files of that repository, as
#                                the method app's is
#   unversioned: <root>          as inside:, but that repository ignores every file of the project,
#                                though not its directory, and tracks none: no repository versions it
#   nested: <root>               <dir> is the root of a repository that lies in the work tree of the
#                                repository at <root>, which does not ignore it, planted there by the
#                                initializer or the user: nothing was staged or committed in either,
#                                and <dir>/.git is left where it is, since removing it is the user's
#                                choice
#   refused: <reason>            nothing was committed, and <reason> is one of usage, no-git,
#                                no-directory, init-failed, write-failed, stage-failed,
#                                nothing-to-commit, commit-failed; git's own message, if any,
#                                goes to stderr
# The exit code is presentation: 0 for committed, kept, inside, unversioned and nested, 1 for
# refused.

set -u

refuse() {
  printf 'refused: %s\n' "$1"
  [ -n "${2:-}" ] && printf '%s\n' "$2" >&2
  exit 1
}

[ $# -eq 2 ] && [ -n "$2" ] || refuse usage "usage: commit-pristine.sh <dir> <message>"
command -v git > /dev/null 2>&1 || refuse no-git
# <dir> where it physically is: a symlinked <dir> lies in the work tree its target lies in, which
# every git command below reads from, so its parent is the target's and not the link's.
dir=$(CDPATH= cd -- "$1" 2> /dev/null && pwd -P) || refuse no-directory "no directory at $1"
message=$2

# An initializer that wrote nothing leaves nothing to commit, and a commit of the .gitignore
# below alone would read as a scaffold. A lone .git is the user's repository, not a scaffold.
[ -n "$(ls -A "$dir" | grep -vx '\.git')" ] || refuse nothing-to-commit

# Whether the repository whose work tree holds <dir>'s parent ignores <dir>, the directory: then a
# repository there is as invisible to it as plain files would be. It is asked from the parent,
# naming <dir> with no trailing slash: git reads a path as a directory when one stands there, and
# a slash, which asking from inside as `.` adds, makes `*` and `<name>/*` match an empty last name,
# so a directory a later pattern re-includes (`!*/`) would read as ignored. The `./` keeps a
# leading `:` from reading as pathspec magic, which `--literal-pathspecs` cannot, since
# check-ignore refuses it. Any answer but a plain yes reads as not ignored, because mistaking a
# tracked directory for an ignored one plants a repository in the user's tracked tree, and git
# reads a directory holding a tracked path as not ignored whatever the patterns say.
ignored_around() {
  parent=${dir%/*}
  git -C "${parent:-/}" check-ignore -q -- "./${dir##*/}"
}

# The repository test, never inferred from which initializer ran: `uv init` and create-next-app
# initialize a repository only when no enclosing one exists, so the list of initializers that
# `git init` is not a substitute. `--show-prefix` prints nothing at a repository's root, which
# needs no path comparison and so survives symlinks and letter case. The outcomes:
#   - outside every work tree, and where the enclosing repository ignores <dir> (an ignored tmp/, a
#     dotfiles repository ignoring `*`), <dir> becomes a repository of its own, and the commit
#     follows: under an ignored path a repository makes the enclosing one fail no `git add -A` and
#     shows it nothing, while without one the project has no baseline for its first diff and the
#     enclosing repository's `git clean -fdx` deletes it;
#   - at a repository's root, the one the initializer made or the user's lone .git, the commit
#     lands there (the skill asks first when the repository was the user's), unless that root lies
#     in another repository's work tree that does not ignore it, which the last case below covers;
#   - inside another repository's work tree that does not ignore <dir>, <dir> gets no repository
#     and no commit, as the method app's initializer gives it none: a repository planted there is
#     one the enclosing repository sees as embedded, and `git -C` sets git's working directory
#     without scoping anything, so a staging there would sweep the user's worktree into this
#     commit. What counts is the directory, not its files: under `*` then `!*/`, or `<name>/*`,
#     the directory is visible though every file in it is ignored, and a repository there would
#     still show. The project is new files of that repository, left for the user to review and
#     commit, or, when it shows none of them, under no version control; its index and HEAD are
#     never touched, and only the .gitignore below is written, so that no `git add` takes the
#     dependency tree or a `.env`, the enclosing repository's or one the user makes there later.
# A repository root can lie inside another work tree too, when an initializer ran `git init`
# there anyway (create-astro tests only for a .git of <dir>'s own) or the user made one. The empty
# prefix reads as a root like any other, so the parent directory is asked as well, and a root the
# enclosing repository does not ignore gets no commit, for the reason above: once it has one, the
# enclosing repository stages it as a pointer to that commit, which no clone can fetch, and stops
# carrying the project's files. It prints `nested:`, its .gitignore is written by its own rules,
# which are <dir>'s .gitignore files that the enclosing repository reads as well once <dir>/.git
# is gone, and neither its index nor its .git is touched: removing that is the user's choice,
# never this script's.
enclosing=
nested=
if prefix=$(git -C "$dir" rev-parse --show-prefix 2> /dev/null); then
  if [ -z "$prefix" ]; then
    parent=${dir%/*}
    around=$(git -C "${parent:-/}" rev-parse --show-toplevel 2> /dev/null) && ! ignored_around && nested=$around
  elif ignored_around; then
    error=$(git -C "$dir" init -q -b main 2>&1) || refuse init-failed "$error"
  else
    enclosing=$(git -C "$dir" rev-parse --show-toplevel)
  fi
else
  error=$(git -C "$dir" init -q -b main 2>&1) || refuse init-failed "$error"
fi

# With no repository of its own, the project is judged by its own rules, whichever verdict it gets
# (see project_git below).
own_rules=
no_index=
if [ -n "$enclosing" ]; then
  own_rules=$(git -C "$dir" rev-parse --absolute-git-dir)
  no_index=--no-index
fi

# An ignore rule reaches only untracked paths, so a `.env` or a node_modules/ an initializer had
# already staged would ride into the commit past the lines written below. Unstage what the index
# holds of either and HEAD does not, before those lines are read: a path the user committed is
# theirs, and stays tracked. `-f` because a file rewritten since it was staged, as `npm install`
# rewrites node_modules/.package-lock.json, is otherwise refused; `--cached` leaves the file itself.
# An enclosing repository's index is the user's, and is left alone, and so is a nested one's.
if [ -z "$enclosing" ] && [ -z "$nested" ]; then
  for staged_early in .env node_modules; do
    [ -n "$(git -C "$dir" ls-files --cached -- "$staged_early")" ] || continue
    git -C "$dir" rev-parse -q --verify "HEAD:$staged_early" > /dev/null 2>&1 && continue
    error=$(git -C "$dir" rm -r -q -f --cached -- "$staged_early" 2>&1) || refuse stage-failed "$error"
  done
fi

# git over <dir> as its ignore rules are judged. With no repository of its own, <dir> is judged by
# its own rules, whether the enclosing repository shows its files or not: a line in <dir>'s own
# .gitignore binds that repository too, since a deeper .gitignore decides over those above it, and
# binds a repository the user makes there later, which reads no other, while a rule of the
# enclosing repository's, which may ignore every file of the project, binds that repository alone.
# So the enclosing git directory takes <dir> as its work tree, which reads only the .gitignore
# files inside <dir>, and `$no_index` keeps its index, whose paths are not <dir>'s, out of
# `check-ignore`.
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

if [ -n "$nested" ]; then
  printf 'nested: %s\n' "$nested"
  exit 0
fi
if [ -n "$enclosing" ]; then
  # Asked once the .gitignore is written, since the enclosing repository shows that file too unless
  # it ignores it. An empty status alone does not say that it shows none of the project: a project
  # it tracks, deleted and then written again as it was, shows nothing either, so its index must
  # hold nothing under <dir> as well. `--no-optional-locks` keeps the status from rewriting the
  # user's index, and any failure reads as `inside:`.
  if shown=$(git --no-optional-locks -C "$dir" status --porcelain --untracked-files=all -- .) &&
    [ -z "$shown" ] && tracked=$(git -C "$dir" ls-files -- .) && [ -z "$tracked" ]; then
    printf 'unversioned: %s\n' "$enclosing"
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
