"""Pin the pipelex-scaffold skill: two branches, no templates of its own, one commit, and a key that never crosses the conversation.

The method app is the template family's own two commands, its initializer and `npm run serve`, whose programs
and tests live in `pipelex-sdk`'s `method-apps/`, and which run with no `make` on every OS. The initializer
branch's two scripts are executed in `test_pipelex_scaffold_scripts.py`, and the two scripts
`references/uncreated-copy.md` runs, for a copy of the template the initializer did not finish, in
`test_pipelex_scaffold_copy_scripts.py`. What this module executes is the report's plane test, a `node`
one-liner, in every shell the machine has.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.check import SKILL_CEILING_CHARS
from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir

REPO_ROOT = Path(__file__).parents[2]
SKILL_TEMPLATE = REPO_ROOT / "templates" / "skills" / "pipelex-scaffold" / "SKILL.md.j2"
REFERENCES_DIR = REPO_ROOT / "skills" / "pipelex-scaffold" / "references"
INITIALIZERS_REFERENCE = REFERENCES_DIR / "initializers.md"
UNCREATED_COPY_REFERENCE = REFERENCES_DIR / "uncreated-copy.md"

BASH_BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)
# The method app's two commands, each the whole of its block, and the uncreated copy's two blocks, each
# named by a string that occurs in exactly one of them.
# The method app's commands that carry the user's values take none on their command line: the agent writes them
# into a request file the script reads (L-261126-54e9af).
CREATE_COMMAND = 'node "<skill-dir>/scripts/method-app.mjs" init'
# The skill's directory as the template spells it, and as Claude Code and the other targets read it.
SKILL_DIR_SPELLINGS = ("{{ skill_dir }}", "${CLAUDE_SKILL_DIR}", "<skill-dir>")
REQUEST = '`{"dir": "<dir>", "method": "<method>", "options": {}}`'
SERVE_COMMAND = "npm --prefix '<dir>' run serve"
# The uncreated copy's three blocks: the git reading, the pristine commit and the gesture's run.
READ_COPY_GIT_COMMAND = "node \"<skill-dir>/scripts/read-copy-git.mjs\" '<dir>'"
RUN_CREATE_COMMAND = 'node "<skill-dir>/scripts/method-app.mjs" create'
# The pristine commit's subject, as `pipelex-sdk`'s initializer writes it (`method-apps/initializers/js/lib/git.mjs`,
# `pristineMessage`), and as it wrote it from `pipelex-method-apps` before the move, which a copy made then keeps.
PRISTINE_SUBJECT_PREFIX = "Start from Pipelex/pipelex-sdk/method-apps/webapp-js "
PRISTINE_SUBJECT_PREFIX_BEFORE_THE_MOVE = "Start from Pipelex/pipelex-method-apps/webapp-js "
PRISTINE_COPY_COMMIT = "git -C '<dir>' add -A -- .\ngit -C '<dir>' commit -m \"Start from Pipelex/pipelex-sdk/method-apps/webapp-js <version>\" -- ."
TARGETS = ("prod", "codex", "mistral-vibe")
# The method app's report reads the plane of the `.env.local` `npm run create` wrote with this test, a `node`
# one-liner every shell runs, since a POSIX `${VAR:-…}` test is no PowerShell command.
PLANE_TEST = (
    "node -p \"['','https://api.pipelex.com','https://api.pipelex.com/'].includes(process.env.PIPELEX_BASE_URL ?? '') ? 'production' : 'other'\""
)
# Every `make` the template has is also an npm script, and the npm script is the one every OS runs, Windows
# without `make` included. The one `make` a shipped file still names is the guard's `make dev`, a way of
# starting the server the skill forbids.
MAKE_COMMANDS_GONE = ("make create", "make serve", "make stop", "make all", "make add-method", "make -C")

# What the family's initializer and `npm run serve` print, as `pipelex-sdk` documents them
# (`method-apps/initializers/js/README.md`, `method-apps/webapp-js/scripts/lib/serve.mts`). The skill keys its stop table on
# these words; a verdict the family adds or renames is re-read here and in the table together.
INITIALIZER_VERDICTS_WITH_A_ROW = (
    "`refused: not-empty`",
    "`refused: no-key`",
    "`refused: inside-template-checkout`",
    "`refused: missing-tool`",
    "`node-too-old`",
    "`failed: create`",
)
# `failed: write` and `failed: commit`, like the script's own `failed: npm` and `failed: log`, fall to the stop table's
# row for any other `refused:` or `failed:`, which reads the message under the line.
SERVE_VERDICTS = ('`serving <url> — "<title>"`', "`already-serving`", "`refused: not-loopback`")


def _bash_blocks(text: str) -> list[str]:
    return [match.group(1) for match in BASH_BLOCK.finditer(text)]


def _shells() -> list[list[str]]:
    """Every shell on this machine an agent's harness might run a command in, with the arguments that make it run one line.

    On macOS and Linux they are bash, sh and zsh, the last with `-f` so that no `.zshenv` of the machine's can
    export a real credential into it, and PowerShell when it is installed; on Windows they are Windows
    PowerShell 5.1, PowerShell 7 when installed, and cmd.
    """
    if os.name == "nt":
        candidates = [
            ["powershell", "-NoProfile", "-NonInteractive", "-Command"],
            ["pwsh", "-NoProfile", "-NonInteractive", "-Command"],
            ["cmd", "/d", "/s", "/c"],
        ]
    else:
        candidates = [["bash", "-c"], ["sh", "-c"], ["zsh", "-f", "-c"], ["pwsh", "-NoProfile", "-NonInteractive", "-Command"]]
    shells: list[list[str]] = []
    for candidate in candidates:
        executable = shutil.which(candidate[0])
        if executable is not None:
            shells.append([executable, *candidate[1:]])
    return shells


def _run_in(shell: list[str], command: str, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """`command` run by `shell` as typed. cmd reads its own command line, so it gets the line whole, not a list
    quoted by the C runtime's rules."""
    if Path(shell[0]).stem.lower() == "cmd":
        return subprocess.run(f'"{shell[0]}" /d /s /c "{command}"', capture_output=True, text=True, check=True, env=environment)
    return subprocess.run([*shell, command], capture_output=True, text=True, check=True, env=environment)


def _render_skill(target_name: str) -> str:
    """The skill as one target's users read it, rendered from `templates/` in memory."""
    config = load_target_config(REPO_ROOT / "targets", target_name)
    rendered = render_templates(
        REPO_ROOT / "templates",
        REPO_ROOT,
        config.template_vars,
        include_skills=["pipelex-scaffold"],
        target_name=config.name,
    )
    return next(content for path, content in rendered.items() if path.match("skills/pipelex-scaffold/SKILL.md"))


def _recipe(text: str, marker: str) -> str:
    """The one shipped bash block containing `marker`, verbatim.

    Pinned to exactly one so that a recipe split in two, or a second one written
    beside it, fails here instead of letting this suite execute an arbitrary half.
    """
    blocks = [block for block in _bash_blocks(text) if marker in block]
    assert len(blocks) == 1, f"expected exactly one bash block containing {marker!r}, found {len(blocks)}"
    return blocks[0]


def _bodies() -> list[str]:
    """The template and every render: a rule that holds only in `templates/` is a rule no user reads."""
    return [SKILL_TEMPLATE.read_text(encoding="utf-8")] + [_render_skill(target) for target in TARGETS]


class TestPipelexScaffoldSkill:
    """The skill is executable guidance, so these tests guard what a user's new
    project depends on: nothing is written into a non-empty directory, the skill
    makes at most one commit, the method app's commands are the family's and never
    reimplemented, the key never crosses the conversation, and no MCP tool is needed.
    """

    SKILLS = REPO_ROOT / "templates" / "skills"
    TEMPLATE = SKILL_TEMPLATE
    REFERENCES = ("initializers.md", "version-managers.md", "github.md", "uncreated-copy.md")
    SCRIPTS = ("commit-pristine.mjs", "write-env-file.mjs")
    # The scripts `references/uncreated-copy.md` runs, named by path there rather than in the skill.
    REFERENCE_SCRIPTS = ("read-copy-git.mjs", "method-app.mjs")
    SCRIPTS_DIR = REPO_ROOT / "skills" / "pipelex-scaffold" / "scripts"
    RULES = (
        "exactly two branches and carries no templates of its own",
        "no cookiecutter, no copier, no framework matrix of its own",
        "never write into a directory that exists and is not empty",
        "never offer to move, delete or merge what it holds to make room",
        "the **one commit this skill makes**",
        "**The starters are not scaffolded from**",
        "**Never print a key, and never ask for one in the conversation.**",
        "a key in the transcript is a key to rotate",
        # A file-editing tool needs the literal value in its parameters, which is the transcript.
        "**the value moves only through a shell that expands the variable itself, and never through you**",
        "never move one with a file-editing tool",
        "**no reading an env file back**",
        "One thing always confirms, in every mode: **`gh repo create`**",
        "Add **no** SDK dependency and create **no** empty `methods/` directory",
        "Nothing beyond what the initializer writes is authored by this skill",
        # Both scripts run on `node`, so every branch needs it, Python's included, and finds that out before
        # an initializer has created anything.
        "or later with `npm` on every branch, before anything is created;",
        # A version manager that downloads a version is the toolchain install the step forbids.
        "**Never install a toolchain, and never let a version manager download one.**",
        # The default TS branch is prescribed in the reference, whose costs it states.
        "**Read [references/initializers.md](references/initializers.md) before running any initializer**",
        # The initializer branch's programs are scripts, run by path and never retyped.
        "/scripts/commit-pristine.mjs\" '<dir>' 'Scaffold <framework or language> project'",
        "/scripts/write-env-file.mjs\" '<dir>'",
    )

    @property
    def scaffold(self) -> str:
        return self.TEMPLATE.read_text(encoding="utf-8")

    def render(self, target_name: str) -> str:
        """The skill as one target's users read it, rendered from `templates/` in memory.

        A rule asserted on the template alone is a rule that may never reach a user: the platform
        conditionals are resolved here, and the committed trees under `pipelex*/` are built from
        exactly this call.
        """
        return _render_skill(target_name)

    def test_the_rules_are_stated(self) -> None:
        body = self.scaffold
        for rule in self.RULES:
            assert rule in body, f"missing rule: {rule}"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_skill_fits_what_a_compaction_keeps(self, target_name: str) -> None:
        size = len(self.render(target_name))
        assert size <= SKILL_CEILING_CHARS, f"{target_name}: pipelex-scaffold renders {size} characters, over the {SKILL_CEILING_CHARS} ceiling"

    def test_the_initializer_recipes_live_in_their_reference_alone(self) -> None:
        """Round 2 of the scaffold's own review found the reference and the skill body contradicting each
        other: the reference put `--no-workspace` on every `uv init` while the body's recipe kept the bare
        form. The size diet left the recipes in the reference alone, which the skill points at before any
        initializer runs, so the bare form must be nowhere a user reads.
        """
        initializers = INITIALIZERS_REFERENCE.read_text(encoding="utf-8")
        assert "uv init --package --no-workspace <dir>" in initializers
        # A bare `uv init --package <dir>` appends a [tool.uv.workspace] table to the USER'S own
        # pyproject.toml and leaves the new project without its own lock. The reference names the bare
        # form only to warn against it, so no recipe of its own spells it, and the skill never does.
        assert "| `uv init --package <dir>`" not in initializers and "uv init --package <dir> &&" not in initializers
        for body in _bodies():
            assert "uv init --package <dir>" not in body, "a bare uv init absorbs <dir> into the parent workspace"

    def test_an_uncreated_copy_is_finished_and_the_template_s_checkout_refused(self) -> None:
        for body in _bodies():
            assert "**A copy of the template not yet made the user's**" in body
            assert (
                "is finished and never created again: read [references/uncreated-copy.md](references/uncreated-copy.md) before running anything in it"
                in body
            )
            # The row names the template's home; a clone of `pipelex-method-apps`, where it lived before, is refused
            # by the initializer and by the reference's own `origin` reading, which both still name it.
            assert "| `refused: inside-template-checkout`, or an `origin` at `Pipelex/pipelex-sdk` | STOP: that is the template, not a copy |" in body

    def test_only_a_lone_git_reads_as_empty_and_no_cruft_list_joins_it(self) -> None:
        """`L-260912-724b71`, ruled 2026-09-13: a directory holding nothing but `.git` is empty.

        The refusal it narrows is the right one — the agent has no business deciding which of a
        user's files matter — and the exception exists because `mkdir my-app && cd my-app && git
        init` is an ordinary opening move.

        The cruft list was deliberately declined in the same ruling: `.DS_Store`, `.idea/`,
        `.vscode/` and `Thumbs.db` keep refusing until a real report names one, because a list that
        grows by guesswork is how this rule drifts back into the judgement it forbids. So this test
        pins the exception as an entry named `.git` rather than as a predicate over ignorable
        files, and pins the four declined names as still-refusing — adding any of them to the
        exception means rewording a sentence asserted here, which is the point.
        """
        for body in _bodies():
            assert "**An empty directory has no entry, or only `.git`." in body
            assert (
                "A lone `.git` is the only entry that does not make a directory non-empty, and that is a ruling about `.git` and nothing else**"
                in body
            )
            assert "`.DS_Store`, `.idea/`, `.vscode/`, `Thumbs.db` and every other entry refuse" in body
            assert "since judging which of a user's files matter is what this rule forbids" in body
            # Untouched by the ruling: a directory read as empty is never cleared, so the skill
            # still never offers to make room. Narrowing what counts as occupied is not permission
            # to empty what is.
            assert "never offer to move, delete or merge what it holds to make room" in body
            assert "never delete, move or write into it, and never offer to" in body
            # Round 2 of the lone-`.git` ruling: the rationale once promised a `git init` that the
            # pristine-commit script exists to gate, and the family's initializer reads git itself.
            assert "branch B runs `git init -b main` in the directory it is working in one step later" not in body

    def test_the_pristine_commit_confirms_when_it_lands_on_the_users_repository(self) -> None:
        """A pristine commit into a directory that already held a repository lands on the user's branch.

        Phase 5a's smoke sessions found a directory holding only the user's `.git` taking the initializer
        branch's commit with no question; branch B's step 2 now asks before the script runs. The method
        app's initializer refuses a repository with commits or with a staged file, so its commit holds
        the template alone and asks nothing; a copy the initializer did not make, whose repository is the
        user's, confirms its commit in the reference that makes it.
        """
        for body in _bodies():
            assert "A second confirms on branch B: a pristine commit into a directory that already held a repository." in body
            ask = body.index("**When `<dir>` held a `.git` before step 1, ask before running the script**")
            assert ask < body.index("scripts/commit-pristine.mjs\" '<dir>'")
            assert "showing `git -C '<dir>' status --short`" in body
        reference = UNCREATED_COPY_REFERENCE.read_text(encoding="utf-8")
        assert "The directory is the user's, so this commit confirms in every mode" in reference

    def test_branch_b_locks_the_python_project_before_the_hand_off(self) -> None:
        """Round 2: `uv init` writes a `pyproject.toml` and neither a lock file nor an environment.

        `/pipelex-integrate` picks the package manager off the lock file and reads its absence as
        `pip install` into the active environment, so the default Python scaffold — the minimal and
        script forms, which are what "no framework named" selects — handed over a uv project for the
        next skill to install into with pip, and into no environment at all. Asserted on the body and
        on the reference, because either alone is the half-application.
        """
        for body in _bodies():
            assert "**On a project `uv init` created, finish with `uv sync --directory '<dir>'`**" in body
        assert "`{{ skill_prefix }}pipelex-integrate` reads no lock file as `pip install`" in SKILL_TEMPLATE.read_text(encoding="utf-8")
        for target_name in TARGETS:
            prefix = load_target_config(REPO_ROOT / "targets", target_name).template_vars["skill_prefix"]
            assert f"`{prefix}pipelex-integrate` reads no lock file as `pip install`" in _render_skill(target_name), target_name
        reference = INITIALIZERS_REFERENCE.read_text(encoding="utf-8")
        assert (
            "**On a project `uv init` created, run `uv sync --directory '<dir>'` before the pristine commit, and commit the `uv.lock` it writes.**"
            in reference
        )
        assert "`uv init` writes a `pyproject.toml` and nothing else: no lock file and no environment." in reference

    def test_the_initializer_branch_runs_its_scripts_and_reports_their_verdicts(self) -> None:
        """The pristine commit and the env file of the initializer branch are scripts (box E of the size
        diet): the skill runs each by path, its stop table keys on the verdict words they print, and the
        report turns the env file's verdict into words without the URL, in the words the initializers
        reference gives each, which branch B reads before anything runs. The scripts themselves are
        executed in `test_pipelex_scaffold_scripts.py`."""
        for body in _bodies():
            assert "| A script says `refused:` |" in body
            for verdict in ("`usage`", "`no-directory`", "`not-a-repository`"):
                assert verdict in body, f"the stop table has no reading of {verdict}"
            # The script prints no git message for it: the initializer is re-run, not the user sent to fix git.
            assert "`nothing-to-commit`: the initializer wrote nothing in `<dir>`; read its output and rerun it" in body
            assert "`committed:` names it and lists the staged paths" in body
            assert "`kept:` names the commit the initializer made itself" in body
            # Ruled 2026-09-24: inside another repository's work tree, branch B makes no repository and no
            # commit, as the method app does, and the report says the project is new files of it. Ruled
            # 2026-09-25: a `<dir>` that repository ignores gets a repository of its own, as outside every
            # work tree. A `<dir>` whose every file it ignores, though not the directory, gets none and a
            # verdict of its own, since the report cannot call those files new files of the repository.
            assert "makes `<dir>` a repository when none holds it or the one around it ignores it" in body
            assert "`inside:`, `unversioned:` and `nested:` name the enclosing repository, where it commits nothing" in body
            assert "the pristine commit and who made it, or on `inside:` that the project is new files of that repository" in body
            assert (
                "the `unversioned:`, `nested:` and env verdicts in the words "
                "[references/initializers.md](references/initializers.md) gives each, never the URL"
            ) in body
            assert "`ignored:`" not in body
            # The method app's report still reads the plane by a test, never an echo, and only of the file
            # `npm run create` wrote: one the user wrote is `uncreated-copy.md`'s to report.
            assert f"the plane of the `.env.local` `npm run create` wrote, `{PLANE_TEST}`" in body
            # The env file's own command left the skill: the script is the only thing that writes it.
            assert ">> <dir>/.env" not in body
            assert "cp -n" not in body
        initializers = INITIALIZERS_REFERENCE.read_text(encoding="utf-8")
        assert "**Inside another repository's work tree that does not ignore `<dir>`, it initializes nothing and commits nothing**" in initializers
        assert "where the repository whose work tree holds `<dir>` ignores it (an ignored `tmp/`, a dotfiles repository ignoring `*`)" in initializers
        assert "the script does the same and prints `unversioned:` instead" in initializers
        assert "reads no git identity from the enclosing repository's own `.git/config`" in initializers
        assert (
            "**`unversioned:`**, from the pristine-commit script: say that `<root>` ignores every file of the project but not its directory"
            in initializers
        )
        assert "How to version it is the user's choice, which this skill does not make for them" in initializers
        assert "`ignored:`" not in initializers
        # Review round of 2026-09-25: a repository an initializer plants inside the user's work tree anyway
        # (create-astro does) reads as a root, and was committed in. The script now says `nested:`, and the
        # report offers the removal of `<dir>/.git` without performing it, since it may hold history.
        assert "**`nested:`**, from the pristine-commit script" in initializers
        # Review round 3: the removal is offered only of a repository the initializer planted, never of one
        # the user had before step 1, whose history is theirs.
        assert (
            "**When `<dir>` held no `.git` before step 1**, the initializer made it: offer, never perform, the removal of `<dir>/.git`"
            in initializers
        )
        assert (
            "**When `<dir>` held a `.git` before step 1**, that repository and its history are the user's: never offer to remove it" in initializers
        )
        assert (
            "**An initializer not in the tables below that would run `git init` gets its no-git flag when `<dir>` lies inside another work tree**"
            in initializers
        )
        for word in ("**`kept`**", "**`empty`**", "**`base-url=copied`**", "**`base-url=file`**"):
            assert word in initializers, f"the reference does not say what {word} means"
        # The script never copies the shell's key, so `filled` is no verdict, and the report sends the user's
        # own key to the file without offering to copy the exported one there.
        assert "**`filled`**" not in initializers
        assert "say that the user puts their own key on `.env`'s `PIPELEX_API_KEY=` line" in initializers
        assert "The script never copies the key the shell exports, whatever key that is, so never offer to copy it there either" in initializers
        assert "warn that a key from `app.pipelex.com` is production's and will be refused there" in initializers

    @pytest.mark.cross_os
    @pytest.mark.skipif(shutil.which("node") is None, reason="the plane test is a node one-liner")
    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).stem)
    @pytest.mark.parametrize(
        ("base_url", "plane"),
        [(None, "production"), ("https://api.pipelex.com/", "production"), ("https://api-dev.pipelex.com", "other")],
        ids=["unset", "production-with-a-slash", "another-plane"],
    )
    def test_the_plane_test_reads_an_unset_base_url_as_production(self, shell: list[str], base_url: str | None, plane: str) -> None:
        """`npm run create` writes production's URL when the shell exports none, so the test must say so too, in
        every shell: the same line runs in bash, zsh and sh, PowerShell 5.1 and 7, and cmd."""
        environment = {key: value for key, value in os.environ.items() if key != "PIPELEX_BASE_URL"}
        if base_url is not None:
            environment["PIPELEX_BASE_URL"] = base_url
        result = _run_in(shell, PLANE_TEST, environment)
        assert result.stdout.strip() == plane

    def test_the_interpreter_check_needs_uv_only_where_uv_runs(self) -> None:
        """A poetry, pdm or hatch project on a machine with no uv is not stopped for lacking one."""
        for body in _bodies():
            assert "With uv, `uv python find '>=" in body

    def test_declares_no_mcp_tool(self) -> None:
        """The scaffold skill is MCP-free: no allowed-tools entry, no MCP-absent STOP message."""
        body = self.scaffold
        assert "mcp__" not in body
        assert "plugin manifest spawns" not in body
        assert "and it needs no MCP tool" in body

    def test_integrate_hands_a_missing_project_to_scaffold(self) -> None:
        integrate = (self.SKILLS / "pipelex-integrate" / "SKILL.md.j2").read_text(encoding="utf-8")
        assert "none means offering" in integrate
        assert "pipelex-scaffold" in integrate

    def test_every_pointer_to_the_version_managers_names_a_runtime_that_is_missing(self) -> None:
        """Phase 5a's smoke sessions: a pointer reading "reached `node` through a version manager" sent a
        model whose `node` answered on the `PATH`, from under `~/.nvm`, to read the reference off its
        branch. Every pointer names the condition, a runtime the `PATH` lacks or one below the floor."""
        pointers = [line for line in self.scaffold.splitlines() if "references/version-managers.md" in line]
        assert pointers
        for line in pointers:
            assert "missing" in line, line
        # References are one level deep, so no reference sends the reader to another one.
        for reference in self.REFERENCES:
            assert "references/" not in (REFERENCES_DIR / reference).read_text(encoding="utf-8"), reference

    def test_the_references_carry_the_initializers_the_version_managers_and_github(self) -> None:
        # The initializers reference sends the reader to the repository test the script runs rather
        # than to the inference the skill forbids by name.
        initializers = INITIALIZERS_REFERENCE.read_text(encoding="utf-8")
        assert initializers.split("\n\n")[1].startswith("Read this when ")
        assert "**the test, never the inference from which initializer ran**" in initializers
        assert "pipelex-starter" not in initializers and "the starter" not in initializers
        # A sourced shell does not survive the next command, so the runtime is resolved to a path.
        managers = (REFERENCES_DIR / "version-managers.md").read_text(encoding="utf-8")
        assert managers.split("\n\n")[1].startswith("Read this when ")
        assert "A runtime the machine already has, where only the `PATH` is missing it, is not a missing piece" in managers
        assert "## Resolve it to an absolute path, never source a shell" in managers
        assert "**A shim is not a runtime.**" in managers
        assert "**`volta` and `mise` install on first use.**" in managers
        # Phase 5a's review, round 4: a `uv` that only asdf or mise holds was never looked for, and the
        # restart warning named nvm and fnm alone although any runtime reached by a PATH prefix is
        # invisible to the harness that spawns the workshop.
        assert "`mise which uv`" in managers and "`asdf which uv`" in managers
        assert "a `node` reached only through a `PATH` prefix means no workshop at all, whichever manager supplied it" in managers
        assert "`make dev`" not in managers and "the method app's initializer and `npm run serve`" in managers
        # The `PATH` is set for one command in the form the shell gives, never as a POSIX prefix spelled out.
        assert 'PATH="' not in managers and "$NVM_DIR" not in managers
        assert "`fnm exec --using=<v> -- node -p process.execPath`" in managers
        github = (REFERENCES_DIR / "github.md").read_text(encoding="utf-8")
        assert github.split("\n\n")[1].startswith("Read this when ")
        assert "**state the exact command and confirm before running it**" in github
        assert "gh repo create <owner>/<name> --private --source <dir> --remote origin" in github
        assert "--template" in github and "--template Pipelex/" not in github
        # `gh` refuses a directory inside another work tree and hints at the nested `git init` both branches refuse.
        assert (
            "**A project inside another repository's work tree that does not ignore it has neither a repository nor a pristine commit of its own**, "
            "on either branch"
        ) in github
        assert "the pristine-commit script's `inside:` verdict" in github
        assert "On `unversioned:`, or a `git:` line saying the project is under no version control" in github
        assert "Treat `nested:` as `inside:`" in github
        assert "A project under a path the enclosing repository ignores has a repository and a pristine commit of its own" in github
        assert "never follow `gh`'s hint to `git init` the directory" in github
        assert "npm create next-app@latest <dir> -- --ts --app --src-dir --eslint --use-npm --yes" in initializers
        assert "No SDK dependency" in initializers
        # Every `uv add` runs inside the new project: from the parent it writes to the user's own. `--directory`
        # scopes it in one command, which every shell runs, where a `(cd … && …)` subshell is POSIX alone.
        assert "**Every `uv add` above runs inside `<dir>`, and `--directory <dir>` is why.**" in initializers
        for recipe in (
            '`uv add --directory <dir> "fastapi[standard]"`',
            "`uv add --directory <dir> typer`",
            "`uv add --directory <dir> django`, then `uv run --directory <dir> django-admin startproject config .`",
        ):
            assert recipe in initializers, f"uv add not scoped to the project: {recipe}"
        assert "(cd " not in initializers and "&&" not in initializers
        # Every `uv init` carries --no-workspace. Without it, run inside a directory that already
        # holds a pyproject.toml, uv appends a [tool.uv.workspace] table to the USER'S file and puts
        # the lock at the parent root, so the new project does not resolve standalone. Same hazard
        # class as the `uv add --directory` above, one command earlier.
        assert "uv init --package --no-workspace <dir>" in initializers
        assert "uv init --app --no-workspace <dir>" in initializers
        # `pdm init` runs `git init` even inside another repository's work tree (PDM 2.29.2), which would
        # plant the nested repository the pristine-commit script refuses to make.
        assert "`pdm init -p <dir> --non-interactive --no-git`" in initializers
        assert "pdm: yes, even inside another repository, and `--no-git` skips it" in initializers
        # `pdm init` takes no directory argument: without `-p` it initializes the shell's working directory.
        # And under any parent pyproject.toml it joins that project's workspace, writing into the user's
        # file, with no opt-out (PDM 2.29.2), so the reference sends the user to another tool there.
        assert "**`pdm init` takes its directory only as `-p <dir>`, and has no `--no-workspace`.**" in initializers
        assert "when a `pyproject.toml` is there, do not run pdm" in initializers
        assert "`--no-workspace` is on every `uv init` above" in initializers
        # npm resolves the project it writes to upward exactly as uv does, and unlike uv it finds the
        # parent and silently succeeds, so every follow-on install is scoped too.
        for recipe in (
            "`npm install --prefix <dir>`",
            "`npm install --prefix <dir> express`, then `npm install --prefix <dir> --save-dev @types/express`",
        ):
            assert recipe in initializers, f"npm install not scoped to the project: {recipe}"
        assert "**Every follow-on `npm install` above takes `--prefix <dir>`" in initializers
        # `npm init` and `tsc --init` write where they run, whatever `--prefix` says, so the minimal recipe runs
        # each of its commands with `<dir>` as the harness's working directory, confirmed first, never after a
        # chained `cd` (L-261126-54e9af).
        assert "each command on its own, run with `<dir>` as its working directory as the note below says: `npm init -y`," in initializers
        assert "its command tool's working-directory setting when it has one, else a `cd <dir>` it keeps" in initializers
        assert '**Confirm the directory before the first of them**: `node -p "process.cwd()"` must print `<dir>`' in initializers
        assert "(`npm init` and `tsc --init` write where they run, whatever `--prefix` says)" in initializers
        # The minimal TS default meets the emitter defect, and a bundler resolution only moves it from the
        # type check to runtime when `tsc`'s ES module output runs under plain Node, as
        # `pipelex-integrate`'s TypeScript reference says. The CommonJS emit is the minimal shape it
        # does not touch, and `tsc --init`'s `verbatimModuleSyntax: true` refuses that shape (TS1295).
        assert "meets the ts-zod emitter's extensionless-import defect whichever ES module resolution it uses" in initializers
        assert "so a bundler resolution is no cure for a project whose code `node` runs from `dist/`" in initializers
        assert (
            "which the defect does not touch" in initializers and "`--moduleResolution bundler`, which the defect does not touch" not in initializers
        )
        assert 'set `"verbatimModuleSyntax": false`' in initializers
        integrate_typescript = (REPO_ROOT / "skills" / "pipelex-integrate" / "references" / "typescript.md").read_text(encoding="utf-8")
        assert "meets the same `ERR_MODULE_NOT_FOUND` at runtime with no `TS2835` to warn of it" in integrate_typescript
        # `tsc --init` writes an active `"types": []`, which switches off the @types/node the line
        # before it installed — the integrate call site then fails TS2591 on node:path and process.
        assert '`tsc --init` writes `"types": []` as an active key' in initializers
        assert 'set `"types": ["node"]` as part of the recipe' in initializers

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_platform_renders_the_skill_and_its_references(self, target_name: str) -> None:
        config = load_target_config(REPO_ROOT / "targets", target_name)
        body = self.render(target_name)
        assert "# Scaffold a project for Pipelex methods" in body
        assert "{%" not in body
        assert "{{" not in body
        assert "mcp__" not in body
        for rule in self.RULES:
            assert rule in body, f"{target_name}: missing rule: {rule}"
        # A session is started inside the project in two commands, since Windows PowerShell 5.1 chains none.
        assert "`cd <dir>`, then " in body
        assert "`cd <dir> && " not in body
        if target_name == "prod":
            assert "`cd <dir>`, then `claude` there" in body
            assert "`/pipelex-integrate` with the method" in body
        else:
            assert "`claude`" not in body
            assert "`../pipelex-integrate/SKILL.md` with the method" in body

        skill_dir = resolve_output_dir(REPO_ROOT, config.source) / "skills" / "pipelex-scaffold"
        for reference in self.REFERENCES:
            assert (skill_dir / "references" / reference).is_file(), f"{target_name}: missing references/{reference}"
        assert sorted(path.name for path in (skill_dir / "references").iterdir()) == sorted(self.REFERENCES), f"{target_name}: a stale reference"
        for script in self.SCRIPTS:
            assert (skill_dir / "scripts" / script).is_file(), f"{target_name}: missing scripts/{script}"
            assert f'/scripts/{script}"' in body, f"{target_name}: the skill does not run scripts/{script} by path"
        uncreated_copy = (skill_dir / "references" / "uncreated-copy.md").read_text(encoding="utf-8")
        for script in self.REFERENCE_SCRIPTS:
            assert (skill_dir / "scripts" / script).is_file(), f"{target_name}: missing scripts/{script}"
            assert f'node "<skill-dir>/scripts/{script}"' in uncreated_copy, f"{target_name}: the reference does not run scripts/{script} by path"
        assert sorted(path.name for path in (skill_dir / "scripts").iterdir()) == sorted(self.SCRIPTS + self.REFERENCE_SCRIPTS), (
            f"{target_name}: a stale script"
        )
        if target_name != "prod":
            # Codex and Vibe substitute nothing, so the placeholder is defined before its first use.
            assert body.index("`<skill-dir>` stands for the directory holding this `SKILL.md`") < body.index("<skill-dir>/scripts/")

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_committed_references_match_the_source_byte_for_byte(self, target_name: str) -> None:
        """The references are executable know-how, and the committed target copies are the ones a
        user installs — so compare against those, not against a fresh `copytree` into a tmp dir,
        which only ever asserts that `shutil` copies bytes. A stale committed copy is the whole
        failure mode, and it is invisible to any assertion that rebuilds its own expected side.
        """
        config = load_target_config(REPO_ROOT / "targets", target_name)
        installed = resolve_output_dir(REPO_ROOT, config.source) / "skills" / "pipelex-scaffold" / "references"
        for reference in self.REFERENCES:
            assert (installed / reference).is_file(), f"{target_name}: missing references/{reference}"
            assert (installed / reference).read_bytes() == (REFERENCES_DIR / reference).read_bytes(), (
                f"{target_name}: references/{reference} is stale — run `make build`"
            )
        scripts = installed.parent / "scripts"
        for script in self.SCRIPTS + self.REFERENCE_SCRIPTS:
            assert (scripts / script).read_bytes() == (self.SCRIPTS_DIR / script).read_bytes(), f"{target_name}: scripts/{script} is stale"
            assert os.access(scripts / script, os.X_OK), f"{target_name}: scripts/{script} lost its executable bit"


class TestMethodAppBranch:
    """The TypeScript branch is the method app: the family's initializer, then its serve script.

    Ratified on 2026-09-16 with the method-app template, and amended at the size diet's ratification on
    2026-09-23 (box E of the size diet's design, L-260923-a9bdfe): a program that belongs to a template lives in
    the template. The family, under `pipelex-sdk`'s `method-apps/`, publishes `@pipelex/create-method-app`, which writes `webapp-js/`,
    makes the pristine commit and runs the copy's `make create`, and the template's `make serve`, which
    starts the dev server detached on loopback and proves the page answers. The skill runs those two
    commands, keys its stop table on their verdicts, and keeps no copy of the template's layout.
    """

    def test_the_method_app_is_the_family_s_two_commands(self) -> None:
        """Ruled 2026-11-26 for Windows (L-261126-54e9af): the copy is created and served through its npm scripts
        on every OS, since a Windows machine has no `make`, and with no per-OS branch."""
        for body in _bodies():
            assert "runs the copy's own `npm run create` with the method; the copy's `npm run serve` then starts the app" in body
            # Run by its script, which reads the request and runs `npm create @pipelex/method-app@latest` with it.
            assert _recipe(body, "method-app.mjs").strip() in {CREATE_COMMAND.replace("<skill-dir>", spelled) for spelled in SKILL_DIR_SPELLINGS}
            assert f"Write `pipelex-scaffold-request.json` in the working directory with your file tools, {REQUEST}" in body
            assert "`npm create @pipelex/method-app` never prompts and reads a bundle path from the working directory" in body
            assert _recipe(body, SERVE_COMMAND).strip() == SERVE_COMMAND
            assert "Both are the family's commands, and nothing they do is reimplemented here." in body
            assert "**The method app needs the method first**" in body
            # A create option carries a value the user gave, never an invented one.
            assert "only with a value the user gave, never an invented one" in body

    def test_the_acquisition_and_dev_server_chains_left_the_skill(self) -> None:
        """The chains the family's commands replaced are gone from every file the skill ships."""
        shipped = _bodies() + [(REFERENCES_DIR / reference).read_text(encoding="utf-8") for reference in TestPipelexScaffoldSkill.REFERENCES]
        for text in shipped:
            for gone in (
                "pipelex-method-apps.git",
                "pipelex-sdk.git",
                "git clone",
                'cp -R "$tmp',
                "nohup",
                "port-check",
                "lsof -ti",
                "pgrep",
                "curl -sS",
            ):
                assert gone not in text, f"the skill still carries {gone!r}"
            # The template's npm scripts replaced its make targets in every command the skill gives (L-261126-54e9af).
            for gone in MAKE_COMMANDS_GONE:
                assert gone not in text, f"the skill still runs {gone!r}, which a Windows machine has no make for"
            assert re.findall(r"`make [^`]*`", text) in ([], ["`make dev`"]), "a make command beyond the guard's `make dev`"

    def test_the_verdict_is_read_from_its_line_never_from_the_exit_code(self) -> None:
        """The registry proof of `L-260922-12f302`: under `npm create`, a run that exits 1 is followed by
        npm's own `npm error` lines, so the verdict is the last line opening with a verdict word rather than
        the last line printed, and so is `npm run serve`'s."""
        for body in _bodies():
            assert (
                "**Its verdict is the last line opening with `created`, `copied`, `refused:` or `failed:`**, not npm's `npm error` lines after it"
                in body
            )
            assert "with no such line, npm itself failed, and you relay its error" in body
            assert "Branch on the verdict's first word, never on the exit code." in body
            # `npm run serve` exits 1 on a refusal, which npm follows with its own `npm error` lines.
            assert (
                'Its verdict is the last line opening with `serving <url> — "<title>"`, `already-serving`, `refused:` or `failed:`. '
                "**Never report a URL that did not answer**"
            ) in body

    def test_a_command_whose_verdict_decides_the_next_step_runs_in_the_foreground(self) -> None:
        """A headless session ends with its turn and kills what it backgrounded, which left a half-made copy
        holding an `.env.local` in the phase 5b smoke sessions; "several minutes" alone invited the background."""
        for body in _bodies():
            assert "**Run it in the foreground with a long timeout**: it takes minutes, and its verdict decides the next step." in body
        reference = UNCREATED_COPY_REFERENCE.read_text(encoding="utf-8")
        assert "**Run the script in the foreground with a long timeout**, never in the background" in reference

    def test_the_stop_table_keys_on_the_family_s_verdicts(self) -> None:
        for body in _bodies():
            table = body[body.index("## When something goes wrong") :]
            for verdict in INITIALIZER_VERDICTS_WITH_A_ROW:
                assert verdict in table, f"the stop table has no row for {verdict}"
            # The script's own `failed: npm` and `failed: log`, and a `refused: bad-request` whose cause is on stderr,
            # fall to the row that reads the message under the line.
            assert "| any other `refused:` or `failed:` | the line, and the message under it, say what stands and name the fix:" in table
            assert "| any other `npm run serve` verdict |" in table
            # A server the user started from the copy is left running by `npm run serve`, and its verdict says so.
            assert "when it says the server was stopped, read `<dir>/.serve/server.log`'s tail" in table
            assert "one still running is the user's to stop" in table
            # `copied` is what --dry-run and --no-create print, and it leads to the uncreated copy.
            assert "`copied`, which only `dry-run` or `no-create` prints, to [references/uncreated-copy.md](references/uncreated-copy.md)" in body
            for verdict in SERVE_VERDICTS:
                assert verdict in body, f"the skill never reads {verdict}"

    def test_the_key_reaches_the_gesture_without_crossing_the_conversation(self) -> None:
        for body in _bodies():
            assert "`npm run create` reads it there, and **the user writes their own key into either file, never you**" in body
            assert "Never list the environment, never echo a key" in body
            # Neither `npm run create` nor `write-env-file.mjs` copies the shell's key into a file, so the skill
            # never says a script moves one, and never reports a key as `filled`.
            assert "the method app's `.env.local` hold" not in body
            assert "`write-env-file.mjs` moves it" not in body
            assert "`filled`" not in body
            row = next(line for line in body.splitlines() if line.startswith("| `refused: no-key` |"))
            assert "a harness restarted from a shell that exports the key" in row
            # An unattended model took the second way itself in the phase 5b smoke sessions.
            assert row.startswith("| `refused: no-key` | STOP and offer two ways, running neither until the user picks: ")
            assert '`"no-create": true` in `options` and a `<dir>/.env.local` the user writes in their own editor' in row
            # A key is refused by every plane but the one that issued it.
            assert "never substitute a base URL the user did not declare" in body
            assert "a git identity is the user's to set, never yours" in body

    def test_the_method_app_ends_with_the_page_answering_and_the_url_first(self) -> None:
        for body in _bodies():
            assert "**Never report a URL that did not answer**: only the first two give one." in body
            # The Server Actions spend the key for whoever calls them: `npm run serve` binds loopback and
            # refuses a copy that cannot, and the skill starts the server no other way, `make dev` included.
            assert _recipe(body, SERVE_COMMAND).strip() == SERVE_COMMAND
            assert "**Never start the server any other way** (`make dev`, `npm run dev`, an `APP_HOST`)" in body
            assert "| `npm run serve` says `refused: not-loopback` | report no URL" in body
            assert "Nothing is run through the method." in body
            assert "**On the method app, the URL comes first**" in body
            assert "how the verdict says to stop it" in body
            # The running app took the key from the shell that started it; a restart from another shell
            # reads `.env.local`, where the user's own key goes.
            assert "the user puts their own key in `<dir>/.env.local` before restarting it from another shell with `npm run serve` in `<dir>`" in body
            assert "`make serve` inside the project restarts it" not in body
            # The warnings are relayed, the LICENSE holder first.
            assert "first that `LICENSE` still names the template's holder when it does" in body
            # The method app's `git:` line says what happened, a repository under an ignored path included.
            assert "the template's version and the git outcome; that" in body

    def test_no_value_the_user_gave_is_typed_into_a_command(self) -> None:
        """POSIX quoting spells a quote inside single quotes `'\\''`, which PowerShell reads as the end of a string
        and a stray backslash, and no quoting reads alike in every shell, so the method and every option travel in
        a request file the script reads; `<dir>` alone is typed, held to characters both shells read literally
        inside single quotes (L-261126-54e9af)."""
        for body in _bodies() + [UNCREATED_COPY_REFERENCE.read_text(encoding="utf-8")]:
            assert "'\\''" not in body
            for block in _bash_blocks(body):
                assert "<method>" not in block, f"a method typed into a command: {block!r}"
                assert "'<dir>'" in block or "<dir>" not in block, f"an unquoted <dir> in {block!r}"
        for body in _bodies():
            assert "**No value the user gave is typed into a command**, as no quoting reads alike in every shell" in body
            assert "only of letters, digits, spaces and `. _ - / \\ :`, neither starting with `-` nor ending with `\\`; else ask for another" in body

    def test_no_block_assigns_a_name_zsh_reserves(self) -> None:
        """`status` is read-only in zsh, the default shell on macOS, so `status=$?` aborts the line."""
        for text in [*_bodies(), UNCREATED_COPY_REFERENCE.read_text(encoding="utf-8")]:
            for block in _bash_blocks(text):
                assert re.search(r"(^|[\s;])(status|path|argv)=", block) is None, f"a block assigns a zsh-reserved name: {block!r}"

    def test_integrate_runs_the_bundle_arm_on_a_project_that_has_one(self) -> None:
        """A project made from the method app scaffolds a local bundle with one command.

        The gallery's `make add-method` refuses a bundle path, so `/pipelex-integrate` sent every
        local bundle down the hand-written route. The method app's takes one, and its usage says so.
        """
        # The harness branch left the skill body for a reference read at step 1 (the size diet, phase 2).
        harness = (REPO_ROOT / "skills" / "pipelex-integrate" / "references" / "harness.md").read_text(encoding="utf-8")
        assert "**A local bundle is one command when the project's `make add-method` takes a bundle path**" in harness
        assert "**Otherwise, place the method where the project keeps them**" in harness
        typescript = (REPO_ROOT / "skills" / "pipelex-integrate" / "references" / "typescript.md").read_text(encoding="utf-8")
        assert "a local bundle is one command when `make add-method` takes a bundle path" in typescript
        assert "where `make add-method` takes only a catalog id or an address, as the gallery's does" in typescript


class TestUncreatedCopyReference:
    """`references/uncreated-copy.md`: a copy of the method app that `npm run create` has not run in.

    The initializer leaves one after `--dry-run`, `--no-create` or a `failed: create`, and a user may stand
    in one made by hand. The reference reads git with `scripts/read-copy-git.mjs` and runs the copy's own
    `npm run create` with `scripts/method-app.mjs`, both executed in `test_pipelex_scaffold_copy_scripts.py`.
    """

    @property
    def reference(self) -> str:
        return UNCREATED_COPY_REFERENCE.read_text(encoding="utf-8")

    def test_it_opens_on_its_condition_and_hands_back_to_serve(self) -> None:
        entry = self.reference.split("\n\n")[1]
        assert entry.startswith("Read this when ")
        for condition in ("`copied` (after a `dry-run` or `no-create` request)", "`failed: create`", "the user stands in one"):
            assert condition in entry, condition
        assert "`/pipelex-scaffold` then goes on at branch A's step 2, `npm run serve`" in self.reference
        # A Codex session served a copy whose `make all` was red in the phase 5b smoke sessions.
        assert "**Never run `npm run serve` on a copy whose `npm run create` failed**" in entry
        assert "and `npm run serve` waits until it is fixed. On `0`, go on to `npm run serve`." in self.reference

    def test_every_command_is_one_a_shell_runs_alone(self) -> None:
        """Windows PowerShell 5.1 chains no command with `&&` or `||`, so each block gives one command a line,
        and every program the reference used to spell in shell is a script run by path (L-261126-54e9af)."""
        reference = self.reference
        assert _recipe(reference, "read-copy-git.mjs").strip() == READ_COPY_GIT_COMMAND
        assert _recipe(reference, "method-app.mjs").strip() == RUN_CREATE_COMMAND
        assert "`<skill-dir>` is the directory holding the skill's `SKILL.md`, the parent of the directory holding this file" in reference
        assert "Run them, never their steps by hand" in reference
        for gone in ("&&", "||", "2>/dev/null", "mktemp", "grep", "rm -rf", "pwd -P", "TMPDIR", "LICENSE_HOLDER="):
            assert gone not in reference, f"the reference still carries {gone!r}"
        # The bootstrap's directory is removed by Node, the same in every shell.
        assert "`node -e \"fs.rmSync(process.argv[1], { recursive: true, force: true })\" '<dir>/.claude/skills/bootstrap'`" in reference

    def test_the_git_reading_names_every_verdict_of_its_script(self) -> None:
        """The reference keys on the script's verdict words, so each one the script's header lists has a reading."""
        reference = self.reference
        header = (REPO_ROOT / "skills" / "pipelex-scaffold" / "scripts" / "read-copy-git.mjs").read_text(encoding="utf-8").split("\nimport ", 1)[0]
        for verdict in ("pristine:", "no-commit:", "history:", "inside:"):
            assert f"//   {verdict}" in header, verdict
            assert f"**`{verdict}" in reference, f"the reference has no reading of {verdict}"
        for refusal in ("template-checkout", "tracked <root>", "usage", "no-directory", "no-git", "init-failed"):
            assert refusal in header, refusal
            assert refusal in reference, f"the reference has no reading of {refusal}"
        # The history is read first, since the user seldom says who made the copy, and git before anything is initialized.
        assert "Read git before anything else, since the user seldom says who made the copy, and before initializing anything" in reference

    def test_a_cause_the_sandbox_imposes_is_handed_to_the_user(self) -> None:
        """Codex's `workspace-write` sandbox denies `ps`, which the template's tests and `npm run serve` need,
        and no edit in the copy lifts it (`L-260923-e82e4a`)."""
        reference = self.reference
        assert "**A cause the harness's own sandbox imposes is the user's to lift, never yours to work around**" in reference
        assert "a denied `ps`, which the template's tests and `npm run serve` both need" in reference
        assert "A red `npm run all` is fixed, never handed off, but for the one cause below." in reference

    def test_the_create_gesture_is_driven_and_never_reimplemented(self) -> None:
        reference = self.reference
        assert "None of `npm run create`'s work is reimplemented here" in reference
        assert "never by editing `src/generated/`" in reference
        assert "It commits nothing." in reference
        # A bundle is read from where the user stood, as the initializer reads it, and passed on as an absolute path.
        assert "is read from the working directory, which is where the user stood, and the script passes it on as an absolute path" in reference
        # The values travel in the request, never on the command line, and the script installs what the gesture imports.
        assert "**No value the user gave goes on the command line**" in reference
        assert "the script runs `npm install` in it first, as the template's own gesture expects" in reference
        assert "`npm install exited <code>; the whole log is <path>` when the install failed and the gesture never started" in reference
        assert "**The gesture's warnings are read from the whole log, not from its tail.**" in reference
        assert 'goes into the real run\'s request as `"license-holder"`' in reference
        # A refusal in the read-only half can run again; a failure after the scaffold cannot.
        assert "changed no tracked file, so it can run again" in reference
        assert "cannot be undone by running `npm run create` again" in reference
        # The key reaches the gesture from the shell or a file the user wrote, and is never read back.
        assert "`npm run create` reads that file and never touches an `.env.local` that already exists. Nothing reads it back" in reference
        # A kept `.env.local` already holds the user's key, so the report does not send them to put it there.
        assert "the report says it was kept, in place of telling the user where their key goes" in reference
        assert "or from an env file already in the project, `.env.local` or `.env`, and refuses without one" in reference
        assert "so the log's tail is safe to read, and no env file is." in reference
        # The report's plane rule falls back to production, which a file the user wrote may contradict.
        assert "names its plane only from a `PIPELEX_BASE_URL` the shell exports, never production by default" in reference
        # The gesture's run decides the next step, so it runs in the foreground.
        assert "**Run the script in the foreground with a long timeout**, never in the background" in reference

    def test_the_fresh_copy_is_recognized_before_git_is_initialized_in_it(self) -> None:
        """The method app's own checkout sits inside the family repository.

        Initializing first would hide the family's `origin` behind a new, remote-less repository and
        let `npm run create` rewrite the template's tracked files.
        """
        reference = self.reference
        assert "**A directory another repository already tracks is not a fresh copy**" in reference
        assert (
            "**A copy that sits untracked inside another repository's work tree that does not ignore it gets no repository and no commit**"
            in reference
        )
        # The pristine commit is made only once the script said the copy is its own repository with no commit.
        assert reference.index(READ_COPY_GIT_COMMAND) < reference.index("On `no-commit:`, make the pristine commit")

    def test_the_copy_s_pristine_commit_cannot_reach_an_enclosing_repository(self) -> None:
        """`git -C <dir>` sets git's working directory and scopes nothing, and a bare `git commit`
        commits the whole index, so the copy's commit carries the pathspec on both commands, which run
        one after the other since Windows PowerShell 5.1 has no `&&`."""
        reference = self.reference
        assert reference.count("git -C '<dir>' add -A -- .") == 1
        assert _recipe(reference, "git -C '<dir>' add -A -- .").strip() == PRISTINE_COPY_COMMIT
        assert "each only once the one before succeeded" in reference
        hand_made = PRISTINE_COPY_COMMIT.split('"')[1]
        assert hand_made.startswith(PRISTINE_SUBJECT_PREFIX)
