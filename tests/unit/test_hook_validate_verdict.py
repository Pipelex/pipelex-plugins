"""The edit hook's validate stage reads a verdict whose faults are MTHDS problem items.

A runner that speaks the MTHDS problem document answers an invalid bundle with a `200` whose `is_valid` is false and
whose faults are problem items in `errors[]`, each with its own `code`, `detail`, `params` and `location`, where the
older shape carried `validation_errors[]`. A validation that produced no verdict, such as a dry run meeting a model the
deployment does not serve, is no longer an invalid verdict at all: the runner answers it as a non-2xx problem document.
These tests run `templates/hooks/assets/check.mjs`, the copy every target carries byte for byte, as a Claude
`PostToolUse` `Write`, against a stand-in API on a loopback port that answers each of those shapes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.unit.stub_api import StubApiServer, run_write_hook

METHOD_FILE = "greeting.mthds"
GREETING_METHOD = """domain      = "greetings"
description = "Greeting a visitor by name"
main_pipe   = "greet_visitor"

[pipe.greet_visitor]
type        = "PipeLLM"
description = "Writes a one-line greeting for the visitor"
inputs      = { name = "Text" }
output      = "Text"
prompt      = "Write a one-line greeting for $name."
"""
PROBLEM_ITEMS: list[dict[str, Any]] = [
    {
        "code": "method.input_undeclared",
        "detail": "Pipe 'greet_visitor' reads names its inputs do not declare: visitor.",
        "params": {"pipe": "greet_visitor", "variables": ["visitor"]},
        "location": {"pipe": "greet_visitor", "file": METHOD_FILE},
    },
    {
        "code": "method.input_unused",
        "detail": "Pipe 'greet_visitor' declares inputs it never reads: name.",
        "params": {"pipe": "greet_visitor", "variables": ["name"]},
        "location": {"pipe": "greet_visitor", "file": METHOD_FILE},
    },
]
RENDERED_MARKDOWN = (
    "# Validation failed\n\n"
    "1. **A pipe reads an input it does not declare** (`method.input_undeclared`)\n"
    "   - Pipe: `greet_visitor`\n"
    f"   - File: `{METHOD_FILE}`\n"
    "   - Pipe 'greet_visitor' reads names its inputs do not declare: visitor.\n\n"
    "2. **A pipe declares an input it never reads** (`method.input_unused`)\n"
    "   - Pipe: `greet_visitor`\n"
    f"   - File: `{METHOD_FILE}`\n"
    "   - Pipe 'greet_visitor' declares inputs it never reads: name."
)
INVALID_VERDICT: dict[str, Any] = {
    "is_valid": False,
    "errors": PROBLEM_ITEMS,
    "pending_signatures": [],
    "is_runnable": False,
    "message": "The method does not validate.",
}
# What a runner speaking the problem answers when the validation produced no verdict: its problem, on the code's status.
NO_VERDICT_PROBLEM: dict[str, Any] = {
    "type": "https://mthds.ai/errors/model.unavailable",
    "title": "This deployment serves no backend for the model",
    "status": 501,
    "detail": "The llm model 'gpt-unserved' exists, but this deployment does not serve it (reason: not_served).",
    "code": "model.unavailable",
    "domain": "operator",
    "retry": "no",
    "next_step": {"kind": "change_model", "detail": "Use a model this deployment serves in place of 'gpt-unserved'."},
    "params": {"model": "gpt-unserved", "model_type": "llm", "reason": "not_served"},
    "request_id": "req_stand_in",
}


def _write_method(directory: Path) -> Path:
    method = directory / METHOD_FILE
    method.write_text(GREETING_METHOD, encoding="utf-8")
    return method


def _decision(stdout: str) -> dict[str, Any]:
    """The hook's one JSON line on stdout."""
    decision: dict[str, Any] = json.loads(stdout)
    return decision


class TestHookValidateVerdict:
    def test_an_invalid_verdict_blocks_with_the_servers_markdown_verbatim(self, node: str, stub_api: StubApiServer, tmp_path: Path) -> None:
        """The hook asks for the server's Markdown and forwards it whole, so the problem items reach the agent as rendered."""
        stub_api.verdict = {**INVALID_VERDICT, "rendered_markdown": RENDERED_MARKDOWN}
        method = _write_method(tmp_path)

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        assert [request.path for request in stub_api.recorded] == ["/v1/validate"]
        assert "markdown" in stub_api.recorded[0].body["render"], "the hook must ask for the Markdown it forwards"
        assert _decision(result.stdout) == {"decision": "block", "reason": RENDERED_MARKDOWN}

    def test_an_invalid_verdict_without_markdown_still_blocks_with_its_message(self, node: str, stub_api: StubApiServer, tmp_path: Path) -> None:
        """A server that sends no Markdown still gets the edit blocked: the verdict is `is_valid`, never the rendering."""
        stub_api.verdict = INVALID_VERDICT
        method = _write_method(tmp_path)

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        decision = _decision(result.stdout)
        assert decision["decision"] == "block"
        assert decision["reason"].startswith(f"Validation failed for {method}:")
        assert INVALID_VERDICT["message"] in decision["reason"]

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "The vendored check.mjs builds a reason without Markdown from `validation_errors[]` and does not read `errors[]` yet: "
            "its source in pipelex-sdk's js/src/hooks must read the problem items, and the bundle be re-vendored. "
            "The re-vendor that brings the reading turns this test into an unexpected pass, which fails until this marker goes."
        ),
    )
    def test_an_invalid_verdict_without_markdown_names_each_problem_item(self, node: str, stub_api: StubApiServer, tmp_path: Path) -> None:
        """The reason the hook builds itself names every item by its code, its sentence and its pipe."""
        stub_api.verdict = INVALID_VERDICT
        method = _write_method(tmp_path)

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        reason = _decision(result.stdout)["reason"]
        for item in PROBLEM_ITEMS:
            assert item["code"] in reason, f"the reason does not name {item['code']}: {reason}"
            assert item["detail"] in reason, f"the reason does not carry the sentence of {item['code']}: {reason}"
        assert "greet_visitor" in reason

    def test_a_validation_that_produced_no_verdict_passes(self, node: str, stub_api: StubApiServer, tmp_path: Path) -> None:
        """A non-2xx problem document is no verdict, so the validate stage is skipped and the edit passes silently."""
        stub_api.verdict = NO_VERDICT_PROBLEM
        stub_api.status = 501
        stub_api.content_type = "application/problem+json"
        method = _write_method(tmp_path)

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        assert [request.path for request in stub_api.recorded] == ["/v1/validate"]
        assert result.stdout.strip() == "", f"a validation with no verdict must not block, but the hook said: {result.stdout}"
