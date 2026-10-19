"""The edit hook's verdict on a `PipeFunc`'s `function_name`, held by the vendored engine's schema.

A `PipeFunc` names its function by its Python import path from the root of the method's tree, such as
`funcs.text_utils.capitalize`, and the MTHDS JSON Schema frozen into the vendored `check.mjs` holds
`function_name` to that form from `@pipelex/tools-wasm` 0.6.0 on: at least one dot, and no empty
segment. The MTHDS Test Corpus has no `PipeFunc` entry and leaves the step to a consumer's own fixtures
(`tests/data/mthds-corpus/vocabulary.toml`), so the corpus sweep cannot see this rule, and a re-vendor
onto an engine that dropped it, or that began refusing an import path, would pass every other test.
These tests run `templates/hooks/assets/check.mjs`, the copy every target carries byte for byte, as a
Claude `PostToolUse` `Write` on a copy of the method in a temporary directory, since the format stage
writes back in place, and with the Pipelex credentials stripped, so the validate stage never runs.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, NamedTuple

import pytest

REPO_ROOT = Path(__file__).parents[2]
CHECK_MJS = REPO_ROOT / "templates" / "hooks" / "assets" / "check.mjs"
HOOK_TIMEOUT_SECONDS = 60
# What reaches the validate stage, and so the network: removed so that only the offline stages run.
CREDENTIAL_PREFIXES = ("PIPELEX_", "CLAUDE_PLUGIN_OPTION_")
# The category the lint renders a schema diagnostic under, and where it places this one.
SCHEMA_DIAGNOSTIC = "[schema/"
FUNCTION_NAME_PATH = "pipe.capitalize_text.function_name"

PIPE_FUNC_METHOD = """domain      = "text_tools"
description = "Uppercasing a text"
main_pipe   = "capitalize_text"

[pipe.capitalize_text]
type          = "PipeFunc"
description   = "Uppercase the input text"
inputs        = {{ text = "Text" }}
output        = "Text"
function_name = "{function_name}"
"""

# A bare name, the retired registry's key, and every place an empty segment can sit.
REFUSED_NAMES = ("capitalize", "funcs..capitalize", "funcs.", ".funcs")
# An import path from the tree's root, a module beside the root bundle and one in a subdirectory.
IMPORT_PATHS = ("text_utils.capitalize", "funcs.text_utils.capitalize")


class HookVerdict(NamedTuple):
    blocked: bool
    reason: str
    stdout: str
    stderr: str


@pytest.fixture(scope="module")
def offline_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if not key.startswith(CREDENTIAL_PREFIXES)}


def run_hook(*, node: str, function_name: str, directory: Path, environment: dict[str, str]) -> HookVerdict:
    """One PostToolUse `Write` of a method whose one `PipeFunc` names `function_name`."""
    method = directory / "text_tools.mthds"
    method.write_text(PIPE_FUNC_METHOD.format(function_name=function_name), encoding="utf-8")
    payload = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": str(method)}})
    result = subprocess.run(
        [node, str(CHECK_MJS), "--platform=claude"],
        input=payload,
        capture_output=True,
        text=True,
        env=environment,
        timeout=HOOK_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, f"{function_name}: the hook exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    blocked = False
    reason = ""
    if result.stdout.strip():
        decision: dict[str, Any] = json.loads(result.stdout)
        blocked = decision.get("decision") == "block"
        reason = str(decision.get("reason", ""))
    return HookVerdict(blocked=blocked, reason=reason, stdout=result.stdout, stderr=result.stderr)


class TestHookPipeFuncFunctionName:
    @pytest.mark.parametrize("function_name", REFUSED_NAMES)
    def test_the_hook_blocks_a_name_that_is_not_an_import_path(
        self, function_name: str, node: str, offline_environment: dict[str, str], tmp_path: Path
    ) -> None:
        """A bare name or an empty segment blocks offline, with the schema diagnostic placed on `function_name`."""
        verdict = run_hook(node=node, function_name=function_name, directory=tmp_path, environment=offline_environment)
        assert verdict.blocked, f"{function_name!r} is not an import path, but the hook did not block it: {verdict.stdout or 'pass'}"
        diagnostics = [line for line in verdict.reason.splitlines() if SCHEMA_DIAGNOSTIC in line and FUNCTION_NAME_PATH in line]
        assert diagnostics, f"the hook blocked {function_name!r} without a schema diagnostic on {FUNCTION_NAME_PATH}: {verdict.reason}"

    @pytest.mark.parametrize("function_name", IMPORT_PATHS)
    def test_the_hook_passes_an_import_path_silently(
        self, function_name: str, node: str, offline_environment: dict[str, str], tmp_path: Path
    ) -> None:
        verdict = run_hook(node=node, function_name=function_name, directory=tmp_path, environment=offline_environment)
        assert not (verdict.stdout.strip() or verdict.stderr.strip()), (
            f"{function_name!r} is an import path, but the hook did not pass it silently: {verdict.reason or verdict.stdout} {verdict.stderr}"
        )
