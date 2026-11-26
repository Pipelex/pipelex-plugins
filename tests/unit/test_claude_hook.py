"""The Claude plugin's `.mthds` hook, `hooks/check-mthds.mjs`, started as `hooks.json` says: `node <wrapper>`, no shell.

The wrapper runs from a plugin root whose path holds a space, on a project whose path holds one too, with the edited
file named by its native absolute path, backslashes on Windows. The vendored `check.mjs` gives the verdicts; a
stand-in bundle shows what the wrapper hands it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.unit.claude_plugin import clean_environment, copy_built_plugin, hook_commands

HOOK_TIMEOUT_SECONDS = 60
BROKEN_METHOD = """domain = "demo"
description = "Demo"
main_pipe = "say_hello"

[pipe.say_hello]
type = "PipeLLM"
description = "Say hello"
output = "Text"
prompt = "Say hello."
not_a_field = 3
"""
VALID_METHOD = BROKEN_METHOD.replace("not_a_field = 3\n", "")
# Stands in for the bundle: reports the key it sees and the payload it was handed, then exits with STUB_EXIT.
STUB_BUNDLE = """\
let received = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) {
  received += chunk;
}
process.stdout.write(JSON.stringify({ apiKey: process.env.PIPELEX_API_KEY ?? null, received }));
process.stderr.write("stub bundle stderr");
process.exitCode = Number(process.env.STUB_EXIT ?? "0");
"""


def _write_payload(file_path: Path, project: Path) -> str:
    """A `PostToolUse` payload for a `Write`, with the fields Claude Code sends."""
    return json.dumps(
        {
            "session_id": "session-1",
            "transcript_path": "",
            "cwd": str(project),
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": str(file_path), "content": file_path.read_text(encoding="utf-8") if file_path.exists() else ""},
            "tool_response": {"filePath": str(file_path), "success": True},
        }
    )


@pytest.fixture
def plugin_root(tmp_path: Path) -> Path:
    return copy_built_plugin(tmp_path)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    project = tmp_path / "my project"
    (project / "sub dir").mkdir(parents=True)
    return project


def _command(plugin_root: Path) -> list[str]:
    """The one command line both hook entries share, which must be `node <wrapper>`."""
    commands = hook_commands(plugin_root)
    assert commands, "hooks.json declares no command hook"
    assert all(command == commands[0] for command in commands), f"the hook entries start different commands: {commands}"
    assert commands[0][0] == "node" and len(commands[0]) == 2, f"the hook is not started as `node <wrapper>`: {commands[0]}"
    return commands[0]


def _run(plugin_root: Path, project: Path, payload: str, **environment: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _command(plugin_root),
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=project,
        env=clean_environment(**environment),
        timeout=HOOK_TIMEOUT_SECONDS,
        check=False,
    )


def _stub_bundle(plugin_root: Path) -> None:
    (plugin_root / "hooks" / "check.mjs").write_text(STUB_BUNDLE, encoding="utf-8")


@pytest.mark.cross_os
@pytest.mark.usefixtures("node")
class TestClaudeHook:
    def test_a_broken_method_is_blocked_with_its_lint_errors(self, plugin_root: Path, project: Path) -> None:
        method = project / "sub dir" / "broken.mthds"
        method.write_text(BROKEN_METHOD, encoding="utf-8")
        result = _run(plugin_root, project, _write_payload(method, project))
        assert result.returncode == 0, result.stderr
        verdict: dict[str, Any] = json.loads(result.stdout)
        assert verdict["decision"] == "block"
        assert "MTHDS lint errors" in verdict["reason"]
        assert str(method) in verdict["reason"]
        assert "not_a_field" in verdict["reason"]

    def test_a_clean_method_passes_silently_and_is_formatted(self, plugin_root: Path, project: Path) -> None:
        method = project / "sub dir" / "valid.mthds"
        unformatted = VALID_METHOD.replace('domain = "demo"', 'domain   =   "demo"')
        method.write_text(unformatted, encoding="utf-8")
        result = _run(plugin_root, project, _write_payload(method, project))
        assert result.returncode == 0, result.stderr
        assert result.stdout == ""
        assert method.read_text(encoding="utf-8") != unformatted, "the format stage did not write the method back"

    @pytest.mark.parametrize("file_name", ["notes.md", "method.mthds.bak", "mthds.txt"])
    def test_any_other_file_ends_in_the_pre_filter_before_the_bundle_loads(self, plugin_root: Path, project: Path, file_name: str) -> None:
        _stub_bundle(plugin_root)
        result = _run(plugin_root, project, _write_payload(project / file_name, project))
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == "", "the wrapper loaded the bundle for a file that is not a method"

    def test_the_bundle_gets_the_payload_whole_and_its_exit_code_and_streams_pass_through(self, plugin_root: Path, project: Path) -> None:
        _stub_bundle(plugin_root)
        method = project / "sub dir" / "é method.mthds"
        method.write_text(VALID_METHOD, encoding="utf-8")
        payload = _write_payload(method, project)
        result = _run(plugin_root, project, payload, STUB_EXIT="2")
        assert result.returncode == 2
        assert result.stderr == "stub bundle stderr"
        assert json.loads(result.stdout)["received"] == payload

    @pytest.mark.parametrize(
        ("environment", "expected"),
        [
            ({"CLAUDE_PLUGIN_OPTION_API_KEY": "plx_from_the_option", "PIPELEX_API_KEY": "plx_from_the_shell"}, "plx_from_the_option"),
            ({"CLAUDE_PLUGIN_OPTION_API_KEY": "", "PIPELEX_API_KEY": "plx_from_the_shell"}, "plx_from_the_shell"),
            ({"PIPELEX_API_KEY": "plx_from_the_shell"}, "plx_from_the_shell"),
            ({"CLAUDE_PLUGIN_OPTION_API_KEY": ""}, None),
        ],
    )
    def test_a_filled_option_becomes_the_key_and_an_empty_one_changes_nothing(
        self, plugin_root: Path, project: Path, environment: dict[str, str], expected: str | None
    ) -> None:
        _stub_bundle(plugin_root)
        method = project / "valid.mthds"
        method.write_text(VALID_METHOD, encoding="utf-8")
        result = _run(plugin_root, project, _write_payload(method, project), **environment)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["apiKey"] == expected

    def test_a_missing_bundle_passes_with_a_note(self, plugin_root: Path, project: Path) -> None:
        (plugin_root / "hooks" / "check.mjs").unlink()
        method = project / "broken.mthds"
        method.write_text(BROKEN_METHOD, encoding="utf-8")
        result = _run(plugin_root, project, _write_payload(method, project))
        assert result.returncode == 0
        assert result.stdout == ""
        assert "check.mjs not found beside check-mthds.mjs" in result.stderr

    def test_the_wrapper_is_found_from_a_root_holding_a_space_without_a_shell(self, plugin_root: Path, tmp_path: Path) -> None:
        """Claude Code substitutes the root into `args` as one string and spawns no shell, so the path needs no quoting."""
        command = _command(plugin_root)
        assert " " in command[1]
        assert Path(command[1]).is_file()
        assert shutil.which(command[0]) is not None, "`node` is not on the PATH"
        assert tmp_path in Path(command[1]).parents
