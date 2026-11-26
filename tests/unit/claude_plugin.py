"""The built Claude plugin copied under a root whose path holds a space, and its commands as Claude Code starts them.

Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` into a hook's or an MCP server's `command` and `args` as a plain string
and spawns the result with no shell, so the commands here are the manifest's and `hooks.json`'s own, with the root
substituted the same way: on Windows that gives a path with native backslashes followed by the forward slashes the
templates write.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).parents[2]
BUILT_PLUGIN = REPO_ROOT / "pipelex"
ROOT_PLACEHOLDER = "${CLAUDE_PLUGIN_ROOT}"
SPACED_ROOT_NAME = "plug in"
# What reaches the validate stage or the workshop's credentials: removed so that a test decides what the scripts see.
CREDENTIAL_PREFIXES = ("PIPELEX_", "CLAUDE_PLUGIN_OPTION_")


def copy_built_plugin(parent: Path) -> Path:
    """The checked-in `pipelex/` manifest and hooks, copied to `<parent>/plug in/pipelex`, which the build keeps fresh."""
    root = parent / SPACED_ROOT_NAME / "pipelex"
    for name in (".claude-plugin", "hooks"):
        shutil.copytree(BUILT_PLUGIN / name, root / name)
    return root


def substituted(value: str, plugin_root: Path) -> str:
    """`value` with the plugin root put in as Claude Code puts it: a plain string replacement."""
    return value.replace(ROOT_PLACEHOLDER, str(plugin_root))


def mcp_server_command(plugin_root: Path) -> list[str]:
    """The `pipelex` MCP server's command line, as the manifest declares it."""
    manifest = json.loads((plugin_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    server = manifest["mcpServers"]["pipelex"]
    return [substituted(server["command"], plugin_root), *(substituted(arg, plugin_root) for arg in server["args"])]


def hook_commands(plugin_root: Path) -> list[list[str]]:
    """Every command hook's command line, as `hooks.json` declares it in the exec form."""
    config: dict[str, Any] = json.loads((plugin_root / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    commands: list[list[str]] = []
    for groups in cast("dict[str, list[dict[str, Any]]]", config["hooks"]).values():
        for group in groups:
            for hook in group["hooks"]:
                if hook.get("type") == "command":
                    commands.append([substituted(hook["command"], plugin_root), *(substituted(arg, plugin_root) for arg in hook.get("args", []))])
    return commands


def clean_environment(**overrides: str) -> dict[str, str]:
    """This process's environment without any Pipelex credential, then `overrides`."""
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith(CREDENTIAL_PREFIXES)}
    environment["DO_NOT_TRACK"] = "1"
    environment.update(overrides)
    return environment
