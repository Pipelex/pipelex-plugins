"""Pin the shape of the pipelex-design skill after the size diet, and its references."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.check import SKILL_CEILING_CHARS
from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir

TARGETS = ("prod", "codex", "mistral-vibe")


class TestPipelexDesignSkill:
    """The size diet (`wip/skill-size-diet/`, phase 4) rewrote the skill in the read-before-act
    shape: the contract, the bundle home, the choice of mode, direct construction, the verdicts, the
    runnable gate and delivery in `SKILL.md`, with the re-entry guards and a stop table; and the two
    branches the skill decides first in references read on their condition — stepwise construction
    and re-entry. A catalog id or an address is resolved through the shared reference
    `skills/shared/catalog-id.md`, pinned in `test_gen_skill_docs.py::TestCatalogIdInEverySkill`.
    What these pin is that shape holding: each reference pointed at on the line where its branch is
    taken, each new reference static and opening with its entry condition, one level deep, and
    shipped byte for byte. The rules themselves are pinned in `test_gen_skill_docs.py`
    (`TestAdaptiveDesignSkill`, `TestBundleHome`), and the guards in `test_skill_guards.py`.
    """

    REPO_ROOT = Path(__file__).parents[2]
    REFERENCES_DIR = REPO_ROOT / "skills" / "pipelex-design" / "references"
    # The references the diet wrote, each read on a branch, and the only files the skill ships of
    # its own. The language reference it reads before every write, `writing-mthds.md`, is the one
    # design, edit and explain share: a rendered shared file, `skills/shared/writing-mthds.md`,
    # pointed at like the other shared files and not held to the branch references' opening.
    BRANCH_REFERENCES = ("stepwise.md", "re-entry.md")
    SHIPPED = BRANCH_REFERENCES
    LANGUAGE_REFERENCE = "../shared/writing-mthds.md"
    LANGUAGE_REFERENCE_TEMPLATE = REPO_ROOT / "templates" / "skills" / "shared" / "writing-mthds.md.j2"

    def render(self, target_name: str) -> str:
        """The skill as the named target renders it — what a user of that harness installs."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-design"],
            target_name=config.name,
        )
        return next(content for path, content in rendered.items() if path.match("skills/pipelex-design/SKILL.md"))

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
            "Read [writing-mthds.md]": (self.LANGUAGE_REFERENCE,),
            "- **Stepwise** otherwise": ("references/stepwise.md",),
            "**If the design would need a placeholder": ("references/stepwise.md",),
            "**For a catalog id (`mt_…`) or a published address**": ("../shared/catalog-id.md",),
            "Then read [re-entry.md]": ("references/re-entry.md", self.LANGUAGE_REFERENCE, "references/stepwise.md"),
        }
        for decision, targets in at_the_decision.items():
            line = self.the_line(body, decision)
            for target in targets:
                assert f"]({target})" in line, f"{target_name}: {target} is not pointed at where its branch is taken: {line!r}"
            assert "before" in line, f"{target_name}: the pointer does not say to read before acting: {line!r}"
        index = body.split("## References", 1)[1]
        for name in self.SHIPPED:
            assert f"(references/{name})" in index, f"{target_name}: the reference index does not name {name}"
        assert f"({self.LANGUAGE_REFERENCE})" in index, f"{target_name}: the reference index does not name the language reference"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_runnable_gate_holds_for_a_completed_method_only(self, target_name: str) -> None:
        """A re-entry on a deliberately partial scaffold is delivered at its baseline verdict: a gate that asked
        every ending for a runnable verdict would drive it to expand signatures nobody asked for, or loop."""
        body = self.render(target_name)
        gate = self.the_line(body, "this verdict is the runnable gate")
        assert gate.startswith("For a completed method, "), f"{target_name}: the runnable gate has lost its condition: {gate!r}"
        assert "A re-entry restores at least its baseline verdict instead." in gate
        assert self.the_line(body, "**The baseline, before every edit**").endswith("otherwise deliver as step 6 says.")

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_re_entry_references_are_read_before_any_repair(self, target_name: str) -> None:
        """Repairing a broken baseline edits the bundle, so the references a re-entry reads before editing, the
        authoring reference among them, are pointed at before the repair is asked for."""
        line = self.the_line(self.render(target_name), "**The baseline, before every edit**")
        assert line.index("Then read [re-entry.md]") < line.index("repair it first"), f"{target_name}: {line!r}"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_two_stepwise_signals_win_over_direct(self, target_name: str) -> None:
        """A large graph wanting checkpoints and an explicit request for a scaffold are not complements of the
        direct criteria, so they must choose stepwise even when every direct criterion holds."""
        line = self.the_line(self.render(target_name), "- **Stepwise** otherwise")
        assert line.startswith("- **Stepwise** otherwise, and even where direct holds, "), f"{target_name}: {line!r}"

    def test_an_early_stop_still_gives_the_delivery_notices(self) -> None:
        """A stepwise scaffold stopped early never reaches step 6, where the stale-types check and the saved-copy
        notice live, yet it changed files; the reference sends it back to both."""
        early = self.reference("stepwise.md").split("## Stopping early", 1)[1].split("\n## ", 1)[0]
        assert "stale-types check" in early and "saved-copy notice" in early

    def test_a_signature_driven_re_entry_reads_the_stepwise_reference_first(self) -> None:
        """The skill points at the stepwise reference before `re-entry.md` chooses the mode, so the scaffold's
        section says in words to have read it: its rules govern the scaffold and every refinement."""
        scaffold = self.reference("re-entry.md").split("## 3. ", 1)[1].split("\n## ", 1)[0]
        assert "only after reading the stepwise reference the skill points at for this branch" in scaffold

    def test_the_authoring_reference_says_extraction_reads_no_office_format(self) -> None:
        """A Word file passes validation and preparation and then fails the run at the extraction; the proof lab
        (L-260923-9d0b53) designed a method over Word transcripts because the reference said `Document` covers Word."""
        text = self.LANGUAGE_REFERENCE_TEMPLATE.read_text(encoding="utf-8")
        assert "**It reads a PDF, an image or a web page, and nothing else.**" in text
        assert "Any document (PDF, Word" not in text
        assert "a Word or PowerPoint file, the run fails when it reaches the render" not in text

    def test_the_references_are_static_and_say_when_they_are_read(self) -> None:
        """References are copied verbatim into every target and never rendered, so a template expression in one
        ships as literal braces; and each opens by naming the condition that sends the model to it."""
        for name in self.BRANCH_REFERENCES:
            text = self.reference(name)
            assert "{{" not in text and "{%" not in text, f"references/{name} carries template syntax, which is never rendered"
            first_paragraph = text.split("\n\n")[1]
            assert first_paragraph.startswith("Read this when "), f"references/{name} does not open with its entry condition"

    def test_a_reference_never_sends_the_model_to_another(self) -> None:
        """References are one level deep: one read is enough to take a branch. A reference may name the skill's
        steps and guards, the authoring reference the skill reads before writing, and the stepwise reference a
        signature-driven re-entry reads, in words, but never another reference by its file, and it links nothing
        but the shared files. A signature-driven re-entry needs both branch references, so the skill points at
        both from the same line, and `re-entry.md` names the stepwise one in words where that mode is taken."""
        for name in self.BRANCH_REFERENCES:
            text = self.reference(name)
            for other in (*self.SHIPPED, "writing-mthds.md"):
                if other != name:
                    assert other not in text, f"references/{name} sends the model on to references/{other}"
            for target in re.findall(r"\]\(([^)]+)\)", text):
                assert target.startswith("../../shared/"), f"references/{name} links {target}, which is not a shared file"

    def test_the_references_carry_no_per_target_spelling(self) -> None:
        """A static reference is the same file on every target, so it cannot carry a sentence that differs per
        harness; the catalog-id hand-off, which does, is the rendered shared reference's."""
        for name in self.BRANCH_REFERENCES:
            text = self.reference(name)
            assert "cross-skill invocation" not in text
            assert "catalog id" not in text.lower(), f"references/{name} restates the catalog-id bridge"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_target_ships_the_references_byte_for_byte(self, target_name: str) -> None:
        """The committed target copies are the ones a user installs, so compare against those."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        installed = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-design" / "references"
        assert sorted(path.name for path in installed.iterdir()) == sorted(self.SHIPPED), f"{target_name}: stale or missing references"
        for name in self.SHIPPED:
            assert (installed / name).read_bytes() == (self.REFERENCES_DIR / name).read_bytes(), f"{target_name}: references/{name} is stale"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_skill_fits_what_a_compaction_keeps(self, target_name: str) -> None:
        """The diet brought this skill under the ceiling while `make check` still only reports, so a growth past
        it would pass every gate; this holds the phase's result until the ceiling bites for every skill."""
        size = len(self.render(target_name))
        assert size <= SKILL_CEILING_CHARS, f"{target_name}: pipelex-design renders {size} characters, over the {SKILL_CEILING_CHARS} ceiling"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_formatting_note_is_not_a_design_step(self, target_name: str) -> None:
        """The formatting-hook note is a stop by the read-before-act test — the hook's block names the syntax
        error, and the harness refuses an edit to a file changed since it was read — so design carries none of
        it. Phase 6 decided the same for `pipelex-edit` and `pipelex-organize`, pinned in their own modules."""
        assert "**Formatting is automatic.**" not in self.render(target_name)

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_platform_renders_the_skill(self, target_name: str) -> None:
        body = self.render(target_name)
        assert "# Design a MTHDS bundle top-down at the right depth" in body
        assert "{%" not in body
        assert "{{" not in body
        if target_name == "prod":
            assert "mcp__plugin_pipelex_pipelex__mthds_validate" in body
            assert "mcp__plugin_pipelex_pipelex__mthds_inputs_template" in body
        else:
            assert "mcp__" not in body
