"""Pin the shared framing reference: what it holds, that its words belong to no skill, and what the lab keeps of its own."""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

import pytest

from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir

TARGETS = ("prod", "codex", "mistral-vibe")
REPO_ROOT = Path(__file__).parents[2]


class TestFramingReference:
    """The questions that frame a need and what "Right means" means are a shared reference, so that a skill other than
    the lab, an outside target's among them, can frame a need from the same text. That only holds while the text belongs
    to no skill and no harness, so the lab's own uses of the answers stay in its `frame.md`, and the two are held apart
    here in both directions."""

    QUESTIONS: ClassVar[tuple[str, ...]] = (
        "**What arrives?** The documents, images, pages or messages the work starts from, how many at a time, and in what format.",
        "**What gets decided or written?** The output a person produces today: a verdict, a set of fields, a memo, a reply, a ranking.",
        '**Who checks it today, and how?** Whatever a reviewer compares against is what "right" means.',
        "**What does a mistake cost?** A missed clause, a wrong total, a reply sent to the wrong person.",
    )
    RIGHT_MEANS = "the facts a correct output gets right, and the mistakes that cost the most"
    # Each word belongs to one skill's loop or one harness, and none has a meaning here a skill without them could use.
    NOT_NEUTRAL = re.compile(
        r"\b(lab|loop|keys?|scores?|scored|scoring|scorecard|rounds?|budget|candidates?|brief|cases?|tools?|skills?|harness|session"
        r"|claude|codex|vibe|mcp|workshop|mthds_\w+)\b|/pipelex",
        flags=re.IGNORECASE,
    )

    @staticmethod
    def rendered(target_name: str) -> str:
        """The reference as the named target renders it, which is what a skill's link reaches."""
        config = load_target_config(REPO_ROOT / "targets", target_name)
        files = render_templates(REPO_ROOT / "templates", REPO_ROOT, config.template_vars, include_skills=[], target_name=config.name)
        return next(content for path, content in files.items() if path.match("skills/shared/framing.md"))

    @staticmethod
    def frame() -> str:
        return (REPO_ROOT / "skills" / "pipelex-lab" / "references" / "frame.md").read_text(encoding="utf-8")

    def test_it_reads_the_same_on_every_target(self) -> None:
        """It takes no variable, so no target can word it for one harness."""
        assert len({self.rendered(target_name) for target_name in TARGETS}) == 1

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_it_holds_the_questions_and_what_right_means_means(self, target_name: str) -> None:
        body = self.rendered(target_name)
        assert body.split("\n\n")[1].startswith("Read this "), "the reference does not open with its entry condition"
        for question in self.QUESTIONS:
            assert f"- {question}\n" in body
        assert self.RIGHT_MEANS in body.split('## What "Right means" means', 1)[1]

    def test_its_words_belong_to_no_skill_and_no_harness(self) -> None:
        """No lab, no loop that runs and scores, no tool and no slash skill name: an outside target's skill reads this file
        as it is, on a harness that has none of them."""
        found = self.NOT_NEUTRAL.findall(self.rendered("prod"))
        assert not found, f"framing.md names what belongs to one skill or one harness: {found}"

    def test_the_lab_keeps_its_own_uses_of_the_answers_and_none_of_the_questions(self) -> None:
        """The lab says everything it said before the move: `frame.md` keeps what the answers seed and the brief's format,
        and stops restating the questions and what "Right means" means, which would be a second source."""
        frame = self.frame()
        for question in self.QUESTIONS:
            assert question.split("** ", 1)[1] not in frame, f"frame.md restates {question!r}"
        assert self.RIGHT_MEANS not in frame.lower()
        assert "such as the fields it fills" not in frame
        assert "**Who checks it today** is the seed of a key." in frame
        assert "mistakes that cost the most become the traps of a case" in frame
        assert "seed the keys" in frame
        assert "## Candidates" in frame
        assert "ask the shared framing reference's last two questions" in frame
        assert "the shared framing reference" in frame
        assert "The lab reads both beside this one." in frame

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_target_ships_it_in_its_shared_files(self, target_name: str) -> None:
        config = load_target_config(REPO_ROOT / "targets", target_name)
        installed = resolve_output_dir(REPO_ROOT, config.source) / "skills" / "shared" / "framing.md"
        assert installed.read_text(encoding="utf-8") == self.rendered(target_name)
