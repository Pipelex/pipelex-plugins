"""The Claude plugin's workshop launcher, `hooks/launch-pipelex-mcp.mjs`, started as the manifest says.

The manifest spawns `node <root>/hooks/launch-pipelex-mcp.mjs` with no shell, and the launcher spawns `npx -y
@pipelex/mcp@latest`: by name on macOS and Linux, and on Windows through npm's `npx-cli.js` beside the Node binary, or
through the shell when that file is absent. The hermetic tests run the launcher on a copy of the Node binary whose
directory holds a stand-in `npx-cli.js`, with a stand-in `npx` first on the `PATH`, so each test sees which way the
launcher went. The last tests start the real workshop from npm and the real Claude Code CLI.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple, cast

import pytest

from tests.unit.claude_plugin import clean_environment, copy_built_plugin, mcp_server_command

IS_WINDOWS = sys.platform == "win32"
LAUNCHER_TIMEOUT_SECONDS = 60
# The first `npx` start of the workshop fills the npm cache, which takes a while on a cold runner.
WORKSHOP_TIMEOUT_SECONDS = 300
SHIPPED_ARGS = ["-y", "@pipelex/mcp@latest"]
# Set by the Windows job, which installs the Claude Code CLI: there a missing `claude` is a failure, never a skip.
REQUIRE_CLAUDE_CLI = "PIPELEX_PLUGINS_REQUIRE_CLAUDE_CLI"

# Stands in for the workshop, behind `npx-cli.js` and behind the `npx` on the PATH alike: it says which way it was
# reached, what it was given and which key it sees, echoes its stdin upper-cased, and exits with FAKE_EXIT.
FAKE_WORKSHOP = """\
const report = {
  via: process.env.FAKE_VIA ?? "npx-cli",
  argv: process.argv.slice(2),
  apiKey: process.env.PIPELEX_API_KEY ?? null,
};
process.stdout.write(JSON.stringify(report) + "\\n");
let received = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  received += chunk;
});
process.stdin.on("end", () => {
  process.stdout.write(received.toUpperCase());
  process.exitCode = Number(process.env.FAKE_EXIT ?? "0");
});
"""


class NodeHome(NamedTuple):
    """A copy of the Node binary, the directory it sits in, and a directory holding a stand-in `npx` for the PATH."""

    node: Path
    path_bin: Path


class LauncherRun(NamedTuple):
    report: dict[str, Any]
    echoed: str
    returncode: int
    stderr: str


def _node_home(base: Path, *, node: str, with_npm: bool) -> NodeHome:
    """Lay out a Node home under `base`: the binary copied, `node_modules/npm/bin/npx-cli.js` beside it when `with_npm`.

    The binary is copied, never linked, because Node reports its own path with links resolved, and the launcher looks for
    npm beside that path.
    """
    home = base / "node home"
    home.mkdir(parents=True)
    copied = home / Path(node).name
    shutil.copy2(node, copied)
    fake_workshop = base / "fake-workshop.mjs"
    fake_workshop.write_text(FAKE_WORKSHOP, encoding="utf-8")
    if with_npm:
        npx_cli = home / "node_modules" / "npm" / "bin" / "npx-cli.js"
        npx_cli.parent.mkdir(parents=True)
        npx_cli.write_text(FAKE_WORKSHOP, encoding="utf-8")
    path_bin = base / "path bin"
    path_bin.mkdir()
    if IS_WINDOWS:
        (path_bin / "npx.cmd").write_text(f'@set FAKE_VIA=path\r\n@"{node}" "{fake_workshop}" %*\r\n', encoding="utf-8", newline="")
    else:
        stand_in = path_bin / "npx"
        stand_in.write_text(f'#!/bin/sh\nFAKE_VIA=path exec "{node}" "{fake_workshop}" "$@"\n', encoding="utf-8")
        stand_in.chmod(0o755)
    return NodeHome(node=copied, path_bin=path_bin)


@pytest.fixture(scope="session")
def node_home(tmp_path_factory: pytest.TempPathFactory, node: str) -> NodeHome:
    return _node_home(tmp_path_factory.mktemp("node-home"), node=node, with_npm=True)


@pytest.fixture
def plugin_root(tmp_path: Path) -> Path:
    return copy_built_plugin(tmp_path)


def _launcher(plugin_root: Path) -> Path:
    """The launcher's path, taken from the manifest's command line, which must be `node <launcher>`."""
    command = mcp_server_command(plugin_root)
    assert command[0] == "node" and len(command) == 2, f"the manifest does not start the workshop as `node <launcher>`: {command}"
    return Path(command[1])


def _run_launcher(plugin_root: Path, home: NodeHome, *, stdin: str = "hello\n", **environment: str) -> LauncherRun:
    path = f"{home.path_bin}{os.pathsep}{os.environ.get('PATH', '')}"
    completed = subprocess.run(
        [str(home.node), str(_launcher(plugin_root))],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=plugin_root.parent,
        env=clean_environment(PATH=path, **environment),
        timeout=LAUNCHER_TIMEOUT_SECONDS,
        check=False,
    )
    first_line, _, echoed = completed.stdout.partition("\n")
    assert first_line, f"the workshop never started (exit {completed.returncode}): {completed.stderr}"
    return LauncherRun(report=json.loads(first_line), echoed=echoed, returncode=completed.returncode, stderr=completed.stderr)


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class _LineReader:
    """Reads a process's stdout on a thread, so a test can wait for a line with a timeout on every OS."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self.lines: queue.Queue[str | None] = queue.Queue()
        assert process.stdout is not None
        stdout = process.stdout

        def pump() -> None:
            for line in stdout:
                self.lines.put(line)
            self.lines.put(None)

        threading.Thread(target=pump, daemon=True).start()

    def response(self, request_id: int, *, timeout: float) -> dict[str, Any]:
        """The JSON-RPC response to `request_id`, skipping notifications and any other line."""
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            assert remaining > 0, f"no response to request {request_id} within {timeout} s"
            line = self.lines.get(timeout=remaining)
            assert line is not None, f"the workshop closed its stdout before answering request {request_id}"
            try:
                message: object = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
            response = cast("dict[str, Any]", message)
            if response.get("id") == request_id:
                return response


@pytest.fixture
def workshop(plugin_root: Path, node: str) -> Iterator[tuple[subprocess.Popen[str], _LineReader]]:
    """The real workshop from npm, started exactly as the manifest's command line says, with the option left unfilled."""
    assert node
    project = plugin_root.parent.parent / "a project"
    project.mkdir()
    process = subprocess.Popen(
        mcp_server_command(plugin_root),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        cwd=project,
        env=clean_environment(PIPELEX_PLUGIN_API_KEY=""),
    )
    try:
        yield process, _LineReader(process)
    finally:
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _send(process: subprocess.Popen[str], message: dict[str, Any]) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(message) + "\n")
    process.stdin.flush()


class TestMcpLauncher:
    @pytest.mark.cross_os
    def test_it_starts_npx_the_way_the_os_needs_and_inherits_stdio(self, plugin_root: Path, node_home: NodeHome) -> None:
        """macOS and Linux spawn `npx` from the PATH, never npm's script beside the Node binary, which Homebrew and nvm
        lay out differently; Windows runs that script with the same Node, since `npx.cmd` cannot be spawned without a
        shell. Either way the workshop gets the shipped arguments exactly, and the launcher's own stdin and stdout."""
        run = _run_launcher(plugin_root, node_home)
        assert run.returncode == 0, run.stderr
        assert run.report["via"] == ("npx-cli" if IS_WINDOWS else "path")
        assert run.report["argv"] == SHIPPED_ARGS
        assert run.echoed == "HELLO\n"

    @pytest.mark.cross_os
    def test_a_filled_option_becomes_the_key(self, plugin_root: Path, node_home: NodeHome) -> None:
        run = _run_launcher(plugin_root, node_home, PIPELEX_PLUGIN_API_KEY="plx_from_the_option", PIPELEX_API_KEY="plx_from_the_shell")
        assert run.report["apiKey"] == "plx_from_the_option"

    @pytest.mark.cross_os
    def test_an_empty_option_leaves_the_shell_key(self, plugin_root: Path, node_home: NodeHome) -> None:
        """An unfilled option reaches the launcher as an empty string, and must not shadow the key the shell exported."""
        run = _run_launcher(plugin_root, node_home, PIPELEX_PLUGIN_API_KEY="", PIPELEX_API_KEY="plx_from_the_shell")
        assert run.report["apiKey"] == "plx_from_the_shell"

    @pytest.mark.cross_os
    def test_no_option_and_no_shell_key_sets_none(self, plugin_root: Path, node_home: NodeHome) -> None:
        run = _run_launcher(plugin_root, node_home, PIPELEX_PLUGIN_API_KEY="")
        assert run.report["apiKey"] is None

    @pytest.mark.cross_os
    def test_the_workshops_exit_code_is_the_launchers(self, plugin_root: Path, node_home: NodeHome) -> None:
        run = _run_launcher(plugin_root, node_home, FAKE_EXIT="7")
        assert run.returncode == 7

    @pytest.mark.cross_os
    @pytest.mark.skipif(not IS_WINDOWS, reason="the shell route is the Windows fallback when no npm sits beside node.exe")
    def test_on_windows_without_npm_beside_node_it_goes_through_the_shell(self, plugin_root: Path, tmp_path: Path, node: str) -> None:
        home = _node_home(tmp_path / "bare", node=node, with_npm=False)
        run = _run_launcher(plugin_root, home)
        assert run.returncode == 0, run.stderr
        assert run.report["via"] == "path"
        assert run.report["argv"] == SHIPPED_ARGS
        assert run.echoed == "HELLO\n"

    @pytest.mark.skipif(IS_WINDOWS, reason="Windows finds npx beside node.exe, so the PATH cannot miss it")
    def test_a_missing_npx_is_named_and_exits_127(self, plugin_root: Path, node_home: NodeHome, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        completed = subprocess.run(
            [str(node_home.node), str(_launcher(plugin_root))],
            capture_output=True,
            text=True,
            env=clean_environment(PATH=str(empty)),
            timeout=LAUNCHER_TIMEOUT_SECONDS,
            check=False,
        )
        assert completed.returncode == 127
        assert "could not start npx" in completed.stderr

    @pytest.mark.skipif(IS_WINDOWS, reason="POSIX termination signals")
    def test_a_termination_signal_reaches_the_workshop_and_ends_the_launcher_the_same_way(self, plugin_root: Path, tmp_path: Path, node: str) -> None:
        """The bash launcher `exec`ed the workshop, so a signal the harness sent reached it directly. The Node launcher
        stands between them, so it passes the signal on, leaves no workshop behind, and dies of the same signal."""
        path_bin = tmp_path / "bin"
        path_bin.mkdir()
        pid_file = tmp_path / "workshop.pid"
        stand_in = path_bin / "npx"
        stand_in.write_text(f'#!/bin/sh\necho $$ > "{pid_file}"\nexec sleep 30\n', encoding="utf-8")
        stand_in.chmod(0o755)
        launcher = subprocess.Popen(
            [node, str(_launcher(plugin_root))],
            stdin=subprocess.DEVNULL,
            env=clean_environment(PATH=f"{path_bin}{os.pathsep}{os.environ['PATH']}"),
        )
        try:
            deadline = time.monotonic() + LAUNCHER_TIMEOUT_SECONDS
            while not (pid_file.is_file() and pid_file.read_text(encoding="utf-8").strip()):
                assert time.monotonic() < deadline, "the stand-in workshop never started"
                time.sleep(0.05)
            workshop_pid = int(pid_file.read_text(encoding="utf-8"))
            launcher.send_signal(signal.SIGTERM)
            assert launcher.wait(timeout=LAUNCHER_TIMEOUT_SECONDS) == -signal.SIGTERM
        finally:
            if launcher.poll() is None:
                launcher.kill()
        deadline = time.monotonic() + 5
        while _is_alive(workshop_pid):
            assert time.monotonic() < deadline, "the workshop outlived the launcher"
            time.sleep(0.05)

    @pytest.mark.cross_os
    def test_the_workshop_answers_initialize_over_stdio_when_started_as_the_manifest_says(
        self, workshop: tuple[subprocess.Popen[str], _LineReader]
    ) -> None:
        """The proof the item asks for: `node <launcher>`, spawned with no shell from a root holding a space, reaches the real
        `@pipelex/mcp` through `npx`, which completes an MCP `initialize` and lists its tools. Needs the npm registry."""
        process, reader = workshop
        _send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pipelex-plugins-tests", "version": "0"}},
            },
        )
        initialized = reader.response(1, timeout=WORKSHOP_TIMEOUT_SECONDS)
        assert "result" in initialized, initialized
        assert initialized["result"]["serverInfo"]["name"]
        _send(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        _send(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = reader.response(2, timeout=LAUNCHER_TIMEOUT_SECONDS)
        assert "mthds_validate" in {tool["name"] for tool in tools["result"]["tools"]}

    @pytest.mark.cross_os
    def test_claude_code_connects_the_plugins_server(self, plugin_root: Path, tmp_path: Path, node: str) -> None:
        """`claude --plugin-dir <plugin> mcp list` starts the plugin's server the way a session does and reports whether it
        connected. It needs no sign-in: the configuration directory is a new, empty one."""
        assert node
        claude = shutil.which("claude")
        if claude is None:
            if os.environ.get(REQUIRE_CLAUDE_CLI):
                pytest.fail(f"no `claude` on the PATH, while {REQUIRE_CLAUDE_CLI} says the job installed the Claude Code CLI")
            pytest.skip("no Claude Code CLI on the PATH")
        project = tmp_path / "a project"
        project.mkdir()
        completed = subprocess.run(
            [claude, "--plugin-dir", str(plugin_root), "mcp", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=project,
            env=clean_environment(CLAUDE_CONFIG_DIR=str(tmp_path / "claude config"), CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1"),
            timeout=WORKSHOP_TIMEOUT_SECONDS,
            check=False,
        )
        output = completed.stdout + completed.stderr
        [line] = [line for line in output.splitlines() if line.startswith("plugin:pipelex:pipelex:")] or [f"no plugin server listed:\n{output}"]
        assert "Connected" in line and "Failed" not in line, output
