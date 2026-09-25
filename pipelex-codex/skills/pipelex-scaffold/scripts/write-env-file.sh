#!/usr/bin/env bash
# The env file of /pipelex-scaffold's initializer branch: `.env.example` with the two Pipelex
# lines, `.env` ignored by git, then `.env` copied from the example and filled from the shell.
#
# Usage: write-env-file.sh <dir>
#
# It prints one line and never a value. The line opens with a verdict on the key, and the stop
# table and the report key on it:
#   <key> base-url=<origin> plane=<plane>
#     <key>     filled   the key was copied from the shell's PIPELEX_API_KEY
#               kept     `.env` already carried a key, so it was not touched
#               empty    no key: the user fills `.env`'s PIPELEX_API_KEY= line
#     <origin>  copied   the shell's PIPELEX_BASE_URL was copied into `.env`
#               file     `.env`'s own line stands: the example's production URL, or the user's
#     <plane>   production when the base URL `.env` resolves to is https://api.pipelex.com, or
#               when it names none; other for any other URL
#   refused: <reason>   no key was written, and <reason> is one of usage, no-directory,
#                       not-a-repository (<dir> is not where the pristine commit leaves it: it
#                       has not run), not-ignored, write-failed (a file in <dir> could not be
#                       written, or `.env` could not be closed to other users before the key
#                       reached it)
# The exit code is presentation: 0 unless refused.
#
# Why every value moves through this shell and never through the model: a value typed into a
# command, a file-editing tool's parameters or a read of the file lands in the transcript, and a
# key there is a key to rotate. The shell expands the variables itself, so only their names are
# ever written down, and the file is read here only to test it.

set -u
# A trace inherited through SHELLOPTS or BASH_ENV would print every expanded value on stderr.
set +x

production=https://api.pipelex.com

refuse() {
  printf 'refused: %s\n' "$1"
  exit 1
}

[ $# -eq 1 ] || refuse usage
# <dir> where it physically is, as the pristine commit reads it.
dir=$(CDPATH= cd -- "$1" 2> /dev/null && pwd -P) || refuse no-directory

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

# The pristine commit left <dir> the root of a repository of its own, a repository planted inside
# another's work tree, which it reports as `nested:`, or a directory inside another repository's
# work tree that does not ignore it, with no repository of its own (`inside:` or `unversioned:`).
# A root is judged by its own rules, which for a nested one are <dir>'s .gitignore files, read by
# the enclosing repository too once the user removes <dir>/.git; a directory with no repository of
# its own by its own rules as well (see project_git). A <dir> outside every work tree, or one its
# enclosing repository ignores, is where the pristine commit makes a repository, so it has not run:
# git could judge no ignore rule there that a repository of the project's reads, and nothing is
# written.
prefix=$(git -C "$dir" rev-parse --show-prefix 2> /dev/null) || refuse not-a-repository
own_rules=
no_index=
if [ -n "$prefix" ]; then
  ! ignored_around || refuse not-a-repository
  own_rules=$(git -C "$dir" rev-parse --absolute-git-dir)
  no_index=--no-index
fi
example="$dir/.env.example"
env="$dir/.env"

# Whether <file> assigns <name>, in any form a dotenv reader accepts.
assigns() {
  grep -Eq "^[[:space:]]*(export[[:space:]]+)?$2[[:space:]]*=" "$1"
}

# Appends to <file> whichever of the two Pipelex lines it lacks. A line it carries is never
# repeated, since a dotenv reader resolves a repeated name to its later line.
add_missing_lines() {
  lines=
  assigns "$1" PIPELEX_BASE_URL || lines="PIPELEX_BASE_URL=$production"$'\n'
  assigns "$1" PIPELEX_API_KEY || lines="${lines}PIPELEX_API_KEY="$'\n'
  [ -z "$lines" ] || printf '\n%s' "$lines" >> "$1" || refuse write-failed
}

# The example carries the two lines every Pipelex project shares; an example the initializer
# wrote for its own variables keeps them, and gains whichever of the two it lacks.
if [ ! -e "$example" ]; then
  printf 'PIPELEX_BASE_URL=%s\nPIPELEX_API_KEY=\n' "$production" > "$example" || refuse write-failed
else
  add_missing_lines "$example"
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

# An initializer's `.env*` rule, which create-next-app writes, hides the example as well, and a
# hidden example is never reviewed, committed or carried by a clone. With no repository of its own,
# a rule in an enclosing repository's .gitignore files is that repository's policy for its whole
# tree, which the project's .gitignore adds to and never lifts, and project_git does not read it.
if project_git check-ignore $no_index -q -- .env.example; then
  printf '\n!.env.example\n' >> "$dir/.gitignore" || refuse write-failed
fi

# `.env` is ignored before a key can reach it, and nothing is written when it cannot be.
if ! ignored_by_the_project .env; then
  printf '\n.env\n' >> "$dir/.gitignore" || refuse write-failed
  ignored_by_the_project .env || refuse not-ignored
fi
# Read with no index, the project's rules cannot see a `<dir>/.env` the enclosing repository tracks,
# which no rule ignores: that repository answers for its own index.
[ -z "$own_rules" ] || git -C "$dir" check-ignore -q -- .env || refuse not-ignored

# An existing `.env` is never overwritten: it may hold a key the user filled. A new one is
# readable by its owner alone, since it is about to hold a key.
if [ ! -e "$env" ]; then
  (umask 077 && cp "$example" "$env") || refuse write-failed
fi

# The value a dotenv reader resolves for a name: its last assignment, with an `export ` prefix, the
# spaces around `=` and one pair of quotes taken off. It is read into the shell and never printed.
resolved() {
  sed -n -E "s/^[[:space:]]*(export[[:space:]]+)?$1[[:space:]]*=[[:space:]]*//p" "$env" | tail -n 1 |
    sed -E -e 's/[[:space:]]+$//' -e 's/^"(.*)"$/\1/' -e "s/^'(.*)'\$/\1/"
}

# One test on the file's key decides whether anything is written. A file that carries a key is
# left as it is, because every dotenv reader resolves a repeated name to its later line, so an
# append after the user's lines would silently replace them. The base URL cannot carry a test of
# its own: the example ships its line non-empty. A file without a key gains the lines it lacks, so
# the report's `PIPELEX_API_KEY=` line is there. A base URL the shell sets is copied with a key or
# without one, since it is the plane the user declared, and a key is refused by every plane but
# the one that issued it. The comment goes out once, and only when a line follows it.
origin=file
key=empty
if [ -n "$(resolved PIPELEX_API_KEY)" ]; then
  key=kept
else
  add_missing_lines "$env"
  if [ -n "${PIPELEX_API_KEY:-}${PIPELEX_BASE_URL:-}" ]; then
    # A `.env` the initializer wrote was made under the user's umask, readable by others as often
    # as not. Only the group's and others' bits go, so a file its owner made read-only stays so.
    [ -z "${PIPELEX_API_KEY:-}" ] || chmod go-rwx "$env" || refuse write-failed
    {
      printf '\n# Copied from the shell environment; a later line overrides an earlier one.\n'
      [ -z "${PIPELEX_API_KEY:-}" ] || printf 'PIPELEX_API_KEY=%s\n' "$PIPELEX_API_KEY"
      [ -z "${PIPELEX_BASE_URL:-}" ] || printf 'PIPELEX_BASE_URL=%s\n' "$PIPELEX_BASE_URL"
    } >> "$env" || refuse write-failed
    [ -z "${PIPELEX_API_KEY:-}" ] || key=filled
    [ -z "${PIPELEX_BASE_URL:-}" ] || origin=copied
  fi
fi

# The plane the file resolves to, read as a dotenv reader reads it.
url=$(resolved PIPELEX_BASE_URL)
url=${url%/}
if [ -z "$url" ] || [ "$url" = "$production" ]; then plane=production; else plane=other; fi

printf '%s base-url=%s plane=%s\n' "$key" "$origin" "$plane"
