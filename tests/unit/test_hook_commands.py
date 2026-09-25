from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest

from scripts.gen_skill_docs import load_target_config, render_templates

REPO_ROOT = Path(__file__).parents[2]
TARGETS = ("prod", "codex", "mistral-vibe")
# The placeholders a harness replaces with the plugin root. Codex honours the Claude spelling too.
ROOT_PLACEHOLDERS = ("${CLAUDE_PLUGIN_ROOT}", "${PLUGIN_ROOT}")
SPACED_ROOT_NAME = "plug in"
STUB_MARKER = "hook started"
HOOK_TIMEOUT_SECONDS = 60
# What reaches the validate stage, and so the network: removed so that only the offline stages run.
CREDENTIAL_PREFIXES = ("PIPELEX_", "CLAUDE_PLUGIN_OPTION_")

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


def _render_hooks(target_name: str, plugin_root: Path) -> dict[Path, str]:
    """A target's hook files rendered from the real templates, written under `plugin_root` as the target ships them."""
    config = load_target_config(REPO_ROOT / "targets", target_name)
    rendered = render_templates(REPO_ROOT / "templates", plugin_root, config.template_vars, include_skills=[], target_name=config.name)
    hooks = {path: content for path, content in rendered.items() if path.parent == plugin_root / "hooks"}
    for path, content in hooks.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if path.suffix == ".sh":
            path.chmod(0o755)
    return hooks


def _shell_commands(hooks: dict[Path, str]) -> list[str]:
    """Every hook command a shell runs: Claude's and Codex's shell-form entries, and each Vibe entry."""
    commands: list[str] = []
    for path, content in hooks.items():
        if path.suffix == ".json":
            events: dict[str, list[dict[str, Any]]] = json.loads(content)["hooks"]
            for groups in events.values():
                for group in groups:
                    commands.extend(hook["command"] for hook in group["hooks"] if hook.get("type") == "command" and "args" not in hook)
        elif path.name == "vibe-hooks.toml":
            commands.extend(hook["command"] for hook in tomllib.loads(content)["hooks"])
    return commands


def _as_the_user_writes_it(command: str, plugin_root: Path) -> str:
    """Vibe expands nothing, so the install page has the user write the script's absolute path in place of `./`."""
    return command.replace("./hooks/", f"{plugin_root}/hooks/")


def _substituted(command: str, plugin_root: Path) -> str:
    """The command after a textual substitution of the root, which is what Codex does before its shell runs it."""
    for placeholder in ROOT_PLACEHOLDERS:
        command = command.replace(placeholder, str(plugin_root))
    return command


def _run_in_shell(command: str, *, plugin_root: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run `command` with `sh -c` from `cwd`, the plugin root exported the way Claude Code and Codex export it."""
    environment = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(plugin_root), "PLUGIN_ROOT": str(plugin_root)}
    return subprocess.run(
        ["sh", "-c", command], input="{}", capture_output=True, text=True, cwd=cwd, env=environment, timeout=HOOK_TIMEOUT_SECONDS, check=False
    )


def _stub_every_script(hooks: dict[Path, str]) -> None:
    """Replace each wrapper by a script that says it started, so a run proves the command reached it."""
    for path in hooks:
        if path.suffix == ".sh":
            path.write_text(f'#!/bin/sh\necho "{STUB_MARKER}"\n', encoding="utf-8")
            path.chmod(0o755)


class CodexHookRun:
    """The rendered Codex hook under a root holding a space, run as Codex runs it, with every `node` start recorded."""

    def __init__(self, *, tmp_path: Path, node: str) -> None:
        self.plugin_root = tmp_path / SPACED_ROOT_NAME
        hooks = _render_hooks("codex", self.plugin_root)
        config = json.loads(hooks[self.plugin_root / "hooks" / "codex-hooks.json"])
        group = config["hooks"]["PostToolUse"][0]
        self.matcher: str = group["matcher"]
        self.command = _substituted(group["hooks"][0]["command"], self.plugin_root)
        self.project = tmp_path / "project"
        (self.project / "sub").mkdir(parents=True)
        (self.project / "broken.mthds").write_text(BROKEN_METHOD, encoding="utf-8")
        (self.project / "valid.mthds").write_text(VALID_METHOD, encoding="utf-8")
        # A `node` ahead of the real one on the PATH, which leaves a mark and then runs the real one.
        self.node_starts = tmp_path / "node-starts"
        stub_bin = tmp_path / "bin"
        stub_bin.mkdir()
        stub = stub_bin / "node"
        stub.write_text(f'#!/bin/sh\necho started >> "{self.node_starts}"\nexec "{node}" "$@"\n', encoding="utf-8")
        stub.chmod(0o755)
        self.environment = {key: value for key, value in os.environ.items() if not key.startswith(CREDENTIAL_PREFIXES)}
        self.environment["PATH"] = f"{stub_bin}{os.pathsep}{self.environment.get('PATH', '')}"

    def payload(self, *, tool_name: str, command: str) -> str:
        """A PostToolUse payload with the fields Codex 0.153 sends, in its compact JSON, the session's directory as `cwd`."""
        return json.dumps(
            {
                "session_id": "session-1",
                "turn_id": "turn-1",
                "transcript_path": None,
                "cwd": str(self.project),
                "hook_event_name": "PostToolUse",
                "model": "gpt-5.5",
                "permission_mode": "default",
                "tool_name": tool_name,
                "tool_input": {"command": command},
                "tool_response": "Success. Updated the following files:\n",
                "tool_use_id": "call-1",
            },
            separators=(",", ":"),
        )

    def run(self, *, tool_name: str, command: str) -> tuple[str, bool]:
        """The hook's stdout and whether it started Node. Codex runs a hook from the session's directory."""
        if self.node_starts.exists():
            self.node_starts.unlink()
        result = subprocess.run(
            ["sh", "-c", self.command],
            input=self.payload(tool_name=tool_name, command=command),
            capture_output=True,
            text=True,
            cwd=self.project,
            env=self.environment,
            timeout=HOOK_TIMEOUT_SECONDS,
            check=False,
        )
        assert result.returncode == 0, f"the hook exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        return result.stdout, self.node_starts.exists()


def _patch(path: str) -> str:
    """A patch adding `path` with a valid method's text; the file already on disk is what the hook checks."""
    lines = "\n".join(f"+{line}" for line in VALID_METHOD.splitlines())
    return f"*** Begin Patch\n*** Add File: {path}\n{lines}\n*** End Patch"


def _shell_patch(path: str, *, prefix: str = "", suffix: str = "") -> str:
    """A patch run through the shell. `apply_patch <<'PATCH'` alone, or after `cd <dir> &&`, is one Codex intercepts."""
    return f"{prefix}apply_patch <<'PATCH'{suffix}\n{_patch(path)}\nPATCH"


@pytest.mark.skipif(shutil.which("sh") is None, reason="the harnesses run hook commands through sh")
class TestHookCommands:
    @pytest.fixture
    def codex(self, tmp_path: Path, node: str) -> CodexHookRun:
        return CodexHookRun(tmp_path=tmp_path, node=node)

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_hook_command_starts_its_script_from_a_root_with_a_space(self, target_name: str, tmp_path: Path) -> None:
        """Each harness runs a hook command through a shell, so an unquoted root holding a space splits and the hook never starts."""
        plugin_root = tmp_path / SPACED_ROOT_NAME
        project = tmp_path / "project"
        project.mkdir()
        hooks = _render_hooks(target_name, plugin_root)
        commands = _shell_commands(hooks)
        assert commands, f"{target_name}: no hook command was rendered, so this test would pass having run nothing"
        _stub_every_script(hooks)

        for command in commands:
            if target_name == "mistral-vibe":
                runs = {"the absolute path the user writes": _as_the_user_writes_it(command, plugin_root)}
            else:
                assert any(placeholder in command for placeholder in ROOT_PLACEHOLDERS), (
                    f"{target_name}: {command!r} names its script by no plugin-root placeholder"
                )
                runs = {"the shell expanding the root": command, "the root substituted into the text": _substituted(command, plugin_root)}
            for how, runnable in runs.items():
                result = _run_in_shell(runnable, plugin_root=plugin_root, cwd=project)
                assert result.returncode == 0 and result.stdout.strip() == STUB_MARKER, (
                    f"{target_name}: {command!r}, run through sh -c with {how}, did not start its script under a root holding a space "
                    f"(exit {result.returncode}, stderr {result.stderr.strip()!r}): wrap the root in double quotes"
                )

    def test_an_unquoted_root_fails_the_same_run(self, tmp_path: Path) -> None:
        """The run above tells a quoted command from an unquoted one: the form the hooks had exits 127."""
        plugin_root = tmp_path / SPACED_ROOT_NAME
        script = plugin_root / "hooks" / "check-mthds.sh"
        script.parent.mkdir(parents=True)
        script.write_text(f'#!/bin/sh\necho "{STUB_MARKER}"\n', encoding="utf-8")
        script.chmod(0o755)

        unquoted = _run_in_shell("${CLAUDE_PLUGIN_ROOT}/hooks/check-mthds.sh", plugin_root=plugin_root, cwd=tmp_path)
        quoted = _run_in_shell('"${CLAUDE_PLUGIN_ROOT}"/hooks/check-mthds.sh', plugin_root=plugin_root, cwd=tmp_path)

        assert unquoted.returncode == 127
        assert STUB_MARKER not in unquoted.stdout
        assert quoted.returncode == 0
        assert quoted.stdout.strip() == STUB_MARKER

    def test_the_codex_matcher_admits_the_patch_tool_and_the_shell(self, codex: CodexHookRun) -> None:
        """A patch run through the shell in a form Codex does not intercept reaches hooks as `Bash`."""
        assert re.search(codex.matcher, "apply_patch")
        assert re.search(codex.matcher, "Bash")
        for other in ("exec_command", "shell", "mcp__pipelex__mthds_validate", "spawn_agent"):
            assert not re.search(codex.matcher, other), f"the matcher admits {other}"

    def test_a_codex_patch_run_through_the_shell_is_checked_by_absolute_path(self, codex: CodexHookRun) -> None:
        """The bundle reads the patch headers from a `Bash` call's `tool_input.command` as it does from the patch tool's."""
        target = codex.project / "broken.mthds"
        stdout, started_node = codex.run(tool_name="Bash", command=_shell_patch(str(target), suffix=" && echo applied"))
        verdict = json.loads(stdout)
        assert verdict["decision"] == "block"
        assert "MTHDS lint errors" in verdict["reason"]
        assert str(target) in verdict["reason"]
        assert started_node

    def test_a_valid_method_patched_through_the_codex_shell_passes_silently(self, codex: CodexHookRun) -> None:
        target = codex.project / "valid.mthds"
        stdout, started_node = codex.run(tool_name="Bash", command=_shell_patch(str(target), suffix=" && echo applied"))
        assert stdout == ""
        assert started_node

    def test_the_codex_patch_tool_reads_a_relative_path_from_the_session_directory(self, codex: CodexHookRun) -> None:
        """The patch tool applies its patch in the session's directory, so a relative path is checked there, and formatted."""
        unformatted = codex.project / "valid.mthds"
        stdout, _ = codex.run(tool_name="apply_patch", command=_patch("broken.mthds"))
        verdict = json.loads(stdout)
        assert verdict["decision"] == "block"
        assert str(codex.project / "broken.mthds") in verdict["reason"]
        codex.run(tool_name="apply_patch", command=_patch("valid.mthds"))
        assert unformatted.read_text(encoding="utf-8") != VALID_METHOD, "the patch tool's relative path was not formatted in place"

    @pytest.mark.parametrize("command", ["ls -la", "cat broken.mthds", "grep -rl pipe --include='*.mthds' ."])
    def test_any_other_codex_shell_command_ends_in_the_pre_filter(self, codex: CodexHookRun, command: str) -> None:
        """A shell command that patches no .mthds file passes silently without starting Node, one naming a broken method included."""
        stdout, started_node = codex.run(tool_name="Bash", command=command)
        assert stdout == ""
        assert not started_node, f"{command!r} started Node: the wrapper's pre-filter let a command with no patch header through"

    @pytest.mark.parametrize(("prefix", "directory"), [("", "."), ("cd sub; ", "sub")])
    def test_a_relative_path_in_a_codex_shell_patch_is_read_where_the_script_moved(self, codex: CodexHookRun, prefix: str, directory: str) -> None:
        """The bundle follows the script's `cd` from the payload's `cwd`, so `cd sub; apply_patch …` is checked in `sub/`.

        Both directories hold a broken `broken.mthds` carrying the patch's added lines, so only the one the patch wrote is named.
        """
        (codex.project / "sub" / "broken.mthds").write_text(BROKEN_METHOD, encoding="utf-8")
        target = codex.project / directory / "broken.mthds"
        other = codex.project / ("sub" if directory == "." else ".") / "broken.mthds"
        stdout, _ = codex.run(tool_name="Bash", command=_shell_patch("broken.mthds", prefix=prefix, suffix=" && echo applied"))
        verdict = json.loads(stdout)
        assert verdict["decision"] == "block"
        assert str(target) in verdict["reason"]
        assert str(other) not in verdict["reason"], f"a shell patch run from {directory!r} was checked in the other directory"

    def test_a_shell_patch_after_cd_leaves_the_session_directorys_file_untouched(self, codex: CodexHookRun) -> None:
        """`cd sub; apply_patch …` wrote `sub/broken.mthds`, so the valid but unformatted `broken.mthds` beside the session is not formatted."""
        untouched = codex.project / "broken.mthds"
        untouched.write_text(VALID_METHOD, encoding="utf-8")
        edited = codex.project / "sub" / "broken.mthds"
        edited.write_text(BROKEN_METHOD, encoding="utf-8")
        stdout, _ = codex.run(tool_name="Bash", command=_shell_patch("broken.mthds", prefix="cd sub; "))
        verdict = json.loads(stdout)
        assert verdict["decision"] == "block"
        assert str(edited) in verdict["reason"]
        assert untouched.read_bytes() == VALID_METHOD.encode("utf-8"), "the session's same-named file was rewritten"

    def test_a_shell_patch_the_hook_cannot_place_gets_a_note_and_no_block(self, codex: CodexHookRun) -> None:
        """A script with no `cd` may have run in the `workdir` given to `exec_command`, which the payload does not carry.

        Here the patch wrote `sub/broken.mthds`, and the same-named file in the session's directory, broken too, does not hold the
        lines the patch added: the hook checks neither, and names the path in a non-blocking note rather than passing in silence.
        """
        elsewhere = BROKEN_METHOD.replace('description = "Demo"\n', 'description = "Another method"\n')
        assert elsewhere != BROKEN_METHOD
        (codex.project / "broken.mthds").write_text(elsewhere, encoding="utf-8")
        (codex.project / "sub" / "broken.mthds").write_text(BROKEN_METHOD, encoding="utf-8")
        stdout, _ = codex.run(tool_name="Bash", command=_shell_patch("broken.mthds", suffix=" && echo applied"))
        output = json.loads(stdout)
        assert "decision" not in output, "the hook blocked on a file the patch did not write"
        assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert "`broken.mthds`" in output["hookSpecificOutput"]["additionalContext"]
        assert (codex.project / "broken.mthds").read_text(encoding="utf-8") == elsewhere

    def test_an_absolute_path_in_a_codex_patch_is_checked_wherever_the_patch_ran(self, codex: CodexHookRun) -> None:
        target = codex.project / "sub" / "broken.mthds"
        target.write_text(BROKEN_METHOD, encoding="utf-8")
        stdout, _ = codex.run(tool_name="Bash", command=_shell_patch(str(target), prefix="cd sub; "))
        verdict = json.loads(stdout)
        assert verdict["decision"] == "block"
        assert str(target) in verdict["reason"]
