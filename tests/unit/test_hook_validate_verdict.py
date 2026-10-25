"""The edit hook's validate stage reads a verdict whose faults are MTHDS problem items.

A runner that speaks the MTHDS problem document answers an invalid bundle with a `200` whose `is_valid` is false and
whose faults are problem items in `errors[]`, each with its own `code`, `detail`, `params` and `location`, where the
older shape carried `validation_errors[]`. A validation that produced no verdict, such as a dry run meeting a model the
deployment does not serve, is no longer an invalid verdict at all: the runner answers it as a non-2xx problem document.
These tests run `templates/hooks/assets/check.mjs`, the copy every target carries byte for byte, as a Claude
`PostToolUse` `Write`, against a stand-in API on a loopback port that answers each of those shapes, after the version
handshake the client asks before it sends the method's tree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
PIPE_CODE = "greet_visitor"
# Each item's sentence names neither its pipe nor its file, so only the item's `location` can put them in a reason.
PROBLEM_ITEMS: list[dict[str, Any]] = [
    {
        "code": "method.input_undeclared",
        "detail": "The prompt reads a variable the inputs do not declare: visitor.",
        "params": {"pipe": PIPE_CODE, "variables": ["visitor"]},
        "location": {"pipe": PIPE_CODE, "file": METHOD_FILE},
        "suggested_fix": {
            "fix_code": "declare-input",
            "description": "Declare visitor among the inputs.",
            "safety": "safe",
            "ops": [{"kind": "set_key", "table_path": ["pipe", PIPE_CODE, "inputs"], "key": "visitor", "value": "Text"}],
        },
    },
    {
        "code": "method.input_unused",
        "detail": "An input is declared that the prompt never reads: name.",
        "params": {"pipe": PIPE_CODE, "variables": ["name"]},
        "location": {"pipe": PIPE_CODE, "file": METHOD_FILE},
        "suggested_fix": {
            "fix_code": "remove-unused-input",
            "description": "Remove name from the inputs.",
            "safety": "unsafe",
            "ops": [{"kind": "delete_key", "table_path": ["pipe", PIPE_CODE, "inputs"], "key": "name"}],
        },
    },
]
# The lines the bundle gives those items when the server sends no Markdown: each item's code, its sentence and its
# location as the `mthds` package's `formatLocation` words it, then its suggested fix as `formatSuggestedFix` words it.
PROBLEM_ITEM_LINES = [
    f"- `method.input_undeclared`: The prompt reads a variable the inputs do not declare: visitor. (pipe '{PIPE_CODE}', file '{METHOD_FILE}')",
    "  - Suggested fix (safe, declare-input): Declare visitor among the inputs.",
    f"- `method.input_unused`: An input is declared that the prompt never reads: name. (pipe '{PIPE_CODE}', file '{METHOD_FILE}')",
    "  - Suggested fix (unsafe, remove-unused-input): Remove name from the inputs.",
]
RENDERED_MARKDOWN = (
    "# Validation failed\n\n"
    "1. **A pipe reads an input it does not declare** (`method.input_undeclared`)\n"
    f"   - Pipe: `{PIPE_CODE}`\n"
    f"   - File: `{METHOD_FILE}`\n"
    "   - The prompt reads a variable the inputs do not declare: visitor.\n\n"
    "2. **A pipe declares an input it never reads** (`method.input_unused`)\n"
    f"   - Pipe: `{PIPE_CODE}`\n"
    f"   - File: `{METHOD_FILE}`\n"
    "   - An input is declared that the prompt never reads: name."
)
VERDICT_MESSAGE = "The method does not validate."
INVALID_VERDICT: dict[str, Any] = {
    "is_valid": False,
    "errors": PROBLEM_ITEMS,
    "pending_signatures": [],
    "is_runnable": False,
    "message": VERDICT_MESSAGE,
}
# Entries the bundle cannot read whole, beside one it can: a code that is not a string, an entry with no sentence, and
# entries whose `suggested_fix` or `location` is not of the shape the bundle reads.
UNREADABLE_ENTRIES: list[Any] = [
    {"code": 1, "detail": "A code that is not a string."},
    {"code": "method.input_unused", "params": {"pipe": PIPE_CODE}},
    "an entry that is not an object",
    {"code": "method.input_unused", "detail": "An input is declared that the prompt never reads: name.", "suggested_fix": "Remove the input."},
    {
        "code": "method.input_undeclared",
        "detail": "The prompt reads a variable the inputs do not declare: visitor.",
        "location": f"{METHOD_FILE}, line 9",
        "suggested_fix": {"fix_code": "declare-input"},
    },
]
# Of those, the bundle keeps the last two, each without the member it cannot read, and skips the rest.
READABLE_ENTRY_LINES = [
    "- `method.input_unused`: An input is declared that the prompt never reads: name.",
    "- `method.input_undeclared`: The prompt reads a variable the inputs do not declare: visitor.",
]
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

        assert stub_api.routes == ["GET /v1/version", "POST /v1/validate"]
        assert "markdown" in stub_api.recorded[1].body["render"], "the hook must ask for the Markdown it forwards"
        assert _decision(result.stdout) == {"decision": "block", "reason": RENDERED_MARKDOWN}

    def test_an_invalid_verdict_without_markdown_still_blocks_with_its_message(self, node: str, stub_api: StubApiServer, tmp_path: Path) -> None:
        """A server that sends no Markdown still gets the edit blocked: the verdict is `is_valid`, never the rendering."""
        stub_api.verdict = INVALID_VERDICT
        method = _write_method(tmp_path)

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        decision = _decision(result.stdout)
        assert decision["decision"] == "block"
        assert decision["reason"].startswith(f"Validation failed for {method}:")
        assert VERDICT_MESSAGE in decision["reason"]

    def test_an_invalid_verdict_without_markdown_names_each_problem_item(self, node: str, stub_api: StubApiServer, tmp_path: Path) -> None:
        """The reason the hook builds itself gives every item its code, its sentence, its pipe and its file, with its
        suggested fix on the line beneath."""
        for item in PROBLEM_ITEMS:
            assert PIPE_CODE not in item["detail"], "an item's sentence must not name its pipe, or the test cannot see the location"
            assert METHOD_FILE not in item["detail"], "an item's sentence must not name its file, or the test cannot see the location"
        stub_api.verdict = INVALID_VERDICT
        method = _write_method(tmp_path)

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        decision = _decision(result.stdout)
        assert decision["decision"] == "block"
        assert decision["reason"] == "\n".join([f"Validation failed for {method}:", "", VERDICT_MESSAGE, "", *PROBLEM_ITEM_LINES])

    def test_an_entry_the_hook_cannot_read_is_skipped_and_a_member_it_cannot_read_left_out(
        self, node: str, stub_api: StubApiServer, tmp_path: Path
    ) -> None:
        """An entry with no string code or sentence is skipped; a `location` or `suggested_fix` of another shape is left
        out of its item, which still blocks the edit."""
        stub_api.verdict = {**INVALID_VERDICT, "errors": UNREADABLE_ENTRIES}
        method = _write_method(tmp_path)

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        assert stub_api.routes == ["GET /v1/version", "POST /v1/validate"]
        decision = _decision(result.stdout)
        assert decision["decision"] == "block"
        assert decision["reason"] == "\n".join([f"Validation failed for {method}:", "", VERDICT_MESSAGE, "", *READABLE_ENTRY_LINES])

    def test_a_validation_that_produced_no_verdict_passes(self, node: str, stub_api: StubApiServer, tmp_path: Path) -> None:
        """A non-2xx problem document is no verdict, so the validate stage is skipped and the edit passes silently."""
        stub_api.verdict = NO_VERDICT_PROBLEM
        stub_api.status = 501
        stub_api.content_type = "application/problem+json"
        method = _write_method(tmp_path)

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        assert stub_api.routes == ["GET /v1/version", "POST /v1/validate"]
        assert result.stdout.strip() == "", f"a validation with no verdict must not block, but the hook said: {result.stdout}"
