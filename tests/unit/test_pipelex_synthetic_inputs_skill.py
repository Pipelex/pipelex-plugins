"""Pin the shape of the pipelex-synthetic-inputs skill after the size diet, and its references."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from pytest_mock import MockerFixture

from scripts.check import SKILL_CEILING_CHARS
from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir

TARGETS = ("prod", "codex", "mistral-vibe")


class TestPipelexSyntheticInputsSkillShape:
    """The size diet (L-260923-a9bdfe, phase 6) rewrote the skill in the read-before-act
    shape: what it makes and refuses, its guards, the main path and a stop table in `SKILL.md`, the
    venv rung in a reference read when `uv` is absent, and the recipes in the references they
    already lived in. What these pin is that shape holding: each reference pointed at where its
    branch is taken, static, opening with its entry condition, one level deep, and shipped byte for
    byte. The identity rules and the environment ladder are pinned in `test_gen_skill_docs.py`, the
    recipes and the venv program in `tests/recipes`, and the guards in `test_skill_guards.py`.
    """

    REPO_ROOT = Path(__file__).parents[2]
    REFERENCES_DIR = REPO_ROOT / "skills" / "pipelex-synthetic-inputs" / "references"
    REFERENCES = ("pdf.md", "png.md", "office.md", "venv.md", "photograph.md")
    VENV_SCRIPT = REPO_ROOT / "skills" / "pipelex-synthetic-inputs" / "scripts" / "synth_venv.py"

    def render(self, target_name: str) -> str:
        """The skill as the named target renders it — what a user of that harness installs."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-synthetic-inputs"],
            target_name=config.name,
        )
        return next(content for path, content in rendered.items() if path.match("skills/pipelex-synthetic-inputs/SKILL.md"))

    def reference(self, name: str) -> str:
        return (self.REFERENCES_DIR / name).read_text(encoding="utf-8")

    @staticmethod
    def the_line(body: str, needle: str) -> str:
        """The one line carrying `needle`. Two of them is a duplicated rule, which is its own defect."""
        lines = [line for line in body.splitlines() if needle in line]
        assert len(lines) == 1, f"expected exactly one line containing {needle!r}, found {len(lines)}"
        return lines[0]

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_each_branch_is_pointed_at_where_it_is_taken(self, target_name: str) -> None:
        """Box A of the size diet: a branch moves to a reference only behind a pointer placed at the decision
        point, read before acting — a pointer only in the closing index is a caveat that will not be read."""
        body = self.render(target_name)
        at_the_decision = {
            "**Rung 2 — no `uv`, but a Python 3 with `venv` and `pip`.**": ("references/venv.md",),
            "Read the format's reference": ("references/pdf.md", "references/png.md", "references/office.md"),
            "A `photograph` follows": ("references/photograph.md",),
        }
        for decision, targets in at_the_decision.items():
            line = self.the_line(body, decision)
            for target in targets:
                assert f"]({target})" in line, f"{target_name}: {target} is not pointed at where its branch is taken: {line!r}"
            assert "before" in line, f"{target_name}: the pointer does not say to read before acting: {line!r}"
        index = body.split("## References", 1)[1]
        for name in self.REFERENCES:
            assert f"(references/{name})" in index, f"{target_name}: the reference index does not name {name}"

    def test_the_references_are_static_and_say_when_they_are_read(self) -> None:
        """References are copied verbatim into every target and never rendered, so a template expression in one
        ships as literal braces; and each opens by naming the condition that sends the model to it."""
        for name in self.REFERENCES:
            text = self.reference(name)
            assert "{{" not in text and "{%" not in text, f"references/{name} carries template syntax, which is never rendered"
            first_paragraph = text.split("\n\n")[1]
            assert first_paragraph.startswith("Read this "), f"references/{name} does not open with its entry condition"

    def test_a_reference_never_sends_the_model_to_another(self) -> None:
        """References are one level deep: one read is enough to take a branch. A reference may name the skill's
        steps and its stop table, and link its own headings, but never another reference. It links no shared file: a
        static reference is copied verbatim, and where the shared files sit differs between layouts."""
        for name in self.REFERENCES:
            text = self.reference(name)
            for other in self.REFERENCES:
                if other != name:
                    assert other not in text, f"references/{name} sends the model on to references/{other}"
            for target in re.findall(r"\]\(([^)]+)\)", text):
                assert target.startswith("#"), (
                    f"references/{name} links {target}; a static reference is copied verbatim, so it links only its own headings"
                )

    def test_the_photograph_rule_is_the_skills_and_sees_a_scanned_photo(self) -> None:
        """How a photograph is made is a guard, so it lives in `SKILL.md` and not in the PNG recipes, which are
        read at step 4, after step 1 has decided it. The one exception it carries — a photo of a receipt is a
        `document_scan`, which code makes — sat in `png.md`, where a model deciding at step 1 never read it. The
        proof lab (L-260923-9d0b53) replaced the refusal of photographs and handwriting with generation through
        the workshop and simulated handwriting, and the rule keeps both the exception and the ban on stand-ins."""
        for target_name in TARGETS:
            body = self.render(target_name)
            rule = self.the_line(body, "**A photograph is generated, never drawn:**")
            assert "A photo of a receipt or a form is a `document_scan`, which code makes" in rule
            assert "never from a procedural scene or a public image" in rule
            assert "**Handwriting is simulated**" in rule and "reads more easily than a real hand" in rule
        png = self.reference("png.md")
        assert "**Not covered:**" not in png
        assert "in disguise" not in png
        assert "## Handwritten marks (Pillow)" in png

    def test_the_photograph_reference_generates_through_the_workshop(self) -> None:
        """A photograph is generated by `gpt-image-2` from an inline one-pipe bundle, saved with the workshop's
        download tool, checked fact by fact, and reported as AI-generated with its run id and cost."""
        text = self.reference("photograph.md")
        assert 'model        = "gpt-image-2"' in text
        assert 'type         = "PipeImgGen"' in text
        for tool in ("`mthds_run`", "`mthds_run_status`", "`mthds_run_results`", "`mthds_download_artifacts`"):
            assert tool in text, f"photograph.md does not name {tool}"
        assert "spends inference credit" in text
        assert "**Plant every fact the method must find, visibly and unambiguously.**" in text
        assert "AI-generated" in text

    def test_a_set_of_photographs_of_one_subject_shares_a_reference(self) -> None:
        """Photographs of one subject generated from words alone show a different car each time, which plants a
        mismatch nobody asked for; the proof lab (L-260923-9d0b53) saw three of five drift. The first photograph
        becomes the reference image of the others, through a second inline bundle with an `Image` input. A room
        drifts even then: the reference kept its materials and the model redrew its walls, so a room's set is
        described from a plan by the wall each view faces, and checked by reading the plan back out."""
        text = self.reference("photograph.md")
        assert "**Several photographs of one subject**" in text
        assert 'inputs       = { reference = "Image", description = "Text" }' in text
        assert 'prompt       = "Reference photo: $reference\\n\\n$description"' in text
        assert "the photographs of one subject show the same one" in text
        assert "**A room seen from two places keeps its materials and loses its walls.**" in text
        assert "read the plan back out of each photograph" in text

    def test_a_document_is_made_in_the_originals_office_format(self) -> None:
        """The hosted plane reads a `.docx`, `.xlsx` or `.pptx` under a `Document` input as it is, so a test file in that
        format exercises the route the user's own files take, where a PDF the user would export skipped it. A legacy or
        OpenDocument file is read as the PDF the platform converts it to, since the extractors and models that read Office
        files read only the modern formats, so its test file is a `pdf`, which exercises the reader but not the
        conversion's losses."""
        body = self.render("prod")
        rule = self.the_line(body, "A `Document` whose originals are `.docx`, `.xlsx` or `.pptx` files")
        assert "is one like them, or a `pdf` when the caller asks." in rule
        assert "A legacy or OpenDocument original (`.doc`, `.xls`, `.ppt`, `.odt`, `.ods`, `.odp`) gets a `pdf`" in rule
        assert "the test exercises the reader, not the conversion's losses." in rule
        assert "Word, Excel or PowerPoint files is a `docx`" not in rule, "a legacy original would get a modern fixture"
        assert "`docx` → `python-docx`; `xlsx` → `openpyxl`; `pptx` → `python-pptx`." in body
        assert "`python-pptx` (MIT)" in body

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_way_out_without_a_file_hands_back_no_path(self, target_name: str) -> None:
        """`/pipelex-inputs` leaves an input unfilled when the factory returns no path, so both ways the skill
        ends without a file — the refusal at step 1 and a graceful stop on the environment — reach step 6's
        hand-back, which states it once."""
        body = self.render(target_name)
        hand_back = self.the_line(body, "return **no path** with the reason")
        assert "After a refusal or a graceful stop" in hand_back
        assert "Then report as step 6 says" in self.the_line(body, "**stop gracefully**")

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_hand_back_says_the_file_goes_up_as_a_test_file(self, target_name: str) -> None:
        """This skill uploads nothing: `/pipelex-inputs` uploads the files it makes, with `kind: "test"`, so the
        team's files list them as the method's test files rather than among the members' own uploads. The
        hand-back says so, and the upload stays the inputs skill's."""
        hand_back = self.the_line(self.render(target_name), "uploads the file with `mthds_prepare_inputs`")
        assert "uploads the file with `mthds_prepare_inputs` as the method's test file, and offers the run" in hand_back
        assert "never uploads anything" in self.render(target_name)

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_a_workbook_s_layout_is_handed_over_and_mapped_onto_the_recipe(self, target_name: str) -> None:
        """A sheet holding an Excel Table is read and filled as that Table, so a workbook a `sheet_range` takes must be
        plain rows or its test proves nothing about the user's sheet. Only `/pipelex-inputs` sees the steps that take
        the workbook, so it passes the layout in `constraints`, the factory's request names it, and the recipe's
        constants map from it."""
        body = self.render(target_name)
        assert "and an `xlsx`'s layout" in self.the_line(body, "- `constraints`:")
        synthetic = (self.REPO_ROOT / "skills" / "pipelex-inputs" / "references" / "synthetic.md").read_text(encoding="utf-8")
        assert "**A workbook's layout follows the steps that take it**" in synthetic
        assert "`layout: plain, sheet: Feuil1, header_row: 3, totals: yes`" in synthetic
        assert "`layout: table, name: Expenses`" in synthetic
        assert "pass **`layout: named, name: Expenses`** when the user's workbook" in synthetic
        assert "when you cannot tell, ask, or pass `table` and say so" in synthetic
        office = self.reference("office.md")
        assert "The layout is the request's `constraints` layout." in office
        assert "# The request's `constraints` layout sets these. LAYOUT is its `layout`" in office
        assert "`layout: named`: the rows with no Table, and a defined name" in office

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_default_target_is_a_temporary_directory_never_beside_a_method(self, target_name: str) -> None:
        """`L-260924-208499`: the factory once wrote into an `inputs/` beside the bundle, which it marked with a
        `.gitignore` of `*`; but every surface sends a method's folder whole, and a `uv_build` wheel ships it whatever
        a `.gitignore` says. A test file reaches a run as an upload, so by default it is made in a fresh temporary
        directory, standalone too, and `/pipelex-inputs` uploads it from there with `kind: "test"`. A target the
        caller names is honoured: the lab names a case's `inputs/`, outside every method. The temporary path goes
        into the report, with the file's name among the team's files."""
        body = self.render(target_name)
        target = self.the_line(body, "- `target`: the path to write;")
        assert target == (
            "- `target`: the path to write; by default `<input_variable>.<ext>`, standalone `<name>.<ext>`, in step 2's temporary "
            "directory, **never beside a method**, whose folder travels whole: a test file reaches a run as an upload. "
            "A target the caller or the user names is honoured."
        )
        assert "prints this invocation's temporary directory" in self.the_line(body, "**Rung 1 — `uv --version` answers**")
        assert "./inputs/" not in body
        assert ".gitignore` holding `*`" not in body, "nothing the factory writes by default lies in a tree it must mark"
        synthetic = (self.REPO_ROOT / "skills" / "pipelex-inputs" / "references" / "synthetic.md").read_text(encoding="utf-8")
        assert "`<tmp>` being a temporary directory made once for the preparation with `mktemp -d`" in synthetic
        assert "For a case's copies, `<output_dir>/inputs/` stands in for `<tmp>`" in synthetic
        assert "No `target` lies beside the method" in synthetic
        assert "The report gives each generated file's temporary path" in synthetic

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_a_failure_removes_the_recipes_partial_file(self, target_name: str) -> None:
        """Every recipe renders to a hidden `PART` beside `OUT`, deletes it in a `finally` and renames it onto `OUT` only on
        success, so only a run killed mid-save leaves that file behind. Step 4's cleanup names it, spelled as the recipes
        compute it, and deletes it through the runner, in any shell, or "a failure leaves nothing behind" is false."""
        part_line = 'PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))'
        for name in ("pdf.md", "png.md", "office.md"):
            text = self.reference(name)
            recipes = text.count("os.replace(PART, OUT)")
            assert recipes > 0, f"references/{name} has no recipe renaming PART onto OUT"
            assert text.count(part_line) == recipes, f"references/{name}: a recipe computes its partial file another way"
            assert text.count("finally:\n    Path(PART).unlink(missing_ok=True)") == recipes, (
                f"references/{name}: a recipe keeps its partial file on failure"
            )
        example = Path("invoice.pdf")
        partial = example.with_name(f".{example.stem}.part{example.suffix}")
        cleanup = self.render(target_name).split("### Step 4", 1)[1].split("### Step 5", 1)[0]
        assert f"`{partial.as_posix()}` for `{example.as_posix()}`" in cleanup
        assert '`<runner> -c "import os, sys; os.remove(sys.argv[1])" "<partial file>"`' in cleanup
        assert "rm -f" not in cleanup

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_verify_step_matches_the_harness(self, target_name: str) -> None:
        """Only Claude Code has a tool that shows the model an image; elsewhere the check stands on its own."""
        verify = self.the_line(self.render(target_name), "Reopen the file with its reference's verify command")
        if target_name == "prod":
            assert "view a PNG with the `Read` tool" in verify
            assert "Open a PNG if the harness can display images" not in verify
        else:
            assert "Open a PNG if the harness can display images" in verify
            assert "`Read` tool" not in verify

    def test_the_png_verify_command_reports_the_size(self) -> None:
        """Step 5 reads a PNG's kilobytes to tell a scan from a mistake, and the command moved from the skill into
        `png.md`'s verify block, which printed no size before."""
        verify = self.reference("png.md").split("## Verify", 1)[1]
        assert "os.path.getsize(sys.argv[1]) // 1024, 'KB'" in verify

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_target_ships_the_references_byte_for_byte(self, target_name: str) -> None:
        """The committed target copies are the ones a user installs, so compare against those."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        installed = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-synthetic-inputs" / "references"
        assert sorted(path.name for path in installed.iterdir()) == sorted(self.REFERENCES), f"{target_name}: stale or missing references"
        for name in self.REFERENCES:
            assert (installed / name).read_bytes() == (self.REFERENCES_DIR / name).read_bytes(), f"{target_name}: references/{name} is stale"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_skill_fits_what_a_compaction_keeps(self, target_name: str) -> None:
        """The diet brought this skill under the ceiling; this holds the phase's result on every target."""
        size = len(self.render(target_name))
        assert size <= SKILL_CEILING_CHARS, (
            f"{target_name}: pipelex-synthetic-inputs renders {size} characters, over the {SKILL_CEILING_CHARS} ceiling"
        )

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_target_ships_the_venv_script_byte_for_byte(self, target_name: str) -> None:
        """The venv rung is the script, so the copy a user installs is the one that must match."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        installed = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-synthetic-inputs" / "scripts"
        assert sorted(path.name for path in installed.iterdir()) == [self.VENV_SCRIPT.name], f"{target_name}: stale or missing scripts"
        assert (installed / self.VENV_SCRIPT.name).read_bytes() == self.VENV_SCRIPT.read_bytes(), f"{target_name}: the venv script is stale"

    def load_venv_script(self) -> ModuleType:
        """The shipped script as a module, so a test can narrow its allowlist to what needs no network. It is compiled
        from its source rather than imported, which would leave a `__pycache__` beside it for the build to ship."""
        module = ModuleType("synth_venv")
        module.__file__ = str(self.VENV_SCRIPT)
        exec(compile(self.VENV_SCRIPT.read_text(encoding="utf-8"), str(self.VENV_SCRIPT), "exec"), module.__dict__)
        return module

    @pytest.mark.cross_os
    def test_the_venv_script_refuses_a_path_that_is_not_a_venv(self, tmp_path: Path) -> None:
        """The script builds with `--clear`, which empties the directory first, and it runs unattended: a path that
        exists and is not a venv is refused, untouched, with the reason on stderr and exit code 1."""
        venv = tmp_path / "pipelex-plugins" / "synth-venv"
        venv.mkdir(parents=True)
        precious = venv / "notes.txt"
        precious.write_text("someone's file", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(self.VENV_SCRIPT)],
            env={**os.environ, "XDG_CACHE_HOME": str(tmp_path)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1, result.stderr
        assert "refusing to build a venv over" in result.stderr and "it exists and is not a venv" in result.stderr
        assert result.stdout == ""
        assert precious.read_text(encoding="utf-8") == "someone's file"

    @pytest.mark.cross_os
    def test_the_venv_script_builds_reuses_and_hands_over(self, tmp_path: Path, mocker: MockerFixture, capfd: pytest.CaptureFixture[str]) -> None:
        """With no argument the script builds the venv with the interpreter that started it and prints the venv's
        interpreter, `Scripts\\python.exe` on Windows and `bin/python` elsewhere; with arguments it hands them to that
        interpreter and passes its exit code back, which is what makes it the runner in every shell; a second call
        reuses the venv. The allowlist is narrowed to the standard library so no package is downloaded."""
        module = self.load_venv_script()
        mocker.patch.object(module, "IMPORTS", ("json",))
        mocker.patch.object(module, "PACKAGES", ())
        mocker.patch.dict(os.environ, {"XDG_CACHE_HOME": str(tmp_path)})
        venv = tmp_path / "pipelex-plugins" / "synth-venv"
        expected = (venv / "Scripts" / "python.exe") if os.name == "nt" else (venv / "bin" / "python")

        assert module.main([]) == 0
        built = capfd.readouterr()
        assert built.out.strip() == str(expected.absolute()), built.err
        assert "building the venv" in built.err

        code = "import sys; print(sys.prefix); sys.exit(7)"
        assert module.main(["-c", code]) == 7, "the interpreter's exit code is not passed back"
        handed = capfd.readouterr()
        assert Path(handed.out.strip()).resolve() == venv.resolve(), "the arguments did not run in the venv"
        assert handed.err == "", f"the reuse path built or installed again: {handed.err}"
