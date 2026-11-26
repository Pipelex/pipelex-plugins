"""Run the commands the skills give, as shipped, through every shell this machine has (L-261126-4c4a95).

Each command is read from the rendered Claude target, so the test runs what a user's harness runs: `pipelex-integrate`'s
gate copy, `node "${CLAUDE_SKILL_DIR}/scripts/copy-gate.mjs" …`, with the skill's directory substituted as Claude Code
does, and `pipelex-inputs`' temporary directory, `node -p "…mkdtempSync…"`. On macOS and Linux the shells are bash, zsh
and sh, and PowerShell when it is installed; on Windows they are Windows PowerShell 5.1, PowerShell 7 when installed, and
cmd. The script's own verdicts are run through `node` with no shell at all.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]
INTEGRATE = REPO_ROOT / "pipelex" / "skills" / "pipelex-integrate"
COPY_GATE = INTEGRATE / "scripts" / "copy-gate.mjs"
USER_DATA = REPO_ROOT / "pipelex" / "skills" / "pipelex-inputs" / "references" / "user-data.md"
SYNTHETIC = REPO_ROOT / "pipelex" / "skills" / "pipelex-inputs" / "references" / "synthetic.md"
MARKER = "Copied verbatim into a project by /pipelex-integrate"
GATES = ("codegen-check.mjs", "codegen_check.py")


def _shells() -> list[tuple[str, list[str]]]:
    """Each shell on this machine with the arguments that make it run one command line."""
    candidates: list[tuple[str, list[str]]]
    if sys.platform == "win32":
        candidates = [
            ("powershell", ["powershell", "-NoProfile", "-NonInteractive", "-Command"]),
            ("pwsh", ["pwsh", "-NoProfile", "-NonInteractive", "-Command"]),
            ("cmd", ["cmd"]),
        ]
    else:
        candidates = [
            ("bash", ["bash", "-c"]),
            ("zsh", ["zsh", "-c"]),
            ("sh", ["sh", "-c"]),
            ("pwsh", ["pwsh", "-NoProfile", "-NonInteractive", "-Command"]),
        ]
    return [(name, argv) for name, argv in candidates if shutil.which(argv[0]) is not None]


SHELLS = _shells()


def _code_spans(text: str, prefix: str) -> list[str]:
    return [span for span in re.findall(r"`([^`\n]+)`", text) if span.startswith(prefix)]


def _run(shell: list[str], command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    if shell[0] == "cmd":
        # cmd reads its own command line, not the C runtime's quoting Python would give a list: `/s` strips the outer
        # quotes and runs the rest exactly as typed, as a user's prompt would.
        return subprocess.run(f'cmd /d /s /c "{command}"', cwd=cwd, capture_output=True, text=True, check=False, timeout=120)
    return subprocess.run([*shell, command], cwd=cwd, capture_output=True, text=True, check=False, timeout=120)


@pytest.mark.cross_os
class TestShellNeutralCommands:
    @pytest.fixture()
    def skill_dir(self, tmp_path: Path) -> Path:
        """The integrate skill as a harness installs it, under a path holding a space."""
        installed = tmp_path / "plugin cache" / "pipelex-integrate"
        shutil.copytree(INTEGRATE, installed)
        return installed

    @pytest.fixture()
    def project(self, tmp_path: Path) -> Path:
        project = tmp_path / "my project"
        project.mkdir()
        return project

    def _gate_command(self, gate: str, skill_dir: Path) -> str:
        """Step 10's line for `gate`, with `${CLAUDE_SKILL_DIR}` substituted as Claude Code substitutes it."""
        body = (INTEGRATE / "SKILL.md").read_text(encoding="utf-8")
        (command,) = [span for span in _code_spans(body, "node ") if span.endswith(f" {gate}")]
        assert command == f'node "${{CLAUDE_SKILL_DIR}}/scripts/copy-gate.mjs" {gate}'
        return command.replace("${CLAUDE_SKILL_DIR}", str(skill_dir))

    def test_every_target_gives_the_same_command(self) -> None:
        for target, skill_dir in (("pipelex-codex", "<skill-dir>"), ("pipelex-vibe", "<skill-dir>"), ("pipelex", "${CLAUDE_SKILL_DIR}")):
            body = (REPO_ROOT / target / "skills" / "pipelex-integrate" / "SKILL.md").read_text(encoding="utf-8")
            for gate in GATES:
                assert f'`node "{skill_dir}/scripts/copy-gate.mjs" {gate}`' in body, f"{target}: {gate}"
            assert "mkdir -p" not in body and "cp " not in body, target

    @pytest.mark.parametrize(("shell_name", "shell"), SHELLS, ids=[name for name, _ in SHELLS])
    @pytest.mark.parametrize("gate", GATES)
    def test_the_gate_copy_runs_in_every_shell(self, shell_name: str, shell: list[str], gate: str, skill_dir: Path, project: Path) -> None:
        completed = _run(shell, self._gate_command(gate, skill_dir), project)
        assert completed.returncode == 0, f"{shell_name}: {completed.stdout}{completed.stderr}"
        assert completed.stdout.strip().splitlines()[-1] == f"copied {gate} to scripts/{gate}"
        assert (project / "scripts" / gate).read_bytes() == (INTEGRATE / "references" / gate).read_bytes()

    @pytest.mark.parametrize(("shell_name", "shell"), SHELLS, ids=[name for name, _ in SHELLS])
    def test_the_temporary_directory_command_runs_in_every_shell(self, shell_name: str, shell: list[str], project: Path) -> None:
        user_data = USER_DATA.read_text(encoding="utf-8")
        synthetic = SYNTHETIC.read_text(encoding="utf-8")
        (command,) = set(_code_spans(user_data, "node -p ") + _code_spans(synthetic, "node -p "))
        completed = _run(shell, command, project)
        assert completed.returncode == 0, f"{shell_name}: {completed.stdout}{completed.stderr}"
        made = Path(completed.stdout.strip())
        try:
            assert made.is_absolute() and made.is_dir(), f"{shell_name}: {completed.stdout!r}"
            assert made.name.startswith("pipelex-")
            assert made.parent.resolve() == Path(tempfile.gettempdir()).resolve()
            assert list(made.iterdir()) == []
        finally:
            shutil.rmtree(made, ignore_errors=True)

    def _copy(self, node: str, project: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([node, str(COPY_GATE), *args], cwd=project, capture_output=True, text=True, check=False)

    def test_an_identical_copy_is_left_alone(self, node: str, project: Path) -> None:
        assert self._copy(node, project, "codegen_check.py").returncode == 0
        again = self._copy(node, project, "codegen_check.py")
        assert (again.returncode, again.stdout.strip()) == (0, "unchanged: scripts/codegen_check.py already matches the reference")

    def test_an_older_copy_of_the_skill_s_own_is_replaced(self, node: str, project: Path) -> None:
        (project / "scripts").mkdir()
        (project / "scripts" / "codegen-check.mjs").write_text(f"// {MARKER}. An older release.\n", encoding="utf-8")
        completed = self._copy(node, project, "codegen-check.mjs")
        assert (completed.returncode, completed.stdout.strip()) == (0, "copied codegen-check.mjs to scripts/codegen-check.mjs")
        assert (project / "scripts" / "codegen-check.mjs").read_bytes() == (INTEGRATE / "references" / "codegen-check.mjs").read_bytes()

    def test_the_project_s_own_file_is_refused_until_the_user_agrees(self, node: str, project: Path) -> None:
        """The Python starter ships a different `scripts/codegen_check.py`, which a plain `cp` replaced without a word."""
        theirs = project / "scripts" / "codegen_check.py"
        theirs.parent.mkdir()
        theirs.write_text("# the starter's own gate\n", encoding="utf-8")
        refused = self._copy(node, project, "codegen_check.py")
        assert refused.returncode == 1
        assert refused.stdout.strip().startswith("refused: scripts/codegen_check.py is the project's own")
        assert "run this command again with --replace" in refused.stdout
        assert theirs.read_text(encoding="utf-8") == "# the starter's own gate\n"
        agreed = self._copy(node, project, "codegen_check.py", "--replace")
        assert (agreed.returncode, agreed.stdout.strip()) == (0, "copied codegen_check.py to scripts/codegen_check.py")
        assert theirs.read_bytes() == (INTEGRATE / "references" / "codegen_check.py").read_bytes()

    @pytest.mark.parametrize("args", [(), ("orphans.md",), ("codegen_check.py", "codegen-check.mjs"), ("../references/codegen_check.py",)])
    def test_only_a_gate_is_copied(self, node: str, project: Path, args: tuple[str, ...]) -> None:
        completed = self._copy(node, project, *args)
        assert completed.returncode == 2
        assert completed.stdout.strip().startswith("failed: name one gate to copy")
        assert not (project / "scripts").exists()

    def test_a_file_system_error_is_a_verdict(self, node: str, project: Path) -> None:
        (project / "scripts").write_text("a file where the directory goes\n", encoding="utf-8")
        completed = self._copy(node, project, "codegen-check.mjs")
        assert completed.returncode == 2
        assert completed.stdout.strip().startswith("failed: scripts/codegen-check.mjs: ")

    def test_the_shells_ran(self) -> None:
        """A machine with none of the shells would pass the parametrized tests by running none of them."""
        names = {name for name, _ in SHELLS}
        assert ("powershell" in names) if os.name == "nt" else ("bash" in names or "sh" in names), names
