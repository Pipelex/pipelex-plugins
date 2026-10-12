"""A stand-in for the Pipelex API on a loopback port, for the hook's validate stage (the `stub_api` fixture in `conftest.py`)."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, NamedTuple, cast, override


class RecordedRequest(NamedTuple):
    """One request the stand-in received: its path and its JSON body. Its headers, the key among them, are not kept."""

    path: str
    body: dict[str, Any]


class StubApiServer(ThreadingHTTPServer):
    """Records every request and answers each with `verdict`, a produced verdict on a `200`."""

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), StubApiHandler)
        self.recorded: list[RecordedRequest] = []
        self.verdict: dict[str, Any] = {"is_valid": True, "pending_signatures": []}

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
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(answer)))
        self.end_headers()
        self.wfile.write(answer)

    @override
    def log_message(self, format: str, *args: Any) -> None:
        """Keep the server's access log out of the test output."""
