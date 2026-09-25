"""Tests for scripts/check.py validation checks."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import ClassVar

import pytest

from scripts.check import (
    SKILL_CEILING_CHARS,
    VERSION_FLOOR_STATIC_REFS,
    check_build_error_markers,
    check_codex_marketplace_plugins,
    check_codex_no_claude_artifacts,
    check_credential_wiring,
    check_marketplace_plugins,
    check_matched_target_versions,
    check_no_templates_in_output,
    check_shared_files_exist,
    check_skill_argument_placeholders,
    check_skill_ceiling,
    check_skill_frontmatter,
    check_skill_links,
    check_stale_references,
    check_target_plugin_versions,
    check_version_floors,
    check_vibe_target_artifacts,
    load_version_floors,
    resolve_target_var,
)
from scripts.gen_skill_docs import build_target, list_targets, load_target_config

MARKETPLACE = "pipelex-plugins"

VALID_FRONTMATTER = "---\nname: pipelex-test\ndescription: Test skill\n---\n\n# Test Skill\n"

PLUGIN_JSON_TEMPLATE = '{{\n  "name": "{name}",\n  "version": "{version}"\n}}'
MARKETPLACE_JSON_TEMPLATE = """\
{{
  "name": "pipelex-plugins",
  "metadata": {{
    "version": "{version}"
  }},
  "plugins": {plugins_json}
}}"""

CODEX_MARKETPLACE_JSON_TEMPLATE = """\
{{
  "name": "pipelex-plugins",
  "interface": {{
    "displayName": "Pipelex Plugins"
  }},
  "plugins": {plugins_json}
}}"""


def _write_target_configs(
    base: Path,
    targets: dict[str, dict[str, str]],
    defaults_vars: dict[str, str] | None = None,
) -> None:
    """Write targets/ directory with defaults and per-target configs."""
    targets_dir = base / "targets"
    targets_dir.mkdir(parents=True, exist_ok=True)

    if defaults_vars is None:
        defaults_vars = {"marketplace_name": MARKETPLACE}
    vars_lines = "\n".join(f'{key} = "{value}"' for key, value in defaults_vars.items())
    (targets_dir / "defaults.toml").write_text(f"[vars]\n{vars_lines}\n")

    for target_name, target_info in targets.items():
        (targets_dir / f"{target_name}.toml").write_text(
            f'[plugin]\nname = "{target_info["name"]}"\nversion = "{target_info["version"]}"\nsource = "{target_info.get("source", "./")}"\n'
        )


def _write_plugin_json(base: Path, name: str, version: str, subdir: str = ".") -> None:
    plugin_dir = base / subdir / ".claude-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.json").write_text(PLUGIN_JSON_TEMPLATE.format(name=name, version=version))


def _write_marketplace_json(base: Path, version: str, plugins: list[dict[str, str]]) -> None:
    plugin_dir = base / ".claude-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    plugins_json = json.dumps(plugins)
    (plugin_dir / "marketplace.json").write_text(MARKETPLACE_JSON_TEMPLATE.format(version=version, plugins_json=plugins_json))


def _write_codex_marketplace_json(base: Path, plugins: list[dict[str, object]]) -> None:
    plugin_dir = base / "packaging"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    plugins_json = json.dumps(plugins)
    (plugin_dir / "codex-marketplace.json").write_text(CODEX_MARKETPLACE_JSON_TEMPLATE.format(plugins_json=plugins_json))


@pytest.fixture()
def skill_tree(tmp_path: Path) -> Path:
    """Create a minimal valid skill directory structure with target configs."""
    template_shared = tmp_path / "templates" / "skills" / "shared"
    template_shared.mkdir(parents=True)
    for name in ["writing-mthds.md.j2", "native-content-types.md.j2", "credentials.md.j2", "catalog-id.md.j2"]:
        (template_shared / name).write_text("# placeholder\n")

    (tmp_path / "pipelex" / "skills" / "shared").mkdir(parents=True)
    skill_dir = tmp_path / "pipelex" / "skills" / "pipelex-test"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(VALID_FRONTMATTER)

    _write_target_configs(tmp_path, {"prod": {"name": "pipelex", "version": "0.6.3", "source": "pipelex/"}})
    _write_plugin_json(tmp_path, "pipelex", "0.6.3", "pipelex")
    _write_marketplace_json(tmp_path, "0.6.3", [{"name": "pipelex", "source": "./pipelex"}])

    return tmp_path


class TestTargetPluginVersions:
    def test_versions_consistent(self, skill_tree: Path) -> None:
        errors, versions = check_target_plugin_versions(skill_tree)
        assert errors == []
        assert versions == {"prod": "0.6.3"}

    def test_version_mismatch(self, skill_tree: Path) -> None:
        _write_plugin_json(skill_tree, "pipelex", "0.6.0", "pipelex")
        errors = check_target_plugin_versions(skill_tree)[0]
        assert len(errors) == 1
        assert "0.6.0" in errors[0]
        assert "0.6.3" in errors[0]

    def test_name_mismatch(self, skill_tree: Path) -> None:
        _write_plugin_json(skill_tree, "wrong-name", "0.6.3", "pipelex")
        errors = check_target_plugin_versions(skill_tree)[0]
        assert len(errors) == 1
        assert "wrong-name" in errors[0]

    def test_missing_plugin_json(self, tmp_path: Path) -> None:
        _write_target_configs(tmp_path, {"prod": {"name": "pipelex", "version": "0.6.3", "source": "pipelex/"}})
        errors = check_target_plugin_versions(tmp_path)[0]
        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_mistral_vibe_needs_no_plugin_json(self, tmp_path: Path) -> None:
        """A Mistral Vibe target is manifestless — it must not require a plugin.json."""
        _write_target_configs(tmp_path, {"prod": {"name": "pipelex", "version": "0.6.3", "source": "pipelex/"}})
        _write_plugin_json(tmp_path, "pipelex", "0.6.3", "pipelex")
        (tmp_path / "targets" / "mistral-vibe.toml").write_text(
            '[plugin]\nname = "pipelex-vibe"\nversion = "0.6.3"\nsource = "pipelex-vibe/"\n\n[vars]\nplatform = "mistral-vibe"\n'
        )
        errors, versions = check_target_plugin_versions(tmp_path)
        assert errors == []
        assert versions == {"prod": "0.6.3", "mistral-vibe": "0.6.3"}


class TestMatchedTargetVersions:
    def test_all_targets_match(self, tmp_path: Path) -> None:
        _write_target_configs(
            tmp_path,
            {
                "prod": {"name": "pipelex", "version": "0.8.2", "source": "pipelex/"},
                "codex": {"name": "pipelex", "version": "0.8.2", "source": "pipelex-codex/"},
            },
        )
        (tmp_path / "targets" / "mistral-vibe.toml").write_text(
            '[plugin]\nname = "pipelex-vibe"\nversion = "0.8.2"\nsource = "pipelex-vibe/"\n\n[vars]\nplatform = "mistral-vibe"\n'
        )
        assert check_matched_target_versions(tmp_path) == []

    def test_drift_between_targets(self, tmp_path: Path) -> None:
        _write_target_configs(
            tmp_path,
            {
                "prod": {"name": "pipelex", "version": "0.8.2", "source": "pipelex/"},
                "codex": {"name": "pipelex", "version": "0.1.1", "source": "pipelex-codex/"},
            },
        )
        errors = check_matched_target_versions(tmp_path)
        assert len(errors) == 1
        assert "lockstep" in errors[0]
        assert "prod=0.8.2" in errors[0]
        assert "codex=0.1.1" in errors[0]


class TestMarketplacePlugins:
    def test_matching(self, skill_tree: Path) -> None:
        assert check_marketplace_plugins(skill_tree) == []

    def test_missing_from_marketplace(self, skill_tree: Path) -> None:
        _write_target_configs(
            skill_tree,
            {
                "prod": {"name": "pipelex", "version": "0.6.3", "source": "pipelex/"},
                "codex": {"name": "pipelex-extra", "version": "0.6.3", "source": "pipelex-extra/"},
            },
        )
        errors = check_marketplace_plugins(skill_tree)
        assert len(errors) == 1
        assert "pipelex-extra" in errors[0]
        assert "missing from .claude-plugin/marketplace.json plugins array" in errors[0]

    def test_mistral_vibe_not_required_in_claude_marketplace(self, skill_tree: Path) -> None:
        (skill_tree / "targets" / "mistral-vibe.toml").write_text(
            '[plugin]\nname = "pipelex-vibe"\nversion = "0.6.3"\nsource = "pipelex-vibe/"\n\n[vars]\nplatform = "mistral-vibe"\n'
        )
        assert check_marketplace_plugins(skill_tree) == []

    def test_extra_in_marketplace(self, skill_tree: Path) -> None:
        _write_marketplace_json(
            skill_tree,
            "0.6.3",
            [{"name": "pipelex", "source": "./pipelex"}, {"name": "ghost-plugin", "source": "ghost/"}],
        )
        errors = check_marketplace_plugins(skill_tree)
        assert len(errors) == 1
        assert "ghost-plugin" in errors[0]
        assert "no matching Claude target config" in errors[0]

    def test_marketplace_version_cannot_lag_target_version(self, skill_tree: Path) -> None:
        _write_target_configs(skill_tree, {"prod": {"name": "pipelex", "version": "0.6.4", "source": "pipelex/"}})
        _write_plugin_json(skill_tree, "pipelex", "0.6.4", "pipelex")
        errors = check_marketplace_plugins(skill_tree)
        assert len(errors) == 1
        assert "metadata.version" in errors[0]
        assert "lags behind" in errors[0]

    def test_marketplace_source_must_match_target_path(self, skill_tree: Path) -> None:
        _write_marketplace_json(skill_tree, "0.6.3", [{"name": "pipelex", "source": "pipelex/"}])
        errors = check_marketplace_plugins(skill_tree)
        assert len(errors) == 1
        assert "expected './pipelex'" in errors[0]


class TestCodexMarketplacePlugins:
    def _codex_targets(self, tmp_path: Path) -> None:
        _write_target_configs(
            tmp_path,
            {"codex": {"name": "pipelex", "version": "0.1.0", "source": "pipelex-codex/"}},
            defaults_vars={"marketplace_name": MARKETPLACE, "platform": "codex"},
        )

    def test_matching(self, tmp_path: Path) -> None:
        self._codex_targets(tmp_path)
        _write_codex_marketplace_json(
            tmp_path,
            [
                {
                    "name": "pipelex",
                    "source": {"source": "local", "path": "./pipelex-codex"},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": "Developer Tools",
                }
            ],
        )
        assert check_codex_marketplace_plugins(tmp_path) == []

    def test_missing_authentication(self, tmp_path: Path) -> None:
        self._codex_targets(tmp_path)
        _write_codex_marketplace_json(
            tmp_path,
            [
                {
                    "name": "pipelex",
                    "source": {"source": "local", "path": "./pipelex-codex"},
                    "policy": {"installation": "AVAILABLE"},
                    "category": "Developer Tools",
                }
            ],
        )
        errors = check_codex_marketplace_plugins(tmp_path)
        assert len(errors) == 1
        assert "policy.authentication" in errors[0]

    def test_wrong_source_path(self, tmp_path: Path) -> None:
        self._codex_targets(tmp_path)
        _write_codex_marketplace_json(
            tmp_path,
            [
                {
                    "name": "pipelex",
                    "source": {"source": "local", "path": "./plugins/pipelex"},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": "Developer Tools",
                }
            ],
        )
        errors = check_codex_marketplace_plugins(tmp_path)
        assert len(errors) == 1
        assert "expected './pipelex-codex'" in errors[0]


class TestCodexNoClaudeArtifacts:
    def _codex_output(self, tmp_path: Path) -> Path:
        _write_target_configs(
            tmp_path,
            {"codex": {"name": "pipelex", "version": "0.1.0", "source": "pipelex-codex/"}},
            defaults_vars={"marketplace_name": MARKETPLACE, "platform": "codex"},
        )
        skill_dir = tmp_path / "pipelex-codex" / "skills" / "pipelex-test"
        skill_dir.mkdir(parents=True)
        return skill_dir

    def test_clean_codex_output(self, tmp_path: Path) -> None:
        skill_dir = self._codex_output(tmp_path)
        (skill_dir / "SKILL.md").write_text(VALID_FRONTMATTER)
        assert check_codex_no_claude_artifacts(tmp_path) == []

    def test_detects_claude_plugin_dir(self, tmp_path: Path) -> None:
        self._codex_output(tmp_path)
        (tmp_path / "pipelex-codex" / ".claude-plugin").mkdir(parents=True)
        errors = check_codex_no_claude_artifacts(tmp_path)
        assert any(".claude-plugin" in error for error in errors)

    def test_detects_allowed_tools_in_frontmatter(self, tmp_path: Path) -> None:
        skill_dir = self._codex_output(tmp_path)
        (skill_dir / "SKILL.md").write_text("---\nname: t\nallowed-tools:\n  - Bash\n---\n\nBody.\n")
        errors = check_codex_no_claude_artifacts(tmp_path)
        assert any("allowed-tools" in error for error in errors)


class TestVibeTargetArtifacts:
    def _vibe_targets(self, tmp_path: Path) -> Path:
        """Write a prod + Mistral Vibe target pair and return the Vibe hooks dir."""
        _write_target_configs(tmp_path, {"prod": {"name": "pipelex", "version": "0.1.0", "source": "pipelex/"}})
        (tmp_path / "targets" / "mistral-vibe.toml").write_text(
            '[plugin]\nname = "pipelex-vibe"\nversion = "0.1.0"\nsource = "pipelex-vibe/"\n\n[vars]\nplatform = "mistral-vibe"\n'
        )
        hooks_dir = tmp_path / "pipelex-vibe" / "hooks"
        hooks_dir.mkdir(parents=True)
        return hooks_dir

    VALID_MCP_FRAGMENT = '[[mcp_servers]]\nname = "pipelex"\ntransport = "stdio"\ncommand = "npx"\nargs = ["-y", "@pipelex/mcp@latest"]\n'

    def _write_valid_hooks(self, hooks_dir: Path) -> None:
        (hooks_dir / "vibe-hooks.toml").write_text(
            '[[hooks]]\ntype = "post_tool"\nmatch = "re:^(edit|write_file)$"\ncommand = "./hooks/check-mthds-vibe.sh"\n'
        )
        hook_script = hooks_dir / "check-mthds-vibe.sh"
        hook_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        hook_script.chmod(0o755)
        self._write_mcp_fragment(hooks_dir, self.VALID_MCP_FRAGMENT)

    def _write_mcp_fragment(self, hooks_dir: Path, body: str) -> None:
        mcp_dir = hooks_dir.parent / "mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)
        (mcp_dir / "vibe-mcp.toml").write_text(body)

    def test_matching(self, tmp_path: Path) -> None:
        self._write_valid_hooks(self._vibe_targets(tmp_path))
        assert check_vibe_target_artifacts(tmp_path) == []

    def test_rejects_plugin_manifest(self, tmp_path: Path) -> None:
        hooks_dir = self._vibe_targets(tmp_path)
        self._write_valid_hooks(hooks_dir)
        (tmp_path / "pipelex-vibe" / ".claude-plugin").mkdir(parents=True)
        errors = check_vibe_target_artifacts(tmp_path)
        assert any(".claude-plugin" in error for error in errors)

    def test_requires_post_tool_hook(self, tmp_path: Path) -> None:
        hooks_dir = self._vibe_targets(tmp_path)
        (hooks_dir / "vibe-hooks.toml").write_text('[[hooks]]\ntype = "pre_tool"\n')
        hook_script = hooks_dir / "check-mthds-vibe.sh"
        hook_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        hook_script.chmod(0o755)
        errors = check_vibe_target_artifacts(tmp_path)
        assert any('type = "post_tool"' in error for error in errors)

    def test_missing_hook_config(self, tmp_path: Path) -> None:
        hooks_dir = self._vibe_targets(tmp_path)
        hook_script = hooks_dir / "check-mthds-vibe.sh"
        hook_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        hook_script.chmod(0o755)
        errors = check_vibe_target_artifacts(tmp_path)
        assert any("vibe-hooks.toml missing" in error for error in errors)

    def test_non_executable_script(self, tmp_path: Path) -> None:
        hooks_dir = self._vibe_targets(tmp_path)
        (hooks_dir / "vibe-hooks.toml").write_text(
            '[[hooks]]\ntype = "post_tool"\nmatch = "re:^(edit|write_file)$"\ncommand = "./hooks/check-mthds-vibe.sh"\n'
        )
        (hooks_dir / "check-mthds-vibe.sh").write_text("#!/usr/bin/env bash\n")
        errors = check_vibe_target_artifacts(tmp_path)
        assert any("not executable" in error for error in errors)

    def test_rejects_claude_hook_artifact(self, tmp_path: Path) -> None:
        hooks_dir = self._vibe_targets(tmp_path)
        self._write_valid_hooks(hooks_dir)
        (hooks_dir / "check-mthds.sh").write_text("#!/usr/bin/env bash\n")
        errors = check_vibe_target_artifacts(tmp_path)
        assert any("not a Vibe artifact" in error for error in errors)

    def test_missing_mcp_fragment(self, tmp_path: Path) -> None:
        hooks_dir = self._vibe_targets(tmp_path)
        self._write_valid_hooks(hooks_dir)
        (hooks_dir.parent / "mcp" / "vibe-mcp.toml").unlink()
        errors = check_vibe_target_artifacts(tmp_path)
        assert any("mcp/vibe-mcp.toml missing" in error for error in errors)

    def test_mcp_fragment_must_be_stdio(self, tmp_path: Path) -> None:
        hooks_dir = self._vibe_targets(tmp_path)
        self._write_valid_hooks(hooks_dir)
        self._write_mcp_fragment(hooks_dir, '[[mcp_servers]]\nname = "pipelex"\ntransport = "streamable-http"\nurl = "https://example.com/mcp"\n')
        errors = check_vibe_target_artifacts(tmp_path)
        assert any('transport = "stdio"' in error for error in errors)
        assert any("must set a command" in error for error in errors)

    def test_mcp_fragment_keeps_the_server_name(self, tmp_path: Path) -> None:
        hooks_dir = self._vibe_targets(tmp_path)
        self._write_valid_hooks(hooks_dir)
        self._write_mcp_fragment(hooks_dir, self.VALID_MCP_FRAGMENT.replace('"pipelex"', '"pipelex-local"'))
        errors = check_vibe_target_artifacts(tmp_path)
        assert any('must name the server "pipelex"' in error for error in errors)

    def test_mcp_fragment_declares_exactly_one_server(self, tmp_path: Path) -> None:
        hooks_dir = self._vibe_targets(tmp_path)
        self._write_valid_hooks(hooks_dir)
        self._write_mcp_fragment(hooks_dir, self.VALID_MCP_FRAGMENT * 2)
        errors = check_vibe_target_artifacts(tmp_path)
        assert any("exactly one [[mcp_servers]] entry" in error for error in errors)

    def test_mcp_fragment_must_parse(self, tmp_path: Path) -> None:
        hooks_dir = self._vibe_targets(tmp_path)
        self._write_valid_hooks(hooks_dir)
        self._write_mcp_fragment(hooks_dir, "[[mcp_servers]\nname = \n")
        errors = check_vibe_target_artifacts(tmp_path)
        assert any("not valid TOML" in error for error in errors)


class TestCredentialWiring:
    """Each generated target must carry the credential wiring `targets/defaults.toml` declares.

    The expectation comes from the defaults, never from a target's merged variables: a target whose
    override lost `env_vars` or `user_config` renders files that agree with it, so the freshness
    check passes them. The trees below are the real targets rendered from the real templates.
    """

    REPO_ROOT = Path(__file__).parents[2]
    DEV_OVERRIDE = '\n[vars.mcp_server]\ncommand = "node"\nargs = ["../pipelex-mcp/packages/workshop/dist/main.js"]\n'

    def _built_tree(self, tmp_path: Path, override: str = "") -> Path:
        """The repository's targets, `override` appended to each, built from its templates into `tmp_path`."""
        targets = tmp_path / "targets"
        shutil.copytree(self.REPO_ROOT / "targets", targets)
        for name in list_targets(targets):
            with (targets / f"{name}.toml").open("a", encoding="utf-8") as target_toml:
                target_toml.write(override)
            config = load_target_config(targets, name)
            for path, content in build_target(self.REPO_ROOT, config, dry_run=True).files.items():
                if path.name == "check.mjs":
                    continue  # the vendored bundle carries no credential wiring, and weighs megabytes
                destination = tmp_path / path.relative_to(self.REPO_ROOT)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content, encoding="utf-8")
        return tmp_path

    def test_the_built_targets_carry_the_wiring(self, tmp_path: Path) -> None:
        assert check_credential_wiring(self._built_tree(tmp_path)) == []

    def test_the_dev_override_on_every_target_keeps_the_wiring(self, tmp_path: Path) -> None:
        """A table override used to replace the defaults' whole: the Claude manifest lost its
        `userConfig` and launcher, the Codex manifest its forwarded names, the Vibe fragment its
        `env` keys, and the hook and launcher their promotions, with every check green."""
        assert check_credential_wiring(self._built_tree(tmp_path, self.DEV_OVERRIDE)) == []

    @pytest.mark.parametrize(
        ("generated", "old", "new", "expected"),
        [
            ("pipelex/.claude-plugin/plugin.json", '"userConfig"', '"userConfigGone"', "userConfig offers no `api_key` option"),
            ("pipelex/.claude-plugin/plugin.json", '"sensitive": true', '"sensitive": false', "userConfig `api_key` is no longer sensitive"),
            ("pipelex/.claude-plugin/plugin.json", '"${CLAUDE_PLUGIN_ROOT}/hooks/launch-pipelex-mcp.sh"', '"npx"', "does not spawn"),
            ("pipelex/.claude-plugin/plugin.json", '"PIPELEX_PLUGIN_BASE_URL"', '"PIPELEX_BASE_URL"', "does not set PIPELEX_PLUGIN_BASE_URL"),
            (
                "pipelex/hooks/check-mthds.sh",
                'export PIPELEX_API_KEY="$CLAUDE_PLUGIN_OPTION_API_KEY"',
                ": dropped",
                "hooks/check-mthds.sh: does not promote CLAUDE_PLUGIN_OPTION_API_KEY to PIPELEX_API_KEY",
            ),
            (
                "pipelex/hooks/launch-pipelex-mcp.sh",
                'if [[ -n "${PIPELEX_PLUGIN_API_KEY:-}" ]]; then',
                "if true; then",
                "hooks/launch-pipelex-mcp.sh: does not promote PIPELEX_PLUGIN_API_KEY to PIPELEX_API_KEY when it is non-empty",
            ),
            ("pipelex-codex/.codex-plugin/plugin.json", '"env_vars"', '"env_vars_gone"', "forwards no PIPELEX_API_KEY, PIPELEX_BASE_URL"),
            ("pipelex-vibe/mcp/vibe-mcp.toml", 'PIPELEX_API_KEY = ""\n', "", "the env table has no `PIPELEX_API_KEY` key"),
            ("pipelex-vibe/mcp/vibe-mcp.toml", 'PIPELEX_API_KEY = ""', 'PIPELEX_API_KEY = "sk-baked"', "ships a value for `PIPELEX_API_KEY`"),
        ],
    )
    def test_a_target_that_lost_its_wiring_fails(self, tmp_path: Path, generated: str, old: str, new: str, expected: str) -> None:
        tree = self._built_tree(tmp_path)
        path = tree / generated
        text = path.read_text(encoding="utf-8")
        assert old in text, f"the fixture no longer renders {old!r} in {generated}"
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        errors = check_credential_wiring(tree)
        assert any(expected in error and generated in error for error in errors), errors

    def test_defaults_without_a_launcher_expect_nothing(self, skill_tree: Path) -> None:
        assert check_credential_wiring(skill_tree) == []


class TestResolveTargetVar:
    def test_default_value(self, skill_tree: Path) -> None:
        assert resolve_target_var(skill_tree, "prod", "marketplace_name") == MARKETPLACE

    def test_override_value(self, skill_tree: Path) -> None:
        (skill_tree / "targets" / "prod.toml").write_text(
            '[plugin]\nname = "pipelex"\nversion = "0.6.3"\nsource = "pipelex/"\n\n[vars]\nmarketplace_name = "custom"\n'
        )
        assert resolve_target_var(skill_tree, "prod", "marketplace_name") == "custom"

    def test_missing_var(self, skill_tree: Path) -> None:
        with pytest.raises(ValueError, match="not defined"):
            resolve_target_var(skill_tree, "prod", "nonexistent_var")

    def test_missing_target(self, skill_tree: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            resolve_target_var(skill_tree, "nonexistent", "marketplace_name")


class TestStaleReferences:
    def test_no_stale_refs(self, skill_tree: Path) -> None:
        assert check_stale_references(skill_tree) == []

    @pytest.mark.parametrize(
        "ref_path",
        [
            "references/writing-mthds.md",
            "references/native-content-types",
        ],
    )
    def test_detects_stale_ref(self, skill_tree: Path, ref_path: str) -> None:
        skill_md = skill_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + f"\nSee [ref]({ref_path})\n")
        errors = check_stale_references(skill_tree)
        assert len(errors) == 1
        assert "stale references/" in errors[0]

    def test_ignores_correct_shared_path(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nSee [ref](../shared/writing-mthds.md)\n")
        assert check_stale_references(skill_tree) == []


class TestBuildErrorMarkers:
    """A partial that selects one of several blocks by a parameter's value ends its chain in an
    `{% else %}` emitting `PIPELEX_BUILD_ERROR`, so a value that names no branch fails the check.
    An unset or misspelled parameter name never gets that far: the renderer's `StrictUndefined`
    fails the build on it. Without the marker, a wrong value would drop the block from the output
    with the build, the freshness check and the tests all green."""

    MARKER_LINE = 'PIPELEX_BUILD_ERROR: stale_types_variant must be one of edit, design, organize — got "edti"'

    def test_clean_tree(self, skill_tree: Path) -> None:
        assert check_build_error_markers(skill_tree) == []

    def test_reports_the_marker_with_its_line(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + f"\n{self.MARKER_LINE}\n")
        errors = check_build_error_markers(skill_tree)
        assert len(errors) == 1
        assert "SKILL.md:8" in errors[0]
        assert "edti" in errors[0]

    @pytest.mark.parametrize(
        "generated", ["skills/shared/writing-mthds.md", "hooks/check-mthds.sh", "mcp/vibe-mcp.toml", ".claude-plugin/plugin.json"]
    )
    def test_every_generated_file_is_read_not_only_the_skills(self, skill_tree: Path, generated: str) -> None:
        """The check read `SKILL.md` alone while its account said any generated file: a shared
        reference, a hook script and the MCP fragment are rendered from templates too."""
        path = skill_tree / "pipelex" / generated
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"first line\n{self.MARKER_LINE}\n", encoding="utf-8")
        assert check_build_error_markers(skill_tree) == [f"pipelex/{generated}:2: {self.MARKER_LINE}"]

    def test_a_binary_file_is_skipped_rather_than_failing_the_check(self, skill_tree: Path) -> None:
        (skill_tree / "pipelex" / "hooks").mkdir()
        (skill_tree / "pipelex" / "hooks" / "engine.wasm").write_bytes(b"\x00asm\xff\xfe\x80")
        assert check_build_error_markers(skill_tree) == []


class TestSkillArgumentPlaceholders:
    def test_clean_tree(self, skill_tree: Path) -> None:
        assert check_skill_argument_placeholders(skill_tree) == []

    @pytest.mark.parametrize(
        ("line", "token"),
        [
            ('stop_tree() { kill -STOP "$1" 2>/dev/null; }', "$1"),
            ("awk 'NR > 1 { print $9 }'", "$9"),
            ('echo "$0"', "$0"),
            ('set -- "$10"', "$10"),
            ("Summarize $ARGUMENTS.", "$ARGUMENTS"),
            ("Open $ARGUMENTS[0] first.", "$ARGUMENTS"),
            (r'kill "\$1"', "$1"),
            ('echo "$1x"', "$1"),
        ],
        ids=["quoted", "awk-field", "zero", "two-digits", "arguments", "indexed", "escaped", "word-suffix"],
    )
    def test_detects_placeholder(self, skill_tree: Path, line: str, token: str) -> None:
        skill_md = skill_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + f"\n```bash\n{line}\n```\n")
        errors = check_skill_argument_placeholders(skill_tree)
        assert len(errors) == 1
        assert errors[0].startswith("pipelex/skills/pipelex-test/SKILL.md:9: ")
        assert f"`{token}`" in errors[0]

    def test_reports_every_token_on_a_line(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + '\nfor child in $(pgrep -P "$1"); do stop_tree "$2"; done\n')
        errors = check_skill_argument_placeholders(skill_tree)
        assert [error.split("`")[1] for error in errors] == ["$1", "$2"]

    def test_ignores_shell_tokens_claude_code_leaves_alone(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md"
        skill_md.write_text(
            VALID_FRONTMATTER
            + "\n```bash\n"
            + 'launcher=$!; echo $$ "$?" "$pid" "${APP_PORT:-4300}" "${5#APP_HOST=}" "$((n + 1))" "$(pwd)"\n'
            + 'stop_tree() { local p; for p; do kill -STOP "$p"; done; }\n'
            + "```\n"
        )
        assert check_skill_argument_placeholders(skill_tree) == []

    def test_ignores_reference_files(self, skill_tree: Path) -> None:
        """A tool reads references and shared files as they are, so Claude Code substitutes nothing in them."""
        references = skill_tree / "pipelex" / "skills" / "pipelex-test" / "references"
        references.mkdir()
        (references / "recipes.md").write_text("Dollar amounts (`$100`) and `print $9`.\n")
        (skill_tree / "pipelex" / "skills" / "shared" / "writing-mthds.md").write_text("Dollar amounts (`$100`).\n")
        assert check_skill_argument_placeholders(skill_tree) == []

    def test_scans_every_target(self, skill_tree: Path) -> None:
        _write_target_configs(
            skill_tree,
            {
                "prod": {"name": "pipelex", "version": "0.6.3", "source": "pipelex/"},
                "codex": {"name": "pipelex", "version": "0.6.3", "source": "pipelex-codex/"},
            },
        )
        codex_skill = skill_tree / "pipelex-codex" / "skills" / "pipelex-test"
        codex_skill.mkdir(parents=True)
        (codex_skill / "SKILL.md").write_text(VALID_FRONTMATTER + "\nRun it with $ARGUMENTS.\n")
        errors = check_skill_argument_placeholders(skill_tree)
        assert len(errors) == 1
        assert errors[0].startswith("pipelex-codex/skills/pipelex-test/SKILL.md:")


class TestVersionFloors:
    """The floors the skills state to the user live in one table, and this rule is what
    keeps a bump to that table from being a half-bump.

    A misspelled key is the renderer's to catch, not this rule's: the build runs under
    `StrictUndefined`, so `{{ floors.typo }}` fails naming the template and the
    attribute rather than rendering as the empty string. What is left here is drift of
    two other kinds — a floor that reaches no built skill at all, and a static reference
    under `skills/`, copied verbatim into every target and never rendered, whose literal
    no longer matches the table.
    """

    FLOORS = '[vars]\nmarketplace_name = "pipelex-plugins"\n\n[vars.floors]\npipelex_sdk_js = "0.18.0"\nnode = "22.12"\n'

    def _tree(self, tmp_path: Path, *, floors: str | None = None, typescript: str | None = None) -> Path:
        _write_target_configs(tmp_path, {"prod": {"name": "pipelex", "version": "0.6.3", "source": "pipelex/"}})
        (tmp_path / "targets" / "defaults.toml").write_text(self.FLOORS if floors is None else floors)
        skill_dir = tmp_path / "pipelex" / "skills" / "pipelex-integrate"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(VALID_FRONTMATTER + "\nAt least `@pipelex/sdk` 0.18.0 on Node 22.12.\n")
        reference = tmp_path / "skills" / "pipelex-integrate" / "references"
        reference.mkdir(parents=True)
        body = (
            typescript
            if typescript is not None
            else "the SDK facts were checked against `@pipelex/sdk` 0.18.0, the floor the skill's step 8 installs\n"
        )
        (reference / "typescript.md").write_text(body)
        return tmp_path

    def test_a_floor_that_reaches_the_output_and_its_reference_passes(self, tmp_path: Path) -> None:
        tree = self._tree(tmp_path)
        errors = [e for e in check_version_floors(tree) if "typescript.md" in e or "pipelex" in e]
        assert [e for e in errors if "0.18.0" in e or "22.12" in e] == []

    def test_a_floor_no_built_skill_states_any_more_is_caught(self, tmp_path: Path) -> None:
        """A skill reworded until the number fell out of it still reads as well-formed
        prose, and the table entry still reads as current. The floor reaching no built
        skill at all is the only evidence left that the two have parted."""
        tree = self._tree(tmp_path)
        skill_md = tree / "pipelex" / "skills" / "pipelex-integrate" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nAt least `@pipelex/sdk`  on Node 22.12.\n")
        errors = check_version_floors(tree)
        assert any("floor `pipelex_sdk_js` = 0.18.0 reaches no generated skill" in error for error in errors)

    def test_a_static_reference_left_behind_by_a_bump_is_named_with_its_line(self, tmp_path: Path) -> None:
        tree = self._tree(tmp_path)
        floors = self.FLOORS.replace('pipelex_sdk_js = "0.18.0"', 'pipelex_sdk_js = "0.19.0"')
        (tree / "targets" / "defaults.toml").write_text(floors)
        skill_md = tree / "pipelex" / "skills" / "pipelex-integrate" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nAt least `@pipelex/sdk` 0.19.0 on Node 22.12.\n")
        errors = check_version_floors(tree)
        assert any("typescript.md:1: states 0.18.0 for floor `pipelex_sdk_js`, but [vars.floors] says 0.19.0" in error for error in errors)

    def test_a_reworded_reference_fails_rather_than_passing_silently(self, tmp_path: Path) -> None:
        """A pattern that no longer matches means nobody is holding that sentence to the
        table any more, which must not read as a clean check."""
        tree = self._tree(tmp_path, typescript="the SDK facts were checked against version 0.18.0 of the SDK\n")
        errors = check_version_floors(tree)
        assert any("was reworded" in error and "typescript.md" in error for error in errors)

    def test_a_template_that_spells_a_floor_instead_of_reading_it_is_caught(self, tmp_path: Path) -> None:
        """The regression the first round of this branch fixed by hand, and the one drift
        neither other part can see: strict rendering fires on an expression that is there
        and misspelled, never on one somebody replaced with its own value, and the presence
        check is satisfied by any other sentence that still reads the table."""
        tree = self._tree(tmp_path)
        template = tree / "templates" / "skills" / "pipelex-integrate"
        template.mkdir(parents=True)
        (template / "SKILL.md.j2").write_text("Install `@pipelex/sdk` 0.18.0 or later.\n")
        errors = check_version_floors(tree)
        assert any("SKILL.md.j2:1: spells floor `pipelex_sdk_js` as the literal 0.18.0" in error for error in errors)

    def test_a_template_reading_the_table_is_not_a_hardcoded_floor(self, tmp_path: Path) -> None:
        tree = self._tree(tmp_path)
        template = tree / "templates" / "skills" / "pipelex-integrate"
        template.mkdir(parents=True)
        (template / "SKILL.md.j2").write_text("Install `@pipelex/sdk` {{ floors.pipelex_sdk_js }} or later.\n")
        assert [error for error in check_version_floors(tree) if "spells floor" in error] == []

    def test_an_empty_table_is_a_failure_rather_than_nothing_to_check(self, tmp_path: Path) -> None:
        tree = self._tree(tmp_path, floors='[vars]\nmarketplace_name = "pipelex-plugins"\n')
        errors = check_version_floors(tree)
        assert len(errors) == 1
        assert "[vars.floors] is missing or empty" in errors[0]

    # A number under `skills/` that equals a floor and means something else entirely. Such
    # numbers are the reason the anchors are written against prose instead of swept
    # numerically, and naming them here is what lets the sweep below refuse every other
    # stray match.
    UNRELATED_FLOOR_LOOKALIKES: ClassVar[set[tuple[str, str]]] = {
        ("skills/pipelex-synthetic-inputs/references/png.md", "3.11"),
    }

    def test_every_static_statement_of_a_floor_is_anchored(self) -> None:
        """The anchors are a hand-kept list, so the way this rule fails is by omission:
        somebody states a floor in a file nothing renders, nobody adds the entry, and the
        next bump moves the table while that sentence keeps the old number — with the
        whole check still green, which is worse than not having it.

        So sweep the static tree for each floor's literal value and require every
        occurrence to be either anchored or listed above as meaning something else. A new
        unrelated number fails this too, deliberately: somebody has to look.
        """
        repo_root = Path(__file__).parents[2]
        floors = load_version_floors(repo_root)

        unanchored: list[str] = []
        for source in sorted((repo_root / "skills").rglob("*")):
            if not source.is_file():
                continue
            rel = source.relative_to(repo_root).as_posix()
            try:
                text = source.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            # The spans the anchors on this file actually capture. Occurrence level, not
            # file level: `typescript.md` stated the JS floor in two places with only the
            # first anchored, which a file-level sweep would have called covered.
            captured = [
                match.span(1) for rel_path, pattern, _key in VERSION_FLOOR_STATIC_REFS if rel_path == rel for match in re.finditer(pattern, text)
            ]

            for key, value in sorted(floors.items()):
                if (rel, value) in self.UNRELATED_FLOOR_LOOKALIKES:
                    continue
                start = text.find(value)
                while start != -1:
                    if not any(span_start <= start and start + len(value) <= span_end for span_start, span_end in captured):
                        line = text[:start].count("\n") + 1
                        unanchored.append(f"{rel}:{line} states floor `{key}` = {value}, but no VERSION_FLOOR_STATIC_REFS entry captures it")
                    start = text.find(value, start + 1)

        assert unanchored == []


class TestSharedFilesExist:
    def test_all_present(self, skill_tree: Path) -> None:
        assert check_shared_files_exist(skill_tree) == []

    def test_missing_file(self, skill_tree: Path) -> None:
        (skill_tree / "templates" / "skills" / "shared" / "writing-mthds.md.j2").unlink()
        errors = check_shared_files_exist(skill_tree)
        assert len(errors) == 1
        assert "writing-mthds.md.j2" in errors[0]

    def test_all_missing(self, tmp_path: Path) -> None:
        (tmp_path / "templates" / "skills" / "shared").mkdir(parents=True)
        errors = check_shared_files_exist(tmp_path)
        assert len(errors) == len(["writing-mthds.md.j2", "native-content-types.md.j2", "credentials.md.j2", "catalog-id.md.j2"])


class TestNoTemplatesInOutput:
    def test_clean_state(self, skill_tree: Path) -> None:
        assert check_no_templates_in_output(skill_tree) == []

    def test_detects_leaked_j2_in_skills(self, skill_tree: Path) -> None:
        (skill_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md.j2").write_text("leaked\n")
        errors = check_no_templates_in_output(skill_tree)
        assert len(errors) == 1
        assert "LEAKED TEMPLATE" in errors[0]

    def test_detects_leaked_j2_in_target_dir(self, skill_tree: Path) -> None:
        _write_target_configs(
            skill_tree,
            {
                "prod": {"name": "pipelex", "version": "0.6.3", "source": "pipelex/"},
                "codex": {"name": "pipelex", "version": "0.6.3", "source": "pipelex-codex/"},
            },
        )
        target_skills = skill_tree / "pipelex-codex" / "skills" / "pipelex-test"
        target_skills.mkdir(parents=True)
        (target_skills / "SKILL.md.j2").write_text("leaked\n")
        errors = check_no_templates_in_output(skill_tree)
        assert len(errors) == 1
        assert "pipelex-codex" in errors[0]
        assert "LEAKED TEMPLATE" in errors[0]

    @pytest.mark.parametrize("leaked", ["pipelex/mcp/vibe-mcp.toml.j2", "pipelex/.claude-plugin/plugin.json.j2", "mcp/vibe-mcp.toml.j2"])
    def test_detects_leaked_j2_outside_skills_and_hooks(self, skill_tree: Path, leaked: str) -> None:
        """A target's whole directory is output, `mcp/` included, and the root's `mcp/` is where a root target renders its fragment."""
        path = skill_tree / leaked
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("leaked\n")
        assert check_no_templates_in_output(skill_tree) == [f"LEAKED TEMPLATE: {leaked} (should be in templates/)"]

    def test_missing_targets_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Targets directory not found"):
            check_no_templates_in_output(tmp_path)


class TestSkillFrontmatter:
    """Mistral Vibe drops a skill whose frontmatter strict YAML rejects, so `make check` parses it the same way."""

    def test_a_valid_frontmatter_passes(self, skill_tree: Path) -> None:
        assert check_skill_frontmatter(skill_tree) == []

    def test_a_colon_in_an_unquoted_description_fails(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md"
        skill_md.write_text("---\nname: pipelex-test\ndescription: Design a method. Construction is adaptive: a graph is written.\n---\n\n# Test\n")
        errors = check_skill_frontmatter(skill_tree)
        assert len(errors) == 1
        assert "not valid YAML" in errors[0]
        assert "Mistral Vibe drops this skill" in errors[0]

    def test_the_name_must_be_the_skill_directory(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md"
        skill_md.write_text("---\nname: pipelex-other\ndescription: A test.\n---\n")
        assert check_skill_frontmatter(skill_tree) == [
            "pipelex/skills/pipelex-test/SKILL.md: frontmatter `name` is 'pipelex-other', not the skill's directory 'pipelex-test'"
        ]

    def test_a_missing_description_or_block_fails(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md"
        skill_md.write_text("---\nname: pipelex-test\n---\n")
        assert check_skill_frontmatter(skill_tree) == ["pipelex/skills/pipelex-test/SKILL.md: frontmatter carries no string `description`"]
        skill_md.write_text("# No frontmatter\n")
        assert check_skill_frontmatter(skill_tree) == ["pipelex/skills/pipelex-test/SKILL.md: no `---` frontmatter block at the top"]


class TestSkillCeiling:
    """Box C of the size diet: every rendered SKILL.md fits in what a compaction keeps."""

    def test_a_skill_under_the_ceiling_is_not_reported(self, skill_tree: Path) -> None:
        assert check_skill_ceiling(skill_tree) == []

    def test_a_skill_over_the_ceiling_is_named_with_its_size(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "x" * SKILL_CEILING_CHARS)
        over = check_skill_ceiling(skill_tree)
        assert len(over) == 1
        assert "pipelex-test/SKILL.md" in over[0]
        assert f"{len(VALID_FRONTMATTER)} over" in over[0]

    def test_the_ceiling_counts_the_whole_file(self, skill_tree: Path) -> None:
        """The frontmatter counts: the check measures the rendered file, which is conservative."""
        skill_md = skill_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md"
        skill_md.write_text("x" * SKILL_CEILING_CHARS)
        assert check_skill_ceiling(skill_tree) == []
        skill_md.write_text("x" * (SKILL_CEILING_CHARS + 1))
        assert len(check_skill_ceiling(skill_tree)) == 1


class TestSkillLinks:
    """Box H of the size diet: pointers resolve, and nothing shipped is named by nothing."""

    @staticmethod
    def _skill(base: Path) -> Path:
        return base / "pipelex" / "skills" / "pipelex-test"

    @staticmethod
    def _shared_named(base: Path) -> None:
        """Give the fixture's shared files a skill that names them, so they do not trip the backward check."""
        shared = base / "pipelex" / "skills" / "shared"
        (shared / "writing-mthds.md").write_text("# MTHDS\n\n## PipeLLM\n")
        skill_md = base / "pipelex" / "skills" / "pipelex-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nSee [the reference](../shared/writing-mthds.md).\n")

    def test_the_fixture_is_clean(self, skill_tree: Path) -> None:
        self._shared_named(skill_tree)
        assert check_skill_links(skill_tree) == []

    def test_a_link_to_a_missing_reference_fails(self, skill_tree: Path) -> None:
        self._shared_named(skill_tree)
        skill_md = self._skill(skill_tree) / "SKILL.md"
        skill_md.write_text(skill_md.read_text() + "On a refresh, read [references/refresh.md](references/refresh.md) first.\n")
        errors = check_skill_links(skill_tree)
        assert any("references/refresh.md" in error and "names no file" in error for error in errors), errors

    def test_an_anchor_must_name_a_heading(self, skill_tree: Path) -> None:
        self._shared_named(skill_tree)
        skill_md = self._skill(skill_tree) / "SKILL.md"
        skill_md.write_text(
            skill_md.read_text()
            + "## Step 8 — a method that is not on disk\n\n"
            + "See [step 8](#step-8--a-method-that-is-not-on-disk) and [gone](#gone) and [LLM](../shared/writing-mthds.md#pipellm).\n"
        )
        errors = check_skill_links(skill_tree)
        assert errors == ["pipelex/skills/pipelex-test/SKILL.md: anchor `#gone` names no heading of SKILL.md"], errors

    def test_a_reference_named_by_nothing_fails(self, skill_tree: Path) -> None:
        self._shared_named(skill_tree)
        references = self._skill(skill_tree) / "references"
        references.mkdir()
        (references / "orphan.md").write_text("# Orphan\n")
        errors = check_skill_links(skill_tree)
        assert any("references/orphan.md" in error and "named by nothing" in error for error in errors), errors

    def test_a_reference_named_only_by_another_reference_fails(self, skill_tree: Path) -> None:
        """References are one level deep: a reference reached only through another is never read on a branch."""
        self._shared_named(skill_tree)
        references = self._skill(skill_tree) / "references"
        references.mkdir()
        (references / "first.md").write_text("# First\n\nThen read [second](second.md).\n")
        (references / "second.md").write_text("# Second\n")
        skill_md = self._skill(skill_tree) / "SKILL.md"
        skill_md.write_text(skill_md.read_text() + "On a refresh, read [references/first.md](references/first.md) first.\n")
        errors = check_skill_links(skill_tree)
        assert [error for error in errors if "named by nothing" in error] == [
            "pipelex/skills/pipelex-test/references/second.md: shipped but named by nothing the model reads"
        ], errors

    def test_a_script_is_named_by_its_path_in_the_skill_or_a_reference(self, skill_tree: Path) -> None:
        self._shared_named(skill_tree)
        scripts = self._skill(skill_tree) / "scripts"
        scripts.mkdir()
        (scripts / "acquire.sh").write_text("#!/bin/sh\n")
        (scripts / "env-file.sh").write_text("#!/bin/sh\n")
        (scripts / "unused.sh").write_text("#!/bin/sh\n")
        references = self._skill(skill_tree) / "references"
        references.mkdir()
        (references / "branch.md").write_text("# Branch\n\nRun `${CLAUDE_SKILL_DIR}/scripts/env-file.sh`.\n")
        skill_md = self._skill(skill_tree) / "SKILL.md"
        skill_md.write_text(
            skill_md.read_text()
            + "Run `${CLAUDE_SKILL_DIR}/scripts/acquire.sh <dir>`. On branch B, read [references/branch.md](references/branch.md).\n"
        )
        errors = check_skill_links(skill_tree)
        assert errors == ["pipelex/skills/pipelex-test/scripts/unused.sh: shipped but named by nothing the model reads"], errors

    def test_a_shared_file_named_by_nothing_fails(self, skill_tree: Path) -> None:
        self._shared_named(skill_tree)
        (skill_tree / "pipelex" / "skills" / "shared" / "credentials.md").write_text("# Credentials\n")
        errors = check_skill_links(skill_tree)
        assert errors == ["pipelex/skills/shared/credentials.md: shipped but named by no skill and no reference"], errors

    def test_a_link_inside_code_is_an_example_not_a_pointer(self, skill_tree: Path) -> None:
        self._shared_named(skill_tree)
        skill_md = self._skill(skill_tree) / "SKILL.md"
        skill_md.write_text(skill_md.read_text() + "```md\n[x](references/nope.md)\n```\n\nInline `[y](references/nope.md)` too.\n")
        assert check_skill_links(skill_tree) == []

    def test_an_indented_or_longer_fence_is_code_too(self, skill_tree: Path) -> None:
        """A list item indents its fences, and a four-backtick fence wraps a three-backtick example."""
        self._shared_named(skill_tree)
        skill_md = self._skill(skill_tree) / "SKILL.md"
        skill_md.write_text(
            skill_md.read_text()
            + "1. Write it:\n\n   ```ts\n   handlers[kind](payload)\n   ```\n\n"
            + "````md\n```ts\n[x](references/nope.md)\n```\n[y](references/gone.md)\n````\n\nAfter the fence.\n"
        )
        assert check_skill_links(skill_tree) == []

    def test_an_anchor_keeps_the_text_of_inline_code(self, skill_tree: Path) -> None:
        self._shared_named(skill_tree)
        skill_md = self._skill(skill_tree) / "SKILL.md"
        skill_md.write_text(
            skill_md.read_text()
            + "### Step 5 — `mthds_run`, and print the run id first\n\n"
            + "See [step 5](#step-5--mthds_run-and-print-the-run-id-first) and [wrong](#step-5---and-print-the-run-id-first).\n"
        )
        errors = check_skill_links(skill_tree)
        assert errors == ["pipelex/skills/pipelex-test/SKILL.md: anchor `#step-5---and-print-the-run-id-first` names no heading of SKILL.md"], errors

    def test_a_repeated_heading_takes_a_numbered_anchor(self, skill_tree: Path) -> None:
        self._shared_named(skill_tree)
        skill_md = self._skill(skill_tree) / "SKILL.md"
        skill_md.write_text(
            skill_md.read_text()
            + "## Prerequisites\n\n## Prerequisites\n\n"
            + "See [A](#prerequisites), [B](#prerequisites-1) and [none](#prerequisites-2).\n"
        )
        errors = check_skill_links(skill_tree)
        assert errors == ["pipelex/skills/pipelex-test/SKILL.md: anchor `#prerequisites-2` names no heading of SKILL.md"], errors

    def test_a_link_leaving_the_target_fails(self, skill_tree: Path) -> None:
        """A file outside the target exists here but not in the installed plugin, so the link fails there."""
        self._shared_named(skill_tree)
        (skill_tree / "README.md").write_text("# Readme\n")
        skill_md = self._skill(skill_tree) / "SKILL.md"
        skill_md.write_text(skill_md.read_text() + "See [the readme](../../../README.md).\n")
        errors = check_skill_links(skill_tree)
        assert errors == [
            "pipelex/skills/pipelex-test/SKILL.md: link to `../../../README.md` leaves the target, whose installed copy does not carry it"
        ], errors

    def test_a_script_named_by_a_nested_reference_is_named(self, skill_tree: Path) -> None:
        self._shared_named(skill_tree)
        scripts = self._skill(skill_tree) / "scripts"
        scripts.mkdir()
        (scripts / "probe.sh").write_text("#!/bin/sh\n")
        nested = self._skill(skill_tree) / "references" / "sub"
        nested.mkdir(parents=True)
        (nested / "x.md").write_text("# X\n\nRun `${CLAUDE_SKILL_DIR}/scripts/probe.sh`.\n")
        skill_md = self._skill(skill_tree) / "SKILL.md"
        skill_md.write_text(skill_md.read_text() + "On a branch, read [references/sub/x.md](references/sub/x.md).\n")
        assert check_skill_links(skill_tree) == []
