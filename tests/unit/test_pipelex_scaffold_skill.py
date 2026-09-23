"""Pin the pipelex-scaffold skill: two branches, no templates of its own, one commit, and a key that never crosses the conversation.

The initializer branch's two scripts are executed in `test_pipelex_scaffold_scripts.py`."""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir

REPO_ROOT = Path(__file__).parents[2]
SKILL_TEMPLATE = REPO_ROOT / "templates" / "skills" / "pipelex-scaffold" / "SKILL.md.j2"
INITIALIZERS_REFERENCE = REPO_ROOT / "skills" / "pipelex-scaffold" / "references" / "initializers.md"

BASH_BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)
# The method app's blocks, each named by a string that occurs in exactly one of them. The family's
# URL is swapped for a local repository, so the copy runs without the network.
METHOD_APPS_URL = "https://github.com/Pipelex/pipelex-method-apps.git"
METHOD_APP_MARKER = "pipelex-method-apps.git"
CREATE_MARKER = "create METHOD='<method>'"
DEV_SERVER_MARKER = 'nohup make -C "$dir" dev APP_PORT=<port> APP_HOST=127.0.0.1'
LOOPBACK_GUARD_MARKER = "node -e 'const dev = "
OWN_REPOSITORY_MARKER = "rev-parse --show-prefix"
PORT_CHECK_COMMAND = "make -C <dir> port-check APP_PORT=4300"
# The port is a version floor now (`[vars.floors].method_app_port`), so the TEMPLATE spells the
# variable and only a RENDER spells the number. Both spellings are asserted, each where it belongs:
# a template asserted on the rendered form would fail for the right reason and read as a regression,
# and a render asserted on the templated form would pass while the floor rendered as the empty string.
PORT_CHECK_COMMAND_TEMPLATED = "make -C <dir> port-check APP_PORT={{ floors.method_app_port }}"
STOP_COMMAND = 'for pid in $(lsof -ti tcp:<port> -sTCP:LISTEN); do kill "$pid"; done'
RESTART_COMMAND = "make dev APP_PORT=<port> APP_HOST=127.0.0.1"
PRISTINE_METHOD_APP_COMMIT = (
    'git -C <dir> add -A -- . && git -C <dir> commit -m "Start from Pipelex/pipelex-method-apps/webapp-js <version> (<sha>)" -- .'
)
TARGETS = ("prod", "codex", "mistral-vibe")

NEEDS_GIT = pytest.mark.skipif(shutil.which("git") is None, reason="the acquisition recipes are git")


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


# The acquisition chains' cleanup: one trap, set on the line after `mktemp`.
CLEANUP_TRAP = "trap 'rm -rf \"$tmp\"' EXIT; trap 'exit 130' INT; trap 'exit 143' TERM"


def _hanging_clone_shim(shim_bin: Path) -> Path:
    """A `git` whose `clone` starts writing its destination and never finishes; every other command is git's."""
    real_git = shutil.which("git")
    assert real_git is not None, "these tests already require git"
    shim_bin.mkdir(exist_ok=True)
    shim = shim_bin / "git"
    shim.write_text(
        f'#!/bin/sh\n[ "$1" = clone ] || exec "{real_git}" "$@"\nfor destination; do :; done\nmkdir -p "$destination/.git/objects"\nexec sleep 30\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return shim_bin


def _interrupt_during_clone(script: str, *, shell: list[str], shim_bin: Path, parent: Path, prefix: str, signal_number: int) -> int:
    """Run an acquisition chain, signal its whole process group once the clone has begun, and return its exit status.

    The group is signalled, not the shell alone, because that is how both interruptions arrive: Ctrl-C
    sends `INT` to the foreground group, and a harness stopping a command sends `TERM` to its group.
    """
    environment = {**os.environ, "PATH": f"{shim_bin}{os.pathsep}{os.environ['PATH']}"}
    process = subprocess.Popen([*shell, "-c", script], env=environment, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 10
        while not any((entry / ".git").is_dir() for entry in parent.iterdir() if entry.name.startswith(prefix)):
            assert process.poll() is None, "the chain ended before its clone began"
            assert time.monotonic() < deadline, "the clone never began"
            time.sleep(0.05)
        os.killpg(process.pid, signal_number)
        return process.wait(timeout=20)
    finally:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)


class TestPipelexScaffoldSkill:
    """The skill is executable guidance, so these tests guard what a user's new
    project depends on: nothing is written into a non-empty directory, the skill
    makes exactly one commit, the method app's gesture is delegated and never
    reimplemented, the key never crosses the conversation, and no MCP tool is needed.
    """

    REPO_ROOT = Path(__file__).parents[2]
    SKILLS = REPO_ROOT / "templates" / "skills"
    TEMPLATE = SKILLS / "pipelex-scaffold" / "SKILL.md.j2"
    REFERENCES_DIR = REPO_ROOT / "skills" / "pipelex-scaffold" / "references"
    REFERENCES = ("initializers.md", "version-managers.md", "github.md")
    SCRIPTS = ("commit-pristine.sh", "write-env-file.sh")
    SCRIPTS_DIR = REPO_ROOT / "skills" / "pipelex-scaffold" / "scripts"
    RULES = (
        "exactly two branches and carries no templates of its own",
        "no cookiecutter, no copier, no framework matrix of its own",
        "never write into a directory that exists and is not empty",
        "never offer to move, delete or merge what it holds to make room",
        "This is the **one commit this skill makes**",
        "**The starters are not scaffolded from.**",
        "**Never print a key, and never ask for one in the conversation.**",
        "a key in the transcript is a key to rotate",
        # A file-editing tool needs the literal value in its parameters, which is the transcript.
        "**the value moves only through a shell that expands the variable itself, and never through you**",
        "**no reading an env file back**",
        "and not validated",
        "One thing always confirms, in every mode: **`gh repo create`**",
        "Add **no** SDK dependency and create **no** empty `methods/` directory",
        "Nothing beyond what the initializer writes is authored by this skill",
        # A version manager that downloads a version is the toolchain install the step forbids.
        "**Never install a toolchain, and never let a version manager download one.**",
        # The default TS branch is prescribed in the reference, whose costs it states.
        "**Read [references/initializers.md](references/initializers.md) before running any initializer.**",
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
        for body in [self.scaffold] + [self.render(target) for target in TARGETS]:
            assert "uv init --package <dir>" not in body, "a bare uv init absorbs <dir> into the parent workspace"

    def test_fresh_clone_shortcut_and_template_checkout_stop(self) -> None:
        body = self.scaffold
        assert "**The fresh-clone shortcut.**" in body
        assert "Do not clone again." in body
        assert "this is the template, not a copy of it" in body

    def test_only_a_lone_git_reads_as_empty_and_no_cruft_list_joins_it(self) -> None:
        """`L-260912-724b71`, ruled 2026-09-13: a directory holding nothing but `.git` is empty.

        The refusal it narrows is the right one — the agent has no business deciding which of a
        user's files matter — and the exception exists because `mkdir my-app && cd my-app && git
        init` is an ordinary opening move and branch B runs `git init -b main` in the directory it
        is working in one step later, so without it the skill refuses a state it produces itself.

        The cruft list was deliberately declined in the same ruling: `.DS_Store`, `.idea/`,
        `.vscode/` and `Thumbs.db` keep refusing until a real report names one, because a list that
        grows by guesswork is how this rule drifts back into the judgement it forbids. So this test
        pins the exception as an entry named `.git` rather than as a predicate over ignorable
        files, and pins the four declined names as still-refusing — adding any of them to the
        exception means rewording a sentence asserted here, which is the point.
        """
        for body in [self.scaffold] + [self.render(target) for target in ("prod", "codex", "mistral-vibe")]:
            # The exception, at both sites, each stated as one named entry and not as a category.
            assert "**and a directory whose only entry is `.git` is empty for this rule**" in body
            assert "**A directory holding nothing but `.git` is empty here and is written into**" in body
            assert "a repository the user made is not work of theirs to write over" in body
            # And the refusal everything else still meets, with the declined names spelled out.
            assert (
                "**A lone `.git` is the only entry that does not make a directory non-empty, and that is a ruling about `.git` and nothing else**"
                in body
            )
            assert "not a class of files you may decide to overlook" in body
            assert "Every other entry still refuses, `.DS_Store`, `.idea/`, `.vscode/` and `Thumbs.db` included" in body
            assert "that exception is the one directory entry by name and not a class" in body
            assert "`.DS_Store`, `.idea/`, `.vscode/`, `Thumbs.db` and anything else still refuse" in body
            # Untouched by the ruling: a directory read as empty is never cleared, so the skill
            # still never offers to make room. Narrowing what counts as occupied is not permission
            # to empty what is.
            assert "never offer to move, delete or merge what it holds to make room" in body
            assert "never delete, move or write into it, and never offer to" in body

    def test_branch_a_acquires_into_the_directory_the_lone_git_rule_admits(self) -> None:
        """`L-260913-f28d9d`, ruled 2026-09-13: branch A serves the lone-`.git` directory too.

        The earlier ruling made a directory whose only entry is `.git` read as empty, which the
        initializer branch honours because its initializers accept such a directory. Branch A could
        not while it cloned into the destination, since git refuses one already holding a `.git`. The
        method app's chain acquires beside the directory and copies in, and these are the claims
        `TestMethodAppRecipes` executes it against, asserted on the template and every render.
        """
        for body in [self.scaffold] + [self.render(target) for target in TARGETS]:
            assert "One chain serves a directory that does not exist, an empty one, and one whose only entry is `.git`" in body
            assert "No `rm -rf` addresses a path under `<dir>`." in body
            assert "carries the entries beginning with a dot" in body
            assert "The directory is read once before anything is fetched and once more right before the copy" in body
            assert "The chain goes out as one command." in body
            assert "One trap removes the temporary path however the command ends, an interruption included." in body
            assert "an earlier run was killed before its trap could run. Leave it" in body
            assert "**The last line initializes only a directory with no repository of its own**" in body
            assert "the commit lands on the user's branch, on top of their history" in body
            assert "On branch A that directory is served by the acquisition beside it (Step 2) and never by a `git clone` into it" in body

    def test_the_lone_git_rule_does_not_promise_a_git_init_that_must_not_run(self) -> None:
        """Round 2: the "Where" row justified the exception with behaviour that cannot occur there.

        It read "branch B runs `git init -b main` in the directory it is working in one step later"
        — but in the lone-`.git` case the user has already run `git init`, so the pristine-commit
        script finds `<dir>` is its own repository and must not re-run it. The rationale invited an
        agent to expect the one command the script exists to gate.
        """
        for body in [self.scaffold] + [self.render(target) for target in ("prod", "codex", "mistral-vibe")]:
            assert "it does **not** re-run `git init` there" in body
            assert "since its pristine-commit script finds `<dir>` is already its own repository" in body
            assert "branch B runs `git init -b main` in the directory it is working in one step later" not in body

    def test_the_pristine_commit_confirms_when_it_lands_on_the_users_repository(self) -> None:
        """Round 2: the Mode section's carve-out was made false by the preserving acquisition.

        It read "the pristine commit does not need confirmation — it is on a directory this skill
        just created, holding the template as it came, and no user content is at stake". On the
        preserving path none of those three grounds holds: the directory is the user's, the commit
        lands on their branch, and `add -A -- .` sweeps in whatever their worktree was already
        showing. Step 3 was qualified when the ruling landed and the Mode section was not, which is
        the half-application this suite exists to catch.
        """
        for body in [self.scaffold] + [self.render(target) for target in ("prod", "codex", "mistral-vibe")]:
            assert "The pristine commit does not need confirmation **on a directory this skill created**" in body
            assert "**The acquisition into a directory that already held a repository is the exception**" in body
            assert "None of the three grounds above holds" in body
            # And Step 3 says what to put in front of the user rather than only what to report.
            assert "That is the commit the Mode section sends back for confirmation" in body
            assert "`git -C <dir> status --short` before staging says what will ride along" in body

    def test_branch_b_locks_the_python_project_before_the_hand_off(self) -> None:
        """Round 2: `uv init` writes a `pyproject.toml` and neither a lock file nor an environment.

        `/pipelex-integrate` picks the package manager off the lock file and reads its absence as
        `pip install` into the active environment, so the default Python scaffold — the minimal and
        script forms, which are what "no framework named" selects — handed over a uv project for the
        next skill to install into with pip, and into no environment at all. Asserted on the body and
        on the reference, because either alone is the half-application.
        """
        for body in [self.scaffold] + [self.render(target) for target in ("prod", "codex", "mistral-vibe")]:
            assert "**On Python, finish with `uv sync` from inside `<dir>`.**" in body
            assert "reads no lock file as `pip install` into the active environment" in body
        reference = INITIALIZERS_REFERENCE.read_text(encoding="utf-8")
        assert "**On Python, run `uv sync` from inside `<dir>` before the pristine commit, and commit the `uv.lock` it writes.**" in reference
        assert "`uv init` writes a `pyproject.toml` and nothing else: no lock file and no environment." in reference

    def test_the_initializer_branch_runs_its_scripts_and_reports_their_verdicts(self) -> None:
        """The pristine commit and the env file of the initializer branch are scripts (box E of the size
        diet): the skill runs each by path, its stop table keys on the verdict words they print, and the
        report turns the env file's verdict into words without the URL. The scripts themselves are
        executed in `test_pipelex_scaffold_scripts.py`."""
        for body in [self.scaffold] + [self.render(target) for target in TARGETS]:
            for verdict in ("`refused: nothing-to-commit`", "`refused: not-ignored`", "`refused: no-directory`", "`empty`"):
                assert verdict in body, f"the stop table has no row for {verdict}"
            assert "`committed:` names the commit and lists the staged paths after it" in body
            assert "`kept:` names a commit the initializer made itself, which is the pristine one" in body
            for word in ("**`filled`**", "**`kept`**", "**`empty`**", "**`base-url=copied`**", "**`base-url=file`**"):
                assert word in body, f"the report does not say what {word} means"
            assert "warn that a key from `app.pipelex.com` is production's and will be refused there" in body
            # The method app's report still reads the plane by a test, never an echo.
            assert '`[ "${PIPELEX_BASE_URL%/}" = https://api.pipelex.com ] && echo production || echo other`' in body
            # The env file's own command left the skill: the script is the only thing that writes it.
            assert ">> <dir>/.env" not in body
            assert "cp -n" not in body

    def test_declares_no_mcp_tool(self) -> None:
        """The scaffold skill is MCP-free: no allowed-tools entry, no MCP-absent STOP message."""
        body = self.scaffold
        assert "mcp__" not in body
        assert "plugin manifest spawns" not in body
        assert "It needs no MCP tool and never handles an API key itself" in body

    def test_integrate_hands_a_missing_project_to_scaffold(self) -> None:
        integrate = (self.SKILLS / "pipelex-integrate" / "SKILL.md.j2").read_text(encoding="utf-8")
        assert "none means offering" in integrate
        assert "pipelex-scaffold" in integrate

    def test_the_references_carry_the_initializers_the_version_managers_and_github(self) -> None:
        # The initializers reference sends the reader to the repository test the script runs rather
        # than to the inference the skill forbids by name.
        initializers = (self.REFERENCES_DIR / "initializers.md").read_text(encoding="utf-8")
        assert initializers.split("\n\n")[1].startswith("Read this when ")
        assert "**the test, never the inference from which initializer ran**" in initializers
        assert "pipelex-starter" not in initializers and "the starter" not in initializers
        # A sourced shell does not survive the next command, so the runtime is resolved to a path.
        managers = (self.REFERENCES_DIR / "version-managers.md").read_text(encoding="utf-8")
        assert managers.split("\n\n")[1].startswith("Read this when ")
        assert "A runtime the machine already has, where only the `PATH` is missing it, is not a missing piece" in managers
        assert "## Resolve it to an absolute path, never source a shell" in managers
        assert "**A shim is not a runtime.**" in managers
        assert "**`volta` and `mise` install on first use.**" in managers
        github = (self.REFERENCES_DIR / "github.md").read_text(encoding="utf-8")
        assert github.split("\n\n")[1].startswith("Read this when ")
        assert "**state the exact command and confirm before running it**" in github
        assert "gh repo create <owner>/<name> --private --source <dir> --remote origin" in github
        assert "--template" in github and "--template Pipelex/" not in github
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
        assert "`--no-workspace` is on every `uv init` above" in initializers
        assert "| `uv init --package <dir>`" not in initializers, "a bare uv init absorbs <dir> into the parent workspace"
        assert "uv init --package <dir> &&" not in initializers, "a bare uv init absorbs <dir> into the parent workspace"
        # npm resolves the project it writes to upward exactly as uv does, and unlike uv it finds the
        # parent and silently succeeds, so every follow-on install is scoped too.
        for recipe in ("(cd <dir> && npm install)", "(cd <dir> && npm install express && npm install --save-dev @types/express)"):
            assert recipe in initializers, f"npm install not scoped to the project: {recipe}"
        assert "**Every follow-on `npm install` above is parenthesised" in initializers
        # The minimal TS default is the very resolution the emitter defect breaks.
        assert "is exactly the shape that meets the ts-zod emitter's extensionless-import defect" in initializers
        # `tsc --init` writes an active `"types": []`, which switches off the @types/node the line
        # before it installed — the integrate call site then fails TS2591 on node:path and process.
        assert '`tsc --init` writes `"types": []` as an active key' in initializers
        assert 'set `"types": ["node"]` as part of the recipe' in initializers

    def test_the_method_app_s_pristine_commit_cannot_reach_an_enclosing_repository(self) -> None:
        """`git -C <dir>` sets git's working directory and scopes nothing, and a bare `git commit`
        commits the whole index, so the method app's commit carries the pathspec on both commands.
        The initializer branch's commit is `commit-pristine.sh`'s, executed in the scripts' test."""
        body = self.TEMPLATE.read_text(encoding="utf-8")
        assert body.count("git -C <dir> add -A -- .") == 1
        assert PRISTINE_METHOD_APP_COMMIT in body
        assert "git -C <dir> add -A &&" not in body

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_every_platform_renders_the_skill_and_its_references(self, target_name: str) -> None:
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-scaffold"],
            target_name=config.name,
        )
        body = next(content for path, content in rendered.items() if path.match("skills/pipelex-scaffold/SKILL.md"))
        assert "# Scaffold a project for Pipelex methods" in body
        assert "{%" not in body
        assert "{{" not in body
        assert "mcp__" not in body
        for rule in self.RULES:
            assert rule in body, f"{target_name}: missing rule: {rule}"
        if target_name == "prod":
            assert "`cd <dir> && claude`" in body
            assert "with `/pipelex-integrate`" in body
        else:
            assert "`cd <dir> && claude`" not in body
            assert "opening `../pipelex-integrate/SKILL.md`" in body

        skill_dir = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-scaffold"
        for reference in self.REFERENCES:
            assert (skill_dir / "references" / reference).is_file(), f"{target_name}: missing references/{reference}"
        assert sorted(path.name for path in (skill_dir / "references").iterdir()) == sorted(self.REFERENCES), f"{target_name}: a stale reference"
        for script in self.SCRIPTS:
            assert (skill_dir / "scripts" / script).is_file(), f"{target_name}: missing scripts/{script}"
            assert f'/scripts/{script}"' in body, f"{target_name}: the skill does not run scripts/{script} by path"
        if target_name != "prod":
            # Codex and Vibe substitute nothing, so the placeholder is defined before its first use.
            assert body.index("`<skill-dir>` stands for the directory holding this `SKILL.md`") < body.index("<skill-dir>/scripts/")

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_the_committed_references_match_the_source_byte_for_byte(self, target_name: str) -> None:
        """The references are executable know-how, and the committed target copies are the ones a
        user installs — so compare against those, not against a fresh `copytree` into a tmp dir,
        which only ever asserts that `shutil` copies bytes. A stale committed copy is the whole
        failure mode, and it is invisible to any assertion that rebuilds its own expected side.
        """
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        installed = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-scaffold" / "references"
        for reference in self.REFERENCES:
            assert (installed / reference).is_file(), f"{target_name}: missing references/{reference}"
            assert (installed / reference).read_bytes() == (self.REFERENCES_DIR / reference).read_bytes(), (
                f"{target_name}: references/{reference} is stale — run `make build`"
            )
        scripts = installed.parent / "scripts"
        for script in self.SCRIPTS:
            assert (scripts / script).read_bytes() == (self.SCRIPTS_DIR / script).read_bytes(), f"{target_name}: scripts/{script} is stale"
            assert os.access(scripts / script, os.X_OK), f"{target_name}: scripts/{script} lost its executable bit"


class TestMethodAppBranch:
    """The TypeScript branch is the method app, driven to a running page.

    Ratified on 2026-09-16 with the method-app template: a TypeScript web app around a method is a
    copy of `pipelex-method-apps`' `webapp-js/`, made the user's by the template's own `make create`
    and left with its dev server up and its URL reported. The starters left the skill on
    2026-09-23 (box E of the size diet). The skill carries none of the gesture: it copies,
    commits once, drives the command and proves the page answers. Asserted on the template and on
    every render, because a rule that holds only in `templates/` is a rule no user reads.
    """

    @staticmethod
    def bodies() -> list[str]:
        return [SKILL_TEMPLATE.read_text(encoding="utf-8")] + [_render_skill(target) for target in TARGETS]

    def test_the_typescript_branch_copies_the_method_app(self) -> None:
        for body in self.bodies():
            assert "the `webapp-js/` directory of `pipelex-method-apps`" in body
            assert "**The starters are not scaffolded from.**" in body
            assert "**The method app needs the method first.**" in body
            recipe = _recipe(body, METHOD_APP_MARKER)
            # Only the template directory crosses, and only into a directory the "Where" rule admits.
            assert 'cp -R "$tmp/webapp-js"/. "$dir"/' in recipe
            assert recipe.count('case "$(ls -A "$dir")" in ""|.git)') == 2, "the directory is read before the fetch and again before the copy"
            assert '[ -f "$tmp/webapp-js/package.json" ]' in recipe
            # One cleanup, the trap, set before anything can fail.
            assert recipe.index(CLEANUP_TRAP) < recipe.index("git clone")
            assert recipe.count('rm -rf "$tmp"') == 1
            # A repository the user made is never initialized over.
            assert recipe.rstrip().endswith('[ -e "$dir/.git" ] || git -C "$dir" init -b main')
            assert "**The `webapp-js/` test is load-bearing.**" in body
            assert "do not fall back to the gallery" in body
            # One pristine commit, named by the family and the directory.
            assert PRISTINE_METHOD_APP_COMMIT in body
            # The GitHub form is a reference read before any `gh` command.
            assert "read [references/github.md](references/github.md) before running any `gh` command" in body

    def test_the_create_gesture_is_driven_and_never_reimplemented(self) -> None:
        for body in self.bodies():
            create = _recipe(body, CREATE_MARKER)
            assert "make -C <dir> create METHOD='<method>'" in create
            assert "**given as an absolute path**" in body
            assert "only when the conversation already holds them or the user asked for something other than what the method carries" in body
            assert "none of it is reimplemented here" in body
            assert "never by editing `src/generated/`" in body
            assert "It commits nothing." in body
            # The warnings are read off the whole log and relayed, the LICENSE holder first.
            # Byte order, so that no locale's collation merges two warnings that differ only in punctuation.
            assert "grep -E '^(warning: |! )' \"$log\" | LC_ALL=C sort -u" in create
            assert "**The gesture's warnings are read from the whole log, not from its tail.**" in body
            assert "`LICENSE_HOLDER='…'`" in body
            assert "`LICENSE`, `LICENSE_HOLDER` and `LICENSE_YEAR` only when the user gave them" in body
            assert (
                "- every warning the gesture printed, each with what answers it, and first, when the gesture left it in place, "
                "that `LICENSE` still names the template's copyright holder"
            ) in body
            # The gesture installs the dependencies before its refusals, dry run included.
            assert "refuses before it changes a tracked file" in body
            assert "changes no tracked file, so the gesture can run again" in body
            assert "exactly as it was, so the gesture" not in body
            # The gesture writes its own env file, under the skill's key guard.
            assert "### Step 5: Start the dev server and prove the page answers" in body
            assert "The `.env.local` it wrote is not: the key guard above holds for it." in body
            # The key reaches the gesture without crossing the conversation, and before anything is made.
            assert "**The method app also needs a key its gesture can read.**" in body
            assert "never ask for the key in the conversation" in body
            assert "never substitute a base URL the user did not declare" in body

    def test_placeholders_are_substituted_as_one_shell_word(self) -> None:
        for body in self.bodies():
            assert "**Every placeholder is substituted as one shell word.**" in body
            assert "unless the block already quotes the placeholder, as `METHOD='<method>'` does" in body

    def test_the_fresh_copy_is_recognized_before_git_is_initialized_in_it(self) -> None:
        """The method app's own checkout sits inside the family repository.

        Initializing first would hide the family's `origin` behind a new, remote-less repository and
        let `make create` rewrite the template's tracked files.
        """
        for body in self.bodies():
            assert "**Read git before initializing anything.**" in body
            assert "**A directory another repository already tracks is not a fresh copy**" in body
            block = _recipe(body, OWN_REPOSITORY_MARKER)
            # The origin is read, and a tracked directory refused, before any repository is made.
            assert block.index("remote get-url origin") < block.index("init -b main")
            assert block.index("ls-files -- . | grep -q .") < block.rindex("init -b main")
            assert "*/Pipelex/pipelex-method-apps*|*:Pipelex/pipelex-method-apps*" in block
            # The first commit is looked for only once the copy is its own repository.
            shortcut = body[body.index("**The fresh-clone shortcut.**") :]
            assert shortcut.index(OWN_REPOSITORY_MARKER) < shortcut.index("git -C <dir> rev-parse -q --verify HEAD")

    def test_no_block_assigns_a_name_zsh_reserves(self) -> None:
        """`status` is read-only in zsh, the default shell on macOS, so `status=$?` aborts the line."""
        for body in self.bodies():
            for block in _bash_blocks(body):
                assert re.search(r"(^|[\s;])(status|path|argv)=", block) is None, f"a block assigns a zsh-reserved name: {block!r}"

    def test_the_method_app_ends_with_the_page_answering_and_the_url_first(self) -> None:
        for body in self.bodies():
            assert "The one server it starts is the method app's own dev server" in body
            expected = PORT_CHECK_COMMAND_TEMPLATED if body == SKILL_TEMPLATE.read_text(encoding="utf-8") else PORT_CHECK_COMMAND
            assert expected in body
            dev = _recipe(body, DEV_SERVER_MARKER)
            assert "--retry-connrefused" in dev
            # A per-attempt limit alone lets a hanging server hold the command for as long as the retries last.
            assert "--retry-max-time 120" in dev
            # The Server Actions spend the key for whoever calls them, from the moment the port opens: a
            # copy whose dev script names no loopback host is not started, and the listener is checked,
            # and a stray one stopped, in the same command and before the first request.
            assert "**The server listens on this machine alone, and a copy that cannot promise it is not started.**" in body
            guard = _recipe(body, LOOPBACK_GUARD_MARKER)
            assert body.index(guard) < body.index(dev)
            assert dev.index("until lsof -ti tcp:<port> -sTCP:LISTEN") < dev.index("curl ")
            assert dev.index('kill "$pid"') < dev.index("curl ")
            assert "which is not this project" in dev
            assert "report no URL" in body
            # No listener is a server that did not start, never a diagnosis about the host.
            assert "**Nothing listens** means the server did not start" in body
            assert "| Nothing listens on the port | the server did not start" in body
            # A server still starting when the wait ends is stopped, launcher and descendants, before the retry.
            assert "nothing to stop" not in body
            assert dev.index("launcher=$!") < dev.index("until lsof")
            assert 'stop_tree "$launcher"' in dev
            # bash's and sh's built-in `pwd -P` keep the typed letter case, and `lsof` reports the disk's.
            assert "dir=$(cd <dir> && env pwd -P)" in dev
            assert "which the template's newer versions do not" not in body
            # A retry never leaves the first server running on another port.
            assert "**Never start a second server while one this step started still runs**" in body
            assert "is already served by this checkout" in body
            assert "retried on the same port once the server this step started is stopped" in body
            assert "**Never report a URL that did not answer.**" in body
            assert "Nothing is run through the method" in body
            assert "**On the method app, the URL comes first**" in body
            assert STOP_COMMAND in body
            # The report restarts the server on the port it reported, bound as the skill bound it.
            assert f"how to start it again (`{RESTART_COMMAND}` from inside the project)" in body
            # Without lsof, port-check passes whatever holds the port and the listener cannot be read; without pgrep, a slow start cannot be stopped.
            assert "The method app also needs `make`, `curl`, `lsof` and `pgrep`" in body

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_recipes_executed_here_are_the_bytes_every_target_ships(self, target_name: str) -> None:
        """`TestMethodAppRecipes` executes the template, so the renders must carry the same blocks.

        The method app's blocks carry no Jinja, which is what makes reading the template safe, but that
        is a claim about the renders, so it is read off them rather than argued.
        """
        config = load_target_config(REPO_ROOT / "targets", target_name)
        installed = (resolve_output_dir(REPO_ROOT, config.source) / "skills" / "pipelex-scaffold" / "SKILL.md").read_text(encoding="utf-8")
        template = SKILL_TEMPLATE.read_text(encoding="utf-8")
        for marker in (METHOD_APP_MARKER, CREATE_MARKER, DEV_SERVER_MARKER, OWN_REPOSITORY_MARKER, LOOPBACK_GUARD_MARKER):
            assert _recipe(installed, marker) == _recipe(template, marker), f"{target_name}: the shipped recipe is not the one executed here"

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


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def _answers(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/", timeout=2) as response:
            return bool(response.status == 200)
    except OSError:
        return False


def _can_bind(host: str) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, 0))
        except OSError:
            return False
        return True


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# The dev-server block waits on `lsof`, stops a slow start with `pgrep` and proves the page with `curl`;
# all three are the method app's prerequisites.
NEEDS_SERVER_TOOLS = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in ("lsof", "curl", "pgrep")), reason="the dev-server block needs lsof, pgrep and curl"
)


@NEEDS_GIT
class TestMethodAppRecipes:
    """The method app's blocks, extracted from the skill and executed.

    The copy-out chain touches a directory the user may have made, so it is proven by running it
    as shipped against a local repository standing in for the family, with only the URL and
    `<dir>` bound. The create and dev-server blocks are run too,
    against a `make` stand-in, in every POSIX shell on the machine: they are commands an agent
    types, and a harness may run them in any of those shells.
    """

    WEBAPP_ENTRIES = frozenset({"package.json", "README.md", "src", "scripts", ".gitignore", ".env.example", ".claude", ".husky"})

    @staticmethod
    def _make_family(root: Path, *, with_webapp: bool) -> Path:
        """A stand-in for `pipelex-method-apps`: family files at the root, the template in `webapp-js/`."""
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / "VERSION").write_text("0.2.0\n", encoding="utf-8")
        (root / "README.md").write_text("# the family\n", encoding="utf-8")
        (root / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
        (root / ".github" / "workflows" / "family.yml").write_text("name: family\n", encoding="utf-8")
        if with_webapp:
            webapp = root / "webapp-js"
            for directory in ("src", "scripts", ".claude/skills/bootstrap", ".husky"):
                (webapp / directory).mkdir(parents=True)
            (webapp / "package.json").write_text('{"name": "pipelex-method-webapp-js", "version": "0.2.0"}\n', encoding="utf-8")
            (webapp / "README.md").write_text("# the web app template\n", encoding="utf-8")
            (webapp / "src" / "page.tsx").write_text("export default function Page() {}\n", encoding="utf-8")
            (webapp / "scripts" / "create.mts").write_text("// the create gesture\n", encoding="utf-8")
            (webapp / ".gitignore").write_text("node_modules/\n.env*.local\n", encoding="utf-8")
            (webapp / ".env.example").write_text("PIPELEX_BASE_URL=https://api.pipelex.com\nPIPELEX_API_KEY=\n", encoding="utf-8")
            (webapp / ".claude" / "skills" / "bootstrap" / "SKILL.md").write_text("# bootstrap\n", encoding="utf-8")
            (webapp / ".husky" / "pre-commit").write_text("npx lint-staged\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "init", "-q", "-b", "main"], check=True)
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        _git_commit(root, "the family as it came")
        return root

    @pytest.fixture(scope="class")
    def family(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        return self._make_family(tmp_path_factory.mktemp("method-apps"), with_webapp=True)

    @property
    def recipe(self) -> str:
        return _recipe(SKILL_TEMPLATE.read_text(encoding="utf-8"), METHOD_APP_MARKER)

    def _run(
        self,
        *,
        family: Path,
        target: Path,
        shell: list[str] | None = None,
        dir_literal: str | None = None,
        cwd: Path | None = None,
        path_prefix: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        script = self.recipe.replace(METHOD_APPS_URL, f"file://{family}").replace("<dir>", dir_literal or str(target))
        assert "<dir>" not in script and "github.com" not in script, "a placeholder survived the binding"
        environment = dict(os.environ)
        if path_prefix is not None:
            environment["PATH"] = f"{path_prefix}{os.pathsep}{environment['PATH']}"
        return subprocess.run(
            [*(shell or ["bash"]), "-c", script],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
            cwd=None if cwd is None else str(cwd),
        )

    @staticmethod
    def _git(repository: Path, *arguments: str) -> str:
        return subprocess.run(["git", "-C", str(repository), *arguments], capture_output=True, text=True, check=True).stdout

    @staticmethod
    def _entries(directory: Path) -> set[str]:
        return {entry.name for entry in directory.iterdir()}

    @staticmethod
    def _temporaries_beside(target: Path) -> list[str]:
        return [entry.name for entry in target.parent.iterdir() if entry.name.startswith(".pipelex-method-apps-")]

    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    def test_the_copy_populates_a_directory_that_does_not_exist(self, family: Path, tmp_path: Path, shell: list[str]) -> None:
        target = tmp_path / "receipt-review"
        result = self._run(family=family, target=target, shell=shell)
        assert result.returncode == 0, result.stderr
        # The template directory alone: none of the family's root files came with it.
        assert self._entries(target) == self.WEBAPP_ENTRIES | {".git"}
        assert (target / "README.md").read_text(encoding="utf-8") == "# the web app template\n"
        assert (target / ".claude" / "skills" / "bootstrap" / "SKILL.md").is_file()
        assert (target / ".husky" / "pre-commit").is_file()
        # A fresh repository, with no history and no remote, and the family's identity printed.
        assert self._git(target, "remote") == ""
        assert subprocess.run(["git", "-C", str(target), "rev-parse", "-q", "--verify", "HEAD"], capture_output=True, check=False).returncode != 0
        assert "0.2.0" in result.stdout
        assert self._git(family, "rev-parse", "HEAD").strip() in result.stdout
        assert self._temporaries_beside(target) == []

    def test_the_copy_populates_an_empty_directory(self, family: Path, tmp_path: Path) -> None:
        target = tmp_path / "receipt-review"
        target.mkdir()
        result = self._run(family=family, target=target)
        assert result.returncode == 0, result.stderr
        assert self._entries(target) == self.WEBAPP_ENTRIES | {".git"}

    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    def test_the_copy_leaves_the_users_repository_standing(self, family: Path, tmp_path: Path, shell: list[str]) -> None:
        target = tmp_path / "receipt-review"
        target.mkdir()
        subprocess.run(["git", "-C", str(target), "init", "-q", "-b", "trunk"], check=True)
        (target / "NOTES.md").write_text("mine\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(target), "add", "NOTES.md"], check=True)
        _git_commit(target, "my own first commit")
        subprocess.run(["git", "-C", str(target), "rm", "-q", "NOTES.md"], check=True)
        _git_commit(target, "and then I emptied the worktree")
        subprocess.run(["git", "-C", str(target), "remote", "add", "origin", "https://github.com/someone/theirs.git"], check=True)
        before = (self._git(target, "log", "--format=%H"), self._git(target, "reflog"), self._git(target, "rev-parse", "--abbrev-ref", "HEAD"))
        assert self._entries(target) == {".git"}

        result = self._run(family=family, target=target, shell=shell)

        assert result.returncode == 0, result.stderr
        # Not re-initialized: the same history, reflog, branch and remote.
        assert (
            self._git(target, "log", "--format=%H"),
            self._git(target, "reflog"),
            self._git(target, "rev-parse", "--abbrev-ref", "HEAD"),
        ) == before
        assert "https://github.com/someone/theirs.git" in self._git(target, "remote", "-v")
        assert "pipelex-method-apps" not in self._git(target, "remote", "-v")
        assert self._entries(target) == self.WEBAPP_ENTRIES | {".git"}

    @pytest.mark.parametrize("spelling", [".", "./"])
    def test_the_copy_serves_the_destination_spelled_here(self, family: Path, tmp_path: Path, spelling: str) -> None:
        target = tmp_path / "receipt-review"
        target.mkdir()
        subprocess.run(["git", "-C", str(target), "init", "-q", "-b", "main"], check=True)
        result = self._run(family=family, target=target, dir_literal=spelling, cwd=target)
        assert result.returncode == 0, result.stderr
        assert self._entries(target) == self.WEBAPP_ENTRIES | {".git"}
        assert self._temporaries_beside(target) == []

    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    def test_the_copy_serves_a_name_with_a_space_substituted_as_one_word(self, family: Path, tmp_path: Path, shell: list[str]) -> None:
        target = tmp_path / "receipt review"
        result = self._run(family=family, target=target, shell=shell, dir_literal="'receipt review'", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert self._entries(target) == self.WEBAPP_ENTRIES | {".git"}
        assert not (tmp_path / "receipt").exists() and not (tmp_path / "review").exists()
        assert self._temporaries_beside(target) == []

    @pytest.mark.parametrize(
        "occupants",
        [{"theirs.txt"}, {".git", "theirs.txt"}, {".DS_Store", ".idea", ".vscode", "Thumbs.db"}],
        ids=["a-file", "git-and-a-file", "ignorable-cruft"],
    )
    def test_the_copy_refuses_anything_but_nothing_or_a_lone_git(self, family: Path, tmp_path: Path, occupants: set[str]) -> None:
        target = tmp_path / "receipt-review"
        target.mkdir()
        for name in occupants:
            if name == ".git":
                subprocess.run(["git", "-C", str(target), "init", "-q", "-b", "main"], check=True)
            elif name in {".idea", ".vscode"}:
                (target / name).mkdir()
            else:
                (target / name).write_text("mine\n", encoding="utf-8")
        result = self._run(family=family, target=target)
        assert result.returncode != 0
        assert self._entries(target) == occupants
        assert self._temporaries_beside(target) == []

    def test_the_copy_stops_when_the_default_branch_carries_no_webapp_js(self, tmp_path: Path) -> None:
        """The family's `main` before its mono-repo release: a head with no `webapp-js/` copies nothing."""
        old_family = self._make_family(tmp_path / "old-family", with_webapp=False)
        target = tmp_path / "receipt-review"
        result = self._run(family=old_family, target=target)
        assert result.returncode != 0
        assert "no webapp-js/" in result.stderr
        assert self._entries(target) == set()
        assert self._temporaries_beside(target) == []

    def test_the_copy_removes_its_temporary_path_when_the_clone_fails(self, tmp_path: Path) -> None:
        target = tmp_path / "receipt-review"
        result = self._run(family=tmp_path / "no-such-repository", target=target)
        assert result.returncode != 0
        assert self._temporaries_beside(target) == []
        assert self._entries(target) == set()

    @pytest.mark.parametrize("signal_number", [signal.SIGINT, signal.SIGTERM], ids=["INT", "TERM"])
    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    def test_the_copy_removes_its_temporary_path_when_interrupted(self, tmp_path: Path, shell: list[str], signal_number: int) -> None:
        """The second reading found an empty `.pipelex-method-apps-…` beside an empty project, left by a
        session cleared while the chain ran. A harness sends `TERM` to the command's group first, and
        the trap turns it into an exit that removes the half-written clone."""
        assert self.recipe.index(CLEANUP_TRAP) < self.recipe.index("git clone")
        target = tmp_path / "receipt-review"
        script = self.recipe.replace(METHOD_APPS_URL, f"file://{tmp_path / 'never-reached'}").replace("<dir>", str(target))
        shim_bin = _hanging_clone_shim(tmp_path / "shim-bin")

        returncode = _interrupt_during_clone(
            script, shell=shell, shim_bin=shim_bin, parent=tmp_path, prefix=".pipelex-method-apps-", signal_number=signal_number
        )

        assert returncode == 128 + signal_number
        assert self._temporaries_beside(target) == []
        assert self._entries(target) == set()

    def test_no_delete_in_the_copy_addresses_a_path_under_the_target(self, family: Path, tmp_path: Path) -> None:
        real_rm = shutil.which("rm")
        assert real_rm is not None, "these tests already require a POSIX userland"
        log = tmp_path / "rm-targets.log"
        shim_bin = tmp_path / "shim-bin"
        shim_bin.mkdir()
        shim = shim_bin / "rm"
        shim.write_text(
            f'#!/bin/sh\nfor a in "$@"; do case "$a" in -*) ;; *) echo "$a" >> "{log}";; esac; done\nexec {real_rm} "$@"\n', encoding="utf-8"
        )
        shim.chmod(0o755)
        target = tmp_path / "receipt-review"
        target.mkdir()
        subprocess.run(["git", "-C", str(target), "init", "-q", "-b", "main"], check=True)

        result = self._run(family=family, target=target, path_prefix=shim_bin)

        assert result.returncode == 0, result.stderr
        deleted = [line for line in log.read_text(encoding="utf-8").splitlines() if line]
        assert deleted, "the shim recorded nothing — the chain no longer deletes, or the shim was bypassed"
        assert [line for line in deleted if Path(line) == target or target in Path(line).parents] == []
        assert all(".pipelex-method-apps-" in line for line in deleted), deleted

    @staticmethod
    def _own_repository(*, dir_literal: str, shell: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        block = _recipe(SKILL_TEMPLATE.read_text(encoding="utf-8"), OWN_REPOSITORY_MARKER).replace("<dir>", dir_literal)
        assert "<dir>" not in block
        return subprocess.run([*shell, "-c", block], capture_output=True, text=True, check=False, cwd=str(cwd))

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
    def test_a_copy_inside_another_repository_gets_its_own(self, tmp_path: Path, shell: list[str]) -> None:
        parent = tmp_path / "monorepo"
        parent.mkdir()
        subprocess.run(["git", "-C", str(parent), "init", "-q", "-b", "trunk"], check=True)
        (parent / "README.md").write_text("theirs\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(parent), "add", "README.md"], check=True)
        _git_commit(parent, "the user's own history")
        before = (self._git(parent, "log", "--format=%H"), self._git(parent, "status", "--porcelain"))
        target = parent / "apps" / "receipt-review"
        target.mkdir(parents=True)
        (target / "package.json").write_text('{"name": "pipelex-method-webapp-js"}\n', encoding="utf-8")
        result = self._own_repository(dir_literal=str(target), shell=shell, cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        # The copy is a repository of its own, with no commit yet, so the pristine commit is made there.
        assert self._git(target, "rev-parse", "--show-toplevel").strip() == str(target.resolve())
        assert subprocess.run(["git", "-C", str(target), "rev-parse", "-q", "--verify", "HEAD"], capture_output=True, check=False).returncode != 0
        assert self._git(parent, "log", "--format=%H") == before[0]

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
        block = _recipe(_render_skill("prod"), CREATE_MARKER).replace("<dir>", str(target)).replace("<method>", str(bundle))
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
        block = _recipe(_render_skill("prod"), CREATE_MARKER).replace("<dir>", str(target)).replace("<method>", "mt_receipt")
        environment = {**os.environ, "PATH": f"{shim_bin}{os.pathsep}{os.environ['PATH']}", "TMPDIR": str(tmp_path)}

        result = subprocess.run([*shell, "-c", block], capture_output=True, text=True, encoding="utf-8", check=False, env=environment)

        assert result.returncode == 0, result.stderr
        lines = result.stdout.splitlines()
        listed = lines[lines.index("its warnings:") + 1 :]
        assert listed == [scope_warning, license_warning]
        # The tail alone would have shown neither.
        assert scope_warning not in lines[: lines.index("its warnings:")]
        assert license_warning not in lines[: lines.index("its warnings:")]

    @pytest.mark.skipif(shutil.which("node") is None, reason="the guard reads package.json with node")
    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    @pytest.mark.parametrize(
        ("dev_script", "admitted"),
        [
            ("next dev -H ${APP_HOST:-127.0.0.1} -p ${APP_PORT:-4300}", True),
            ('next dev -H "${APP_HOST:-127.0.0.1}" -p ${APP_PORT:-4300}', True),
            ("next dev --hostname=127.0.0.1 -p 4300", True),
            ("next dev --hostname localhost", True),
            ("next dev -p ${APP_PORT:-4300}", False),
            ("next dev -H 0.0.0.0 -p ${APP_PORT:-4300}", False),
            ("next dev -H ${APP_HOST:-0.0.0.0} -p ${APP_PORT:-4300}", False),
            ("next dev -H 127.0.0.1.example.com", False),
            (None, False),
        ],
        ids=["template", "template-quoted", "literal-equals", "localhost", "no-host", "every-interface", "wide-default", "lookalike", "no-script"],
    )
    def test_the_loopback_guard_admits_only_a_dev_script_bound_to_loopback(
        self, tmp_path: Path, shell: list[str], dev_script: str | None, admitted: bool
    ) -> None:
        target = tmp_path / "receipt review"
        target.mkdir()
        manifest: dict[str, object] = {"name": "receipt-review"}
        if dev_script is not None:
            manifest["scripts"] = {"dev": dev_script, "build": "next build"}
        (target / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
        guard = _recipe(_render_skill("prod"), LOOPBACK_GUARD_MARKER).replace("<dir>", "'receipt review'")
        result = subprocess.run([*shell, "-c", guard], capture_output=True, text=True, check=False, cwd=str(tmp_path))
        assert (result.returncode == 0) is admitted, result.stderr
        if not admitted:
            assert "would listen on every interface" in result.stderr

    def _dev_block(
        self, *, target: Path, port: int, shim_bin: Path, tmp_path: Path, shell: list[str], bound: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        block = _recipe(_render_skill("prod"), DEV_SERVER_MARKER).replace("<dir>", str(target)).replace("<port>", str(port))
        if bound is not None:
            assert block.count("-ge 300") == 1
            block = block.replace("-ge 300", f"-ge {bound}")
        environment = {**os.environ, "PATH": f"{shim_bin}{os.pathsep}{os.environ['PATH']}", "TMPDIR": str(tmp_path)}
        return subprocess.run([*shell, "-c", block], capture_output=True, text=True, check=False, env=environment, timeout=120)

    @staticmethod
    def _serving_shim(shim_bin: Path, pid_file: Path, *, bind: str) -> Path:
        """A `make` that serves its `-C` directory, bound where `bind` says (a shell word)."""
        return TestMethodAppRecipes._make_shim(
            shim_bin,
            '[ "$3" = dev ] || exit 0\n'
            'case "$5" in APP_HOST=?*) ;; *) echo "no host given" >&2; exit 2 ;; esac\n'
            'cd "$2" || exit 1\n'
            f'echo $$ > "{pid_file}"\n'
            f'exec "{sys.executable}" -m http.server "${{4#APP_PORT=}}" --bind {bind}\n',
        )

    @staticmethod
    def _page(target: Path) -> None:
        target.mkdir()
        (target / "index.html").write_text("<html><head><title>Receipt Review</title></head><body></body></html>\n", encoding="utf-8")

    @staticmethod
    def _stop(pid_file: Path) -> None:
        if pid_file.exists():
            with contextlib.suppress(ProcessLookupError, ValueError):
                os.kill(int(pid_file.read_text(encoding="utf-8").strip()), signal.SIGTERM)

    @NEEDS_SERVER_TOOLS
    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    def test_the_dev_server_block_outlives_its_command_and_proves_the_page(self, tmp_path: Path, shell: list[str]) -> None:
        """`nohup make dev &`, then the listener check, then one request: the server answers after the command has returned.

        `make` is a stand-in that serves the project directory where `APP_HOST` says, so the block's
        own checks read a real listener and its `curl` a real page, and the report's stop command is
        run against the server the block started.
        """
        port = _free_port()
        pid_file = tmp_path / "server.pid"
        shim_bin = self._serving_shim(tmp_path / "shim-bin", pid_file, bind='"${5#APP_HOST=}"')
        target = tmp_path / "receipt-review"
        self._page(target)
        try:
            result = self._dev_block(target=target, port=port, shim_bin=shim_bin, tmp_path=tmp_path, shell=shell)
            assert result.returncode == 0, result.stderr
            assert result.stdout.splitlines()[0] == "200"
            assert "<title>Receipt Review</title>" in result.stdout
            assert "listening on this machine alone" in result.stdout
            # The command has returned, and the server it started still answers.
            assert _answers(port)

            stop = STOP_COMMAND.replace("<port>", str(port))
            assert subprocess.run([*shell, "-c", stop], capture_output=True, text=True, check=False).returncode == 0
            deadline = time.monotonic() + 10
            while _answers(port) and time.monotonic() < deadline:
                time.sleep(0.1)
            assert not _answers(port), "the report's stop command left the server running"
            # With nothing left on the port, the stop command is a quiet no-op rather than a bare `kill`.
            again = subprocess.run([*shell, "-c", stop], capture_output=True, text=True, check=False)
            assert again.returncode == 0 and again.stderr == "", again.stderr
        finally:
            self._stop(pid_file)

    @NEEDS_SERVER_TOOLS
    @pytest.mark.skipif(not _can_bind("127.0.0.2"), reason="this machine's loopback interface carries 127.0.0.1 alone")
    def test_the_dev_server_block_stops_its_own_server_listening_beyond_127_0_0_1(self, tmp_path: Path) -> None:
        """A copy whose `make dev` ignores the host: the block stops the server before any request.

        127.0.0.2 stands in for every other address: the check admits 127.0.0.1 and ::1 alone, and
        binding here opens nothing to the network while the test runs.
        """
        port = _free_port()
        pid_file = tmp_path / "server.pid"
        shim_bin = self._serving_shim(tmp_path / "shim-bin", pid_file, bind="127.0.0.2")
        target = tmp_path / "receipt-review"
        self._page(target)
        try:
            result = self._dev_block(target=target, port=port, shim_bin=shim_bin, tmp_path=tmp_path, shell=["bash"])
            assert result.returncode != 0
            assert "listened beyond this machine and was stopped" in result.stderr
            assert "200" not in result.stdout.splitlines()
            deadline = time.monotonic() + 10
            while _answers(port, host="127.0.0.2") and time.monotonic() < deadline:
                time.sleep(0.1)
            assert not _answers(port, host="127.0.0.2")
        finally:
            self._stop(pid_file)

    @NEEDS_SERVER_TOOLS
    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    def test_the_dev_server_block_stops_its_own_server_in_the_same_command(self, tmp_path: Path, shell: list[str]) -> None:
        """The stop path in every shell, on any machine: the admitted addresses narrowed to ::1 alone.

        The server binds 127.0.0.1, which the narrowed check reads as beyond this machine, so the
        block must stop it before its request, without opening anything to the network.
        """
        port = _free_port()
        pid_file = tmp_path / "server.pid"
        shim_bin = self._serving_shim(tmp_path / "shim-bin", pid_file, bind='"${5#APP_HOST=}"')
        target = tmp_path / "receipt-review"
        self._page(target)
        admitted = r"'^(127\.0\.0\.1|\[::1\]):<port>$'".replace("<port>", str(port))
        narrowed = r"'^(\[::1\]):<port>$'".replace("<port>", str(port))
        block = _recipe(_render_skill("prod"), DEV_SERVER_MARKER).replace("<dir>", str(target)).replace("<port>", str(port))
        assert block.count(admitted) == 1
        block = block.replace(admitted, narrowed)
        environment = {**os.environ, "PATH": f"{shim_bin}{os.pathsep}{os.environ['PATH']}", "TMPDIR": str(tmp_path)}
        try:
            result = subprocess.run([*shell, "-c", block], capture_output=True, text=True, check=False, env=environment, timeout=120)
            assert result.returncode != 0
            assert "listened beyond this machine and was stopped" in result.stderr
            assert "200" not in result.stdout.splitlines()
            deadline = time.monotonic() + 10
            while _answers(port) and time.monotonic() < deadline:
                time.sleep(0.1)
            assert not _answers(port), "the block left the server running"
        finally:
            self._stop(pid_file)

    @NEEDS_SERVER_TOOLS
    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    def test_the_dev_server_block_leaves_a_holder_that_is_not_the_project_alone(self, tmp_path: Path, shell: list[str]) -> None:
        """Another process took the port after `port-check`: `make dev` refused, and the holder is not touched."""
        port = _free_port()
        elsewhere = tmp_path / "someone-else"
        elsewhere.mkdir()
        holder = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
            cwd=str(elsewhere),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 10
            while not _answers(port) and time.monotonic() < deadline:
                time.sleep(0.1)
            assert _answers(port)
            shim_bin = self._make_shim(tmp_path / "shim-bin", 'echo "Port is held by another checkout" >&2\nexit 1\n')
            target = tmp_path / "receipt-review"
            self._page(target)
            result = self._dev_block(target=target, port=port, shim_bin=shim_bin, tmp_path=tmp_path, shell=shell)
            assert result.returncode != 0
            assert f"held by pid {holder.pid}, which is not this project" in result.stderr
            assert _answers(port), "the block stopped a server that was not the project's"
        finally:
            holder.terminate()
            holder.wait(timeout=10)

    @NEEDS_SERVER_TOOLS
    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    def test_the_dev_server_block_reports_a_server_that_never_started(self, tmp_path: Path, shell: list[str]) -> None:
        port = _free_port()
        shim_bin = self._make_shim(tmp_path / "shim-bin", 'echo "next dev crashed" >&2\nexit 1\n')
        target = tmp_path / "receipt-review"
        self._page(target)
        result = self._dev_block(target=target, port=port, shim_bin=shim_bin, tmp_path=tmp_path, shell=shell, bound="5")
        assert result.returncode != 0
        assert f"nothing listens on port {port}: the server exited" in result.stderr
        assert "stopped" not in result.stderr
        assert "usage" not in result.stderr.lower()

    @NEEDS_SERVER_TOOLS
    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    def test_the_dev_server_block_stops_a_server_still_starting_when_the_wait_ends(self, tmp_path: Path, shell: list[str]) -> None:
        """A `make dev` that has not opened its port by the end of the wait is stopped, with every process under it.

        The stand-in hands the start to a child that sleeps before it serves, as `make` hands it to npm
        and npm to Next: stopping the launcher alone would leave that child to open the port later,
        unchecked, while the retry starts a second server.
        """
        port = _free_port()
        pid_file = tmp_path / "server.pid"
        child_file = tmp_path / "child.pid"
        shim_bin = self._make_shim(
            tmp_path / "shim-bin",
            '[ "$3" = dev ] || exit 0\n'
            'cd "$2" || exit 1\n'
            f'echo $$ > "{pid_file}"\n'
            f'(sleep 30; exec "{sys.executable}" -m http.server "${{4#APP_PORT=}}" --bind 127.0.0.1) &\n'
            f'echo $! > "{child_file}"\n'
            "wait\n",
        )
        target = tmp_path / "receipt-review"
        self._page(target)
        try:
            result = self._dev_block(target=target, port=port, shim_bin=shim_bin, tmp_path=tmp_path, shell=shell, bound="5")
            assert result.returncode != 0
            assert f"nothing listens on port {port} yet, so the server this command started was stopped" in result.stderr
            launched = [int(path.read_text(encoding="utf-8").strip()) for path in (pid_file, child_file)]
            deadline = time.monotonic() + 10
            while any(_alive(pid) for pid in launched) and time.monotonic() < deadline:
                time.sleep(0.1)
            assert not any(_alive(pid) for pid in launched), "the block left a process it launched running"
            assert not _answers(port)
        finally:
            self._stop(child_file)
            self._stop(pid_file)

    @NEEDS_SERVER_TOOLS
    @pytest.mark.parametrize("shell", _shells(), ids=lambda shell: Path(shell[0]).name)
    def test_the_dev_server_block_knows_its_server_through_a_path_typed_in_another_case(self, tmp_path: Path, shell: list[str]) -> None:
        """On a case-insensitive disk, a project named in another letter case is still the project.

        The `pwd -P` built into bash and sh keeps the case the path was typed in, and `lsof` reports the
        case on disk, so a block comparing the two would take its own server for a stranger.
        """
        self._page(tmp_path / "Receipt-Review")
        typed = tmp_path / "receipt-review"
        if not typed.exists():
            pytest.skip("this disk tells letter case apart")
        port = _free_port()
        pid_file = tmp_path / "server.pid"
        shim_bin = self._serving_shim(tmp_path / "shim-bin", pid_file, bind='"${5#APP_HOST=}"')
        try:
            result = self._dev_block(target=typed, port=port, shim_bin=shim_bin, tmp_path=tmp_path, shell=shell)
            assert result.returncode == 0, result.stderr
            assert result.stdout.splitlines()[0] == "200"
        finally:
            self._stop(pid_file)
