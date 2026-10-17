"""No shipped skill teaches a field of the error report the MTHDS problem document replaced.

The runtime's error report carried a class name as `error_type`, who must act as `error_domain` and `error_category`,
the next step as `user_action`, and whether its message was meant for the caller as `caller_facing_message`. The
problem document replaces them with `code`, `domain`, `retry`, `next_step`, `location` and its items in `errors`, and
pipelex writes none of them from the release that brings it. The workshop, the Pipelex MCP server the skills read
errors through, still relays them on a failed run's `failure` object while the hosted plane runs an older pipelex,
and drops them when it moves to the problem document, so a skill that came to depend on one would break then.

The workshop's own error contract is not on this list, since it is what the skills read today: a no-verdict
`status: "error"` with `errors[]` entries carrying a `class`, `retryable`, `location`, `hint` and `kind`, an invalid
verdict's `validation_errors[]`, and a failed run's `failure_message` (pipelex-mcp's `SPEC.md`, "Verdicts and
errors"). That contract moves to the problem document with the workshop itself, when the hosted plane and its clients
do (L-261015-4286ad), and the skills that name it move in the same change.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.gen_skill_docs import load_target_config, resolve_output_dir

REPO_ROOT = Path(__file__).parents[2]
TARGETS = ("prod", "codex", "mistral-vibe")
REPLACED_FIELD = re.compile(r"\b(error_type|error_domain|error_category|user_action|caller_facing_message|ErrorReport|UserActionKind)\b")


class TestSkillErrorFields:
    @pytest.mark.parametrize("target_name", TARGETS)
    def test_no_shipped_skill_file_names_a_replaced_error_field(self, target_name: str) -> None:
        """Every file a target ships under `skills/`, references and scripts included, as a user installs it."""
        config = load_target_config(REPO_ROOT / "targets", target_name)
        skills_dir = resolve_output_dir(REPO_ROOT, config.source) / "skills"
        shipped = sorted(path for path in skills_dir.rglob("*") if path.is_file())
        assert shipped, f"{target_name}: no skill files found under {skills_dir}"

        named: list[str] = []
        for path in shipped:
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), 1):
                for match in REPLACED_FIELD.finditer(line):
                    named.append(f"{path.relative_to(skills_dir)}:{line_number} names `{match.group(1)}`")

        assert not named, f"{target_name}: a skill teaches an error field the problem document replaced: " + "; ".join(named)
