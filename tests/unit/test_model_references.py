"""Pin how `pipelex-design` and `pipelex-edit` look up and check a model reference.

The guidance is the "Model references" section of the shared MTHDS reference, which design reads whole
before every write and edit points at from its model-change bullet; the workshop's `mthds_models` is the
lookup. The rationale is `docs/decisions.md`, "A model reference is looked up, never invented"."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.gen_skill_docs import load_target_config, render_templates

TARGETS = ("prod", "codex", "mistral-vibe")
REPO_ROOT = Path(__file__).parents[2]
SECTION_HEADING = "### Model references"
ANCHOR = "../shared/writing-mthds.md#model-references"


def rendered(target_name: str, skill: str) -> dict[Path, str]:
    config = load_target_config(REPO_ROOT / "targets", target_name)
    return render_templates(
        REPO_ROOT / "templates",
        REPO_ROOT,
        config.template_vars,
        include_skills=[skill],
        target_name=config.name,
    )


def skill_body(target_name: str, skill: str) -> str:
    return next(content for path, content in rendered(target_name, skill).items() if path.match(f"skills/{skill}/SKILL.md"))


def model_section(target_name: str) -> str:
    """The language reference's "Model references" section, up to the next heading of its level or above."""
    reference = next(content for path, content in rendered(target_name, "pipelex-edit").items() if path.match("skills/shared/writing-mthds.md"))
    assert reference.count(f"\n{SECTION_HEADING}\n") == 1, f"{target_name}: the language reference must carry one model section"
    _, rest = reference.split(f"\n{SECTION_HEADING}\n", 1)
    return re.split(r"\n#{1,3} ", rest, maxsplit=1)[0]


class TestModelReferences:
    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_section_teaches_the_lookup(self, target_name: str) -> None:
        """The lookup replaced "offer a preset or ask which model": each case the user can ask for is met
        by a call, and the check's three answers are each read."""
        section = model_section(target_name)
        assert "**Look a reference up before writing it**, with the `mthds_models` tool." in section
        for case in (
            "- **A kind of behaviour**:",
            "- **A model or a reference the user typed**:",
            "- **A model and a setting**:",
            "- **A setting but no model**:",
        ):
            assert case in section, f"{target_name}: the section lost the case {case!r}"
        for answer in ("`resolved`", "`not_found`", "`unconfirmed`", "`suggestions`", "`other_kinds`", "`other_categories`"):
            assert answer in section, f"{target_name}: the section does not read {answer}"
        assert "offer a preset or ask which model, never invent a handle" not in section

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_a_sigil_hint_is_read_whatever_the_resolution(self, target_name: str) -> None:
        """A bare `best-gpt` checked against the dev deck came back `unconfirmed` with `@best-gpt` in
        `other_kinds`: read only on `not_found`, the hint would be skipped and the bare name written."""
        section = model_section(target_name)
        assert "When `other_kinds` holds the same name under another sigil, whatever the resolution" in section
        assert "On `unconfirmed` with neither hint" in section

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_another_category_is_read_on_any_unresolved_answer(self, target_name: str) -> None:
        """`gpt-image-2` checked as `llm` comes back `unconfirmed` with `img_gen` in `other_categories`:
        read only on `not_found`, the handle would be written on a `PipeLLM`."""
        assert "On any answer but `resolved`, a non-empty `other_categories` says the reference serves another kind of pipe" in (
            model_section(target_name)
        )

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_a_model_and_a_setting_never_write_an_unchecked_table(self, target_name: str) -> None:
        """A temperature lives only in an inline table, which validation never reads: an unconfirmed
        handle there fails at run time, so the user chooses between the model and the setting."""
        section = model_section(target_name)
        bullet = next(line for line in section.splitlines() if line.startswith("- **A model and a setting**"))
        assert "whose model must answer `resolved` and must not be a preset" in bullet
        assert "the setting on an alias the deck lists and the model without the setting" in bullet
        assert "a handle `unconfirmed` with neither hint as a plain `model` string, and anything else only as the bullet above allows" in bullet

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_a_resolved_preset_never_goes_in_an_inline_table(self, target_name: str) -> None:
        """A preset answers `resolved`, but the run-time deck refuses one inside an inline table, which
        validation never reads: `resolved` alone would let `$writing-factual` at a temperature through."""
        assert "answers `resolved` for a reference that is not a preset" in model_section(target_name)

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_section_keeps_the_default_and_never_invents(self, target_name: str) -> None:
        """A reference nobody asked for pinned a model the gateway refused after validation passed."""
        section = model_section(target_name)
        assert "**Omit `model` unless the user asks for a model, a setting such as a temperature, or a kind of behaviour" in section
        assert "Never invent a handle." in section
        assert "never invent a reference" in section

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_an_inline_table_is_checked_because_validation_skips_it(self, target_name: str) -> None:
        """`pipelex` never looks inside an inline settings table at validation, and resolves its `model`
        through aliases and waterfalls but not presets at run time."""
        section = model_section(target_name)
        assert "**Validation never looks inside an inline table**" in section
        assert "write one only once `mthds_models` answers `resolved`" in section
        assert "The table's own `model` is an alias, a waterfall or a handle, never a preset." in section
        assert 'model = { model = "@default-general", temperature = 0.2 }' in section, (
            f"{target_name}: the inline example must name an alias, never a handle"
        )

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_deck_is_not_the_account(self, target_name: str) -> None:
        """A listed model can still be refused when a run starts: the deck is the runner's, not the account's."""
        assert "**The deck is what the runner can serve, not what the account may use**" in model_section(target_name)

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_an_older_workshop_falls_back_without_a_stop(self, target_name: str) -> None:
        assert "**Without `mthds_models`**, on a workshop older than the release that brought it" in model_section(target_name)

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_edit_points_at_the_section_where_a_model_changes(self, target_name: str) -> None:
        """The read-before-act rule: the pointer sits at the decision point and says to read before acting."""
        body = skill_body(target_name, "pipelex-edit")
        bullet = next(line for line in body.splitlines() if line.startswith("- **Change a model reference**"))
        assert f"]({ANCHOR}) before writing one" in bullet
        assert "`mthds_models`" in bullet
        assert "**`mthds_models`** serves a model change in Step 4, and its absence is no stop" in body
        assert f"]({ANCHOR}): before writing or changing a `model` field." in body.split("## References", 1)[1]

    @pytest.mark.parametrize("skill", ["pipelex-design", "pipelex-edit"])
    def test_the_writing_skills_pre_approve_the_lookup_on_claude(self, skill: str) -> None:
        """A read-only lookup that prompts on its first call is friction in the skills that write models."""
        frontmatter = skill_body("prod", skill).split("\n---\n", 1)[0]
        assert "  - mcp__plugin_pipelex_pipelex__mthds_models" in frontmatter

    @pytest.mark.parametrize(
        "skill", ["pipelex-explain", "pipelex-inputs", "pipelex-run", "pipelex-integrate", "pipelex-organize", "pipelex-catalog"]
    )
    def test_no_other_skill_declares_the_lookup(self, skill: str) -> None:
        """Only design and edit write a `model` field; the other readers of the language reference never call it."""
        assert "mcp__plugin_pipelex_pipelex__mthds_models" not in skill_body("prod", skill)
