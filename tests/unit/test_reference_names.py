"""Pin how a static reference's skill name reaches the user on Mistral Vibe."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.gen_skill_docs import load_target_config, resolve_output_dir

TARGETS = ("prod", "codex", "mistral-vibe")
REPO_ROOT = Path(__file__).parents[2]

# The skills whose references route the user to another skill, each with one such hand-off.
ROUTING_REFERENCES = {
    "pipelex-run": ("failed-run.md", "| `/pipelex-edit` |"),
    "pipelex-design": ("stepwise.md", "offer `/pipelex-organize`"),
    "pipelex-lab": ("frame.md", "which `/pipelex-scaffold` makes"),
}

# The lines of scaffold's and integrate's references that reach the user. The size ceiling leaves those
# skills no room for the sentence, so each line names its skill in words and leaves the spelling to the
# skill's own hand-offs, which carry the prefix.
IN_WORDS = {
    ("pipelex-scaffold", "version-managers.md"): "before the skill the usual hand-off names can run",
    ("pipelex-scaffold", "initializers.md"): "when you hand a minimal TypeScript project to the integrate skill",
    ("pipelex-integrate", "python.md"): "naming that skill to the user the way this skill's own hand-offs name a sibling",
}


class TestReferenceNames:
    """The references under `skills/` are copied verbatim, so they name a sibling skill by its bare
    `/pipelex-<name>`. Vibe resolves only `/pipelex:pipelex-<name>`, so the skills whose references
    route the user carry, on Vibe alone, the sentence that has the agent rewrite the name."""

    @staticmethod
    def shipped(target_name: str, skill: str) -> str:
        config = load_target_config(REPO_ROOT / "targets", target_name)
        return (resolve_output_dir(REPO_ROOT, config.source) / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")

    @pytest.mark.parametrize("skill", sorted(ROUTING_REFERENCES))
    def test_each_reference_still_routes_by_the_bare_name(self, skill: str) -> None:
        """The sentence is warranted only while the reference hands the user a bare name."""
        reference, hand_off = ROUTING_REFERENCES[skill]
        assert hand_off in (REPO_ROOT / "skills" / skill / "references" / reference).read_text(encoding="utf-8")

    @pytest.mark.parametrize("target_name", TARGETS)
    @pytest.mark.parametrize("skill", sorted(ROUTING_REFERENCES))
    def test_vibe_alone_rewrites_the_name_before_the_references(self, target_name: str, skill: str) -> None:
        config = load_target_config(REPO_ROOT / "targets", target_name)
        sentence = (
            f"These references name a skill by its bare `/pipelex-<name>`; to the user, write it "
            f"`{config.template_vars['skill_prefix']}pipelex-<name>`, the only name Mistral Vibe resolves."
        )
        body = self.shipped(target_name, skill)
        if config.template_vars["platform"] == "mistral-vibe":
            assert f"## References\n\n{sentence}\n\n- [" in body
            assert config.template_vars["skill_prefix"] == "/pipelex:"
        else:
            assert "These references name a skill" not in body
            assert "## References\n\n- [" in body

    @pytest.mark.parametrize(("skill", "reference"), sorted(IN_WORDS))
    def test_a_line_reaching_the_user_without_the_sentence_names_no_bare_skill(self, skill: str, reference: str) -> None:
        lines = (REPO_ROOT / "skills" / skill / "references" / reference).read_text(encoding="utf-8").splitlines()
        line = next((line for line in lines if IN_WORDS[(skill, reference)] in line), None)
        assert line is not None, f"{skill}/{reference}: the hand-off names its skill in words"
        assert "`/pipelex-" not in line, f"{skill}/{reference}: Mistral Vibe resolves no bare `/pipelex-<name>`"
