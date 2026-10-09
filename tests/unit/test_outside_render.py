"""Tests for scripts/outside_render.py: rendering the plugin's skills for a target kept in another repository.

The fixture under `tests/data/outside-target/` exercises every kind of change an outside target may
make: an overlay on an upstream skill linking a reference it adds, an outside skill including an
upstream partial, a replaced shared partial, and a skill forked in place with one static reference
dropped and one pinned, on the `agent-skills` platform in the `in-each-skill` layout. Its hashes are
placeholders: each test copies the fixture under `tmp_path` and writes the SHA-256 of the upstream
file as it is today, so an upstream edit to a file the fixture names never breaks the suite.
"""

from __future__ import annotations

import re
import shutil
import stat
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from scripts.check import check_target_platforms
from scripts.gen_skill_docs import load_target_config
from scripts.outside_render import (
    OWNER_MARKER_NAME,
    OutsideTarget,
    build,
    check,
    declaration_errors,
    file_sha256,
    link_errors,
    load_outside_target,
    main,
    render_outside,
)

REPO_ROOT = Path(__file__).parents[2]
FIXTURE = REPO_ROOT / "tests" / "data" / "outside-target"
TARGET_FILE = "outside-fixture.toml"
PLACEHOLDER = "sha256:computed-by-the-test"
WRONG_HASH = "sha256:" + "0" * 64
# The directories of this repository an outside render could write into if it went wrong.
UPSTREAM_WATCHED = ("templates", "skills", "targets", "pipelex", "pipelex-codex", "pipelex-vibe", ".agents")

Mutation = Callable[[Path], Path]


def _set_hashes(target_file: Path) -> None:
    """Replace every placeholder hash with the SHA-256 of the upstream file the line names."""
    lines: list[str] = []
    for line in target_file.read_text().splitlines():
        match = re.match(r'^"(?P<path>[^"]+)" = "' + re.escape(PLACEHOLDER) + '"$', line)
        lines.append(f'"{match["path"]}" = "{file_sha256(REPO_ROOT / match["path"])}"' if match else line)
    target_file.write_text("\n".join(lines) + "\n")


def _fixture(tmp_path: Path) -> Path:
    """A copy of the fixture with its hashes computed, at `tmp_path/src/`; it renders into `tmp_path/rendered/`."""
    source = tmp_path / "src"
    shutil.copytree(FIXTURE, source)
    target_file = source / TARGET_FILE
    _set_hashes(target_file)
    return target_file


def _edit(target_file: Path, old: str, new: str) -> Path:
    text = target_file.read_text()
    assert old in text, f"the fixture no longer holds {old!r}"
    target_file.write_text(text.replace(old, new, 1))
    return target_file


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _frontmatter_keys(skill_md: Path) -> set[str]:
    text = skill_md.read_text()
    end = text.index("\n---\n", 4)
    loaded: dict[str, object] = yaml.safe_load(text[4:end])
    return set(loaded)


def _shared_links(text: str, prefix: str) -> set[str]:
    """The shared files a Markdown text links to, read with a pattern of the test's own rather than the render's."""
    return set(re.findall(r"\]\(" + re.escape(prefix) + r"([a-z-]+\.md)(?:#[^)]*)?\)", text))


def _snapshot(*roots: Path) -> dict[Path, tuple[int, int]]:
    """Every file under `roots`, with its size and modification time."""
    files: dict[Path, tuple[int, int]] = {}
    for root in roots:
        if root.is_dir():
            for path in root.rglob("*"):
                if path.is_file():
                    info = path.stat()
                    files[path] = (info.st_size, info.st_mtime_ns)
    return files


def _every_skill(tmp_path: Path, layout: str) -> Path:
    """A target with no file of its own beside it, so it renders every upstream skill as the upstream ships it."""
    return _write(
        tmp_path / "src" / "every-skill.toml",
        f'[render]\noutput = "../rendered"\nshared = "{layout}"\n\n'
        '[vars]\nplatform = "agent-skills"\nharness_name = "the harness"\nskill_dir = "<skill-dir>"\n',
    )


def _git_checkout(output: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(output)], check=True)
    _write(output / "README.md", "# Somebody's repository\n")


def _another_target_s_output(output: Path) -> None:
    _write(output / OWNER_MARKER_NAME, 'target = "another-target"\n')


def _without_output(target_file: Path) -> Path:
    return _edit(target_file, 'output = "../rendered"\n', "")


def _output_inside(target_file: Path) -> Path:
    return _edit(target_file, 'output = "../rendered"', 'output = "rendered"')


def _output_holding(target_file: Path) -> Path:
    return _edit(target_file, 'output = "../rendered"', 'output = ".."')


def _output_upstream(target_file: Path) -> Path:
    return _edit(target_file, 'output = "../rendered"', f'output = "{REPO_ROOT / "pipelex-outside"}"')


def _unknown_layout(target_file: Path) -> Path:
    return _edit(target_file, 'shared = "in-each-skill"', 'shared = "flat"')


def _unknown_skill(target_file: Path) -> Path:
    return _edit(target_file, '"house-notes"]', '"house-notes", "pipelex-nope"]')


def _in_repo_name(target_file: Path) -> Path:
    return target_file.rename(target_file.with_name("prod.toml"))


def _misspelled_table(target_file: Path) -> Path:
    return _edit(target_file, "[render.pins]", "[render.pin]")


def _claude_platform(target_file: Path) -> Path:
    return _edit(target_file, 'platform = "agent-skills"', 'platform = "claude"')


def _defaulted_harness(target_file: Path) -> Path:
    return _edit(target_file, 'harness_name = "the fixture harness"\n', "")


def _derived_variable(target_file: Path) -> Path:
    return _edit(target_file, 'skill_dir = "<skill-dir>"', 'skill_dir = "<skill-dir>"\nshared_dir = "elsewhere"')


def _malformed_hash(target_file: Path) -> Path:
    path = "skills/pipelex-synthetic-inputs/references/pdf.md"
    return _edit(target_file, f'"{path}" = "{file_sha256(REPO_ROOT / path)}"', f'"{path}" = "{file_sha256(REPO_ROOT / path)[:20]}"')


def _two_tables(target_file: Path) -> Path:
    path = "skills/pipelex-synthetic-inputs/references/venv.md"
    return _edit(target_file, "[render.pins]\n", f'[render.pins]\n"{path}" = "{file_sha256(REPO_ROOT / path)}"\n')


def _undeclarable_path(target_file: Path) -> Path:
    return _edit(target_file, "[render.pins]\n", f'[render.pins]\n"targets/defaults.toml" = "{WRONG_HASH}"\n')


def _undeclared_replacement(target_file: Path) -> Path:
    _write(target_file.parent / "templates/skills/shared/stale-types-notice.md.j2", "Nothing is stale here.\n")
    return target_file


def _replacement_without_file(target_file: Path) -> Path:
    (target_file.parent / "templates/skills/shared/saved-copy-notice.md.j2").unlink()
    return target_file


def _declaration_naming_nothing(target_file: Path) -> Path:
    return _edit(target_file, "[render.pins]\n", f'[render.pins]\n"skills/pipelex-edit/references/gone.md" = "{WRONG_HASH}"\n')


def _dropped_template(target_file: Path) -> Path:
    path = "templates/skills/shared/graph-page.md.j2"
    return _edit(target_file, "[render.drops]\n", f'[render.drops]\n"{path}" = "{file_sha256(REPO_ROOT / path)}"\n')


def _dropped_yet_provided(target_file: Path) -> Path:
    _write(target_file.parent / "skills/pipelex-synthetic-inputs/references/venv.md", "# A venv\n")
    return target_file


def _pinned_yet_provided(target_file: Path) -> Path:
    _write(target_file.parent / "skills/pipelex-synthetic-inputs/references/pdf.md", "# A PDF\n")
    return target_file


def _misplaced_template(target_file: Path) -> Path:
    _write(target_file.parent / "templates/README.md", "# Templates\n")
    return target_file


def _misplaced_asset(target_file: Path) -> Path:
    _write(target_file.parent / "skills/house-notes/notes.txt", "Notes.\n")
    return target_file


class TestOutsideRender:
    def test_the_fixture_renders_what_it_declares_and_checks_fresh(self, tmp_path: Path) -> None:
        target = load_outside_target(_fixture(tmp_path))
        assert build(target) == 0
        output = tmp_path / "rendered"

        # The overlay is appended to the upstream skill, and the reference it adds is copied beside it.
        edit = (output / "pipelex-edit" / "SKILL.md").read_text()
        assert edit.endswith("\n## On the fixture harness\n\nRead [the house rules](references/house-rules.md) before the first edit.\n")
        assert (output / "pipelex-edit/references/house-rules.md").read_bytes() == (
            FIXTURE / "skills/pipelex-edit/references/house-rules.md"
        ).read_bytes()
        # The replaced partial is what the upstream skill includes.
        assert "**The fixture's closing step.**" in edit
        assert "**Save the linked method's draft.**" not in edit
        # The outside skill includes an upstream partial by name, and its script keeps its executable bit.
        notes = (output / "house-notes" / "SKILL.md").read_text()
        assert "Before writing a `PipeFunc`, know this: **`PipeFunc` is experimental on the hosted plane.**" in notes
        assert (output / "house-notes/scripts/tidy.sh").stat().st_mode & stat.S_IXUSR
        # The forked skill is the fork, with its dropped reference gone and its pinned one as upstream ships it.
        forked = output / "pipelex-synthetic-inputs"
        assert "# Synthetic inputs, forked" in (forked / "SKILL.md").read_text()
        assert not (forked / "references" / "venv.md").exists()
        assert (forked / "references/pdf.md").read_bytes() == (REPO_ROOT / "skills/pipelex-synthetic-inputs/references/pdf.md").read_bytes()
        # Each skill carries exactly the shared files it links to, followed through their own links.
        for skill_dir in sorted(path for path in output.iterdir() if path.is_dir()):
            linked = set[str]()
            for markdown in [skill_dir / "SKILL.md", *sorted(skill_dir.glob("references/**/*.md"))]:
                linked |= _shared_links(markdown.read_text(), "shared/" if markdown.name == "SKILL.md" else "../shared/")
            pending = list(linked)
            while pending:
                for name in _shared_links((skill_dir / "shared" / pending.pop()).read_text(), "") - linked:
                    linked.add(name)
                    pending.append(name)
            copied = {path.name for path in skill_dir.glob("shared/*")}
            assert copied == linked, skill_dir.name
        assert {path.name for path in (output / "house-notes/shared").iterdir()} == {"writing-mthds.md", "native-content-types.md"}
        # The agent-skills frontmatter is the name and the description, and nothing a plugin carries is written.
        for skill_md in output.glob("*/SKILL.md"):
            assert _frontmatter_keys(skill_md) == {"name", "description"}, skill_md
        assert not [path for path in output.rglob("*") if path.name in {"hooks", "mcp", ".claude-plugin", ".codex-plugin"}]
        # The marker at the top names the target whose output this is, and lists every other file the render wrote.
        written = sorted(path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file() and path.name != OWNER_MARKER_NAME)
        assert tomllib.loads((output / OWNER_MARKER_NAME).read_text()) == {"target": "outside-fixture", "files": written}
        assert check(target) == 0

    @pytest.mark.parametrize(
        ("mutation", "refusal"),
        [
            (_without_output, "[render] output is required"),
            (_output_inside, "holds or sits inside the source root"),
            (_output_holding, "holds or sits inside the source root"),
            (_output_upstream, "overlaps pipelex-plugins itself"),
            (_unknown_layout, "[render] shared 'flat' is not a layout"),
            (_unknown_skill, "[skills] include names 'pipelex-nope', a skill that exists neither upstream nor"),
            (_in_repo_name, "its name 'prod' is an in-repo target's"),
            (_misspelled_table, "unknown [render] key(s) pin"),
            (_claude_platform, "[vars] platform is 'claude': an outside target renders for 'agent-skills'"),
            (_defaulted_harness, "[vars] must set harness_name"),
            (_derived_variable, "[vars] shared_dir is set by the render itself"),
            (_malformed_hash, "is not a hash"),
            (_two_tables, "is declared in both [render.drops] and [render.pins]"),
            (_undeclarable_path, "'targets/defaults.toml' names no skill template or static asset"),
        ],
    )
    def test_a_target_file_the_render_cannot_honour_is_refused(self, tmp_path: Path, mutation: Mutation, refusal: str) -> None:
        target_file = mutation(_fixture(tmp_path))
        with pytest.raises(SystemExit, match=re.escape(refusal)):
            load_outside_target(target_file)

    @pytest.mark.parametrize(
        ("mutation", "refusal"),
        [
            (
                _undeclared_replacement,
                "templates/skills/shared/stale-types-notice.md.j2: replaces the upstream file at the same path without saying so",
            ),
            (
                _replacement_without_file,
                "[render.replaces] templates/skills/shared/saved-copy-notice.md.j2: no file at that path under the source root",
            ),
            (_declaration_naming_nothing, "[render.pins] skills/pipelex-edit/references/gone.md: names no upstream file"),
            (_dropped_template, "[render.drops] templates/skills/shared/graph-page.md.j2: only a static asset is dropped"),
            (_dropped_yet_provided, "[render.drops] skills/pipelex-synthetic-inputs/references/venv.md: dropped, yet the source root holds a file"),
            (_pinned_yet_provided, "[render.pins] skills/pipelex-synthetic-inputs/references/pdf.md: pinned as used as it is, yet"),
            (_misplaced_template, "templates/README.md: the render reads only templates under templates/skills/ ending .j2"),
            (_misplaced_asset, "skills/house-notes/notes.txt: the render copies only a skill's references/ and scripts/"),
        ],
    )
    def test_a_change_upstream_the_target_does_not_declare_is_refused(self, tmp_path: Path, mutation: Mutation, refusal: str) -> None:
        target = load_outside_target(mutation(_fixture(tmp_path)))
        errors = declaration_errors(target)
        assert [error for error in errors if refusal in error], errors
        assert build(target) == 1
        assert not (tmp_path / "rendered").exists()

    @pytest.mark.parametrize(
        ("table", "path"),
        [
            ("replaces", "templates/skills/shared/saved-copy-notice.md.j2"),
            ("drops", "skills/pipelex-synthetic-inputs/references/venv.md"),
            ("pins", "skills/pipelex-synthetic-inputs/references/pdf.md"),
        ],
    )
    def test_a_stale_hash_names_both_hashes_and_the_diff_to_read(self, tmp_path: Path, table: str, path: str) -> None:
        actual = file_sha256(REPO_ROOT / path)
        target_file = _edit(_fixture(tmp_path), f'"{path}" = "{actual}"', f'"{path}" = "{WRONG_HASH}"')
        errors = declaration_errors(load_outside_target(target_file))
        assert errors == [
            f"[render.{table}] {path}: the upstream file changed: declared {WRONG_HASH}, now {actual}. Read the change "
            f"(`git diff <old-tag>..<new-tag> -- {path}` in pipelex-plugins), carry it over or decide against it, then update the hash"
        ]

    def test_a_link_that_leaves_its_skill_fails_and_nothing_is_written(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """In the in-each-skill layout each skill is uploaded alone, so a link to a sibling skill names a file its copy lacks."""
        target_file = _fixture(tmp_path)
        _edit(
            target_file.parent / "templates/skills/pipelex-edit/SKILL.outside-fixture.md.j2",
            "before the first edit.",
            "before [the fork](../pipelex-synthetic-inputs/SKILL.md).",
        )
        assert build(load_outside_target(target_file)) == 1
        assert "rendered/pipelex-edit/SKILL.md: link to `../pipelex-synthetic-inputs/SKILL.md` leaves its skill" in capsys.readouterr().out
        assert not (tmp_path / "rendered").exists()

    def test_check_reports_every_drift_and_a_build_repairs_all_but_a_template(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        target = load_outside_target(_fixture(tmp_path))
        build(target)
        output = tmp_path / "rendered"
        (output / "pipelex-edit/SKILL.md").write_text("stale\n")
        (output / "house-notes/shared/native-content-types.md").unlink()
        (output / "house-notes/scripts/tidy.sh").chmod(0o644)
        _write(output / "stray.md", "# Stray\n")
        _write(output / "house-notes/SKILL.md.j2", "{{ leaked }}\n")
        capsys.readouterr()
        assert check(target) == 1
        report = capsys.readouterr().out
        for finding in (
            "STALE: rendered/pipelex-edit/SKILL.md",
            "MISSING: rendered/house-notes/shared/native-content-types.md",
            "MODE: rendered/house-notes/scripts/tidy.sh",
            "ORPHAN: rendered/stray.md",
            "LEAKED TEMPLATE: rendered/house-notes/SKILL.md.j2",
        ):
            assert finding in report, report
        assert build(target) == 0
        capsys.readouterr()
        assert check(target) == 1
        assert capsys.readouterr().out.splitlines()[0].startswith("  LEAKED TEMPLATE: rendered/house-notes/SKILL.md.j2")

    def test_the_render_writes_nothing_outside_its_output(self, tmp_path: Path) -> None:
        target_file = _fixture(tmp_path)
        watched = [target_file.parent, *(REPO_ROOT / name for name in UPSTREAM_WATCHED)]
        before = _snapshot(*watched)
        assert main([str(target_file)]) == 0
        assert main([str(target_file), "--check"]) == 0
        assert _snapshot(*watched) == before
        assert {path.relative_to(tmp_path).parts[0] for path in tmp_path.rglob("*") if path.is_file()} == {"src", "rendered"}

    def test_the_beside_layout_writes_the_linked_shared_files_once(self, tmp_path: Path) -> None:
        target = load_outside_target(_edit(_fixture(tmp_path), 'shared = "in-each-skill"', 'shared = "beside"'))
        files = render_outside(target)
        assert not [rel for rel in files if rel.count("/") > 1 and rel.split("/")[1] == "shared"]
        assert {rel for rel in files if rel.startswith("shared/")} >= {"shared/writing-mthds.md", "shared/native-content-types.md"}
        assert "](../shared/writing-mthds.md)" in files["house-notes/SKILL.md"].content.decode()
        assert build(target) == 0
        assert check(target) == 0

    def test_an_in_repo_target_on_agent_skills_is_refused(self, tmp_path: Path) -> None:
        targets = tmp_path / "targets"
        _write(targets / "defaults.toml", '[vars]\nplatform = "claude"\n')
        _write(targets / "skills-only.toml", '[plugin]\nname = "pipelex"\nversion = "1.0.0"\nsource = "out/"\n\n[vars]\nplatform = "agent-skills"\n')
        with pytest.raises(SystemExit, match=re.escape("skills-only.toml: platform 'agent-skills' is for outside targets only")):
            load_target_config(targets, "skills-only")
        assert check_target_platforms(tmp_path) == [
            "targets/skills-only.toml: platform 'agent-skills' is for outside targets only, rendered by scripts/outside_render.py; "
            "an in-repo target renders for claude, codex or mistral-vibe"
        ]

    def test_the_target_s_name_and_layout_reach_the_templates(self, tmp_path: Path) -> None:
        target: OutsideTarget = load_outside_target(_fixture(tmp_path))
        assert target.name == "outside-fixture"
        assert target.template_vars["plugin_name"] == "outside-fixture"
        assert target.template_vars["shared_dir"] == "shared"
        assert target.output_dir == (tmp_path / "rendered").resolve()

    @pytest.mark.parametrize("layout", ["in-each-skill", "beside"])
    def test_every_upstream_skill_renders_with_every_link_whole(self, tmp_path: Path, layout: str) -> None:
        """A template link written `../shared/…` rather than through `shared_dir`, or a static reference linking a shared
        file, works for every in-repo target and breaks only in a consumer's `in-each-skill` render, in another repository's CI."""
        target = load_outside_target(_every_skill(tmp_path, layout))
        assert declaration_errors(target) == []
        files = render_outside(target)
        upstream_skills = {path.parent.name for path in (REPO_ROOT / "templates/skills").glob("*/SKILL.md.j2")}
        assert {rel.split("/")[0] for rel in files if rel.endswith("/SKILL.md")} == upstream_skills
        assert link_errors(target, files) == []

    def test_a_symbolic_link_in_the_output_is_refused_and_nothing_is_written_through_it(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        target = load_outside_target(_fixture(tmp_path))
        assert build(target) == 0
        output = tmp_path / "rendered"
        elsewhere = _write(tmp_path / "elsewhere" / "SKILL.md", "Somebody else's skill.\n").parent
        shutil.rmtree(output / "pipelex-edit")
        (output / "pipelex-edit").symlink_to(elsewhere, target_is_directory=True)
        capsys.readouterr()
        assert build(target) == 1
        assert "rendered/pipelex-edit: a symbolic link, which the render would write through" in capsys.readouterr().out
        assert check(target) == 1
        assert [path.name for path in elsewhere.iterdir()] == ["SKILL.md"]
        assert (elsewhere / "SKILL.md").read_text() == "Somebody else's skill.\n"

    @pytest.mark.parametrize(
        ("prepare", "refusal"),
        [
            (_git_checkout, "rendered/.git: a git repository inside the output, which the render owns whole"),
            (_another_target_s_output, f"rendered: its {OWNER_MARKER_NAME} names the outside target 'another-target', not 'outside-fixture'"),
        ],
    )
    def test_an_output_directory_holding_what_another_wrote_is_refused_untouched(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], prepare: Callable[[Path], None], refusal: str
    ) -> None:
        target = load_outside_target(_fixture(tmp_path))
        output = tmp_path / "rendered"
        prepare(output)
        before = _snapshot(output)
        assert build(target) == 1
        assert refusal in capsys.readouterr().out
        assert check(target) == 1
        assert _snapshot(output) == before

    @pytest.mark.parametrize("where", ["", "pipelex-edit"], ids=["top", "in-a-skill"])
    def test_a_repository_made_in_a_rendered_output_is_refused_untouched(
        self, tmp_path: Path, where: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The marker says the output is the render's, but a repository made in it afterwards is not: the pruning would
        delete its history as files the render does not produce."""
        target = load_outside_target(_fixture(tmp_path))
        output = tmp_path / "rendered"
        assert build(target) == 0
        repository = output / where
        subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
        subprocess.run(["git", "-C", str(repository), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repository), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--quiet", "-m", "publish"], check=True)
        before = _snapshot(output)
        capsys.readouterr()
        assert build(target) == 1
        assert f"{(repository / '.git').relative_to(tmp_path).as_posix()}: a git repository inside the output" in capsys.readouterr().out
        assert check(target) == 1
        assert _snapshot(output) == before

    def test_a_new_or_empty_output_directory_is_the_render_s(self, tmp_path: Path) -> None:
        target = load_outside_target(_fixture(tmp_path))
        (tmp_path / "rendered").mkdir()
        assert build(target) == 0
        assert check(target) == 0

    def test_a_file_git_ignores_under_the_source_root_changes_nothing(self, tmp_path: Path) -> None:
        """What git ignores is never checked against the declarations, so the render never reads it: an ignored file at
        an upstream path would otherwise replace that file with no declaration and no hash."""
        target_file = _fixture(tmp_path)
        source = target_file.parent
        subprocess.run(["git", "init", "--quiet", str(source)], check=True)
        expected = render_outside(load_outside_target(target_file))
        _write(
            source / ".gitignore",
            "templates/skills/shared/stale-types-notice.md.j2\ntemplates/skills/ignored-skill/\nskills/house-notes/scripts/scratch.sh\n",
        )
        _write(source / "templates/skills/shared/stale-types-notice.md.j2", "An ignored replacement.\n")
        _write(source / "templates/skills/ignored-skill/SKILL.md.j2", "---\nname: ignored-skill\n---\nAn ignored skill.\n")
        _write(source / "skills/house-notes/scripts/scratch.sh", "echo an ignored script\n")
        target = load_outside_target(target_file)
        assert declaration_errors(target) == []
        assert render_outside(target) == expected
        with pytest.raises(SystemExit, match=re.escape("[skills] include names 'ignored-skill', a skill that exists neither upstream nor")):
            load_outside_target(_edit(target_file, '"house-notes"]', '"house-notes", "ignored-skill"]'))

    def test_an_output_git_ignores_whole_is_held_to_every_file_it_holds(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """A consumer that git-ignores its rendering ignores what ships, so ignored files there are not litter: an
        ignored directory of somebody's skills is not empty, and a skill the target stops rendering is still removed."""
        subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
        _write(tmp_path / ".gitignore", "rendered/\n")
        target_file = _fixture(tmp_path)
        output = tmp_path / "rendered"
        theirs = _write(output / "pipelex-edit" / "SKILL.md", "Somebody else's skill.\n")
        assert build(load_outside_target(target_file)) == 1
        assert "rendered: holds files no render of this target wrote (rendered/pipelex-edit/SKILL.md)" in capsys.readouterr().out
        assert theirs.read_text() == "Somebody else's skill.\n"
        shutil.rmtree(output)
        assert build(load_outside_target(target_file)) == 0
        target = load_outside_target(_edit(target_file, ', "house-notes"]', "]"))
        capsys.readouterr()
        assert check(target) == 1
        assert "ORPHAN: rendered/house-notes/SKILL.md" in capsys.readouterr().out
        assert build(target) == 0
        assert not (output / "house-notes").exists()
        assert check(target) == 0

    @pytest.mark.parametrize("ignored", ["rendered/\n", ".DS_Store\nrendered/house-notes/\n"], ids=["whole", "in-part"])
    def test_in_an_ignored_output_litter_stays_and_a_skill_no_longer_rendered_goes(
        self, tmp_path: Path, ignored: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The marker lists what each render wrote, so in an output git ignores, in part or as a whole, a skill the target
        stops rendering is reported and removed, while a `.DS_Store` no render wrote is neither."""
        subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
        _write(tmp_path / ".gitignore", ignored)
        target_file = _fixture(tmp_path)
        output = tmp_path / "rendered"
        assert build(load_outside_target(target_file)) == 0
        litter = [_write(output / ".DS_Store", ""), _write(output / "pipelex-edit" / ".DS_Store", "")]
        assert check(load_outside_target(target_file)) == 0
        target = load_outside_target(_edit(target_file, ', "house-notes"]', "]"))
        capsys.readouterr()
        assert check(target) == 1
        assert "ORPHAN: rendered/house-notes/SKILL.md" in capsys.readouterr().out
        assert build(target) == 0
        assert not (output / "house-notes").exists()
        assert all(path.exists() for path in litter)
        assert check(target) == 0
