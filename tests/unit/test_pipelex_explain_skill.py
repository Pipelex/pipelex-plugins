"""Pin the shape of the pipelex-explain skill after the size diet, and its reference."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.check import SKILL_CEILING_CHARS
from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir

TARGETS = ("prod", "codex", "mistral-vibe")


class TestPipelexExplainSkillShape:
    """The size diet (`wip/skill-size-diet/`, phase 6) rewrote the skill in the read-before-act shape: the
    targets, the requirements with the workshop optional, the read-only guard, the five steps of an explanation
    and a stop table in `SKILL.md`, and a method that is not on disk — a catalog id or a published address — in
    one reference read before the first call on one. What these pin is that shape holding: the reference pointed
    at on the line where its branch is taken, static, opening with its entry condition, one level deep and
    shipped byte for byte, and the skill under the ceiling. The rules themselves are pinned in
    `test_gen_skill_docs.py` (`TestPipelexExplainSkill`, `TestCatalogIdInEverySkill`), and the guards in
    `test_skill_guards.py`.
    """

    REPO_ROOT = Path(__file__).parents[2]
    REFERENCES_DIR = REPO_ROOT / "skills" / "pipelex-explain" / "references"
    SHIPPED = ("not-on-disk.md",)

    def render(self, target_name: str) -> str:
        """The skill as the named target renders it — what a user of that harness installs."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-explain"],
            target_name=config.name,
        )
        return next(content for path, content in rendered.items() if path.match("skills/pipelex-explain/SKILL.md"))

    def reference(self, name: str) -> str:
        return (self.REFERENCES_DIR / name).read_text(encoding="utf-8")

    @staticmethod
    def the_line(body: str, needle: str) -> str:
        """The one line carrying `needle`. Two of them is a duplicated rule, which is its own defect."""
        lines = [line for line in body.splitlines() if needle in line]
        assert len(lines) == 1, f"expected exactly one line containing {needle!r}, found {len(lines)}"
        return lines[0]

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_branch_is_pointed_at_where_it_is_taken(self, target_name: str) -> None:
        """Box A of the size diet: a branch moves to a reference only behind a pointer placed at the decision
        point, read before acting. The target is known before the first call, so step 1 is that point, and the
        read-only guard of the branch — no `output_dir` — sits on the same line as the pointer."""
        body = self.render(target_name)
        line = self.the_line(body, "**For a catalog id or a published address, read [not-on-disk.md]")
        assert "](references/not-on-disk.md) before the first call on it.**" in line, f"{target_name}: {line!r}"
        assert "**no `output_dir`**" in line and "Do not pass it, not even to a temporary directory." in line
        assert body.index("## References") > body.index(line), f"{target_name}: the pointer must precede the index"
        index = body.split("## References", 1)[1]
        for name in self.SHIPPED:
            assert f"(references/{name})" in index, f"{target_name}: the reference index does not name {name}"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_workshop_stays_optional(self, target_name: str) -> None:
        """The skill's posture, unchanged by the diet: the shared requirements block's two stops are scoped to a
        target that lives on the platform, an absent `mthds_get_method` narrows the explanation without stopping
        it, and a local bundle is explained whatever the workshop does."""
        body = self.render(target_name)
        requirements = body.split("## Requirements — the workshop is optional here", 1)[1].split("\n## ", 1)[0]
        assert "Never refuse to explain a local bundle because the workshop is not connected." in requirements
        assert "a narrower explanation, not a stop" in requirements
        assert "That stop is only for a target that lives on the platform" in requirements
        assert "Same scope: on a local bundle a `config` error costs the verdict line and nothing else" in requirements

    def test_the_reference_is_static_and_says_when_it_is_read(self) -> None:
        """References are copied verbatim into every target and never rendered, so a template expression in one
        ships as literal braces; and each opens by naming the condition that sends the model to it."""
        for name in self.SHIPPED:
            text = self.reference(name)
            assert "{{" not in text and "{%" not in text, f"references/{name} carries template syntax, which is never rendered"
            first_paragraph = text.split("\n\n")[1]
            assert first_paragraph.startswith("Read this when "), f"references/{name} does not open with its entry condition"

    def test_the_reference_sends_the_model_nowhere_else(self) -> None:
        """References are one level deep: one read is enough to take a branch. This one may name the skill's steps
        and stop table in words, and links nothing."""
        for name in self.SHIPPED:
            text = self.reference(name)
            assert re.findall(r"\]\(([^)]+)\)", text) == [], f"references/{name} links another file"
            assert "references/" not in text, f"references/{name} names another reference"

    def test_the_reference_carries_no_per_target_spelling(self) -> None:
        """A static reference is the same file on every target, so it cannot name a harness or its tool
        spelling."""
        for name in self.SHIPPED:
            text = self.reference(name)
            assert "mcp__" not in text, f"references/{name} spells a Claude tool name"
            for harness in ("Claude Code", "Codex", "Mistral Vibe"):
                assert harness not in text, f"references/{name} names {harness}"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_target_ships_the_reference_byte_for_byte(self, target_name: str) -> None:
        """The committed target copies are the ones a user installs, so compare against those."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        installed = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-explain" / "references"
        assert sorted(path.name for path in installed.iterdir()) == sorted(self.SHIPPED), f"{target_name}: stale or missing references"
        for name in self.SHIPPED:
            assert (installed / name).read_bytes() == (self.REFERENCES_DIR / name).read_bytes(), f"{target_name}: references/{name} is stale"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_skill_fits_what_a_compaction_keeps(self, target_name: str) -> None:
        """The diet brought this skill under the ceiling; this holds the phase's result whether or not `make check`
        enforces it yet."""
        size = len(self.render(target_name))
        assert size <= SKILL_CEILING_CHARS, f"{target_name}: pipelex-explain renders {size} characters, over the {SKILL_CEILING_CHARS} ceiling"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_platform_renders_the_skill(self, target_name: str) -> None:
        body = self.render(target_name)
        assert "# Explain an MTHDS method" in body
        assert "{%" not in body
        assert "{{" not in body
        if target_name == "prod":
            assert "mcp__plugin_pipelex_pipelex__mthds_get_method" in body
        else:
            assert "mcp__" not in body
