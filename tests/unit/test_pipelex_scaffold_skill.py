"""Pin the pipelex-scaffold skill: two branches, no templates of its own, one commit, delegated bootstrap."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir, setup_static_assets


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
        "**state the exact command and confirm before running it**",
        "do not start `make dev`",
        "Add **no** SDK dependency and create **no** empty `methods/` directory",
        "Nothing beyond what the initializer writes is authored by this skill",
    )

    @property
    def scaffold(self) -> str:
        return self.TEMPLATE.read_text(encoding="utf-8")

    def test_the_rules_are_stated(self) -> None:
        body = self.scaffold
        for rule in self.RULES:
            assert rule in body, f"missing rule: {rule}"

    def test_fresh_clone_shortcut_and_template_checkout_stop(self) -> None:
        body = self.scaffold
        assert "**The fresh-clone shortcut.**" in body
        assert "Do not clone again." in body
        assert "this is the template, not a copy of it" in body

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
        assert "git clone --depth 1 https://github.com/Pipelex/pipelex-starter-js.git" in starters
        assert "gh repo create <owner>/<name> --template Pipelex/pipelex-starter-python" in starters
        assert "shell out to a `pipelex` CLI the starter does not depend on" in starters
        initializers = (self.REFERENCES_DIR / "initializers.md").read_text(encoding="utf-8")
        assert "uv init --package <dir>" in initializers
        assert "npm create next-app@latest <dir> -- --ts --app --src-dir --eslint --use-npm --yes" in initializers
        assert "No SDK dependency" in initializers

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
    def test_the_build_copies_the_references_byte_for_byte(self, target_name: str, tmp_path: Path) -> None:
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        setup_static_assets(self.REPO_ROOT, tmp_path, self.REPO_ROOT / "templates", config.include_skills)
        produced = tmp_path / "skills" / "pipelex-scaffold" / "references"
        for reference in self.REFERENCES:
            assert (produced / reference).is_file(), f"{target_name}: the build did not copy references/{reference}"
            assert (produced / reference).read_bytes() == (self.REFERENCES_DIR / reference).read_bytes()
