"""Tests for scripts/local_mcp.py, which `make claude-local-mcp` and `make codex-local-mcp` run."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

import pytest
from pytest_mock import MockerFixture

from scripts import local_mcp
from scripts.gen_skill_docs import build_target, load_target_config, write_files
from scripts.local_mcp import (
    LOCAL_DIR_NAME,
    MAKE_HANDOFF,
    WORKSHOP_BUNDLE,
    Harness,
    Launcher,
    build_checkout,
    checkout_launcher,
    codex_env_vars,
    codex_overrides,
    main,
    npm_resolve,
    parse_args,
    published_launcher,
    render_claude_copy,
    split_passthrough,
    start,
    toml_string,
    workshop_key,
)

REPO_ROOT = Path(__file__).parents[2]

# What the build reads: rendering the Claude target needs every one of these and nothing else.
BUILD_SOURCES = ("templates", "targets", "skills", ".claude-plugin", ".codex-plugin")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A copy of this repository's build sources, so a render never writes into the real checkout."""
    root = tmp_path / "pipelex-plugins"
    for name in BUILD_SOURCES:
        shutil.copytree(REPO_ROOT / name, root / name)
    return root


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """A pipelex-mcp checkout whose `make build-local` has run, under a path holding a space."""
    root = tmp_path / "my checkouts" / "pipelex-mcp"
    bundle = root / WORKSHOP_BUNDLE
    bundle.parent.mkdir(parents=True)
    bundle.write_text("// the workshop\n", encoding="utf-8")
    (root / "packages" / "workshop" / "package.json").write_text('{"name": "@pipelex/mcp", "version": "1.2.3"}\n', encoding="utf-8")
    return root


def _built(checkout: Path) -> Launcher:
    """The checkout's launcher, its `make build-local` taken as run: the fixture's bundle is already there."""
    return checkout_launcher(checkout, build=lambda _root: None)


def _published(spec: str) -> Launcher:
    return published_launcher(spec, resolve=lambda _spec: "0.20.0")


def _npm_answers(mocker: MockerFixture, *, stdout: str, stderr: str = "", returncode: int = 0) -> None:
    mocker.patch.object(local_mcp.shutil, "which", return_value="/usr/bin/npm")
    mocker.patch.object(
        local_mcp.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr),
    )


def _exec_line(launcher: Launcher) -> str:
    """How `launch-pipelex-mcp.sh` spawns the workshop."""
    return f"exec {launcher.command}" + "".join(f' "{arg}"' for arg in launcher.args)


def _spoken(launcher: Launcher) -> str:
    """How a skill names the workshop's command to the user."""
    return " ".join([launcher.command, *launcher.args])


def _tree(root: Path, *, skip: str | None = None) -> dict[Path, tuple[str, int]]:
    """Every file under `root` with its digest and mode, leaving out the top-level directory `skip`."""
    tree: dict[Path, tuple[str, int]] = {}
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if path.is_file() and rel.parts[0] != skip:
            tree[rel] = (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mode)
    return tree


class TestLauncher:
    def test_a_checkout_runs_its_build_by_absolute_path(self, checkout: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The harness spawns the workshop from the session's directory, so a relative path would name another file."""
        monkeypatch.chdir(checkout.parent)
        launcher = _built(Path("pipelex-mcp"))
        assert launcher.command == "node"
        assert launcher.args == [str(checkout.resolve() / WORKSHOP_BUNDLE)]
        assert "@pipelex/mcp 1.2.3" in launcher.label

    def test_a_checkout_whose_build_writes_no_workshop_is_refused(self, checkout: Path) -> None:
        (checkout / WORKSHOP_BUNDLE).unlink()
        with pytest.raises(SystemExit, match="does not exist after `make build-local`"):
            _built(checkout)

    def test_the_checkout_is_built_before_its_workshop_is_looked_for(self, checkout: Path) -> None:
        (checkout / WORKSHOP_BUNDLE).unlink()
        built: list[Path] = []

        def build(root: Path) -> None:
            built.append(root)
            (root / WORKSHOP_BUNDLE).write_text("// built now\n", encoding="utf-8")

        launcher = checkout_launcher(checkout, build=build)
        assert built == [checkout.resolve()]
        assert launcher.args == [str(checkout.resolve() / WORKSHOP_BUNDLE)]

    def test_a_missing_checkout_names_the_variable_to_set_and_builds_nothing(self, tmp_path: Path) -> None:
        built: list[Path] = []
        with pytest.raises(SystemExit, match="MCP="):
            checkout_launcher(tmp_path / "nowhere", build=built.append)
        assert built == []

    def test_the_build_is_given_none_of_the_make_targets_variables(
        self, checkout: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """make hands a target's commands its command-line variables, which would override or fill the checkout's Makefile."""
        for name in MAKE_HANDOFF:
            monkeypatch.setenv(name, "from the make target")
        mocker.patch.object(local_mcp.shutil, "which", return_value="/usr/bin/make")
        run = mocker.patch.object(local_mcp.subprocess, "run", return_value=subprocess.CompletedProcess(args=[], returncode=0))
        build_checkout(checkout)
        assert run.call_args.args[0] == ["/usr/bin/make", "--no-print-directory", "-C", str(checkout), "build-local"]
        environment = run.call_args.kwargs["env"]
        assert not MAKE_HANDOFF & environment.keys()
        assert environment["PATH"] == os.environ["PATH"]

    def test_a_failed_build_starts_nothing(self, checkout: Path, mocker: MockerFixture) -> None:
        mocker.patch.object(local_mcp.shutil, "which", return_value="/usr/bin/make")
        mocker.patch.object(local_mcp.subprocess, "run", return_value=subprocess.CompletedProcess(args=[], returncode=2))
        with pytest.raises(SystemExit, match="`make build-local` failed"):
            build_checkout(checkout)

    def test_a_published_version_is_pinned_to_the_one_npm_resolves(self) -> None:
        launcher = _published("latest")
        assert (launcher.command, launcher.args) == ("npx", ["-y", "@pipelex/mcp@0.20.0"])

    def test_npm_resolves_a_spec_to_one_version(self, mocker: MockerFixture) -> None:
        _npm_answers(mocker, stdout='"0.20.0"\n')
        assert npm_resolve("latest") == "0.20.0"

    def test_a_version_npm_does_not_know_is_refused_with_its_summary(self, mocker: MockerFixture) -> None:
        _npm_answers(
            mocker,
            stdout='{"error": {"code": "E404", "summary": "No match found for version 9.9.9", "detail": "…"}}',
            stderr="npm error code E404\nnpm error 404 …\n",
            returncode=1,
        )
        with pytest.raises(SystemExit, match=r"failed \(No match found for version 9\.9\.9\)"):
            npm_resolve("9.9.9")

    def test_a_spec_npm_answers_nothing_for_is_refused(self, mocker: MockerFixture) -> None:
        _npm_answers(mocker, stdout="")
        with pytest.raises(SystemExit, match="No published @pipelex/mcp matches"):
            npm_resolve("0.0.1")

    def test_a_range_matching_several_versions_is_refused(self, mocker: MockerFixture) -> None:
        _npm_answers(mocker, stdout='["0.19.0", "0.20.0"]')
        with pytest.raises(SystemExit, match="several published versions"):
            npm_resolve("^0.19")


class TestClaudeCopy:
    def test_the_copy_is_the_shipped_target_but_for_the_workshop(self, repo: Path, checkout: Path) -> None:
        """The copy cannot drift from what ships: the same files, byte for byte and mode for mode, once the launcher is swapped back."""
        launcher = _built(checkout)
        copy = render_claude_copy(repo, launcher)
        assert copy == repo / LOCAL_DIR_NAME / workshop_key(launcher) / "pipelex"

        shipped_config = load_target_config(repo / "targets", "prod")
        write_files(build_target(repo, shipped_config).files)
        shipped_dir = repo / "pipelex"
        server = shipped_config.template_vars["mcp_server"]
        assert isinstance(server, dict)
        shipped = Launcher(command=str(server["command"]), args=[str(arg) for arg in cast("list[object]", server["args"])], label="shipped")

        swaps = {_exec_line(launcher): _exec_line(shipped), _spoken(launcher): _spoken(shipped)}
        copy_tree, shipped_tree = _tree(copy), _tree(shipped_dir)
        assert copy_tree.keys() == shipped_tree.keys()
        swapped: list[Path] = []
        for rel, (digest, mode) in copy_tree.items():
            assert mode == shipped_tree[rel][1], f"{rel}: mode differs from the shipped file"
            if digest == shipped_tree[rel][0]:
                continue
            content = (copy / rel).read_text(encoding="utf-8")
            for local_text, shipped_text in swaps.items():
                content = content.replace(local_text, shipped_text)
            assert content == (shipped_dir / rel).read_text(encoding="utf-8"), f"{rel} differs from the shipped file beyond the workshop"
            swapped.append(rel)
        assert Path("hooks/launch-pipelex-mcp.sh") in swapped

    def test_the_launcher_keeps_the_credential_promotion(self, repo: Path, checkout: Path) -> None:
        copy = render_claude_copy(repo, _built(checkout))
        launcher = (copy / "hooks" / "launch-pipelex-mcp.sh").read_text(encoding="utf-8")
        for key in ("API_KEY", "BASE_URL"):
            assert f'export PIPELEX_{key}="$PIPELEX_PLUGIN_{key}"' in launcher
        assert launcher.rstrip().endswith(f'exec node "{checkout.resolve() / WORKSHOP_BUNDLE}"')
        assert os.access(copy / "hooks" / "launch-pipelex-mcp.sh", os.X_OK)

    @pytest.mark.skipif(shutil.which("bash") is None, reason="no bash on the PATH")
    def test_the_launcher_hands_the_workshop_a_path_the_shell_would_act_on_as_it_is(self, repo: Path, tmp_path: Path) -> None:
        """A checkout is any directory, so its path reaches the launcher's `exec` line with whatever it holds."""
        odd = tmp_path / 'a $HOME `true` "quoted" back\\slash' / "pipelex-mcp"
        (odd / WORKSHOP_BUNDLE).parent.mkdir(parents=True)
        (odd / WORKSHOP_BUNDLE).write_text("// the workshop\n", encoding="utf-8")
        copy = render_claude_copy(repo, _built(odd))

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "node").write_text('#!/bin/sh\nprintf "%s" "$1"\n', encoding="utf-8")
        (bin_dir / "node").chmod(0o755)
        environment = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "HOME": str(tmp_path)}
        completed = subprocess.run([str(copy / "hooks" / "launch-pipelex-mcp.sh")], capture_output=True, text=True, check=False, env=environment)
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == str(odd.resolve() / WORKSHOP_BUNDLE)

    def test_a_second_render_of_a_workshop_replaces_its_copy_and_leaves_nothing_beside_it(self, repo: Path, checkout: Path) -> None:
        copy = render_claude_copy(repo, _built(checkout))
        (copy / "stray.txt").write_text("left by hand\n", encoding="utf-8")

        again = render_claude_copy(repo, _built(checkout))
        assert again == copy
        assert not (copy / "stray.txt").exists()
        assert sorted(path.name for path in copy.parent.iterdir()) == [".lock", "pipelex"]

    def test_another_workshop_gets_a_copy_of_its_own_and_leaves_the_first_as_it_was(self, repo: Path, checkout: Path) -> None:
        """A session reads its launcher again at every respawn, so a shared copy would switch the workshop under it."""
        first = render_claude_copy(repo, _built(checkout))
        before = _tree(first)

        second = render_claude_copy(repo, _published("latest"))
        assert second != first
        assert _tree(first) == before
        assert (second / "hooks" / "launch-pipelex-mcp.sh").read_text(encoding="utf-8").rstrip().endswith('exec npx "-y" "@pipelex/mcp@0.20.0"')

    def test_renders_of_one_workshop_at_once_each_swap_in_a_whole_copy(self, repo: Path, checkout: Path) -> None:
        """Two starts at the same moment render apart and swap in turn, so neither fails and neither leaves a partial copy."""
        launcher = _built(checkout)
        whole = _tree(render_claude_copy(repo, launcher))
        with ThreadPoolExecutor(max_workers=4) as pool:
            copies = [future.result() for future in [pool.submit(render_claude_copy, repo, launcher) for _ in range(4)]]
        assert set(copies) == {repo / LOCAL_DIR_NAME / workshop_key(launcher) / "pipelex"}
        assert _tree(copies[0]) == whole
        assert sorted(path.name for path in copies[0].parent.iterdir()) == [".lock", "pipelex"]

    def test_the_render_writes_nothing_outside_the_local_directory(self, repo: Path, checkout: Path) -> None:
        before = _tree(repo, skip=LOCAL_DIR_NAME)
        render_claude_copy(repo, _built(checkout))
        assert _tree(repo, skip=LOCAL_DIR_NAME) == before

    @pytest.mark.skipif(shutil.which("git") is None, reason="no git on the PATH")
    def test_git_ignores_the_local_directory(self) -> None:
        probe = f"{LOCAL_DIR_NAME}/0123456789ab/pipelex/.claude-plugin/plugin.json"
        completed = subprocess.run(["git", "-C", str(REPO_ROOT), "check-ignore", "-q", "--no-index", probe], check=False)
        assert completed.returncode == 0, f"{LOCAL_DIR_NAME}/ must be in .gitignore, since the copy is never committed"


class TestCodexOverrides:
    def test_the_overrides_replace_the_entry_and_forward_the_key_names(self, checkout: Path) -> None:
        """A configuration-tier entry replaces the plugin's whole, so the names it forwards must be given again."""
        launcher = _built(checkout)
        overrides = codex_overrides(launcher, ["PIPELEX_API_KEY", "PIPELEX_BASE_URL"])
        assert overrides[0::2] == ["-c", "-c", "-c"]
        parsed = {key: tomllib.loads(f"v = {value}")["v"] for key, value in (item.split("=", 1) for item in overrides[1::2])}
        assert parsed == {
            "mcp_servers.pipelex.command": "node",
            "mcp_servers.pipelex.args": [str(checkout.resolve() / WORKSHOP_BUNDLE)],
            "mcp_servers.pipelex.env_vars": ["PIPELEX_API_KEY", "PIPELEX_BASE_URL"],
        }

    @pytest.mark.parametrize("value", ["plain", "with space", 'a "quote"', "back\\slash", "tab\tand\nnewline", "accentué ✓ 😀", "del\x7f"])
    def test_a_toml_string_reads_back_as_the_value(self, value: str) -> None:
        assert tomllib.loads(f"v = {toml_string(value)}")["v"] == value

    def test_the_names_forwarded_are_the_codex_targets(self, repo: Path) -> None:
        server = load_target_config(repo / "targets", "codex").template_vars["mcp_server"]
        assert isinstance(server, dict)
        assert codex_env_vars(repo) == server["env_vars"]
        assert codex_env_vars(repo)

    def test_a_codex_target_forwarding_nothing_is_refused(self, repo: Path) -> None:
        with (repo / "targets" / "codex.toml").open("a", encoding="utf-8") as codex_toml:
            codex_toml.write("\n[vars.mcp_server]\nenv_vars = []\n")
        with pytest.raises(SystemExit, match="without a key"):
            codex_env_vars(repo)


class Launched(Exception):
    """What the patched `os.execv` raises in place of replacing the test process."""

    def __init__(self, program: str, argv: list[str]) -> None:
        super().__init__(program)
        self.program = program
        self.argv = argv


class TestStart:
    @pytest.fixture
    def harness_calls(self, mocker: MockerFixture) -> list[Path]:
        """Put every harness on the PATH, record where the session starts, and stop at the exec."""

        def which(name: str) -> str:
            return f"/usr/local/bin/{name}"

        mocker.patch.object(local_mcp.shutil, "which", side_effect=which)

        def execv(program: str, argv: list[str]) -> None:
            raise Launched(program, argv)

        mocker.patch.object(local_mcp.os, "execv", side_effect=execv)
        chdirs: list[Path] = []
        mocker.patch.object(local_mcp.os, "chdir", side_effect=chdirs.append)
        return chdirs

    def test_claude_starts_on_the_copy_in_the_workdir(self, repo: Path, checkout: Path, tmp_path: Path, harness_calls: list[Path]) -> None:
        launcher = _built(checkout)
        with pytest.raises(Launched) as launched:
            start(Harness.CLAUDE, launcher, tmp_path, ["-p", "hello"], repo)
        copy = repo / LOCAL_DIR_NAME / workshop_key(launcher) / "pipelex"
        assert launched.value.argv == ["/usr/local/bin/claude", "--plugin-dir", str(copy), "-p", "hello"]
        assert harness_calls == [tmp_path]

    def test_codex_starts_with_the_overrides_and_renders_nothing(self, repo: Path, checkout: Path, tmp_path: Path, harness_calls: list[Path]) -> None:
        launcher = _built(checkout)
        with pytest.raises(Launched) as launched:
            start(Harness.CODEX, launcher, tmp_path, ["exec", "hello"], repo)
        assert launched.value.argv == ["/usr/local/bin/codex", *codex_overrides(launcher, codex_env_vars(repo)), "exec", "hello"]
        assert not (repo / LOCAL_DIR_NAME).exists()

    @pytest.mark.parametrize(("key", "warned"), [(None, True), ("", True), ("plx_sk_test", False)])
    def test_a_missing_key_is_warned_of(
        self,
        repo: Path,
        tmp_path: Path,
        harness_calls: list[Path],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        key: str | None,
        warned: bool,
    ) -> None:
        if key is None:
            monkeypatch.delenv("PIPELEX_API_KEY", raising=False)
        else:
            monkeypatch.setenv("PIPELEX_API_KEY", key)
        with pytest.raises(Launched):
            start(Harness.CODEX, _published("latest"), tmp_path, [], repo)
        assert ("PIPELEX_API_KEY is not set" in capsys.readouterr().out) is warned

    def test_a_harness_not_on_the_path_stops_before_anything_is_rendered(self, repo: Path, tmp_path: Path, mocker: MockerFixture) -> None:
        mocker.patch.object(local_mcp.shutil, "which", return_value=None)
        with pytest.raises(SystemExit, match="`claude` is not on the PATH"):
            start(Harness.CLAUDE, _published("latest"), tmp_path, [], repo)
        assert not (repo / LOCAL_DIR_NAME).exists()


class TestCommandLine:
    def test_what_follows_the_first_double_dash_goes_to_the_harness_whole(self) -> None:
        own, passthrough = split_passthrough(["claude", "--mcp", "x", "--", "-p", "--", "y"])
        assert own == ["claude", "--mcp", "x"]
        assert passthrough == ["-p", "--", "y"]

    @pytest.mark.parametrize("argv", [["claude"], ["claude", "--mcp", "x", "--mcp-version", "1.0.0"], ["vibe", "--mcp", "x"]])
    def test_one_harness_and_exactly_one_workshop_are_required(self, argv: list[str]) -> None:
        with pytest.raises(SystemExit):
            parse_args(argv)

    def test_a_workdir_that_is_not_a_directory_is_refused(self, checkout: Path, tmp_path: Path) -> None:
        with pytest.raises(SystemExit, match="WORKDIR"):
            main(["claude", "--mcp", str(checkout), "--workdir", str(tmp_path / "nowhere")])


@pytest.mark.skipif(shutil.which("make") is None, reason="no make on the PATH")
class TestMakeTargets:
    def _make(self, *arguments: str, home: Path | None = None) -> subprocess.CompletedProcess[str]:
        """This repository's make, told its venv is installed: `install` would update uv over the network."""
        environment = {**os.environ, "HOME": str(home)} if home is not None else None
        return subprocess.run(
            ["make", "--no-print-directory", "-C", str(REPO_ROOT), "-o", "install", *arguments],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )

    @pytest.mark.skipif(not (REPO_ROOT / ".venv" / "bin" / "python").is_file(), reason="no venv: run `make install`")
    @pytest.mark.parametrize("home_relative", [False, True])
    def test_the_checkout_is_built_with_none_of_the_targets_variables(self, tmp_path: Path, home_relative: bool) -> None:
        """make hands a target's commands its command-line variables, which would override or fill the checkout's own.

        This one runs for real: the checkout's build only reports what it sees, and the script then
        refuses the checkout for having built no workshop, so nothing starts. zsh passes `MCP=~/…` with
        its tilde as it is, so that spelling is run too.
        """
        checkout = tmp_path / "pipelex-mcp"
        checkout.mkdir()
        (checkout / "Makefile").write_text(
            'ARGS = its-own\nbuild-local:\n\t@echo "built with ARGS=[$(ARGS)] MCP=[$(MCP)] MCP_VERSION=[$(MCP_VERSION)] WORKDIR=[$(WORKDIR)]"\n',
            encoding="utf-8",
        )
        mcp = "~/pipelex-mcp" if home_relative else str(checkout)
        completed = self._make("claude-local-mcp", f"MCP={mcp}", "ARGS=--model sonnet", f"WORKDIR={tmp_path}", home=tmp_path)
        assert "built with ARGS=[its-own] MCP=[] MCP_VERSION=[] WORKDIR=[]" in completed.stdout
        assert "does not exist after `make build-local`" in completed.stderr
        assert completed.returncode != 0

    @pytest.mark.skipif(not (REPO_ROOT / ".venv" / "bin" / "python").is_file(), reason="no venv: run `make install`")
    def test_a_missing_checkout_is_refused_with_the_variable_to_set(self, tmp_path: Path) -> None:
        completed = self._make("claude-local-mcp", f"MCP={tmp_path / 'nowhere'}")
        assert "pass MCP=" in completed.stderr
        assert completed.returncode != 0

    def test_a_published_version_reaches_the_script_as_a_version(self) -> None:
        completed = self._make("-n", "claude-local-mcp", "MCP_VERSION=0.20.0", "MCP=/no/checkout/here", "ARGS=--model sonnet")
        assert completed.returncode == 0, completed.stderr
        assert 'scripts/local_mcp.py claude --mcp-version "0.20.0" --workdir "." -- --model sonnet' in completed.stdout
