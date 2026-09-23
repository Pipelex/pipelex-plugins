"""Pin the shape of the pipelex-inputs skill after the size diet, and its references."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.check import SKILL_CEILING_CHARS
from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir

TARGETS = ("prod", "codex", "mistral-vibe")


class TestPipelexInputsSkill:
    """The size diet (`wip/skill-size-diet/`, phase 3) rewrote the skill in the read-before-act
    shape: the main path, its guards and a stop table in `SKILL.md`, and the branches in references
    read on their condition — the Synthetic and User data strategies, a published address, and the
    errors preparation can return. What these pin is that shape holding: each reference pointed at
    on the line where its branch is taken, each reference static and opening with its entry
    condition, one level deep, and shipped byte for byte. The rules themselves are pinned where they
    were before the diet, in `test_gen_skill_docs.py`, and the guards in `test_skill_guards.py`.
    """

    REPO_ROOT = Path(__file__).parents[2]
    REFERENCES_DIR = REPO_ROOT / "skills" / "pipelex-inputs" / "references"
    REFERENCES = ("synthetic.md", "user-data.md", "published-address.md", "prepare-errors.md")

    def render(self, target_name: str) -> str:
        """The skill as the named target renders it — what a user of that harness installs."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-inputs"],
            target_name=config.name,
        )
        return next(content for path, content in rendered.items() if path.match("skills/pipelex-inputs/SKILL.md"))

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
            "- **A published method**": ("references/published-address.md",),
            "- **Synthetic**: read [": ("references/synthetic.md",),
            "- **User data**: read [": ("references/user-data.md",),
            "| template: `is_valid: false` |": ("references/published-address.md",),
            "| prepare: `input_domain` at `inputs`": ("references/prepare-errors.md",),
            "| prepare, by address:": ("references/published-address.md",),
        }
        for decision, targets in at_the_decision.items():
            line = self.the_line(body, decision)
            for target in targets:
                assert f"]({target})" in line, f"{target_name}: {target} is not pointed at where its branch is taken: {line!r}"
            assert "before" in line or "as [" in line, f"{target_name}: the pointer does not say to read before acting: {line!r}"
        assert "read both references" in self.the_line(body, "- **Mixed**:")
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
        steps, its guards and its stop table, and the shared files, but never another reference."""
        for name in self.REFERENCES:
            text = self.reference(name)
            for other in self.REFERENCES:
                if other != name:
                    assert other not in text, f"references/{name} sends the model on to references/{other}"
            for target in re.findall(r"\]\(([^)]+)\)", text):
                assert target.startswith("../../shared/"), f"references/{name} links {target}, which is not a shared file"

    def test_the_references_carry_no_per_target_spelling(self) -> None:
        """A static reference is the same file on every target, so it cannot tell a Codex or Vibe user to type
        a Claude slash command, and the delegation sentence that differs per harness stays in the template."""
        for name in self.REFERENCES:
            text = self.reference(name)
            assert "Invoke it with `/pipelex-synthetic-inputs`" not in text
            assert "cross-skill invocation" not in text

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_target_ships_the_references_byte_for_byte(self, target_name: str) -> None:
        """The committed target copies are the ones a user installs, so compare against those."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        installed = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-inputs" / "references"
        assert sorted(path.name for path in installed.iterdir()) == sorted(self.REFERENCES), f"{target_name}: stale or missing references"
        for name in self.REFERENCES:
            assert (installed / name).read_bytes() == (self.REFERENCES_DIR / name).read_bytes(), f"{target_name}: references/{name} is stale"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_skill_fits_what_a_compaction_keeps(self, target_name: str) -> None:
        """The diet brought this skill under the ceiling while `make check` still only reports, so a growth past
        it would pass every gate; this holds the phase's result until the ceiling bites for every skill."""
        size = len(self.render(target_name))
        assert size <= SKILL_CEILING_CHARS, f"{target_name}: pipelex-inputs renders {size} characters, over the {SKILL_CEILING_CHARS} ceiling"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_platform_renders_the_skill(self, target_name: str) -> None:
        body = self.render(target_name)
        assert "# Prepare Inputs for MTHDS methods" in body
        assert "{%" not in body
        assert "{{" not in body
        if target_name == "prod":
            assert "mcp__plugin_pipelex_pipelex__mthds_prepare_inputs" in body
        else:
            assert "mcp__" not in body
            assert "`/pipelex-run`'s, whose `SKILL.md` sits beside this one" in body
