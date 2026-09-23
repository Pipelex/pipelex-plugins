"""Pin the shape of the pipelex-catalog skill after the size diet, and its references."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.check import SKILL_CEILING_CHARS
from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir

TARGETS = ("prod", "codex", "mistral-vibe")


class TestPipelexCatalogSkillShape:
    """The size diet (`wip/skill-size-diet/`, phase 6) rewrote the skill in the read-before-act
    shape: list and find, the save as numbered steps and the pull as numbered steps in `SKILL.md`,
    with a Guards section and one stop table; and three branches in references read on their
    condition — the Python a `PipeFunc` bundle sends, a save refused because the saved method moved,
    and an error at `method_id`. What these pin is that shape holding: each reference pointed at on
    the line where its branch is taken, static, opening with its entry condition, one level deep, and
    shipped byte for byte. The rules themselves are pinned in
    `test_gen_skill_docs.py::TestPipelexCatalogSkill`, and the guards in `test_skill_guards.py`.
    """

    REPO_ROOT = Path(__file__).parents[2]
    REFERENCES_DIR = REPO_ROOT / "skills" / "pipelex-catalog" / "references"
    REFERENCES = ("python.md", "conflict.md", "unknown-id.md")

    def render(self, target_name: str) -> str:
        """The skill as the named target renders it — what a user of that harness installs."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-catalog"],
            target_name=config.name,
        )
        return next(content for path, content in rendered.items() if path.match("skills/pipelex-catalog/SKILL.md"))

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
            "3. **Decide `python`.**": "references/python.md",
            "| `input_domain` at `expected_updated_at`": "references/conflict.md",
            "| `input_domain` at `method_id`": "references/unknown-id.md",
        }
        for decision, target in at_the_decision.items():
            line = self.the_line(body, decision)
            assert f"]({target})" in line, f"{target_name}: {target} is not pointed at where its branch is taken: {line!r}"
            assert "before" in line, f"{target_name}: the pointer does not say to read before acting: {line!r}"
        index = body.split("## References", 1)[1]
        for name in self.REFERENCES:
            assert f"(references/{name})" in index, f"{target_name}: the reference index does not name {name}"

    def test_the_unknown_id_reference_answers_a_pull_too(self) -> None:
        """The stop-table row names the error, not the tool, so a pull of an unknown id reaches the reference
        as well as a save does. Phase 6's smoke sessions found it written for a save alone."""
        reference = self.reference("unknown-id.md")
        assert "`mthds_save_method` or a pull's `mthds_get_method`" in reference.splitlines()[2]
        assert "**A pull has no link to judge.**" in reference

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_each_branch_keeps_its_guard_at_the_pointer(self, target_name: str) -> None:
        """A guard never lives only in a file read on demand, so the line that sends the model to a branch
        states the guard that branch protects: stored Python is chosen and never swept, the conflict's two
        ways are the user's to choose between, and a dead link is removed only on a yes."""
        body = self.render(target_name)
        assert "do not sweep the directory" in self.the_line(body, "3. **Decide `python`.**")
        assert "**Never choose between them.**" in self.the_line(body, "| `input_domain` at `expected_updated_at`")
        assert "removed only on the user's yes" in self.the_line(body, "| `input_domain` at `method_id`")

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_pull_refusals_are_stated_once_in_the_stop_table(self, target_name: str) -> None:
        """The old skill had a refusal table inside Pull and stop rows restating half of it. The refusals are
        stop-table rows now, each once, and the Pull section names the table rather than restating them."""
        body = self.render(target_name)
        stops = body.split("## Stops", 1)[1].split("\n## ", 1)[0]
        pull = body.split("## Pull", 1)[1].split("\n## ", 1)[0]
        for refusal in (
            "somebody else's work: pull into another directory",
            "say the directory was already up to date",
            "the difference is local work this directory never saved",
            "call again with `overwrite: true`",
        ):
            assert body.count(refusal) == 1, f"{target_name}: {refusal!r} is stated {body.count(refusal)} times"
            assert refusal in stops, f"{target_name}: {refusal!r} is not a stop-table row"
        assert "relay it as the stop table says" in pull

    def test_the_references_are_static_and_say_when_they_are_read(self) -> None:
        """References are copied verbatim into every target and never rendered, so a template expression in one
        ships as literal braces; and each opens by naming the condition that sends the model to it."""
        for name in self.REFERENCES:
            text = self.reference(name)
            assert "{{" not in text and "{%" not in text, f"references/{name} carries template syntax, which is never rendered"
            first_paragraph = text.split("\n\n")[1]
            assert first_paragraph.startswith("Read this when "), f"references/{name} does not open with its entry condition"

    def test_a_reference_never_sends_the_model_to_another(self) -> None:
        """References are one level deep: one read is enough to take a branch. A reference may name the skill's
        guards and its tools in words, but never another reference, and it links nothing but the shared files."""
        for name in self.REFERENCES:
            text = self.reference(name)
            for other in self.REFERENCES:
                if other != name:
                    assert other not in text, f"references/{name} sends the model on to references/{other}"
            for target in re.findall(r"\]\(([^)]+)\)", text):
                assert target.startswith("../../shared/"), f"references/{name} links {target}, which is not a shared file"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_target_ships_the_references_byte_for_byte(self, target_name: str) -> None:
        """The committed target copies are the ones a user installs, so compare against those."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        installed = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-catalog" / "references"
        assert sorted(path.name for path in installed.iterdir()) == sorted(self.REFERENCES), f"{target_name}: stale or missing references"
        for name in self.REFERENCES:
            assert (installed / name).read_bytes() == (self.REFERENCES_DIR / name).read_bytes(), f"{target_name}: references/{name} is stale"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_skill_fits_what_a_compaction_keeps(self, target_name: str) -> None:
        """Hold the phase's result even while `make check` only reports: a growth past the ceiling would
        otherwise pass every gate."""
        size = len(self.render(target_name))
        assert size <= SKILL_CEILING_CHARS, f"{target_name}: pipelex-catalog renders {size} characters, over the {SKILL_CEILING_CHARS} ceiling"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_platform_renders_the_skill(self, target_name: str) -> None:
        body = self.render(target_name)
        assert "# The method catalog" in body
        assert "{%" not in body
        assert "{{" not in body
        if target_name != "prod":
            assert "mcp__" not in body
