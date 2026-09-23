"""Pin the shape of the pipelex-organize skill after the size diet."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check import SKILL_CEILING_CHARS
from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir

TARGETS = ("prod", "codex", "mistral-vibe")


class TestPipelexOrganizeSkill:
    """The size diet (`wip/skill-size-diet/`, phase 6) rewrote the skill in the read-before-act shape:
    its guards, steps 1 to 5 and a stop table in `SKILL.md`, and no reference of its own, since every
    rule left in it is read on every run. It made the three moves `pipelex-edit` made in the same
    phase: the catalog-id bridge is read from the shared reference `skills/shared/catalog-id.md`, the
    formatting-hook note left, and the `runs/` exclusion is stated once, by the submission convention.
    The guards are pinned in `test_skill_guards.py`, the bridge's pointer and guards in
    `test_gen_skill_docs.py::TestCatalogIdInEverySkill`."""

    REPO_ROOT = Path(__file__).parents[2]
    TEMPLATE = REPO_ROOT / "templates" / "skills" / "pipelex-organize" / "SKILL.md.j2"

    def render(self, target_name: str) -> str:
        """The skill as the named target renders it — what a user of that harness installs."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-organize"],
            target_name=config.name,
        )
        return next(content for path, content in rendered.items() if path.match("skills/pipelex-organize/SKILL.md"))

    @staticmethod
    def section(body: str, heading: str) -> str:
        """The text under `heading`, up to the next heading of any level."""
        _, rest = body.split(f"{heading}\n", 1)
        return rest.split("\n#", 1)[0]

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_skill_fits_what_a_compaction_keeps(self, target_name: str) -> None:
        size = len(self.render(target_name))
        assert size <= SKILL_CEILING_CHARS, f"{target_name}: pipelex-organize renders {size} characters, over the {SKILL_CEILING_CHARS} ceiling"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_catalog_id_pointer_opens_step_1(self, target_name: str) -> None:
        """The shared reference sends the model back "just after its pointer to this file", so the
        pointer is step 1's first paragraph and the gather is what follows it — the step the inline
        bridge used to resume at."""
        paragraphs = self.section(self.render(target_name), "### Step 1 — Baseline verdict").strip().split("\n\n")
        assert paragraphs[0].startswith("**For a catalog id (`mt_…`) or a published address**, read [the catalog-id reference]")
        assert paragraphs[1].startswith("Gather the bundle's files as the convention below says")

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_runs_exclusion_is_stated_once(self, target_name: str) -> None:
        """Phase 1's review found step 1 restating the exclusion beside the `validate-call` include
        that states it; the step now defers to the convention, as `pipelex-catalog` and
        `pipelex-design` do, and the on-disk confirmation gathers as step 1 did. The deletion keeps
        its own `runs/` rule, since what it deletes is not what the convention submits."""
        body = self.render(target_name)
        assert body.count("except anything under a `runs/` directory") == 1
        assert "none under a `runs/` directory" not in body
        assert "outside `runs/`" not in body
        assert "validate the bundle once more, gathered as in step 1" in body
        assert "never one under a `runs/` directory" in body

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_formatting_note_is_not_an_organize_step(self, target_name: str) -> None:
        """A stop by the read-before-act test, as for `pipelex-design`: the hook's block names the syntax
        error, and the harness refuses an edit or an overwrite of a file changed since it was read. The
        one consequence organize acts on stays, as the reason its confirmation re-validates."""
        assert "**Formatting is automatic.**" not in self.render(target_name)
        assert 'include "skills/shared/formatting-hook.md.j2"' not in self.TEMPLATE.read_text(encoding="utf-8")
        assert "since the hook may have reformatted what was written" in self.render(target_name)

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_two_notices_share_one_condition(self, target_name: str) -> None:
        """Design's delivery step carries both notices when it invoked organize, so one condition governs
        both here, said once, with both notices listed under it and nowhere else."""
        body = self.render(target_name)
        condition = "**When invoked on its own rather than by `/pipelex-design`**"
        assert body.count(condition) == 1
        _, governed = self.section(body, "### Step 5 — Report").split(condition, 1)
        for notice in ("now stale and offer", "**The saved method does not have this change.**"):
            assert body.count(notice) == 1, f"{target_name}: {notice!r} is said more than once"
            assert notice in governed, f"{target_name}: {notice!r} is not under the condition"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_it_ships_no_reference_of_its_own(self, target_name: str) -> None:
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        installed = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-organize"
        assert not (installed / "references").exists(), f"{target_name}: organize grew a references directory"
        assert not (self.REPO_ROOT / "skills" / "pipelex-organize").exists()
