"""Execute the scripts `pipelex-scaffold` runs by path for the method app: `read-copy-git.mjs` and `method-app.mjs`.

`read-copy-git.mjs` reads where a copy of the method app stands in git and gives it a repository only where the
family's initializer would. `method-app.mjs` reads the user's values from a request file and runs the family's
initializer (`init`) or the copy's own `npm run create` (`create`), installing the copy's dependencies first when
they are missing, with the gesture's output in a log and its warnings listed once each. They replaced bash blocks
and POSIX-quoted command lines, which a Windows machine with PowerShell alone could not run (L-261126-54e9af), so the
suite runs them as a user's harness does, through `node`, and is marked `cross_os`. The skill's side, which keys on
their verdicts, is pinned in `test_pipelex_scaffold_skill.py`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]
SCRIPTS = REPO_ROOT / "skills" / "pipelex-scaffold" / "scripts"
READ_COPY_GIT = SCRIPTS / "read-copy-git.mjs"
METHOD_APP = SCRIPTS / "method-app.mjs"
REQUEST_FILE = "pipelex-scaffold-request.json"
WINDOWS = os.name == "nt"

# The pristine commit's subject, as `pipelex-sdk`'s initializer writes it (`method-apps/initializers/js/lib/git.mjs`,
# `pristineMessage`), and as it wrote it from `pipelex-method-apps` before the move, which a copy made then keeps.
PRISTINE_SUBJECT_PREFIX = "Start from Pipelex/pipelex-sdk/method-apps/webapp-js "
PRISTINE_SUBJECT_PREFIX_BEFORE_THE_MOVE = "Start from Pipelex/pipelex-method-apps/webapp-js "
INSIDE = "inside: "
MADE_NOW = " (a repository made now on main)"

# A stand-in for the template's `scripts/create.mts`: like it, it loads a dependency as it starts, so it fails in a
# copy whose dependencies are not installed; it records how it was run, prints a long log with the gesture's
# warnings early on both streams and twice, as the bootstrap's dry run and write print them, then sixty lines of
# `npm run all`, and exits with the code the test asks for.
FAKE_CREATE = """\
const fs = require("node:fs");
require("fake-dep");
fs.writeFileSync(process.env.RECORD, JSON.stringify({ args: process.argv.slice(2), cwd: process.cwd(), initCwd: process.env.INIT_CWD }));
const warn = process.env.WARN === "1";
console.log("create: Receipt Review");
if (warn) console.log("! a method_id is scoped to your key's organization.");
if (warn) console.error("warning: LICENSE copyright line left untouched — pass --license-holder to claim it.");
console.log("create: 2/6 run the bootstrap with the values above");
if (warn) console.error("warning: LICENSE copyright line left untouched — pass --license-holder to claim it.");
for (let step = 0; step < 60; step++) console.log(`npm run all: step ${step}`);
process.exitCode = Number(process.env.EXIT_CODE ?? "0");
"""
SCOPE_WARNING = "! a method_id is scoped to your key's organization."
# A value holding what bash, PowerShell or cmd.exe reads as syntax: quotes of each kind, POSIX's quote escape,
# expansions, a backtick, separators, redirections and cmd's variables.
HOSTILE = """O'Brien's "app" '\\'' ‘curly’ $(whoami) ${HOME} $env:PATH `id` ; & && | || < > %PATH% ^ ! é"""
LICENSE_WARNING = "warning: LICENSE copyright line left untouched — pass --license-holder to claim it."

pytestmark = [
    pytest.mark.cross_os,
    pytest.mark.skipif(shutil.which("git") is None or shutil.which("node") is None, reason="the scripts are Node over git and npm"),
]


def _environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The test process's environment without credentials, npm's own variables or git configuration of the machine's.

    A fixed identity makes a commit deterministic in CI, `NODE_OPTIONS` and `NODE_DEBUG` are dropped so that no
    preloaded module can change what a script does, and npm's update notice is turned off so that it never lands in a log.
    """
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith(("PIPELEX_", "NPM_", "GIT_")) and name not in {"NODE_OPTIONS", "NODE_DEBUG", "INIT_CWD"}
    }
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            "npm_config_update_notifier": "false",
            "npm_config_fund": "false",
        }
    )
    environment.update(extra or {})
    return environment


def _node(script: Path, *arguments: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(script), *arguments],
        cwd=cwd,
        env=env if env is not None else _environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=120,
    )


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.run(["git", "-C", str(repository), *arguments], env=_environment(), capture_output=True, text=True, check=True).stdout


def _commit(repository: Path, message: str) -> None:
    subprocess.run(["git", "-C", str(repository), "commit", "-q", "-m", message], env=_environment(), check=True)


def _repository(path: Path, branch: str = "main") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", branch)
    return path


def _committed_copy(target: Path, *subjects: str) -> None:
    _repository(target)
    for number, subject in enumerate(subjects):
        (target / f"file-{number}.txt").write_text(f"{number}\n", encoding="utf-8")
        _git(target, "add", "-A", "--", ".")
        _commit(target, subject)


def _user_repository(parent: Path) -> Path:
    """A repository of the user's, on its own branch, with history of its own."""
    _repository(parent, branch="trunk")
    (parent / "README.md").write_text("theirs\n", encoding="utf-8")
    _git(parent, "add", "README.md")
    _commit(parent, "the user's own history")
    return parent


def _copy(target: Path) -> Path:
    target.mkdir(parents=True)
    (target / "package.json").write_text('{"name": "pipelex-method-webapp-js"}\n', encoding="utf-8")
    return target


def _names(printed: str, expected: Path) -> bool:
    """Whether a path a script printed is `expected`: git prints forward slashes on Windows, and a temporary
    directory may be reached through a symlink, `/var` to `/private/var` on macOS."""
    return Path(printed).resolve() == expected.resolve()


def _fake_project(directory: Path, dependency: str = "file:./fake-dep") -> Path:
    """A copy whose `create` script needs its dependency installed, which is a local package, so no install
    reaches the network."""
    directory.mkdir(parents=True)
    (directory / "package.json").write_text(
        json.dumps(
            {
                "name": "pipelex-method-webapp-js",
                "version": "0.0.0",
                "private": True,
                "dependencies": {"fake-dep": dependency},
                "scripts": {"create": "node create.js"},
            }
        ),
        encoding="utf-8",
    )
    (directory / "create.js").write_text(FAKE_CREATE, encoding="utf-8")
    (directory / "fake-dep").mkdir()
    (directory / "fake-dep" / "package.json").write_text('{"name": "fake-dep", "version": "1.0.0", "main": "index.js"}\n', encoding="utf-8")
    (directory / "fake-dep" / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")
    return directory


def _request(where: Path, payload: object) -> Path:
    """The request the agent writes with its file tools, in the directory the script runs in."""
    request = where / REQUEST_FILE
    request.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
    return request


def _log_of(stdout: str) -> Path:
    return Path(stdout.splitlines()[-1].split("; the whole log is ", 1)[1])


# A stand-in for npm's own `npm-cli.js`, which the script runs when `npm_execpath` names it: it records the
# arguments it was given and where it ran, prints a verdict line as the family's initializer would, and exits with
# the code the test asks for.
FAKE_NPM_CLI = """\
const fs = require("node:fs");
fs.writeFileSync(process.env.RECORD, JSON.stringify({ args: process.argv.slice(2), cwd: process.cwd(), gitDir: process.env.GIT_DIR ?? null }));
console.log("created somewhere; next: npm run serve");
process.exitCode = Number(process.env.EXIT_CODE ?? "0");
"""


class TestUncreatedCopyScripts:
    @pytest.mark.parametrize(
        "subject",
        [
            f"{PRISTINE_SUBJECT_PREFIX}0.4.0 (2598d4e)",
            f"{PRISTINE_SUBJECT_PREFIX}0.4.0",
            f"{PRISTINE_SUBJECT_PREFIX_BEFORE_THE_MOVE}0.4.0 (2598d4e)",
            f"{PRISTINE_SUBJECT_PREFIX_BEFORE_THE_MOVE}0.4.0",
        ],
        ids=["the-initializer-s", "made-by-hand", "the-initializer-s-before-the-move", "made-by-hand-before-the-move"],
    )
    def test_a_copy_already_committed_names_its_pristine_commit(self, tmp_path: Path, subject: str) -> None:
        """A user standing in a copy seldom says who made it, so its history is read first, under a later commit too."""
        target = tmp_path / "receipt review"
        _committed_copy(target, subject, "the user's own change")
        pristine = _git(target, "log", "--format=%h", "-1", "HEAD~1").strip()
        result = _node(READ_COPY_GIT, "receipt review", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert result.stdout == f"pristine: {pristine} {subject}\n"

    @pytest.mark.parametrize(
        "subject",
        ["Start from Pipelex/pipelex-sdk-js/webapp-js 0.4.0", "Start from Pipelex/pipelex-sdk/method-apps/webapp-jsx 0.4.0", "the user's copy"],
        ids=["a-sibling-repository", "a-sibling-template", "another-history"],
    )
    def test_any_other_history_is_the_user_s(self, tmp_path: Path, subject: str) -> None:
        target = tmp_path / "receipt-review"
        _committed_copy(target, subject)
        before = _git(target, "log", "--format=%H")
        result = _node(READ_COPY_GIT, str(target), cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        verdict, printed = result.stdout.rstrip("\n").split(" ", 1)
        assert verdict == "history:"
        assert _names(printed, target)
        assert _git(target, "log", "--format=%H") == before

    def test_a_pristine_commit_of_an_enclosing_repository_is_not_the_copy_s(self, tmp_path: Path) -> None:
        """Only a copy at its repository's root is read for the pristine commit: the monorepo's is another project's."""
        monorepo = tmp_path / "monorepo"
        _committed_copy(monorepo, f"{PRISTINE_SUBJECT_PREFIX}0.4.0 (2598d4e)")
        target = _copy(monorepo / "apps" / "receipt-review")
        result = _node(READ_COPY_GIT, str(target), cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith(INSIDE)
        assert _names(result.stdout[len(INSIDE) :].rstrip("\n"), monorepo)
        assert not (target / ".git").exists()

    def test_a_copy_outside_every_repository_gets_one_on_main(self, tmp_path: Path) -> None:
        target = _copy(tmp_path / "receipt review")
        result = _node(READ_COPY_GIT, str(target), cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("no-commit: ") and result.stdout.endswith(f"{MADE_NOW}\n")
        assert _names(result.stdout[len("no-commit: ") : -len(MADE_NOW) - 1], target)
        assert (target / ".git").is_dir()
        assert _git(target, "symbolic-ref", "--short", "HEAD").strip() == "main"
        # The repository is the copy's alone, with no commit: the reference makes the pristine one after a confirmation.
        assert subprocess.run(["git", "-C", str(target), "rev-parse", "-q", "--verify", "HEAD"], env=_environment(), check=False).returncode != 0

    def test_a_repository_the_user_made_with_no_commit_is_left_for_the_pristine_commit(self, tmp_path: Path) -> None:
        target = _copy(tmp_path / "receipt-review")
        _repository(target, branch="trunk")
        result = _node(READ_COPY_GIT, str(target), cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("no-commit: ") and MADE_NOW not in result.stdout
        assert _git(target, "symbolic-ref", "--short", "HEAD").strip() == "trunk"

    def test_a_copy_inside_another_repository_gets_none_of_its_own(self, tmp_path: Path) -> None:
        """The initializer plants no repository inside another's work tree, so a later session that meets
        its copy there, after `--no-create` or `failed: create`, plants none either."""
        parent = _user_repository(tmp_path / "monorepo")
        history = _git(parent, "log", "--format=%H")
        target = _copy(parent / "apps" / "receipt-review")
        result = _node(READ_COPY_GIT, str(target), cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith(INSIDE)
        assert _names(result.stdout[len(INSIDE) :].rstrip("\n"), parent)
        assert not (target / ".git").exists()
        assert _git(parent, "log", "--format=%H") == history
        assert _git(parent, "diff", "--cached", "--name-only") == ""

    @pytest.mark.parametrize(("rule", "own_repository"), [("apps/\n", True), ("*\n!*/\n", False)], ids=["ignored", "every-file-ignored"])
    def test_a_copy_the_enclosing_repository_ignores_gets_one_of_its_own(self, tmp_path: Path, rule: str, own_repository: bool) -> None:
        """Ruled 2026-09-25: a copy under an ignored path gets a repository of its own, as the initializer gives it.
        What counts is the directory: one the enclosing repository sees, though it ignores every file in it, gets
        none, since a repository there would show."""
        parent = _user_repository(tmp_path / "monorepo")
        (parent / ".gitignore").write_text(rule, encoding="utf-8")
        target = _copy(parent / "apps" / "receipt-review")
        result = _node(READ_COPY_GIT, str(target), cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        if own_repository:
            assert result.stdout.endswith(f"{MADE_NOW}\n")
            assert _names(_git(target, "rev-parse", "--show-toplevel").strip(), target)
            assert _git(target, "symbolic-ref", "--short", "HEAD").strip() == "main"
        else:
            assert result.stdout.startswith(INSIDE)
            assert not (target / ".git").exists()
        assert _git(parent, "status", "--porcelain", "--untracked-files=all", "--", "apps") == ""

    @staticmethod
    def _repository_tracking_a_copy(root: Path, origin: str) -> Path:
        """A repository with `origin` set that tracks a method-app copy in `webapp-js/`, as the family does."""
        _repository(root)
        _git(root, "remote", "add", "origin", origin)
        copy = _copy(root / "webapp-js")
        (copy / "scripts").mkdir()
        (copy / "scripts" / "create.mts").write_text("// the create gesture\n", encoding="utf-8")
        _git(root, "add", "-A")
        _commit(root, "the family as it came")
        return copy

    @pytest.mark.parametrize(
        "origin",
        [
            "https://github.com/Pipelex/pipelex-sdk.git",
            "https://github.com/Pipelex/pipelex-sdk",
            "git@github.com:Pipelex/pipelex-sdk.git",
            "git@github.com:pipelex/pipelex-sdk.git/",
            "https://github.com/Pipelex/pipelex-method-apps.git",
            "git@github.com:Pipelex/pipelex-method-apps.git",
        ],
        ids=["https", "https-without-suffix", "ssh", "ssh-lowercase-with-slash", "https-before-the-move", "ssh-before-the-move"],
    )
    def test_the_template_s_own_checkout_is_refused_and_left_alone(self, tmp_path: Path, origin: str) -> None:
        family = tmp_path / "template-repository"
        copy = self._repository_tracking_a_copy(family, origin)
        result = _node(READ_COPY_GIT, str(copy), cwd=tmp_path)
        assert result.stdout == "refused: template-checkout\n"
        assert result.returncode == 1
        assert "template's own checkout" in result.stderr
        assert not (copy / ".git").exists()
        assert _git(family, "status", "--porcelain") == ""

    @pytest.mark.parametrize(
        "origin",
        [
            "https://github.com/someone/pipelex-method-apps.git",
            "https://github.com/Pipelex/pipelex-sdk-js.git",
            "https://github.com/Pipelex/pipelex-sdk.wiki.git",
            "https://gitlab.com/Pipelex/pipelex-sdk/other.git",
        ],
        ids=["a-fork", "a-sibling-of-the-template-s-repository", "the-template-s-wiki", "a-repository-nested-under-its-name"],
    )
    def test_a_directory_another_repository_tracks_is_refused_whatever_its_origin(self, tmp_path: Path, origin: str) -> None:
        """A fork of the family under another owner carries no Pipelex origin, and is still not a fresh copy; a
        repository whose name only begins like the template's is not the template, and is refused the same way."""
        fork = tmp_path / "our-apps"
        copy = self._repository_tracking_a_copy(fork, origin)
        result = _node(READ_COPY_GIT, str(copy), cwd=tmp_path)
        assert result.returncode == 1
        assert result.stdout.startswith("refused: tracked ")
        assert _names(result.stdout.rstrip("\n")[len("refused: tracked ") :], fork)
        assert "already tracks this directory" in result.stderr
        assert not (copy / ".git").exists()

    @pytest.mark.parametrize("through_symlink", [False, True], ids=["direct", "through-a-symlink"])
    def test_a_copy_that_is_its_own_repository_is_left_alone(self, tmp_path: Path, through_symlink: bool) -> None:
        real = tmp_path / "real"
        target = _copy(real / "receipt-review")
        _repository(target, branch="trunk")
        _git(target, "add", "package.json")
        _commit(target, "the user's copy")
        before = (_git(target, "log", "--format=%H"), _git(target, "reflog"), _git(target, "rev-parse", "--abbrev-ref", "HEAD"))
        spelled = target
        if through_symlink:
            try:
                (tmp_path / "linked").symlink_to(real, target_is_directory=True)
            except OSError:
                pytest.skip("this machine does not let the test make a symlink")
            spelled = tmp_path / "linked" / "receipt-review"
        result = _node(READ_COPY_GIT, str(spelled), cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("history: ")
        assert (_git(target, "log", "--format=%H"), _git(target, "reflog"), _git(target, "rev-parse", "--abbrev-ref", "HEAD")) == before

    @pytest.mark.parametrize(
        ("arguments", "verdict"), [((), "usage"), (("",), "usage"), (("a", "b"), "usage"), (("missing",), "no-directory")], ids=str
    )
    def test_a_mistyped_reading_is_refused(self, tmp_path: Path, arguments: tuple[str, ...], verdict: str) -> None:
        result = _node(READ_COPY_GIT, *arguments, cwd=tmp_path)
        assert result.stdout == f"refused: {verdict}\n"
        assert result.returncode == 1
        assert not (tmp_path / ".git").exists()

    def test_git_sees_no_pipelex_variable(self, tmp_path: Path) -> None:
        """The key a shell exports never reaches git's environment, which Node's debug log prints with the spawn."""
        target = _copy(tmp_path / "receipt-review")
        fake_key = "plx_fake_key_for_tests_0000"
        environment = _environment({"PIPELEX_API_KEY": fake_key, "NODE_DEBUG": "child_process"})
        result = _node(READ_COPY_GIT, str(target), cwd=tmp_path, env=environment)
        assert result.returncode == 0, result.stderr
        assert fake_key not in result.stdout + result.stderr

    def test_a_ceiling_the_environment_carries_never_plants_a_repository_in_the_user_s(self, tmp_path: Path) -> None:
        """Under a `GIT_CEILING_DIRECTORIES` naming the user's repository, git says "not a git repository" with a
        repository above, as it does at a mount point; the reading searches past both, so the copy stays new files
        of the user's repository."""
        parent = _user_repository(tmp_path / "monorepo")
        target = _copy(parent / "apps" / "receipt-review")
        environment = _environment({"GIT_CEILING_DIRECTORIES": str(parent)})
        result = _node(READ_COPY_GIT, str(target), cwd=tmp_path, env=environment)
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith(INSIDE)
        assert _names(result.stdout[len(INSIDE) :].rstrip("\n"), parent)
        assert not (target / ".git").exists()

    # read-copy-git.mjs: git that cannot read the directory, and a git pointed elsewhere

    @pytest.mark.parametrize("where", ["a-gitfile-git-cannot-read", "inside-a-dot-git"])
    def test_a_directory_git_cannot_read_is_refused_and_never_initialized(self, tmp_path: Path, where: str) -> None:
        """Only git's "not a git repository" means outside every one; any other failure of `rev-parse`, such as a
        `.git` file git cannot read or a directory inside a `.git`, is refused with git's message, since a
        repository initialized there would sit inside one git could not read."""
        if where == "a-gitfile-git-cannot-read":
            target = _copy(tmp_path / "receipt-review")
            (target / ".git").write_text("not a gitfile\n", encoding="utf-8")
        else:
            repository = _repository(tmp_path / "repository")
            target = _copy(repository / ".git" / "receipt-review")
        result = _node(READ_COPY_GIT, str(target), cwd=tmp_path)
        assert result.stdout == "refused: git-failed\n"
        assert result.returncode == 1
        assert result.stderr.strip(), "git's own message is relayed on standard error"
        assert not (target / ".git").is_dir()

    def test_a_git_dir_the_environment_carries_is_ignored(self, tmp_path: Path) -> None:
        """A hook or a wrapper can leave `GIT_DIR` and `GIT_WORK_TREE` set; the reading is about the copy, as the
        family's initializer makes it, so a copy outside every repository still gets its own."""
        elsewhere = _user_repository(tmp_path / "elsewhere")
        history = _git(elsewhere, "log", "--format=%H")
        target = _copy(tmp_path / "copies" / "receipt-review")
        environment = _environment({"GIT_DIR": str(elsewhere / ".git"), "GIT_WORK_TREE": str(elsewhere)})
        result = _node(READ_COPY_GIT, str(target), cwd=tmp_path, env=environment)
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("no-commit: ") and result.stdout.endswith(f"{MADE_NOW}\n")
        assert (target / ".git").is_dir()
        assert _git(elsewhere, "log", "--format=%H") == history

    # method-app.mjs: the request

    @pytest.mark.parametrize(
        ("command", "payload", "message"),
        [
            ("create", "{not json", "is not JSON"),
            ("create", [], "not a JSON object"),
            ("create", {"dir": "receipt-review"}, '"method" must be a string'),
            ("create", {"dir": "receipt-review", "method": "  "}, '"method" must be a string'),
            ("create", {"dir": "", "method": "mt_receipt"}, '"dir" must be a string'),
            ("create", {"dir": "receipt-review", "method": "mt_receipt", "extra": 1}, '"extra" is not a field'),
            ("create", {"dir": "receipt-review", "method": "mt_receipt", "options": {"bogus": "x"}}, '"bogus" is not an option of create'),
            ("create", {"dir": "receipt-review", "method": "mt_receipt", "options": {"no-create": True}}, '"no-create" is not an option of create'),
            ("init", {"dir": "receipt-review", "method": "mt_receipt", "options": {"dry-run": "yes"}}, '"dry-run" is a switch'),
            ("init", {"dir": "receipt-review", "method": "mt_receipt", "options": {"title": 3}}, '"title" must be a string'),
            ("init", {"dir": "receipt-review", "method": "mt_receipt", "options": {"title": "a\nb"}}, '"title" holds a line break'),
            ("init", {"dir": "receipt-review", "method": "mt_receipt", "options": []}, '"options" is not a JSON object'),
        ],
        ids=lambda value: value if isinstance(value, str) and len(value) < 30 else None,
    )
    def test_a_malformed_request_is_refused_and_removed(self, tmp_path: Path, command: str, payload: object, message: str) -> None:
        """The request is removed whatever it holds, so the next run reads only the request written for it."""
        (tmp_path / "receipt-review").mkdir()
        request = _request(tmp_path, payload)
        result = _node(METHOD_APP, command, cwd=tmp_path, env=_environment({"npm_execpath": str(tmp_path / "npm-cli.js")}))
        assert result.stdout == "refused: bad-request\n"
        assert result.returncode == 1
        assert message in result.stderr
        assert not request.exists()

    @pytest.mark.parametrize("arguments", [(), ("serve",), ("create", "receipt-review"), ("init", "mt_receipt")], ids=str)
    def test_a_value_on_the_command_line_is_refused(self, tmp_path: Path, arguments: tuple[str, ...]) -> None:
        """The scripts take no value on their command line, where no quoting reads alike in every shell."""
        request = _request(tmp_path, {"dir": "receipt-review", "method": "mt_receipt"})
        result = _node(METHOD_APP, *arguments, cwd=tmp_path)
        assert result.stdout == "refused: usage\n"
        assert result.returncode == 1
        assert request.exists(), "a refused command line reads no request"

    @pytest.mark.parametrize("command", ["init", "create"])
    def test_a_missing_request_names_where_it_was_looked_for(self, tmp_path: Path, command: str) -> None:
        result = _node(METHOD_APP, command, cwd=tmp_path)
        assert result.returncode == 1
        assert result.stdout.startswith("refused: no-request ")
        assert _names(result.stdout.rstrip("\n")[len("refused: no-request ") :], tmp_path / REQUEST_FILE)

    @pytest.mark.parametrize("command", ["init", "create"])
    @pytest.mark.parametrize("setting", ["child_process", "fs,CHILD_PROCESS", "child*", "*"])
    def test_node_s_child_process_log_is_refused_before_anything_spawns(self, tmp_path: Path, command: str, setting: str) -> None:
        """npm's environment carries the key, which the gesture reads, and Node's child_process log prints a spawn's
        environment on stderr, so the script refuses to spawn while the log is on, matched as Node matches it, and
        keeps the request, which it has not read."""
        (tmp_path / "receipt-review").mkdir()
        cli = tmp_path / "npm-cli.js"
        cli.write_text(FAKE_NPM_CLI, encoding="utf-8")
        record = tmp_path / "record.json"
        request = _request(tmp_path, {"dir": "receipt-review", "method": "mt_receipt"})
        fake_key = "plx_fake_key_for_tests_0000"
        environment = _environment({"npm_execpath": str(cli), "RECORD": str(record), "PIPELEX_API_KEY": fake_key, "NODE_DEBUG": setting})
        result = _node(METHOD_APP, command, cwd=tmp_path, env=environment)
        assert result.stdout == "refused: node-debug\n"
        assert result.returncode == 1
        assert "NODE_DEBUG" in result.stderr
        assert fake_key not in result.stdout + result.stderr
        assert request.exists()
        assert not record.exists(), "npm was started"

    def test_another_node_debug_log_is_no_refusal(self, tmp_path: Path) -> None:
        cli = tmp_path / "npm-cli.js"
        cli.write_text(FAKE_NPM_CLI, encoding="utf-8")
        record = tmp_path / "record.json"
        _request(tmp_path, {"dir": "receipt-review", "method": "mt_receipt"})
        environment = _environment({"npm_execpath": str(cli), "RECORD": str(record), "NODE_DEBUG": "http,net"})
        result = _node(METHOD_APP, "init", cwd=tmp_path, env=environment)
        assert result.returncode == 0, result.stderr
        assert result.stdout == "created somewhere; next: npm run serve\n"
        assert record.exists()

    # method-app.mjs init

    @pytest.mark.parametrize("exit_code", [0, 1])
    def test_init_hands_every_value_to_the_initializer_as_one_argument(self, tmp_path: Path, exit_code: int) -> None:
        """Every value reaches npm as written, whatever a shell would have read in it, the directory and a bundle the
        working directory holds as absolute paths, the switches after the options and `--quiet` last; the
        initializer's output and exit code pass through untouched, and git's redirections never reach npm."""
        (tmp_path / "my methods").mkdir()
        (tmp_path / "my methods" / "receipt.mthds").write_text("domain = 'receipt'\n", encoding="utf-8")
        cli = tmp_path / "npm" / "npm-cli.js"
        cli.parent.mkdir()
        cli.write_text(FAKE_NPM_CLI, encoding="utf-8")
        record = tmp_path / "record.json"
        request = _request(
            tmp_path,
            {
                "dir": "O'Brien app",
                "method": "my methods/receipt.mthds",
                "options": {"title": HOSTILE, "author-name": "Mary O'Brien", "license-holder": "", "dry-run": True, "no-create": False},
            },
        )
        environment = _environment(
            {"npm_execpath": str(cli), "RECORD": str(record), "EXIT_CODE": str(exit_code), "GIT_DIR": str(tmp_path / "elsewhere")}
        )
        result = _node(METHOD_APP, "init", cwd=tmp_path, env=environment)
        assert result.returncode == exit_code, result.stderr
        assert result.stdout == "created somewhere; next: npm run serve\n"
        assert not request.exists()
        recorded = json.loads(record.read_text(encoding="utf-8"))
        args = recorded["args"]
        assert args[:3] == ["create", "--yes", "@pipelex/method-app@latest"]
        assert _names(args[3], tmp_path / "O'Brien app")
        assert args[4:6] == ["--", "--method"]
        assert _names(args[6], tmp_path / "my methods" / "receipt.mthds")
        assert args[7:] == ["--title", HOSTILE, "--author-name", "Mary O'Brien", "--dry-run", "--quiet"]
        assert _names(recorded["cwd"], tmp_path)
        assert recorded["gitDir"] is None

    def test_init_passes_a_catalog_id_or_an_address_as_written(self, tmp_path: Path) -> None:
        cli = tmp_path / "npm-cli.js"
        cli.write_text(FAKE_NPM_CLI, encoding="utf-8")
        record = tmp_path / "record.json"
        _request(tmp_path, {"dir": "receipt-review", "method": "github.com/acme/methods/receipt@v1", "options": {"no-create": True}})
        result = _node(METHOD_APP, "init", cwd=tmp_path, env=_environment({"npm_execpath": str(cli), "RECORD": str(record)}))
        assert result.returncode == 0, result.stderr
        args = json.loads(record.read_text(encoding="utf-8"))["args"]
        assert args[6:] == ["github.com/acme/methods/receipt@v1", "--no-create", "--quiet"]

    # method-app.mjs create

    @pytest.mark.skipif(shutil.which("npm") is None, reason="the gesture runs through npm")
    @pytest.mark.parametrize("exit_code", [0, 3])
    def test_create_installs_then_runs_the_gesture_with_every_value_as_one_argument(self, tmp_path: Path, exit_code: int) -> None:
        """A copy whose dependencies are not installed, as `--no-create` or a copy made by hand leaves it, gets
        `npm install` first, as the template's `make create` ran it, since the gesture loads its dependencies as it
        starts. Every value then reaches `npm run create` as written, a bundle the working directory holds as an
        absolute path, and the gesture runs in the copy. Its code is reported, never taken as the script's."""
        project = _fake_project(tmp_path / "O'Brien app")
        (tmp_path / "my methods").mkdir()
        (tmp_path / "my methods" / "receipt.mthds").write_text("domain = 'receipt'\n", encoding="utf-8")
        record = tmp_path / "record.json"
        request = _request(
            tmp_path, {"dir": "O'Brien app", "method": "my methods/receipt.mthds", "options": {"license-holder": HOSTILE, "title": " "}}
        )
        environment = _environment({"RECORD": str(record), "EXIT_CODE": str(exit_code)})
        result = _node(METHOD_APP, "create", cwd=tmp_path, env=environment)
        assert result.returncode == 0, result.stdout + result.stderr
        assert not request.exists()
        recorded = json.loads(record.read_text(encoding="utf-8"))
        assert _names(recorded["args"][0], tmp_path / "my methods" / "receipt.mthds")
        assert recorded["args"][1:] == ["--license-holder", HOSTILE]
        assert _names(recorded["cwd"], project)
        assert _names(recorded["initCwd"], tmp_path)
        assert (project / "node_modules" / ".package-lock.json").is_file()
        assert (project / "node_modules" / ".lock-installed").is_file()
        last = result.stdout.splitlines()[-1]
        assert last.startswith(f"npm run create exited {exit_code}; the whole log is ")
        log = _log_of(result.stdout)
        assert log.is_file() and log.name == "create.log" and log.parent.name.startswith("pipelex-create-")
        assert "npm run all: step 0" in log.read_text(encoding="utf-8")
        shutil.rmtree(log.parent)

    @pytest.mark.skipif(shutil.which("npm") is None, reason="the gesture runs through npm")
    def test_a_failed_install_stops_before_the_gesture(self, tmp_path: Path) -> None:
        _fake_project(tmp_path / "receipt-review", dependency="file:./missing-dep.tgz")
        record = tmp_path / "record.json"
        _request(tmp_path, {"dir": "receipt-review", "method": "mt_receipt"})
        result = _node(METHOD_APP, "create", cwd=tmp_path, env=_environment({"RECORD": str(record)}))
        assert result.returncode == 0, result.stdout + result.stderr
        last = result.stdout.splitlines()[-1]
        assert last.startswith("npm install exited ") and not last.startswith("npm install exited 0;")
        assert "warnings" not in result.stdout.splitlines()[-2]
        assert not record.exists(), "the gesture never started"
        shutil.rmtree(_log_of(result.stdout).parent)

    @pytest.mark.skipif(shutil.which("npm") is None, reason="the gesture runs through npm")
    def test_an_installed_copy_is_not_installed_again(self, tmp_path: Path) -> None:
        """npm's record of an install says the dependencies are there, so a copy the dry run or a first run
        installed goes straight to the gesture: an install here would fail on the dependency that is gone."""
        project = _fake_project(tmp_path / "receipt-review", dependency="file:./missing-dep.tgz")
        (project / "node_modules" / "fake-dep").mkdir(parents=True)
        (project / "node_modules" / "fake-dep" / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")
        (project / "node_modules" / ".package-lock.json").write_text("{}\n", encoding="utf-8")
        _request(tmp_path, {"dir": "receipt-review", "method": "mt_receipt"})
        result = _node(METHOD_APP, "create", cwd=tmp_path, env=_environment({"RECORD": str(tmp_path / "record.json")}))
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines()[-1].startswith("npm run create exited 0; ")
        shutil.rmtree(_log_of(result.stdout).parent)

    @pytest.mark.skipif(shutil.which("npm") is None, reason="the gesture runs through npm")
    def test_each_warning_the_gesture_printed_is_listed_once(self, tmp_path: Path) -> None:
        """The gesture's warnings come before `npm run all`, whose output fills the tail, and the bootstrap's come
        twice. The script lists each one once, in byte order, whatever stream it was on."""
        _fake_project(tmp_path / "receipt-review")
        _request(tmp_path, {"dir": "receipt-review", "method": "mt_receipt"})
        environment = _environment({"RECORD": str(tmp_path / "record.json"), "WARN": "1"})
        result = _node(METHOD_APP, "create", cwd=tmp_path, env=environment)
        assert result.returncode == 0, result.stdout + result.stderr
        lines = result.stdout.splitlines()
        listed = lines[lines.index("warnings:") + 1 : -1]
        assert listed == sorted([SCOPE_WARNING, LICENSE_WARNING], key=lambda line: line.encode("utf-8"))
        # The tail alone would have shown neither.
        tail = lines[: lines.index("warnings:")]
        assert len(tail) == 40
        assert tail[-1] == "npm run all: step 59"
        assert SCOPE_WARNING not in tail and LICENSE_WARNING not in tail
        shutil.rmtree(_log_of(result.stdout).parent)

    @pytest.mark.skipif(shutil.which("npm") is None, reason="the gesture runs through npm")
    def test_a_gesture_with_no_warning_says_so(self, tmp_path: Path) -> None:
        _fake_project(tmp_path / "receipt-review")
        _request(tmp_path, {"dir": "receipt-review", "method": "mt_receipt"})
        result = _node(METHOD_APP, "create", cwd=tmp_path, env=_environment({"RECORD": str(tmp_path / "record.json")}))
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines()[-2] == "warnings: none"
        shutil.rmtree(_log_of(result.stdout).parent)

    def test_create_refuses_a_directory_that_is_not_there(self, tmp_path: Path) -> None:
        request = _request(tmp_path, {"dir": "missing", "method": "mt_receipt"})
        result = _node(METHOD_APP, "create", cwd=tmp_path)
        assert result.stdout == "refused: no-directory\n"
        assert result.returncode == 1
        assert not request.exists()

    @pytest.mark.skipif(WINDOWS, reason="on Windows npm is an npm-cli.js run with node, not a name on the PATH")
    def test_an_npm_that_cannot_start_is_a_verdict(self, tmp_path: Path) -> None:
        node = shutil.which("node")
        assert node is not None
        _fake_project(tmp_path / "receipt-review")
        _request(tmp_path, {"dir": "receipt-review", "method": "mt_receipt"})
        empty = tmp_path / "empty-bin"
        empty.mkdir()
        result = subprocess.run(
            [node, str(METHOD_APP), "create"],
            cwd=tmp_path,
            env=_environment({"PATH": str(empty)}),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.stdout == "failed: npm\n"
        assert result.returncode == 1
        assert "ENOENT" in result.stderr

    @pytest.mark.skipif(shutil.which("npm") is None, reason="the gesture runs through npm")
    @pytest.mark.parametrize("named", ["pnpm.cjs", "yarn.js", "npx-cli.js"])
    def test_only_npm_s_own_script_is_taken_from_npm_execpath(self, tmp_path: Path, named: str) -> None:
        """pnpm, yarn and npx name scripts of their own in `npm_execpath`; the gesture is run with npm all the same,
        as the template's `scripts/lib/npm.mts` decides."""
        _fake_project(tmp_path / "receipt-review")
        impostor = tmp_path / named
        impostor.write_text(f'require("node:fs").writeFileSync({json.dumps(str(tmp_path / "impostor-ran"))}, "");\n', encoding="utf-8")
        _request(tmp_path, {"dir": "receipt-review", "method": "mt_receipt"})
        environment = _environment({"RECORD": str(tmp_path / "record.json"), "npm_execpath": str(impostor)})
        result = _node(METHOD_APP, "create", cwd=tmp_path, env=environment)
        assert result.returncode == 0, result.stdout + result.stderr
        assert not (tmp_path / "impostor-ran").exists()
        assert (tmp_path / "record.json").is_file(), "npm ran the gesture"
        shutil.rmtree(_log_of(result.stdout).parent)

    @pytest.mark.skipif(not WINDOWS, reason="Windows alone runs npm as an npm-cli.js found beside node.exe or an npm.cmd")
    def test_on_windows_npm_is_found_beside_an_npm_cmd_or_reported_missing(self, tmp_path: Path) -> None:
        """A node.exe with no npm beside it, as a version manager may lay it out, takes the `npm-cli.js` beside an
        `npm.cmd` on the PATH, and with none, `failed: npm` names what it looked for rather than an exit code that
        reads like the initializer's."""
        node = shutil.which("node")
        assert node is not None
        lone = tmp_path / "lone-node"
        lone.mkdir()
        shutil.copy2(node, lone / "node.exe")
        record = tmp_path / "record.json"
        empty = tmp_path / "empty-bin"
        empty.mkdir()
        _request(tmp_path, {"dir": "receipt-review", "method": "mt_receipt"})
        missing = subprocess.run(
            [str(lone / "node.exe"), str(METHOD_APP), "init"],
            cwd=tmp_path,
            env=_environment({"PATH": str(empty)}),
            capture_output=True,
            text=True,
            check=False,
        )
        assert missing.stdout == "failed: npm\n"
        assert missing.returncode == 1
        assert "npm-cli.js" in missing.stderr
        npm_home = tmp_path / "npm-home"
        (npm_home / "node_modules" / "npm" / "bin").mkdir(parents=True)
        (npm_home / "npm.cmd").write_text("@echo off\r\n", encoding="utf-8")
        (npm_home / "node_modules" / "npm" / "bin" / "npm-cli.js").write_text(FAKE_NPM_CLI, encoding="utf-8")
        _request(tmp_path, {"dir": "receipt-review", "method": "mt_receipt"})
        found = subprocess.run(
            [str(lone / "node.exe"), str(METHOD_APP), "init"],
            cwd=tmp_path,
            env=_environment({"PATH": f"{empty};{npm_home}", "RECORD": str(record)}),
            capture_output=True,
            text=True,
            check=False,
        )
        assert found.returncode == 0, found.stdout + found.stderr
        assert json.loads(record.read_text(encoding="utf-8"))["args"][:3] == ["create", "--yes", "@pipelex/method-app@latest"]

    @pytest.mark.parametrize("script", [READ_COPY_GIT, METHOD_APP], ids=lambda path: path.name)
    def test_each_script_says_what_it_prints_and_is_executable(self, script: Path) -> None:
        """The reference keys on the verdict words, so each script's header states them. The reference runs each
        through `node`, and the build keeps the executable bit it ships with for a direct run on macOS and Linux."""
        header = script.read_text(encoding="utf-8").split("\nimport ", 1)[0]
        assert header.startswith("#!/usr/bin/env node\n")
        assert f"// Usage: node {script.name} " in header
        assert "refused: <reason>" in header
        assert "The exit code is presentation" in header
        text = script.read_text(encoding="utf-8")
        assert "shell:" not in text, "a script spawns nothing through a shell"
        if not WINDOWS:
            assert os.access(script, os.X_OK)
