"""Execute the scripts `pipelex-scaffold`'s initializer branch runs by path.

Box E of the size diet (`wip/skill-size-diet/design.md`): a procedure whose text is its correctness
ships as a script, and the unit suite executes the script directly. These tests run each one as a
user's harness does, through `bash`, against a scratch project, and read what it leaves behind.
The skill's side, which runs the scripts and keys its stop table on their verdicts, is pinned in
`test_pipelex_scaffold_skill.py`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]
SCRIPTS = REPO_ROOT / "skills" / "pipelex-scaffold" / "scripts"
COMMIT_PRISTINE = SCRIPTS / "commit-pristine.sh"
WRITE_ENV_FILE = SCRIPTS / "write-env-file.sh"

PRODUCTION_URL = "https://api.pipelex.com"
# Fake credentials only. The machine's own PIPELEX_* values are removed from every environment
# these tests build, so no real key can reach a temporary file or an assertion message.
FAKE_KEY = "plx_fake_key_for_tests_0000"
FAKE_URL = "https://api.fake-plane.example"
COMMENT_LINE = "# Copied from the shell environment; a later line overrides an earlier one."
EXAMPLE = f"PIPELEX_BASE_URL={PRODUCTION_URL}\nPIPELEX_API_KEY=\n"

pytestmark = pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None, reason="the scripts are bash over git")


def _environment(credentials: dict[str, str] | None = None) -> dict[str, str]:
    """The test process's environment with this machine's credentials and git configuration removed.

    A fixed identity makes a commit deterministic in CI, and `BASH_ENV` is dropped so that no startup
    file can put a real value back.
    """
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in {"PIPELEX_API_KEY", "PIPELEX_BASE_URL", "BASH_ENV", "ENV"} and not name.startswith("GIT_")
    }
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
    )
    environment.update(credentials or {})
    return environment


def _run(
    script: Path, *arguments: str, cwd: Path, credentials: dict[str, str] | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *arguments],
        cwd=cwd,
        env=env if env is not None else _environment(credentials),
        capture_output=True,
        text=True,
        check=False,
    )


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.run(["git", "-C", str(repository), *arguments], env=_environment(), capture_output=True, text=True, check=True).stdout.strip()


def _repository(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    return path


def _ignored_only_on_this_machine(tmp_path: Path, project: Path, where: str, pattern: str, environment: dict[str, str]) -> None:
    """Ignore `pattern` where a clone never carries it: this machine's global excludes file, as a
    developer's often does, or the repository's own `info/exclude`."""
    if where == "global-excludes":
        excludes = tmp_path / "global-ignore"
        excludes.write_text(f"{pattern}\n", encoding="utf-8")
        config = tmp_path / "global-config"
        config.write_text(f"[core]\n\texcludesFile = {excludes}\n", encoding="utf-8")
        environment["GIT_CONFIG_GLOBAL"] = str(config)
    else:
        exclude = project / ".git" / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text(f"{pattern}\n", encoding="utf-8")


def _dotenv_reading(text: str) -> dict[str, str]:
    """An env file resolved the way dotenv readers resolve it: the later of two assignments wins."""
    resolved: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.removeprefix("export ").split("=", 1)
        resolved[name.strip()] = value.strip()
    return resolved


class TestCommitPristine:
    """The pristine commit: the repository test, the `.gitignore`, and one commit held to `<dir>`."""

    def test_it_commits_a_new_project_and_lists_what_it_staged(self, tmp_path: Path) -> None:
        project = tmp_path / "my-app"
        project.mkdir()
        (project / "pyproject.toml").write_text('[project]\nname = "my-app"\n', encoding="utf-8")
        result = _run(COMMIT_PRISTINE, "my-app", "Scaffold Python project", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        lines = result.stdout.splitlines()
        assert lines[0].startswith("committed: ") and lines[0].endswith(" Scaffold Python project")
        assert sorted(lines[1:]) == [".gitignore", "pyproject.toml"]
        assert _git(project, "log", "--format=%s") == "Scaffold Python project"
        assert _git(project, "status", "--porcelain") == ""

    def test_the_dependency_tree_never_reaches_the_commit(self, tmp_path: Path) -> None:
        """`npm init -y` and `tsc --init` write no `.gitignore`, so the staging would commit `node_modules/`."""
        project = tmp_path / "lib"
        (project / "node_modules" / "typescript").mkdir(parents=True)
        (project / "node_modules" / "typescript" / "index.js").write_text("//\n", encoding="utf-8")
        (project / "package.json").write_text("{}\n", encoding="utf-8")
        result = _run(COMMIT_PRISTINE, str(project), "Scaffold TypeScript project", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert (project / ".gitignore").read_text(encoding="utf-8") == "node_modules/\ndist/\n.env\n"
        assert "node_modules" not in _git(project, "ls-files")

    def test_an_initializer_s_own_gitignore_is_kept_and_completed(self, tmp_path: Path) -> None:
        project = tmp_path / "svc"
        (project / "node_modules" / "x").mkdir(parents=True)
        (project / "node_modules" / "x" / "i.js").write_text("//\n", encoding="utf-8")
        (project / ".gitignore").write_text("build/", encoding="utf-8")
        result = _run(COMMIT_PRISTINE, str(project), "Scaffold Express project", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert (project / ".gitignore").read_text(encoding="utf-8") == "build/\nnode_modules/\n"
        assert "node_modules" not in _git(project, "ls-files")

    @pytest.mark.parametrize("where", ["global-excludes", "info-exclude"])
    def test_a_node_modules_only_this_machine_ignores_goes_into_the_project_s_gitignore(self, tmp_path: Path, where: str) -> None:
        """A teammate's clone carries the project's `.gitignore` alone, so their next `git add` would
        take the dependency tree this machine's own rule kept out of the pristine commit."""
        project = _repository(tmp_path / "svc")
        (project / "node_modules" / "x").mkdir(parents=True)
        (project / "node_modules" / "x" / "i.js").write_text("//\n", encoding="utf-8")
        (project / ".gitignore").write_text("build/\n", encoding="utf-8")
        environment = _environment()
        _ignored_only_on_this_machine(tmp_path, project, where, "node_modules/", environment)
        result = _run(COMMIT_PRISTINE, str(project), "Scaffold Express project", cwd=tmp_path, env=environment)
        assert result.returncode == 0, result.stderr
        assert (project / ".gitignore").read_text(encoding="utf-8") == "build/\n\nnode_modules/\n"

    def test_a_python_project_gets_python_s_lines(self, tmp_path: Path) -> None:
        """`uv init` writes no `.gitignore` inside an enclosing repository, and Node's lines would leave
        `__pycache__/` to be committed on the first run."""
        project = tmp_path / "cli"
        project.mkdir()
        (project / "pyproject.toml").write_text('[project]\nname = "cli"\n', encoding="utf-8")
        result = _run(COMMIT_PRISTINE, str(project), "Scaffold Python project", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        lines = (project / ".gitignore").read_text(encoding="utf-8").splitlines()
        assert {"__pycache__/", ".venv/", ".env"} <= set(lines)
        assert "node_modules/" not in lines

    def test_a_mixed_project_keeps_its_dependency_tree_out(self, tmp_path: Path) -> None:
        """A Python project that also installed Node packages gets Python's lines and `node_modules/`."""
        project = tmp_path / "mixed"
        (project / "node_modules" / "x").mkdir(parents=True)
        (project / "node_modules" / "x" / "i.js").write_text("//\n", encoding="utf-8")
        (project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        result = _run(COMMIT_PRISTINE, str(project), "Scaffold Python project", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "node_modules" not in _git(project, "ls-files")

    def test_an_env_file_the_initializer_wrote_never_reaches_the_commit(self, tmp_path: Path) -> None:
        """The env-file script ignores `.env` one step too late for a `.env` the initializer wrote: once
        committed, no ignore rule reaches it and it stays in the history."""
        project = tmp_path / "svc"
        project.mkdir()
        (project / ".gitignore").write_text("build/\n", encoding="utf-8")
        (project / ".env").write_text("SECRET=generated\n", encoding="utf-8")
        (project / "main.py").write_text("\n", encoding="utf-8")
        result = _run(COMMIT_PRISTINE, str(project), "Scaffold Python project", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert sorted(_git(project, "ls-files").splitlines()) == [".gitignore", "main.py"]
        assert (project / ".gitignore").read_text(encoding="utf-8") == "build/\n\n.env\n"

    def test_a_directory_inside_the_user_s_repository_gets_its_own(self, tmp_path: Path) -> None:
        """`git -C <dir>` scopes nothing: with no `.git` of its own, `<dir>` is governed by the user's
        repository, and a staging there would sweep their worktree into this commit. `uv init` makes a
        workspace member rather than a repository in exactly this case, so the test is never inferred
        from which initializer ran."""
        outer = _repository(tmp_path / "their-repo")
        (outer / "notes.md").write_text("mine\n", encoding="utf-8")
        (outer / "staged.md").write_text("staged by them\n", encoding="utf-8")
        _git(outer, "add", "staged.md")
        project = outer / "new-app"
        project.mkdir()
        (project / "main.py").write_text("print('hi')\n", encoding="utf-8")
        result = _run(COMMIT_PRISTINE, "new-app", "Scaffold Python project", cwd=outer)
        assert result.returncode == 0, result.stderr
        assert (project / ".git").is_dir()
        assert sorted(_git(project, "ls-files").splitlines()) == [".gitignore", "main.py"]
        # The user's repository is exactly as they left it: nothing committed, their staging intact.
        assert subprocess.run(["git", "-C", str(outer), "rev-parse", "-q", "--verify", "HEAD"], capture_output=True, check=False).returncode != 0
        assert _git(outer, "diff", "--cached", "--name-only") == "staged.md"

    def test_a_repository_the_user_made_is_committed_on_and_never_reinitialized(self, tmp_path: Path) -> None:
        """The lone-`.git` directory: the user's own repository, with their history, gets the commit."""
        project = _repository(tmp_path / "mine")
        (project / "README.md").write_text("mine\n", encoding="utf-8")
        _git(project, "add", "README.md")
        _git(project, "commit", "-q", "-m", "my first commit")
        _git(project, "rm", "-q", "README.md")
        _git(project, "commit", "-q", "-m", "and then I emptied it")
        (project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        result = _run(COMMIT_PRISTINE, str(project), "Scaffold Python project", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert _git(project, "log", "--format=%s").splitlines() == ["Scaffold Python project", "and then I emptied it", "my first commit"]

    def test_an_initializer_that_committed_is_taken_and_never_doubled(self, tmp_path: Path) -> None:
        """`create-next-app` runs `git init`, stages everything and commits: that commit is the pristine one."""
        project = _repository(tmp_path / "web")
        (project / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        (project / "package.json").write_text("{}\n", encoding="utf-8")
        _git(project, "add", "-A")
        _git(project, "commit", "-q", "-m", "Initial commit from Create Next App")
        result = _run(COMMIT_PRISTINE, str(project), "Scaffold Next.js project", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("kept: ") and "Initial commit from Create Next App" in result.stdout
        assert _git(project, "rev-list", "--count", "HEAD") == "1"

    @pytest.mark.parametrize("occupants", [set[str](), {".git"}], ids=["empty", "lone-git"])
    def test_a_directory_the_initializer_left_empty_is_refused(self, tmp_path: Path, occupants: set[str]) -> None:
        project = tmp_path / "empty"
        project.mkdir()
        if ".git" in occupants:
            _repository(project)
        result = _run(COMMIT_PRISTINE, str(project), "Scaffold Python project", cwd=tmp_path)
        assert result.stdout == "refused: nothing-to-commit\n"
        assert result.returncode == 1
        assert sorted(entry.name for entry in project.iterdir()) == sorted(occupants), "a refusal wrote something"

    def test_a_commit_git_refuses_is_reported_with_git_s_message(self, tmp_path: Path) -> None:
        project = tmp_path / "noid"
        project.mkdir()
        (project / "main.py").write_text("\n", encoding="utf-8")
        environment = _environment()
        for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            environment.pop(name)
        environment.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "user.useConfigOnly", "GIT_CONFIG_VALUE_0": "true"})
        result = _run(COMMIT_PRISTINE, str(project), "Scaffold Python project", cwd=tmp_path, env=environment)
        assert result.stdout == "refused: commit-failed\n"
        assert result.stderr.strip(), "git's own message is relayed on standard error"

    @pytest.mark.parametrize(
        ("arguments", "verdict"),
        [((), "usage"), (("only-a-dir",), "usage"), (("dir", ""), "usage"), (("no-such-dir", "Scaffold"), "no-directory")],
        ids=["no-arguments", "no-message", "empty-message", "no-directory"],
    )
    def test_a_mistyped_command_is_refused(self, tmp_path: Path, arguments: tuple[str, ...], verdict: str) -> None:
        result = _run(COMMIT_PRISTINE, *arguments, cwd=tmp_path)
        assert result.stdout == f"refused: {verdict}\n"
        assert result.returncode == 1

    def test_a_name_with_a_space_is_one_directory(self, tmp_path: Path) -> None:
        project = tmp_path / "my app"
        project.mkdir()
        (project / "main.py").write_text("\n", encoding="utf-8")
        result = _run(COMMIT_PRISTINE, "my app", "Scaffold Python project", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert (project / ".git").is_dir()


class TestWriteEnvFile:
    """The env file: the example, `.env` ignored, and `.env` filled from the shell and never printed."""

    @staticmethod
    def project(tmp_path: Path, example: str | None = EXAMPLE) -> Path:
        project = _repository(tmp_path / "app")
        if example is not None:
            (project / ".env.example").write_text(example, encoding="utf-8")
        return project

    @pytest.mark.parametrize(
        ("credentials", "expected_key", "expected_url", "verdict"),
        [
            pytest.param(
                {"PIPELEX_API_KEY": FAKE_KEY, "PIPELEX_BASE_URL": FAKE_URL}, FAKE_KEY, FAKE_URL, "filled base-url=copied plane=other", id="both-set"
            ),
            pytest.param(
                {"PIPELEX_API_KEY": FAKE_KEY, "PIPELEX_BASE_URL": f"{PRODUCTION_URL}/"},
                FAKE_KEY,
                f"{PRODUCTION_URL}/",
                "filled base-url=copied plane=production",
                id="both-set-production-with-a-trailing-slash",
            ),
            pytest.param({"PIPELEX_API_KEY": FAKE_KEY}, FAKE_KEY, PRODUCTION_URL, "filled base-url=file plane=production", id="key-only"),
            pytest.param(
                {"PIPELEX_API_KEY": FAKE_KEY, "PIPELEX_BASE_URL": ""},
                FAKE_KEY,
                PRODUCTION_URL,
                "filled base-url=file plane=production",
                id="key-beside-an-empty-base-url",
            ),
            pytest.param({}, "", PRODUCTION_URL, "empty base-url=file plane=production", id="neither"),
            pytest.param({"PIPELEX_BASE_URL": FAKE_URL}, "", FAKE_URL, "empty base-url=copied plane=other", id="base-url-without-a-key"),
        ],
    )
    @pytest.mark.parametrize("example", [EXAMPLE, EXAMPLE.rstrip("\n"), None], ids=["example", "example-without-final-newline", "no-example"])
    def test_it_writes_the_pair_the_shell_holds(
        self, tmp_path: Path, example: str | None, credentials: dict[str, str], expected_key: str, expected_url: str, verdict: str
    ) -> None:
        """A base URL the shell sets is copied with a key or without one, since it is the plane the user
        declared; the key only when the shell sets it; and a shell that sets neither leaves the example as
        it came. The claim is about what a dotenv reader resolves, so the file is read back that way."""
        project = self.project(tmp_path, example)
        result = _run(WRITE_ENV_FILE, str(project), cwd=tmp_path, credentials=credentials)
        assert result.returncode == 0, result.stderr
        assert result.stdout == f"{verdict}\n"
        written = (project / ".env").read_text(encoding="utf-8")
        shipped = (project / ".env.example").read_text(encoding="utf-8")
        reading = _dotenv_reading(written)
        assert reading["PIPELEX_API_KEY"] == expected_key
        assert reading["PIPELEX_BASE_URL"] == expected_url
        # The example's lines come first and untouched, then the comment once and the supplied lines.
        assert written.startswith(shipped)
        appended = [line for line in written[len(shipped) :].splitlines() if line]
        supplied = [f"{name}={credentials[name]}" for name in ("PIPELEX_API_KEY", "PIPELEX_BASE_URL") if credentials.get(name)]
        assert appended == ([COMMENT_LINE, *supplied] if supplied else [])
        # `.env` is ignored before a key can reach it.
        assert subprocess.run(["git", "-C", str(project), "check-ignore", "-q", ".env"], check=False).returncode == 0

    @pytest.mark.parametrize(
        "carried",
        [
            f"PIPELEX_BASE_URL={PRODUCTION_URL}\nPIPELEX_API_KEY=plx_the_users_own_fake_key\n",
            "PIPELEX_BASE_URL=http://127.0.0.1:8081\nPIPELEX_API_KEY=plx_the_users_own_fake_key",
            "export PIPELEX_API_KEY=plx_the_users_own_fake_key\n",
            'PIPELEX_API_KEY = "plx_the_users_own_fake_key"\r\n',
        ],
        ids=["their-key-beside-the-example-url", "their-key-beside-their-own-url-without-final-newline", "exported", "spaced-quoted-crlf"],
    )
    def test_a_file_that_already_carries_a_key_is_left_byte_for_byte(self, tmp_path: Path, carried: str) -> None:
        """A later assignment of either line would silently replace a working credential while the report
        said theirs was kept, so neither may move. Compared as bytes."""
        project = self.project(tmp_path)
        (project / ".env").write_bytes(carried.encode("utf-8"))
        result = _run(WRITE_ENV_FILE, str(project), cwd=tmp_path, credentials={"PIPELEX_API_KEY": FAKE_KEY, "PIPELEX_BASE_URL": FAKE_URL})
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("kept base-url=file plane=")
        assert (project / ".env").read_bytes() == carried.encode("utf-8")

    @pytest.mark.parametrize(
        "carried",
        [
            "PIPELEX_BASE_URL=http://127.0.0.1:8081\nPIPELEX_API_KEY=plx_the_users_own_fake_key\n",
            "export PIPELEX_BASE_URL = 'http://127.0.0.1:8081/'\nexport PIPELEX_API_KEY=plx_the_users_own_fake_key\n",
        ],
        ids=["plain", "exported-spaced-quoted"],
    )
    def test_the_plane_is_read_from_the_file_the_user_kept(self, tmp_path: Path, carried: str) -> None:
        project = self.project(tmp_path)
        (project / ".env").write_text(carried, encoding="utf-8")
        assert _run(WRITE_ENV_FILE, str(project), cwd=tmp_path).stdout == "kept base-url=file plane=other\n"

    def test_a_key_the_file_empties_again_is_filled(self, tmp_path: Path) -> None:
        """A dotenv reader resolves the last assignment, so a key followed by an empty one is no key."""
        project = self.project(tmp_path)
        (project / ".env").write_text("PIPELEX_API_KEY=plx_an_old_fake_key\nPIPELEX_API_KEY=\n", encoding="utf-8")
        result = _run(WRITE_ENV_FILE, str(project), cwd=tmp_path, credentials={"PIPELEX_API_KEY": FAKE_KEY})
        assert result.stdout == "filled base-url=file plane=production\n"
        assert _dotenv_reading((project / ".env").read_text(encoding="utf-8"))["PIPELEX_API_KEY"] == FAKE_KEY

    def test_an_example_a_dotenv_star_rule_hid_is_made_visible(self, tmp_path: Path) -> None:
        """`create-next-app` ignores `.env*`, which hides the example from review, commit and clone."""
        project = self.project(tmp_path, example=None)
        (project / ".gitignore").write_text("node_modules\n.env*\n", encoding="utf-8")
        result = _run(WRITE_ENV_FILE, str(project), cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert subprocess.run(["git", "-C", str(project), "check-ignore", "-q", ".env.example"], check=False).returncode == 1
        assert subprocess.run(["git", "-C", str(project), "check-ignore", "-q", ".env"], check=False).returncode == 0
        assert (project / ".gitignore").read_text(encoding="utf-8") == "node_modules\n.env*\n\n!.env.example\n"

    @pytest.mark.parametrize("inherited", ["shellopts", "bash-env"])
    def test_an_inherited_trace_prints_no_value(self, tmp_path: Path, inherited: str) -> None:
        """Bash starts traced when the environment carries `SHELLOPTS=xtrace` or a `BASH_ENV` that sets
        it, and a trace prints each command with its variables expanded."""
        project = self.project(tmp_path)
        environment = _environment({"PIPELEX_API_KEY": FAKE_KEY, "PIPELEX_BASE_URL": FAKE_URL})
        if inherited == "shellopts":
            environment["SHELLOPTS"] = "xtrace"
        else:
            startup = tmp_path / "startup.sh"
            startup.write_text("set -x\n", encoding="utf-8")
            environment["BASH_ENV"] = str(startup)
        result = _run(WRITE_ENV_FILE, str(project), cwd=tmp_path, env=environment)
        assert result.stdout == "filled base-url=copied plane=other\n"
        for value in (FAKE_KEY, FAKE_URL):
            assert value not in result.stdout and value not in result.stderr

    @pytest.mark.parametrize(
        "credentials",
        [{"PIPELEX_API_KEY": FAKE_KEY, "PIPELEX_BASE_URL": FAKE_URL}, {"PIPELEX_API_KEY": FAKE_KEY}, {"PIPELEX_BASE_URL": FAKE_URL}],
        ids=["both", "key", "url"],
    )
    def test_no_value_is_ever_printed(self, tmp_path: Path, credentials: dict[str, str]) -> None:
        """A value on either stream lands in the transcript, and a key there is a key to rotate."""
        project = self.project(tmp_path)
        result = _run(WRITE_ENV_FILE, str(project), cwd=tmp_path, credentials=credentials)
        for value in credentials.values():
            assert value not in result.stdout and value not in result.stderr

    def test_an_example_the_initializer_wrote_keeps_its_own_lines(self, tmp_path: Path) -> None:
        project = self.project(tmp_path, "DATABASE_URL=\n")
        result = _run(WRITE_ENV_FILE, str(project), cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert (project / ".env.example").read_text(encoding="utf-8") == f"DATABASE_URL=\n\nPIPELEX_BASE_URL={PRODUCTION_URL}\nPIPELEX_API_KEY=\n"

    def test_an_example_that_already_names_pipelex_is_left_alone(self, tmp_path: Path) -> None:
        shipped = f"# Pipelex\nPIPELEX_BASE_URL={PRODUCTION_URL}\nPIPELEX_API_KEY=\nOTHER=1\n"
        project = self.project(tmp_path, shipped)
        _run(WRITE_ENV_FILE, str(project), cwd=tmp_path)
        assert (project / ".env.example").read_text(encoding="utf-8") == shipped

    def test_an_env_file_git_already_tracks_gets_no_key(self, tmp_path: Path) -> None:
        """No ignore rule reaches a tracked file, so a `.env` the initializer wrote and the pristine commit
        took stays tracked whatever `.gitignore` says. A key written there would ride the user's next
        commit, so the script reads the verdict back from git and writes nothing."""
        project = self.project(tmp_path)
        (project / ".env").write_text("PIPELEX_API_KEY=\n", encoding="utf-8")
        _git(project, "add", ".env")
        _git(project, "commit", "-q", "-m", "an initializer that commits its .env")
        result = _run(WRITE_ENV_FILE, str(project), cwd=tmp_path, credentials={"PIPELEX_API_KEY": FAKE_KEY})
        assert result.stdout == "refused: not-ignored\n"
        assert result.returncode == 1
        assert FAKE_KEY not in (project / ".env").read_text(encoding="utf-8")

    @pytest.mark.parametrize("where", ["global-excludes", "info-exclude"])
    def test_an_ignore_rule_only_this_machine_carries_is_not_the_project_s(self, tmp_path: Path, where: str) -> None:
        """Phase 5a's smoke sessions: a developer's global excludes file ignored `.env`, so the project got
        no line of its own, and a teammate's clone would have taken the key with its next `git add`."""
        project = self.project(tmp_path)
        environment = _environment({"PIPELEX_API_KEY": FAKE_KEY})
        _ignored_only_on_this_machine(tmp_path, project, where, ".env", environment)
        result = _run(WRITE_ENV_FILE, str(project), cwd=tmp_path, env=environment)
        assert result.stdout == "filled base-url=file plane=production\n"
        assert (project / ".gitignore").read_text(encoding="utf-8") == "\n.env\n"

    def test_outside_a_repository_nothing_is_written(self, tmp_path: Path) -> None:
        project = tmp_path / "loose"
        project.mkdir()
        result = _run(WRITE_ENV_FILE, str(project), cwd=tmp_path, credentials={"PIPELEX_API_KEY": FAKE_KEY})
        assert result.stdout == "refused: not-a-repository\n"
        assert list(project.iterdir()) == []

    @pytest.mark.parametrize(("arguments", "verdict"), [((), "usage"), (("no-such-dir",), "no-directory")], ids=["no-arguments", "no-directory"])
    def test_a_mistyped_command_is_refused(self, tmp_path: Path, arguments: tuple[str, ...], verdict: str) -> None:
        assert _run(WRITE_ENV_FILE, *arguments, cwd=tmp_path).stdout == f"refused: {verdict}\n"


@pytest.mark.parametrize("script", [COMMIT_PRISTINE, WRITE_ENV_FILE], ids=lambda path: path.name)
def test_an_exported_cdpath_never_moves_the_directory(tmp_path: Path, script: Path) -> None:
    """`cd` searches `CDPATH` before the working directory, so a same-named directory elsewhere would
    be the one resolved, and printed onto the resolved path."""
    decoy = tmp_path / "elsewhere" / "app"
    decoy.mkdir(parents=True)
    project = _repository(tmp_path / "work" / "app")
    (project / "main.py").write_text("\n", encoding="utf-8")
    environment = _environment()
    environment["CDPATH"] = str(tmp_path / "elsewhere")
    arguments = ("app", "Scaffold Python project") if script == COMMIT_PRISTINE else ("app",)
    result = _run(script, *arguments, cwd=tmp_path / "work", env=environment)
    assert result.returncode == 0, result.stdout + result.stderr
    assert list(decoy.iterdir()) == []
    assert (project / ".gitignore").is_file()


@pytest.mark.parametrize("script", [COMMIT_PRISTINE, WRITE_ENV_FILE], ids=lambda path: path.name)
def test_each_script_says_what_it_prints_and_is_executable(script: Path) -> None:
    """The stop table keys on the verdict words, so each script's header states them, and the build keeps
    the executable bit it ships with."""
    header = script.read_text(encoding="utf-8").split("\nset -u\n", 1)[0]
    assert header.startswith("#!/usr/bin/env bash\n")
    assert "refused: <reason>" in header
    assert "The exit code is presentation" in header
    assert os.access(script, os.X_OK)
