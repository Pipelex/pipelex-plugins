"""Pin the pipelex-scaffold skill: two branches, no templates of its own, one commit, delegated bootstrap."""

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
STARTERS_REFERENCE = REPO_ROOT / "skills" / "pipelex-scaffold" / "references" / "starters.md"
INITIALIZERS_REFERENCE = REPO_ROOT / "skills" / "pipelex-scaffold" / "references" / "initializers.md"

BASH_BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)
# The one string both acquisition recipes point at a real remote, swapped for a
# local repository so the recipes run as shipped without touching the network.
STARTER_URL = "https://github.com/Pipelex/<starter>.git"

# The method app's blocks, each named by a string that occurs in exactly one of them. The family's
# URL is swapped for a local repository, as the starter's is, so the copy runs without the network.
METHOD_APPS_URL = "https://github.com/Pipelex/pipelex-method-apps.git"
METHOD_APP_MARKER = "pipelex-method-apps.git"
CREATE_MARKER = "create METHOD='<method>'"
DEV_SERVER_MARKER = 'nohup make -C "$dir" dev APP_PORT=<port> APP_HOST=127.0.0.1'
LOOPBACK_GUARD_MARKER = "node -e 'const dev = "
OWN_REPOSITORY_MARKER = "rev-parse --show-prefix"
PORT_CHECK_COMMAND = "make -C <dir> port-check APP_PORT=4300"
STOP_COMMAND = 'for pid in $(lsof -ti tcp:<port> -sTCP:LISTEN); do kill "$pid"; done'
RESTART_COMMAND = "make dev APP_PORT=<port> APP_HOST=127.0.0.1"
PRISTINE_METHOD_APP_COMMIT = (
    'git -C <dir> add -A -- . && git -C <dir> commit -m "Start from Pipelex/pipelex-method-apps/webapp-js <version> (<sha>)" -- .'
)
TARGETS = ("prod", "codex", "mistral-vibe")

NEEDS_GIT = pytest.mark.skipif(shutil.which("git") is None, reason="the acquisition recipes are git")

# The env-file write, as the skill ships it. The marker names the one bash block that fills the
# file; the fragments are what make it one decision: the guard on the file's key (and on the shell
# setting anything at all) opens the braces, and the comment and both appends sit inside them.
ENV_FILE_MARKER = r"""printf 'PIPELEX_BASE_URL=%s\n' "$PIPELEX_BASE_URL" >> <dir>/.env.local"""
ENV_FILE_GUARD = r"""grep -q '^PIPELEX_API_KEY=.\+' <dir>/.env.local || [ -z "${PIPELEX_API_KEY:-}${PIPELEX_BASE_URL:-}" ] || {"""
ENV_FILE_COMMENT_LINE = "# Copied from the shell environment; a later line overrides an earlier one."
ENV_FILE_COMMENT = r"""printf '\n""" + ENV_FILE_COMMENT_LINE + r"""\n' >> <dir>/.env.local &&"""
ENV_FILE_KEY_APPEND = r"""{ [ -z "${PIPELEX_API_KEY:-}" ] || printf 'PIPELEX_API_KEY=%s\n' "$PIPELEX_API_KEY" >> <dir>/.env.local; }"""
ENV_FILE_URL_APPEND = r"""{ [ -z "${PIPELEX_BASE_URL:-}" ] || printf 'PIPELEX_BASE_URL=%s\n' "$PIPELEX_BASE_URL" >> <dir>/.env.local; }"""
# The file-side confirmations and the plane test, which print a verdict and never a value.
ENV_FILE_KEY_CONFIRMATION = r"""grep -q '^PIPELEX_API_KEY=.\+' <dir>/.env.local && echo filled || echo empty"""
ENV_FILE_URL_CONFIRMATION = r"""grep -qxF "PIPELEX_BASE_URL=$PIPELEX_BASE_URL" <dir>/.env.local && echo copied || echo missing"""
PLANE_TEST = r"""[ "${PIPELEX_BASE_URL%/}" = https://api.pipelex.com ] && echo production || echo other"""

PRODUCTION_URL = "https://api.pipelex.com"
# Fake credentials only. The machine's own PIPELEX_* values are removed from every environment
# these tests build, so no real key can reach a temporary file or an assertion message.
FAKE_KEY = "plx_fake_key_for_tests_0000"
FAKE_URL = "https://api.fake-plane.example"
# The JS starter's example shape (comments, blank lines, a third variable, a trailing newline) and
# branch B's two-line example written without one, which is the shape an append can glue onto.
STARTER_EXAMPLE = (
    "# Pipelex API endpoint and credentials.\n"
    "PIPELEX_BASE_URL=https://api.pipelex.com\n"
    "PIPELEX_API_KEY=\n"
    "\n"
    "# Default execution mode for the examples.\n"
    "NEXT_PUBLIC_EXECUTION_MODE=durable\n"
)
INITIALIZER_EXAMPLE = "PIPELEX_BASE_URL=https://api.pipelex.com\nPIPELEX_API_KEY="


def _bash_blocks(text: str) -> list[str]:
    return [match.group(1) for match in BASH_BLOCK.finditer(text)]


def _dotenv_reading(text: str) -> dict[str, str]:
    """An env file resolved the way dotenv readers resolve it.

    Blank lines and comments are skipped, an optional `export ` prefix is dropped, and a name
    assigned twice resolves to its later assignment — which is what python-dotenv, Node's `dotenv`
    and `util.parseEnv`, and a Makefile `include` all do, and the property the skill's append relies on.
    """
    resolved: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.removeprefix("export ").split("=", 1)
        resolved[name.strip()] = value.strip()
    return resolved


def _shell_environment(credentials: dict[str, str]) -> dict[str, str]:
    """The test process's environment with this machine's credentials removed and fakes put in.

    `BASH_ENV` and `ENV` are dropped too, so no startup file a shell would source can put a real
    value back.
    """
    environment = {name: value for name, value in os.environ.items() if name not in {"PIPELEX_API_KEY", "PIPELEX_BASE_URL", "BASH_ENV", "ENV"}}
    environment.update(credentials)
    return environment


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


class TestPipelexScaffoldSkill:
    """The skill is executable guidance, so these tests guard what a user's new
    project depends on: nothing is written into a non-empty directory, the skill
    makes exactly one commit, the starters' bootstrap is delegated and never
    reimplemented, the key never crosses the conversation, and no MCP tool is needed.
    """

    REPO_ROOT = Path(__file__).parents[2]
    SKILLS = REPO_ROOT / "templates" / "skills"
    TEMPLATE = SKILLS / "pipelex-scaffold" / "SKILL.md.j2"
    REFERENCES_DIR = REPO_ROOT / "skills" / "pipelex-scaffold" / "references"
    REFERENCES = ("starters.md", "initializers.md")
    RULES = (
        "exactly two branches and carries no templates of its own",
        "no cookiecutter, no copier, no framework matrix of its own",
        "never write into a directory that exists and is not empty",
        "never offer to move, delete or merge what it holds to make room",
        "This is the **one commit this skill makes**",
        "Read `<dir>/.claude/skills/bootstrap/SKILL.md` and follow it as written",
        "**Add nothing to that procedure and reimplement none of it.**",
        "**Never print a key, and never ask for one in the conversation.**",
        "a key in the transcript is a key to rotate",
        "**state the exact command and confirm before running it**",
        "do not start `make dev`",
        "Add **no** SDK dependency and create **no** empty `methods/` directory",
        "Nothing beyond what the initializer writes is authored by this skill",
        "a runtime the machine already has and only the `PATH` is missing is not a missing piece",
        # A sourced shell does not survive the next command, so the runtime is resolved to a path.
        "**Activating it means resolving it to an absolute path, not sourcing a shell.**",
        "**A shim is not a runtime**",
        # A file-editing tool needs the literal value in its parameters, which is the transcript.
        "**The value moves only through a shell that expands the variable itself, and never through you.**",
        "**no reading the env file back**",
        "and not validated",
        # The destructive line runs only behind a clone that succeeded.
        "git clone --depth 1 https://github.com/Pipelex/<starter>.git <dir> || exit",
        # cp -n: an env file the user already filled is the most expensive thing in the tree to lose.
        "cp -n <dir>/.env.example <dir>/.env.local",
        # npm eats the flags without the separator and create-next-app then prompts.
        "npm create next-app@latest <dir> -- --ts --app --src-dir --eslint --use-npm --yes",
        # uv add resolves the project from its working directory, which from the parent is the user's.
        "**from inside `<dir>`**",
        # An initializer that commits has already made the pristine commit.
        "**An initializer that commits as well as `git init`s has already made this commit.**",
        # The default TS branch is prescribed in the skill; both its costs live in the reference.
        "**Read [references/initializers.md](references/initializers.md) before running either**",
        # npm init -y and tsc --init write no .gitignore, so the staging would commit node_modules.
        "**Then confirm there is a `.gitignore` covering the dependency tree and the build output**",
        # <dir> with no .git of its own is governed by the repo enclosing it — the user's.
        "**Test whether `<dir>` is its own repository; never infer it from which initializer ran.**",
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

    def test_the_skill_body_carries_the_guards_the_references_state(self) -> None:
        """Two guards were stated in `references/initializers.md` and pinned only there.

        The skill body is the document an agent actually executes; a reference it is told to read
        is a second hop. Round 2 added `--no-workspace` to every `uv init` in the reference and
        asserted it there, while the named-framework recipe *in the skill* kept the bare form — so
        the reference said "on every `uv init` above" and the executable line one hop away
        contradicted it. These assertions run on the template and on all three renders, because a
        rule that holds only in `templates/` is a rule no user reads.
        """
        for body in [self.scaffold] + [self.render(target) for target in ("prod", "codex", "mistral-vibe")]:
            # A bare `uv init --package <dir>` appends a [tool.uv.workspace] table to the USER'S
            # own pyproject.toml and leaves the new project without its own lock.
            assert "uv init --package --no-workspace <dir>" in body
            assert "uv init --package <dir>" not in body, "a bare uv init absorbs <dir> into the parent workspace"
            # The append is gated: on the fresh-clone shortcut the env file may be one the user
            # filled, and a second assignment after theirs is the one dotenv resolves to.
            assert "grep -q '^PIPELEX_API_KEY=.\\+' <dir>/.env.local || [ -z" in body
            assert ">> <dir>/.env.local`.\n" not in body, "an ungated append shadows a key the user already filled"

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

        The earlier ruling made a directory whose only entry is `.git` read as empty, which branch
        B can honour because `uv init` accepts such a directory. Branch A could not: its first
        command on the chosen directory is `git clone`, and git refuses a destination already
        holding a `.git`. So the skill admitted a directory it then could not populate, and the
        founder's own motivating case — `mkdir my-app && cd my-app && git init` — dead-ended for
        anyone who wanted the starter rather than the initializer. Scoping the allowance to branch
        B was rejected: it would answer that user with the refusal the exception was written to
        remove, and the ruling would mean two different things depending on which branch they
        landed in.

        Branch A now acquires beside the directory and moves in. These are the claims the recipe
        one file over is executed against in `TestScaffoldAcquisitionRecipes`; asserted on the
        template, on all three renders and on the reference, because round 1 found a guard that
        had been pinned against the reference alone and was missing from the document an agent
        actually executes.
        """
        for body in [self.scaffold] + [self.render(target) for target in ("prod", "codex", "mistral-vibe")]:
            assert "**Local, into a directory that already holds a repository.**" in body
            # Both halves of the ruling: the same end state, and the user's repository left alone.
            assert "The end state is the one the default recipe reaches" in body
            assert "the repository the user made goes on standing instead of being replaced" in body
            # Ordering: the destructive line is spent on the temporary path before anything moves.
            assert "**No `rm -rf` here ever addresses a path under `<dir>`, and that is the ordering rather than a coincidence.**" in body
            assert 'the only two paths any delete is pointed at are `"$tmp/.git"` and `"$tmp"`' in body
            # Dotfiles: the naive glob drops them and still exits 0.
            assert '**`cp -R "$tmp"/. "$dir"/`, and never `mv "$tmp"/* "$dir"/`.**' in body
            assert "The glob matches no entry beginning with a dot" in body
            # The destination is resolved before its parent is computed, so `.` cannot make the
            # temporary path a child of the target. Round 2 found the unresolved form refusing
            # every "scaffold here", which is the ruling's own motivating case.
            assert "**The first line resolves the destination, and that is what keeps the temporary path a sibling rather than a child.**" in body
            assert "would put the temporary directory **inside** the destination" in body
            # Collision: one admitted entry, so the template can only add.
            assert '**The `ls -A` line is the "Where" rule read again, against the copy.**' in body
            assert "a collision is therefore impossible rather than merely unlikely" in body
            assert "Nothing of the user's is overwritten, moved or deleted to make room" in body
            # The guards and the cleanup hold only inside one shell.
            assert "**The chain goes out as one command.**" in body
            # The user's repository is not re-initialised; the pristine commit lands on their branch.
            assert "**Nothing is initialized here.**" in body
            assert "the commit lands on the user's branch, on top of their history" in body
            # And the failure table sends branch A down this route rather than at a clone.
            assert "On branch A that directory is served by the acquisition beside it (Step 2) and never by a `git clone` into it" in body

        # The reference is the file the skill names as carrying every command, so the recipe and
        # the three properties that make it safe are stated there as well as in the skill body.
        reference = STARTERS_REFERENCE.read_text(encoding="utf-8")
        assert "dir=$(cd <dir> && pwd) || exit 1" in reference
        assert 'tmp=$(mktemp -d "$(dirname "$dir")/.pipelex-starter-XXXXXX") || exit 1' in reference
        assert "**No `rm -rf` in it addresses a path under `<dir>`**" in reference
        assert '**`cp -R "$tmp"/. "$dir"/` carries the entries beginning with a dot**' in reference
        assert "**the `ls -A` line admits exactly one entry**" in reference
        assert "**The first line resolves `<dir>` to an absolute path before the parent is computed from it**" in reference

    def test_every_acquisition_block_names_one_starter(self) -> None:
        """Round 2: the reference's blocks each carried both starters' URLs on consecutive lines.

        Read as the chain the prose calls them — "It is one chain and goes out as one command" —
        the second clone lands on a destination the first has just filled, fails, and its handler
        deletes the successful clone before anything is copied. The skill body had always used a
        single `<starter>` placeholder, so this was the body-and-reference divergence round 1 was
        told to watch for, reappearing on the other side.
        """
        reference = STARTERS_REFERENCE.read_text(encoding="utf-8")
        assert "pipelex-starter-js.git" not in reference
        assert "pipelex-starter-python.git" not in reference
        assert "--template Pipelex/pipelex-starter-js" not in reference
        assert "--template Pipelex/pipelex-starter-python" not in reference
        # The placeholder is bound where the blocks begin, so `<starter>` is not left dangling.
        assert "`<starter>` below is the one the choice above settled" in reference
        assert "never a menu to run top to bottom" in reference

    def test_the_lone_git_rule_does_not_promise_a_git_init_that_must_not_run(self) -> None:
        """Round 2: the "Where" row justified the exception with behaviour that cannot occur there.

        It read "branch B runs `git init -b main` in the directory it is working in one step later"
        — but in the lone-`.git` case the user has already run `git init`, so Step 3's own test finds
        `<dir>` is its own repository and branch B must not re-run it. The rationale invited an agent
        to expect the one command the step exists to gate.
        """
        for body in [self.scaffold] + [self.render(target) for target in ("prod", "codex", "mistral-vibe")]:
            assert "it does **not** re-run `git init` there" in body
            assert "since Step 3's test finds `<dir>` is already its own repository" in body
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

    def test_the_base_url_comes_from_the_shell_in_every_copy_a_user_installs(self) -> None:
        """`L-260913-15af9f`: the key was copied from the shell and the base URL left at production.

        A key is refused by every plane but the one that issued it, so a shell exporting a dev or
        staging pair got an env file pairing that plane's key with production's URL — invisible to
        the session, which reads the process environment, and broken the first time anything read
        the file. A first fix moved the URL only beside a key; the developer then ruled on
        2026-09-13 that an exported base URL is the user's declared plane and is copied with a key
        or without one, because the keyless self-hosted runner the Python starter's example
        documents is exactly the project the narrower rule pointed at production. One guard on the
        file's key decides whether anything is written: the example ships its URL line non-empty,
        so the URL can carry no presence guard of its own. Asserted on the template, on the three
        in-memory renders and on the three committed trees, because the executed tests below run
        the command out of one of them.
        """
        template = self.scaffold
        recipe = _recipe(template, ENV_FILE_MARKER)
        # Inside the braces the guard opens, in this order, so decided by the same test and never on
        # their own: the comment once, then whichever of the two lines the shell supplies.
        fragments = (ENV_FILE_GUARD, ENV_FILE_COMMENT, ENV_FILE_KEY_APPEND, ENV_FILE_URL_APPEND)
        positions = [recipe.index(fragment) for fragment in fragments]
        assert positions == sorted(positions), "the guard, the comment and the two appends are out of order"
        assert recipe.count(ENV_FILE_COMMENT_LINE) == 1
        assert recipe.rstrip().endswith("}")

        bodies = [template]
        for target_name in ("prod", "codex", "mistral-vibe"):
            config = load_target_config(self.REPO_ROOT / "targets", target_name)
            installed = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-scaffold" / "SKILL.md"
            bodies.extend([self.render(target_name), installed.read_text(encoding="utf-8")])
        for body in bodies:
            assert _recipe(body, ENV_FILE_MARKER) == recipe, "a copy ships a different env-file command than the one executed here"
            assert "**`PIPELEX_BASE_URL` comes from the shell too, with a key or without one.**" in body
            assert "because a base URL the shell exports is the plane the user has declared" in body
            assert "is not copied" not in body, "the rule that pointed a keyless self-hosted project at production is back"
            assert "**The one test on the file's key decides whether anything is written" in body
            assert "the leading newline and the comment are written once, whichever of the two lines follows them" in body
            assert "**The report names the plane the file points at, without printing the URL**" in body
            # A URL copied without a key and not production's: the key app.pipelex.com issues is refused there.
            assert (
                "say the file points at another plane, and warn that a key from `app.pipelex.com` is production's and will be refused there" in body
            )
            assert "| `PIPELEX_BASE_URL` is set in the shell | copy it, with the key or without one," in body
            assert ENV_FILE_KEY_CONFIRMATION in body
            assert ENV_FILE_URL_CONFIRMATION in body
            assert PLANE_TEST in body
            assert "stays as the example ships it" not in body, "the sentence that split the credential is back"

        starters = STARTERS_REFERENCE.read_text(encoding="utf-8")
        initializers = INITIALIZERS_REFERENCE.read_text(encoding="utf-8")
        assert "**The env file's two Pipelex lines name one plane.**" in starters
        assert "copies a base URL the shell sets whether or not the shell also sets a key" in starters
        assert "`PIPELEX_BASE_URL` filled from it whenever the shell sets one, with a key or without" in initializers
        assert "the base URL whenever the shell sets one, with or without a key" in initializers
        for reference in (starters, initializers):
            assert "stays as the example ships it" not in reference
            assert "is not copied" not in reference

    def _run_env_file_command(
        self, *, shell: list[str], command: str, project: Path, credentials: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        """One shipped command, `<dir>` bound to `project`, run with fake credentials only."""
        script = command.replace("<dir>", str(project))
        assert "<dir>" not in script, "a placeholder survived the binding"
        return subprocess.run(
            [*shell, "-c", script],
            capture_output=True,
            text=True,
            check=False,
            env=_shell_environment(credentials),
            cwd=str(project),
        )

    @staticmethod
    def _node_reading(env_file: Path) -> dict[str, str] | None:
        """The file as Node's own dotenv parser resolves it, or None where this machine has none."""
        node = shutil.which("node")
        if node is None:
            return None
        script = (
            "const util = require('node:util');"
            "if (typeof util.parseEnv !== 'function') process.exit(3);"
            "process.stdout.write(JSON.stringify(util.parseEnv(require('node:fs').readFileSync(process.argv[1], 'utf8'))));"
        )
        result = subprocess.run([node, "-e", script, str(env_file)], capture_output=True, text=True, check=False)
        if result.returncode == 3:
            return None
        assert result.returncode == 0, result.stderr
        reading: dict[str, str] = json.loads(result.stdout)
        return reading

    @pytest.mark.parametrize("example", [STARTER_EXAMPLE, INITIALIZER_EXAMPLE], ids=["starter-example", "initializer-example-without-final-newline"])
    @pytest.mark.parametrize(
        ("credentials", "expected_key", "expected_url", "expected_plane"),
        [
            pytest.param({"PIPELEX_API_KEY": FAKE_KEY, "PIPELEX_BASE_URL": FAKE_URL}, FAKE_KEY, FAKE_URL, "other", id="both-set"),
            pytest.param(
                {"PIPELEX_API_KEY": FAKE_KEY, "PIPELEX_BASE_URL": f"{PRODUCTION_URL}/"},
                FAKE_KEY,
                f"{PRODUCTION_URL}/",
                "production",
                id="both-set-production-spelled-with-a-trailing-slash",
            ),
            pytest.param({"PIPELEX_API_KEY": FAKE_KEY}, FAKE_KEY, PRODUCTION_URL, None, id="key-only"),
            pytest.param({"PIPELEX_API_KEY": FAKE_KEY, "PIPELEX_BASE_URL": ""}, FAKE_KEY, PRODUCTION_URL, None, id="key-beside-an-empty-base-url"),
            pytest.param({}, "", PRODUCTION_URL, None, id="neither"),
            pytest.param({"PIPELEX_BASE_URL": FAKE_URL}, "", FAKE_URL, "other", id="base-url-without-a-key"),
        ],
    )
    def test_the_env_file_command_writes_the_pair_the_shell_holds(
        self,
        example: str,
        credentials: dict[str, str],
        expected_key: str,
        expected_url: str,
        expected_plane: str | None,
        tmp_path: Path,
    ) -> None:
        """Run the command the skill ships, and read the file the way the project will.

        The claim is about what a dotenv reader resolves, not about which lines were written, so
        every case is read back through a last-assignment-wins reading — and through Node's own
        `util.parseEnv` where this machine has it. A base URL the shell sets is copied with a key or
        without one, and a shell that sets neither leaves the example byte for byte as it came. The
        command runs in every POSIX shell on the machine, because the harness that runs it for a
        user may be any of them, and the confirmations and the plane test the skill prescribes are
        run too: they are commands an agent types, so they are held to the same standard.
        """
        command = _recipe(self.render("prod"), ENV_FILE_MARKER)
        shells = _shells()
        assert shells, "these tests already require a POSIX shell"
        for shell in shells:
            project = tmp_path / Path(shell[0]).name
            project.mkdir()
            env_file = project / ".env.local"
            env_file.write_text(example, encoding="utf-8")

            result = self._run_env_file_command(shell=shell, command=command, project=project, credentials=credentials)
            assert result.returncode == 0, f"{shell[0]}: {result.stderr}"
            assert result.stdout == "", f"{shell[0]}: the write printed something"

            written = env_file.read_text(encoding="utf-8")
            # The example's own lines are kept as they were, and nothing appended is glued onto the
            # last of them — which a file without a final newline invites, and the leading newline
            # in the command is there to prevent.
            assert written.splitlines()[: len(example.splitlines())] == example.splitlines(), f"{shell[0]}: the example's lines were altered"
            reading = _dotenv_reading(written)
            assert reading["PIPELEX_API_KEY"] == expected_key, f"{shell[0]}: the key resolved to the wrong value"
            assert reading["PIPELEX_BASE_URL"] == expected_url, f"{shell[0]}: the base URL resolved to the wrong plane"
            # Nothing else the example carries changed meaning.
            untouched = {name: value for name, value in _dotenv_reading(example).items() if not name.startswith("PIPELEX_")}
            assert {name: value for name, value in reading.items() if not name.startswith("PIPELEX_")} == untouched
            # Whatever was appended is the comment once, then the lines the shell supplied, and
            # nothing at all when it supplied neither.
            appended = [line for line in written.splitlines()[len(example.splitlines()) :] if line]
            supplied = [f"{name}={credentials[name]}" for name in ("PIPELEX_API_KEY", "PIPELEX_BASE_URL") if credentials.get(name)]
            if supplied:
                assert appended == [ENV_FILE_COMMENT_LINE, *supplied], (
                    f"{shell[0]}: the appended lines are not the comment once and the supplied lines"
                )
            else:
                assert written == example, f"{shell[0]}: a shell that sets neither variable still changed the file"
            node_reading = self._node_reading(env_file)
            if node_reading is not None:
                assert node_reading["PIPELEX_API_KEY"] == expected_key, f"{shell[0]}: Node reads a different key"
                assert node_reading["PIPELEX_BASE_URL"] == expected_url, f"{shell[0]}: Node reads a different base URL"

            key_confirmation = self._run_env_file_command(shell=shell, command=ENV_FILE_KEY_CONFIRMATION, project=project, credentials=credentials)
            assert key_confirmation.stdout == ("filled\n" if expected_key else "empty\n")
            if expected_plane is not None:
                url_confirmation = self._run_env_file_command(
                    shell=shell, command=ENV_FILE_URL_CONFIRMATION, project=project, credentials=credentials
                )
                assert url_confirmation.stdout == "copied\n"
                plane = self._run_env_file_command(shell=shell, command=PLANE_TEST, project=project, credentials=credentials)
                assert plane.stdout == f"{expected_plane}\n"

    @pytest.mark.parametrize(
        "carried",
        [
            "PIPELEX_BASE_URL=https://api.pipelex.com\nPIPELEX_API_KEY=plx_the_users_own_fake_key\n",
            "PIPELEX_BASE_URL=http://127.0.0.1:8081\nPIPELEX_API_KEY=plx_the_users_own_fake_key",
        ],
        ids=["their-key-beside-the-example-url", "their-key-beside-their-own-url-without-final-newline"],
    )
    def test_the_env_file_command_leaves_a_file_that_already_carries_a_key_byte_for_byte(self, carried: str, tmp_path: Path) -> None:
        """The fresh-clone shortcut: the env file may be one the user filled, base URL and all.

        With a different pair exported in the shell, neither line may move — a later assignment of
        either one would silently replace a working credential while the report said theirs was
        kept. Compared as bytes, because "resolves the same" would pass a file that had grown lines.
        """
        command = _recipe(self.render("prod"), ENV_FILE_MARKER)
        for shell in _shells():
            project = tmp_path / Path(shell[0]).name
            project.mkdir()
            env_file = project / ".env.local"
            env_file.write_bytes(carried.encode("utf-8"))
            result = self._run_env_file_command(
                shell=shell,
                command=command,
                project=project,
                credentials={"PIPELEX_API_KEY": FAKE_KEY, "PIPELEX_BASE_URL": FAKE_URL},
            )
            assert result.returncode == 0, f"{shell[0]}: {result.stderr}"
            assert env_file.read_bytes() == carried.encode("utf-8"), f"{shell[0]}: a file carrying the user's key was changed"

    def test_declares_no_mcp_tool(self) -> None:
        """The scaffold skill is MCP-free: no allowed-tools entry, no MCP-absent STOP message."""
        body = self.scaffold
        assert "mcp__" not in body
        assert "plugin manifest spawns" not in body
        assert "It needs no MCP tool and never handles an API key itself" in body

    def test_integrate_hands_a_missing_project_to_scaffold(self) -> None:
        integrate = (self.SKILLS / "pipelex-integrate" / "SKILL.md.j2").read_text(encoding="utf-8")
        assert "**No project at all** → this is not an integration yet: offer" in integrate
        assert "pipelex-scaffold" in integrate

    def test_references_describe_both_starters_and_the_initializers(self) -> None:
        starters = (self.REFERENCES_DIR / "starters.md").read_text(encoding="utf-8")
        assert "pipelex-starter-js" in starters and "pipelex-starter-python" in starters
        # The `|| exit` is the guard on the `rm -rf <dir>/.git` below it: a clone that never ran
        # leaves that line to delete whatever `.git` is at that path — a user's history, if <dir>
        # was theirs. The SKILL.md carries it; so must the reference the skill names as the source
        # of every command, or the guard exists only in the copy nobody executes from.
        assert "git clone --depth 1 https://github.com/Pipelex/<starter>.git <dir> || exit" in starters
        assert "The `|| exit` on the clone is load-bearing" in starters
        # Round 1 put the `-- .` pathspec on the commit as well as on the staging and wrote that it
        # is on "both commands for a reason"; the reference kept the old bare commit, so the rule
        # held only in the copy an agent does not read the commands out of. The mirror of the
        # half-application round 1 was itself convened to fix.
        assert 'git -C <dir> add -A -- . && git -C <dir> commit -m "Start from Pipelex/<starter> <version> (<sha>)" -- .' in starters
        assert "**The `-- .` pathspec is on the commit as well as on the staging**" in starters
        # And the initializers reference must send the reader to the repository test rather than to
        # the inference the skill body forbids by name.
        initializers = (self.REFERENCES_DIR / "initializers.md").read_text(encoding="utf-8")
        assert "**the test, never the inference from which initializer ran**" in initializers
        assert "`git init -b main` only if `git -C <dir> rev-parse --show-toplevel` does not print `<dir>` itself" in initializers
        assert "gh repo create <owner>/<name> --template Pipelex/<starter> --private --clone" in starters
        # The Python starter regenerates through the hosted API with pipelex-sdk: only its offline
        # check still wants a `pipelex` CLI. Describing `make codegen` as needing one sent an agent
        # down the workshop fallback on a project whose own generator would have worked.
        assert "`make codegen` (keyed: `PIPELEX_API_KEY` from `.env` or the shell" in starters
        assert "`make codegen-check` (offline) is the one target still shelling out to a `pipelex` CLI" in starters
        assert "both shell out to a `pipelex` CLI" not in starters
        # The second source kind, and the agent-facing files and docs the parity pass added.
        assert "`<package>/methods/<name>/method.json` naming exactly one of `method_id` / `method_ref`" in starters
        assert "| `CLAUDE.md`, `AGENTS.md`; skills `bootstrap`, `release` |" in starters
        assert "`docs/codegen.md`, `docs/add-method.md`, `docs/cli-architecture.md`" in starters
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

    def test_the_pristine_commit_cannot_reach_an_enclosing_repository(self) -> None:
        """`git -C <dir>` sets git's working directory and scopes nothing. With no `.git` of its own,
        <dir> is governed by whatever repo encloses it — the user's — and a pathspec-less `add -A`
        stages that whole worktree, committing the user's unrelated files under this skill's message.
        `uv init` is on the list of initializers that `git init`, but only when it creates a
        standalone project; inside an existing one it makes <dir> a workspace member and no repo.
        """
        body = self.TEMPLATE.read_text(encoding="utf-8")
        assert "git -C <dir> rev-parse --show-toplevel` must print `<dir>` itself" in body
        assert "never infer it from which initializer ran" in body
        # Both pristine commits carry the pathspec, so the staging cannot escape <dir>.
        assert body.count("git -C <dir> add -A -- .") == 2
        # `add -A -- .` bounds only the staging; a bare `git commit` commits the whole index,
        # so anything the user had staged in an enclosing repo would ride along. Both commits
        # carry the pathspec, which leaves their staged work staged.
        assert 'commit -m "Start from Pipelex/<template> <version> (<sha>)" -- .' in body
        assert 'commit -m "Scaffold <framework or language> project" -- .' in body
        assert "git -C <dir> add -A &&" not in body
        # The read-back must name paths; a --stat count cannot tell a scaffold from a swept worktree.
        assert "git -C <dir> diff --cached --name-only" in body
        assert "git -C <dir> diff --cached --stat | tail -1" not in body

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

        references_dir = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-scaffold" / "references"
        for reference in self.REFERENCES:
            assert (references_dir / reference).is_file(), f"{target_name}: missing references/{reference}"

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


@NEEDS_GIT
class TestScaffoldAcquisitionRecipes:
    """Branch A's two acquisition recipes, extracted from the skill and executed.

    `L-260913-f28d9d` was ruled with a condition attached: the recipe is proven by being
    run, not by being read. Three reasons, each specific. It touches the one area of this
    skill that deletes; this campaign's history is that recipes composed during review
    rounds became the next round's defects; and `references/starters.md` already warns that
    the `|| exit` guard holds only inside one shell, which is the single thing standing
    between a `rm -rf` and a user's repository.

    So these tests read the bash blocks out of the skill template, swap the starter's URL
    for a local repository standing in for it, and run the bytes as shipped. Nothing is
    mocked and nothing is paraphrased: a recipe reworded in the skill is the recipe that
    runs here. No network, so this is part of the default suite rather than opt-in.
    """

    DEFAULT_MARKER = "rm -rf <dir>/.git && git -C <dir> init -b main"
    PRESERVING_MARKER = ".pipelex-starter-XXXXXX"

    @staticmethod
    def _commit(repository: Path, message: str) -> None:
        _git_commit(repository, message)

    @pytest.fixture(scope="class")
    def starter(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        """A local repository standing in for a starter template.

        It carries what makes the move hard rather than what makes it look real: entries
        beginning with a dot at the top level and nested inside one, which is the failure
        the shipped `cp -R "$tmp"/.` form exists to avoid.
        """
        template = tmp_path_factory.mktemp("starter-template")
        (template / "src").mkdir()
        (template / ".github" / "workflows").mkdir(parents=True)
        (template / ".claude" / "skills" / "bootstrap").mkdir(parents=True)
        (template / "package.json").write_text('{"name": "pipelex-starter-js", "version": "0.4.2"}\n', encoding="utf-8")
        (template / "README.md").write_text("# Starter\n", encoding="utf-8")
        (template / "src" / "index.ts").write_text("export const x = 1\n", encoding="utf-8")
        (template / ".gitignore").write_text("node_modules/\n.env.local\n", encoding="utf-8")
        (template / ".env.example").write_text("PIPELEX_BASE_URL=https://api.pipelex.com\nPIPELEX_API_KEY=\n", encoding="utf-8")
        (template / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
        (template / ".claude" / "skills" / "bootstrap" / "SKILL.md").write_text("# bootstrap\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(template), "init", "-q", "-b", "main"], check=True)
        subprocess.run(["git", "-C", str(template), "add", "-A"], check=True)
        self._commit(template, "the template as it came")
        return template

    # Every entry the stand-in starter ships, so a dropped one is named rather than counted.
    TEMPLATE_ENTRIES = frozenset({"package.json", "README.md", "src", ".gitignore", ".env.example", ".github", ".claude"})
    DOTTED_ENTRIES = frozenset({".gitignore", ".env.example", ".github", ".claude"})

    def _run(
        self,
        recipe: str,
        *,
        starter: Path,
        target: Path,
        path_prefix: Path | None = None,
        dir_literal: str | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """The recipe as shipped, with only the remote and `<dir>` bound.

        `dir_literal` binds `<dir>` to a spelling other than the target's absolute path — `.`, say —
        and `cwd` is the directory the shell starts in, which is what makes such a spelling mean the
        target at all.
        """
        script = recipe.replace(STARTER_URL, f"file://{starter}").replace("<dir>", dir_literal or str(target))
        assert "<dir>" not in script and "github.com" not in script, "a placeholder survived the binding"
        environment = dict(os.environ)
        if path_prefix is not None:
            environment["PATH"] = f"{path_prefix}{os.pathsep}{environment['PATH']}"
        return subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
            cwd=None if cwd is None else str(cwd),
        )

    @property
    def default_recipe(self) -> str:
        return _recipe(SKILL_TEMPLATE.read_text(encoding="utf-8"), self.DEFAULT_MARKER)

    @property
    def preserving_recipe(self) -> str:
        return _recipe(SKILL_TEMPLATE.read_text(encoding="utf-8"), self.PRESERVING_MARKER)

    @staticmethod
    def _entries(directory: Path) -> set[str]:
        return {entry.name for entry in directory.iterdir()}

    @staticmethod
    def _make_repository(directory: Path, branch: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "-C", str(directory), "init", "-q", "-b", branch], check=True)

    @staticmethod
    def _temporaries_beside(target: Path) -> list[str]:
        return [entry.name for entry in target.parent.iterdir() if entry.name.startswith(".pipelex-starter-")]

    def test_the_default_recipe_populates_a_directory_that_does_not_exist(self, starter: Path, tmp_path: Path) -> None:
        target = tmp_path / "my-app"
        result = self._run(self.default_recipe, starter=starter, target=target)
        assert result.returncode == 0, result.stderr
        assert self._entries(target) == self.TEMPLATE_ENTRIES | {".git"}
        # Fresh history and no remote: what GitHub's "Use this template" button produces.
        assert subprocess.run(["git", "-C", str(target), "remote"], capture_output=True, text=True, check=True).stdout == ""
        assert subprocess.run(["git", "-C", str(target), "log", "-1"], capture_output=True, text=True, check=False).returncode != 0

    def test_the_default_recipe_populates_an_empty_directory(self, starter: Path, tmp_path: Path) -> None:
        target = tmp_path / "my-app"
        target.mkdir()
        result = self._run(self.default_recipe, starter=starter, target=target)
        assert result.returncode == 0, result.stderr
        assert self._entries(target) == self.TEMPLATE_ENTRIES | {".git"}

    def test_the_default_recipe_cannot_serve_a_lone_git_directory(self, starter: Path, tmp_path: Path) -> None:
        """The reproduction the ruling was made on, kept executable.

        This is why the preserving recipe exists, and the assertion that would go green if
        someone decided one recipe was enough after all. The `|| exit` holds, so the user's
        repository is untouched — the cost is a dead end, not damage.
        """
        target = tmp_path / "my-app"
        self._make_repository(target, "main")
        result = self._run(self.default_recipe, starter=starter, target=target)
        assert result.returncode != 0
        assert "already exists and is not an empty directory" in result.stderr
        assert self._entries(target) == {".git"}

    def test_the_preserving_recipe_leaves_the_users_repository_standing(self, starter: Path, tmp_path: Path) -> None:
        """The ruling itself: their commit, their branch, their reflog, their remote.

        An assertion that the run succeeded is not the claim being made — the claim is that
        the repository the user made survived it, so every part of it is read back.
        """
        target = tmp_path / "my-app"
        self._make_repository(target, "trunk")
        (target / "NOTES.md").write_text("my notes\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(target), "add", "NOTES.md"], check=True)
        self._commit(target, "my own first commit")
        subprocess.run(["git", "-C", str(target), "rm", "-q", "NOTES.md"], check=True)
        self._commit(target, "and then I emptied the worktree")
        subprocess.run(["git", "-C", str(target), "remote", "add", "origin", "https://github.com/someone/theirs.git"], check=True)

        def read(*arguments: str) -> str:
            return subprocess.run(["git", "-C", str(target), *arguments], capture_output=True, text=True, check=True).stdout

        commits_before, branch_before, reflog_before = read("log", "--format=%H"), read("rev-parse", "--abbrev-ref", "HEAD"), read("reflog")
        assert self._entries(target) == {".git"}, "the fixture is not the lone-.git shape the ruling is about"

        result = self._run(self.preserving_recipe, starter=starter, target=target)
        assert result.returncode == 0, result.stderr

        assert read("log", "--format=%H") == commits_before, "a commit of the user's did not survive"
        assert read("rev-parse", "--abbrev-ref", "HEAD") == branch_before == "trunk\n"
        assert read("reflog") == reflog_before, "the reflog was rewritten"
        assert "https://github.com/someone/theirs.git" in read("remote", "-v"), "the user's remote is gone"
        assert "pipelex-starter" not in read("remote", "-v"), "the template's remote came with it"
        # Their first commit still holds the file they put in it, so nothing was rewritten quietly.
        assert "NOTES.md" in read("show", "--stat", "--format=", f"{commits_before.split()[-1]}")
        assert read("fsck", "--no-progress") == ""
        # And the template arrived, so this is an acquisition and not a no-op that preserved
        # the repository by doing nothing at all.
        assert self._entries(target) == self.TEMPLATE_ENTRIES | {".git"}

    def test_the_preserving_recipe_carries_every_entry_beginning_with_a_dot(self, starter: Path, tmp_path: Path) -> None:
        """`mv "$tmp"/*` drops these and exits 0, so the failure looks exactly like success.

        Read off the destination rather than reasoned about from the glob, which is the
        whole point: a starter that arrives without its `.gitignore` commits `node_modules/`
        into the baseline, and nothing in the run says so.
        """
        target = tmp_path / "my-app"
        self._make_repository(target, "main")
        result = self._run(self.preserving_recipe, starter=starter, target=target)
        assert result.returncode == 0, result.stderr
        assert self.DOTTED_ENTRIES <= self._entries(target)
        # Nested inside a dot-directory too, not just at the top level.
        assert (target / ".github" / "workflows" / "ci.yml").is_file()
        assert (target / ".claude" / "skills" / "bootstrap" / "SKILL.md").is_file()
        # And the recipe never reaches for the glob that would have dropped them.
        assert 'mv "$tmp"/*' not in self.preserving_recipe

    def test_the_preserving_recipe_refuses_a_directory_holding_git_and_anything_else(self, starter: Path, tmp_path: Path) -> None:
        """Not the ruled case. The exception is one entry named `.git`, never `.git` and friends."""
        target = tmp_path / "my-app"
        self._make_repository(target, "main")
        (target / "my-file.txt").write_text("mine\n", encoding="utf-8")
        result = self._run(self.preserving_recipe, starter=starter, target=target)
        assert result.returncode != 0
        assert self._entries(target) == {".git", "my-file.txt"}
        assert (target / "my-file.txt").read_text(encoding="utf-8") == "mine\n"
        assert self._temporaries_beside(target) == []

    def test_the_preserving_recipe_refuses_a_directory_holding_only_ignorable_cruft(self, starter: Path, tmp_path: Path) -> None:
        """The names the earlier ruling deliberately declined go on refusing.

        `.DS_Store`, `.idea/`, `.vscode/` and `Thumbs.db` are not an exception waiting to be
        granted: a list that grows by guesswork is how this rule drifts back into the agent
        judging which of a user's files matter, which is what the refusal exists to forbid.
        The recipe's own `ls -A` line is that rule in executable form, so it is read here.
        """
        target = tmp_path / "my-app"
        target.mkdir()
        (target / ".idea").mkdir()
        (target / ".vscode").mkdir()
        (target / ".DS_Store").write_text("", encoding="utf-8")
        (target / "Thumbs.db").write_text("", encoding="utf-8")
        result = self._run(self.preserving_recipe, starter=starter, target=target)
        assert result.returncode != 0
        assert self._entries(target) == {".idea", ".vscode", ".DS_Store", "Thumbs.db"}
        assert self._temporaries_beside(target) == []

    def test_no_delete_in_the_preserving_recipe_addresses_a_path_under_the_target(self, starter: Path, tmp_path: Path) -> None:
        """The ordering claim, recorded rather than argued.

        Every argument every `rm` is given is logged by a shim on the `PATH`, and the run is
        read back: the only paths a delete may be pointed at are the temporary clone's `.git`
        and the temporary clone itself. This is what makes the recipe safe to aim at a
        directory holding somebody's repository, and it is the assertion that would fail if
        the discard were ever reordered to after the copy.
        """
        real_rm = shutil.which("rm")
        assert real_rm is not None, "these tests already require a POSIX userland"
        log = tmp_path / "rm-targets.log"
        shim_bin = tmp_path / "shim-bin"
        shim_bin.mkdir()
        shim = shim_bin / "rm"
        shim.write_text(
            f'#!/bin/sh\nfor a in "$@"; do case "$a" in -*) ;; *) echo "$a" >> "{log}";; esac; done\nexec {real_rm} "$@"\n',
            encoding="utf-8",
        )
        shim.chmod(0o755)

        target = tmp_path / "my-app"
        self._make_repository(target, "main")
        result = self._run(self.preserving_recipe, starter=starter, target=target, path_prefix=shim_bin)
        assert result.returncode == 0, result.stderr

        targets = [line for line in log.read_text(encoding="utf-8").splitlines() if line]
        assert targets, "the shim recorded nothing — the recipe no longer deletes, or the shim was bypassed"
        under_the_users_directory = [line for line in targets if Path(line) == target or target in Path(line).parents]
        assert under_the_users_directory == [], f"a delete was pointed inside the user's directory: {under_the_users_directory}"
        assert all(".pipelex-starter-" in line for line in targets), f"a delete left the temporary path: {targets}"

    def test_the_preserving_recipe_removes_its_temporary_path_on_success_and_on_refusal(self, starter: Path, tmp_path: Path) -> None:
        """A temporary directory left beside the user's project is litter they did not make,
        and on the refusal paths it is litter with a whole starter inside it."""
        succeeding = tmp_path / "ok" / "my-app"
        self._make_repository(succeeding, "main")
        assert self._run(self.preserving_recipe, starter=starter, target=succeeding).returncode == 0
        assert self._temporaries_beside(succeeding) == []

        refusing = tmp_path / "no" / "my-app"
        self._make_repository(refusing, "main")
        (refusing / "theirs.txt").write_text("mine\n", encoding="utf-8")
        assert self._run(self.preserving_recipe, starter=starter, target=refusing).returncode != 0
        assert self._temporaries_beside(refusing) == []

        # A clone that cannot run at all: the failure the `|| exit` chain was written for.
        unreachable = tmp_path / "gone" / "my-app"
        self._make_repository(unreachable, "main")
        missing_remote = self.preserving_recipe.replace(STARTER_URL, f"file://{tmp_path / 'no-such-repository'}")
        assert self._run(missing_remote, starter=starter, target=unreachable).returncode != 0
        assert self._temporaries_beside(unreachable) == []
        assert self._entries(unreachable) == {".git"}

    @pytest.mark.parametrize("spelling", [".", "./"])
    def test_the_preserving_recipe_serves_the_destination_spelled_here(self, starter: Path, tmp_path: Path, spelling: str) -> None:
        """The destination is usually `.`, and the recipe has to survive being told so.

        `mkdir my-app && cd my-app && git init` is the "Where" rule's own account of how a user
        reaches a directory holding nothing but `.git`, and they then ask for the project *here* —
        so `<dir>` binds to `.`, not to a path with a parent to speak of. Computing the parent from
        that spelling gives `.` again, which puts the temporary directory inside the destination;
        the `ls -A` line then finds it beside `.git` and refuses, every time, on the one case the
        ruling was written to serve. Every other recipe test binds `<dir>` to an absolute path,
        which is exactly why this went unnoticed until round 2.
        """
        target = tmp_path / "my-app"
        self._make_repository(target, "main")
        (target / "NOTES.md").write_text("theirs\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(target), "add", "NOTES.md"], check=True)
        self._commit(target, "the user's own commit")
        (target / "NOTES.md").unlink()
        head = subprocess.run(["git", "-C", str(target), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout

        result = self._run(self.preserving_recipe, starter=starter, target=target, dir_literal=spelling, cwd=target)

        assert result.returncode == 0, result.stderr
        assert self.TEMPLATE_ENTRIES <= self._entries(target)
        assert self.DOTTED_ENTRIES <= self._entries(target)
        # The temporary path was a sibling, and it was cleaned up.
        assert self._temporaries_beside(target) == []
        assert [entry for entry in self._entries(target) if entry.startswith(".pipelex-starter-")] == []
        # And the user's repository is untouched: same commit, same branch.
        assert subprocess.run(["git", "-C", str(target), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout == head
        assert (
            subprocess.run(["git", "-C", str(target), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
            == "main"
        )

    def test_the_temporary_path_is_beside_the_target_and_collision_proof(self, starter: Path, tmp_path: Path) -> None:
        """Beside, so the acquisition never crosses a filesystem or a small `/tmp`; named by
        `mktemp`, so two runs in the same parent cannot land on each other."""
        recipe = self.preserving_recipe
        assert 'tmp=$(mktemp -d "$(dirname "$dir")/.pipelex-starter-XXXXXX")' in recipe
        target = tmp_path / "my-app"
        self._make_repository(target, "main")
        # The name is generated, so the same recipe run twice in one parent must not collide.
        assert self._run(recipe, starter=starter, target=target).returncode == 0
        second = tmp_path / "other-app"
        self._make_repository(second, "main")
        assert self._run(recipe, starter=starter, target=second).returncode == 0
        assert self._temporaries_beside(target) == []

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_the_recipes_executed_here_are_the_bytes_every_target_ships(self, target_name: str) -> None:
        """This suite executes the template, so the renders must carry the same block.

        The acquisition recipes carry no Jinja, which is what makes reading the template
        safe — but that is a claim about the renders, so it is read off them rather than
        argued. `make agent-check` proves the committed trees are fresh; this proves the
        freshness is of these lines, which are the ones a user installs and runs.
        """
        config = load_target_config(REPO_ROOT / "targets", target_name)
        installed = (resolve_output_dir(REPO_ROOT, config.source) / "skills" / "pipelex-scaffold" / "SKILL.md").read_text(encoding="utf-8")
        template = SKILL_TEMPLATE.read_text(encoding="utf-8")
        for marker in (
            self.DEFAULT_MARKER,
            self.PRESERVING_MARKER,
            METHOD_APP_MARKER,
            CREATE_MARKER,
            DEV_SERVER_MARKER,
            OWN_REPOSITORY_MARKER,
            LOOPBACK_GUARD_MARKER,
        ):
            assert _recipe(installed, marker) == _recipe(template, marker), f"{target_name}: the shipped recipe is not the one executed here"


class TestMethodAppBranch:
    """The TypeScript branch is the method app, driven to a running page.

    Ratified on 2026-09-16 with the method-app template: a TypeScript web app around a method is a
    copy of `pipelex-method-apps`' `webapp-js/`, made the user's by the template's own `make create`
    and left with its dev server up and its URL reported. The gallery, `pipelex-starter-js`, is
    acquired only when the user names it. The skill carries none of the gesture: it copies,
    commits once, drives the command and proves the page answers. Asserted on the template and on
    every render, because a rule that holds only in `templates/` is a rule no user reads.
    """

    @staticmethod
    def bodies() -> list[str]:
        return [SKILL_TEMPLATE.read_text(encoding="utf-8")] + [_render_skill(target) for target in TARGETS]

    def test_the_typescript_branch_copies_the_method_app_and_the_gallery_waits_to_be_named(self) -> None:
        for body in self.bodies():
            assert "the `webapp-js/` directory of `pipelex-method-apps`" in body
            assert (
                "`pipelex-starter-js`, the gallery of worked examples the method app was extracted from, is acquired only when the user names it"
                in body
            )
            assert "**The gallery is never offered**" in body
            assert "**The method app needs the method first.**" in body
            recipe = _recipe(body, METHOD_APP_MARKER)
            # Only the template directory crosses, and only into a directory the "Where" rule admits.
            assert 'cp -R "$tmp/webapp-js"/. "$dir"/' in recipe
            assert recipe.count('case "$(ls -A "$dir")" in ""|.git)') == 2, "the directory is read before the fetch and again before the copy"
            assert '[ -f "$tmp/webapp-js/package.json" ]' in recipe
            # A repository the user made is never initialized over.
            assert recipe.rstrip().endswith('[ -e "$dir/.git" ] || git -C "$dir" init -b main')
            assert "**The `webapp-js/` test is load-bearing.**" in body
            assert "do not fall back to the gallery" in body
            # One pristine commit for every template, named by the family and the directory.
            assert "`<template>` is `pipelex-method-apps/webapp-js`, `pipelex-starter-js` or `pipelex-starter-python`" in body
            # The method app is not a template repository, so the GitHub form starts from the copy.
            assert "gh repo create <owner>/<name> --private --source <dir> --remote origin" in body

    def test_the_create_gesture_is_driven_and_never_reimplemented(self) -> None:
        for body in self.bodies():
            create = _recipe(body, CREATE_MARKER)
            assert "make -C <dir> create METHOD='<method>'" in create
            assert "**given as an absolute path**" in body
            assert "only when the conversation already holds them or the user asked for something other than what the method carries" in body
            assert "none of it is reimplemented here" in body
            assert "never by editing `src/generated/`" in body
            assert "It commits nothing." in body
            # The gesture installs the dependencies before its refusals, dry run included.
            assert "refuses before it changes a tracked file" in body
            assert "changes no tracked file, so the gesture can run again" in body
            assert "exactly as it was, so the gesture" not in body
            # The gesture writes its own env file, so the skill's env-file step is the starters' alone.
            assert "### Step 5: The env file — a starter only" in body
            assert "The method app's gesture wrote `.env.local` in step 4" in body
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
            assert PORT_CHECK_COMMAND in body
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
            assert "| Nothing listens once the wait is spent | the server did not start" in body
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
            # Without lsof, port-check passes whatever holds the port and the listener cannot be read.
            assert "The method app also needs `make`, `curl` and `lsof`" in body
            # The starters keep the ruling that the skill starts no server for them.
            assert body.index("do not start `make dev`") > body.index("#### A starter: hand off")

    def test_the_reference_puts_the_method_app_first_and_carries_its_recipe(self) -> None:
        reference = STARTERS_REFERENCE.read_text(encoding="utf-8")
        assert "| | The method app (`pipelex-method-apps/webapp-js`) | `pipelex-starter-js` (the gallery) | `pipelex-starter-python` |" in reference
        assert "The skill acquires it only when the user names it." in reference
        # The reference's chain is the skill's. The pristine commit is a block of its own, because on a
        # repository the user made it lands on their branch and is confirmed before it runs.
        skill_recipe = _recipe(SKILL_TEMPLATE.read_text(encoding="utf-8"), METHOD_APP_MARKER)
        reference_recipe = _recipe(reference, METHOD_APP_MARKER)
        assert reference_recipe == skill_recipe, "the reference ships a different copy-out chain than the skill"
        assert 'git -C "$dir" commit' not in reference_recipe and " add -A" not in reference_recipe
        assert _recipe(reference, "webapp-js <version>").strip() == PRISTINE_METHOD_APP_COMMIT
        assert "make dev APP_PORT=<port> APP_HOST=127.0.0.1" in reference
        # A dry run installs the dependencies first, so it is not free of writes.
        assert "writes nothing" not in reference
        assert "gh repo create <owner>/<name> --private --source <dir> --remote origin" in reference

    def test_integrate_runs_the_bundle_arm_on_a_project_that_has_one(self) -> None:
        """A project made from the method app scaffolds a local bundle with one command.

        The gallery's `make add-method` refuses a bundle path, so `/pipelex-integrate` sent every
        local bundle down the hand-written route. The method app's takes one, and its usage says so.
        """
        integrate = (REPO_ROOT / "templates" / "skills" / "pipelex-integrate" / "SKILL.md.j2").read_text(encoding="utf-8")
        assert "**a local bundle is one command when the project's `make add-method` takes a bundle path**" in integrate
        assert "**otherwise, place the method where the project keeps them**" in integrate
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


# The dev-server block waits on `lsof` and proves the page with `curl`; both are the method app's prerequisites.
NEEDS_SERVER_TOOLS = pytest.mark.skipif(
    shutil.which("lsof") is None or shutil.which("curl") is None, reason="the dev-server block needs lsof and curl"
)


@NEEDS_GIT
class TestMethodAppRecipes:
    """The method app's blocks, extracted from the skill and executed.

    The copy-out chain touches a directory the user may have made, so it is proven the way the
    starters' acquisition is: run as shipped against a local repository standing in for the
    family, with only the URL and `<dir>` bound. The create and dev-server blocks are run too,
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
    def test_a_starter_s_own_checkout_is_refused(self, tmp_path: Path, shell: list[str]) -> None:
        checkout = tmp_path / "pipelex-starter-python"
        checkout.mkdir()
        subprocess.run(["git", "-C", str(checkout), "init", "-q", "-b", "main"], check=True)
        subprocess.run(["git", "-C", str(checkout), "remote", "add", "origin", "https://github.com/Pipelex/pipelex-starter-python.git"], check=True)
        result = self._own_repository(dir_literal=str(checkout), shell=shell, cwd=tmp_path)
        assert result.returncode != 0
        assert "Reinitialized" not in result.stdout + result.stderr

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
        assert f"nothing listens on port {port}" in result.stderr
        assert "stopped" not in result.stderr
        assert "usage" not in result.stderr.lower()
