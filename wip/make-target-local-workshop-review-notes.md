# Local-workshop make targets: deferred review findings

Findings the `/rev` passes on `feature/Make-target-local-workshop` (item L-260926-2b15c9) deferred rather than fixed. The first four were raised in round 3, whose bar (`necessity`) fixes only a defect the previous pass introduced or one too severe to ship with, and none of them is either; Codex raised all four again in round 4. The last was raised in round 4, whose bar (`freeze`) fixes only a critical. **None of them was verified**: each rests on its reviewer's word, read against the code but not reproduced.

## The local copy's credential guidance points at the plugin configuration

- **Reporter:** Codex (P2), `scripts/local_mcp.py`, `render_claude_copy`.
- **Claim:** the copy `make claude-local-mcp` renders keeps the shipped `credentials.md`, which tells the agent to answer a `config`-class authentication error by setting the key in the plugin's configuration and never by telling the user to export a shell variable. In this workflow the copy's plugin options are empty and the workshop takes its key from the shell's `PIPELEX_API_KEY`, so the recovery instruction is the wrong one.
- **Why deferred:** it predates the review passes, and the target already prints a warning naming `PIPELEX_API_KEY` when the shell has none. Whether `pipelex@inline` exposes a configuration dialog at all is unknown, which decides the right wording.
- **When picked up:** render the copy with a variable that switches the Claude branch of `templates/skills/shared/credentials.md.j2` to the shell channel, and extend `TestClaudeCopy`'s file-for-file comparison to allow that difference.

## The Makefile's `VIRTUAL_ENV` reaches the session

- **Reporter:** cubic (P2), `scripts/local_mcp.py`, `MAKE_STATE`.
- **Claim:** the Makefile sets `VIRTUAL_ENV := $(CURDIR)/.venv`. When the shell has a virtual environment active, make hands its commands that value, and the harness inherits it, so a tool in the user's project that reads `VIRTUAL_ENV` acts on this repository's `.venv` while `PATH` still names the user's.
- **Why deferred:** it needs an active virtual environment in the shell that starts the target, and it predates the environment filter. The filter could restore the shell's value only if the Makefile passed it along, since make has replaced it by the time the script runs.

## For an instant during the swap there is no copy

- **Reporter:** cubic (P3), `scripts/local_mcp.py`, `render_claude_copy`.
- **Claim:** between `final.rename(retired)` and `staging.rename(final)` the copy's path does not exist, so a session of the same workshop respawning its server or running its hook at that instant fails.
- **Why deferred:** the window is two renames long and needs a second start of the same workshop at that moment. An atomic flip, a symlink replaced with `os.replace`, would close it.

## A relative harness path is executed after the `chdir`

- **Reporter:** cubic (P3), `scripts/local_mcp.py`, `start`.
- **Claim:** `shutil.which` returns a relative path when the matching `PATH` entry is relative, such as `.` or `node_modules/.bin`, and `start` then changes to `WORKDIR` before `os.execve`, so the path resolves against the wrong directory.
- **Why deferred:** it needs a relative `PATH` entry ahead of the harness's real location. Making `program` absolute before the `chdir` fixes it.

## The headless Codex recipe needs a git repository

- **Reporter:** cubic (P3), `.claude/skills/pipelex-mcp-source/SKILL.md` and `docs/development.md`, the headless form.
- **Claim:** both recommend `make codex-local-mcp MCP=<path> WORKDIR=<scratch project> ARGS='exec "…"'`, and `codex exec` refuses to run outside a git repository or a directory Codex already trusts unless it is given `--skip-git-repo-check`, so the recipe stops before the workshop starts in a fresh scratch directory.
- **Why deferred:** it is documentation, and a scratch project that is a git repository, or one Codex already trusts, runs as written.
- **When picked up:** add `--skip-git-repo-check` to the `exec` example in both places, or say the scratch project must be a git repository.
