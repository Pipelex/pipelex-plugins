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
    check_credential_wiring,
    check_marketplace_plugins,
    check_matched_target_versions,
    check_no_claude_artifacts,
    check_no_templates_in_output,
    check_python_pin,
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
    for name in [
        "writing-mthds.md.j2",
        "native-content-types.md.j2",
        "credentials.md.j2",
        "catalog-id.md.j2",
        "fit.md.j2",
        "team-files.md.j2",
        "file-roles.md.j2",
    ]:
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

    def test_mistral_vibe_reads_its_plugin_json_at_the_plugin_root(self, tmp_path: Path) -> None:
        """A Mistral Vibe target's Agent Plugins manifest sits at its output's root, not in a directory of its own."""
        _write_target_configs(tmp_path, {"prod": {"name": "pipelex", "version": "0.6.3", "source": "pipelex/"}})
        _write_plugin_json(tmp_path, "pipelex", "0.6.3", "pipelex")
        (tmp_path / "targets" / "mistral-vibe.toml").write_text(
            '[plugin]\nname = "pipelex"\nversion = "0.6.3"\nsource = "pipelex-vibe/"\n\n[vars]\nplatform = "mistral-vibe"\n'
        )
        assert check_target_plugin_versions(tmp_path)[0] == ["[mistral-vibe] plugin.json not found at pipelex-vibe/plugin.json"]
        (tmp_path / "pipelex-vibe").mkdir()
        (tmp_path / "pipelex-vibe" / "plugin.json").write_text(PLUGIN_JSON_TEMPLATE.format(name="pipelex", version="0.6.3"))
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


class TestNoClaudeArtifacts:
    @staticmethod
    def _output(tmp_path: Path, platform: str) -> Path:
        _write_target_configs(
            tmp_path,
            {platform: {"name": "pipelex", "version": "0.1.0", "source": "pipelex-out/"}},
            defaults_vars={"marketplace_name": MARKETPLACE, "platform": platform},
        )
        skill_dir = tmp_path / "pipelex-out" / "skills" / "pipelex-test"
        skill_dir.mkdir(parents=True)
        return skill_dir

    @pytest.mark.parametrize("platform", ["codex", "mistral-vibe"])
    def test_clean_output(self, tmp_path: Path, platform: str) -> None:
        skill_dir = self._output(tmp_path, platform)
        (skill_dir / "SKILL.md").write_text(VALID_FRONTMATTER)
        assert check_no_claude_artifacts(tmp_path) == []

    @pytest.mark.parametrize("platform", ["codex", "mistral-vibe"])
    def test_detects_claude_plugin_dir(self, tmp_path: Path, platform: str) -> None:
        self._output(tmp_path, platform)
        (tmp_path / "pipelex-out" / ".claude-plugin").mkdir(parents=True)
        assert check_no_claude_artifacts(tmp_path) == [f"[{platform}] .claude-plugin/ found in {platform} output pipelex-out/"]

    @pytest.mark.parametrize("platform", ["codex", "mistral-vibe"])
    def test_detects_allowed_tools_in_frontmatter(self, tmp_path: Path, platform: str) -> None:
        skill_dir = self._output(tmp_path, platform)
        (skill_dir / "SKILL.md").write_text("---\nname: t\nallowed-tools:\n  - Bash\n---\n\nBody.\n")
        assert check_no_claude_artifacts(tmp_path) == [
            f"[{platform}] pipelex-out/skills/pipelex-test/SKILL.md: contains 'allowed-tools' (Claude Code only, not read on {platform})"
        ]

    def test_a_claude_target_may_carry_them(self, tmp_path: Path) -> None:
        skill_dir = self._output(tmp_path, "claude")
        (skill_dir / "SKILL.md").write_text("---\nname: t\nallowed-tools:\n  - Bash\n---\n\nBody.\n")
        (tmp_path / "pipelex-out" / ".claude-plugin").mkdir(parents=True)
        assert check_no_claude_artifacts(tmp_path) == []


class TestVibeTargetArtifacts:
    """The Vibe build is the native plugin Vibe's resolver loads, its manifest and wrapper, with the hook entry and the fragment the user appends."""

    REPO_ROOT = Path(__file__).parents[2]
    VALID_MANIFEST: ClassVar[dict[str, object]] = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "pipelex",
        "version": "0.1.0",
        "author": {"name": "Pipelex staff", "email": "oss@pipelex.com"},
    }
    HOOK_COMMAND = '"${VIBE_HOME:-$HOME/.vibe}/plugins/pipelex/hooks/check-mthds-vibe.sh"'
    VALID_HOOKS = f'[[hooks]]\nname = "check-mthds"\ntype = "post_tool"\nmatch = "re:^(edit|write_file)$"\ncommand = \'{HOOK_COMMAND}\'\n'

    VALID_MCP_FRAGMENT = '[[mcp_servers]]\nname = "pipelex"\ntransport = "stdio"\ncommand = ["npx"]\nargs = ["-y", "@pipelex/mcp@latest"]\n'

    def _vibe_target(self, tmp_path: Path, *, skill_prefix: str | None = "/pipelex:") -> Path:
        """Write a prod + Mistral Vibe target pair with a valid native Vibe output, and return that output."""
        _write_target_configs(tmp_path, {"prod": {"name": "pipelex", "version": "0.1.0", "source": "pipelex/"}})
        prefix_line = f'skill_prefix = "{skill_prefix}"\n' if skill_prefix is not None else ""
        (tmp_path / "targets" / "mistral-vibe.toml").write_text(
            f'[plugin]\nname = "pipelex"\nversion = "0.1.0"\nsource = "pipelex-vibe/"\n\n[vars]\nplatform = "mistral-vibe"\n{prefix_line}'
        )
        output = tmp_path / "pipelex-vibe"
        (output / "hooks").mkdir(parents=True)
        (output / "plugin.json").write_text(json.dumps(self.VALID_MANIFEST))
        (output / "hooks" / "vibe-hooks.toml").write_text(self.VALID_HOOKS)
        hook_script = output / "hooks" / "check-mthds-vibe.sh"
        hook_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        hook_script.chmod(0o755)
        (output / "mcp").mkdir()
        (output / "mcp" / "vibe-mcp.toml").write_text(self.VALID_MCP_FRAGMENT)
        return output

    def test_matching(self, tmp_path: Path) -> None:
        self._vibe_target(tmp_path)
        assert check_vibe_target_artifacts(tmp_path) == []

    def test_the_real_build_matches(self, tmp_path: Path) -> None:
        """The repository's own Vibe target, rendered from its templates, passes the check it ships under."""
        targets = tmp_path / "targets"
        shutil.copytree(self.REPO_ROOT / "targets", targets)
        config = load_target_config(targets, "mistral-vibe")
        for path, content in build_target(self.REPO_ROOT, config, dry_run=True).files.items():
            destination = tmp_path / path.relative_to(self.REPO_ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
            if destination.suffix == ".sh":
                destination.chmod(0o755)
        assert check_vibe_target_artifacts(tmp_path) == []
        assert check_skill_frontmatter(tmp_path) == []
        assert check_no_claude_artifacts(tmp_path) == []

    @pytest.mark.parametrize("dirname", [".claude-plugin", ".codex-plugin"])
    def test_rejects_another_harness_manifest(self, tmp_path: Path, dirname: str) -> None:
        (self._vibe_target(tmp_path) / dirname).mkdir()
        assert check_vibe_target_artifacts(tmp_path) == [
            f"[mistral-vibe] {dirname}/ found in Vibe output pipelex-vibe/, which Vibe would refuse as ambiguous"
        ]

    def test_rejects_an_mcp_json(self, tmp_path: Path) -> None:
        (self._vibe_target(tmp_path) / "mcp.json").write_text("{}")
        assert check_vibe_target_artifacts(tmp_path) == [
            "[mistral-vibe] mcp.json found in Vibe output pipelex-vibe/; it would start the workshop outside the project"
        ]

    @pytest.mark.parametrize(
        ("field", "value", "expected"),
        [
            ("userConfig", {}, "plugin.json carries userConfig, which Vibe's manifest refuses"),
            ("$schema", "https://example.com/plugin.schema.json", "plugin.json must declare $schema"),
            ("name", "Pipelex", "plugin.json name 'Pipelex' is not a name Vibe accepts"),
            ("name", "pipe--lex", "plugin.json name 'pipe--lex' is not a name Vibe accepts"),
            ("name", "other", "plugin.json name is 'other', targets/mistral-vibe.toml has 'pipelex'"),
            ("author", {"name": "Pipelex", "twitter": "@pipelex"}, "plugin.json author carries twitter"),
            ("extensions", {"ai.mistral.vibe": "on"}, "extension must be an object"),
            ("extensions", {"ai.mistral.vibe": {"schemaVersion": 2}}, "extension must set schemaVersion = 1"),
            ("extensions", {"ai.mistral.vibe": {"schemaVersion": 1, "hooks": "x"}}, "extension carries hooks, which Vibe refuses"),
        ],
    )
    def test_the_manifest_holds_to_vibe_fields(self, tmp_path: Path, field: str, value: object, expected: str) -> None:
        output = self._vibe_target(tmp_path)
        (output / "plugin.json").write_text(json.dumps({**self.VALID_MANIFEST, field: value}))
        errors = check_vibe_target_artifacts(tmp_path)
        assert len(errors) == 1, errors
        assert expected in errors[0]

    def test_the_manifest_may_declare_the_vibe_extension(self, tmp_path: Path) -> None:
        """The build declares no extension, but one held to Vibe's fields passes."""
        output = self._vibe_target(tmp_path)
        (output / "plugin.json").write_text(json.dumps({**self.VALID_MANIFEST, "extensions": {"ai.mistral.vibe": {"schemaVersion": 1}}}))
        assert check_vibe_target_artifacts(tmp_path) == []

    def test_a_missing_manifest_fails(self, tmp_path: Path) -> None:
        (self._vibe_target(tmp_path) / "plugin.json").unlink()
        assert check_vibe_target_artifacts(tmp_path) == ["[mistral-vibe] plugin.json is missing, not valid JSON, or not an object"]

    @pytest.mark.parametrize(
        ("old", "new", "expected"),
        [
            ('type = "post_tool"', 'type = "pre_tool"', 'must use type = "post_tool"'),
            ("re:^(edit|write_file)$", "re:^write_file$", "must match re:^(edit|write_file)$"),
            (HOOK_COMMAND, '"${PLUGIN_ROOT}"/hooks/check-mthds-vibe.sh', "command must be"),
            (HOOK_COMMAND, "${VIBE_HOME:-$HOME/.vibe}/plugins/pipelex/hooks/check-mthds-vibe.sh", "command must be"),
            (HOOK_COMMAND, HOOK_COMMAND.replace("/pipelex/", "/other/"), "command must be"),
            ("[[hooks]]", "[[hooks]\n", "not valid TOML"),
        ],
    )
    def test_the_hook_entry_declares_the_one_hook(self, tmp_path: Path, old: str, new: str, expected: str) -> None:
        hooks = self._vibe_target(tmp_path) / "hooks" / "vibe-hooks.toml"
        hooks.write_text(self.VALID_HOOKS.replace(old, new))
        errors = check_vibe_target_artifacts(tmp_path)
        assert len(errors) == 1, errors
        assert expected in errors[0]

    def test_the_hook_entry_declares_exactly_one_hook(self, tmp_path: Path) -> None:
        (self._vibe_target(tmp_path) / "hooks" / "vibe-hooks.toml").write_text(self.VALID_HOOKS * 2)
        assert check_vibe_target_artifacts(tmp_path) == ["[mistral-vibe] hooks/vibe-hooks.toml must declare exactly one [[hooks]] table"]

    def test_a_missing_hook_entry_fails(self, tmp_path: Path) -> None:
        (self._vibe_target(tmp_path) / "hooks" / "vibe-hooks.toml").unlink()
        assert check_vibe_target_artifacts(tmp_path) == ["[mistral-vibe] hooks/vibe-hooks.toml missing"]

    def test_rejects_a_plugin_hooks_file(self, tmp_path: Path) -> None:
        """Vibe 2.26.1 lists the hooks a plugin declares and runs none, so a plugin hooks file would never check an edit."""
        output = self._vibe_target(tmp_path)
        (output / "ai.mistral.vibe").mkdir()
        (output / "ai.mistral.vibe" / "hooks.toml").write_text(self.VALID_HOOKS)
        assert check_vibe_target_artifacts(tmp_path) == [
            "[mistral-vibe] ai.mistral.vibe/hooks.toml found in Vibe output pipelex-vibe/; Vibe 2.26.1 runs no hook a plugin declares, "
            "so the hook ships as hooks/vibe-hooks.toml"
        ]

    def test_non_executable_script(self, tmp_path: Path) -> None:
        (self._vibe_target(tmp_path) / "hooks" / "check-mthds-vibe.sh").chmod(0o644)
        assert check_vibe_target_artifacts(tmp_path) == ["[mistral-vibe] hooks/check-mthds-vibe.sh is not executable"]

    @pytest.mark.parametrize("filename", ["check-mthds.sh", "hooks.json", "codex-hooks.json"])
    def test_rejects_another_hook_artifact(self, tmp_path: Path, filename: str) -> None:
        (self._vibe_target(tmp_path) / "hooks" / filename).write_text("")
        assert check_vibe_target_artifacts(tmp_path) == [f"[mistral-vibe] hooks/{filename} is not an artifact of the native Vibe plugin"]

    def test_missing_mcp_fragment(self, tmp_path: Path) -> None:
        (self._vibe_target(tmp_path) / "mcp" / "vibe-mcp.toml").unlink()
        assert check_vibe_target_artifacts(tmp_path) == ["[mistral-vibe] mcp/vibe-mcp.toml missing"]

    @pytest.mark.parametrize(
        ("fragment", "expected"),
        [
            ('[[mcp_servers]]\nname = "pipelex"\ntransport = "streamable-http"\nurl = "https://example.com/mcp"\n', 'must use transport = "stdio"'),
            (VALID_MCP_FRAGMENT.replace('"pipelex"', '"pipelex-local"'), 'must name the server "pipelex"'),
            (VALID_MCP_FRAGMENT * 2, "exactly one [[mcp_servers]] entry"),
            ("[[mcp_servers]\nname = \n", "not valid TOML"),
            (VALID_MCP_FRAGMENT.replace('["npx"]', '"npx"'), "must set command as a one-element list"),
            (VALID_MCP_FRAGMENT + '[mcp_servers.env]\nPIPELEX_API_KEY = ""\n', "carries an env table"),
        ],
    )
    def test_the_mcp_fragment_is_the_keyless_stdio_entry(self, tmp_path: Path, fragment: str, expected: str) -> None:
        (self._vibe_target(tmp_path) / "mcp" / "vibe-mcp.toml").write_text(fragment)
        errors = check_vibe_target_artifacts(tmp_path)
        assert any(expected in error for error in errors), errors

    def test_the_skill_prefix_is_the_plugin_namespace(self, tmp_path: Path) -> None:
        self._vibe_target(tmp_path, skill_prefix="/")
        assert check_vibe_target_artifacts(tmp_path) == [
            "[mistral-vibe] skill_prefix is '/', but Vibe names a plugin's skill /pipelex:<skill>, so a skill named another way is never found"
        ]

    def test_a_target_without_a_skill_prefix_fails(self, tmp_path: Path) -> None:
        self._vibe_target(tmp_path, skill_prefix=None)
        assert check_vibe_target_artifacts(tmp_path) == ["[mistral-vibe] defines no skill_prefix, the prefix a skill names another skill by"]


class TestCredentialWiring:
    """Each generated target must carry the credential wiring `targets/defaults.toml` declares.

    The expectation comes from the defaults, never from a target's merged variables: a target whose
    override lost `env_vars` or `user_config` renders files that agree with it, so the freshness
    check passes them. The trees below are the real targets rendered from the real templates.
    """

    REPO_ROOT = Path(__file__).parents[2]
    DEV_OVERRIDE = '\n[vars.mcp_server]\ncommand = "node"\nargs = ["../pipelex-mcp/dist/main.js"]\n'

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
        `userConfig` and launcher, the Codex manifest its forwarded names, and the hook and
        launcher their promotions, with every check green."""
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
            (
                "pipelex-codex/.codex-plugin/plugin.json",
                '"env_vars"',
                '"env_vars_gone"',
                "forwards no PIPELEX_API_KEY, PIPELEX_BASE_URL, PIPELEX_HOME",
            ),
            ("pipelex-codex/.codex-plugin/plugin.json", ',\n        "PIPELEX_HOME"', "", "forwards no PIPELEX_HOME"),
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


class TestPythonPin:
    """`.python-version` names the Python the repository develops on, and it is the floor.

    The bug this rule closes was three places naming an interpreter, or failing to name one,
    with nothing comparing them: a new worktree was built on the newest Python on the machine
    while CI ran the floor. So every disagreement is named with the file that has to change.
    """

    PYPROJECT = (
        '[project]\nname = "fixture"\nrequires-python = ">=3.13"\n\n'
        '[tool.mypy]\npython_version = "3.13"\n\n'
        '[tool.pyright]\npythonVersion = "3.13"\n\n'
        '[tool.ruff]\ntarget-version = "py313"\n'
    )
    SETUP_PYTHON_WITH_FILE = "      - uses: actions/setup-python@v5\n        with:\n          python-version-file: .python-version\n"
    WORKFLOW_HEAD = "name: Tests\non:\n  pull_request:\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v5\n"

    def _tree(self, tmp_path: Path, *, pin: str | None = "3.13\n", pyproject: str | None = None, setup_python: str | None = None) -> Path:
        if pin is not None:
            (tmp_path / ".python-version").write_text(pin)
        (tmp_path / "pyproject.toml").write_text(self.PYPROJECT if pyproject is None else pyproject)
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        step = self.SETUP_PYTHON_WITH_FILE if setup_python is None else setup_python
        (workflows / "tests.yml").write_text(self.WORKFLOW_HEAD + step + "      - run: make agent-test\n")
        # A workflow that installs no Python is none of this rule's business.
        (workflows / "guard.yml").write_text(self.WORKFLOW_HEAD + "      - run: echo guarded\n")
        return tmp_path

    def test_the_repository_as_it_stands_passes(self) -> None:
        repo_root = Path(__file__).parents[2]
        assert check_python_pin(repo_root) == []

    def test_a_consistent_tree_passes(self, tmp_path: Path) -> None:
        assert check_python_pin(self._tree(tmp_path)) == []

    def test_a_missing_pin_is_named(self, tmp_path: Path) -> None:
        errors = check_python_pin(self._tree(tmp_path, pin=None))
        assert len(errors) == 1
        assert errors[0].startswith(".python-version is missing")

    @pytest.mark.parametrize(
        "pin",
        [
            pytest.param("3.13.17\n", id="a patch version"),
            pytest.param("cpython\n", id="not a version"),
            pytest.param("3.13\n3.14\n", id="two versions"),
        ],
    )
    def test_a_pin_that_is_not_a_single_minor_version_is_named(self, tmp_path: Path, pin: str) -> None:
        errors = check_python_pin(self._tree(tmp_path, pin=pin))
        assert len(errors) == 1
        assert errors[0].startswith(".python-version holds")
        assert "not a single X.Y version" in errors[0]

    def test_a_requires_python_floor_above_the_pin_is_named(self, tmp_path: Path) -> None:
        pyproject = self.PYPROJECT.replace('requires-python = ">=3.13"', 'requires-python = ">=3.14"')
        errors = check_python_pin(self._tree(tmp_path, pyproject=pyproject))
        assert errors == ["pyproject.toml: the floor of [project] requires-python is 3.14, but .python-version pins 3.13"]

    def test_a_requires_python_with_no_floor_is_named(self, tmp_path: Path) -> None:
        pyproject = self.PYPROJECT.replace('requires-python = ">=3.13"', 'requires-python = "<3.15"')
        errors = check_python_pin(self._tree(tmp_path, pyproject=pyproject))
        assert len(errors) == 1
        assert errors[0].startswith("pyproject.toml: [project] requires-python states no >= floor")

    def test_an_upper_bound_beside_the_floor_is_not_a_disagreement(self, tmp_path: Path) -> None:
        pyproject = self.PYPROJECT.replace('requires-python = ">=3.13"', 'requires-python = ">=3.13,<4"')
        assert check_python_pin(self._tree(tmp_path, pyproject=pyproject)) == []

    @pytest.mark.parametrize(
        ("line", "replacement", "label"),
        [
            pytest.param('python_version = "3.13"', 'python_version = "3.14"', "[tool.mypy] python_version", id="mypy"),
            pytest.param('pythonVersion = "3.13"', 'pythonVersion = "3.14"', "[tool.pyright] pythonVersion", id="pyright"),
            pytest.param('target-version = "py313"', 'target-version = "py314"', "[tool.ruff] target-version", id="ruff"),
        ],
    )
    def test_a_tool_version_that_differs_from_the_pin_is_named(self, tmp_path: Path, line: str, replacement: str, label: str) -> None:
        errors = check_python_pin(self._tree(tmp_path, pyproject=self.PYPROJECT.replace(line, replacement)))
        assert len(errors) == 1
        assert errors[0].startswith(f"pyproject.toml: {label} is ")
        assert "but .python-version pins 3.13" in errors[0]

    def test_a_tool_version_that_is_not_set_is_named(self, tmp_path: Path) -> None:
        pyproject = self.PYPROJECT.replace('[tool.mypy]\npython_version = "3.13"\n\n', "")
        errors = check_python_pin(self._tree(tmp_path, pyproject=pyproject))
        assert errors == ["pyproject.toml: [tool.mypy] python_version is not set; it should be '3.13', the version .python-version pins"]

    def test_a_raised_pin_names_every_floor_it_left_behind(self, tmp_path: Path) -> None:
        """Raising the pin alone is the half-move the rule exists for: the floors are named, and
        the workflows, which read the file, are not."""
        errors = check_python_pin(self._tree(tmp_path, pin="3.14\n"))
        assert len(errors) == 4
        assert all(error.startswith("pyproject.toml: ") for error in errors)

    def test_a_workflow_with_a_literal_python_version_is_named(self, tmp_path: Path) -> None:
        setup_python = '      - uses: actions/setup-python@v5\n        with:\n          python-version: "3.13"\n'
        errors = check_python_pin(self._tree(tmp_path, setup_python=setup_python))
        assert len(errors) == 1
        assert errors[0].startswith(
            ".github/workflows/tests.yml: job `test`, step 2 (actions/setup-python@v5) passes the literal python-version '3.13'"
        )

    def test_a_workflow_passing_both_keys_is_named_for_its_literal(self, tmp_path: Path) -> None:
        setup_python = (
            '      - uses: actions/setup-python@v5\n        with:\n          python-version: "3.13"\n          python-version-file: .python-version\n'
        )
        errors = check_python_pin(self._tree(tmp_path, setup_python=setup_python))
        assert len(errors) == 1
        assert ".github/workflows/tests.yml" in errors[0]
        assert "passes the literal python-version" in errors[0]

    @pytest.mark.parametrize(
        "setup_python",
        [
            pytest.param("      - uses: actions/setup-python@v5\n", id="neither key"),
            pytest.param("      - uses: actions/setup-python@v5\n        with:\n          cache: pip\n", id="other inputs only"),
            pytest.param("      - uses: actions/setup-python@v5\n        with:\n          python-version-file: pyproject.toml\n", id="another file"),
        ],
    )
    def test_a_workflow_that_does_not_read_the_pin_is_named(self, tmp_path: Path, setup_python: str) -> None:
        errors = check_python_pin(self._tree(tmp_path, setup_python=setup_python))
        assert errors == [
            ".github/workflows/tests.yml: job `test`, step 2 (actions/setup-python@v5) does not pass python-version-file: .python-version, "
            "so CI does not run the version the repository pins"
        ]


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
        assert len(errors) == len(
            [
                "writing-mthds.md.j2",
                "native-content-types.md.j2",
                "credentials.md.j2",
                "catalog-id.md.j2",
                "fit.md.j2",
                "team-files.md.j2",
                "file-roles.md.j2",
            ]
        )


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

    @pytest.mark.parametrize("address", ["github.com/owner/repo[/selector]", "a [link] of some kind"])
    def test_a_square_bracket_in_the_description_fails(self, skill_tree: Path, address: str) -> None:
        """Vibe's slash completion renders a description as markup, where `[/selector]` closes no open tag and crashes it."""
        skill_md = skill_tree / "pipelex" / "skills" / "pipelex-test" / "SKILL.md"
        skill_md.write_text(f"---\nname: pipelex-test\ndescription: Run {address}.\n---\n")
        assert check_skill_frontmatter(skill_tree) == [
            "pipelex/skills/pipelex-test/SKILL.md: frontmatter `description` holds a square bracket, "
            "which Mistral Vibe's slash completion reads as markup"
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
