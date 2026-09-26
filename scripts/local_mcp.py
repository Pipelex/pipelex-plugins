#!/usr/bin/env python3
"""Start Claude Code or Codex with a Pipelex workshop the plugin does not ship, touching no tracked file.

`make claude-local-mcp` and `make codex-local-mcp` run this. The workshop is a `pipelex-mcp` checkout's
own build (`--mcp`, which runs the checkout's `make build-local` first), spawned as
`node <checkout>/packages/workshop/dist/main.js`, or a published `@pipelex/mcp` (`--mcp-version`),
spawned through `npx` at the exact version npm resolves it to.

- **Claude Code.** The Claude target is rendered by the build's own renderer, with `[vars.mcp_server]`
  `command` and `args` pointed at that workshop and the rest of the table kept, into a directory of
  that workshop's own under `.local-mcp/`, which git ignores, and Claude Code starts with `--plugin-dir` on it. The copy
  loads as `pipelex@inline` and takes the place of an installed `pipelex@pipelex-plugins` for that
  session, so its skills are this checkout's.
- **Codex.** Nothing is rendered. Codex starts with `-c` overrides of its `mcp_servers.pipelex` entry,
  which replace the plugin's entry whole, so they carry the `env_vars` the plugin forwards as well as
  the command. The skills are whichever copy of the plugin Codex has installed.

Either way the workshop takes its key from the shell's `PIPELEX_API_KEY`: the Claude copy's plugin
options arrive empty, since the key saved for the installed plugin is not the inline copy's, and Codex
forwards what `env_vars` names. docs/decisions.md records how each of these was verified.
"""

from __future__ import annotations

import argparse
import dataclasses
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NoReturn, cast

from scripts.gen_skill_docs import (
    MCP_SERVER_NAME,
    TARGETS_DIR_NAME,
    build_target,
    load_target_config,
    merge_template_vars,
    remove_path,
    write_files,
)

# Where the Claude copies are rendered, one per workshop, relative to the repository root. `.gitignore` lists it.
LOCAL_DIR_NAME = ".local-mcp"

# What `make build-local` writes in a pipelex-mcp checkout, and the manifest npm publishes it from.
WORKSHOP_BUNDLE = Path("packages/workshop/dist/main.js")
WORKSHOP_MANIFEST = Path("packages/workshop/package.json")
WORKSHOP_PACKAGE = "@pipelex/mcp"

# The variables a make target hands its commands beside its own: make's, then this repository's
# local-workshop targets'. None of them reaches the checkout's build.
MAKE_HANDOFF = frozenset({"MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES", "MAKELEVEL", "MCP", "MCP_VERSION", "WORKDIR", "ARGS"})

CLAUDE_TARGET = "prod"
CODEX_TARGET = "codex"
KEY_VARIABLE = "PIPELEX_API_KEY"


class Harness(StrEnum):
    CLAUDE = "claude"
    CODEX = "codex"


@dataclass(frozen=True)
class Launcher:
    """What spawns the workshop, and the words that say which workshop it is."""

    command: str
    args: list[str]
    label: str


def build_checkout(root: Path) -> None:
    """Build the checkout's workshop with its own `make build-local`, given none of the make target's variables.

    make hands the commands of a target the variables on its command line, through `MAKEFLAGS` and
    the environment, and a make run from here would read them there: `ARGS` or `MCP` would then
    override or fill the checkout's own Makefile.
    """
    make = shutil.which("make")
    if make is None:
        msg = "make is not on the PATH, and a checkout's workshop is built with its `make build-local`."
        raise SystemExit(msg)
    environment = {name: value for name, value in os.environ.items() if name not in MAKE_HANDOFF}
    completed = subprocess.run([make, "--no-print-directory", "-C", str(root), "build-local"], env=environment, check=False)
    if completed.returncode != 0:
        msg = f"`make build-local` failed in {root}, so no workshop was started."
        raise SystemExit(msg)


def checkout_launcher(checkout: Path, build: Callable[[Path], None] = build_checkout) -> Launcher:
    """The workshop of a `pipelex-mcp` checkout or worktree, built now and spawned by absolute path.

    Absolute, because the harness spawns the workshop from the session's working directory, which is
    neither this repository nor the checkout.
    """
    root = checkout.expanduser().resolve()
    if not root.is_dir():
        msg = f"There is no pipelex-mcp checkout at {root}: pass MCP=<path to a checkout or worktree of pipelex-mcp>."
        raise SystemExit(msg)
    build(root)
    bundle = root / WORKSHOP_BUNDLE
    if not bundle.is_file():
        msg = f"{bundle} does not exist after `make build-local` in {root}: MCP must name a pipelex-mcp checkout that builds the workshop package."
        raise SystemExit(msg)
    return Launcher(command="node", args=[str(bundle)], label=f"the build in {root} ({WORKSHOP_PACKAGE} {_manifest_version(root)})")


def _manifest_version(root: Path) -> str:
    """The version the checkout's workshop manifest names, which is what its handshake reports."""
    try:
        manifest = json.loads((root / WORKSHOP_MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "of unknown version"
    version = cast("dict[str, object]", manifest).get("version") if isinstance(manifest, dict) else None
    return str(version) if version else "of unknown version"


def npm_resolve(spec: str) -> str:
    """The one published version of the workshop that `spec`, a version or a dist-tag, names.

    Asked before anything starts, because a spec npm cannot resolve would otherwise fail only when
    the harness spawns the workshop, as an npx error inside the session.
    """
    npm = shutil.which("npm")
    if npm is None:
        msg = "npm is not on the PATH, and a published workshop is spawned through npx."
        raise SystemExit(msg)
    query = f"{WORKSHOP_PACKAGE}@{spec}"
    completed = subprocess.run([npm, "view", query, "version", "--json"], capture_output=True, text=True, check=False)
    resolved = _json_answer(completed.stdout)
    listing = f"`npm view {WORKSHOP_PACKAGE} versions` lists the published ones"
    # npm answers an error as a JSON object on stdout, beside its exit status, and a version as a JSON string.
    error = _npm_error_summary(resolved)
    if completed.returncode != 0 or error is not None:
        stderr_lines = [line.strip() for line in completed.stderr.splitlines() if line.strip()]
        reason = error or (stderr_lines[-1] if stderr_lines else "no reason given")
        msg = f"`npm view {query} version` failed ({reason}): {listing}."
        raise SystemExit(msg)
    if resolved is None:
        msg = f"No published {WORKSHOP_PACKAGE} matches {spec!r}: {listing}."
        raise SystemExit(msg)
    if isinstance(resolved, list):
        versions = [str(item) for item in cast("list[object]", resolved)]
        msg = f"{spec!r} matches several published versions ({', '.join(versions)}): name one."
        raise SystemExit(msg)
    return str(resolved)


def _json_answer(stdout: str) -> object:
    """What `npm view --json` printed, parsed: None for nothing, the text itself when it is not JSON."""
    text = stdout.strip()
    if not text:
        return None
    try:
        parsed: object = json.loads(text)
    except ValueError:
        return text
    return parsed


def _npm_error_summary(answer: object) -> str | None:
    """The summary of the error object `npm view --json` prints when it fails, or None when the answer is not one."""
    if not isinstance(answer, dict):
        return None
    error = cast("dict[str, object]", answer).get("error")
    summary = cast("dict[str, object]", error).get("summary") if isinstance(error, dict) else None
    return str(summary) if summary else "npm answered an error with no summary"


def published_launcher(spec: str, resolve: Callable[[str], str] = npm_resolve) -> Launcher:
    """A published workshop, pinned to the exact version `spec` resolves to now, so the one checked is the one spawned."""
    version = resolve(spec)
    return Launcher(command="npx", args=["-y", f"{WORKSHOP_PACKAGE}@{version}"], label=f"{WORKSHOP_PACKAGE} {version} from npm")


def workshop_key(launcher: Launcher) -> str:
    """The name of the directory under `.local-mcp/` that holds the copy spawning `launcher`, one per workshop."""
    return hashlib.sha256("\0".join([launcher.command, *launcher.args]).encode()).hexdigest()[:12]


def render_claude_copy(base_dir: Path, launcher: Launcher) -> Path:
    """Render the Claude target with `launcher` as its workshop into `.local-mcp/<key>/<plugin>/`, and return that directory.

    The target's `[vars.mcp_server]` table gets the launcher's `command` and `args` and keeps the rest,
    `user_config` among it, by the merge every target's own table goes through, so the copy is what
    `make build` would ship but for the workshop it spawns.

    Each workshop has a copy of its own, because a session reads its launcher again whenever it
    respawns the server: in one shared copy, a later start with another workshop would change the
    workshop of every session already running. A copy is rendered into a staging directory of this
    run's own and swapped in under a lock, so two starts at once never write into each other's files,
    and a session running from the copy never meets a half-written plugin.
    """
    shipped = load_target_config(base_dir / TARGETS_DIR_NAME, CLAUDE_TARGET)
    workshop_dir = base_dir / LOCAL_DIR_NAME / workshop_key(launcher)
    workshop_dir.mkdir(parents=True, exist_ok=True)
    final = workshop_dir / shipped.plugin_name
    retired = workshop_dir / f".{shipped.plugin_name}.retired"
    staging = Path(tempfile.mkdtemp(prefix=f".{shipped.plugin_name}.staging-", dir=workshop_dir))
    try:
        template_vars = merge_template_vars(shipped.template_vars, {"mcp_server": {"command": launcher.command, "args": launcher.args}})
        config = dataclasses.replace(shipped, source=f"{staging.relative_to(base_dir).as_posix()}/", template_vars=template_vars)
        write_files(build_target(base_dir, config).files)
        with (workshop_dir / ".lock").open("w", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            remove_path(retired)
            if final.exists() or final.is_symlink():
                final.rename(retired)
            staging.rename(final)
            remove_path(retired)
    finally:
        remove_path(staging)
    return final


def codex_env_vars(base_dir: Path) -> list[str]:
    """The variable names the Codex plugin's entry forwards into the workshop's environment."""
    server = load_target_config(base_dir / TARGETS_DIR_NAME, CODEX_TARGET).template_vars.get("mcp_server")
    names = server.get("env_vars") if isinstance(server, dict) else None
    if not isinstance(names, list) or not names:
        msg = f"targets/{CODEX_TARGET}.toml resolves no [vars.mcp_server] env_vars, so the workshop would start without a key."
        raise SystemExit(msg)
    return [str(name) for name in cast("list[object]", names)]


def codex_overrides(launcher: Launcher, env_vars: list[str]) -> list[str]:
    """The `-c` arguments that point Codex's `mcp_servers.pipelex` entry at `launcher`.

    An entry at the configuration tier replaces the plugin's whole rather than merging into it, and
    Codex spawns a server with a minimal environment, so the names the plugin forwards are set again
    here or the workshop starts without the shell's key.
    """
    entry = f"mcp_servers.{MCP_SERVER_NAME}"
    return [
        "-c",
        f"{entry}.command={toml_string(launcher.command)}",
        "-c",
        f"{entry}.args={toml_array(launcher.args)}",
        "-c",
        f"{entry}.env_vars={toml_array(env_vars)}",
    ]


def toml_string(value: str) -> str:
    """`value` as a TOML basic string, which is how Codex parses the value of a `-c` override."""
    escaped: list[str] = []
    for char in value:
        if char in {'"', "\\"}:
            escaped.append(f"\\{char}")
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            escaped.append(f"\\u{ord(char):04x}")
        else:
            escaped.append(char)
    return f'"{"".join(escaped)}"'


def toml_array(values: list[str]) -> str:
    """`values` as a TOML array of basic strings."""
    return f"[{', '.join(toml_string(value) for value in values)}]"


def start(harness: Harness, launcher: Launcher, workdir: Path, passthrough: list[str], base_dir: Path) -> NoReturn:
    """Prepare `harness` to spawn `launcher` as its Pipelex workshop, say what runs, and replace this process with it."""
    program = shutil.which(harness.value)
    if program is None:
        msg = f"`{harness.value}` is not on the PATH."
        raise SystemExit(msg)

    lines = [f"• Workshop: {launcher.label}"]
    match harness:
        case Harness.CLAUDE:
            plugin_dir = render_claude_copy(base_dir, launcher)
            command = [program, "--plugin-dir", str(plugin_dir), *passthrough]
            lines.append(f"• Plugin: {plugin_dir}, this checkout's skills, loaded as pipelex@inline in place of an installed pipelex")
        case Harness.CODEX:
            command = [program, *codex_overrides(launcher, codex_env_vars(base_dir)), *passthrough]
            lines.append("• Plugin: the one Codex has installed, its pipelex server entry overridden for this session")
    lines.append(f"• Starting {harness.value} in {workdir}")
    if not os.environ.get(KEY_VARIABLE):
        lines.append(
            f"• Warning: {KEY_VARIABLE} is not set in this shell. Started this way, the workshop takes its key from there alone, "
            "so the Pipelex tools will answer Unauthorized. Export the key and start again."
        )
    print("\n".join(lines), flush=True)

    os.chdir(workdir)
    os.execv(program, command)


def split_passthrough(argv: list[str]) -> tuple[list[str], list[str]]:
    """This script's own arguments, and what follows the first `--`, which goes to the harness as it is."""
    if "--" in argv:
        marker = argv.index("--")
        return argv[:marker], argv[marker + 1 :]
    return argv, []


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("harness", choices=[harness.value for harness in Harness], help="The agent to start.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--mcp", type=Path, help="A pipelex-mcp checkout or worktree, built with its `make build-local` first (the Makefile's MCP).")
    source.add_argument("--mcp-version", help=f"A published {WORKSHOP_PACKAGE} version or dist-tag (the Makefile's MCP_VERSION).")
    parser.add_argument("--workdir", type=Path, default=Path(), help="Where the session starts, and so where the workshop resolves a { path } file.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    own, passthrough = split_passthrough(sys.argv[1:] if argv is None else argv)
    args = parse_args(own)
    base_dir = Path(__file__).resolve().parent.parent
    workdir: Path = args.workdir.expanduser().resolve()
    if not workdir.is_dir():
        msg = f"WORKDIR {workdir} is not a directory."
        raise SystemExit(msg)
    launcher = checkout_launcher(args.mcp) if args.mcp is not None else published_launcher(args.mcp_version)
    start(Harness(args.harness), launcher, workdir, passthrough, base_dir)


if __name__ == "__main__":
    sys.exit(main())
