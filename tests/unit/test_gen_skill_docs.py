"""Tests for scripts/gen_skill_docs.py template rendering."""

from __future__ import annotations

import json
import os
from pathlib import Path

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
)

DEFAULT_VARS: dict[str, str | bool] = {"marketplace_name": "pipelex-plugins", "plugin_name": "pipelex", "platform": "claude"}

# Include-only partial: a file under templates/skills/shared/ that skill
# templates {% include %}, but which is NOT in SHARED_TEMPLATES (not rendered
# standalone).
FRONTMATTER_PARTIAL = "skills/shared/frontmatter.md.j2"
FRONTMATTER_BODY = '{%- if platform == "claude" -%}\nallowed-tools:\n  - Bash\n{% endif -%}\n'


# Minimal hook templates for every platform. render_templates declares hooks
# per platform (Claude: hooks.json + check-mthds.sh; Codex: codex-hooks.json;
# Vibe: vibe-hooks.toml + check-mthds-vibe.sh), so any test tree that reaches
# skill/hook rendering must provide them or render fails with "hook template not
# found".
HOOK_TEMPLATE_BODIES = {
    "hooks/hooks.json.j2": '{"hooks": {"PostToolUse": []}}\n',
    "hooks/check-mthds.sh.j2": "#!/usr/bin/env bash\nexit 0\n",
    "hooks/codex-hooks.json.j2": '{"hooks": {"PostToolUse": []}}\n',
    "hooks/check-mthds-codex.sh.j2": "#!/usr/bin/env bash\nexit 0\n",
    "hooks/vibe-hooks.toml.j2": '[[hooks]]\ntype = "post_tool"\nmatch = "re:^(edit|write_file)$"\ncommand = "./hooks/check-mthds-vibe.sh"\n',
    "hooks/check-mthds-vibe.sh.j2": "#!/usr/bin/env bash\nexit 0\n",
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
        '[vars]\nmarketplace_name = "pipelex-plugins"\nplatform = "claude"\nmcp_server_url = "https://mcp.test/mcp"\n'
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

    def test_claude_plugin_json_declares_mcp_server(self, tmp_path: Path) -> None:
        """The Claude manifest carries the pipelex MCP server with a literal URL —
        the Claude desktop app does no env expansion in plugin MCP config, so a
        ${VAR:-default} wrapper would reach it verbatim and break the connection."""
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "prod")
        plugin_json = make_plugin_json(tree, config)
        assert plugin_json["mcpServers"] == {"pipelex": {"type": "http", "url": "https://mcp.test/mcp"}}

    def test_codex_plugin_json_declares_mcp_server_literal_url(self, tmp_path: Path) -> None:
        """The Codex manifest carries the pipelex MCP server with a literal URL —
        Codex does no env expansion in MCP config; the bare url selects the
        streamable-HTTP transport structurally (verified against Codex 0.144.4)."""
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "codex")
        plugin_json = make_plugin_json(tree, config)
        assert plugin_json["mcpServers"] == {"pipelex": {"url": "https://mcp.test/mcp"}}

    def test_claude_plugin_json_without_mcp_server_url_skips_entry(self, template_tree: Path) -> None:
        """A tree that defines no mcp_server_url gets no mcpServers key."""
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


class TestHookRendering:
    def test_all_platforms_declare_their_hook_templates(self) -> None:
        """Each platform declares its own hook template set."""
        assert set(HOOK_TEMPLATES_BY_PLATFORM) == {Platform.CLAUDE, Platform.CODEX, Platform.MISTRAL_VIBE}
        assert HOOK_TEMPLATES_BY_PLATFORM[Platform.CLAUDE] == ["hooks/hooks.json.j2", "hooks/check-mthds.sh.j2"]
        assert HOOK_TEMPLATES_BY_PLATFORM[Platform.CODEX] == ["hooks/codex-hooks.json.j2", "hooks/check-mthds-codex.sh.j2"]
        assert HOOK_TEMPLATES_BY_PLATFORM[Platform.MISTRAL_VIBE] == ["hooks/vibe-hooks.toml.j2", "hooks/check-mthds-vibe.sh.j2"]

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

    def test_vibe_renders_toml_and_vibe_script(self, tmp_path: Path) -> None:
        tree = _create_codex_tree(tmp_path)
        results = render_templates(tree / "templates", tree, {**DEFAULT_VARS, "platform": "mistral-vibe"})
        output_names = {path.name for path in results}
        assert "vibe-hooks.toml" in output_names
        assert "check-mthds-vibe.sh" in output_names

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
