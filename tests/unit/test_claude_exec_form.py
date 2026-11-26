from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.check import check_claude_exec_form

REPO_ROOT = Path(__file__).parents[2]
LAUNCHER_ARG = "${CLAUDE_PLUGIN_ROOT}/hooks/launch-pipelex-mcp.mjs"
HOOK_ARG = "${CLAUDE_PLUGIN_ROOT}/hooks/check-mthds.mjs"


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """The repository's targets and the built Claude plugin's manifest and hooks, the bundle left out."""
    shutil.copytree(REPO_ROOT / "targets", tmp_path / "targets")
    shutil.copytree(REPO_ROOT / "pipelex" / ".claude-plugin", tmp_path / "pipelex" / ".claude-plugin")
    shutil.copytree(REPO_ROOT / "pipelex" / "hooks", tmp_path / "pipelex" / "hooks", ignore=shutil.ignore_patterns("check.mjs"))
    return tmp_path


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{path.name} no longer holds {old!r}"
    path.write_text(text.replace(old, new), encoding="utf-8")


class TestClaudeExecForm:
    def test_the_built_plugin_starts_both_as_node_scripts(self, tree: Path) -> None:
        assert check_claude_exec_form(tree) == []

    def test_the_checked_in_plugin_passes(self) -> None:
        assert check_claude_exec_form(REPO_ROOT) == []

    @pytest.mark.parametrize(
        ("file", "old", "new", "expected"),
        [
            (
                "hooks/hooks.json",
                '"command": "node",\n            "args": ["' + HOOK_ARG + '"],',
                '"command": "\\"${CLAUDE_PLUGIN_ROOT}\\"/hooks/check-mthds.sh",',
                "a PostToolUse hook is not started as `node <script>`",
            ),
            ("hooks/hooks.json", HOOK_ARG, "${CLAUDE_PLUGIN_ROOT}/hooks/gone.mjs", "which the target does not ship"),
            ("hooks/hooks.json", HOOK_ARG, "hooks/check-mthds.mjs", "which is not a script under ${CLAUDE_PLUGIN_ROOT}"),
            (
                ".claude-plugin/plugin.json",
                '"command": "node"',
                '"command": "' + LAUNCHER_ARG.replace(".mjs", ".sh") + '"',
                "the `pipelex` server is not started",
            ),
            (".claude-plugin/plugin.json", LAUNCHER_ARG, "${CLAUDE_PLUGIN_ROOT}/hooks/launch-pipelex-mcp.sh", "which the target does not ship"),
        ],
    )
    def test_a_shell_form_or_a_missing_script_is_refused(self, tree: Path, file: str, old: str, new: str, expected: str) -> None:
        _edit(tree / "pipelex" / file, old, new)
        errors = check_claude_exec_form(tree)
        assert any(expected in error for error in errors), errors

    def test_a_manifest_without_user_config_is_held_to_the_same_form(self, tree: Path) -> None:
        manifest_path = tree / "pipelex" / ".claude-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest["userConfig"]
        manifest["mcpServers"]["pipelex"] = {"type": "stdio", "command": "npx", "args": ["-y", "@pipelex/mcp@latest"]}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        errors = check_claude_exec_form(tree)
        assert any("the `pipelex` server is not started" in error for error in errors), errors

    def test_an_unreadable_hooks_file_is_left_to_other_checks(self, tree: Path) -> None:
        (tree / "pipelex" / "hooks" / "hooks.json").write_text("{", encoding="utf-8")
        assert check_claude_exec_form(tree) == []

    def test_the_manifest_names_the_shipped_launcher(self) -> None:
        manifest = json.loads((REPO_ROOT / "pipelex" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        assert manifest["mcpServers"]["pipelex"]["command"] == "node"
        assert manifest["mcpServers"]["pipelex"]["args"] == [LAUNCHER_ARG]
