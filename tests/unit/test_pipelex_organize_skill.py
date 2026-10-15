"""Pin the shape of the pipelex-organize skill after the size diet."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check import SKILL_CEILING_CHARS
from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir

TARGETS = ("prod", "codex", "mistral-vibe")


class TestPipelexOrganizeSkill:
    """The size diet (L-260923-a9bdfe, phase 6) rewrote the skill in the read-before-act shape:
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
        pointer is step 1's first paragraph and the baseline call is what follows it — the step the
        inline bridge used to resume at."""
        paragraphs = self.section(self.render(target_name), "### Step 1 — Baseline verdict").strip().split("\n\n")
        assert paragraphs[0].startswith("**For a catalog id (`mt_…`) or a published address**, read [the catalog-id reference]")
        assert paragraphs[1].startswith("Call `mthds_validate` on the bundle directory.")

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_runs_exclusion_is_stated_once(self, target_name: str) -> None:
        """Phase 1's review found step 1 restating the exclusion beside the `validate-call` include
        that states it. Step 1 now passes the bundle directory as `method_dir`, so the workshop's
        folder rule decides what is sent, a saved run kept out by the `.gitignore` in its `runs/`,
        and the step reads the files the call sent; the on-disk confirmation validates as step 1
        did. The include's inline fallback names the exclusion once, for the files it lists. The
        deletion keeps its own `runs/` rule, since a `runs/` saved into before the workshop marked
        it may still be sent."""
        body = self.render(target_name)
        assert "except anything under a `runs/` directory" not in body
        assert "none under a `runs/` directory" not in body
        assert body.count("outside `runs/`") == 1, "only the include's inline fallback names the exclusion"
        assert "Read every `.mthds` file the call sent" in body
        assert "validate the bundle once more, as in Step 1" in body
        assert "never one under a `runs/` directory" in body

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_swap_touches_only_the_files_the_call_sent(self, target_name: str) -> None:
        """Step 1 reads the `.mthds` files the folder call sent, so the swap deletes only those: a
        `.mthds` file the folder rule leaves out (under a dot directory, a nested repository, a
        virtual environment or `node_modules/`, or excluded by a `.gitignore`) was never read, and
        deleting it would lose it unseen, with no copy for the rollback to restore. For the same
        reason a new file never lands on the path of an existing file outside that set."""
        steps = self.section(self.render(target_name), "### Step 4 — Swap the layout")
        write, delete = steps.strip().split("\n")[:2]
        assert write.startswith("1. Write every file of the new layout.")
        assert "may take the path of a `.mthds` file Step 1's call sent, never that of any other existing file" in write
        assert delete.startswith(
            "2. Delete every `.mthds` file Step 1's call sent (`files_sent`, or the files it listed) that is not part of the new layout."
        )
        assert "**Delete no other file," in delete
        assert "Delete every `.mthds` file that is not part of the new layout" not in steps

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_a_new_layout_file_the_folder_leaves_out_rolls_the_swap_back(self, target_name: str) -> None:
        """A new file the folder rule leaves out, one a `.gitignore` in the folder excludes, is
        not validated by the confirmation, so an equal verdict would prove a layout that lost it.
        The confirmation checks that the call sent every new-layout file, and a miss is a failure
        that rolls the swap back."""
        steps = self.section(self.render(target_name), "### Step 4 — Swap the layout")
        confirm, rollback = steps.strip().split("\n")[2:4]
        assert confirm.startswith("3. **Confirm on disk**")
        assert "check that every new-layout file is among those it sent" in confirm
        assert rollback.startswith("4. **If that confirmation fails, restore the original layout")
        assert "a new-layout file the call did not send" in rollback

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
        prefix = load_target_config(self.REPO_ROOT / "targets", target_name).template_vars["skill_prefix"]
        condition = f"**When invoked on its own rather than by `{prefix}pipelex-design`**"
        assert body.count(condition) == 1
        _, governed = self.section(body, "### Step 5 — Report").split(condition, 1)
        for notice in ("now stale and offer", "**Save the linked method's draft.**"):
            assert body.count(notice) == 1, f"{target_name}: {notice!r} is said more than once"
            assert notice in governed, f"{target_name}: {notice!r} is not under the condition"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_it_ships_no_reference_of_its_own(self, target_name: str) -> None:
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        installed = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-organize"
        assert not (installed / "references").exists(), f"{target_name}: organize grew a references directory"
        assert not (self.REPO_ROOT / "skills" / "pipelex-organize").exists()

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_a_moved_step_keeps_its_template_and_the_bundle_is_proven_on_disk(self, target_name: str) -> None:
        """A `template_file` resolves from the directory of the `.mthds` file holding its step, so moving a step
        from `sub/report.mthds` into the root module points it at a missing file, or silently at another template
        under the same relative path, which no verdict sees. So the plan records each template's real path,
        rewrites a moved step's `template_file` to reach the same file, which the guard calls layout, keeps a step
        whose template only `..` would reach where it is, and the swap is confirmed against those real paths and
        rolled back otherwise. Step 3's inline proof is skipped for such a bundle, since a template file travels
        only beside `.mthds` files read from disk."""
        body = self.render(target_name)
        guard = self.section(body, "## Guards")
        assert "a `PipeDocGen` step moved to another directory has its `template_file` rewritten to reach the same file, which is layout too" in guard
        plan = self.section(body, "### Step 2 — Plan the layout, compose the files")
        assert (
            "**A `PipeDocGen` step's template is the file its `template_file` reaches from the directory of the `.mthds` file holding the step**"
            in plan
        )
        assert "record each one's real path (`realpath`) before composing, and never move or rename a template file" in plan
        assert "its `template_file` becomes the forward-slash path that reaches the same file from there" in plan
        assert "when only a path through `..` would, which the runner refuses, that step does not move" in plan
        proof = self.section(body, "### Step 3 — Prove equivalence before touching disk")
        assert "**A bundle whose `PipeDocGen` steps name template files skips this proof**" in proof
        assert "Step 4's confirmation, with its rollback, proves the layout instead." in proof
        swap = self.section(body, "### Step 4 — Swap the layout")
        assert (
            "check that every `PipeDocGen` step's `template_file` reaches, from its new file's directory, the real path recorded for it in Step 2"
            in swap
        )
        assert "A valid verdict cannot see a step that now reaches another template under the same name." in swap
        assert "a verdict that differs from the baseline, a new-layout file the call did not send, or a template that differs from Step 2's" in swap
