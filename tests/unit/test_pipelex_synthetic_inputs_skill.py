"""Pin the shape of the pipelex-synthetic-inputs skill after the size diet, and its references."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.check import SKILL_CEILING_CHARS
from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir

TARGETS = ("prod", "codex", "mistral-vibe")


class TestPipelexSyntheticInputsSkillShape:
    """The size diet (`wip/skill-size-diet/`, phase 6) rewrote the skill in the read-before-act
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
            "**Rung 2 — no `uv`, but `python3` with `venv` and `pip`.**": ("references/venv.md",),
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
        steps and its stop table, its own headings and the shared files, but never another reference."""
        for name in self.REFERENCES:
            text = self.reference(name)
            for other in self.REFERENCES:
                if other != name:
                    assert other not in text, f"references/{name} sends the model on to references/{other}"
            for target in re.findall(r"\]\(([^)]+)\)", text):
                assert target.startswith(("#", "../../shared/")), f"references/{name} links {target}, which is not its own heading or a shared file"

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
    def test_a_failure_removes_the_recipes_partial_file(self, target_name: str) -> None:
        """Every recipe renders to a hidden `PART` beside `OUT` and renames it on success, so a recipe that crashes
        mid-save leaves that file behind. Step 4's cleanup names it, spelled as the recipes compute it, or "a
        failure leaves nothing behind" is false."""
        part_line = 'PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))'
        for name in ("pdf.md", "png.md", "office.md"):
            text = self.reference(name)
            recipes = text.count("os.replace(PART, OUT)")
            assert recipes > 0, f"references/{name} has no recipe renaming PART onto OUT"
            assert text.count(part_line) == recipes, f"references/{name}: a recipe computes its partial file another way"
        example = Path("inputs/invoice.pdf")
        partial = example.with_name(f".{example.stem}.part{example.suffix}")
        cleanup = self.render(target_name).split("### Step 4", 1)[1].split("### Step 5", 1)[0]
        assert f"`{partial.as_posix()}` for `{example.as_posix()}`" in cleanup
        assert 'rm -f "<target_dir>/.<target_stem>.part<target_ext>"' in cleanup
        assert 'rm -f "<target>"' in cleanup

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
