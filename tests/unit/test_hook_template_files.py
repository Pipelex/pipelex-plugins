"""The edit hook's validate stage sends the template files a bundle's `PipeDocGen` steps name.

The hosted API loads a bundle sent as content only with the template files its `PipeDocGen` steps
name, sent beside its `.mthds` files as the request's `resources`, so a hook that sent the `.mthds`
files alone would block every edit of a templated bundle on a file the API was never given. These
tests run `templates/hooks/assets/check.mjs`, the copy every target carries byte for byte, as a
Claude `PostToolUse` `Write`, against a stand-in API on a loopback port (`stub_api` in
`conftest.py`), and read what the validate stage sent. The key they give the hook is a placeholder
the stand-in never checks.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.unit.stub_api import StubApiServer

REPO_ROOT = Path(__file__).parents[2]
CHECK_MJS = REPO_ROOT / "templates" / "hooks" / "assets" / "check.mjs"
HOOK_TIMEOUT_SECONDS = 60
# What would reach the real API, or route the request elsewhere: replaced by the stand-in's own.
STRIPPED_PREFIXES = ("PIPELEX_", "CLAUDE_PLUGIN_OPTION_")
PROXY_VARIABLES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy", "NODE_USE_ENV_PROXY")
PLACEHOLDER_KEY = "plx_sk_placeholder_for_the_stub"

TEMPLATE_FILE = "templates/notice.html"
TEMPLATE_HTML = "<h1>$notice.shop_name</h1>\n<p>Weekdays: $notice.weekdays</p>\n<p>Weekend: $notice.weekend</p>\n"
NOTICE_METHOD = f"""domain      = "shop_notices"
description = "Printing the notice a shop tapes to its door"
main_pipe   = "print_notice"

[concept.OpeningNotice]
description = "What a shop wants passers-by to know about its opening hours"

[concept.OpeningNotice.structure]
shop_name = {{ type = "text", description = "The name painted above the shop's door", required = true }}
weekdays  = {{ type = "text", description = "The opening hours from Monday to Friday", required = true }}
weekend   = {{ type = "text", description = "The opening hours on Saturday and Sunday", required = true }}

[concept.PrintedNotice]
description = "The notice laid out as a page to print and tape to the door"
refines     = "Document"

[pipe.print_notice]
type          = "PipeDocGen"
description   = "Prints the opening hours from the shop's template"
inputs        = {{ notice = "OpeningNotice" }}
output        = "PrintedNotice"
format        = "pdf"
template_file = "{TEMPLATE_FILE}"
"""
# A second file whose step names the same path, for a bundle where that path could name two files.
BACK_DOOR_METHOD = (
    NOTICE_METHOD.replace('domain      = "shop_notices"', 'domain      = "shop_back_door"')
    .replace('main_pipe   = "print_notice"', 'main_pipe   = "print_back_notice"')
    .replace("[pipe.print_notice]", "[pipe.print_back_notice]")
)
INVALID_VERDICT: dict[str, Any] = {
    "is_valid": False,
    "message": "The stand-in refuses every bundle it is sent",
    "validation_errors": [{"category": "stub", "message": "refused by the stand-in"}],
    "rendered_markdown": "# Validation failed\n\nRefused by the stand-in.",
}


def _hook_environment(stub_api: StubApiServer) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.startswith(STRIPPED_PREFIXES) and key not in PROXY_VARIABLES}
    environment["PIPELEX_API_KEY"] = PLACEHOLDER_KEY
    environment["PIPELEX_BASE_URL"] = stub_api.base_url
    return environment


def _run_hook(*, node: str, method: Path, stub_api: StubApiServer) -> subprocess.CompletedProcess[str]:
    """One PostToolUse `Write` of `method`, as Claude Code hands it to the hook."""
    payload = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": str(method)}})
    result = subprocess.run(
        [node, str(CHECK_MJS), "--platform=claude"],
        input=payload,
        capture_output=True,
        text=True,
        env=_hook_environment(stub_api),
        timeout=HOOK_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, f"the hook exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    return result


def _write_bundle(bundle: Path) -> Path:
    """The notice bundle with its template beside it, and the graph page a validation leaves there, which no step names."""
    (bundle / "templates").mkdir(parents=True)
    method = bundle / "notice.mthds"
    method.write_text(NOTICE_METHOD, encoding="utf-8")
    (bundle / TEMPLATE_FILE).write_text(TEMPLATE_HTML, encoding="utf-8")
    (bundle / "method-graph.html").write_text("<html><body>the graph page</body></html>\n", encoding="utf-8")
    return method


def _link_the_template_out_of_the_bundle(bundle: Path, elsewhere: Path) -> None:
    """The step's template is a link to a file outside the bundle's directory, which the hook never reads."""
    outside = elsewhere / "notice.html"
    elsewhere.mkdir()
    outside.write_text(TEMPLATE_HTML, encoding="utf-8")
    (bundle / TEMPLATE_FILE).unlink()
    (bundle / TEMPLATE_FILE).symlink_to(outside)


def _name_a_second_file_by_the_same_path(bundle: Path, elsewhere: Path) -> None:
    """A second `.mthds` file in a subdirectory names the same path, which leads there to a different file."""
    back_door = bundle / "back-door"
    (back_door / "templates").mkdir(parents=True)
    (back_door / "back-door.mthds").write_text(BACK_DOOR_METHOD, encoding="utf-8")
    (back_door / TEMPLATE_FILE).write_text(TEMPLATE_HTML.replace("Weekdays", "Back door, weekdays"), encoding="utf-8")


class TestHookTemplateFiles:
    def test_a_template_file_beside_the_bundle_is_sent_under_the_path_its_step_names(
        self, node: str, stub_api: StubApiServer, tmp_path: Path
    ) -> None:
        """The template goes out as `resources`, keyed by the step's `template_file`, and a file no step names stays home."""
        method = _write_bundle(tmp_path / "bundle")

        result = _run_hook(node=node, method=method, stub_api=stub_api)

        assert result.stdout.strip() == "", f"a valid verdict passes silently, but the hook said: {result.stdout}"
        assert [request.path for request in stub_api.recorded] == ["/v1/validate"]
        body = stub_api.recorded[0].body
        assert body["mthds_contents"] == [method.read_text(encoding="utf-8")]
        assert body["resources"] == {TEMPLATE_FILE: base64.b64encode(TEMPLATE_HTML.encode("utf-8")).decode("ascii")}

    @pytest.mark.parametrize("arrange", [_link_the_template_out_of_the_bundle, _name_a_second_file_by_the_same_path], ids=["link-out", "two-files"])
    def test_a_template_the_request_cannot_carry_passes_the_validation_stage_silently(
        self, node: str, stub_api: StubApiServer, tmp_path: Path, arrange: Callable[[Path, Path], None]
    ) -> None:
        """No request leaves, so a stand-in that refuses every bundle never gets to block the edit."""
        stub_api.verdict = INVALID_VERDICT
        bundle = tmp_path / "bundle"
        method = _write_bundle(bundle)
        arrange(bundle, tmp_path / "elsewhere")

        result = _run_hook(node=node, method=method, stub_api=stub_api)

        assert stub_api.recorded == [], f"the hook sent a request it could not make whole: {[request.path for request in stub_api.recorded]}"
        assert result.stdout.strip() == "", f"the validation stage should pass silently, but the hook said: {result.stdout}"
