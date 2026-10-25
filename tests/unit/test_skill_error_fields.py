"""No shipped skill teaches an error field nobody sends any more.

Two error vocabularies are retired, both by the MTHDS problem document. The runtime's error report carried a class name
as `error_type`, who must act as `error_domain` and `error_category`, the next step as `user_action`, and whether its
message was meant for the caller as `caller_facing_message`; pipelex writes none of them from the release that brings the
problem document. The workshop, the Pipelex MCP server the skills read errors through, had a contract of its own: a
no-verdict `status: "error"` whose `errors[]` entries carried a `class` (`input_domain`, `config`, `runtime`), a
`retryable` flag, a free-string `location`, a `hint` and a `kind` tag (`kind: "auth"`, `kind: "role"`), an invalid
verdict's `validation_errors[]`, a failed run's `failure` object and `failure_message`, a template check's
`template_check_warning`, and the platform's old codes `method_not_published` and `method_version_not_found`.

The workshop now answers a no-verdict call with one `problem`, the caller's view of the problem document (`code`,
`domain`, `retry`, `next_step`, `params`, a structured `location`, `errors` items, `request_id`), a verdict's faults as
`errors[]`, and a failed run's problem as `run_error`, or `error` on the status tool (pipelex-mcp's `SPEC.md`, "Verdicts
and errors"). A skill still naming an old field would branch on something that never arrives.

`validation_errors` is the one old name the workshop keeps: `mthds_save_method` and `mthds_publish_method` still carry
their verdict's faults under it, as problem items. So it is allowed in `pipelex-catalog`, the skill that reads those
two tools' verdicts, and refused everywhere else.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.gen_skill_docs import load_target_config, resolve_output_dir

REPO_ROOT = Path(__file__).parents[2]
TARGETS = ("prod", "codex", "mistral-vibe")
RUNTIME_REPORT_FIELD = re.compile(r"\b(error_type|error_domain|error_category|user_action|caller_facing_message|ErrorReport|UserActionKind)\b")
WORKSHOP_RETIRED_FIELD = re.compile(
    r"\b(input_domain|retryable|failure_message|template_check_warning|method_not_published|method_version_not_found)\b"
    r"|`hint`|\bhint verbatim\b|`failure`"
    r"|class `(?:config|runtime)`|error of class|`config`|kind: \"(?:auth|role)\""
)
SAVE_AND_PUBLISH_FIELD = re.compile(r"\bvalidation_errors\b")
SAVE_AND_PUBLISH_SKILL = "pipelex-catalog"


class TestSkillErrorFields:
    @pytest.mark.parametrize("target_name", TARGETS)
    def test_no_shipped_skill_file_names_a_retired_error_field(self, target_name: str) -> None:
        """Every file a target ships under `skills/`, references and scripts included, as a user installs it."""
        config = load_target_config(REPO_ROOT / "targets", target_name)
        skills_dir = resolve_output_dir(REPO_ROOT, config.source) / "skills"
        shipped = sorted(path for path in skills_dir.rglob("*") if path.is_file())
        assert shipped, f"{target_name}: no skill files found under {skills_dir}"

        named: list[str] = []
        for path in shipped:
            relative = path.relative_to(skills_dir)
            patterns = [RUNTIME_REPORT_FIELD, WORKSHOP_RETIRED_FIELD]
            if relative.parts[0] != SAVE_AND_PUBLISH_SKILL:
                patterns.append(SAVE_AND_PUBLISH_FIELD)
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), 1):
                for pattern in patterns:
                    for match in pattern.finditer(line):
                        named.append(f"{relative}:{line_number} names `{match.group(0)}`")

        assert not named, f"{target_name}: a skill teaches an error field nobody sends any more: " + "; ".join(named)

    @pytest.mark.parametrize(
        "line",
        [
            '| `status: "error"`, class `input_domain` | fix the call |',
            "surface the error's `hint` verbatim",
            "Give `failure_message` **verbatim** first",
            "a `config`-class error included",
            'as a `config` error tagged `kind: "role"`',
            "only if `retryable: true`",
            '| `status: "error"`, class `runtime` | report it |',
            "refused as `method_not_published`",
            "before acting on a `template_check_warning`",
        ],
    )
    def test_the_workshop_pattern_refuses_its_old_contract(self, line: str) -> None:
        assert WORKSHOP_RETIRED_FIELD.search(line), f"the guard lets an old workshop field through: {line}"

    @pytest.mark.parametrize(
        "line",
        [
            '| `status: "error"`, `domain: "input"` | fix the call |',
            "relay its `next_step` verbatim",
            "Give the run's `run_error` **verbatim** first",
            "on the summary's `retry_after_seconds` hint",
            "a problem in the `account` domain included",
            "refused as `pipelex.catalog.not_published`",
            "before acting on a `pipelex.docgen.template_warning`",
        ],
    )
    def test_the_workshop_pattern_lets_the_problem_document_through(self, line: str) -> None:
        assert not WORKSHOP_RETIRED_FIELD.search(line), f"the guard refuses a field the workshop sends: {line}"
