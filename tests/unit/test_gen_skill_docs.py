"""Tests for scripts/gen_skill_docs.py template rendering."""

from __future__ import annotations

import json
import os
import re
import shutil
import tomllib
from pathlib import Path
from typing import ClassVar, cast

import pytest

from scripts.gen_skill_docs import (
    CODEX_DISCOVERY_MARKETPLACE_DST,
    CODEX_DISCOVERY_MARKETPLACE_SRC,
    HOOK_TEMPLATES_BY_PLATFORM,
    SHARED_TEMPLATES,
    STATIC_HOOK_ASSETS_BY_PLATFORM,
    Platform,
    TargetConfig,
    build_target,
    check_freshness,
    generate,
    load_target_config,
    make_plugin_json,
    render_codex_discovery_marketplace,
    render_templates,
    resolve_output_dir,
    setup_static_assets,
    static_asset_mismatches,
)

DEFAULT_VARS: dict[str, str | bool] = {"marketplace_name": "pipelex-plugins", "plugin_name": "pipelex", "platform": "claude"}

# Include-only partial: a file under templates/skills/shared/ that skill
# templates {% include %}, but which is NOT in SHARED_TEMPLATES (not rendered
# standalone).
FRONTMATTER_PARTIAL = "skills/shared/frontmatter.md.j2"

# The skills that stop when the workshop is absent. A skill that works without it
# — pipelex-explain, pipelex-synthetic-inputs, pipelex-scaffold — stays out.
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
    (shared / "mthds-reference.md.j2").write_text("# MTHDS Reference {{ marketplace_name }}\n")
    (shared / "native-content-types.md.j2").write_text("# Native Content Types\n")
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
    (shared / "mthds-reference.md.j2").write_text("Ref.\n")
    (shared / "native-content-types.md.j2").write_text("Types.\n")
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
        ref_output = template_tree / "skills" / "shared" / "mthds-reference.md"
        assert ref_output in results
        assert "MTHDS Reference pipelex-plugins" in results[ref_output]

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
        assert "mthds-reference.md" in output_names
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
        assert "mthds-reference.md" in output_names

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
        assert any(path.name == "mthds-reference.md" for path in result.files)

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

    @pytest.mark.parametrize(
        "target_name, manifest_spawns",
        [
            ("prod", True),
            ("codex", True),
            ("mistral-vibe", False),
        ],
    )
    def test_absent_tools_stop_message_matches_platform(self, target_name: str, manifest_spawns: bool) -> None:
        """The MCP-absent STOP guidance must quote the real launcher command and,
        on Vibe (no plugin manifest, no auto-spawn), point at the shipped fragment
        instead of a manifest spawn. Renders the real templates with real target vars."""
        repo_root = Path(__file__).parents[2]
        config = load_target_config(repo_root / "targets", target_name)
        rendered = render_templates(
            repo_root / "templates",
            repo_root,
            config.template_vars,
            include_skills=list(MCP_SKILLS),
            target_name=config.name,
        )
        for skill in MCP_SKILLS:
            body = next(content for path, content in rendered.items() if path.match(f"skills/{skill}/SKILL.md"))
            assert "npx -y @pipelex/mcp@latest" in body, f"{target_name}/{skill}: stale launcher command in STOP message"
            if manifest_spawns:
                assert "plugin manifest spawns" in body, f"{target_name}/{skill}: missing manifest-spawn diagnostic"
            else:
                assert "plugin manifest spawns" not in body, f"{target_name}/{skill}: Vibe has no manifest spawn"
                assert "`mcp/vibe-mcp.toml`" in body, f"{target_name}/{skill}: Vibe STOP message must point at the shipped MCP fragment"
                assert "`env` table" in body, f"{target_name}/{skill}: Vibe STOP message must say where the key goes"
                assert "to the end of `~/.vibe/config.toml`" in body, f"{target_name}/{skill}: Vibe STOP message must say to append the entry"
                assert "`mcp_servers = []`" in body, f"{target_name}/{skill}: Vibe STOP message must say to delete the inline empty array"

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_credential_sentence_names_the_platform_channel(self, target_name: str) -> None:
        """Where the workshop gets its API key from differs per harness, so the
        sentence differs per harness — it used to be shared by Claude and Codex.

        On Claude the canonical channel is the plugin configuration, whose value
        the launcher promotes into the spawn environment, and on Claude Desktop
        it is the only channel: a GUI launch carries no shell environment, so an
        agent that advises exporting a shell variable there advises something
        that cannot work. Codex forwards the session environment by name. Vibe
        spawns with a minimal environment and reads the server entry's own `env`
        table."""
        repo_root = Path(__file__).parents[2]
        config = load_target_config(repo_root / "targets", target_name)
        rendered = render_templates(
            repo_root / "templates",
            repo_root,
            config.template_vars,
            include_skills=list(MCP_SKILLS),
            target_name=config.name,
        )
        for skill in MCP_SKILLS:
            body = next(content for path, content in rendered.items() if path.match(f"skills/{skill}/SKILL.md"))
            session_env_claim = "from the session environment — the same variable the plugin's validation hook documents"
            if target_name == "prod":
                assert "from the **plugin configuration**" in body, f"{target_name}/{skill}: Claude's canonical channel is the plugin configuration"
                assert "OS keychain" in body, f"{target_name}/{skill}: say where the configured key is kept"
                assert "Claude Desktop" in body, f"{target_name}/{skill}: name the host where the shell environment does not exist"
                assert session_env_claim not in body, f"{target_name}/{skill}: the session environment is Claude's fallback, not its channel"
            elif target_name == "codex":
                assert session_env_claim in body, f"{target_name}/{skill}: Codex forwards the session environment"
                assert "plugin configuration" not in body, f"{target_name}/{skill}: Codex has no plugin configuration prompt"
            else:
                assert "`env` table in `~/.vibe/config.toml`" in body, f"{target_name}/{skill}: Vibe reads the server entry's own env table"
                assert "never from the session environment" in body, f"{target_name}/{skill}: Vibe passes no shell env to the server"
                assert "plugin configuration" not in body, f"{target_name}/{skill}: Vibe has no plugin manifest to configure"


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
        "The Pipelex MCP server isn't connected —": "skills/shared/mcp-requirements.md.j2",
        "The server authenticates to the API with": "skills/shared/mcp-requirements.md.j2",
        "**Formatting is automatic.**": "skills/shared/formatting-hook.md.j2",
        "Prefer the path form ": "skills/shared/validate-call.md.j2",
        "now stale and offer": "skills/shared/stale-types-notice.md.j2",
        "`PipeFunc` is experimental": "skills/shared/pipefunc-warning.md.j2",
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
        and run says it beside the stops table, where a `PipeFunc` is named as a
        suspect for a failure nothing upstream could have caught.

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

    def test_the_authoring_reference_carries_the_same_warning(self) -> None:
        """The reference is where a designer reads what a PipeFunc is; a warning
        absent there is a warning the author never meets. It is a static asset
        copied verbatim into every target and never rendered, so it cannot
        include the partial — this test is what holds the two in step, and it
        reads the partial rather than restating it, so that rewording the shared
        sentence and leaving the reference behind fails here instead of shipping
        a plugin whose skill and whose reference disagree."""
        partial = (self.REPO_TEMPLATES / "skills" / "shared" / "pipefunc-warning.md.j2").read_text(encoding="utf-8")
        warning = re.sub(r"\{#.*?#\}", "", partial, flags=re.DOTALL).strip()
        assert warning, "the partial rendered to nothing — its comment wrapper moved"
        reference = (self.REPO_TEMPLATES.parent / "skills" / "pipelex-design" / "references" / "writing-mthds.md").read_text(encoding="utf-8")
        assert warning in reference, "reword the shared warning and the authoring reference in the same change"

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
        assert "except anything under a `runs/` directory" in body

    def test_the_artifact_directory_is_relative_and_a_refusal_is_retried(self) -> None:
        """`dir` is relative to the workshop's own working directory and an absolute
        path is refused before the run is read, so an absolute bundle path would make
        a completed run read as a failed download."""
        body = self.run_skill
        assert "relative to the workshop's own working directory" in body
        assert "A refused `dir` is not a failed download" in body

    def test_user_values_are_laid_over_a_prepared_set(self) -> None:
        """Restating one input of a filled set is ordinary; without the merge it drops
        every other key and fails the template check as drift."""
        body = self.run_skill
        assert "laid over a current `inputs.prepared.json`" in body
        assert "replace only the keys the user named" in body

    def test_the_worked_example_never_writes_back_over_the_source(self) -> None:
        """The example is the most-copied part of a skill: one that still overwrites
        `inputs.json` destroys the source form this change exists to preserve."""
        body = self.inputs_skill
        assert "written back over `inputs.json`" not in body
        assert "written to `inputs.prepared.json` beside an unchanged `inputs.json`" in body

    def test_preparation_is_skipped_only_for_values_already_remote(self) -> None:
        """`data:` URLs and inline bytes are not local files but still need uploading,
        so a skip condition phrased as "no local file" blesses a set that
        `/pipelex-run` then refuses."""
        body = self.inputs_skill
        assert "**When every file-ish value is already an `http(s)` URL or a `pipelex-storage://` reference**" in body
        assert "every file-ish value was already an `http(s)` URL or a `pipelex-storage://` reference" in body
        assert "no input is a local file" not in body
        assert "no value was a local file" not in body

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
        """A durable run sitting in RUNNING with no error is a workflow task that
        failed out of sight, not a slow run — the distinction cost a project hours."""
        body = self.run_skill
        assert "a workflow task that failed out of sight" in body
        assert "It is not a slow run" in body

    def test_it_prepares_nothing_and_routes_instead(self) -> None:
        body = self.run_skill
        assert "Do not prepare inputs here." in body
        assert "inputs.prepared.json" in body, "the run reads the prepared file; it does not write one"

    def test_artifacts_land_beside_the_bundle_when_the_workshop_can_reach_it(self) -> None:
        body = self.run_skill
        assert "`<bundle_dir>/runs/<run_id>/`" in body
        assert "report the paths the tool returns" in body

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
        assert "except anything under a `runs/` directory" in body
        assert "root file first" in body

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
        assert "**Never choose between them:**" in body
        assert "both timestamps" in body
        assert "on an explicit yes and nothing less" in body

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
        body = self.catalog_skill
        assert "**A `function_name` does not name a file.**" in body
        assert "flat, process-wide function registry" in body
        assert "my_package.text_utils" not in body, "the dotted-path claim is wrong and must not come back"

    def test_an_input_domain_error_at_method_id_is_not_read_as_an_unknown_id(self) -> None:
        """A rejected payload, an organization-context failure and the workshop's own
        refusal when the link names another method all land at `method_id`. Reading
        the location alone removes a good `pipelex-method.json` and mints a duplicate
        nothing in this plugin can delete."""
        body = self.catalog_skill
        assert "the location alone never tells them apart**" in body
        assert "only the not-found answer names `pipelex-method.json` and the `api_host`" in body

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
        body = self.catalog_skill
        assert "**The name goes with it**" in body

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
    """

    REPO_ROOT = Path(__file__).parents[2]
    TEMPLATE = REPO_ROOT / "templates" / "skills" / "pipelex-inputs" / "SKILL.md.j2"
    SIZE_BRANCH = '`location: "inputs"` **and the response reports a storage size limit**'
    NON_SIZE_BRANCH = '`location: "inputs"` **and the response is not a size-limit failure**'
    GUARDRAILS = (
        "A preflight size check may inform the report, but it is never a reason to transform, derive, or substitute the asset",
        "Do not compress, optimize, re-encode, resize, downsample, split, truncate, extract pages or content, or convert it",
        "Do not replace it with synthetic data, a public sample, another local file, or any derived file",
        "Never retry preparation with altered or substitute content to evade a storage limit",
        "this is a terminal branch for the current preparation attempt",
        "no run will be offered",
        "Do not transform or substitute the asset and do not retry `mthds_prepare_inputs` with altered content",
    )

    @property
    def inputs_skill(self) -> str:
        return self.TEMPLATE.read_text(encoding="utf-8")

    def test_size_limit_is_terminal_without_asset_or_input_mutation(self) -> None:
        body = self.inputs_skill
        for guardrail in self.GUARDRAILS:
            assert guardrail in body

        size_branch = body.split(self.SIZE_BRANCH, maxsplit=1)[1].split(self.NON_SIZE_BRANCH, maxsplit=1)[0]
        assert "quote the tool's exact `message` and `hint` verbatim" in size_branch
        assert "actual file size and the allowed limit whenever the response provides them" in size_branch
        assert "preparation failed, the inputs are not run-ready" in size_branch
        assert "preserve the user's original file" in size_branch
        assert "`inputs.json` keeps its local-path form because prepare never rewrites it" in size_branch
        assert "resolve its path to absolute" not in size_branch
        assert "surface both and fix *that value*" not in body

    def test_unreadable_path_recovery_preserves_the_asset(self) -> None:
        non_size_branch = self.inputs_skill.split(self.NON_SIZE_BRANCH, maxsplit=1)[1]
        assert "For an unreadable local file" in non_size_branch
        assert "resolve its path to absolute per step 1" in non_size_branch
        assert "retry preparation with the file bytes unchanged" in non_size_branch
        assert "must not rewrite the local relative path in `inputs.json`" in non_size_branch
        assert "retry only when the documented error policy explicitly permits" in non_size_branch

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
        assert "For an unreadable local file" in body
        assert "resolve its path to absolute per step 1" in body


class TestAdaptiveDesignSkill:
    """Pin the behavioral workflow in the canonical skill templates.

    The skill is executable guidance rather than Python control flow, so these
    tests guard the observable decisions and transition invariants that agents
    must follow, plus their propagation to every rendered platform.
    """

    REPO_ROOT = Path(__file__).parents[2]
    SKILLS = REPO_ROOT / "templates" / "skills"

    @property
    def design(self) -> str:
        return (self.SKILLS / "pipelex-design" / "SKILL.md.j2").read_text(encoding="utf-8")

    def test_direct_mode_covers_shallow_concrete_graphs(self) -> None:
        body = self.design
        assert "the graph is one concrete operator; or one top-level controller whose children are concrete leaf operators" in body
        assert "every pipe can be concrete in the first coherent artifact" in body
        assert "Include **no temporary `PipeSignature` declarations**" in body
        assert "A direct result that is already coherent skips `/pipelex-organize`" in body

    def test_controller_count_is_not_a_hard_threshold(self) -> None:
        body = self.design
        assert "One controller is a strong fast-path signal, not a rule" in body
        assert "cross-branch concept dependencies, uncertain ownership, or unresolved child contracts" in body
        assert "Pipe count is secondary" in body

    def test_stepwise_mode_keeps_resumable_guarantees(self) -> None:
        body = self.design
        assert "nested controllers or multiple structural layers whose child contracts are not all fixed" in body
        assert "explicit request for a scaffold, partial design, staged work, or a resumable intermediate result" in body
        assert "Drain the signature backlog breadth-first" in body
        assert "Every expansion adds exactly one new `<code>.mthds` definition file" in body
        assert "Early stopping exists only in stepwise mode" in body

    def test_direct_to_stepwise_transition_removes_the_abandoned_draft(self) -> None:
        body = self.design
        assert "removes abandoned direct-only intermediate concepts and concrete child definitions" in body
        assert "Do **not** append signatures beside the abandoned concrete definitions" in body
        assert "every pipe/concept code is declared only where the stepwise model permits it" in body
        assert "Validate the root scaffold before adding definitions" in body

    def test_existing_method_reentry_is_adaptive(self) -> None:
        body = self.design
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
        assert "Never duplicate a concept already retained by a direct→stepwise transition or signature-driven re-entry" in body

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
        assert "## Direct construction — complete shallow graph" in body
        assert "## Signature-driven construction — validated stepwise refinement" in body
        assert "## Editing an existing method (adaptive re-entry)" in body
        assert "Never ask the user to choose the workflow" in body
        assert "{%" not in body
        assert "{{" not in body

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
    caller relies on (no AI, a fixed package allowlist, ask before installing a
    tool), the delegation contract, and the fact that it needs no MCP tool.
    """

    REPO_ROOT = Path(__file__).parents[2]
    SKILLS = REPO_ROOT / "templates" / "skills"
    REFERENCES = ("pdf.md", "png.md", "office.md")

    @property
    def synthetic(self) -> str:
        return (self.SKILLS / "pipelex-synthetic-inputs" / "SKILL.md.j2").read_text(encoding="utf-8")

    def test_identity_rules_are_stated(self) -> None:
        body = self.synthetic
        assert "**No AI in the loop.**" in body
        assert "**Permissive packages only.**" in body
        for package in ("reportlab", "Pillow", "matplotlib", "numpy", "python-docx", "openpyxl"):
            assert package in body, f"missing allowlisted package: {package}"
        assert "no PyMuPDF (AGPL)" in body
        assert "Nothing installed into the project, nothing installed onto the machine without asking" in body
        assert "Installing a *tool*" in body and "always asks first, in every mode" in body
        assert "A failure leaves nothing behind" in body

    def test_refused_categories_are_named_with_the_ask(self) -> None:
        body = self.synthetic
        assert "**Not covered, by design:** photographs and handwriting." in body
        assert "ask the user for a real file for that input" in body
        assert "Do not draw an approximation, and do not substitute a public image." in body

    def test_environment_ladder_has_both_rungs_and_a_graceful_stop(self) -> None:
        body = self.synthetic
        assert "**Rung 1 — `uv` is on `PATH`**" in body
        assert "**Rung 2 — no `uv`, but `python3` with `venv` and `pip`.**" in body
        assert "pipelex-plugins/synth-venv" in body
        assert "the runner line becomes `\"$VENV/bin/python\" << 'PYEOF'`" in body
        assert "That substitution is the only difference between the rungs" in body
        assert "**substitute the absolute path this command printed**" in body, "the runner line must not be handed over as a $VENV reference"
        assert "curl -LsSf https://astral.sh/uv/install.sh" in body
        assert "return **no path** with the reason" in body

    def test_declares_no_mcp_tool(self) -> None:
        """The file factory is MCP-free: no allowed-tools entry, and it is
        absent from the MCP-backed skill set the STOP-posture tests cover."""
        body = self.synthetic
        assert "mcp__" not in body
        assert "pipelex-synthetic-inputs" not in MCP_SKILLS

    def test_inputs_delegates_instead_of_generating(self) -> None:
        inputs = (self.SKILLS / "pipelex-inputs" / "SKILL.md.j2").read_text(encoding="utf-8")
        assert "pipelex-synthetic-inputs" in inputs
        assert "**`pipelex-synthetic-inputs` is the file factory**" in inputs
        assert "leave that one input unfilled, carry on with the others" in inputs
        # The inline recipes moved out wholesale — no second home for "make a file".
        assert "### PDF Documents" not in inputs
        assert "## Document Generation" not in inputs
        assert "**Fallback Strategy:**" not in inputs
        assert "reportlab" not in inputs
        assert "openpyxl" not in inputs

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
        assert "**No AI in the loop.**" in body
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
        """Both ORPHAN branches, and the build's answer to them.

        A copy with no source is the one mismatch a rebuild used to be unable to
        fix, so `make check` failed pointing at `make build` — advice that did
        nothing. The check reports it and the build now removes it.
        """
        config = load_target_config(self.REPO_ROOT / "targets", target_name)
        templates_dir = self.REPO_ROOT / "templates"
        setup_static_assets(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills)
        references = tmp_path / "skills" / "pipelex-synthetic-inputs" / "references"

        # A file in the copy with no matching source.
        (references / "invented.md").write_text("no source file produced this\n", encoding="utf-8")
        problems = static_asset_mismatches(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills)
        assert any("ORPHAN" in problem and "invented.md" in problem for problem in problems)

        setup_static_assets(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills)
        assert not (references / "invented.md").exists(), "the rebuild left an orphaned file behind"
        assert static_asset_mismatches(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills) == []

        # A whole references/ directory in the copy whose source no longer exists.
        ghost = tmp_path / "skills" / "pipelex-explain" / "references"
        ghost.mkdir(parents=True)
        (ghost / "retired.md").write_text("a reference whose source was removed\n", encoding="utf-8")
        problems = static_asset_mismatches(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills)
        assert any("ORPHAN" in problem and "pipelex-explain" in problem for problem in problems)

        setup_static_assets(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills)
        assert not ghost.exists(), "the rebuild left a whole orphaned references/ directory behind"
        assert static_asset_mismatches(self.REPO_ROOT, tmp_path, templates_dir, config.include_skills) == []

    def test_check_freshness_fails_on_a_stale_reference_copy(self, tmp_path: Path) -> None:
        """The comparison must be wired into `check_freshness`, not merely exist.

        Testing the helper alone leaves the single call site uncovered: deleting
        it keeps the whole unit suite green while restoring the exact bug it was
        written to close.
        """
        tree = tmp_path / "repo"
        shutil.copytree(self.REPO_ROOT, tree, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "node_modules"))
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

    def test_a_remote_method_is_explained_at_contract_level(self) -> None:
        """Box F: no source enters the conversation for an id or an address, by
        the platform's design — so the skill says so rather than implying it
        read something."""
        body = self.body()
        assert "at the level of their contract" in body
        assert "the internals are not readable from here" in body
        assert "`explicit: true`" in body

    def test_one_selector_per_call(self) -> None:
        """`pipelex-mcp/SPEC.md`: the tooling tools take exactly one of files, an
        address or an id; a second is a no-verdict located at the extra field."""
        assert "never two" in self.body()

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
        the field — and a remote target has no source to fall back on."""
        body = self.body()
        assert "when the verdict carries one" in body
        assert "Do not reconstruct a signature from the input template." in body

    def test_an_invalid_remote_method_is_reported_and_not_routed_to_disk(self) -> None:
        """Round 1, Codex: an invalid id or address projects no `main_pipe` and
        answers `validation_errors[]` instead of shapes, so there is nothing to
        explain — and `/pipelex-edit` cannot reach a method that is not on disk."""
        body = self.body()
        assert "Do not route a remote target to `/pipelex-edit` or `/pipelex-design`" in body
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
        assert "### Resolve the bundle home before writing" in body
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
        body = self._template("pipelex-edit")
        assert "calls no tool, so it comes before the baseline verdict on purpose" in body
        assert "would otherwise have paid for two identical verdicts" in body

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
        """Each platform declares its own hook template set."""
        assert set(HOOK_TEMPLATES_BY_PLATFORM) == {Platform.CLAUDE, Platform.CODEX, Platform.MISTRAL_VIBE}
        assert HOOK_TEMPLATES_BY_PLATFORM[Platform.CLAUDE] == ["hooks/hooks.json.j2", "hooks/check-mthds.sh.j2", "hooks/launch-pipelex-mcp.sh.j2"]
        assert HOOK_TEMPLATES_BY_PLATFORM[Platform.CODEX] == ["hooks/codex-hooks.json.j2", "hooks/check-mthds-codex.sh.j2"]
        assert HOOK_TEMPLATES_BY_PLATFORM[Platform.MISTRAL_VIBE] == [
            "hooks/vibe-hooks.toml.j2",
            "hooks/check-mthds-vibe.sh.j2",
            "mcp/vibe-mcp.toml.j2",
        ]

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

    def test_an_untagged_address_is_accepted_everywhere_and_said_to_float(self) -> None:
        """Louis's amendment at ratification: no skill refuses an untagged address
        until the catalog supports versioning. The line that it floats is what the
        user gets instead of a refusal, so its absence is the failure mode."""
        for body in (self.inputs_skill, self.run_skill):
            assert "floats" in body
            assert "default branch at its head" in body

    def test_the_output_directory_of_an_address_drops_the_tag(self) -> None:
        """An address has no directory of its own, so one is derived — and the tag has
        to come off it, or `documents@v0.1.0` becomes a directory name carrying a
        version the next run has no reason to keep."""
        body = self.inputs_skill
        assert "last path segment with its tag dropped" in body
        assert "gives `./documents/`" in body

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
        assert "asks which target is meant" in body
        assert "ask which one is meant" in body

    def test_a_published_method_is_not_routed_into_the_editing_skills(self) -> None:
        """Every other failing target in this skill routes to `/pipelex-design` or
        `/pipelex-edit`. A published method belongs to whoever published it, so the
        same routing would send an agent to edit source the user does not have."""
        body = self.run_skill
        assert "belongs to whoever published it" in body
        assert "is not routed to `/pipelex-design` or `/pipelex-edit`" in body

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
        stale workshop as a missing bundle and goes hunting for files that do not exist."""
        body = self.inputs_skill
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
        body = self.inputs_skill
        assert "in-process Python" in body
        assert "the credential first" in body
        assert "rules nothing out" in body
        assert "the key is not what failed" not in body
