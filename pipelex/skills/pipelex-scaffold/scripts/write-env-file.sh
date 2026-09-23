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
#               kept     `.env` already carried a key, so neither of its lines was touched
#               empty    no key: the user fills `.env`'s PIPELEX_API_KEY= line
#     <origin>  copied   the shell's PIPELEX_BASE_URL was copied into `.env`
#               file     `.env`'s own line stands: the example's production URL, or the user's
#     <plane>   production when the base URL `.env` resolves to is https://api.pipelex.com, or
#               when it names none; other for any other URL
#   refused: <reason>   no key was written, and <reason> is one of usage, no-directory,
#                       not-a-repository, not-ignored
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
dir=$(CDPATH= cd -- "$1" 2> /dev/null && pwd) || refuse no-directory
git -C "$dir" rev-parse --git-dir > /dev/null 2>&1 || refuse not-a-repository
example="$dir/.env.example"
env="$dir/.env"

# The example carries the two lines every Pipelex project shares; an example the initializer
# wrote for its own variables keeps them, and gains the two lines only when it has neither.
if [ ! -e "$example" ]; then
  printf 'PIPELEX_BASE_URL=%s\nPIPELEX_API_KEY=\n' "$production" > "$example"
elif ! grep -q '^PIPELEX_' "$example"; then
  printf '\nPIPELEX_BASE_URL=%s\nPIPELEX_API_KEY=\n' "$production" >> "$example"
fi

# An initializer's `.env*` rule, which create-next-app writes, hides the example as well, and a
# hidden example is never reviewed, committed or carried by a clone.
if git -C "$dir" check-ignore -q -- .env.example; then
  printf '\n!.env.example\n' >> "$dir/.gitignore"
fi

# Ignored by a .gitignore the project carries. This machine's global excludes file and the
# repository's info/exclude never travel with a clone, so a teammate's `git add` would take a
# `.env` that only this machine ignores.
ignored_by_the_project() {
  git -C "$dir" -c core.excludesFile=/dev/null check-ignore -q -- "$1" || return 1
  source=$(git -C "$dir" -c core.excludesFile=/dev/null check-ignore -v -- "$1")
  case ${source%%:*} in .gitignore | */.gitignore) return 0 ;; esac
  return 1
}

# `.env` is ignored before a key can reach it, and nothing is written when it cannot be.
if ! ignored_by_the_project .env; then
  printf '\n.env\n' >> "$dir/.gitignore"
  ignored_by_the_project .env || refuse not-ignored
fi

# An existing `.env` is never overwritten: it may hold a key the user filled.
[ -e "$env" ] || cp "$example" "$env"

# The value a dotenv reader resolves for a name: its last assignment, with an `export ` prefix, the
# spaces around `=` and one pair of quotes taken off. It is read into the shell and never printed.
resolved() {
  sed -n -E "s/^[[:space:]]*(export[[:space:]]+)?$1[[:space:]]*=[[:space:]]*//p" "$env" | tail -n 1 |
    sed -E -e 's/[[:space:]]+$//' -e 's/^"(.*)"$/\1/' -e "s/^'(.*)'\$/\1/"
}

# One test on the file's key decides whether anything is written. A file that carries a key keeps
# both of its lines, because every dotenv reader resolves a repeated name to its later line, so an
# append after the user's key would silently replace it. The base URL cannot carry a test of its
# own: the example ships its line non-empty. A base URL the shell sets is copied with a key or
# without one, since it is the plane the user declared, and a key is refused by every plane but
# the one that issued it. The comment goes out once, and only when a line follows it.
origin=file
if [ -n "$(resolved PIPELEX_API_KEY)" ]; then
  key=kept
elif [ -z "${PIPELEX_API_KEY:-}${PIPELEX_BASE_URL:-}" ]; then
  key=empty
else
  {
    printf '\n# Copied from the shell environment; a later line overrides an earlier one.\n'
    [ -z "${PIPELEX_API_KEY:-}" ] || printf 'PIPELEX_API_KEY=%s\n' "$PIPELEX_API_KEY"
    [ -z "${PIPELEX_BASE_URL:-}" ] || printf 'PIPELEX_BASE_URL=%s\n' "$PIPELEX_BASE_URL"
  } >> "$env"
  if [ -n "${PIPELEX_API_KEY:-}" ]; then key=filled; else key=empty; fi
  [ -z "${PIPELEX_BASE_URL:-}" ] || origin=copied
fi

# The plane the file resolves to, read as a dotenv reader reads it.
url=$(resolved PIPELEX_BASE_URL)
url=${url%/}
if [ -z "$url" ] || [ "$url" = "$production" ]; then plane=production; else plane=other; fi

printf '%s base-url=%s plane=%s\n' "$key" "$origin" "$plane"
