"""Tests for scripts/gen_skill_docs.py template rendering."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import ClassVar, cast

import pytest

from scripts.gen_skill_docs import (
    CODEX_DISCOVERY_MARKETPLACE_DST,
    CODEX_DISCOVERY_MARKETPLACE_SRC,
    HOOK_TEMPLATES_BY_PLATFORM,
    MCP_TEMPLATES_BY_PLATFORM,
    SHARED_TEMPLATES,
    STATIC_HOOK_ASSETS_BY_PLATFORM,
    Platform,
    TargetConfig,
    build_target,
    check_freshness,
    generate,
    load_defaults,
    load_target_config,
    make_plugin_json,
    orphaned_outputs,
    render_codex_discovery_marketplace,
    render_templates,
    resolve_output_dir,
    setup_static_assets,
    static_asset_mismatches,
    static_asset_outputs,
)

DEFAULT_VARS: dict[str, str | bool] = {"marketplace_name": "pipelex-plugins", "plugin_name": "pipelex", "platform": "claude"}

# Include-only partial: a file under templates/skills/shared/ that skill
# templates {% include %}, but which is NOT in SHARED_TEMPLATES (not rendered
# standalone).
FRONTMATTER_PARTIAL = "skills/shared/frontmatter.md.j2"

# The skills that stop when the workshop is absent. A skill that works without it
# — pipelex-explain, pipelex-synthetic-inputs, pipelex-scaffold, and pipelex-lab,
# whose loop alone needs it — stays out.
MCP_SKILLS = ("pipelex-design", "pipelex-organize", "pipelex-edit", "pipelex-inputs", "pipelex-integrate", "pipelex-run", "pipelex-catalog")
FRONTMATTER_BODY = '{%- if platform == "claude" -%}\nallowed-tools:\n  - Bash\n{% endif -%}\n'


# Minimal hook templates for every platform. render_templates declares hooks
# per platform (Claude: hooks.json + check-mthds.sh; Codex: codex-hooks.json;
# Vibe: vibe-hooks.toml + check-mthds-vibe.sh + the mcp/vibe-mcp.toml launcher
# fragment), so any test tree that reaches skill/hook rendering must provide them
# or render fails with "hook template not found".
HOOK_TEMPLATE_BODIES = {
    "hooks/hooks.json.j2": '{"hooks": {"PostToolUse": []}}\n',
    "hooks/check-mthds.sh.j2": "#!/usr/bin/env bash\nexit 0\n",
    "hooks/launch-pipelex-mcp.sh.j2": "#!/usr/bin/env bash\nexit 0\n",
    "hooks/codex-hooks.json.j2": '{"hooks": {"PostToolUse": []}}\n',
    "hooks/check-mthds-codex.sh.j2": "#!/usr/bin/env bash\nexit 0\n",
    "hooks/vibe-hooks.toml.j2": '[[hooks]]\ntype = "post_tool"\nmatch = "re:^(edit|write_file)$"\ncommand = "./hooks/check-mthds-vibe.sh"\n',
    "hooks/check-mthds-vibe.sh.j2": "#!/usr/bin/env bash\nexit 0\n",
    "mcp/vibe-mcp.toml.j2": '[[mcp_servers]]\nname = "pipelex"\ntransport = "stdio"\ncommand = "npx"\n',
}

# Static hook assets are copied verbatim — the fixture body stands in for the
# vendored check.mjs bundle (whose real content is a 4+ MB esbuild artifact).
STATIC_ASSET_BODIES = {
    "hooks/assets/check.mjs": "// vendored hook bundle {{ not_a_template }}\n",
}


def _create_hook_templates(templates_dir: Path) -> None:
    """Create minimal per-platform hook templates and static assets so
    render_templates resolves them."""
    for name, body in HOOK_TEMPLATE_BODIES.items():
        path = templates_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(body)
    for name, body in STATIC_ASSET_BODIES.items():
        path = templates_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(body)


def _create_shared_templates(templates_dir: Path) -> None:
    """Create all shared template files required by render_templates, plus the
    include-only frontmatter partial and the per-platform hook templates."""
    for name in SHARED_TEMPLATES:
        path = templates_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("# placeholder\n")
    partial = templates_dir / FRONTMATTER_PARTIAL
    partial.parent.mkdir(parents=True, exist_ok=True)
    if not partial.exists():
        partial.write_text(FRONTMATTER_BODY)
    _create_hook_templates(templates_dir)


@pytest.fixture()
def template_tree(tmp_path: Path) -> Path:
    """Create a minimal repo with templates/, one skill, and a prod target."""
    templates_dir = tmp_path / "templates"
    shared = templates_dir / "skills" / "shared"
    shared.mkdir(parents=True)
    (shared / "writing-mthds.md.j2").write_text("# MTHDS Language Reference {{ marketplace_name }}\n")
    (shared / "native-content-types.md.j2").write_text("# Native Content Types\n")
    (shared / "credentials.md.j2").write_text("# Credentials\n")
    (shared / "catalog-id.md.j2").write_text("# Catalog id\n")
    (shared / "frontmatter.md.j2").write_text(FRONTMATTER_BODY)
    _create_hook_templates(templates_dir)

    skill_dir = templates_dir / "skills" / "pipelex-test"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md.j2").write_text("---\nname: test\n{% include 'skills/shared/frontmatter.md.j2' %}---\n\nRest of skill.\n")

    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin-base.json").write_text('{"author": {"name": "test"}, "license": "Apache-2.0"}\n')

    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()
    (targets_dir / "defaults.toml").write_text('[vars]\nmarketplace_name = "pipelex-plugins"\nplatform = "claude"\n')
    (targets_dir / "prod.toml").write_text('[plugin]\nname = "pipelex"\nversion = "1.0.0"\nsource = "pipelex/"\n')

    return tmp_path


def _create_codex_tree(tmp_path: Path) -> Path:
    """Create a minimal repo with Claude, Codex, and Mistral Vibe targets."""
    templates_dir = tmp_path / "templates"
    shared = templates_dir / "skills" / "shared"
    shared.mkdir(parents=True)
    (shared / "writing-mthds.md.j2").write_text("Ref.\n")
    (shared / "native-content-types.md.j2").write_text("Types.\n")
    (shared / "credentials.md.j2").write_text("Credentials.\n")
    (shared / "catalog-id.md.j2").write_text("Catalog id.\n")
    (shared / "frontmatter.md.j2").write_text(FRONTMATTER_BODY)
    _create_hook_templates(templates_dir)

    skill_dir = templates_dir / "skills" / "pipelex-test"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md.j2").write_text("---\nname: test\n{% include 'skills/shared/frontmatter.md.j2' %}---\n\nContent.\n")

    claude_plugin = tmp_path / ".claude-plugin"
    claude_plugin.mkdir()
    (claude_plugin / "plugin-base.json").write_text('{"author": {"name": "test"}, "license": "Apache-2.0"}\n')

    codex_plugin = tmp_path / ".codex-plugin"
    codex_plugin.mkdir()
    (codex_plugin / "plugin-base.json").write_text(
        '{"author": {"name": "test"}, "license": "Apache-2.0", "skills": "./skills/", "interface": {"displayName": "Test"}}\n'
    )

    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()
    (targets_dir / "defaults.toml").write_text(
        '[vars]\nmarketplace_name = "pipelex-plugins"\nplatform = "claude"\n\n'
        '[vars.mcp_server]\ncommand = "npx"\nargs = ["-y", "@pipelex/mcp@latest"]\nenv_vars = ["PIPELEX_API_KEY", "PIPELEX_BASE_URL"]\n\n'
        '[vars.mcp_server.user_config.api_key]\ntype = "string"\ntitle = "Pipelex API key"\ndescription = "Key."\nsensitive = true\n\n'
        '[vars.mcp_server.user_config.base_url]\ntype = "string"\ntitle = "Pipelex API base URL"\ndescription = "URL."\n'
    )
    (targets_dir / "prod.toml").write_text('[plugin]\nname = "pipelex"\nversion = "1.0.0"\nsource = "pipelex/"\n')
    (targets_dir / "codex.toml").write_text(
        '[plugin]\nname = "pipelex"\nversion = "1.0.0"\nsource = "pipelex-codex/"\n\n[vars]\nplatform = "codex"\n'
    )
    (targets_dir / "mistral-vibe.toml").write_text(
        '[plugin]\nname = "pipelex-vibe"\nversion = "1.0.0"\nsource = "pipelex-vibe/"\n\n[vars]\nplatform = "mistral-vibe"\n'
    )

    return tmp_path


class TestRenderTemplates:
    def test_renders_include(self, template_tree: Path) -> None:
        results = render_templates(template_tree / "templates", template_tree, DEFAULT_VARS)
        skill_output = template_tree / "skills" / "pipelex-test" / "SKILL.md"
        assert skill_output in results
        rendered = results[skill_output]
        assert "allowed-tools" in rendered
        assert "Rest of skill." in rendered
        assert "{% include" not in rendered

    def test_renders_shared_templates(self, template_tree: Path) -> None:
        results = render_templates(template_tree / "templates", template_tree, DEFAULT_VARS)
        ref_output = template_tree / "skills" / "shared" / "writing-mthds.md"
        assert ref_output in results
        assert "MTHDS Language Reference pipelex-plugins" in results[ref_output]

    def test_frontmatter_not_rendered_standalone(self, template_tree: Path) -> None:
        """frontmatter.md.j2 is an include-only partial — it must never be
        emitted as a standalone skills/shared/frontmatter.md output."""
        results = render_templates(template_tree / "templates", template_tree, DEFAULT_VARS)
        frontmatter_output = template_tree / "skills" / "shared" / "frontmatter.md"
        assert frontmatter_output not in results

    def test_no_skill_templates(self, tmp_path: Path) -> None:
        """With shared templates but no skill templates, shared files still render."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        _create_shared_templates(templates_dir)
        results = render_templates(templates_dir, tmp_path, DEFAULT_VARS)
        output_names = {path.name for path in results}
        assert "writing-mthds.md" in output_names
        assert "native-content-types.md" in output_names

    def test_preserves_frontmatter(self, template_tree: Path) -> None:
        results = render_templates(template_tree / "templates", template_tree, DEFAULT_VARS)
        rendered = results[template_tree / "skills" / "pipelex-test" / "SKILL.md"]
        assert rendered.startswith("---\nname: test\n")

    def test_missing_include_raises(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        skill_dir = templates_dir / "skills" / "pipelex-test"
        skill_dir.mkdir(parents=True)
        _create_shared_templates(templates_dir)
        (skill_dir / "SKILL.md.j2").write_text("{% include 'skills/shared/nonexistent.md.j2' %}\n")
        with pytest.raises(SystemExit, match="include file not found"):
            render_templates(templates_dir, tmp_path, DEFAULT_VARS)

    def test_syntax_error_raises(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        skill_dir = templates_dir / "skills" / "pipelex-test"
        skill_dir.mkdir(parents=True)
        _create_shared_templates(templates_dir)
        (skill_dir / "SKILL.md.j2").write_text("{% if %}\n")
        with pytest.raises(SystemExit, match="syntax error"):
            render_templates(templates_dir, tmp_path, DEFAULT_VARS)

    def test_a_misspelled_variable_fails_the_build_instead_of_rendering_empty(self, tmp_path: Path) -> None:
        """The hazard this repo keeps meeting: under Jinja's default `Undefined`,
        `{{ floors.pipelex_sdk_jss }}` is not an error — it renders as the empty string,
        so the skill ships a sentence with a hole where a version floor belongs and every
        other gate stays green. The renderer builds under `StrictUndefined` for exactly
        that reason, and this is the test that says so.
        """
        templates_dir = tmp_path / "templates"
        skill_dir = templates_dir / "skills" / "pipelex-test"
        skill_dir.mkdir(parents=True)
        _create_shared_templates(templates_dir)
        (skill_dir / "SKILL.md.j2").write_text("Install at least `@pipelex/sdk` {{ floors.pipelex_sdk_jss }}.\n")
        with pytest.raises(SystemExit, match="undefined variable"):
            render_templates(templates_dir, tmp_path, {**DEFAULT_VARS, "floors": {"pipelex_sdk_js": "0.18.0"}})

    def test_an_undefined_top_level_variable_fails_the_build_too(self, tmp_path: Path) -> None:
        """Not only attributes of a table: a bare name nobody defined is the same hazard
        one level up, and it used to render as the empty string just as quietly."""
        templates_dir = tmp_path / "templates"
        skill_dir = templates_dir / "skills" / "pipelex-test"
        skill_dir.mkdir(parents=True)
        _create_shared_templates(templates_dir)
        (skill_dir / "SKILL.md.j2").write_text("The marketplace is {{ marketplace_nam }}.\n")
        with pytest.raises(SystemExit, match="undefined variable"):
            render_templates(templates_dir, tmp_path, DEFAULT_VARS)

    def test_missing_shared_template_raises(self, tmp_path: Path) -> None:
        """A declared shared template that is absent fails loudly."""
        templates_dir = tmp_path / "templates"
        (templates_dir / "skills" / "shared").mkdir(parents=True)
        with pytest.raises(SystemExit, match="shared template not found"):
            render_templates(templates_dir, tmp_path, DEFAULT_VARS)

    def test_missing_templates_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit, match="Templates directory not found"):
            render_templates(tmp_path / "templates", tmp_path, DEFAULT_VARS)

    def test_multiple_templates(self, template_tree: Path) -> None:
        templates_dir = template_tree / "templates"
        second = templates_dir / "skills" / "pipelex-second"
        second.mkdir()
        (second / "SKILL.md.j2").write_text("---\nname: second\n---\n\nSecond skill content.\n")

        results = render_templates(templates_dir, template_tree, DEFAULT_VARS)
        skill_names = {path.parent.name for path in results if path.parent.name not in ("shared", "hooks")}
        assert skill_names == {"pipelex-test", "pipelex-second"}

    def test_jinja2_escape_rendering(self, template_tree: Path) -> None:
        templates_dir = template_tree / "templates"
        skill_dir = templates_dir / "skills" / "pipelex-escape"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md.j2").write_text("Raw Jinja2 `{{ '{{' }} {{ '}}' }}` syntax\n")

        results = render_templates(templates_dir, template_tree, DEFAULT_VARS)
        rendered = results[template_tree / "skills" / "pipelex-escape" / "SKILL.md"]
        assert "{{ }}" in rendered
        assert "{{ '{{' }}" not in rendered

    def test_include_skills_filter(self, template_tree: Path) -> None:
        templates_dir = template_tree / "templates"
        second = templates_dir / "skills" / "pipelex-second"
        second.mkdir()
        (second / "SKILL.md.j2").write_text("---\nname: second\n---\n\nContent.\n")

        results = render_templates(templates_dir, template_tree, DEFAULT_VARS, include_skills=["pipelex-test"])
        skill_names = {path.parent.name for path in results if path.parent.name not in ("shared", "hooks")}
        assert skill_names == {"pipelex-test"}

    def test_empty_skill_filter_still_renders_shared(self, template_tree: Path) -> None:
        results = render_templates(template_tree / "templates", template_tree, DEFAULT_VARS, include_skills=["nonexistent-skill"])
        output_names = {path.name for path in results}
        assert "writing-mthds.md" in output_names

    def test_template_vars_injected(self, template_tree: Path) -> None:
        templates_dir = template_tree / "templates"
        skill_dir = templates_dir / "skills" / "pipelex-var"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md.j2").write_text("Marketplace: {{ marketplace_name }}\n")

        custom_vars = {**DEFAULT_VARS, "marketplace_name": "custom-name"}
        results = render_templates(templates_dir, template_tree, custom_vars)
        assert "Marketplace: custom-name" in results[template_tree / "skills" / "pipelex-var" / "SKILL.md"]


class TestSkillOverlay:
    """The per-target overlay: a SKILL.<target>.md.j2 next to a skill is
    appended to that skill's output only when building <target>."""

    def _write_overlay_skill(self, tmp_path: Path) -> Path:
        templates_dir = tmp_path / "templates"
        _create_shared_templates(templates_dir)
        skill_dir = templates_dir / "skills" / "pipelex-test"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md.j2").write_text("Base skill body.\n")
        (skill_dir / "SKILL.special.md.j2").write_text("OVERLAY for {{ marketplace_name }}.\n")
        return templates_dir

    def _skill_body(self, templates_dir: Path, base_dir: Path, target_name: str | None) -> str:
        rendered = render_templates(templates_dir, base_dir, DEFAULT_VARS, ["pipelex-test"], target_name=target_name)
        return next(content for path, content in rendered.items() if path.name == "SKILL.md")

    def test_overlay_appended_for_matching_target(self, tmp_path: Path) -> None:
        templates_dir = self._write_overlay_skill(tmp_path)
        assert "OVERLAY for pipelex-plugins." in self._skill_body(templates_dir, tmp_path, "special")

    def test_overlay_absent_for_other_target(self, tmp_path: Path) -> None:
        templates_dir = self._write_overlay_skill(tmp_path)
        assert "OVERLAY" not in self._skill_body(templates_dir, tmp_path, "prod")

    def test_no_target_name_skips_overlay(self, tmp_path: Path) -> None:
        templates_dir = self._write_overlay_skill(tmp_path)
        assert "OVERLAY" not in self._skill_body(templates_dir, tmp_path, None)


class TestGenerate:
    def test_writes_files(self, template_tree: Path) -> None:
        result = generate(template_tree, "prod")
        assert result == 0
        output = template_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md"
        assert output.is_file()
        assert "allowed-tools" in output.read_text()

    @pytest.mark.parametrize(
        ("source", "refusal"),
        [
            ("templates/", "overlaps the repository's templates/"),
            ("skills/pipelex-test/", "overlaps the repository's skills/"),
            ("pipelex-codex/", "overlaps the output of target 'codex'"),
            ("../outside/", "is not a directory inside the repository"),
        ],
    )
    def test_a_target_whose_directory_the_build_cannot_own_is_refused(self, tmp_path: Path, source: str, refusal: str) -> None:
        """The build prunes a target's directory down to what it produces, so a `source` that held the
        repository's own files or another target's output would have them deleted; the build and the
        check refuse it instead, and touch nothing."""
        tree = _create_codex_tree(tmp_path / "repo")
        (tree / "targets" / "prod.toml").write_text(f'[plugin]\nname = "pipelex"\nversion = "1.0.0"\nsource = "{source}"\n')
        before = sorted(path for path in tree.rglob("*"))
        with pytest.raises(SystemExit, match=re.escape(refusal)):
            generate(tree, "prod")
        with pytest.raises(SystemExit, match=re.escape(refusal)):
            check_freshness(tree, "prod")
        assert sorted(path for path in tree.rglob("*")) == before

    def test_no_templates_fails(self, tmp_path: Path) -> None:
        """Missing shared template files cause a clear SystemExit."""
        (tmp_path / "templates").mkdir()
        targets_dir = tmp_path / "targets"
        targets_dir.mkdir()
        (targets_dir / "defaults.toml").write_text('[vars]\nmarketplace_name = "pipelex-plugins"\n')
        (targets_dir / "prod.toml").write_text('[plugin]\nname = "pipelex"\nversion = "1.0.0"\nsource = "pipelex/"\n')
        with pytest.raises(SystemExit, match="shared template not found"):
            generate(tmp_path, "prod")


class TestCheckFreshness:
    def test_fresh_passes(self, template_tree: Path) -> None:
        generate(template_tree, "prod")
        assert check_freshness(template_tree, "prod") == 0

    def test_stale_fails(self, template_tree: Path) -> None:
        generate(template_tree, "prod")
        (template_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md").write_text("outdated content\n")
        assert check_freshness(template_tree, "prod") == 1

    def test_missing_md_fails(self, template_tree: Path) -> None:
        assert check_freshness(template_tree, "prod") == 1

    def test_orphaned_md_fails(self, template_tree: Path) -> None:
        generate(template_tree, "prod")
        orphan_dir = template_tree / "pipelex" / "skills" / "pipelex-orphan"
        orphan_dir.mkdir()
        (orphan_dir / "SKILL.md").write_text("orphaned content\n")
        assert check_freshness(template_tree, "prod") == 1

    def test_dry_run_no_side_effects(self, template_tree: Path) -> None:
        # Second Claude target (reuses the existing .claude-plugin base).
        targets_dir = template_tree / "targets"
        (targets_dir / "alt.toml").write_text('[plugin]\nname = "pipelex"\nversion = "1.0.0"\nsource = "pipelex-alt/"\n')
        alt_dir = template_tree / "pipelex-alt"
        assert not alt_dir.exists()
        check_freshness(template_tree, "alt")
        assert not alt_dir.exists(), "check_freshness must not create output directories"

    @pytest.mark.parametrize(
        "stray",
        [
            "pipelex/hooks/stray.sh",
            "pipelex/skills/shared/stray.md",
            "pipelex-vibe/mcp/stale.toml",
            "pipelex-codex/.claude-plugin/plugin.json",
        ],
    )
    def test_a_file_no_source_produces_is_reported_and_the_build_removes_it(
        self, tmp_path: Path, stray: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The whole file set of every target, not only its skills.

        The check used to look for an orphaned `SKILL.md` alone, so a file left under `hooks/`,
        `mcp/` or `skills/shared/` by a renamed template shipped with the check green, and the one
        orphan it did report came with `make build` as its cure, which removed nothing. The build
        now owns each target's directory: it removes what no source produces, the other platform's
        manifest after a platform change included, and the directory it leaves empty.
        """
        tree = _create_codex_tree(tmp_path)
        assert generate(tree, "all") == 0
        assert check_freshness(tree, "all") == 0
        (tree / stray).parent.mkdir(parents=True, exist_ok=True)
        (tree / stray).write_text("left behind\n", encoding="utf-8")

        capsys.readouterr()
        assert check_freshness(tree, "all") == 1
        assert f"ORPHAN: {stray} (no template or source file produces it: `make build` removes it)" in capsys.readouterr().out

        assert generate(tree, "all") == 0
        assert not (tree / stray).exists(), "the build left a file no source produces"
        if stray.startswith("pipelex-codex/.claude-plugin/"):
            assert not (tree / "pipelex-codex" / ".claude-plugin").exists(), "the emptied manifest directory stayed in the Codex target"
        assert check_freshness(tree, "all") == 0

    def test_a_retired_skill_leaves_with_its_directory(self, template_tree: Path) -> None:
        generate(template_tree, "prod")
        retired = template_tree / "pipelex" / "skills" / "pipelex-retired"
        (retired / "references").mkdir(parents=True)
        (retired / "SKILL.md").write_text("a skill whose template was removed\n", encoding="utf-8")
        (retired / "references" / "branch.md").write_text("its reference\n", encoding="utf-8")
        assert check_freshness(template_tree, "prod") == 1

        generate(template_tree, "prod")
        assert not retired.exists()
        assert (template_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md").is_file()
        assert check_freshness(template_tree, "prod") == 0

    def test_a_target_at_the_repository_root_is_never_pruned(self, template_tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """The root holds every source beside the output, so a leftover there is reported with the
        cure that works, deleting it, and the build removes nothing."""
        (template_tree / "targets" / "prod.toml").write_text('[plugin]\nname = "pipelex"\nversion = "1.0.0"\nsource = "./"\n')
        generate(template_tree, "prod")
        assert check_freshness(template_tree, "prod") == 0
        leftover = template_tree / "skills" / "pipelex-retired" / "SKILL.md"
        leftover.parent.mkdir(parents=True)
        leftover.write_text("a skill whose template was removed\n", encoding="utf-8")

        capsys.readouterr()
        assert check_freshness(template_tree, "prod") == 1
        assert "ORPHAN: skills/pipelex-retired/SKILL.md (no template produces it: delete it" in capsys.readouterr().out
        generate(template_tree, "prod")
        assert leftover.is_file(), "the build pruned the repository root"

    def test_a_template_leaked_into_mcp_is_reported_and_never_deleted(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """A `.j2` in a target is a source written in the wrong place, maybe somebody's work, so the
        check names it wherever it is, `mcp/` included, and the build leaves it for its author to move."""
        tree = _create_codex_tree(tmp_path)
        generate(tree, "all")
        leaked = tree / "pipelex-vibe" / "mcp" / "vibe-mcp.toml.j2"
        leaked.write_text("[[mcp_servers]]\n", encoding="utf-8")

        capsys.readouterr()
        assert check_freshness(tree, "all") == 1
        assert "LEAKED TEMPLATE: pipelex-vibe/mcp/vibe-mcp.toml.j2 (a template belongs under templates/: move it there, or delete it)" in (
            capsys.readouterr().out
        )
        generate(tree, "all")
        assert leaked.is_file(), "the build deleted a template"
        assert check_freshness(tree, "all") == 1

    def test_a_file_git_ignores_is_neither_reported_nor_removed(self, template_tree: Path) -> None:
        """What git ignores never ships, so it is not the build's: Finder's `.DS_Store` is the usual one."""
        git = shutil.which("git")
        if git is None:
            pytest.skip("no git on the PATH")
        subprocess.run([git, "init", "-q", str(template_tree)], check=True)
        (template_tree / ".gitignore").write_text(".DS_Store\n", encoding="utf-8")
        generate(template_tree, "prod")
        junk = template_tree / "pipelex" / "skills" / ".DS_Store"
        junk.write_bytes(b"\x00\x00\x00\x01Bud1")
        stray = template_tree / "pipelex" / "skills" / "stray.md"
        stray.write_text("not ignored\n", encoding="utf-8")
        assert orphaned_outputs(
            template_tree,
            template_tree / "pipelex",
            build_target(template_tree, load_target_config(template_tree / "targets", "prod"), dry_run=True).produced,
        ) == [stray]

        generate(template_tree, "prod")
        assert junk.is_file(), "the build deleted a file git ignores"
        assert not stray.exists()
        assert check_freshness(template_tree, "prod") == 0


class TestCodexDiscoveryMarketplace:
    """Tests for the .agents/plugins/marketplace.json sync (the file Codex
    reads when resolving `codex plugin marketplace add Pipelex/pipelex-plugins`)."""

    def test_render_returns_none_when_source_absent(self, tmp_path: Path) -> None:
        assert render_codex_discovery_marketplace(tmp_path) is None

    def test_render_returns_content_when_source_present(self, tmp_path: Path) -> None:
        source_path = tmp_path / CODEX_DISCOVERY_MARKETPLACE_SRC
        source_path.parent.mkdir(parents=True)
        canonical = '{"name": "pipelex-plugins", "plugins": []}\n'
        source_path.write_text(canonical, encoding="utf-8")
        assert render_codex_discovery_marketplace(tmp_path) == canonical

    def test_generate_writes_discovery_when_source_present(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        source_path = tree / CODEX_DISCOVERY_MARKETPLACE_SRC
        source_path.parent.mkdir(parents=True)
        canonical = '{"name": "pipelex-plugins", "plugins": [{"name": "pipelex"}]}\n'
        source_path.write_text(canonical, encoding="utf-8")

        assert generate(tree, "codex") == 0
        synced = tree / CODEX_DISCOVERY_MARKETPLACE_DST
        assert synced.is_file()
        assert synced.read_text(encoding="utf-8") == canonical

    def test_generate_skips_discovery_when_source_absent(self, template_tree: Path) -> None:
        generate(template_tree, "prod")
        assert not (template_tree / CODEX_DISCOVERY_MARKETPLACE_DST).exists()

    def test_check_freshness_detects_missing_discovery(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        source_path = tree / CODEX_DISCOVERY_MARKETPLACE_SRC
        source_path.parent.mkdir(parents=True)
        source_path.write_text('{"name": "pipelex-plugins", "plugins": []}\n', encoding="utf-8")
        generate(tree, "codex")
        (tree / CODEX_DISCOVERY_MARKETPLACE_DST).unlink()
        assert check_freshness(tree, "codex") == 1

    def test_check_freshness_detects_stale_discovery(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        source_path = tree / CODEX_DISCOVERY_MARKETPLACE_SRC
        source_path.parent.mkdir(parents=True)
        source_path.write_text('{"name": "pipelex-plugins", "plugins": []}\n', encoding="utf-8")
        generate(tree, "codex")
        (tree / CODEX_DISCOVERY_MARKETPLACE_DST).write_text('{"name": "stale", "plugins": []}\n', encoding="utf-8")
        assert check_freshness(tree, "codex") == 1


class TestTargetConfig:
    def test_platform_default_is_claude(self) -> None:
        config = TargetConfig(
            name="test",
            plugin_name="test",
            plugin_version="1.0.0",
            plugin_description="",
            source="test/",
            template_vars={},
        )
        assert config.platform == "claude"
        assert config.has_plugin_manifest

    def test_platform_codex(self) -> None:
        config = TargetConfig(
            name="test",
            plugin_name="test",
            plugin_version="1.0.0",
            plugin_description="",
            source="test/",
            template_vars={"platform": "codex"},
        )
        assert config.platform == "codex"
        assert config.has_plugin_manifest

    def test_platform_mistral_vibe_has_no_manifest(self) -> None:
        config = TargetConfig(
            name="test",
            plugin_name="test",
            plugin_version="1.0.0",
            plugin_description="",
            source="test/",
            template_vars={"platform": "mistral-vibe"},
        )
        assert config.platform == "mistral-vibe"
        assert not config.has_plugin_manifest

    def test_load_codex_target_config(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "codex")
        assert config.platform == "codex"
        assert config.plugin_name == "pipelex"
        assert config.source == "pipelex-codex/"

    def test_load_mistral_vibe_target_config(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "mistral-vibe")
        assert config.platform == "mistral-vibe"
        assert config.plugin_name == "pipelex-vibe"
        assert config.include_skills is None

    REPO_ROOT = Path(__file__).parents[2]
    DEV_OVERRIDE = '\n[vars.mcp_server]\ncommand = "node"\nargs = ["../pipelex-mcp/dist/local/main.js"]\n'

    def test_the_dev_override_keeps_the_credential_wiring(self, tmp_path: Path) -> None:
        """The override `docs/build-targets.md` advertises sets `command` and `args` alone.

        The target's table used to replace the defaults' whole, dropping `env_vars` and
        `user_config`: the Claude manifest lost its `userConfig` and its launcher, and the hook and
        the launcher their credential promotion, with every check green. It merges now, and the real
        templates render the whole wiring around the local command.
        """
        targets = tmp_path / "targets"
        shutil.copytree(self.REPO_ROOT / "targets", targets)
        with (targets / "prod.toml").open("a", encoding="utf-8") as prod_toml:
            prod_toml.write(self.DEV_OVERRIDE)

        defaults_server = load_defaults(self.REPO_ROOT / "targets")["mcp_server"]
        assert isinstance(defaults_server, dict)
        config = load_target_config(targets, "prod")
        assert config.template_vars["mcp_server"] == {**defaults_server, "command": "node", "args": ["../pipelex-mcp/dist/local/main.js"]}

        manifest = make_plugin_json(self.REPO_ROOT, config)
        assert manifest["userConfig"] == defaults_server["user_config"]
        assert manifest["mcpServers"] == {
            "pipelex": {
                "type": "stdio",
                "command": "${CLAUDE_PLUGIN_ROOT}/hooks/launch-pipelex-mcp.sh",
                "args": [],
                "env": {"PIPELEX_PLUGIN_API_KEY": "${user_config.api_key}", "PIPELEX_PLUGIN_BASE_URL": "${user_config.base_url}"},
            }
        }
        rendered = render_templates(self.REPO_ROOT / "templates", self.REPO_ROOT, config.template_vars, include_skills=[], target_name="prod")
        launcher = rendered[self.REPO_ROOT / "hooks" / "launch-pipelex-mcp.sh"]
        hook = rendered[self.REPO_ROOT / "hooks" / "check-mthds.sh"]
        for key in ("API_KEY", "BASE_URL"):
            assert f'export PIPELEX_{key}="$PIPELEX_PLUGIN_{key}"' in launcher
            assert f'export PIPELEX_{key}="$CLAUDE_PLUGIN_OPTION_{key}"' in hook
        assert launcher.rstrip().endswith('exec node "../pipelex-mcp/dist/local/main.js"')

    def test_a_nested_table_merges_an_array_replaces_and_no_target_aliases_another(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        (tree / "targets" / "prod.toml").write_text(
            '[plugin]\nname = "pipelex"\nversion = "1.0.0"\nsource = "pipelex/"\n\n'
            '[vars.mcp_server]\nenv_vars = ["PIPELEX_API_KEY"]\n\n[vars.mcp_server.user_config.api_key]\ntitle = "Key"\n'
        )
        defaults = load_defaults(tree / "targets")
        prod = load_target_config(tree / "targets", "prod", defaults)
        codex = load_target_config(tree / "targets", "codex", defaults)

        prod_server = prod.template_vars["mcp_server"]
        assert isinstance(prod_server, dict)
        assert prod_server["env_vars"] == ["PIPELEX_API_KEY"], "an array replaces the default's, never extends it"
        assert prod_server["user_config"] == {
            "api_key": {"type": "string", "title": "Key", "description": "Key.", "sensitive": True},
            "base_url": {"type": "string", "title": "Pipelex API base URL", "description": "URL."},
        }
        assert codex.template_vars["mcp_server"] == defaults["mcp_server"]
        assert defaults["mcp_server"] == load_defaults(tree / "targets")["mcp_server"], "a target's merge wrote into the shared defaults"


class TestPluginManifests:
    def test_codex_frontmatter_has_no_allowed_tools(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        results = render_templates(tree / "templates", tree, {**DEFAULT_VARS, "platform": "codex"})
        rendered = results[tree / "skills" / "pipelex-test" / "SKILL.md"]
        assert "allowed-tools" not in rendered

    def test_claude_frontmatter_has_allowed_tools(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        results = render_templates(tree / "templates", tree, {**DEFAULT_VARS, "platform": "claude"})
        assert "allowed-tools" in results[tree / "skills" / "pipelex-test" / "SKILL.md"]

    def test_codex_plugin_json_uses_codex_base(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "codex")
        plugin_json = make_plugin_json(tree, config)
        assert plugin_json["name"] == "pipelex"
        assert plugin_json["version"] == "1.0.0"
        assert "skills" in plugin_json
        assert "interface" in plugin_json

    def test_claude_plugin_json_uses_claude_base(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "prod")
        plugin_json = make_plugin_json(tree, config)
        assert plugin_json["name"] == "pipelex"
        assert "skills" not in plugin_json
        assert "interface" not in plugin_json

    def test_claude_plugin_json_declares_mcp_server_with_user_config(self, tmp_path: Path) -> None:
        """With a user_config block, the Claude manifest declares userConfig
        (prompted at enable time) and routes the MCP spawn through the
        launch-pipelex-mcp.sh wrapper, injecting each option as
        PIPELEX_PLUGIN_<KEY> via `${user_config.*}` substitution — the only
        credential channel on GUI launches (Claude Desktop has no shell env).

        The indirection is deliberate: injecting straight into PIPELEX_* lets an
        unfilled option substitute to "" and shadow a working shell credential,
        which surfaces as a config-class "Unauthorized" that hard-stops every
        MCP-backed skill (regressed in 0.3.1, restored here)."""
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "prod")
        plugin_json = make_plugin_json(tree, config)
        assert plugin_json["userConfig"] == {
            "api_key": {"type": "string", "title": "Pipelex API key", "description": "Key.", "sensitive": True},
            "base_url": {"type": "string", "title": "Pipelex API base URL", "description": "URL."},
        }
        assert plugin_json["mcpServers"] == {
            "pipelex": {
                "type": "stdio",
                "command": "${CLAUDE_PLUGIN_ROOT}/hooks/launch-pipelex-mcp.sh",
                "args": [],
                "env": {
                    "PIPELEX_PLUGIN_API_KEY": "${user_config.api_key}",
                    "PIPELEX_PLUGIN_BASE_URL": "${user_config.base_url}",
                },
            }
        }

    def test_claude_plugin_json_without_user_config_spawns_directly(self, tmp_path: Path) -> None:
        """Without a user_config block, the Claude manifest spawns the workshop
        command directly — Claude Code passes the full shell env to the spawned
        server (verified in live plugin-dir sessions)."""
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "prod")
        mcp_server = config.template_vars["mcp_server"]
        assert isinstance(mcp_server, dict)
        mcp_server.pop("user_config")
        plugin_json = make_plugin_json(tree, config)
        assert "userConfig" not in plugin_json
        assert plugin_json["mcpServers"] == {
            "pipelex": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@pipelex/mcp@latest"],
            }
        }

    def test_codex_plugin_json_declares_mcp_server_command(self, tmp_path: Path) -> None:
        """The Codex manifest declares the launcher as a bare command (stdio is
        picked structurally, no `type` key) and forwards the named env vars —
        Codex spawns MCP servers with a whitelist env, so PIPELEX_API_KEY only
        reaches the workshop through `env_vars` (verified against Codex 0.144.5)."""
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "codex")
        plugin_json = make_plugin_json(tree, config)
        assert plugin_json["mcpServers"] == {
            "pipelex": {
                "command": "npx",
                "args": ["-y", "@pipelex/mcp@latest"],
                "env_vars": ["PIPELEX_API_KEY", "PIPELEX_BASE_URL"],
            }
        }

    def test_claude_plugin_json_without_mcp_server_skips_entry(self, template_tree: Path) -> None:
        """A tree that defines no mcp_server block gets no mcpServers key."""
        config = load_target_config(template_tree / "targets", "prod")
        plugin_json = make_plugin_json(template_tree, config)
        assert "mcpServers" not in plugin_json

    def test_build_codex_target_writes_codex_plugin_dir(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "codex")
        result = build_target(tree, config)
        codex_manifest = tree / "pipelex-codex" / ".codex-plugin" / "plugin.json"
        claude_manifest = tree / "pipelex-codex" / ".claude-plugin" / "plugin.json"
        assert codex_manifest in result.files
        assert claude_manifest not in result.files
        plugin_data = json.loads(result.files[codex_manifest])
        assert plugin_data["name"] == "pipelex"
        assert "interface" in plugin_data

    def test_build_mistral_vibe_target_writes_no_plugin_manifest(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "mistral-vibe")
        result = build_target(tree, config)
        claude_manifest = tree / "pipelex-vibe" / ".claude-plugin" / "plugin.json"
        codex_manifest = tree / "pipelex-vibe" / ".codex-plugin" / "plugin.json"
        assert claude_manifest not in result.files
        assert codex_manifest not in result.files
        assert any(path.name == "writing-mthds.md" for path in result.files)

    def test_build_claude_target_writes_claude_plugin_dir(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "prod")
        result = build_target(tree, config)
        claude_manifest = tree / "pipelex" / ".claude-plugin" / "plugin.json"
        codex_manifest = tree / "pipelex" / ".codex-plugin" / "plugin.json"
        assert claude_manifest in result.files
        assert codex_manifest not in result.files


class TestSkillFailureDiscipline:
    """The disk-mutating MCP-backed skills must instruct a recovery path when
    the post-write validation yields no verdict: the Step-1 in-memory content
    is the recovery source (no git/backup machinery — the bundle dir is not
    guaranteed to be a git repo). Pins the real templates, not fixtures."""

    REPO_TEMPLATES = Path(__file__).parents[2] / "templates" / "skills"

    def test_organize_restores_original_layout_on_failed_confirmation(self) -> None:
        body = (self.REPO_TEMPLATES / "pipelex-organize" / "SKILL.md.j2").read_text(encoding="utf-8")
        assert "restore the original layout" in body

    def test_edit_offers_restore_on_no_verdict(self) -> None:
        body = (self.REPO_TEMPLATES / "pipelex-edit" / "SKILL.md.j2").read_text(encoding="utf-8")
        assert "applied but **unproven**" in body

    @staticmethod
    def _render_mcp_skills(target_name: str) -> tuple[dict[str, str], str]:
        """The MCP-backed skills' rendered bodies for a target, and its rendered `shared/credentials.md`."""
        repo_root = Path(__file__).parents[2]
        config = load_target_config(repo_root / "targets", target_name)
        rendered = render_templates(
            repo_root / "templates",
            repo_root,
            config.template_vars,
            include_skills=list(MCP_SKILLS),
            target_name=config.name,
        )
        bodies = {skill: next(content for path, content in rendered.items() if path.match(f"skills/{skill}/SKILL.md")) for skill in MCP_SKILLS}
        credentials = next(content for path, content in rendered.items() if path.match("skills/shared/credentials.md"))
        return bodies, credentials

    @pytest.mark.parametrize(
        "target_name, manifest_spawns",
        [
            ("prod", True),
            ("codex", True),
            ("mistral-vibe", False),
        ],
    )
    def test_absent_tools_stop_message_matches_platform(self, target_name: str, manifest_spawns: bool) -> None:
        """The MCP-absent STOP stays in every MCP-backed skill and sends the model to
        `shared/credentials.md` for what to tell the user (box F of the size diet).
        That message must quote the real launcher command and, on Vibe (no plugin
        manifest, no auto-spawn), point at the shipped fragment instead of a manifest
        spawn. Renders the real templates with real target vars."""
        bodies, credentials = self._render_mcp_skills(target_name)
        for skill, body in bodies.items():
            assert "the Pipelex MCP server isn't connected: STOP" in body, f"{target_name}/{skill}: the absent-tool stop left the skill"
            assert "(../shared/credentials.md#the-tool-is-absent)" in body, f"{target_name}/{skill}: the stop must point at the connection reference"
        assert "npx -y @pipelex/mcp@latest" in credentials, f"{target_name}: stale launcher command in the connection message"
        if manifest_spawns:
            assert "plugin manifest spawns" in credentials, f"{target_name}: missing manifest-spawn diagnostic"
        else:
            assert "plugin manifest spawns" not in credentials, f"{target_name}: Vibe has no manifest spawn"
            assert "`mcp/vibe-mcp.toml`" in credentials, f"{target_name}: Vibe's message must point at the shipped MCP fragment"
            assert "`env` table" in credentials, f"{target_name}: Vibe's message must say where the key goes"
            assert "to the end of `~/.vibe/config.toml`" in credentials, f"{target_name}: Vibe's message must say to append the entry"
            assert "`mcp_servers = []`" in credentials, f"{target_name}: Vibe's message must say to delete the inline empty array"

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_credential_sentence_names_the_platform_channel(self, target_name: str) -> None:
        """Where the workshop gets its API key from differs per harness, so the
        sentence differs per harness — it used to be shared by Claude and Codex.
        It lives in `shared/credentials.md`, read when a `config` error is about
        the key, and no skill restates it.

        On Claude the canonical channel is the plugin configuration, whose value
        the launcher promotes into the spawn environment, and on Claude Desktop
        it is the only channel: a GUI launch carries no shell environment, so an
        agent that advises exporting a shell variable there advises something
        that cannot work. Codex forwards the session environment by name. Vibe
        spawns with a minimal environment and reads the server entry's own `env`
        table."""
        bodies, body = self._render_mcp_skills(target_name)
        for skill, skill_body in bodies.items():
            assert "(../shared/credentials.md#where-the-key-comes-from)" in skill_body, (
                f"{target_name}/{skill}: the config stop must point at the key reference"
            )
            assert "The server authenticates to the API with" not in skill_body, (
                f"{target_name}/{skill}: the credential sentence lives in shared/credentials.md"
            )
        session_env_claim = "from the session environment — the same variable the plugin's validation hook documents"
        if target_name == "prod":
            assert "from the **plugin configuration**" in body, f"{target_name}: Claude's canonical channel is the plugin configuration"
            assert "OS keychain" in body, f"{target_name}: say where the configured key is kept"
            assert "Claude Desktop" in body, f"{target_name}: name the host where the shell environment does not exist"
            assert session_env_claim not in body, f"{target_name}: the session environment is Claude's fallback, not its channel"
        elif target_name == "codex":
            assert session_env_claim in body, f"{target_name}: Codex forwards the session environment"
            assert "plugin configuration" not in body, f"{target_name}: Codex has no plugin configuration prompt"
        else:
            assert "`env` table in `~/.vibe/config.toml`" in body, f"{target_name}: Vibe reads the server entry's own env table"
            assert "never from the session environment" in body, f"{target_name}: Vibe passes no shell env to the server"
            assert "plugin configuration" not in body, f"{target_name}: Vibe has no plugin manifest to configure"


class TestSharedSkillIncludes:
    """Box J of `wip/plugin-skills-gaps/design.md`: the blocks the MCP-backed
    skills used to copy live in `templates/skills/shared/` and are included.

    The cost of the copies was concrete — the wrong Claude credential sentence
    (`L-260912-65d6fc`) sat in five templates — so these tests pin the property
    that made it expensive: each shared block has exactly one source. A new
    skill that pastes a block instead of including it fails here."""

    REPO_TEMPLATES = Path(__file__).parents[2] / "templates"

    # A sentence from each shared block, and the include that owns it.
    SHARED_BLOCK_OWNERS: ClassVar[dict[str, str]] = {
        "The Pipelex MCP server isn't connected —": "skills/shared/credentials.md.j2",
        "The server authenticates to the API with": "skills/shared/credentials.md.j2",
        "the Pipelex MCP server isn't connected: STOP": "skills/shared/mcp-requirements.md.j2",
        "Prefer the path form ": "skills/shared/validate-call.md.j2",
        "now stale and offer": "skills/shared/stale-types-notice.md.j2",
        "`PipeFunc` is experimental": "skills/shared/pipefunc-warning.md.j2",
        "**The saved method does not have this change.**": "skills/shared/saved-copy-notice.md.j2",
        "One search over the link files": "skills/shared/catalog-id-bridge.md.j2",
        "read [the catalog-id reference](../shared/catalog-id.md) before reading any file": "skills/shared/catalog-id-pointer.md.j2",
        "a `setup.py` or a `requirements.txt` at or above the working directory": "skills/shared/project-root.md.j2",
        "stands for the directory holding this `SKILL.md`": "skills/shared/skill-dir.md.j2",
        "relative to that file's directory, say so, and check again": "skills/shared/git-ignore.md.j2",
        "so one still not ignored is not written until the user says so": "skills/shared/git-ignore.md.j2",
    }

    @pytest.mark.parametrize("sentence, owner", sorted(SHARED_BLOCK_OWNERS.items()))
    def test_shared_block_has_exactly_one_source(self, sentence: str, owner: str) -> None:
        carriers = sorted(
            str(path.relative_to(self.REPO_TEMPLATES)) for path in self.REPO_TEMPLATES.rglob("*.j2") if sentence in path.read_text(encoding="utf-8")
        )
        assert carriers == [owner], f"{sentence!r} should live only in {owner}, found in {carriers}"

    def test_the_pipefunc_warning_reaches_the_skills_that_ship_it(self) -> None:
        """An include nothing includes ships nowhere. The partial landed with the
        shared-includes phase and is wired into every skill where a user meets a
        `PipeFunc`: design says it twice — once while the contract is still the
        user's to change, once at delivery — explain says it when it meets one,
        and run says it at step 8, where a failed run is routed and a `PipeFunc`
        is named as a suspect for a failure nothing upstream could have caught.

        Run was the one that shipped late, because `pipelex-run` did not exist
        when the partial landed, and in the meantime its table restated the
        warning in its own words — the same drift this test caught in the
        authoring reference, where two copies of one sentence were free to part."""
        include = "skills/shared/pipefunc-warning.md.j2"
        design = (self.REPO_TEMPLATES / "skills" / "pipelex-design" / "SKILL.md.j2").read_text(encoding="utf-8")
        explain = (self.REPO_TEMPLATES / "skills" / "pipelex-explain" / "SKILL.md.j2").read_text(encoding="utf-8")
        run = (self.REPO_TEMPLATES / "skills" / "pipelex-run" / "SKILL.md.j2").read_text(encoding="utf-8")
        assert design.count(include) == 2, "design warns in the contract line and again at delivery"
        assert include in explain
        assert include in run

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_the_language_reference_carries_the_same_warning(self, target_name: str) -> None:
        """The language reference is where a designer reads what a PipeFunc is; a
        warning absent there is a warning the author never meets. It used to be a
        static asset of `pipelex-design`, copied verbatim and never rendered, so it
        held a copy of the sentence that only this test kept in step. It is now a
        rendered shared reference, so it includes the partial like any skill, and
        the rendered file is held to the partial's own body."""
        reference_template = (self.REPO_TEMPLATES / "skills" / "shared" / "writing-mthds.md.j2").read_text(encoding="utf-8")
        assert 'include "skills/shared/pipefunc-warning.md.j2"' in reference_template
        partial = (self.REPO_TEMPLATES / "skills" / "shared" / "pipefunc-warning.md.j2").read_text(encoding="utf-8")
        warning = re.sub(r"\{#.*?#\}", "", partial, flags=re.DOTALL).strip()
        assert warning, "the partial rendered to nothing — its comment wrapper moved"
        repo_root = self.REPO_TEMPLATES.parent
        config = load_target_config(repo_root / "targets", target_name)
        rendered = render_templates(self.REPO_TEMPLATES, repo_root, config.template_vars, include_skills=[], target_name=config.name)
        reference = next(content for path, content in rendered.items() if path.match("skills/shared/writing-mthds.md"))
        assert warning in reference, f"{target_name}: the rendered language reference lost the PipeFunc warning"

    def test_no_skill_restates_the_sandbox_beside_a_pipefunc(self) -> None:
        """The one-source test proves a block has one source; it is blind to a
        restatement, which is how `pipelex-run`'s failure table came to say "its
        Python runs in a network-blocked sandbox" in its own words for a phase,
        beside no include at all — the skill was written against a `dev` that
        had no partial to include. The sandbox is the partial's fact: a skill
        template that names `PipeFunc` and the sandbox on one line is restating
        it, whatever the words, and the fact reaches a skill through the include
        or not at all. `pipelex-inputs` names the sandbox in its by-address
        refusal reading, beside in-process Python and never beside `PipeFunc`,
        and stays clear."""
        offenders = [
            f"{path.relative_to(self.REPO_TEMPLATES)}:{number}"
            for path in sorted((self.REPO_TEMPLATES / "skills").glob("*/SKILL.md.j2"))
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
            if "PipeFunc" in line and "sandbox" in line
        ]
        assert offenders == [], f"the sandbox fact reaches a skill through the include or not at all: {offenders}"

    @pytest.mark.parametrize("skill", ["pipelex-inputs", "pipelex-lab", "pipelex-run"])
    def test_the_ignore_procedure_reaches_every_skill_that_writes_the_user_s_data(self, skill: str) -> None:
        """Three skills write what holds the user's data into a project that is usually a
        repository: `pipelex-inputs` the copies of the user's files, `pipelex-lab` a case of
        them and its key, and `pipelex-run` the saved output, which carries the facts the run
        extracted from them. Each keeps it out of version control with the same procedure,
        and each used to word it for itself until run needed it too. The partial is the one
        source, and each skill names only what it checks and the entry it writes."""
        body = (self.REPO_TEMPLATES / "skills" / skill / "SKILL.md.j2").read_text(encoding="utf-8")
        assert body.count('include "skills/shared/git-ignore.md.j2"') == 1
        assert "{% set git_ignore_paths %}" in body
        assert "{% set git_ignore_entry %}" in body

    def test_no_skill_restates_the_ignore_check(self) -> None:
        """The one-source test is blind to a paraphrase: a fourth skill that words the check
        for itself passes it while dropping the tracked-path guard. `git check-ignore` reaches
        a skill template through the partial or not at all; the scaffold's scripts run it
        themselves and are not templates."""
        offenders = [
            str(path.relative_to(self.REPO_TEMPLATES))
            for path in sorted((self.REPO_TEMPLATES / "skills").glob("*/SKILL.md.j2"))
            if "check-ignore" in path.read_text(encoding="utf-8")
        ]
        assert offenders == [], f"the ignore check reaches a skill through skills/shared/git-ignore.md.j2 alone: {offenders}"

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_the_submission_convention_names_the_workshop_s_path_containment(self, target_name: str) -> None:
        """`L-260923-019e50`: the local workshop refuses a `{ path }` item that resolves
        outside its own working directory, an absolute one included (`pipelex-mcp`,
        `src/local/files.ts`). The include used to say "pass an absolute one" as though
        that were enough, so a session launched below or beside the bundle met the
        refusal with no cure. Every skill that submits a bundle now names the refusal
        and the relaunch that cures it. All but the catalog keep the inline fallback: a
        save is the one submission the inline form leaves unlinked."""
        includers = sorted(
            path.parent.name
            for path in (self.REPO_TEMPLATES / "skills").glob("*/SKILL.md.j2")
            if 'include "skills/shared/validate-call.md.j2"' in path.read_text(encoding="utf-8")
        )
        assert "pipelex-catalog" in includers
        repo_root = self.REPO_TEMPLATES.parent
        config = load_target_config(repo_root / "targets", target_name)
        rendered = render_templates(self.REPO_TEMPLATES, repo_root, config.template_vars, include_skills=includers, target_name=config.name)
        fallback = "is the fallback, and the only form the hosted console accepts."
        for skill in includers:
            body = next(content for path, content in rendered.items() if path.match(f"skills/{skill}/SKILL.md"))
            assert "The workshop refuses a path outside **its own** working directory" in body, f"{target_name}/{skill}: the refusal is unnamed"
            assert "relaunching the harness from a directory holding the bundle cures that" in body, f"{target_name}/{skill}: the cure is unnamed"
            assert "pass an absolute one" not in body, f"{target_name}/{skill}: an absolute path outside the workshop is refused too"
            if skill == "pipelex-catalog":
                assert fallback not in body, "the save tool is the workshop's alone, and the inline form leaves a save unlinked"
            else:
                assert fallback in body, f"{target_name}/{skill}: the inline fallback is gone"

    @pytest.mark.parametrize("skill", MCP_SKILLS)
    def test_mcp_backed_skill_includes_the_requirements_block(self, skill: str) -> None:
        body = (self.REPO_TEMPLATES / "skills" / skill / "SKILL.md.j2").read_text(encoding="utf-8")
        assert 'include "skills/shared/mcp-requirements.md.j2"' in body

    def test_pipefunc_warning_states_the_sandbox_the_experiment_and_the_risk(self) -> None:
        """Box G: PipeFunc is warned about, never refused. The warning is written
        before any skill includes it, so the later phases only add the include."""
        body = (self.REPO_TEMPLATES / "skills" / "shared" / "pipefunc-warning.md.j2").read_text(encoding="utf-8")
        assert "sandbox with no network access" in body
        assert "still in development" in body
        assert "validates can still fail when it runs" in body


class TestPipelexRunSkill:
    """`pipelex-run` owns the run lifecycle, and the boundary is what these pin.

    A run spends the user's inference credit, so the expensive mistakes are all
    boundary mistakes: preparing inputs here instead of routing, running a
    method that was never validated, re-running a failure to see what happens,
    or losing the run id — the only handle a later session has on the run."""

    REPO_ROOT = Path(__file__).parents[2]
    TEMPLATES = REPO_ROOT / "templates" / "skills"

    @property
    def run_skill(self) -> str:
        return (self.TEMPLATES / "pipelex-run" / "SKILL.md.j2").read_text(encoding="utf-8")

    @property
    def inputs_skill(self) -> str:
        return (self.TEMPLATES / "pipelex-inputs" / "SKILL.md.j2").read_text(encoding="utf-8")

    def test_it_has_two_entries_and_names_them(self) -> None:
        body = self.run_skill
        assert "## Start a run" in body
        assert "## Follow a run" in body

    def test_the_run_id_is_reported_before_anything_else(self) -> None:
        """The id is the only durable handle on the run: a session that loses it
        before the run finishes has paid for a result nobody can fetch."""
        body = self.run_skill
        assert "**Report that id the moment it returns, before anything else.**" in body

    def test_either_target_is_validated_before_credit_is_spent(self) -> None:
        """A scaffold is a *valid* bundle and `mthds_inputs_template` answers validity
        alone, so the template call cannot stand in for validation on the by-id path:
        a stored method with pending signatures would reach the run and burn its
        implemented pipes before stopping at the one that is not."""
        body = self.run_skill
        assert "Prove the target before spending credit" in body
        assert "Never run a method that did not pass." in body
        assert "the same call with `method_id` in place of `files`" in body
        assert "a scaffold is a *valid* bundle" in body

    def test_the_bundle_sweep_excludes_the_artifact_tree(self) -> None:
        """Step 7 saves under `runs/`, an artifact keeps its filename extension, and
        the submission gathers every `.mthds` file beneath the bundle — so without an
        exclusion a method that emits or echoes one submits its own output as source."""
        body = self.run_skill
        assert 'include "skills/shared/validate-call.md.j2"' in body
        assert "validate_call_file_set" not in body, "run submits the shared file set, runs/ exclusion included"
        partial = (self.REPO_ROOT / "templates" / "skills" / "shared" / "validate-call.md.j2").read_text(encoding="utf-8")
        assert "except anything under a `runs/` directory" in partial

    def test_a_refused_dir_is_retried_into_the_default_folder(self) -> None:
        """`dir` is relative to the workshop's own working directory and an absolute
        path is refused before the run is read. Since `@pipelex/mcp` 0.18.0 an omitted
        `dir` saves into `runs/<run_id>/`, not the working directory itself, so the retry
        without it lands where step 7 would have saved, and a completed run must not
        read as a failed save."""
        body = self.run_skill
        assert "Pass `dir` only for a folder the user named, relative to that directory." in body
        assert "refuses a `dir` the user named | call again without it, which saves into `runs/<run_id>/`" in body
        assert "A refused `dir` is not a failed save" in body

    def test_user_values_are_laid_over_a_prepared_set(self) -> None:
        """Restating one input of a filled set is ordinary; without the merge it drops
        every other key and fails the template check as drift."""
        body = self.run_skill
        assert "laid over a current `inputs.prepared.json`" in body
        assert "replace only the keys the user named" in body

    def test_the_worked_example_never_writes_back_over_the_source(self) -> None:
        """The example is the most-copied part of a skill: one that still overwrites
        `inputs.json` destroys the source form this change exists to preserve. The size
        diet moved the worked examples into the strategy references, so every file the
        skill ships is held to it, and to the sentences `L-260922-e01c73` caught still
        saying preparation rewrites `inputs.json`."""
        references = self.REPO_ROOT / "skills" / "pipelex-inputs" / "references"
        texts = {"SKILL.md.j2": self.inputs_skill} | {path.name: path.read_text(encoding="utf-8") for path in sorted(references.glob("*.md"))}
        for name, text in texts.items():
            for retired in (
                "written back over `inputs.json`",
                "rewrites `inputs.json`",
                "is what `inputs.json` holds from then on",
                "rewrites it to",
            ):
                assert retired not in text, f"{name} still says preparation rewrites inputs.json: {retired!r}"
        assert "written to `inputs.prepared.json` beside an unchanged `inputs.json`" in texts["user-data.md"]

    def test_preparation_is_skipped_only_for_values_already_remote(self) -> None:
        """`data:` URLs and inline bytes are not local files but still need uploading,
        so a skip condition phrased as "no local file" blesses a set that
        `/pipelex-run` then refuses."""
        body = self.inputs_skill
        assert "**when every file-ish value is already an `http(s)` URL or a `pipelex-storage://` reference**" in body
        assert "Skip the call for the Template strategy" in body
        assert "or step 5 skipped it because nothing needed uploading" in body
        assert "no input is a local file" not in body
        assert "no value was a local file" not in body

    def test_an_earlier_prepared_file_is_deleted_before_preparing(self) -> None:
        """A skipped, declined or failed preparation writes no prepared file, and one an
        earlier pass left would still be read: `/pipelex-run` hands a not-current one back
        here, which skips again, and takes a current-looking one as run-ready. So the
        deletion comes before the pass-through skip and before the user can decline the
        upload, and after the Template strategy's skip: a template pass prepares nothing,
        and the prepared file may be the only run-ready copy of values it just replaced."""
        body = self.inputs_skill
        delete = body.index("Otherwise **first delete any `inputs.prepared.json` an earlier prepare left in `<output_dir>`**")
        assert body.index("Skip the call for the Template strategy") < delete
        assert delete < body.index("Skip the call too **when every file-ish value is already")
        assert delete < body.index("If the user declines, stop before the call")
        errors = (Path(__file__).parents[2] / "skills" / "pipelex-inputs" / "references" / "prepare-errors.md").read_text(encoding="utf-8")
        assert "the skill's step 5 deleted any earlier one before the call" in errors

    def test_a_list_input_keeps_its_files_in_a_directory_of_its_own(self) -> None:
        """An indexed list item `photo_1.png` is also the copy of a scalar input called
        `photo_1`, a list file kept under its own name `invoice.pdf` is also the copy of
        an input called `invoice`, and a renamed duplicate `shoe_1.jpg` is also a real
        file of that name: each time one file silently replaces another and two values
        upload the same bytes. A directory per list input, its files named by position,
        leaves no name two values can share — and a worked example is what a model
        copies, so none of them may show a list flat under `inputs/`."""
        references = Path(__file__).parents[2] / "skills" / "pipelex-inputs" / "references"
        user_data = (references / "user-data.md").read_text(encoding="utf-8")
        synthetic = (references / "synthetic.md").read_text(encoding="utf-8")
        assert "A list input's files go in a directory named after the input, each named by its position" in user_data
        assert "`<output_dir>/inputs/<input_variable>/1.<ext>`" in synthetic
        for text in (user_data, synthetic):
            assert "`<input_variable>_1.<ext>`" not in text
            assert not re.search(r"\[\s*\"inputs/[^/\"]+\"", text), "a list example puts its files flat under inputs/"

    def test_the_offer_names_whichever_file_the_run_reads(self) -> None:
        """No prepared file is written when nothing needed uploading, so an offer that
        hard-codes `inputs.prepared.json` names a file that is not there."""
        body = self.inputs_skill
        assert "`inputs.prepared.json` where prepare wrote one, `inputs.json` where prepare was skipped" in body

    def test_it_routes_a_failure_and_never_bisects(self) -> None:
        body = self.run_skill
        assert "never bisected" in body or "never bisects" in body
        assert "Per-pipe bisection is not this skill's" in body
        assert "Do not re-run a failed method with altered inputs" in body
        assert "`failure_message` **verbatim**" in body

    def test_a_stuck_run_is_named_rather_than_waited_on(self) -> None:
        """A durable run sitting in RUNNING with no error may be a workflow task that
        failed out of sight — waiting on one cost a project hours — but the status cannot
        tell it from a slow run, so the skill stops waiting and reports rather than diagnoses."""
        body = self.run_skill
        assert "a workflow task that failed out of sight" in body
        assert "stop waiting" in body

    def test_it_prepares_nothing_and_routes_instead(self) -> None:
        body = self.run_skill
        assert "Do not prepare inputs here." in body
        assert "inputs.prepared.json" in body, "the run reads the prepared file; it does not write one"

    def test_every_completed_run_is_saved_whole(self) -> None:
        """A run whose output references no stored file used to leave nothing on disk,
        and a model asked for the results as files retyped them (the proof lab of
        2026-09-24). `mthds_download_artifacts` now writes the whole output as
        `main_stuff.json` into `runs/<run_id>/` by default, so step 7 saves every
        completed run with the run id alone and passes no `dir` of its own."""
        body = self.run_skill
        assert "save the run, file or no file" in body
        assert "with the run id alone writes the whole output as `main_stuff.json` into `runs/<run_id>/`" in body
        assert 'dir: "runs/<run_id>"' not in body, "the default folder is the tool's; the skill no longer passes it"
        assert "report the paths the tool returns" in body
        assert '**"save run X"**' in body
        assert "download the files from run X" not in body

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_the_run_tools_left_pipelex_inputs(self, target_name: str) -> None:
        """The four run tools are pipelex-run's. A rendered pipelex-inputs that
        still declares them would let it run a method behind the hand-off."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-inputs", "pipelex-run"],
            target_name=config.name,
        )
        inputs = next(content for path, content in rendered.items() if path.match("skills/pipelex-inputs/SKILL.md"))
        run = next(content for path, content in rendered.items() if path.match("skills/pipelex-run/SKILL.md"))
        for tool in ("mthds_run", "mthds_run_status", "mthds_run_results", "mthds_download_artifacts"):
            assert f"mcp__plugin_pipelex_pipelex__{tool}" not in inputs, f"{target_name}: pipelex-inputs still declares {tool}"
        assert "/pipelex-run" in inputs, f"{target_name}: pipelex-inputs must hand the run over"
        if target_name == "prod":
            for tool in ("mthds_run", "mthds_run_status", "mthds_run_results", "mthds_download_artifacts"):
                assert f"mcp__plugin_pipelex_pipelex__{tool}" in run, f"{target_name}: pipelex-run must declare {tool}"

    def test_prepare_writes_a_separate_file_and_never_rewrites_the_source(self) -> None:
        """The in-place rewrite destroyed the source form: the storage references
        are scoped to one org on one plane, so the committed file was unusable by
        a teammate and after a move between planes."""
        body = self.inputs_skill
        assert "leave `inputs.json` exactly as it is" in body
        assert "prepare never rewrites it" in body
        assert "no envelope, no hash and no sidecar" in body
        assert "add `inputs.prepared.json` to the nearest `.gitignore`" in body

    def test_design_points_at_the_run_without_running(self) -> None:
        design = (self.TEMPLATES / "pipelex-design" / "SKILL.md.j2").read_text(encoding="utf-8")
        assert "`/pipelex-run` runs the method" in design
        assert "mcp__plugin_pipelex_pipelex__mthds_run" not in design


class TestPipelexCatalogSkill:
    """`pipelex-catalog` owns every gesture between a bundle directory and the
    organization's catalog, and the expensive mistakes are all irreversible ones.

    An update rewrites the whole catalog row with no earlier version kept, and
    every caller of the id runs the new content from its next call — so a save
    made on the skill's own initiative, one made over a change it never saw, or
    one carrying a `.py` file that is not the method's cannot be taken back. The
    pull is the same hazard pointing the other way: it writes into a directory
    the user is standing in."""

    REPO_ROOT = Path(__file__).parents[2]
    TEMPLATES = REPO_ROOT / "templates" / "skills"

    @property
    def catalog_skill(self) -> str:
        return (self.TEMPLATES / "pipelex-catalog" / "SKILL.md.j2").read_text(encoding="utf-8")

    def catalog_reference(self, name: str) -> str:
        """A branch the size diet moved out of `SKILL.md`, read on its condition."""
        return (self.REPO_ROOT / "skills" / "pipelex-catalog" / "references" / name).read_text(encoding="utf-8")

    def test_it_has_the_three_gestures_and_names_them(self) -> None:
        body = self.catalog_skill
        assert "## List and find" in body
        assert "## Save" in body
        assert "## Pull" in body

    def test_the_update_line_says_an_update_is_a_deployment(self) -> None:
        """Box Q's one non-optional sentence. An update reaches production call
        sites on their next call, and the catalog keeps no earlier version, so a
        user who was not told that cannot have consented to it."""
        body = self.catalog_skill
        assert "This is a deployment: every caller of that id, a production call site included, runs the new content from its next call." in body
        assert "the user's request is the consent" in body

    def test_it_never_saves_on_its_own_initiative(self) -> None:
        body = self.catalog_skill
        assert "**A save is never proposed as a side effect of other work**" in body
        assert "never saves on its own initiative" in body, "the description must carry it too — that is what a host reads before the body"

    def test_it_does_not_validate_on_the_way_to_a_save(self) -> None:
        """`mthds_save_method` reads, validates and saves in one call precisely so
        that the saved bytes are provably the validated ones. A skill that took its
        own verdict first would read the files twice and pay twice for it."""
        body = self.catalog_skill
        assert "Never call it on the way to a save" in body
        assert "reads the files, validates them and saves those same bytes in one call" in body

    def test_an_invalid_bundle_is_a_verdict_and_not_an_error(self) -> None:
        body = self.catalog_skill
        assert "is a **produced verdict**, not an error" in body
        assert "A **valid bundle with pending signatures is saved**" in body

    def test_the_bundle_sweep_excludes_the_artifact_tree(self) -> None:
        """`/pipelex-run` saves artifacts under `runs/` and an artifact keeps its
        extension, so a method that emits or echoes a `.mthds` file would otherwise
        have its own output saved to the catalog as part of its source."""
        body = self.catalog_skill
        assert 'include "skills/shared/validate-call.md.j2"' in body
        assert "validate_call_file_set" not in body, "catalog submits the shared file set, runs/ exclusion included"
        partial = (self.REPO_ROOT / "templates" / "skills" / "shared" / "validate-call.md.j2").read_text(encoding="utf-8")
        assert "except anything under a `runs/` directory" in partial
        assert "root file first" in body

    def test_a_save_takes_the_path_form_and_an_unlinkable_one_waits_for_a_yes(self) -> None:
        """The workshop writes `pipelex-method.json` only beside a `{ path }` root file
        (`pipelex-mcp`, `src/capabilities/catalog-write.ts`, `linkDirectoryOf`), and
        `link_dir` is bounded by the same working directory as a path is. So a method
        created from inline files is linked to nothing, and the directory's next save
        creates a second one, which only an admin can delete. The skill says it through
        the include's parameter rather than a pasted variant of the convention."""
        body = self.catalog_skill
        assert "{% set validate_call_inline %}" in body
        assert "**a save takes the path form**" in body
        assert "say that this session cannot write the link and which of the two that costs, and save inline only on the user's yes" in body
        assert "Never pass `link_dir`" in body
        # The update arm too: an inline update leaves the link's `synced_updated_at` behind the catalog, so the
        # directory's next save is refused at `expected_updated_at`, a conflict with this session's own save.
        assert "a method updated that way keeps the link's old sync time" in body

    def test_a_conflict_with_this_session_s_own_save_is_not_called_somebody_else_s(self) -> None:
        """A save whose link write failed, an inline one always, leaves the link's sync time behind the
        catalog, so the next save from the directory is refused as though somebody had saved over the
        method. The reference recognises the case by the stored `updated_at` this session's own save
        reported, says so, and carries the save on with that `updated_at` as the expectation; step 5
        names the cure for the stale link, a pull into the same directory, rather than a bare save again."""
        conflict = self.catalog_reference("conflict.md")
        own = conflict.split("**First, is it this session's own save?**", 1)[1].split("\n\n", 1)[0]
        assert "never say that somebody saved over the method" in own
        assert "with `expected_updated_at` set to that stored `updated_at`" in own
        assert "relaunched from a directory holding the bundle" in own
        assert conflict.index("**First, is it this session's own save?**") < conflict.index("somebody saved over this method")
        body = self.catalog_skill
        assert "unless it finds this session's own save, give the user both timestamps" in body
        assert "a pull of this method into this directory rewrites the link alone while the files still match what was saved" in body
        assert "fix whatever blocked the write and save again" not in body

    def test_python_is_chosen_and_never_swept(self) -> None:
        """The workshop gates on the `.py` extension and on bundle containment and
        nothing else, so which files are the method's is this skill's judgement —
        and a file sent by mistake is uploaded to the organization's catalog."""
        body = self.catalog_skill
        assert "which `.py` files are the method's is this skill's judgement, not the tool's**" in body
        assert "**A bundle with no `PipeFunc` sends no `python` at all**" in body
        assert "do not sweep the directory" in body
        assert "sending `[]` clears them" in body

    def test_a_conflict_stops_with_both_timestamps_and_picks_neither_way(self) -> None:
        body = self.catalog_skill
        assert "**Never choose between them.**" in body
        assert "both timestamps" in body
        conflict = self.catalog_reference("conflict.md")
        assert "on an explicit yes and nothing less" in conflict
        assert "the user's to remove once the comparison is done" in conflict, "the skill takes nothing off disk but a dead link"

    def test_the_pull_refusals_are_relayed_and_overwrite_needs_a_yes(self) -> None:
        """The link records no hashes, so a pull into a linked directory cannot tell
        whose change it is looking at. `overwrite: true` is the caller's assertion
        that the user was asked, and nothing else makes it true."""
        body = self.catalog_skill
        assert "**Ask the user**, showing both timestamps, and only on an explicit yes call again with `overwrite: true`" in body
        assert "the difference is local work this directory never saved" in body
        assert "every refusal writes nothing at all" in body

    def test_the_pull_uses_the_written_arm_and_leaves_the_inline_one_to_explain(self) -> None:
        body = self.catalog_skill
        assert "Always use the **written arm**" in body
        assert "/pipelex-explain" in body

    def test_unmanaged_files_are_named_and_never_deleted(self) -> None:
        """A pull writes what the catalog holds now; it does not make the directory
        match it. Nothing on hand tells a file the catalog dropped from one the user
        keeps beside the method, and deleting on that guess is unrecoverable."""
        body = self.catalog_skill
        assert "**delete nothing**" in body
        assert "`unmanaged_truncated`" in body

    def test_a_create_is_never_retried_after_a_transport_fault(self) -> None:
        """`POST /v1/methods` honours an idempotency key that the SDK cannot send
        yet, so a retry whose first response was lost mints a second method — and
        delete is admin-only, so nobody can remove it."""
        body = self.catalog_skill
        assert "**does not retry.**" in body
        assert "list the catalog first" in body

    def test_it_writes_no_file_itself(self) -> None:
        """The link file is the workshop's, because the workshop is the only party
        that knows which API host it talks to. A hand-written one records the wrong
        host and makes an unknown id undiagnosable."""
        body = self.catalog_skill
        assert "**This skill writes no file itself.**" in body
        assert "Never hand-write or hand-edit a link file." in body

    def test_delete_is_named_as_the_webapp_s_gesture(self) -> None:
        body = self.catalog_skill
        assert "deletion is admin-only on the platform and erases every run the method produced" in body

    def test_design_and_edit_point_at_it_without_gaining_catalog_tools(self) -> None:
        """Box Q: the catalog logic lives in one skill and the others gain a
        sentence. A design or edit that declared a catalog tool could save."""
        for skill in ("pipelex-design", "pipelex-edit"):
            body = (self.TEMPLATES / skill / "SKILL.md.j2").read_text(encoding="utf-8")
            assert "/pipelex-catalog" in body, f"{skill} must point at the catalog skill"
            assert "mthds_save_method" not in body, f"{skill} must not declare the save tool"
            assert "mthds_get_method" not in body, f"{skill} must not declare the get tool"

    def test_the_python_rule_does_not_call_function_name_a_file_path(self) -> None:
        """`function_name` is a key in the runtime's flat function registry — by
        default the decorated function's own name — so nothing in the bundle says
        which module defines it. A skill told otherwise sends one file, and since
        `python` replaces rather than merges, that deletes the helpers beside it."""
        python = self.catalog_reference("python.md")
        assert "**A `function_name` does not name a file.**" in python
        assert "flat, process-wide function registry" in python
        for text in (self.catalog_skill, python):
            assert "my_package.text_utils" not in text, "the dotted-path claim is wrong and must not come back"

    def test_an_input_domain_error_at_method_id_is_not_read_as_an_unknown_id(self) -> None:
        """A rejected payload, an organization-context failure and the workshop's own
        refusal when the link names another method all land at `method_id`. Reading
        the location alone removes a good `pipelex-method.json` and mints a duplicate
        nothing in this plugin can delete."""
        unknown_id = self.catalog_reference("unknown-id.md")
        assert "The location alone never tells them apart**" in unknown_id
        assert "only the not-found answer names `pipelex-method.json` and the `api_host`" in unknown_id
        assert "read [unknown-id.md](references/unknown-id.md) before concluding anything" in self.catalog_skill

    def test_the_landing_path_is_stated_relative_to_the_workshop(self) -> None:
        """`output_dir` resolves against the workshop's working directory, not the
        session's, and a path inside the workshop is legal wherever it points — so
        the rule has to name the root it is measured from."""
        body = self.catalog_skill
        assert "relative to the workshop's own working directory**" in body

    def test_the_catalog_name_becomes_one_directory_segment(self) -> None:
        """A catalog name is unvalidated free text at every layer. Spelled into
        `methods/<name>/` verbatim, `../../src` resolves inside the workshop root,
        where the containment check still passes."""
        body = self.catalog_skill
        assert "**A name never contributes a path**" in body
        assert "ask the user for the directory name" in body

    def test_the_pull_stops_on_a_method_app(self) -> None:
        """`make add-method` writes the action trio, the narrower and the registry
        entry around the bundle, so a plain write leaves the app unable to see it.
        The pull mirrors the stop `/pipelex-design` already makes."""
        body = self.catalog_skill
        assert "make add-method" in body
        design = (self.TEMPLATES / "pipelex-design" / "SKILL.md.j2").read_text(encoding="utf-8")
        assert "make add-method" in design, "the pull mirrors design's stop, so design must still carry it"

    def test_a_failed_link_write_is_never_reported_as_unlinked(self) -> None:
        """The workshop distinguishes linked-but-stale from genuinely-unlinked, and
        telling a still-linked directory it is unlinked advises passing a `method_id`
        by hand — which is how the wrong method gets overwritten."""
        body = self.catalog_skill
        assert "**Never tell this directory it is unlinked**" in body
        assert "**Linked but stale**" in body
        assert "**Genuinely unlinked**" in body

    def test_the_forced_overwrite_says_the_name_goes_with_it(self) -> None:
        """An update rewrites the row's `name` from the call and the link's copy was
        taken at the last sync, so a forced save reverts a rename made since — and
        the refusal that led there carries timestamps only."""
        assert "**The name goes with it**" in self.catalog_reference("conflict.md")

    def test_it_does_not_route_a_publish_request_at_integrate(self) -> None:
        """`/pipelex-integrate` consumes an address and recommends publishing one;
        no skill here performs that act, so a user who asks to publish must not be
        sent to a skill that will ask them for the address instead."""
        body = self.catalog_skill
        assert "`/pipelex-integrate` publishes" not in body
        integrate = (self.TEMPLATES / "pipelex-integrate" / "SKILL.md.j2").read_text(encoding="utf-8")
        assert "publishing an address" in integrate, "integrate recommends publishing; it does not do it"

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_the_catalog_tools_are_declared_and_nothing_that_writes_files_is(self, target_name: str) -> None:
        """Pre-approval, not restriction: an unlisted tool still asks, so the narrow
        set is what makes a write in this skill stop for the user. A bare `Bash`
        defeats that on its own — `cat > pipelex-method.json` needs no `Write` — so
        the only command pre-approved here is the read-only one the skill runs
        unprompted."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-catalog"],
            target_name=config.name,
        )
        body = next(content for path, content in rendered.items() if path.match("skills/pipelex-catalog/SKILL.md"))
        if target_name == "prod":
            for tool in ("mthds_list_methods", "mthds_save_method", "mthds_get_method", "mthds_validate"):
                assert f"mcp__plugin_pipelex_pipelex__{tool}" in body, f"{target_name}: pipelex-catalog must declare {tool}"
            frontmatter = body.split("---")[1]
            assert "- Write" not in frontmatter, "a skill that writes no file pre-approves no writer"
            assert "- Edit" not in frontmatter, "a skill that writes no file pre-approves no editor"
            assert "- Bash(git status:*)" in frontmatter, "the one command the skill runs unprompted is the only Bash it pre-approves"
            assert "- Bash\n" not in frontmatter, "a bare Bash entry pre-approves the very write this skill promises will stop"
            assert "- Read" in frontmatter
        else:
            assert "allowed-tools" not in body, f"{target_name}: allowed-tools is a Claude field"


class TestVibeMcpFragment:
    """The Vibe target bakes the workshop launcher as a `[[mcp_servers]]` fragment.

    Vibe has no plugin manifest, so this fragment is its MCP declaration. These
    tests render the real template with the real target variables and read the
    result the way Vibe does: as TOML holding one stdio server entry.
    """

    REPO_ROOT = Path(__file__).parents[2]

    def _render(self, target_name: str) -> dict[Path, str]:
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        return render_templates(self.REPO_ROOT / "templates", self.REPO_ROOT, config.template_vars, include_skills=[], target_name=config.name)

    def test_fragment_declares_the_launcher_from_defaults(self) -> None:
        config = load_target_config(self.REPO_ROOT / "targets", "mistral-vibe")
        mcp_server = config.template_vars["mcp_server"]
        assert isinstance(mcp_server, dict)
        rendered = self._render("mistral-vibe")
        body = rendered[self.REPO_ROOT / "mcp" / "vibe-mcp.toml"]
        servers = tomllib.loads(body)["mcp_servers"]
        assert len(servers) == 1
        server = servers[0]
        assert server["name"] == "pipelex"
        assert server["transport"] == "stdio"
        assert server["command"] == mcp_server["command"]
        assert server["args"] == mcp_server["args"]
        assert "npx -y @pipelex/mcp@latest" == " ".join([server["command"], *server["args"]])

    def test_fragment_env_names_every_forwarded_variable_unset(self) -> None:
        """Vibe forwards no shell env into a stdio spawn, so each variable Codex
        forwards by name must appear here as a key the user fills in. Empty
        values count as unset in the workshop, so an unfilled fragment is keyless
        rather than carrying a bogus key."""
        config = load_target_config(self.REPO_ROOT / "targets", "mistral-vibe")
        mcp_server = config.template_vars["mcp_server"]
        assert isinstance(mcp_server, dict)
        env_vars = mcp_server["env_vars"]
        assert isinstance(env_vars, list)
        expected_env = {str(name): "" for name in cast("list[object]", env_vars)}
        body = self._render("mistral-vibe")[self.REPO_ROOT / "mcp" / "vibe-mcp.toml"]
        server = tomllib.loads(body)["mcp_servers"][0]
        assert expected_env
        assert server["env"] == expected_env

    def test_fragment_outlasts_the_cold_npx_spawn(self) -> None:
        """Vibe's default startup timeout is 10 s and a first-ever npx spawn takes longer."""
        body = self._render("mistral-vibe")[self.REPO_ROOT / "mcp" / "vibe-mcp.toml"]
        assert tomllib.loads(body)["mcp_servers"][0]["startup_timeout_sec"] > 10

    # The shape Vibe's first run writes: bare keys first, an inline empty
    # `mcp_servers`, then tables (tomli_w.dump(VibeConfig.create_default())).
    VIBE_DEFAULT_CONFIG = 'active_model = "devstral-2"\nmcp_servers = []\nskill_paths = []\n\n[session_logging]\nenabled = true\n'

    def test_fragment_installs_into_a_default_vibe_config_only_after_deleting_the_inline_array(self) -> None:
        """Appended to a fresh Vibe config as is, the fragment is invalid TOML and
        Vibe cannot start; with the `mcp_servers = []` line deleted it loads, and
        every top-level setting stays top-level. The fragment has to carry that
        step, the paste position, and the session-log warning."""
        body = self._render("mistral-vibe")[self.REPO_ROOT / "mcp" / "vibe-mcp.toml"]
        with pytest.raises(tomllib.TOMLDecodeError):
            tomllib.loads(self.VIBE_DEFAULT_CONFIG + "\n" + body)
        installed = tomllib.loads(self.VIBE_DEFAULT_CONFIG.replace("mcp_servers = []\n", "") + "\n" + body)
        assert installed["active_model"] == "devstral-2"
        assert installed["skill_paths"] == []
        assert [server["name"] for server in installed["mcp_servers"]] == ["pipelex"]
        assert "Delete the `mcp_servers = []` line" in body
        assert "two servers of the same name" in body
        assert "Append everything below to the end of the file" in body
        assert "~/.vibe/logs/session/" in body

    @pytest.mark.parametrize("target_name", ["prod", "codex"])
    def test_plugin_targets_do_not_ship_the_fragment(self, target_name: str) -> None:
        rendered = self._render(target_name)
        assert not any(path.name == "vibe-mcp.toml" for path in rendered)


class TestPipelexInputsSizeLimitDiscipline:
    """Pin the terminal oversized-asset branch and its propagation.

    The skill is executable guidance, so these assertions protect the exact
    behavioral boundary: size rejection stops, while an unreadable path may be
    corrected without changing the selected asset.

    The size diet (`wip/skill-size-diet/`, phase 3) split the two halves by what a
    model must have read before it acts. The file-fidelity rule is a guard — a
    derived file uploaded in place of the user's is silently wrong — so it stays in
    `SKILL.md`, once, at the prepare step. The failure branches announce themselves
    by the error, so they moved to `references/prepare-errors.md`, which the stop
    table points at, keyed on the error's `location`.
    """

    REPO_ROOT = Path(__file__).parents[2]
    TEMPLATE = REPO_ROOT / "templates" / "skills" / "pipelex-inputs" / "SKILL.md.j2"
    REFERENCE = REPO_ROOT / "skills" / "pipelex-inputs" / "references" / "prepare-errors.md"
    SIZE_BRANCH = '## `location: "inputs"` and the response reports a storage size limit'
    NON_SIZE_BRANCH = '## `location: "inputs"` and the response is not a size-limit failure'
    GUARDRAILS = (
        "A preflight size check may inform the report, but it is never a reason to transform, derive, or substitute the asset",
        "Do not compress, optimize, re-encode, resize, downsample, split, truncate, extract pages or content, or convert it",
        "Do not replace it with synthetic data, a public sample, another local file, or any derived file",
        "The same prohibition applies after an upload failure.",
        "Never retry preparation with altered or substitute content to evade a storage limit",
    )

    @property
    def inputs_skill(self) -> str:
        return self.TEMPLATE.read_text(encoding="utf-8")

    @property
    def reference(self) -> str:
        return self.REFERENCE.read_text(encoding="utf-8")

    def test_size_limit_is_terminal_without_asset_or_input_mutation(self) -> None:
        body = self.inputs_skill
        for guardrail in self.GUARDRAILS:
            assert guardrail in body

        size_branch = self.reference.split(self.SIZE_BRANCH, maxsplit=1)[1].split(self.NON_SIZE_BRANCH, maxsplit=1)[0]
        assert "This is a terminal branch for the current preparation attempt." in size_branch
        assert "quote the tool's exact `message` and `hint` verbatim" in size_branch
        assert "actual file size and the allowed limit whenever the response provides them" in size_branch
        assert "preparation failed, the inputs are not run-ready, and no run will be offered" in size_branch
        assert "preserve the user's original file" in size_branch
        assert "write no `inputs.prepared.json`" in size_branch
        assert "`inputs.json` keeps its local-path form because prepare never rewrites it" in size_branch
        assert "Continue only after the user supplies a different acceptable input or reference, or the service limit changes" in size_branch
        assert "resolve its path to absolute" not in size_branch
        # The reference names the guard rather than restating it: a guard lives in SKILL.md once.
        assert "The skill's file-fidelity guard holds throughout" in self.reference
        assert "surface both and fix *that value*" not in body

    def test_unreadable_path_recovery_preserves_the_asset(self) -> None:
        non_size_branch = self.reference.split(self.NON_SIZE_BRANCH, maxsplit=1)[1]
        assert "For an unreadable local file" in non_size_branch
        assert "resolve its path to absolute as step 5 does" in non_size_branch
        assert "retry preparation with the file bytes unchanged" in non_size_branch
        assert "must not rewrite the local relative path in `inputs.json`" in non_size_branch
        assert "retry only when the documented error policy explicitly permits" in non_size_branch
        assert "don't revalidate it" in non_size_branch

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_every_platform_renders_the_same_size_limit_guardrails(self, target_name: str) -> None:
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-inputs"],
            target_name=config.name,
        )
        body = next(content for path, content in rendered.items() if path.match("skills/pipelex-inputs/SKILL.md"))
        for guardrail in self.GUARDRAILS:
            assert guardrail in body, f"{target_name}: missing oversized-asset guardrail: {guardrail}"
        # The stop table sends the model to the branch, and says the size limit is terminal on its own line.
        stop_row = next(line for line in body.splitlines() if line.startswith("| prepare: `input_domain` at `inputs`"))
        assert "](references/prepare-errors.md)" in stop_row
        assert "a storage size limit at `inputs` is terminal for this attempt" in stop_row
        shipped = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-inputs" / "references" / "prepare-errors.md"
        assert shipped.read_bytes() == self.REFERENCE.read_bytes(), f"{target_name}: the shipped prepare-errors.md is stale"


class TestAdaptiveDesignSkill:
    """Pin the behavioral workflow in the canonical skill templates.

    The skill is executable guidance rather than Python control flow, so these
    tests guard the observable decisions and transition invariants that agents
    must follow, plus their propagation to every rendered platform.

    Since the size diet's phase 4 the choice of mode and direct construction are
    `SKILL.md`'s, and stepwise construction and re-entry are references read on
    their condition (`skills/pipelex-design/references/stepwise.md` and
    `re-entry.md`), so each pin reads the file its sentence moved to.
    """

    REPO_ROOT = Path(__file__).parents[2]
    SKILLS = REPO_ROOT / "templates" / "skills"
    REFERENCES = REPO_ROOT / "skills" / "pipelex-design" / "references"

    @property
    def design(self) -> str:
        return (self.SKILLS / "pipelex-design" / "SKILL.md.j2").read_text(encoding="utf-8")

    @property
    def stepwise(self) -> str:
        return (self.REFERENCES / "stepwise.md").read_text(encoding="utf-8")

    @property
    def reentry(self) -> str:
        return (self.REFERENCES / "re-entry.md").read_text(encoding="utf-8")

    def test_direct_mode_covers_shallow_concrete_graphs(self) -> None:
        body = self.design
        assert "the graph is one concrete operator; or one top-level controller whose children are concrete leaf operators" in body
        assert "every pipe can be concrete in the first coherent artifact" in body
        assert "Include **no temporary `PipeSignature` declarations**" in body
        assert "a result already coherent in either mode skips it" in body

    def test_controller_count_is_not_a_hard_threshold(self) -> None:
        body = self.design
        assert "One controller is a strong fast-path signal, not a rule" in body
        assert "cross-branch concept dependencies, uncertain ownership, or unresolved child contracts" in body
        assert "Pipe count is secondary" in body

    def test_stepwise_mode_keeps_resumable_guarantees(self) -> None:
        """The skill chooses stepwise as the complement of the direct criteria, plus the two
        signals that are not complements; the reference names every signal as its entry condition."""
        assert "explicit request for a scaffold, partial design, staged work, or a resumable intermediate result" in self.design
        assert "a large graph that benefits from independently valid review checkpoints" in self.design
        body = self.stepwise
        assert "nested controllers or multiple structural layers whose child contracts are not all fixed" in body
        assert "explicit request for a scaffold, partial design, staged work, or a resumable intermediate result" in body
        assert "Drain the signature backlog breadth-first" in body
        assert "Every expansion adds exactly one new `<code>.mthds` definition file" in body
        assert "Early stopping exists only in stepwise mode" in body

    def test_direct_to_stepwise_transition_removes_the_abandoned_draft(self) -> None:
        body = self.stepwise
        assert "removes abandoned direct-only intermediate concepts and concrete child definitions" in body
        assert "Do **not** append signatures beside the abandoned concrete definitions" in body
        assert "every pipe/concept code is declared only where the stepwise model permits it" in body
        assert "Validate the root scaffold before adding definitions" in body
        assert (
            "**If the design would need a placeholder or a guessed contract, or writing or validation exposes an unresolved structural boundary**"
            in self.design
        )

    def test_existing_method_reentry_is_adaptive(self) -> None:
        body = self.reentry
        assert "Choose the re-entry mode from the affected graph, not the whole method's size" in body
        assert "**Direct coherent edit:** when the affected region is shallow" in body
        assert (
            "**Signature-driven re-entry:** when the affected region is nested, uncertain, cross-module, cross-branch, or intentionally staged"
            in body
        )
        assert "A pipe contract change includes every parent controller" in body
        assert "A concept reshape includes its introducing declaration and every consumer that field-reads it" in body
        assert "Keep or coherently edit the smallest unaffected concrete ancestor" in body
        assert "remove their old concrete definitions before validating" in body
        assert "each changed concept exactly once in the scaffold" in body
        assert "Do not predeclare deeper descendants while their parent is only a signature" in body
        assert "Never duplicate a concept already retained by a direct→stepwise transition or signature-driven re-entry" in self.stepwise

    def test_the_reentry_baseline_and_recovery_stay_in_the_skill(self) -> None:
        """What protects the user's bundle on a re-entry is a guard, so it is read before the
        reference is: the baseline, the retained original, and the restore on failure."""
        body = self.design
        assert "**Never redesign on a broken baseline**" in body
        assert "**Retain the original contents until the final verdict is restored.**" in body
        assert "restore the retained baseline contents and report the failure" in body

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_every_platform_renders_the_adaptive_workflow(self, target_name: str) -> None:
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-design"],
            target_name=config.name,
        )
        body = next(content for path, content in rendered.items() if path.match("skills/pipelex-design/SKILL.md"))
        assert "Design a MTHDS bundle top-down at the right depth" in body
        assert "### 3. Infer the construction mode" in body
        assert "### 4. Direct construction" in body
        assert "## Re-entry" in body
        assert "read [stepwise.md](references/stepwise.md) before writing any file" in body
        assert "read [re-entry.md](references/re-entry.md) before editing any file" in body
        assert "Never ask the user to choose the workflow" in body
        assert "{%" not in body
        assert "{{" not in body
        assert self.stepwise.startswith("# Signature-driven stepwise construction")
        assert self.reentry.startswith("# Re-entering an existing method")

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_design_is_model_invocable_on_every_platform(self, target_name: str) -> None:
        """The design skill must stay reachable without a slash command.

        It shipped ``disable-model-invocation: true`` through 0.5.0, which made
        ``pipelex-edit``'s structural-change routing a dead end. Both halves of
        the fix are pinned: the flag is gone, and the description carries the
        natural-language triggers without which removing the flag is inert.
        """
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-design"],
            target_name=config.name,
        )
        body = next(content for path, content in rendered.items() if path.match("skills/pipelex-design/SKILL.md"))
        assert "disable-model-invocation" not in body
        assert 'Use when the user says "design a method"' in body
        assert '"add a step", "rewire this pipeline"' in body

    def test_edit_hands_structural_changes_off_by_invoking_design(self) -> None:
        edit = (self.SKILLS / "pipelex-edit" / "SKILL.md.j2").read_text(encoding="utf-8")
        assert "then invoke `/pipelex-design`" in edit
        assert "hand off to `/pipelex-design` now, before any files change" in edit
        assert "and stop. Never attempt a partial structural edit here." not in edit

    def test_adjacent_skills_describe_organization_as_conditional(self) -> None:
        organize = (self.SKILLS / "pipelex-organize" / "SKILL.md.j2").read_text(encoding="utf-8")
        edit = (self.SKILLS / "pipelex-edit" / "SKILL.md.j2").read_text(encoding="utf-8")
        assert "Direct designs are normally coherent already and skip this skill" in organize
        assert "auto-invokes it after converged signature-driven construction or re-entry" in organize
        assert "an already coherent direct result does not invoke it solely for process compliance" in organize
        assert "re-enters existing methods adaptively" in edit


class TestSyntheticInputsSkill:
    """Pin the file-factory skill and the delegation that replaced
    `/pipelex-inputs`' inline Document Generation section.

    The skill is executable guidance, so these tests guard the identity rules a
    caller relies on (no AI for what code renders, a fixed package allowlist, ask before installing a
    tool), the delegation contract, and the fact that it needs no MCP tool.
    """

    REPO_ROOT = Path(__file__).parents[2]
    SKILLS = REPO_ROOT / "templates" / "skills"
    REFERENCES = ("pdf.md", "png.md", "office.md", "venv.md", "photograph.md")

    @property
    def synthetic(self) -> str:
        return (self.SKILLS / "pipelex-synthetic-inputs" / "SKILL.md.j2").read_text(encoding="utf-8")

    def test_identity_rules_are_stated(self) -> None:
        body = self.synthetic
        assert "**No AI for what code can render.**" in body
        assert "**Permissive packages only.**" in body
        for package in ("reportlab", "Pillow", "matplotlib", "numpy", "python-docx", "openpyxl"):
            assert package in body, f"missing allowlisted package: {package}"
        assert "no PyMuPDF (AGPL)" in body
        assert "Nothing installed into the project, nothing installed onto the machine without asking" in body
        assert "Installing a *tool*" in body and "always asks first, in every mode" in body
        assert "A failure leaves nothing behind" in body

    def test_photographs_are_generated_and_handwriting_simulated(self) -> None:
        body = self.synthetic
        assert "**A photograph is generated, never drawn:**" in body
        assert "never from a procedural scene or a public image" in body
        assert "**Handwriting is simulated**" in body
        assert "never draw a stand-in" in body

    def test_environment_ladder_has_both_rungs_and_a_graceful_stop(self) -> None:
        body = self.synthetic
        assert "**Rung 1 — `uv` is on `PATH`**" in body
        assert "**Rung 2 — no `uv`, but `python3` with `venv` and `pip`.**" in body
        assert "pipelex-plugins/synth-venv" in body
        # The venv rung is read from its reference when `uv` is absent (the size diet, phase 6).
        assert "When `uv` is not on `PATH` (the preflight prints nothing, and `command -v uv` finds nothing" in body
        assert "for a format that has no preflight), read [venv.md](references/venv.md) before creating anything" in body
        venv = (self.REPO_ROOT / "skills" / "pipelex-synthetic-inputs" / "references" / "venv.md").read_text(encoding="utf-8")
        assert "the runner line becomes `\"$VENV/bin/python\" << 'PYEOF'`" in venv
        assert "That substitution is the only difference between the rungs" in venv
        assert "**substitute the absolute path this command printed**" in venv, "the runner line must not be handed over as a $VENV reference"
        assert "curl -LsSf https://astral.sh/uv/install.sh" in body
        assert "return **no path** with the reason" in body

    def test_declares_no_mcp_tool(self) -> None:
        """The file factory is MCP-free except for a photograph, whose branch names the workshop's tools by
        their bare names and stops gracefully without them: no allowed-tools entry, and it is absent from the
        MCP-backed skill set the STOP-posture tests cover."""
        body = self.synthetic
        assert "mcp__" not in body
        assert "pipelex-synthetic-inputs" not in MCP_SKILLS

    def test_inputs_delegates_instead_of_generating(self) -> None:
        inputs = (self.SKILLS / "pipelex-inputs" / "SKILL.md.j2").read_text(encoding="utf-8")
        assert "pipelex-synthetic-inputs" in inputs
        assert "**`pipelex-synthetic-inputs` is the file factory**" in inputs
        assert "leave that one input unfilled, carry on with the others" in inputs
        # The inline recipes moved out wholesale — no second home for "make a file",
        # the synthetic strategy's reference included.
        synthetic = (self.REPO_ROOT / "skills" / "pipelex-inputs" / "references" / "synthetic.md").read_text(encoding="utf-8")
        for text in (inputs, synthetic):
            assert "### PDF Documents" not in text
            assert "## Document Generation" not in text
            assert "**Fallback Strategy:**" not in text
            assert "reportlab" not in text
            assert "openpyxl" not in text

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_every_platform_renders_the_skill_and_its_references(self, target_name: str) -> None:
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-synthetic-inputs"],
            target_name=config.name,
        )
        body = next(content for path, content in rendered.items() if path.match("skills/pipelex-synthetic-inputs/SKILL.md"))
        assert "# Generate synthetic input files" in body
        assert "**No AI for what code can render.**" in body
        assert "{%" not in body
        assert "{{" not in body

        references_dir = resolve_output_dir(self.REPO_ROOT, config.source) / "skills" / "pipelex-synthetic-inputs" / "references"
        for reference in self.REFERENCES:
            assert (references_dir / reference).is_file(), f"{target_name}: missing references/{reference}"

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_delegation_sentence_matches_the_platform(self, target_name: str) -> None:
        """Only Claude Code can invoke a sibling skill; the others are told to
        read it off disk, which the copied-whole plugin directory makes reachable."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-inputs"],
            target_name=config.name,
        )
        body = next(content for path, content in rendered.items() if path.match("skills/pipelex-inputs/SKILL.md"))
        if target_name == "prod":
            assert "Invoke it with `/pipelex-synthetic-inputs`." in body
            assert "open `../pipelex-synthetic-inputs/SKILL.md`" not in body
        else:
            assert "open `../pipelex-synthetic-inputs/SKILL.md` and follow it." in body
            assert "Invoke it with `/pipelex-synthetic-inputs`." not in body

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_the_build_copies_the_references_it_ships(self, target_name: str, tmp_path: Path) -> None:
        """Exercise the copy step, not the committed tree.

        `render_templates` does not copy static assets — `setup_static_assets`
        does, and asserting on the checked-in output directories only proved
        that three committed files were still committed. Dropping the skill from
        the copy step would have left every test green.
        """
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        setup_static_assets(self.REPO_ROOT, tmp_path, self.REPO_ROOT / "templates", config.include_skills)

        produced = tmp_path / "skills" / "pipelex-synthetic-inputs" / "references"
        source = self.REPO_ROOT / "skills" / "pipelex-synthetic-inputs" / "references"
        for reference in self.REFERENCES:
            assert (produced / reference).is_file(), f"{target_name}: the build did not copy references/{reference}"
            assert (produced / reference).read_bytes() == (source / reference).read_bytes(), (
                f"{target_name}: references/{reference} was copied but does not match its source"
            )

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_freshness_catches_a_stale_reference_copy(self, target_name: str, tmp_path: Path) -> None:
        """A reference edited without `make build` must fail `make check`.

        The copies are not rendered, so they never enter a BuildResult and the
        freshness check used to skip them entirely — a shipped plugin could carry
        recipes that differ from the ones the recipe suite ran.
        """
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        setup_static_assets(self.REPO_ROOT, tmp_path, self.REPO_ROOT / "templates", config.include_skills)
        templates_dir = self.REPO_ROOT / "templates"
        assert static_asset_mismatches(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills) == []

        stale = tmp_path / "skills" / "pipelex-synthetic-inputs" / "references" / "png.md"
        stale.write_text(stale.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
        assert any("STALE" in problem for problem in static_asset_mismatches(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills))

        stale.unlink()
        assert any("MISSING" in problem for problem in static_asset_mismatches(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills))

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_orphan_copies_are_reported_and_the_build_clears_them(self, target_name: str, tmp_path: Path) -> None:
        """Both kinds of orphaned copy, and the build's answer to them.

        A copy with no source is the one mismatch a rebuild used to be unable to
        fix, so `make check` failed pointing at `make build` — advice that did
        nothing. The check reports it and the build now removes it.
        """
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        templates_dir = self.REPO_ROOT / "templates"
        setup_static_assets(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills)
        references = tmp_path / "skills" / "pipelex-synthetic-inputs" / "references"

        def orphans() -> list[Path]:
            return orphaned_outputs(self.REPO_ROOT, tmp_path, static_asset_outputs(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills))

        # A file in the copy with no matching source.
        (references / "invented.md").write_text("no source file produced this\n", encoding="utf-8")
        assert orphans() == [references / "invented.md"]

        setup_static_assets(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills)
        assert not (references / "invented.md").exists(), "the rebuild left an orphaned file behind"
        assert orphans() == []
        assert static_asset_mismatches(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills) == []

        # A whole asset directory in the copy whose source no longer exists. The skill is picked
        # rather than named: the size diet gives references to more skills as it goes, and this
        # test named `pipelex-explain` until phase 6 gave it one.
        shipped = config.include_skills or sorted(path.parent.name for path in templates_dir.glob("skills/*/SKILL.md.j2"))
        bare_skill, bare_dir = next(
            (skill, asset_dir)
            for asset_dir in ("references", "scripts")
            for skill in shipped
            if not (self.REPO_ROOT / "skills" / skill / asset_dir).exists()
        )
        ghost = tmp_path / "skills" / bare_skill / bare_dir
        ghost.mkdir(parents=True)
        (ghost / "retired.md").write_text("an asset whose source was removed\n", encoding="utf-8")
        assert orphans() == [ghost / "retired.md"]

        setup_static_assets(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills)
        assert not ghost.exists(), "the rebuild left a whole orphaned references/ directory behind"
        assert orphans() == []
        assert static_asset_mismatches(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills) == []

    def test_check_freshness_fails_on_a_stale_reference_copy(self, tmp_path: Path) -> None:
        """The comparison must be wired into `check_freshness`, not merely exist.

        Testing the helper alone leaves the single call site uncovered: deleting
        it keeps the whole unit suite green while restoring the exact bug it was
        written to close.
        """
        tree = tmp_path / "repo"
        # `.DS_Store` too: the copy has no git to say it is ignored, so one Finder left in an output
        # directory of the checkout would be an orphan of the copy.
        shutil.copytree(self.REPO_ROOT, tree, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "node_modules", ".DS_Store"))
        assert check_freshness(tree, "prod") == 0, "the copied tree should start fresh"

        shipped = tree / "pipelex" / "skills" / "pipelex-synthetic-inputs" / "references" / "png.md"
        shipped.write_text(shipped.read_text(encoding="utf-8") + "\nedited without a rebuild\n", encoding="utf-8")
        assert check_freshness(tree, "prod") == 1, "a stale reference copy must fail the freshness gate"


class TestPipelexExplainSkill:
    """Boxes F and M of `wip/plugin-skills-gaps/design.md`: explain is brought on
    par with the main skills — a directory target, every pipe type named, the
    workshop optional, a remote method at contract level — and it is strictly
    read-only, which the tool list is made to match."""

    REPO_ROOT = Path(__file__).parents[2]
    TEMPLATE = REPO_ROOT / "templates" / "skills" / "pipelex-explain" / "SKILL.md.j2"
    RENDERED = REPO_ROOT / "pipelex" / "skills" / "pipelex-explain" / "SKILL.md"
    # The size diet's phase 6 moved the old step 8 — a catalog id or a published
    # address — to this reference, read before the first call on one; its guards
    # stayed in SKILL.md (`tests/unit/test_skill_guards.py`).
    NOT_ON_DISK = REPO_ROOT / "skills" / "pipelex-explain" / "references" / "not-on-disk.md"

    # Every pipe type the authoring reference documents. The old skill named
    # eight of them and left PipeCompose out entirely.
    PIPE_TYPES: ClassVar[tuple[str, ...]] = (
        "PipeLLM",
        "PipeSequence",
        "PipeBatch",
        "PipeParallel",
        "PipeCondition",
        "PipeCompose",
        "PipeExtract",
        "PipeSearch",
        "PipeImgGen",
        "PipeFunc",
        "PipeSignature",
    )

    def body(self) -> str:
        return self.TEMPLATE.read_text(encoding="utf-8")

    @pytest.mark.parametrize("pipe_type", PIPE_TYPES)
    def test_every_pipe_type_is_named(self, pipe_type: str) -> None:
        """Box F: a reader who meets a pipe the skill cannot name learns nothing
        from the passage about it."""
        assert pipe_type in self.body(), f"{pipe_type} is never named"

    def test_a_signature_is_pending_only_when_nothing_implements_it(self) -> None:
        """Box F, as Louis precised it at ratification. Signature-driven design
        leaves satisfied headers behind in the file that declared them, so a
        header read on its own reports a gap the next file fills."""
        assert "pending only when no concrete pipe of the same code exists anywhere in the files you read" in self.body()

    def test_the_workshop_is_the_authority_on_pending_signatures(self) -> None:
        """Box F: where the skill's own reading and the verdict disagree, the
        verdict wins and the user is told, because a disagreement means a file
        was missed or a code is spelled two ways."""
        body = self.body()
        assert "`pending_signatures` is the authority" in body
        assert "disagree" in body

    def test_the_explanation_opens_on_complete_or_scaffold(self) -> None:
        """Box F: an accurate walkthrough of a half-built method, given without
        saying it is half-built, misinforms."""
        body = self.body()
        assert "**complete**" in body
        assert "**scaffold with a backlog**" in body

    def test_the_workshop_is_optional_for_a_bundle_on_disk(self) -> None:
        """Box F: the source is on disk, so the tool adds a verdict line and is
        never what makes the explanation possible."""
        body = self.body()
        assert "Never refuse to explain a local bundle because the workshop is not connected." in body
        assert "say the verdict was not checked" in body

    def test_the_absent_workshop_stop_is_scoped_to_a_remote_target(self) -> None:
        """The shared requirements block states a hard stop; this skill only has
        one for a target that is not on disk, so both its bullets are scoped."""
        body = self.body()
        assert "mcp_absent_suffix" in body
        assert "mcp_config_suffix" in body
        assert "That stop is only for a target that lives on the platform" in body

    def test_a_published_address_is_explained_at_contract_level(self) -> None:
        """Box F: a published address's internals ride a channel only views see,
        so the skill describes its contract and says so rather than implying it
        read something.

        This held for a **catalog id** too until `mthds_get_method` shipped in
        `@pipelex/mcp` 0.16.0 — box F.4's own caveat, that an id is explained at
        contract level "until the release that carries" the tool. Box H's phase
        spends that caveat: an id names the user's own organization's method, so
        it is now read in full, and only the address is bounded by design. The
        fallback for an id where the tool is absent is asserted beside it.

        How the address is read is the not-on-disk reference's since the size
        diet; the skill keeps the target's one-line definition."""
        body = self.body()
        assert "explained at the level of its contract, through the workshop; the source stays in the repository it names" in body
        reference = self.NOT_ON_DISK.read_text(encoding="utf-8")
        assert "the internals are not readable from here" in reference
        assert "`explicit: true`" in reference
        for text in (body, reference):
            assert "at the level of their contract" not in text, "the id and the address no longer share one reading"

    def test_one_selector_per_call(self) -> None:
        """`pipelex-mcp/SPEC.md`: the tooling tools take exactly one of files, an
        address or an id; a second is a no-verdict located at the extra field.
        Only a remote target can carry a second, so the rule is the not-on-disk
        reference's."""
        assert "never two" in self.NOT_ON_DISK.read_text(encoding="utf-8")

    def test_the_skill_writes_nothing_and_says_so(self) -> None:
        """Box F, amended at ratification: the first draft wrote a `README.md` on
        request."""
        body = self.body()
        assert "strictly read-only" in body.lower()
        assert "writes no file" in body

    def test_the_description_no_longer_offers_to_document(self) -> None:
        """Box F: "document this pipeline" leaves the description, because it is
        the phrase that recruited the skill into writing files."""
        assert "document this pipeline" not in self.body()

    def test_the_pipefunc_warning_is_included_not_restated(self) -> None:
        """Box G's sentence has one source; explain says it when it meets one."""
        assert 'include "skills/shared/pipefunc-warning.md.j2"' in self.body()

    def test_the_tool_list_pre_approves_no_writing_tool(self) -> None:
        """Box M. `allowed-tools` pre-approves rather than restricts, so this is
        what makes a write in a read-only skill stop for the user instead of
        happening silently."""
        rendered = self.RENDERED.read_text(encoding="utf-8")
        frontmatter = rendered.split("---")[1]
        assert "  - Read" in frontmatter
        assert "  - Grep" in frontmatter
        assert "  - Glob" in frontmatter
        for writing_tool in ("  - Bash", "  - Write", "  - Edit"):
            assert writing_tool not in frontmatter, f"a read-only skill pre-approves {writing_tool.strip()}"

    def test_the_writing_skills_keep_the_default_tool_list(self) -> None:
        """Box M: explain gets the narrow list, the other skills keep today's."""
        design = (self.REPO_ROOT / "pipelex" / "skills" / "pipelex-design" / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = design.split("---")[1]
        for tool in ("  - Bash", "  - Read", "  - Write", "  - Edit", "  - Grep", "  - Glob"):
            assert tool in frontmatter, f"the default list lost {tool.strip()}"

    def test_the_offline_path_may_state_its_own_reading(self) -> None:
        """Round 1, cubic and Codex independently: the prohibition on reporting
        an unverified verdict also banned the source-derived backlog that steps
        2, 4 and 6 require when no workshop answered, so the skill both
        mandated and forbade the same sentence."""
        body = self.body()
        assert "Your own reading of the source is not a guess" in body
        assert "do not present a validation verdict, a typed signature or a pending list as the workshop's" in body

    def test_the_offline_fallback_is_denied_to_a_remote_target(self) -> None:
        """The same loosening must not reach a target with no source: there the
        tool's answer is all there is, and guessing is what the rule forbids."""
        assert "On a target that is not on disk there is no such fallback." in self.body()

    def test_an_absent_main_pipe_is_named_and_never_reconstructed(self) -> None:
        """Round 1, cubic: a positive verdict can carry no `main_pipe` — no entry
        pipe, a contract that did not come back whole, or a workshop predating
        the field — and a remote target has no source to fall back on. The
        prohibition is a guard and stays in the skill's stop row; the three
        causes and the address's conditional signature are the not-on-disk
        reference's."""
        body = self.body()
        reference = self.NOT_ON_DISK.read_text(encoding="utf-8")
        assert "when the verdict carries one" in reference
        assert "the workshop predates the field" in reference
        assert "| the verdict carries no `main_pipe` |" in body
        assert "Do not reconstruct a signature from the input template." in body

    def test_an_invalid_remote_method_is_reported_and_not_routed_to_disk(self) -> None:
        """Round 1, Codex: an invalid id or address projects no `main_pipe` and
        answers `validation_errors[]` instead of shapes, so there is nothing to
        explain — and `/pipelex-edit` cannot reach a method that is not on disk.
        The routing is the not-on-disk reference's since the size diet; the
        stop rows stay in the skill."""
        body = self.body()
        assert "Do not route a remote target to `/pipelex-edit` or `/pipelex-design`" in self.NOT_ON_DISK.read_text(encoding="utf-8")
        assert "a **local bundle** does not validate" in body, "the stops row must be scoped to disk"

    def test_an_untagged_address_is_accepted_and_said_to_float(self) -> None:
        """Box E as amended at ratification: every skill accepts an untagged
        address and says in one line that it floats. This skill is where the
        optional tag is advertised."""
        body = self.body()
        assert "An address with no `@<tag>` floats" in body
        assert "Accept it, and say so in one line." in body

    def test_explain_is_not_an_mcp_backed_skill(self) -> None:
        """Box F: it stays out of the tuple, which asserts a hard stop this skill
        does not have."""
        assert "pipelex-explain" not in MCP_SKILLS


class TestBundleHome:
    """A method's sources are loaded at runtime by the call site that runs them.

    Writing them to a directory named "wip" meant every integration was either a
    production call site loading from `pipelex-wip/`, or a copy whose original no
    longer had a sidecar naming it — so a later edit of that original reported a
    clean bill that was wrong."""

    REPO_ROOT = Path(__file__).parents[2]
    SKILLS = REPO_ROOT / "templates" / "skills"

    def _template(self, skill: str) -> str:
        return (self.SKILLS / skill / "SKILL.md.j2").read_text(encoding="utf-8")

    def test_design_resolves_the_home_before_it_writes(self) -> None:
        body = self._template("pipelex-design")
        assert "### 2. Resolve the bundle home before writing" in body
        assert "A path the user named" in body
        assert "`<package>/methods/<name>/`" in body
        assert "`<project root>/methods/<name>/`" in body
        assert "`./methods/<name>/`" in body

    def test_design_announces_the_home_with_the_contract(self) -> None:
        """The user can only redirect the write while it has not happened."""
        body = self._template("pipelex-design")
        assert "with the bundle home resolved below in the same line" in body

    def test_the_name_follows_the_project_language_casing(self) -> None:
        body = self._template("pipelex-design")
        assert "`summarize-pdf` in TypeScript, `summarize_pdf` in Python" in body

    def test_nothing_a_skill_ships_still_defaults_to_pipelex_wip(self) -> None:
        """It survives only as a directory a user may already have, never as the
        default this plugin writes to nor as an example it teaches from.

        Every template under `templates/skills/` counts, shared partials included:
        a partial is inlined into each skill that includes it, so a name
        reintroduced there ships in several skills while appearing in none of
        their sources. The static `skills/*/references/` documents count too —
        they are copied verbatim into every target and are what the skills send
        the model to read."""
        shipped = sorted(self.SKILLS.rglob("*.j2")) + sorted((self.REPO_ROOT / "skills").rglob("*.md"))
        assert shipped, "found nothing to check — the layout moved"
        for path in shipped:
            body = path.read_text(encoding="utf-8")
            assert "pipelex-wip" not in body, f"{path.relative_to(self.REPO_ROOT)} still names pipelex-wip"


class TestEditClassifiesFirstAndTriggersStopColliding:
    """Box L of `wip/plugin-skills-gaps/design.md`.

    Two things a description cannot say twice and a step order that decides who
    pays for a verdict: `pipelex-edit` routes a structural change to
    `/pipelex-design` before it validates anything, and the trigger phrases two
    skills both claimed now belong to one each."""

    REPO_ROOT = Path(__file__).parents[2]
    SKILLS = REPO_ROOT / "templates" / "skills"

    def _template(self, skill: str) -> str:
        return (self.SKILLS / skill / "SKILL.md.j2").read_text(encoding="utf-8")

    def _description(self, skill: str) -> str:
        for line in self._template(skill).splitlines():
            if line.startswith("description:"):
                return line
        raise AssertionError(f"{skill} has no description line")

    def test_edit_classifies_before_it_baselines(self) -> None:
        """A request routed to design must not pay for a verdict here first.

        Classification reads the files Step 1 already loaded and calls no tool,
        so putting it after the baseline call bought nothing and cost a
        validation on every structural request — which design then repeats when
        it re-enters."""
        body = self._template("pipelex-edit")
        classify = body.index("### Step 2: Classify the change")
        baseline = body.index("### Step 3: Baseline verdict")
        assert classify < baseline
        assert "hand off to `/pipelex-design` now, before any files change" in body
        assert "### Step 3: Classify the change" not in body
        assert "### Step 2: Baseline verdict" not in body

    def test_edit_says_why_the_order_is_what_it_is(self) -> None:
        """The skill keeps the half-sentence that marks the order as deliberate; the reason itself is
        rationale, which the size diet's phase 6 left in `docs/decisions.md` alone."""
        body = self._template("pipelex-edit")
        assert "calls no tool, so it comes before the baseline verdict on purpose" in body
        decisions = (self.REPO_ROOT / "docs" / "decisions.md").read_text(encoding="utf-8")
        assert "paid for a verdict here before being handed to `/pipelex-design`, which validates its own baseline when it re-enters" in decisions

    def test_edit_re_validates_against_the_step_that_holds_the_baseline(self) -> None:
        """Step 5's back-reference moves with the step it names."""
        body = self._template("pipelex-edit")
        assert "Same whole-bundle `mthds_validate` call as Step 3." in body
        assert "Same whole-bundle `mthds_validate` call as Step 2." not in body

    @pytest.mark.parametrize("trigger", ['"add a step"', '"remove this pipe"', '"refactor this pipeline"'])
    def test_edit_stops_advertising_work_it_cannot_do(self, trigger: str) -> None:
        """Edit cannot apply any of them, so recruiting it on the phrase only
        buys a hand-off turn. Its Step 2 routing stays as the safety net for a
        request that reaches it anyway."""
        assert trigger not in self._description("pipelex-edit")

    def test_design_carries_one_of_them_and_covers_the_rest_by_umbrella(self) -> None:
        """Only "add a step" was ever design's verbatim trigger, and nothing was
        added to its description to receive the other two — they fall under the
        umbrella clause, which is the same wording edit's own scope split uses
        for removing and refactoring. The record says so, so the test does."""
        description = self._description("pipelex-design")
        assert '"add a step", "rewire this pipeline"' in description
        assert '"refactor the flow"' in description
        assert "or asks for a structural or contract change to an existing bundle" in description
        assert "adding, removing, or rewiring steps" in self._template("pipelex-edit")

    def test_edit_still_routes_a_structural_request_that_reaches_it(self) -> None:
        body = self._template("pipelex-edit")
        assert '| "Add a step to do X" (open-ended) | structural → route to `/pipelex-design` |' in body
        assert '| "Refactor this pipeline" (subjective) | structural → route to `/pipelex-design` |' in body

    def test_scaffolding_is_the_scaffold_skills_word(self) -> None:
        """`/pipelex-scaffold` starts a project; in every other skill here a
        scaffold is a bundle with pending signatures. Design claimed the phrase
        for neither meaning."""
        assert '"scaffold a method"' not in self._description("pipelex-design")
        assert '"bootstrap a Pipelex project"' in self._description("pipelex-scaffold")

    def test_inputs_does_not_claim_the_bare_word_template(self) -> None:
        """Too generic to recruit on: the word reaches this skill from a code
        template, a project template and a prompt template alike."""
        description = self._description("pipelex-inputs")
        assert '"template"' not in description
        assert '"prepare inputs"' in description

    def test_inputs_keeps_the_word_as_a_strategy_signal(self) -> None:
        """Dropping it from the description does not drop it from the table
        that picks a strategy once the skill is already running."""
        body = self._template("pipelex-inputs")
        assert 'User says "template" / "schema" / "placeholder"' in body

    def test_no_skill_explains_what_another_skill_defaults_to(self) -> None:
        """The generic mode preamble told the reader that "each skill defines
        its own default" — inside the one skill that carries it."""
        for path in sorted(self.SKILLS.rglob("*.j2")):
            body = path.read_text(encoding="utf-8")
            assert "Each skill defines its own default" not in body, path.relative_to(self.REPO_ROOT)

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_every_platform_renders_the_modes_inputs_actually_has(self, target_name: str) -> None:
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=["pipelex-inputs"],
            target_name=config.name,
        )
        body = next(content for path, content in rendered.items() if path.match("skills/pipelex-inputs/SKILL.md"))
        assert "**Default**: automatic — name the strategy and the assumptions it rests on in one line" in body
        assert "carry the chosen strategy through to its own end without stopping" in body
        assert "**Go interactive** when the user asks for it" in body
        assert "when the table below lands on its no-signal row" in body
        assert "**Either mode can turn into the other mid-run**" in body
        assert "### Mode behavior" not in body
        assert "### Mode switching" not in body


class TestHookRendering:
    def test_all_platforms_declare_their_hook_templates(self) -> None:
        """Each platform declares its own hook template set, and the MCP fragment is not among them."""
        assert set(HOOK_TEMPLATES_BY_PLATFORM) == {Platform.CLAUDE, Platform.CODEX, Platform.MISTRAL_VIBE}
        assert HOOK_TEMPLATES_BY_PLATFORM[Platform.CLAUDE] == ["hooks/hooks.json.j2", "hooks/check-mthds.sh.j2", "hooks/launch-pipelex-mcp.sh.j2"]
        assert HOOK_TEMPLATES_BY_PLATFORM[Platform.CODEX] == ["hooks/codex-hooks.json.j2", "hooks/check-mthds-codex.sh.j2"]
        assert HOOK_TEMPLATES_BY_PLATFORM[Platform.MISTRAL_VIBE] == ["hooks/vibe-hooks.toml.j2", "hooks/check-mthds-vibe.sh.j2"]
        assert MCP_TEMPLATES_BY_PLATFORM == {Platform.CLAUDE: [], Platform.CODEX: [], Platform.MISTRAL_VIBE: ["mcp/vibe-mcp.toml.j2"]}

    def test_a_missing_mcp_template_is_named_for_what_it_is(self, tmp_path: Path) -> None:
        """The Vibe fragment is the workshop launcher's declaration, not a hook, and its absence says so."""
        tree = _create_codex_tree(tmp_path)
        (tree / "templates" / "mcp" / "vibe-mcp.toml.j2").unlink()
        with pytest.raises(SystemExit, match=r"^Declared MCP template not found: mcp/vibe-mcp\.toml\.j2$"):
            render_templates(tree / "templates", tree, {**DEFAULT_VARS, "platform": "mistral-vibe"})

    def test_claude_renders_hook_json_and_script(self, template_tree: Path) -> None:
        results = render_templates(template_tree / "templates", template_tree, DEFAULT_VARS)
        output_names = {path.name for path in results}
        assert "hooks.json" in output_names
        assert "check-mthds.sh" in output_names
        assert "codex-hooks.json" not in output_names

    def test_codex_renders_only_codex_hook(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        results = render_templates(tree / "templates", tree, {**DEFAULT_VARS, "platform": "codex"})
        output_names = {path.name for path in results}
        assert "codex-hooks.json" in output_names
        assert "check-mthds-codex.sh" in output_names
        assert "hooks.json" not in output_names
        assert "check-mthds.sh" not in output_names
        assert "vibe-mcp.toml" not in output_names

    def test_vibe_renders_toml_and_vibe_script(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        results = render_templates(tree / "templates", tree, {**DEFAULT_VARS, "platform": "mistral-vibe"})
        output_names = {path.name for path in results}
        assert "vibe-hooks.toml" in output_names
        assert "check-mthds-vibe.sh" in output_names
        assert tree / "mcp" / "vibe-mcp.toml" in results

    def test_generate_makes_hook_script_executable(self, template_tree: Path) -> None:
        generate(template_tree, "prod")
        hook_script = template_tree / "pipelex" / "hooks" / "check-mthds.sh"
        assert hook_script.is_file()
        assert os.access(hook_script, os.X_OK)

    def test_all_platforms_declare_check_mjs_static_asset(self) -> None:
        """One vendored check.mjs bundle serves all three platforms."""
        for platform in Platform:
            assert STATIC_HOOK_ASSETS_BY_PLATFORM[platform] == ["hooks/assets/check.mjs"]

    def test_static_asset_copied_verbatim_not_rendered(self, template_tree: Path) -> None:
        """check.mjs must bypass Jinja: its body (a generated bundle) may contain
        brace sequences that a template pass would mangle or reject."""
        results = render_templates(template_tree / "templates", template_tree, DEFAULT_VARS)
        asset_output = template_tree / "hooks" / "check.mjs"
        assert asset_output in results
        assert results[asset_output] == STATIC_ASSET_BODIES["hooks/assets/check.mjs"]

    def test_generate_writes_static_asset_into_target(self, template_tree: Path) -> None:
        generate(template_tree, "prod")
        asset = template_tree / "pipelex" / "hooks" / "check.mjs"
        assert asset.is_file()
        assert asset.read_text() == STATIC_ASSET_BODIES["hooks/assets/check.mjs"]

    def test_missing_static_asset_raises(self, template_tree: Path) -> None:
        (template_tree / "templates" / "hooks" / "assets" / "check.mjs").unlink()
        with pytest.raises(SystemExit, match="static hook asset not found"):
            render_templates(template_tree / "templates", template_tree, DEFAULT_VARS)

    def test_check_freshness_detects_stale_static_asset(self, template_tree: Path) -> None:
        generate(template_tree, "prod")
        (template_tree / "pipelex" / "hooks" / "check.mjs").write_text("// stale bundle\n")
        assert check_freshness(template_tree, "prod") == 1

    def test_vibe_and_codex_ship_the_static_asset(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        for platform in ("mistral-vibe", "codex"):
            results = render_templates(tree / "templates", tree, {**DEFAULT_VARS, "platform": platform})
            output_names = {path.name for path in results}
            assert "check.mjs" in output_names


class TestNoShippedSkillNamesAnAbsentSkill:
    """A skill that points the user at a sibling skill the target does not contain is a dead end
    the user meets and we never do: on Claude the slash command resolves to nothing, and on Codex
    and Vibe the relative `../<skill>/SKILL.md` the body tells the agent to open is not there.

    `test_pipelex_integrate_skill.py` pins the one name a cut actually removed
    (`assert "pipelex-scaffold" not in body`), which catches that spelling and no other — a
    forward reference reintroduced under any different name passes it. This resolves every
    cross-skill reference in every shipped body against the skills the target really ships, so
    the next rename or cut cannot leave a dangling one behind under a name nobody thought to
    grep for. It reads the committed target trees, because those are what a user installs.
    """

    REPO_ROOT = Path(__file__).parents[2]
    TARGETS = ("prod", "codex", "mistral-vibe")

    # A backticked slash command (`/pipelex-design`) and a relative sibling path
    # (`../pipelex-design/SKILL.md`) are the only two ways a body names another skill. The
    # leading backtick matters: without it, a cache path like `.../pipelex-plugins/synth-venv`
    # would be read as a reference to a skill named `pipelex-plugins`.
    SLASH_REFERENCE = re.compile(r"`/(pipelex-[a-z0-9-]+)`")
    SIBLING_REFERENCE = re.compile(r"\.\./([a-z0-9-]+)/SKILL\.md")

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_cross_skill_reference_resolves_in_the_shipped_tree(self, target_name: str) -> None:
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        skills_dir = resolve_output_dir(self.REPO_ROOT, config.source) / "skills"
        shipped = {path.name for path in skills_dir.iterdir() if path.is_dir()}
        assert shipped, f"{target_name}: no skills found under {skills_dir}"

        unresolved: list[str] = []
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            body = skill_md.read_text(encoding="utf-8")
            named = set(self.SLASH_REFERENCE.findall(body)) | set(self.SIBLING_REFERENCE.findall(body))
            unresolved += [f"{skill_md.parent.name} names {name}, which this target does not ship" for name in sorted(named - shipped)]

        assert not unresolved, f"{target_name}: dangling cross-skill references: " + "; ".join(unresolved)


class TestPublishedAddressTarget:
    """A published address is the third target form in `pipelex-inputs` and `pipelex-run`.

    Box E of `wip/plugin-skills-gaps/design.md` at the workspace root, ratified
    2026-09-21. An address is passed as `method_ref` exactly as a catalog id is
    passed as `method_id`, so no step grows a special case — and what these pin
    is the handful of places where an address is genuinely not like an id: it
    has no directory of its own, it pairs with no other selector, an untagged
    one floats, the method is not the user's to repair, and one refusal on the
    way is about the workshop rather than the request."""

    REPO_ROOT = Path(__file__).parents[2]
    TEMPLATES = REPO_ROOT / "templates" / "skills"

    @property
    def inputs_skill(self) -> str:
        return (self.TEMPLATES / "pipelex-inputs" / "SKILL.md.j2").read_text(encoding="utf-8")

    @property
    def run_skill(self) -> str:
        return (self.TEMPLATES / "pipelex-run" / "SKILL.md.j2").read_text(encoding="utf-8")

    def test_both_skills_carry_the_address_as_a_third_target(self) -> None:
        """The whole of box E rests on the selector reaching every call: a skill that
        names the address in its prose and then templates or runs by `files` has
        added a paragraph, not a target."""
        assert "three forms" in self.inputs_skill
        for body in (self.inputs_skill, self.run_skill):
            assert "`method_ref`" in body
            assert "github.com/<owner>/<repo>[/<selector>][@<tag>]" in body

    @property
    def inputs_address_reference(self) -> str:
        """`pipelex-inputs`' address branch, read at step 1 when the target is a `method_ref` (size diet, phase 3)."""
        return (self.REPO_ROOT / "skills" / "pipelex-inputs" / "references" / "published-address.md").read_text(encoding="utf-8")

    @property
    def run_address_reference(self) -> str:
        """`pipelex-run`'s address branch, read at step 1 when the target is a `method_ref` (size diet, phase 6)."""
        return (self.REPO_ROOT / "skills" / "pipelex-run" / "references" / "published-address.md").read_text(encoding="utf-8")

    @property
    def run_failure_reference(self) -> str:
        """`pipelex-run`'s failure branch, read at step 8 before a failed run is routed (size diet, phase 6)."""
        return (self.REPO_ROOT / "skills" / "pipelex-run" / "references" / "failed-run.md").read_text(encoding="utf-8")

    def test_an_untagged_address_is_accepted_everywhere_and_said_to_float(self) -> None:
        """Louis's amendment at ratification: no skill refuses an untagged address
        until the catalog supports versioning. The line that it floats is what the
        user gets instead of a refusal, so its absence is the failure mode. In
        `pipelex-inputs` the instruction to say so stays at step 1, and what floating
        means is the address reference's, read before the first call. In `pipelex-run`
        both are the address reference's, which step 1 points at before the first call."""
        assert "**An address with no tag is accepted, and it floats**: say so in one line" in self.inputs_skill
        for body in (self.inputs_address_reference, self.run_address_reference):
            assert "default branch at its head" in body
        assert "never a reason to refuse the work" in self.inputs_address_reference
        assert "Say that in one line, recommend the tag, and start the run." in self.run_address_reference
        assert "](references/published-address.md) before the first call" in self.run_skill

    def test_the_output_directory_of_an_address_drops_the_tag(self) -> None:
        """An address has no directory of its own, so one is derived — and the tag has
        to come off it, or `documents@v0.1.0` becomes a directory name carrying a
        version the next run has no reason to keep."""
        for body in (self.inputs_address_reference, self.run_address_reference):
            assert "last path segment with its tag dropped" in body
            assert "gives `./documents/`" in body
        assert "](references/published-address.md) before the first call" in self.inputs_skill

    def test_an_address_pairs_with_no_other_selector(self) -> None:
        """`mthds_run` takes `files` + `method_id` together — the files run and the id
        is recorded as linkage — so "one selector per call" is not a rule an agent can
        infer from the run tool it already knows. An address is the exception and says so."""
        body = self.run_skill
        assert "an address pairs with nothing" in body.lower()
        assert "complete run source" in body
        # The stops table says what the body says: a second selector is a refusal, not a
        # normalization the skill performs silently on the user's behalf.
        assert "drops the extra one" not in body
        assert "refused before anything runs" in body
        # And the skill does not resolve the ambiguity itself: a run is paid, so two
        # targets in hand is a question for the user, not a selector to quietly omit.
        # The stop row that restated it went in the size diet; the guard at step 1 holds it.
        assert "ask which one is meant" in body
        assert "never pick one yourself" in body

    def test_a_published_method_is_not_routed_into_the_editing_skills(self) -> None:
        """Every other failing target in this skill routes to `/pipelex-design` or
        `/pipelex-edit`. A published method belongs to whoever published it, so the
        same routing would send an agent to edit source the user does not have. The
        verdict's routing is the address reference's, the run failure's is the failure
        reference's, and step 3 points at the first where an address's verdict fails."""
        body = self.run_address_reference
        assert "belongs to whoever published it" in body
        assert "is not routed to `/pipelex-design` or `/pipelex-edit`" in body
        assert "an address's verdict is reported as [its reference](references/published-address.md) says" in self.run_skill
        failure = self.run_failure_reference.split("## A published address", 1)[1]
        assert "every row below the inputs one is reported rather than routed" in failure
        assert "the resolved commit SHA the skill's step 5 reported" in failure

    def test_an_address_run_reports_what_was_actually_fetched(self) -> None:
        """A floating address and a moved tag both make "which content ran" unanswerable
        after the fact. The resolved commit SHA rides the start acknowledgement and
        nothing later recovers it, so it is reported beside the run id or lost."""
        body = self.run_skill
        assert "`method_provenance`" in body
        assert "resolved commit SHA" in body

    def test_the_stale_workshop_refusal_is_read_off_the_error_it_produces(self) -> None:
        """The one thing in box E that needed checking against the workshop rather than
        the design: `mthds_prepare_inputs` did not take `method_ref` before the release
        that added it, and a host validating against the older tool schema drops the
        argument before sending it — so the error arrives at `files` saying no selector
        was supplied, NOT at `method_ref`. An agent told to look for the latter reads a
        stale workshop as a missing bundle and goes hunting for files that do not exist.
        The reading is the address reference's, and the stop table keys on the error."""
        assert "`input_domain` at `files`" in self.inputs_skill
        body = self.inputs_address_reference
        assert "Provide MTHDS files or a method_id" in body
        assert "npx -y @pipelex/mcp@latest" in body
        assert "predates the selector" in body
        # The refresh is not a cure on its own: the launcher decides what the NEXT spawn
        # fetches, and a workshop that carries the selector has to exist to be fetched.
        assert "restarts the server" in body
        assert "leaving them refreshing in a loop" in body

    def test_the_address_config_refusal_names_the_gate_without_suppressing_the_credential(self) -> None:
        """Prepare resolves an address through the run route, so a published package
        shipping in-process Python is refused there — in the same `config` arm, wearing
        the deployment's authentication wording. Naming that cause is worth doing; the
        first draft went further and told the agent the credential was fine, which the
        round refuted: preparation uploads with the key and templating never exercises
        that, so a template call that succeeded rules nothing out, and the arm also
        covers a paywall, an unreachable API and a missing upload route. The credential
        stays the first thing checked, because it is the one the user can act on."""
        assert "`config` (the credential first, as the requirements say)" in self.inputs_skill
        body = self.inputs_address_reference
        assert "in-process Python" in body
        assert "the credential first" in body
        assert "rules nothing out" in body
        assert "the key is not what failed" not in body


class TestCatalogIdInEverySkill:
    """Box H of `wip/plugin-skills-gaps/design.md`, with box A step 5, box F.4
    and box R's notice: a catalog id is a target every skill accepts.

    The three file-based skills reach a saved method through a directory — the
    one already linked to it, or the one `/pipelex-catalog` pulls it into — and
    say when the saved copy has fallen behind. `pipelex-run` files a run of a
    linked directory under its method. `pipelex-explain` reads a saved method's
    source in full.

    What these guard is the pair of claims that are cheap to get wrong and
    expensive to ship wrong: that the file-based skills never save on the tail
    of an edit, and that `pipelex-explain` stays read-only while gaining a tool
    whose other arm writes to disk."""

    REPO_ROOT = Path(__file__).parents[2]
    TEMPLATES = REPO_ROOT / "templates" / "skills"

    BRIDGED: ClassVar[tuple[str, ...]] = ("pipelex-design", "pipelex-edit", "pipelex-organize")
    # Every file-based skill reads the bridge block from the shared reference
    # `skills/shared/catalog-id.md`: `pipelex-design` since the size diet's phase 4, and
    # `pipelex-edit` and `pipelex-organize` since phase 6, so none carries it inline.
    SHARED_BRIDGE = "skills/shared/catalog-id.md.j2"

    def skill(self, name: str) -> str:
        return (self.TEMPLATES / name / "SKILL.md.j2").read_text(encoding="utf-8")

    def run_reference(self, name: str) -> str:
        """A `pipelex-run` reference, read on its branch since the size diet's phase 6."""
        return (self.REPO_ROOT / "skills" / "pipelex-run" / "references" / name).read_text(encoding="utf-8")

    @pytest.mark.parametrize("skill", BRIDGED)
    def test_a_skill_can_bridge_through_the_shared_reference(self, skill: str) -> None:
        """The bridge block keeps one source: the shared reference includes it and sets its resume
        step, and a skill that points there says when, before reading any file, and keeps the
        bridge's two guards itself — a guard never lives only in a file read on demand."""
        shared = (self.TEMPLATES.parent / self.SHARED_BRIDGE).read_text(encoding="utf-8")
        assert 'include "skills/shared/catalog-id-bridge.md.j2"' in shared
        assert "catalog_id_bridge_resume" in shared, "the shared reference sets the resume step"
        body = self.skill(skill)
        assert 'include "skills/shared/catalog-id-bridge.md.j2"' not in body, "the block has one carrier per skill"
        assert body.count('include "skills/shared/catalog-id-pointer.md.j2"') == 1, "the pointer is said once, in the shared words"
        pointer = (self.TEMPLATES / "shared" / "catalog-id-pointer.md.j2").read_text(encoding="utf-8")
        assert "read [the catalog-id reference](../shared/catalog-id.md) before reading any file" in pointer
        assert "**For a catalog id (`mt_…`) or a published address**" in pointer, "an address is the bridge's to refuse"
        assert "never choose" in pointer
        assert "**Never present a linked directory as the saved method's current content.**" in pointer

    @pytest.mark.parametrize("skill", BRIDGED)
    def test_the_file_based_skills_say_when_the_saved_copy_fell_behind(self, skill: str) -> None:
        body = self.skill(skill)
        assert 'include "skills/shared/saved-copy-notice.md.j2"' in body

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_the_bridge_resumes_at_a_named_step_on_every_target(self, target_name: str) -> None:
        """`catalog_id_bridge_resume` is interpolated bare, and `StrictUndefined`
        is what fails the render when a skill forgets to set it — a guard around
        it would suppress that failure rather than add to it. This asserts the
        other half: that the step reaches the rendered text on every target and
        carries no build-error marker, rather than trusting the build to have
        run — in the shared reference every file-based skill reads it from."""
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        rendered = render_templates(
            self.REPO_ROOT / "templates",
            self.REPO_ROOT,
            config.template_vars,
            include_skills=list(self.BRIDGED),
            target_name=config.name,
        )
        for carrier in ("skills/shared/catalog-id.md",):
            body = next(content for path, content in rendered.items() if path.match(carrier))
            assert "PIPELEX_BUILD_ERROR" not in body, f"{target_name}/{carrier}: the bridge's resume step did not resolve"
            assert "say which one, and go to **" in body, f"{target_name}/{carrier}: the bridge names no step to resume at"
        shared = next(content for path, content in rendered.items() if path.match("skills/shared/catalog-id.md"))
        assert shared.startswith("# A catalog id or a published address as the target\n\nRead this when "), (
            f"{target_name}: the shared reference opens with its entry condition"
        )
        assert "pipelex-design" not in shared, f"{target_name}: the shared reference names no skill, so edit and organize can point at it unchanged"
        # The skill that points here sends the model with a pointer, not a numbered step, so "the step that sent
        # you here" could resolve to the pointer itself and send the model back to this file.
        assert "go to **the skill that sent you here, just after its pointer to this file**" in shared, (
            f"{target_name}: the shared reference does not say where to continue"
        )
        # A published address is refused here, so the return to the sending skill is conditional on an id that
        # resolved; an unconditional one would carry the skill into its file-based flow with no directory.
        opening = shared.split("\n\n")[1]
        assert "Once a catalog id resolves to a directory, return to the skill that sent you here" in opening
        assert "a published address is the end of that skill's work" in opening

    def test_the_bridge_never_picks_between_two_linked_directories(self) -> None:
        """`/pipelex-catalog`'s conflict path deliberately creates a second
        directory carrying the same link — a comparison copy, meant for reading
        and explicitly not for saving from. A bridge that took the first grep
        hit would edit that copy about as often as it edited the work."""
        body = (self.TEMPLATES / "shared" / "catalog-id-bridge.md.j2").read_text(encoding="utf-8")
        assert "never yours" in body
        assert "comparison copy" in body
        assert "ask which one is the work" in body

    def test_the_bridge_does_not_claim_the_local_files_are_the_saved_content(self) -> None:
        """The link records no hashes, so a grep hit proves where the method
        lives locally and nothing about whether it matches the catalog."""
        body = (self.TEMPLATES / "shared" / "catalog-id-bridge.md.j2").read_text(encoding="utf-8")
        assert "records no hashes" in body
        assert "do not present the local files as the saved method's current content" in body

    def test_the_notice_offers_the_save_and_never_makes_it(self) -> None:
        """A save is a deployment: `pipelex-mcp/SPEC.md`'s catalog write scope
        and `/pipelex-catalog` both hold that no other skill saves at all. The
        notice is the one place three skills mention the catalog right after
        writing files, which is exactly where an autonomous save would creep
        in."""
        body = (self.TEMPLATES / "shared" / "saved-copy-notice.md.j2").read_text(encoding="utf-8")
        assert "**Offer that; never do it.**" in body
        assert "deployment" in body
        assert "Never write or edit `pipelex-method.json`" in body

    def test_the_notice_asserts_no_ordering_between_the_two_copies(self) -> None:
        """The link file records no hashes, which the bridge says in as many
        words, so the notice may claim only that this directory changed and the
        catalog has not seen it. A teammate's save since the last sync puts the
        catalog *ahead*, and calling the saved copy old there tells the user
        callers are running content they are not."""
        body = (self.TEMPLATES / "shared" / "saved-copy-notice.md.j2").read_text(encoding="utf-8")
        assert "may equally be behind the catalog" in body
        assert "asserts an ordering nothing here can read" in body
        assert "what compares the two" in body

    def test_organize_leaves_the_notice_to_design_when_design_called_it(self) -> None:
        """`/pipelex-design`'s delivery step invokes `/pipelex-organize` and
        carries the same notice, so an unguarded include says it twice in one
        flow. Since the size diet's phase 6 one condition governs both of
        organize's report notices, the stale-types one and this one."""
        body = self.skill("pipelex-organize")
        assert "**When invoked on its own rather than by `/pipelex-design`** (whose delivery step carries both notices)" in body

    def test_a_linked_run_sends_the_id_beside_the_files(self) -> None:
        """Box A step 5. `files` + `method_id` is the one legal selector pair
        (`pipelex-mcp/SPEC.md`'s Method Selectors): the files run and the id is
        run-history linkage."""
        body = self.skill("pipelex-run")
        assert "pipelex-method.json" in body
        assert "the files are what run" in body
        assert "filed under that method" in body

    def test_a_linked_run_does_not_read_as_the_saved_method_having_run(self) -> None:
        """The run appears under the method in the webapp's history while the
        content that ran is the directory's. Reporting the filing without that
        distinction tells the user the catalog's method ran, which is the one
        thing the pair does not mean."""
        body = self.skill("pipelex-run")
        assert "do not let the filing read as the saved method having run" in body

    def test_a_files_run_blames_the_pipefunc_only_when_the_failure_does(self) -> None:
        """Step 8's standing rule is to route once from `failure_message`.
        Holding a `PipeFunc` is not evidence that one failed: a run that dies on
        a missing input upstream of the custom pipe would otherwise be declared
        a registration failure and sent to `/pipelex-catalog`, which is a
        deployment gesture and no cure for a missing input. The reading is the
        failure reference's since the size diet, and step 8 points at it before routing."""
        body = self.run_reference("failed-run.md")
        assert "Where `failure_message` implicates resolving or registering that function" in body
        assert "**Where it says anything else, route on what it says**" in body
        assert "not evidence that it is what failed" in body
        assert "then read [failed-run.md](references/failed-run.md) before routing it" in self.skill("pipelex-run")

    def test_a_linked_run_carries_no_stored_python(self) -> None:
        """Verified in `pipelex-server`: a caller-supplied source takes
        precedence and the stored method is resolved only when no files were
        sent at all, so the assembled `.mthds` + `.py` run bundle is reached on
        the id-only path alone. A `files` submission is `.mthds`-only, so a
        custom `PipeFunc` has no channel on any files run — the skill has to say
        so, or it routes a user to bisect a failure whose cause is structural.
        It is acted on only when a `files` run fails, so the failure reference says it."""
        body = self.run_reference("failed-run.md")
        assert "no channel for its Python on any files run" in body
        assert "assembled into the run bundle server-side" in body

    def test_an_unknown_linkage_id_is_read_off_a_location_that_discriminates(self) -> None:
        """`RUN_START_MIXED_ERROR_OPTIONS` splits the locations deliberately: a
        rejected payload and a refused execution locus land at `files`, and only
        the unknown-method arm lands at `method_id`. That is the opposite of
        `/pipelex-catalog`'s save, where one location carries several causes —
        so the reason is stated, and an agent does not carry either rule to the
        other place. The reading is `linked-run.md`'s, which the stop table's row
        for that refusal points at."""
        body = self.run_reference("linked-run.md")
        assert "that location is the discriminator rather than a coincidence" in body
        assert "api_host` the link file records" in body
        assert "without** the id" in body
        assert "| `mthds_run`: `input_domain` at `method_id`, on a linked run |" in self.skill("pipelex-run")

    def test_explain_reads_a_saved_method_and_writes_none_of_it(self) -> None:
        """Box F.4 amended. `mthds_get_method`'s other arm writes the sources
        and a link file to disk, so the one guard that matters for a strictly
        read-only skill is that it never passes `output_dir`."""
        body = self.skill("pipelex-explain")
        assert "mthds_get_method" in body
        assert "no `output_dir`" in body
        assert "Do not pass it, not even to a temporary directory." in body

    def test_explain_declares_only_the_read_half_of_the_catalog(self) -> None:
        """A read-only skill gains a catalog tool; the write ones stay out."""
        body = self.skill("pipelex-explain")
        assert "mcp__plugin_pipelex_pipelex__mthds_get_method" in body
        assert "mthds_save_method" not in body
        assert "mthds_list_methods" not in body

    def test_explain_says_a_bounded_read_is_partial(self) -> None:
        """The inline arm withholds whole files above its budget, carrying the
        name and byte size with no content. Explaining the rest as the whole
        library is step 1's own hazard, reached through a tool instead of
        through a missed file."""
        body = self.skill("pipelex-explain")
        assert "truncated" in body
        assert "the explanation is partial" in body
        assert "Never describe a withheld file's pipes as absent." in body

    def test_explain_keeps_an_empty_stored_source_distinct_from_an_unknown_id(self) -> None:
        """Both are `input_domain` at `method_id`; one is somebody's draft and
        the other is a wrong id, and collapsing them sends the user hunting for
        a typo in an id that is correct."""
        body = self.skill("pipelex-explain")
        assert "different answers" in body
        assert "not a wrong id" in body

    def test_explain_falls_back_to_the_contract_where_the_read_tool_is_absent(self) -> None:
        """`mthds_get_method` is the local workshop's alone — the hosted console
        serves neither catalog-write tool — so an id there is explained at
        contract level. A narrower explanation, never a stop: explain's whole
        posture is that the workshop is optional."""
        body = self.skill("pipelex-explain")
        assert "narrower explanation, not a stop" in body

    def test_explain_names_both_causes_of_an_absent_read_tool(self) -> None:
        """A workshop older than the release carrying `mthds_get_method`
        presents exactly as the hosted console does — the tool is simply not in
        the list — so naming only the console sends a workshop user looking for
        a host they are not on. The cure is stated without a version, because
        `floors.pipelex_mcp` is a ceiling about the main-pipe signature and
        quoting it here would name the wrong release. The two causes are the
        not-on-disk reference's since the size diet, and the skill's stop row
        names both through it."""
        body = self.skill("pipelex-explain")
        reference = (self.REPO_ROOT / "skills" / "pipelex-explain" / "references" / "not-on-disk.md").read_text(encoding="utf-8")
        assert "a local workshop that predates the tool" in reference
        assert "npx -y @pipelex/mcp@latest" in reference
        assert "say both rather than picking one" in reference
        assert "name both causes [not-on-disk.md](references/not-on-disk.md) gives" in body

    def test_explain_still_reads_an_invalid_catalog_id_from_its_source(self) -> None:
        """The stops table is titled for where the skill stops, so an agent
        reads it as the authority. A row collapsing an id with an address there
        — no source to explain, stop — discards the source this phase taught the
        skill to read."""
        body = self.skill("pipelex-explain")
        assert "| a **catalog id** does not validate | explain it from the source read above" in body
        assert "| a published **address** does not validate |" in body
        assert "an **id or address** does not validate" not in body

    def test_explain_stays_out_of_the_hard_stop_roster(self) -> None:
        """`MCP_SKILLS` asserts a skill that stops without the workshop. Explain
        gained a third tool and still explains local source without any."""
        assert "pipelex-explain" not in MCP_SKILLS

    def test_the_lab_stays_out_of_the_hard_stop_roster(self) -> None:
        """The lab frames a use case and writes keys with no workshop at all, and
        stops before its loop, which is the only move that reads a run."""
        assert "pipelex-lab" not in MCP_SKILLS


class TestSkillScriptsCopy:
    """A skill's `scripts/` travels beside its `references/`, executable bit and all.

    A skill runs its scripts by path, so the build must copy them into every
    target, keep the bit that lets them run, and let the freshness check see a
    copy that lost either its bytes or its bit (box E of the size diet's design).
    """

    @staticmethod
    def _repo(tmp_path: Path) -> Path:
        base = tmp_path / "repo"
        (base / "templates" / "skills" / "demo").mkdir(parents=True)
        (base / "templates" / "skills" / "demo" / "SKILL.md.j2").write_text("demo\n", encoding="utf-8")
        scripts = base / "skills" / "demo" / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "probe.sh").write_text("#!/bin/sh\necho probe-ok\n", encoding="utf-8")
        (scripts / "probe.sh").chmod(0o755)
        (base / "skills" / "demo" / "references").mkdir()
        (base / "skills" / "demo" / "references" / "branch.md").write_text("branch\n", encoding="utf-8")
        return base

    def test_scripts_are_copied_executable_and_fresh(self, tmp_path: Path) -> None:
        base = self._repo(tmp_path)
        out = tmp_path / "out"
        setup_static_assets(base, out, base / "templates", None)

        copied = out / "skills" / "demo" / "scripts" / "probe.sh"
        assert copied.read_bytes() == (base / "skills" / "demo" / "scripts" / "probe.sh").read_bytes()
        assert os.access(copied, os.X_OK), "the build dropped the script's executable bit"
        assert (out / "skills" / "demo" / "references" / "branch.md").is_file()
        assert static_asset_mismatches(base, out, base / "templates", None) == []

    def test_a_copy_that_lost_its_executable_bit_is_reported(self, tmp_path: Path) -> None:
        base = self._repo(tmp_path)
        out = tmp_path / "out"
        setup_static_assets(base, out, base / "templates", None)

        (out / "skills" / "demo" / "scripts" / "probe.sh").chmod(0o644)
        problems = static_asset_mismatches(base, out, base / "templates", None)
        assert any(problem.strip().startswith("MODE:") and "probe.sh" in problem for problem in problems), problems

    def test_a_stale_or_orphan_script_is_reported_and_a_retired_directory_is_cleared(self, tmp_path: Path) -> None:
        base = self._repo(tmp_path)
        out = tmp_path / "out"
        setup_static_assets(base, out, base / "templates", None)

        copied = out / "skills" / "demo" / "scripts" / "probe.sh"
        copied.write_text("#!/bin/sh\necho drift\n", encoding="utf-8")
        assert any("STALE" in problem for problem in static_asset_mismatches(base, out, base / "templates", None))

        shutil.rmtree(base / "skills" / "demo" / "scripts")
        assert orphaned_outputs(base, out, static_asset_outputs(base, out, base / "templates", None)) == [
            out / "skills" / "demo" / "scripts" / "probe.sh"
        ]
        setup_static_assets(base, out, base / "templates", None)
        assert not (out / "skills" / "demo" / "scripts").exists(), "a retired scripts/ directory kept shipping"
        assert static_asset_mismatches(base, out, base / "templates", None) == []


class TestRenderedFrontmatterShape:
    """The size diet's box F: the frontmatter partial leaves no blank line inside the block."""

    REPO_ROOT = Path(__file__).parents[2]

    @pytest.mark.parametrize("target", ["pipelex", "pipelex-codex", "pipelex-vibe"])
    def test_no_blank_line_inside_the_frontmatter(self, target: str) -> None:
        for skill_md in sorted((self.REPO_ROOT / target / "skills").glob("*/SKILL.md")):
            text = skill_md.read_text(encoding="utf-8")
            block = text[4 : text.index("\n---\n", 4)]
            assert "\n\n" not in block, f"{skill_md.relative_to(self.REPO_ROOT)}: a blank line inside the frontmatter"
