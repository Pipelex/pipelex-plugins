"""`check_skill_posix_shell`: the skill text every target ships gives no command only a POSIX shell runs.

A skill's commands run in whatever shell the harness uses, which on Windows may be PowerShell 7 or Windows
PowerShell 5.1, with no `&&` and no `||` (L-261126-4c4a95). The rule reads code alone, inline spans and shell
or unnamed fences, so prose and code written for another reader stay free.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check import POSIX_SHELL_ALLOWED, POSIX_SHELL_PENDING_SKILLS, check_skill_posix_shell

REPO_ROOT = Path(__file__).parents[2]
FRONTMATTER = "---\nname: pipelex-test\ndescription: Test skill\n---\n\n# Test Skill\n"

pytestmark = pytest.mark.cross_os


@pytest.fixture()
def tree(tmp_path: Path) -> Path:
    """One Claude target, `pipelex/`, holding one skill whose SKILL.md the tests write."""
    targets = tmp_path / "targets"
    targets.mkdir()
    (targets / "defaults.toml").write_text('[vars]\nmarketplace_name = "pipelex-plugins"\n', encoding="utf-8")
    (targets / "prod.toml").write_text('[plugin]\nname = "pipelex"\nversion = "0.1.0"\nsource = "pipelex/"\n', encoding="utf-8")
    skill = tmp_path / "pipelex" / "skills" / "pipelex-test"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(FRONTMATTER, encoding="utf-8")
    return tmp_path


def _write(tree: Path, body: str, relative: str = "pipelex-test/SKILL.md") -> None:
    path = tree / "pipelex" / "skills" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(FRONTMATTER + body, encoding="utf-8")


class TestCheckSkillPosixShell:
    @pytest.mark.parametrize(
        ("code", "construct"),
        [
            ("command -v uv >/dev/null", "command -v"),
            ('mkdir -p scripts && cp "${CLAUDE_SKILL_DIR}/references/gate.mjs" scripts/gate.mjs', "mkdir -p"),
            ('mkdir -p scripts && cp "${CLAUDE_SKILL_DIR}/references/gate.mjs" scripts/gate.mjs', "&&"),
            ('cp "${CLAUDE_SKILL_DIR}/references/gate.mjs" scripts/gate.mjs', "cp from the skill's directory"),
            ('cp "<skill-dir>/references/gate.mjs" scripts/gate.mjs', "cp from the skill's directory"),
            ('soffice --convert-to pdf --outdir "$(mktemp -d)" <file>', "mktemp"),
            ('cat "${VIBE_HOME:-$HOME/.vibe}/config.toml"', "${VAR:-…}"),
            ("/tmp/tmp.Xq3v9K/chart.png", "/tmp"),
            ("git rev-parse --show-cdup 2>/dev/null", "/dev/null"),
            ("uv --version || echo missing", "||"),
            ("python << 'PYEOF'", "heredoc"),
            ("grep -rl '\"pipelex-integrate\"' --include=sources.json .", "grep"),
            ("env | grep PIPELEX", "grep"),
            ("export PIPELEX_API_KEY=x", "export VAR="),
        ],
    )
    def test_an_inline_command_is_refused(self, tree: Path, code: str, construct: str) -> None:
        _write(tree, f"\nRun `{code}` from the project root.\n")
        errors = check_skill_posix_shell(tree, allowed={}, pending={})
        assert any(error.startswith("pipelex/skills/pipelex-test/SKILL.md:8: ") and f"`{construct}` in " in error for error in errors), errors

    @pytest.mark.parametrize("language", ["", "bash", "sh", "shell", "powershell"])
    def test_a_shell_fence_is_read_line_by_line(self, tree: Path, language: str) -> None:
        _write(tree, f"\n```{language}\nuv --version\nmkdir -p out\n```\n")
        errors = check_skill_posix_shell(tree, allowed={}, pending={})
        assert errors == ["pipelex/skills/pipelex-test/SKILL.md:10: `mkdir -p` in `mkdir -p out`: " + errors[0].split(": ", 2)[2]]

    def test_references_and_shared_files_are_held_too(self, tree: Path) -> None:
        _write(tree, "\nRun `mktemp -d`.\n", relative="pipelex-test/references/branch.md")
        _write(tree, "\nRun `mktemp -d`.\n", relative="shared/credentials.md")
        errors = check_skill_posix_shell(tree, allowed={}, pending={})
        assert [error.split(":", 1)[0] for error in errors] == [
            "pipelex/skills/pipelex-test/references/branch.md",
            "pipelex/skills/shared/credentials.md",
        ]

    def test_prose_is_not_code(self, tree: Path) -> None:
        _write(tree, "\nThe user keeps files under /tmp && elsewhere, and grep is a word here.\n")
        assert check_skill_posix_shell(tree, allowed={}, pending={}) == []

    @pytest.mark.parametrize("language", ["json", "ts", "python", "toml", "make"])
    def test_a_fence_in_another_language_is_code_for_another_reader(self, tree: Path, language: str) -> None:
        """An npm script's `&&` runs in cmd.exe on Windows, and a TypeScript `&&` is no shell at all."""
        _write(tree, f'\n```{language}\n"check": "npm run lint && npm run typecheck"\nif (a && b) {{}}\n```\n')
        assert check_skill_posix_shell(tree, allowed={}, pending={}) == []

    def test_the_claude_code_substitutions_are_not_expansions(self, tree: Path) -> None:
        """Claude Code substitutes these before any shell runs the command."""
        _write(tree, '\nRun `node "${CLAUDE_SKILL_DIR}/scripts/copy-gate.mjs" codegen-check.mjs` or `node "${CLAUDE_PLUGIN_ROOT}/x.mjs"`.\n')
        assert check_skill_posix_shell(tree, allowed={}, pending={}) == []

    def test_a_fence_closes(self, tree: Path) -> None:
        _write(tree, "\n```json\n{}\n```\n\nThen `uv --version`, and after it the prose says && freely.\n")
        assert check_skill_posix_shell(tree, allowed={}, pending={}) == []

    def test_an_allowlisted_example_passes(self, tree: Path) -> None:
        _write(tree, "\nWindows PowerShell 5.1 has no `&&`.\n")
        allowed = {("pipelex-test/SKILL.md", "&&"): "names the operator PowerShell 5.1 lacks"}
        assert check_skill_posix_shell(tree, allowed=allowed, pending={}) == []

    def test_the_same_code_elsewhere_is_still_refused(self, tree: Path) -> None:
        _write(tree, "\nWindows PowerShell 5.1 has no `&&`.\n", relative="pipelex-test/references/other.md")
        allowed = {("pipelex-test/SKILL.md", "&&"): "names the operator PowerShell 5.1 lacks"}
        errors = check_skill_posix_shell(tree, allowed=allowed, pending={})
        assert errors[0].startswith("pipelex/skills/pipelex-test/references/other.md:8: `&&`")
        assert errors[1] == "allowlisted `&&` in pipelex-test/SKILL.md no longer appears in any target"

    def test_a_stale_entry_is_reported(self, tree: Path) -> None:
        allowed = {("pipelex-test/SKILL.md", "mktemp -d"): "an example removed since"}
        assert check_skill_posix_shell(tree, allowed=allowed, pending={}) == [
            "allowlisted `mktemp -d` in pipelex-test/SKILL.md no longer appears in any target"
        ]

    def test_a_pending_skill_is_skipped(self, tree: Path) -> None:
        _write(tree, "\nRun `mktemp -d`.\n")
        assert check_skill_posix_shell(tree, allowed={}, pending={"pipelex-test": "L-000000-000000"}) == []

    def test_every_target_passes(self) -> None:
        assert check_skill_posix_shell(REPO_ROOT) == []

    def test_every_pending_skill_exists(self) -> None:
        """A pending entry for a skill that no longer exists would hide nothing, and only mislead."""
        for skill in POSIX_SHELL_PENDING_SKILLS:
            assert (REPO_ROOT / "templates" / "skills" / skill).is_dir(), skill

    def test_every_allowlist_entry_says_why(self) -> None:
        for key, reason in POSIX_SHELL_ALLOWED.items():
            assert reason.strip(), key
