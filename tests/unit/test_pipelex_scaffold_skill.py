"""Pin the pipelex-scaffold skill: two branches, no templates of its own, one commit, delegated bootstrap."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir


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
            assert "branch B runs `git init -b main` in the directory it is working in one step later" in body
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
        assert "git clone --depth 1 https://github.com/Pipelex/pipelex-starter-js.git <dir> || exit" in starters
        assert "git clone --depth 1 https://github.com/Pipelex/pipelex-starter-python.git <dir> || exit" in starters
        assert "The `|| exit` on the clone is load-bearing" in starters
        assert "gh repo create <owner>/<name> --template Pipelex/pipelex-starter-python" in starters
        assert "shell out to a `pipelex` CLI the starter does not depend on" in starters
        initializers = (self.REFERENCES_DIR / "initializers.md").read_text(encoding="utf-8")
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
