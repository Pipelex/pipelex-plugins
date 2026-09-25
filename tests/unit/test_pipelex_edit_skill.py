"""Pin the shape of the pipelex-edit skill after the size diet."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check import SKILL_CEILING_CHARS
from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir

TARGETS = ("prod", "codex", "mistral-vibe")


class TestPipelexEditSkill:
    """The size diet (`wip/skill-size-diet/`, phase 6) rewrote the skill in the read-before-act shape:
    its scope split, mode table, steps 1 to 7 under their old headings, a stop table and a reference
    index, and no reference of its own, since its rename checklist is read on most runs. It made the
    moves `pipelex-organize` made in the same phase: the catalog-id bridge is read from the shared
    reference `skills/shared/catalog-id.md`, and the formatting-hook note left. The guards are pinned
    in `test_skill_guards.py`, the routing and the step order in
    `test_gen_skill_docs.py::TestEditClassifiesFirstAndTriggersStopColliding`, the bridge's pointer and
    guards in `test_gen_skill_docs.py::TestCatalogIdInEverySkill`."""

    REPO_ROOT = Path(__file__).parents[2]
    TEMPLATE = REPO_ROOT / "templates" / "skills" / "pipelex-edit" / "SKILL.md.j2"

    def render(self, target_name: str) -> str:
        """The skill as the named target renders it — what a user of that harness installs."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-edit"],
            target_name=config.name,
        )
        return next(content for path, content in rendered.items() if path.match("skills/pipelex-edit/SKILL.md"))

    @staticmethod
    def section(body: str, heading: str) -> str:
        """The text under `heading`, up to the next heading of any level."""
        _, rest = body.split(f"{heading}\n", 1)
        return rest.split("\n#", 1)[0]

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_skill_fits_what_a_compaction_keeps(self, target_name: str) -> None:
        size = len(self.render(target_name))
        assert size <= SKILL_CEILING_CHARS, f"{target_name}: pipelex-edit renders {size} characters, over the {SKILL_CEILING_CHARS} ceiling"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_catalog_id_pointer_opens_step_1(self, target_name: str) -> None:
        """The shared reference sends the model back "just after its pointer to this file", so the
        pointer is step 1's first paragraph and the read is what follows it — the step the inline
        bridge used to resume at."""
        paragraphs = self.section(self.render(target_name), "### Step 1: Read the bundle").strip().split("\n\n")
        assert paragraphs[0].startswith("**For a catalog id (`mt_…`) or a published address**, read [the catalog-id reference]")
        assert paragraphs[1].startswith("Read **every** `.mthds` file of the bundle directory outside `runs/`")

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_formatting_note_is_not_an_edit_step(self, target_name: str) -> None:
        """A stop by the read-before-act test, as for `pipelex-design`: the hook's block names the syntax
        error, and the harness refuses an edit to a file changed since it was read."""
        assert "**Formatting is automatic.**" not in self.render(target_name)
        assert 'include "skills/shared/formatting-hook.md.j2"' not in self.TEMPLATE.read_text(encoding="utf-8")

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_authoring_reference_is_pointed_at_where_edits_are_made(self, target_name: str) -> None:
        """Box B puts a pointer at its condition, never only in the closing index."""
        body = self.render(target_name)
        pointer = "Before editing a construct you have not touched recently, read [the MTHDS reference](../shared/writing-mthds.md)."
        assert pointer in self.section(body, "### Step 4: Apply the edits")
        assert "[MTHDS reference](../shared/writing-mthds.md): before editing a construct you have not touched recently." in body

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_it_ships_no_reference_of_its_own(self, target_name: str) -> None:
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        installed = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-edit"
        assert not (installed / "references").exists(), f"{target_name}: edit grew a references directory"
        assert not (self.REPO_ROOT / "skills" / "pipelex-edit").exists()
