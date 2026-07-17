"""Tests for scripts/check.py validation checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.check import (
    check_codex_marketplace_plugins,
    check_codex_no_claude_artifacts,
    check_marketplace_plugins,
    check_matched_target_versions,
    check_no_templates_in_output,
    check_shared_files_exist,
    check_stale_references,
    check_target_plugin_versions,
    check_vibe_target_artifacts,
    resolve_target_var,
)

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
    for name in ["mthds-reference.md.j2", "native-content-types.md.j2"]:
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

    def _write_valid_hooks(self, hooks_dir: Path) -> None:
        (hooks_dir / "vibe-hooks.toml").write_text(
            '[[hooks]]\ntype = "after_tool"\nmatch = "re:^(edit|write_file)$"\ncommand = "./hooks/check-mthds-vibe.sh"\n'
        )
        hook_script = hooks_dir / "check-mthds-vibe.sh"
        hook_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        hook_script.chmod(0o755)

    def test_matching(self, tmp_path: Path) -> None:
        self._write_valid_hooks(self._vibe_targets(tmp_path))
        assert check_vibe_target_artifacts(tmp_path) == []

    def test_rejects_plugin_manifest(self, tmp_path: Path) -> None:
        hooks_dir = self._vibe_targets(tmp_path)
        self._write_valid_hooks(hooks_dir)
        (tmp_path / "pipelex-vibe" / ".claude-plugin").mkdir(parents=True)
        errors = check_vibe_target_artifacts(tmp_path)
        assert any(".claude-plugin" in error for error in errors)

    def test_requires_after_tool_hook(self, tmp_path: Path) -> None:
        hooks_dir = self._vibe_targets(tmp_path)
        (hooks_dir / "vibe-hooks.toml").write_text('[[hooks]]\ntype = "before_tool"\n')
        hook_script = hooks_dir / "check-mthds-vibe.sh"
        hook_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        hook_script.chmod(0o755)
        errors = check_vibe_target_artifacts(tmp_path)
        assert any('type = "after_tool"' in error for error in errors)

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
            '[[hooks]]\ntype = "after_tool"\nmatch = "re:^(edit|write_file)$"\ncommand = "./hooks/check-mthds-vibe.sh"\n'
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
            "references/mthds-reference.md",
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
        skill_md.write_text(VALID_FRONTMATTER + "\nSee [ref](../shared/mthds-reference.md)\n")
        assert check_stale_references(skill_tree) == []


class TestSharedFilesExist:
    def test_all_present(self, skill_tree: Path) -> None:
        assert check_shared_files_exist(skill_tree) == []

    def test_missing_file(self, skill_tree: Path) -> None:
        (skill_tree / "templates" / "skills" / "shared" / "mthds-reference.md.j2").unlink()
        errors = check_shared_files_exist(skill_tree)
        assert len(errors) == 1
        assert "mthds-reference.md.j2" in errors[0]

    def test_all_missing(self, tmp_path: Path) -> None:
        (tmp_path / "templates" / "skills" / "shared").mkdir(parents=True)
        errors = check_shared_files_exist(tmp_path)
        assert len(errors) == len(["mthds-reference.md.j2", "native-content-types.md.j2"])


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

    def test_missing_targets_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Targets directory not found"):
            check_no_templates_in_output(tmp_path)
