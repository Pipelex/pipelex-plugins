"""Pin the pipelex-scaffold skill: two branches, no templates of its own, one commit, delegated bootstrap."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
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

NEEDS_GIT = pytest.mark.skipif(shutil.which("git") is None, reason="the acquisition recipes are git")


def _bash_blocks(text: str) -> list[str]:
    return [match.group(1) for match in BASH_BLOCK.finditer(text)]


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
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-scaffold"],
            target_name=config.name,
        )
        return next(content for path, content in rendered.items() if path.match("skills/pipelex-scaffold/SKILL.md"))

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
            assert "grep -q '^PIPELEX_API_KEY=.\\+' <dir>/.env.local || printf" in body
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

    def test_declares_no_mcp_tool(self) -> None:
        """The scaffold skill is MCP-free: no allowed-tools entry, no MCP-absent STOP message."""
        body = self.scaffold
        assert "mcp__" not in body
        assert "plugin manifest spawns" not in body
        assert "It needs no MCP tool and no API key" in body

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
        assert "shell out to a `pipelex` CLI the starter does not depend on" in starters
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
        assert 'commit -m "Start from Pipelex/<starter> <version> (<sha>)" -- .' in body
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
    PRESERVING_MARKER = "mktemp -d"

    @staticmethod
    def _commit(repository: Path, message: str) -> None:
        subprocess.run(
            ["git", "-C", str(repository), "-c", "user.email=t@example.com", "-c", "user.name=Test", "commit", "-q", "-m", message],
            check=True,
        )

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
        for marker in (self.DEFAULT_MARKER, self.PRESERVING_MARKER):
            assert _recipe(installed, marker) == _recipe(template, marker), f"{target_name}: the shipped recipe is not the one executed here"
