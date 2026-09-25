"""Pin the pipelex-scaffold skill: two branches, no templates of its own, one commit, and a key that never crosses the conversation.

The method app is the template family's own two commands, its initializer and `make serve`, whose programs
and tests live in `pipelex-method-apps`. The initializer branch's two scripts are executed in
`test_pipelex_scaffold_scripts.py`. What this module executes is what the skill still carries of the method
app: the git reading and the `make create` run of `references/uncreated-copy.md`, for a copy of the template
the initializer did not finish.
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
CREATE_COMMAND = "npm create --yes @pipelex/method-app@latest '<dir>' -- --method '<method>' --quiet"
SERVE_COMMAND = "make -C '<dir>' serve"
CREATE_MARKER = "create METHOD='<method>'"
OWN_REPOSITORY_MARKER = "rev-parse --show-prefix"
INITIALIZER_COPY_MARKER = "rev-parse --show-cdup"
PRISTINE_SUBJECT_PREFIX = "Start from Pipelex/pipelex-method-apps/webapp-js "
PRISTINE_COPY_COMMIT = 'git -C <dir> add -A -- . && git -C <dir> commit -m "Start from Pipelex/pipelex-method-apps/webapp-js <version>" -- .'
TARGETS = ("prod", "codex", "mistral-vibe")
# The method app's report reads the plane of the `.env.local` `make create` wrote with this test.
PLANE_TEST = 'u=${PIPELEX_BASE_URL:-https://api.pipelex.com}; [ "${u%/}" = https://api.pipelex.com ] && echo production || echo other'

# What the family's initializer and `make serve` print, as `pipelex-method-apps` documents them
# (`initializers/js/README.md`, `webapp-js/scripts/lib/serve.mts`). The skill keys its stop table on
# these words; a verdict the family adds or renames is re-read here and in the table together.
INITIALIZER_VERDICTS_WITH_A_ROW = (
    "`refused: not-empty`",
    "`refused: no-key`",
    "`refused: inside-template-checkout`",
    "`refused: missing-tool`",
    "`node-too-old`",
    "`failed: write`",
    "`failed: commit`",
    "`failed: create`",
)
SERVE_VERDICTS = ('`serving <url> — "<title>"`', "`already-serving`", "`refused: not-loopback`")

NEEDS_GIT = pytest.mark.skipif(shutil.which("git") is None, reason="the uncreated copy's git reading is git")


def _bash_blocks(text: str) -> list[str]:
    return [match.group(1) for match in BASH_BLOCK.finditer(text)]


def _shells() -> list[list[str]]:
    """Every POSIX shell on this machine an agent's harness might run the command in.

    `zsh` runs with `-f` so that no `.zshenv` of the machine's can export a real credential into it.
    """
    shells: list[list[str]] = []
    for name, flags in (("bash", []), ("sh", []), ("zsh", ["-f"])):
        executable = shutil.which(name)
        if executable is not None:
            shells.append([executable, *flags])
    return shells


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


def _git_commit(repository: Path, message: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository), "-c", "user.email=t@example.com", "-c", "user.name=Test", "commit", "-q", "-m", message],
        check=True,
    )


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
    SCRIPTS = ("commit-pristine.sh", "write-env-file.sh")
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
        "**and not validated**",
        "One thing always confirms, in every mode: **`gh repo create`**",
        "Add **no** SDK dependency and create **no** empty `methods/` directory",
        "Nothing beyond what the initializer writes is authored by this skill",
        # A version manager that downloads a version is the toolchain install the step forbids.
        "**Never install a toolchain, and never let a version manager download one.**",
        # The default TS branch is prescribed in the reference, whose costs it states.
        "**Read [references/initializers.md](references/initializers.md) before running any initializer**",
        # The initializer branch's programs are scripts, run by path and never retyped.
        "/scripts/commit-pristine.sh\" '<dir>' 'Scaffold <framework or language> project'",
        "/scripts/write-env-file.sh\" '<dir>'",
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
            assert (
                "| `refused: inside-template-checkout`, or an `origin` at `Pipelex/pipelex-method-apps` | STOP: that is the template, not a copy |"
                in body
            )

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
            assert ask < body.index("scripts/commit-pristine.sh\" '<dir>'")
            assert "showing `git -C <dir> status --short`" in body
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
            assert "**On a project `uv init` created, finish with `uv sync` from inside `<dir>`**" in body
            assert "`/pipelex-integrate` reads no lock file as `pip install`" in body
        reference = INITIALIZERS_REFERENCE.read_text(encoding="utf-8")
        assert (
            "**On a project `uv init` created, run `uv sync` from inside `<dir>` before the pristine commit, and commit the `uv.lock` it writes.**"
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
            # `make create` wrote: one the user wrote is `uncreated-copy.md`'s to report.
            assert f"the plane of the `.env.local` `make create` wrote, `{PLANE_TEST}`" in body
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
        for word in ("**`filled`**", "**`kept`**", "**`empty`**", "**`base-url=copied`**", "**`base-url=file`**"):
            assert word in initializers, f"the reference does not say what {word} means"
        assert "warn that a key from `app.pipelex.com` is production's and will be refused there" in initializers

    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    @pytest.mark.parametrize(
        ("base_url", "plane"),
        [(None, "production"), ("https://api.pipelex.com/", "production"), ("https://api-dev.pipelex.com", "other")],
        ids=["unset", "production-with-a-slash", "another-plane"],
    )
    def test_the_plane_test_reads_an_unset_base_url_as_production(self, shell: list[str], base_url: str | None, plane: str) -> None:
        """`make create` writes production's URL when the shell exports none, so the test must say so too."""
        environment = {key: value for key, value in os.environ.items() if key != "PIPELEX_BASE_URL"}
        if base_url is not None:
            environment["PIPELEX_BASE_URL"] = base_url
        result = subprocess.run([*shell, "-c", PLANE_TEST], capture_output=True, text=True, check=True, env=environment)
        assert result.stdout == f"{plane}\n"

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
        assert "`make dev`" not in managers and "the method app's initializer and `make serve`" in managers
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
        # Every `uv add` runs inside the new project: from the parent it writes to the user's own.
        assert "**Every `uv add` above runs inside `<dir>`, and the parentheses are why.**" in initializers
        for recipe in (
            '(cd <dir> && uv add "fastapi[standard]")',
            "(cd <dir> && uv add typer)",
            "(cd <dir> && uv add django && uv run django-admin startproject config .)",
        ):
            assert recipe in initializers, f"uv add not scoped to the project: {recipe}"
        # Every `uv init` carries --no-workspace. Without it, run inside a directory that already
        # holds a pyproject.toml, uv appends a [tool.uv.workspace] table to the USER'S file and puts
        # the lock at the parent root, so the new project does not resolve standalone. Same hazard
        # class as the `uv add` parentheses above, one command earlier.
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
        for recipe in ("(cd <dir> && npm install)", "(cd <dir> && npm install express && npm install --save-dev @types/express)"):
            assert recipe in initializers, f"npm install not scoped to the project: {recipe}"
        assert "**Every follow-on `npm install` above is parenthesised" in initializers
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
        if target_name == "prod":
            assert "`cd <dir> && claude`" in body
            assert "`/pipelex-integrate` with the method" in body
        else:
            assert "`cd <dir> && claude`" not in body
            assert "`../pipelex-integrate/SKILL.md` with the method" in body

        skill_dir = resolve_output_dir(REPO_ROOT, config.source) / "skills" / "pipelex-scaffold"
        for reference in self.REFERENCES:
            assert (skill_dir / "references" / reference).is_file(), f"{target_name}: missing references/{reference}"
        assert sorted(path.name for path in (skill_dir / "references").iterdir()) == sorted(self.REFERENCES), f"{target_name}: a stale reference"
        for script in self.SCRIPTS:
            assert (skill_dir / "scripts" / script).is_file(), f"{target_name}: missing scripts/{script}"
            assert f'/scripts/{script}"' in body, f"{target_name}: the skill does not run scripts/{script} by path"
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
        for script in self.SCRIPTS:
            assert (scripts / script).read_bytes() == (self.SCRIPTS_DIR / script).read_bytes(), f"{target_name}: scripts/{script} is stale"
            assert os.access(scripts / script, os.X_OK), f"{target_name}: scripts/{script} lost its executable bit"


class TestMethodAppBranch:
    """The TypeScript branch is the method app: the family's initializer, then its serve target.

    Ratified on 2026-09-16 with the method-app template, and amended at the size diet's ratification on
    2026-09-23 (box E of `wip/skill-size-diet/design.md`): a program that belongs to a template lives in
    the template. `pipelex-method-apps` publishes `@pipelex/create-method-app`, which writes `webapp-js/`,
    makes the pristine commit and runs the copy's `make create`, and the template's `make serve`, which
    starts the dev server detached on loopback and proves the page answers. The skill runs those two
    commands, keys its stop table on their verdicts, and keeps no copy of the template's layout.
    """

    def test_the_method_app_is_the_family_s_two_commands(self) -> None:
        for body in _bodies():
            assert _recipe(body, "@pipelex/method-app").strip() == CREATE_COMMAND
            assert _recipe(body, SERVE_COMMAND).strip() == SERVE_COMMAND
            assert "Both are the family's commands, and nothing they do is reimplemented here." in body
            assert "**The method app needs the method first**" in body
            # A create option carries a value the user gave, never an invented one.
            assert "only with a value the user gave, never an invented one" in body

    def test_the_acquisition_and_dev_server_chains_left_the_skill(self) -> None:
        """The chains the family's commands replaced are gone from every file the skill ships."""
        shipped = _bodies() + [(REFERENCES_DIR / reference).read_text(encoding="utf-8") for reference in TestPipelexScaffoldSkill.REFERENCES]
        for text in shipped:
            for gone in ("pipelex-method-apps.git", "git clone", 'cp -R "$tmp', "nohup", "port-check", "lsof -ti", "pgrep", "curl -sS"):
                assert gone not in text, f"the skill still carries {gone!r}"

    def test_the_verdict_is_read_from_its_line_never_from_the_exit_code(self) -> None:
        """The registry proof of `L-260922-12f302`: under `npm create`, a run that exits 1 is followed by
        npm's own `npm error` lines, so the verdict is the last line opening with a verdict word rather than
        the last line printed. `make serve`'s is the last line make itself did not print."""
        for body in _bodies():
            assert (
                "**Its verdict is the last line opening with `created`, `copied`, `refused:` or `failed:`**, not npm's `npm error` lines after it"
                in body
            )
            assert "with no such line, npm itself failed, and you relay its error" in body
            assert "Branch on the verdict's first word, never on the exit code." in body
            assert "Its verdict is its last line not opening with `make`" in body

    def test_a_command_whose_verdict_decides_the_next_step_runs_in_the_foreground(self) -> None:
        """A headless session ends with its turn and kills what it backgrounded, which left a half-made copy
        holding an `.env.local` in the phase 5b smoke sessions; "several minutes" alone invited the background."""
        for body in _bodies():
            assert "**Run it in the foreground with a long timeout**: it takes minutes, and its verdict decides the next step." in body
        reference = UNCREATED_COPY_REFERENCE.read_text(encoding="utf-8")
        assert "**Run the block in the foreground with a long timeout**, never in the background" in reference

    def test_the_stop_table_keys_on_the_family_s_verdicts(self) -> None:
        for body in _bodies():
            table = body[body.index("## When something goes wrong") :]
            for verdict in INITIALIZER_VERDICTS_WITH_A_ROW:
                assert verdict in table, f"the stop table has no row for {verdict}"
            assert "| any other `refused:`, `failed: write` or `failed: commit` |" in table
            assert "| any other `make serve` verdict |" in table
            # A server the user started from the copy is left running by `make serve`, and its verdict says so.
            assert "when it says the server was stopped, read `<dir>/.serve/server.log`'s tail" in table
            assert "one still running is the user's to stop" in table
            # `copied` is what --dry-run and --no-create print, and it leads to the uncreated copy.
            assert "`copied`, which only `--dry-run` or `--no-create` prints, to [references/uncreated-copy.md](references/uncreated-copy.md)" in body
            for verdict in SERVE_VERDICTS:
                assert verdict in body, f"the skill never reads {verdict}"

    def test_the_key_reaches_the_gesture_without_crossing_the_conversation(self) -> None:
        for body in _bodies():
            assert "`write-env-file.sh` moves it on one branch and `make create` on the other" in body
            row = next(line for line in body.splitlines() if line.startswith("| `refused: no-key` |"))
            assert "a harness restarted from a shell that exports the key" in row
            # An unattended model took the second way itself in the phase 5b smoke sessions.
            assert row.startswith("| `refused: no-key` | STOP and offer two ways, running neither until the user picks: ")
            assert "`--no-create` and a `<dir>/.env.local` the user writes in their own editor" in row
            # A key is refused by every plane but the one that issued it.
            assert "never substitute a base URL the user did not declare" in body
            assert "a git identity is the user's to set, never yours" in body

    def test_the_method_app_ends_with_the_page_answering_and_the_url_first(self) -> None:
        for body in _bodies():
            assert "**Never report a URL that did not answer**: only those two verdicts give one." in body
            # The Server Actions spend the key for whoever calls them: `make serve` binds loopback and
            # refuses a copy that cannot, and the skill starts the server no other way.
            assert "**Never start the server any other way** (`make dev`, `npm run dev`, an `APP_HOST`)" in body
            assert "| `make serve` says `refused: not-loopback` | report no URL" in body
            assert "Nothing is run through the method." in body
            assert "**On the method app, the URL comes first**" in body
            assert "how the verdict says to stop it" in body
            # The warnings are relayed, the LICENSE holder first.
            assert "first that `LICENSE` still names the template's holder when it does" in body
            # The method app's `git:` line says what happened, a repository under an ignored path included.
            assert "the template's version and the git outcome; that" in body

    def test_placeholders_are_substituted_as_one_shell_word(self) -> None:
        for body in _bodies():
            assert "**Every placeholder is one shell word**" in body
            for block in _bash_blocks(body):
                for placeholder in ("<dir>", "<method>"):
                    assert f"'{placeholder}'" in block or placeholder not in block, f"an unquoted {placeholder} in {block!r}"

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
    """`references/uncreated-copy.md`: a copy of the method app that `make create` has not run in.

    The initializer leaves one after `--dry-run`, `--no-create` or a `failed: create`, and a user may stand
    in one made by hand. The reference runs the copy's own `make create` directly, and reads git first for a
    copy the initializer did not make. Its two blocks are extracted and executed below.
    """

    @property
    def reference(self) -> str:
        return UNCREATED_COPY_REFERENCE.read_text(encoding="utf-8")

    def test_it_opens_on_its_condition_and_hands_back_to_serve(self) -> None:
        entry = self.reference.split("\n\n")[1]
        assert entry.startswith("Read this when ")
        for condition in ("`copied` (after `--dry-run` or `--no-create`)", "`failed: create`", "the user stands in one"):
            assert condition in entry, condition
        assert "`/pipelex-scaffold` then goes on at branch A's step 2, `make serve`" in self.reference
        # A Codex session served a copy whose `make all` was red in the phase 5b smoke sessions.
        assert "**Never run `make serve` on a copy whose `make create` failed**" in entry
        assert "and `make serve` waits until it is fixed. On `0`, go on to `make serve`." in self.reference

    def test_a_copy_the_initializer_committed_goes_straight_to_create(self) -> None:
        """A user standing in a copy seldom says who made it, so its history is read before the git reading a
        hand-made copy gets, and a copy already committed is not read as one that needs a repository."""
        reference = self.reference
        block = _recipe(reference, INITIALIZER_COPY_MARKER)
        assert PRISTINE_SUBJECT_PREFIX in block
        assert reference.index(INITIALIZER_COPY_MARKER) < reference.index(OWN_REPOSITORY_MARKER)
        # The commit this file makes by hand carries the subject the block recognizes.
        assert PRISTINE_COPY_COMMIT.split('"')[1].startswith(PRISTINE_SUBJECT_PREFIX)

    def test_a_cause_the_sandbox_imposes_is_handed_to_the_user(self) -> None:
        """Codex's `workspace-write` sandbox denies `ps`, which the template's tests and `make serve` need,
        and no edit in the copy lifts it (`L-260923-e82e4a`)."""
        reference = self.reference
        assert "**A cause the harness's own sandbox imposes is the user's to lift, never yours to work around**" in reference
        assert "A red `make all` is fixed, never handed off, but for the one cause below." in reference

    def test_the_create_gesture_is_driven_and_never_reimplemented(self) -> None:
        reference = self.reference
        create = _recipe(reference, CREATE_MARKER)
        assert "make -C <dir> create METHOD='<method>'" in create
        assert "**given as an absolute path**" in reference
        assert "None of `make create`'s work is reimplemented here" in reference
        assert "never by editing `src/generated/`" in reference
        assert "It commits nothing." in reference
        # The warnings are read off the whole log and relayed, the LICENSE holder first.
        # Byte order, so that no locale's collation merges two warnings that differ only in punctuation.
        assert "grep -E '^(warning: |! )' \"$log\" | LC_ALL=C sort -u" in create
        assert "**The gesture's warnings are read from the whole log, not from its tail.**" in reference
        assert "`LICENSE_HOLDER='…'`" in reference
        # A refusal in the read-only half can run again; a failure after the scaffold cannot.
        assert "changed no tracked file, so it can run again" in reference
        assert "cannot be undone by running `make create` again" in reference
        # The key reaches the gesture from the shell or a file the user wrote, and is never read back.
        assert "`make create` reads that file and never touches an `.env.local` that already exists. Nothing reads it back" in reference
        # The report's plane rule falls back to production, which a file the user wrote may contradict.
        assert "names its plane only from a `PIPELEX_BASE_URL` the shell exports, never production by default" in reference

    def test_the_fresh_copy_is_recognized_before_git_is_initialized_in_it(self) -> None:
        """The method app's own checkout sits inside the family repository.

        Initializing first would hide the family's `origin` behind a new, remote-less repository and
        let `make create` rewrite the template's tracked files.
        """
        reference = self.reference
        assert "Read git before initializing anything." in reference
        assert "**A directory another repository already tracks is not a fresh copy**" in reference
        block = _recipe(reference, OWN_REPOSITORY_MARKER)
        # The origin is read, and a tracked directory refused, before any repository is made.
        assert block.index("remote get-url origin") < block.index("init -b main")
        assert "*/Pipelex/pipelex-method-apps*|*:Pipelex/pipelex-method-apps*" in block
        # Only a copy outside every repository, or one the enclosing repository ignores, gets one: the family
        # plants no repository where another repository sees it.
        assert block.count("init -b main") == 2
        assert "outside) git -C <dir> init -b main ;;" in block
        assert 'check-ignore -q -- "./${real##*/}"; then git -C <dir> init -b main' in block
        assert (
            "**A copy that sits untracked inside another repository's work tree that does not ignore it gets no repository and no commit**"
            in reference
        )
        # The first commit is looked for only once the copy is its own repository.
        assert reference.index(OWN_REPOSITORY_MARKER) < reference.index("git -C <dir> rev-parse -q --verify HEAD")

    def test_the_copy_s_pristine_commit_cannot_reach_an_enclosing_repository(self) -> None:
        """`git -C <dir>` sets git's working directory and scopes nothing, and a bare `git commit`
        commits the whole index, so the copy's commit carries the pathspec on both commands."""
        reference = self.reference
        assert reference.count("git -C <dir> add -A -- .") == 1
        assert PRISTINE_COPY_COMMIT in reference
        assert "git -C <dir> add -A &&" not in reference


@NEEDS_GIT
class TestUncreatedCopyRecipes:
    """The uncreated copy's blocks, extracted from the reference and executed in every POSIX shell on the
    machine: they are commands an agent types, and a harness may run them in any of those shells."""

    @staticmethod
    def _git(repository: Path, *arguments: str) -> str:
        return subprocess.run(["git", "-C", str(repository), *arguments], capture_output=True, text=True, check=True).stdout

    @staticmethod
    def _own_repository(*, dir_literal: str, shell: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        block = _recipe(UNCREATED_COPY_REFERENCE.read_text(encoding="utf-8"), OWN_REPOSITORY_MARKER).replace("<dir>", dir_literal)
        assert "<dir>" not in block
        return subprocess.run([*shell, "-c", block], capture_output=True, text=True, check=False, cwd=str(cwd))

    @staticmethod
    def _initializer_copy(*, dir_literal: str, shell: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        block = _recipe(UNCREATED_COPY_REFERENCE.read_text(encoding="utf-8"), INITIALIZER_COPY_MARKER).replace("<dir>", dir_literal)
        assert "<dir>" not in block
        return subprocess.run([*shell, "-c", block], capture_output=True, text=True, check=False, cwd=str(cwd))

    @classmethod
    def _committed_copy(cls, target: Path, *subjects: str) -> None:
        target.mkdir(parents=True)
        subprocess.run(["git", "-C", str(target), "init", "-q", "-b", "main"], check=True)
        for number, subject in enumerate(subjects):
            (target / f"file-{number}.txt").write_text(f"{number}\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(target), "add", "-A", "--", "."], check=True)
            _git_commit(target, subject)

    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    @pytest.mark.parametrize(
        "subject",
        [f"{PRISTINE_SUBJECT_PREFIX}0.4.0 (2598d4e)", f"{PRISTINE_SUBJECT_PREFIX}0.4.0"],
        ids=["the-initializer-s", "made-by-hand"],
    )
    def test_a_copy_already_committed_prints_its_pristine_commit(self, tmp_path: Path, shell: list[str], subject: str) -> None:
        target = tmp_path / "receipt review"
        self._committed_copy(target, subject, "the user's own change")
        pristine = self._git(target, "log", "--format=%h", "-1", "HEAD~1").strip()
        result = self._initializer_copy(dir_literal="'receipt review'", shell=shell, cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [f"{pristine} {subject}"]

    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    @pytest.mark.parametrize("case", ["no-repository", "another-history", "inside-a-repository-that-holds-one"])
    def test_any_other_copy_prints_nothing(self, tmp_path: Path, shell: list[str], case: str) -> None:
        """A copy the block prints nothing for goes on to the git reading for a copy made by hand."""
        target = tmp_path / "receipt-review"
        if case == "no-repository":
            target.mkdir()
        elif case == "another-history":
            self._committed_copy(target, "the user's copy")
        else:
            self._committed_copy(tmp_path / "monorepo", f"{PRISTINE_SUBJECT_PREFIX}0.4.0 (2598d4e)")
            target = tmp_path / "monorepo" / "apps" / "receipt-review"
            target.mkdir(parents=True)
        result = self._initializer_copy(dir_literal=str(target), shell=shell, cwd=tmp_path)
        assert result.stdout == ""
        assert not (case == "no-repository" and (target / ".git").exists())

    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    def test_a_copy_without_a_repository_gets_one(self, tmp_path: Path, shell: list[str]) -> None:
        target = tmp_path / "receipt review"
        target.mkdir()
        (target / "package.json").write_text('{"name": "pipelex-method-webapp-js"}\n', encoding="utf-8")
        result = self._own_repository(dir_literal="'receipt review'", shell=shell, cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert (target / ".git").is_dir()
        assert self._git(target, "symbolic-ref", "--short", "HEAD").strip() == "main"

    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    def test_a_copy_inside_another_repository_gets_none_of_its_own(self, tmp_path: Path, shell: list[str]) -> None:
        """The initializer plants no repository inside another's work tree, so a later session that meets
        its copy there, after `--no-create` or `failed: create`, plants none either."""
        parent = tmp_path / "monorepo"
        parent.mkdir()
        subprocess.run(["git", "-C", str(parent), "init", "-q", "-b", "trunk"], check=True)
        (parent / "README.md").write_text("theirs\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(parent), "add", "README.md"], check=True)
        _git_commit(parent, "the user's own history")
        history = self._git(parent, "log", "--format=%H")
        target = parent / "apps" / "receipt-review"
        target.mkdir(parents=True)
        (target / "package.json").write_text('{"name": "pipelex-method-webapp-js"}\n', encoding="utf-8")
        result = self._own_repository(dir_literal=str(target), shell=shell, cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert result.stdout == "inside another repository's work tree: no repository and no commit of its own\n"
        assert not (target / ".git").exists()
        assert self._git(target, "rev-parse", "--show-toplevel").strip() == str(parent.resolve())
        assert self._git(parent, "log", "--format=%H") == history
        assert self._git(parent, "diff", "--cached", "--name-only") == ""

    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    @pytest.mark.parametrize(("rule", "own_repository"), [("apps/\n", True), ("*\n!*/\n", False)], ids=["ignored", "every-file-ignored"])
    def test_a_copy_the_enclosing_repository_ignores_gets_one_of_its_own(
        self, tmp_path: Path, shell: list[str], rule: str, own_repository: bool
    ) -> None:
        """Ruled 2026-09-25: the initializer gives a copy under an ignored path a repository of its own, so a
        later session gives one to a copy it finds there. What counts is the directory: one the enclosing
        repository sees, though it ignores every file in it, gets none, since a repository there would show."""
        parent = tmp_path / "monorepo"
        parent.mkdir()
        subprocess.run(["git", "-C", str(parent), "init", "-q", "-b", "trunk"], check=True)
        (parent / "README.md").write_text("theirs\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(parent), "add", "README.md"], check=True)
        _git_commit(parent, "the user's own history")
        (parent / ".gitignore").write_text(rule, encoding="utf-8")
        target = parent / "apps" / "receipt-review"
        target.mkdir(parents=True)
        (target / "package.json").write_text('{"name": "pipelex-method-webapp-js"}\n', encoding="utf-8")
        result = self._own_repository(dir_literal=str(target), shell=shell, cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        if own_repository:
            assert self._git(target, "rev-parse", "--show-toplevel").strip() == str(target.resolve())
            assert self._git(target, "symbolic-ref", "--short", "HEAD").strip() == "main"
        else:
            assert result.stdout == "inside another repository's work tree: no repository and no commit of its own\n"
            assert not (target / ".git").exists()
        assert self._git(parent, "status", "--porcelain", "--untracked-files=all", "--", "apps") == ""

    @staticmethod
    def _repository_tracking_a_copy(root: Path, origin: str) -> Path:
        """A repository with `origin` set that tracks a method-app copy in `webapp-js/`, as the family does."""
        root.mkdir()
        subprocess.run(["git", "-C", str(root), "init", "-q", "-b", "main"], check=True)
        subprocess.run(["git", "-C", str(root), "remote", "add", "origin", origin], check=True)
        copy = root / "webapp-js"
        (copy / "scripts").mkdir(parents=True)
        (copy / "package.json").write_text('{"name": "pipelex-method-webapp-js"}\n', encoding="utf-8")
        (copy / "scripts" / "create.mts").write_text("// the create gesture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        _git_commit(root, "the family as it came")
        return copy

    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    @pytest.mark.parametrize(
        "origin",
        ["https://github.com/Pipelex/pipelex-method-apps.git", "git@github.com:Pipelex/pipelex-method-apps.git"],
        ids=["https", "ssh"],
    )
    def test_the_template_s_own_checkout_is_refused_and_left_alone(self, tmp_path: Path, shell: list[str], origin: str) -> None:
        family = tmp_path / "pipelex-method-apps"
        copy = self._repository_tracking_a_copy(family, origin)
        result = self._own_repository(dir_literal=str(copy), shell=shell, cwd=tmp_path)
        assert result.returncode != 0
        assert "template's own checkout" in result.stderr
        assert not (copy / ".git").exists()
        assert self._git(family, "status", "--porcelain") == ""

    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    def test_a_directory_another_repository_tracks_is_refused_whatever_its_origin(self, tmp_path: Path, shell: list[str]) -> None:
        """A fork of the family under another owner carries no Pipelex origin, and is still not a fresh copy."""
        fork = tmp_path / "our-apps"
        copy = self._repository_tracking_a_copy(fork, "https://github.com/someone/pipelex-method-apps.git")
        result = self._own_repository(dir_literal=str(copy), shell=shell, cwd=tmp_path)
        assert result.returncode != 0
        assert "already tracks this directory" in result.stderr
        assert not (copy / ".git").exists()

    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    @pytest.mark.parametrize("through_symlink", [False, True], ids=["direct", "through-a-symlink"])
    def test_a_copy_that_is_its_own_repository_is_left_alone(self, tmp_path: Path, shell: list[str], through_symlink: bool) -> None:
        real = tmp_path / "real"
        real.mkdir()
        target = real / "receipt-review"
        target.mkdir()
        subprocess.run(["git", "-C", str(target), "init", "-q", "-b", "trunk"], check=True)
        (target / "package.json").write_text('{"name": "pipelex-method-webapp-js"}\n', encoding="utf-8")
        subprocess.run(["git", "-C", str(target), "add", "package.json"], check=True)
        _git_commit(target, "the user's copy")
        before = (self._git(target, "log", "--format=%H"), self._git(target, "reflog"), self._git(target, "rev-parse", "--abbrev-ref", "HEAD"))
        spelled = target
        if through_symlink:
            (tmp_path / "linked").symlink_to(real, target_is_directory=True)
            spelled = tmp_path / "linked" / "receipt-review"
        result = self._own_repository(dir_literal=str(spelled), shell=shell, cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Reinitialized" not in result.stdout + result.stderr
        assert (
            self._git(target, "log", "--format=%H"),
            self._git(target, "reflog"),
            self._git(target, "rev-parse", "--abbrev-ref", "HEAD"),
        ) == before

    @staticmethod
    def _make_shim(directory: Path, body: str) -> Path:
        directory.mkdir(exist_ok=True)
        shim = directory / "make"
        shim.write_text(f"#!/bin/sh\n{body}", encoding="utf-8")
        shim.chmod(0o755)
        return directory

    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    @pytest.mark.parametrize("exit_code", [0, 3])
    def test_the_create_block_runs_the_gesture_and_reports_its_exit(self, tmp_path: Path, shell: list[str], exit_code: int) -> None:
        """The block reports the gesture's exit status in every shell, zsh included, where `status` is read-only."""
        arguments_log = tmp_path / "make-arguments.log"
        shim_bin = self._make_shim(tmp_path / "shim-bin", f'printf \'%s\\n\' "$@" > "{arguments_log}"\necho "the gesture ran"\nexit {exit_code}\n')
        target = tmp_path / "receipt-review"
        target.mkdir()
        bundle = tmp_path / "my bundles" / "receipt_review"
        recipe = _recipe(UNCREATED_COPY_REFERENCE.read_text(encoding="utf-8"), CREATE_MARKER)
        block = recipe.replace("<dir>", str(target)).replace("<method>", str(bundle))
        environment = {**os.environ, "PATH": f"{shim_bin}{os.pathsep}{os.environ['PATH']}", "TMPDIR": str(tmp_path)}

        result = subprocess.run([*shell, "-c", block], capture_output=True, text=True, check=False, env=environment)

        assert result.returncode == 0, result.stderr
        assert "the gesture ran" in result.stdout
        assert f"make create exited {exit_code};" in result.stdout
        # The path reaches make as one argument, space and all.
        assert arguments_log.read_text(encoding="utf-8").splitlines() == ["-C", str(target), "create", f"METHOD={bundle}"]
        assert result.stdout.splitlines()[-2:] == ["its warnings:", "none"]

    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    def test_the_create_block_lists_each_warning_the_gesture_printed_once(self, tmp_path: Path, shell: list[str]) -> None:
        """The gesture's warnings come before `make all`, whose output fills the tail, and the bootstrap's come
        twice, from its dry run and then from its write. The block lists each one once, whatever stream it was on."""
        scope_warning = "! a method_id is scoped to your key's organization, so `npm run codegen` on this slice needs a key of that same org."
        license_warning = "warning: LICENSE copyright line left untouched — pass --license-holder to claim it."
        before = tmp_path / "before.log"
        before.write_text(
            f"create: Receipt Review\n\n{scope_warning}\ncreate: checking the project values with the bootstrap (--dry-run)\n", encoding="utf-8"
        )
        warned = tmp_path / "warned.log"
        warned.write_text(f"{license_warning}\n", encoding="utf-8")
        after = tmp_path / "after.log"
        after.write_text("".join(f"make all: step {step}\n" for step in range(60)) + "npm warn deprecated glob@7.2.3\n", encoding="utf-8")
        shim_bin = self._make_shim(
            tmp_path / "shim-bin",
            f'cat "{before}"\ncat "{warned}" >&2\n'
            'echo "create: 2/6 run the bootstrap with the values above"\n'
            f'cat "{warned}" >&2\ncat "{after}"\nexit 0\n',
        )
        target = tmp_path / "receipt-review"
        target.mkdir()
        recipe = _recipe(UNCREATED_COPY_REFERENCE.read_text(encoding="utf-8"), CREATE_MARKER)
        block = recipe.replace("<dir>", str(target)).replace("<method>", "mt_receipt")
        environment = {**os.environ, "PATH": f"{shim_bin}{os.pathsep}{os.environ['PATH']}", "TMPDIR": str(tmp_path)}

        result = subprocess.run([*shell, "-c", block], capture_output=True, text=True, encoding="utf-8", check=False, env=environment)

        assert result.returncode == 0, result.stderr
        lines = result.stdout.splitlines()
        listed = lines[lines.index("its warnings:") + 1 :]
        assert listed == [scope_warning, license_warning]
        # The tail alone would have shown neither.
        assert scope_warning not in lines[: lines.index("its warnings:")]
        assert license_warning not in lines[: lines.index("its warnings:")]
