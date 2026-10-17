"""A stand-in for the Pipelex API on a loopback port, for the hook's validate stage (the `stub_api` fixture in `conftest.py`).

It also runs `templates/hooks/assets/check.mjs`, the copy every target carries byte for byte, as Claude Code hands the hook
a `Write`, pointed at the stand-in with a placeholder key the stand-in never checks.
"""

from __future__ import annotations

import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, NamedTuple, cast, override

REPO_ROOT = Path(__file__).parents[2]
CHECK_MJS = REPO_ROOT / "templates" / "hooks" / "assets" / "check.mjs"
HOOK_TIMEOUT_SECONDS = 60
# What would reach the real API, or route the request elsewhere: replaced by the stand-in's own.
STRIPPED_PREFIXES = ("PIPELEX_", "CLAUDE_PLUGIN_OPTION_")
PROXY_VARIABLES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy", "NODE_USE_ENV_PROXY")
PLACEHOLDER_KEY = "plx_sk_placeholder_for_the_stub"


class RecordedRequest(NamedTuple):
    """One request the stand-in received: its path and its JSON body. Its headers, the key among them, are not kept."""

    path: str
    body: dict[str, Any]


class StubApiServer(ThreadingHTTPServer):
    """Records every request and answers each with `verdict`, under `status` and `content_type`.

    By default the answer is a produced verdict on a `200`; a test sets `status` and `content_type` to answer a problem
    document instead, as a server does when no verdict could be produced.
    """

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), StubApiHandler)
        self.recorded: list[RecordedRequest] = []
        self.verdict: dict[str, Any] = {"is_valid": True, "pending_signatures": []}
        self.status = 200
        self.content_type = "application/json"

    @property
    def base_url(self) -> str:
        host = str(self.server_address[0])
        port = int(self.server_address[1])
        return f"http://{host}:{port}"


class StubApiHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        server = cast(StubApiServer, self.server)
        length = int(self.headers.get("Content-Length", "0"))
        body: dict[str, Any] = json.loads(self.rfile.read(length) or b"{}")
        server.recorded.append(RecordedRequest(path=self.path, body=body))
        answer = json.dumps(server.verdict).encode("utf-8")
        self.send_response(server.status)
        self.send_header("Content-Type", server.content_type)
        self.send_header("Content-Length", str(len(answer)))
        self.end_headers()
        self.wfile.write(answer)

    @override
    def log_message(self, format: str, *args: Any) -> None:
        """Keep the server's access log out of the test output."""


def hook_environment(*, stub_api: StubApiServer) -> dict[str, str]:
    """The test's environment with the real API's key and base URL, and any proxy, replaced by the stand-in's."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith(STRIPPED_PREFIXES) and key not in PROXY_VARIABLES}
    environment["PIPELEX_API_KEY"] = PLACEHOLDER_KEY
    environment["PIPELEX_BASE_URL"] = stub_api.base_url
    return environment


def run_write_hook(*, node: str, method: Path, stub_api: StubApiServer) -> subprocess.CompletedProcess[str]:
    """One PostToolUse `Write` of `method`, as Claude Code hands it to the hook, which always exits 0."""
    payload = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": str(method)}})
    result = subprocess.run(
        [node, str(CHECK_MJS), "--platform=claude"],
        input=payload,
        capture_output=True,
        text=True,
        env=hook_environment(stub_api=stub_api),
        timeout=HOOK_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, f"the hook exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    return result
