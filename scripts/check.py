#!/usr/bin/env python3
"""Validate shared references, generated artifacts, and marketplace consistency."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

import yaml

from scripts.gen_skill_docs import CLAUDE_MCP_LAUNCHER_COMMAND, MCP_SERVER_NAME, SHARED_TEMPLATES, Platform
from scripts.hook_bundle import HOOK_BUNDLE_PATH, HOOK_NOTICES_PATH, inlined_packages, read_bundle, read_provenance, unpublished_sources
from scripts.skill_links import skill_link_errors

SHARED_TEMPLATE_FILES = [Path(template_path).name for template_path in SHARED_TEMPLATES]
_SHARED_STEMS = [Path(template_path).name.removesuffix(".md.j2") for template_path in SHARED_TEMPLATES]
STALE_REF_PATTERN = re.compile(r"references/(?:" + "|".join(re.escape(stem) for stem in _SHARED_STEMS) + r")")
# What a template emits where a chain of branches on a parameter's VALUE falls off its end: the
# `{% else %}` of a partial that selects one of several blocks. An unset or misspelled parameter
# NAME never gets this far, since the renderer's `StrictUndefined` fails the build on it; a value
# that is present but names no branch is what strict mode cannot see, and without the marker the
# block would vanish from the output with the build, the freshness check and the tests all green.
BUILD_ERROR_MARKER = "PIPELEX_BUILD_ERROR"
# The directories a target written to the repository root generates into. A target with its own
# output directory is scanned whole; the root also holds every source, so only these are its output.
ROOT_TARGET_OUTPUT_DIRS = ("skills", "hooks", "mcp", ".claude-plugin", ".codex-plugin")
# Claude Code replaces `$ARGUMENTS`, `$ARGUMENTS[N]` and `$N` in a skill body with the invocation's arguments.
ARGUMENT_PLACEHOLDER_PATTERN = re.compile(r"\$(?:ARGUMENTS|\d+)")
# Skill frontmatter keys only Claude Code reads, which no other in-repo target may carry.
CLAUDE_ONLY_SKILL_KEYS = ("allowed-tools",)

# The native Mistral Vibe plugin, as Vibe 2.26.1's resolver reads it (`vibe/core/plugins/_native.py`):
# the Agent Plugins 1.0 manifest at the plugin root, its fields and an `ai.mistral.vibe` extension's.
# Two files of the build are no part of the plugin as Vibe reads it: the hook and the MCP fragment are
# the entries the user appends to their own hooks file and configuration. A plugin's own hooks file,
# `ai.mistral.vibe/hooks.toml`, is refused, since Vibe 2.26.1 lists the hooks it declares and runs none.
VIBE_MANIFEST_PATH = "plugin.json"
VIBE_MANIFEST_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
VIBE_MANIFEST_KEYS = frozenset({"$schema", "name", "version", "description", "author", "homepage", "repository", "license", "keywords", "extensions"})
VIBE_AUTHOR_KEYS = frozenset({"name", "email", "url"})
VIBE_PLUGIN_NAME_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9.-]{0,62}[a-z0-9])?")
VIBE_EXTENSION = "ai.mistral.vibe"
VIBE_EXTENSION_KEYS = frozenset({"schemaVersion", "toolNamespace", "toolOverrides"})
VIBE_PLUGIN_HOOKS_PATH = "ai.mistral.vibe/hooks.toml"
VIBE_HOOKS_PATH = "hooks/vibe-hooks.toml"
VIBE_HOOK_MATCH = "re:^(edit|write_file)$"
VIBE_MCP_FRAGMENT_PATH = "mcp/vibe-mcp.toml"

# The compaction ceiling (box C of the size diet's design, L-260923-a9bdfe). After a compaction Claude
# Code re-attaches each invoked skill within 5,000 tokens, so a SKILL.md longer than that is
# carried forward as its head alone and loses whatever its tail guarded. The ceiling is counted
# in characters, which a check can count exactly, and derived from tokens in phase 0: 5,000
# times the lowest characters-per-token ratio measured over every rendered SKILL.md on every
# target (2.77, the Claude 5 tokenizer), less a margin — the size diet's facts (L-260923-a9bdfe).
SKILL_CEILING_CHARS = 13_000

TARGETS_DIR_NAME = "targets"

# The version floors the skills state, and where a STATIC reference states one.
#
# A template reads its floor from `[vars.floors]` in `targets/defaults.toml`, so a
# bump reaches every rendered skill on its own, and a misspelled key is caught at
# build time — the renderer runs under `StrictUndefined`, which raises on the
# misspelling itself rather than letting it render as the empty string. The first
# half below is therefore no longer that guard: it asserts each floor still reaches
# the built output at all, which is what catches a floor nobody states any more —
# a dead table entry, or a sentence reworded until it dropped the number.
#
# The static references under `skills/` are the ones nothing renders: they are
# copied verbatim into every target, so they keep their literals and only the
# second half can hold them to the table. Every occurrence of a floor there needs
# its own entry — the check reads the ones listed here and nothing else, so a
# statement left off this list drifts silently on the next bump.
#
# Each entry is ANCHORED ON PROSE rather than on a number, and deliberately: a
# bare numeric sweep would read `png.md`'s matplotlib `3.11` as the Python
# floor. A reworded reference fails this check instead of passing silently,
# which is the right way round — re-anchor the pattern in the same change that
# rewords the sentence.
VERSION_FLOOR_STATIC_REFS: list[tuple[str, str, str]] = [
    (
        "skills/pipelex-integrate/references/typescript.md",
        r"`@pipelex/sdk` (\d+\.\d+\.\d+), the floor the skill's step 8 installs",
        "pipelex_sdk_js",
    ),
    (
        "skills/pipelex-integrate/references/typescript.md",
        r"a too-old one is raised to (\d+\.\d+\.\d+) or later, the floor step 8 installs",
        "pipelex_sdk_js",
    ),
    (
        "skills/pipelex-integrate/references/codegen-check.mjs",
        r'const SDK_MINIMUM = "(\d+\.\d+\.\d+)";',
        "pipelex_sdk_js",
    ),
    (
        "skills/pipelex-integrate/references/python.md",
        r"checked against `pipelex-sdk` (\d+\.\d+\.\d+), the floor step 8 installs for `python-pydantic`",
        "pipelex_sdk_py",
    ),
    (
        "skills/pipelex-integrate/references/python.md",
        r"present in the `pipelex-sdk` (\d+\.\d+\.\d+) that step 8 installs",
        "pipelex_sdk_py",
    ),
    (
        "skills/pipelex-integrate/references/codegen_check.py",
        r"`pipelex-sdk` \((\d+\.\d+\.\d+) or later\)",
        "pipelex_sdk_py",
    ),
    (
        "skills/pipelex-integrate/references/codegen_check.py",
        r"pipelex-sdk (\d+\.\d+\.\d+) or later is not importable",
        "pipelex_sdk_py",
    ),
    (
        "skills/pipelex-integrate/references/python.md",
        r"from the `pipelex` (\d+\.\d+\.\d+) that step 8 raises the project to",
        "pipelex",
    ),
]

# A number in a template that equals a floor and means something else entirely.
# Empty today, and meant to stay nearly so: each entry names a template and the
# literal it may contain, and adding one is a claim a reader should be able to
# check from the sentence around the number. It is what keeps the template sweep
# from being a rule with no way out — the failure mode of a correct check nobody
# can satisfy is that somebody deletes it.
TEMPLATE_FLOOR_LOOKALIKES: set[tuple[str, str]] = set()

DEFAULTS_FILE = "defaults.toml"
CLAUDE_MARKETPLACE_PATH = Path(".claude-plugin/marketplace.json")
CODEX_MARKETPLACE_PATH = Path("packaging/codex-marketplace.json")

# The interpreter the repository develops on, which uv reads in every command and CI reads
# through `actions/setup-python`'s `python-version-file`. `check_python_pin` holds it to the
# floors in `pyproject.toml` and holds every workflow to the file.
PYTHON_PIN_FILE = ".python-version"
PYTHON_PIN_PATTERN = re.compile(r"\d+\.\d+")
PYPROJECT_FILE = "pyproject.toml"
WORKFLOWS_DIR = Path(".github/workflows")
SETUP_PYTHON_ACTION = "actions/setup-python"


def _read_json_string(path: Path, *keys: str) -> str:
    """Read a nested key from a JSON file, raising ValueError on any problem."""
    rel = path.name
    if not path.is_file():
        msg = f"{rel} not found"
        raise ValueError(msg)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"{rel} is not valid JSON"
        raise ValueError(msg) from exc
    value: Any = raw
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            msg = f"{rel} missing key: {'.'.join(keys)}"
            raise ValueError(msg)
        value = cast(dict[str, Any], value)[key]
    if not isinstance(value, str):
        msg = f"{rel} key '{'.'.join(keys)}' is not a string"
        raise ValueError(msg)
    return value


def _parse_version(version: str) -> tuple[int, ...]:
    """Parse a dotted numeric version string into an ordered tuple."""
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError as exc:
        msg = f"invalid numeric version {version!r}"
        raise ValueError(msg) from exc


def load_target_configs(base_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all target configs from targets/ directory."""
    targets_dir = base_dir / TARGETS_DIR_NAME
    if not targets_dir.is_dir():
        msg = f"Targets directory not found: {targets_dir}"
        raise ValueError(msg)

    configs: dict[str, dict[str, Any]] = {}
    for toml_path in sorted(targets_dir.glob("*.toml")):
        if toml_path.name == DEFAULTS_FILE:
            continue
        raw = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        configs[toml_path.stem] = raw
    return configs


def load_defaults_vars(base_dir: Path) -> dict[str, str]:
    """Load default template variables from defaults.toml."""
    defaults_path = base_dir / TARGETS_DIR_NAME / DEFAULTS_FILE
    if not defaults_path.is_file():
        msg = f"Defaults file not found: {defaults_path}"
        raise ValueError(msg)
    raw = tomllib.loads(defaults_path.read_text(encoding="utf-8"))
    defaults: dict[str, str] = {}
    if "vars" in raw:
        for key, value in raw["vars"].items():
            defaults[key] = str(value)
    return defaults


def resolve_target_var(base_dir: Path, target_name: str, var_name: str) -> str:
    """Resolve a template variable for a target (target override > default)."""
    defaults = load_defaults_vars(base_dir)
    configs = load_target_configs(base_dir)
    if target_name not in configs:
        msg = f"Target '{target_name}' not found in targets/"
        raise ValueError(msg)
    target_vars = configs[target_name].get("vars", {})
    value = target_vars.get(var_name, defaults.get(var_name))
    if value is None:
        msg = f"Variable '{var_name}' not defined for target '{target_name}'"
        raise ValueError(msg)
    return str(value)


def _platform_for_config(config: dict[str, Any], defaults: dict[str, str] | None = None) -> Platform:
    """Resolve a target platform from plugin, target vars, or defaults."""
    defaults = defaults or {}
    platform = config.get("plugin", {}).get(
        "platform",
        config.get("vars", {}).get("platform", defaults.get("platform", Platform.CLAUDE)),
    )
    return Platform(str(platform))


def check_target_platforms(base_dir: Path) -> list[str]:
    """Refuse an in-repo target on a platform meant for outside targets only.

    `agent-skills` renders skills alone, for a consumer's private target rendered by
    `scripts/outside_render.py`; a public skills-only rendering in this repository would be a
    product surface of its own, to be decided on its own (docs/decisions.md, "Outside targets").
    """
    defaults = load_defaults_vars(base_dir)
    errors: list[str] = []
    for target_name, config in load_target_configs(base_dir).items():
        platform = _platform_for_config(config, defaults)
        if platform.is_outside_only:
            errors.append(
                f"targets/{target_name}.toml: platform {platform.value!r} is for outside targets only, rendered by "
                "scripts/outside_render.py; an in-repo target renders for claude, codex or mistral-vibe"
            )
    return errors


def check_matched_target_versions(base_dir: Path) -> list[str]:
    """Check that every target's ``[plugin].version`` is the same.

    A release bumps all targets to the same version string in lockstep, so
    drift between ``targets/*.toml`` is never valid.
    """
    configs = load_target_configs(base_dir)
    target_versions: dict[str, str] = {name: str(config.get("plugin", {}).get("version", "")) for name, config in configs.items()}
    unique_versions = set(target_versions.values())
    if len(unique_versions) <= 1:
        return []

    drift = ", ".join(f"{name}={version or '<missing>'}" for name, version in sorted(target_versions.items()))
    return [f"Target versions must be in lockstep: {drift}"]


def check_target_plugin_versions(base_dir: Path) -> tuple[list[str], dict[str, str]]:
    """Check that each target's plugin.json version and name match its target config."""
    configs = load_target_configs(base_dir)
    defaults = load_defaults_vars(base_dir)
    errors: list[str] = []
    versions: dict[str, str] = {}

    for target_name, config in configs.items():
        plugin_section = config.get("plugin", {})
        config_version = plugin_section.get("version", "")
        source = plugin_section.get("source", "./")
        plugin_name = plugin_section.get("name", target_name)

        manifest_path = _platform_for_config(config, defaults).manifest_path
        if manifest_path is None:
            versions[target_name] = str(config_version)
            continue

        if source == "./":
            plugin_json_path = base_dir / manifest_path
        else:
            plugin_json_path = base_dir / str(source).rstrip("/") / manifest_path

        if not plugin_json_path.is_file():
            errors.append(f"[{target_name}] plugin.json not found at {plugin_json_path.relative_to(base_dir)}")
            continue

        try:
            actual_version = _read_json_string(plugin_json_path, "version")
        except ValueError as exc:
            errors.append(f"[{target_name}] {exc}")
            continue

        versions[target_name] = actual_version
        if actual_version != config_version:
            errors.append(f"[{target_name}] plugin.json has {actual_version}, targets/{target_name}.toml has {config_version}")

        try:
            actual_name = _read_json_string(plugin_json_path, "name")
        except ValueError as exc:
            errors.append(f"[{target_name}] Cannot read plugin name: {exc}")
            continue

        if actual_name != plugin_name:
            errors.append(f"[{target_name}] plugin.json name is '{actual_name}', targets/{target_name}.toml has '{plugin_name}'")

    return errors, versions


def check_marketplace_plugins(base_dir: Path) -> list[str]:
    """Check that the Claude marketplace matches Claude targets and version rules."""
    marketplace_path = base_dir / CLAUDE_MARKETPLACE_PATH
    if not marketplace_path.is_file():
        return [f"{CLAUDE_MARKETPLACE_PATH} not found"]

    try:
        raw = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [f"{CLAUDE_MARKETPLACE_PATH} is not valid JSON"]

    plugins = raw.get("plugins", [])
    if not isinstance(plugins, list):
        return [f"{CLAUDE_MARKETPLACE_PATH} missing plugins array"]
    plugins_list = cast(list[object], plugins)

    configs = load_target_configs(base_dir)
    defaults = load_defaults_vars(base_dir)
    claude_targets: dict[str, dict[str, str]] = {
        config.get("plugin", {}).get("name", name): {
            "version": str(config.get("plugin", {}).get("version", "")),
            "path": f"./{str(config.get('plugin', {}).get('source', './')).rstrip('/')}",
        }
        for name, config in configs.items()
        if _platform_for_config(config, defaults) == Platform.CLAUDE
    }
    marketplace_names: set[str] = set()
    for plugin in plugins_list:
        if isinstance(plugin, dict):
            plugin_dict = cast(dict[str, Any], plugin)
            name = plugin_dict.get("name")
            if isinstance(name, str):
                marketplace_names.add(name)

    errors: list[str] = []
    for idx, plugin in enumerate(plugins_list):
        if not isinstance(plugin, dict):
            errors.append(f"{CLAUDE_MARKETPLACE_PATH} plugins[{idx}] is not an object")
            continue
        plugin_dict = cast(dict[str, Any], plugin)

        name = plugin_dict.get("name")
        if not isinstance(name, str):
            errors.append(f"{CLAUDE_MARKETPLACE_PATH} plugins[{idx}] is missing 'name' key")
            continue

        source = plugin_dict.get("source")
        expected = claude_targets.get(name)
        if not isinstance(source, str):
            errors.append(f"{CLAUDE_MARKETPLACE_PATH} plugin '{name}' missing source string")
        elif expected and source != expected["path"]:
            errors.append(f"{CLAUDE_MARKETPLACE_PATH} plugin '{name}' has source {source!r}, expected {expected['path']!r}")

    metadata = raw.get("metadata")
    if not isinstance(metadata, dict):
        errors.append(f"{CLAUDE_MARKETPLACE_PATH} missing metadata object")
    else:
        metadata_dict = cast(dict[str, Any], metadata)
        marketplace_version = metadata_dict.get("version")
        if not isinstance(marketplace_version, str):
            errors.append(f"{CLAUDE_MARKETPLACE_PATH} metadata.version missing or not a string")
        else:
            try:
                parsed_marketplace_version = _parse_version(marketplace_version)
            except ValueError as exc:
                errors.append(f"{CLAUDE_MARKETPLACE_PATH} metadata.version {exc}")
            else:
                try:
                    highest_target_version = max(_parse_version(target["version"]) for target in claude_targets.values() if target["version"])
                except ValueError as exc:
                    errors.append(f"Claude target version {exc}")
                else:
                    if parsed_marketplace_version < highest_target_version:
                        expected_floor = ".".join(str(part) for part in highest_target_version)
                        errors.append(
                            f"{CLAUDE_MARKETPLACE_PATH} metadata.version {marketplace_version!r} lags behind Claude target version {expected_floor!r}"
                        )

    for name in claude_targets.keys() - marketplace_names:
        errors.append(f"Claude target plugin '{name}' missing from {CLAUDE_MARKETPLACE_PATH} plugins array")
    for name in marketplace_names - claude_targets.keys():
        errors.append(f"{CLAUDE_MARKETPLACE_PATH} lists plugin '{name}' with no matching Claude target config")

    return errors


def check_codex_marketplace_plugins(base_dir: Path) -> list[str]:
    """Check that the tracked Codex packaging marketplace matches Codex targets and required fields.

    The canonical source.path here points at the build-output dir (e.g. ``./pipelex-codex``),
    which is what `codex plugin marketplace add` reads when adding a local marketplace.
    """
    marketplace_path = base_dir / CODEX_MARKETPLACE_PATH
    if not marketplace_path.is_file():
        return [f"{CODEX_MARKETPLACE_PATH} not found"]

    try:
        raw = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [f"{CODEX_MARKETPLACE_PATH} is not valid JSON"]

    plugins = raw.get("plugins", [])
    if not isinstance(plugins, list):
        return [f"{CODEX_MARKETPLACE_PATH} missing plugins array"]
    plugins_list = cast(list[object], plugins)

    configs = load_target_configs(base_dir)
    defaults = load_defaults_vars(base_dir)
    codex_targets: dict[str, str] = {
        config.get("plugin", {}).get("name", name): f"./{str(config.get('plugin', {}).get('source', './')).rstrip('/')}"
        for name, config in configs.items()
        if _platform_for_config(config, defaults) == Platform.CODEX
    }

    marketplace_names: set[str] = set()
    for plugin in plugins_list:
        if isinstance(plugin, dict):
            plugin_dict = cast(dict[str, Any], plugin)
            name = plugin_dict.get("name")
            if isinstance(name, str):
                marketplace_names.add(name)
    errors: list[str] = []

    for idx, plugin in enumerate(plugins_list):
        if not isinstance(plugin, dict):
            errors.append(f"{CODEX_MARKETPLACE_PATH} plugins[{idx}] is not an object")
            continue
        plugin_dict = cast(dict[str, Any], plugin)

        name = plugin_dict.get("name")
        if not isinstance(name, str):
            errors.append(f"{CODEX_MARKETPLACE_PATH} plugins[{idx}] is missing 'name' key")
            continue

        source = plugin_dict.get("source")
        if not isinstance(source, dict):
            errors.append(f"{CODEX_MARKETPLACE_PATH} plugin '{name}' missing source object")
        else:
            source_dict = cast(dict[str, Any], source)
            if source_dict.get("source") != "local":
                errors.append(f"{CODEX_MARKETPLACE_PATH} plugin '{name}' must have source.source = 'local'")
            expected_path = codex_targets.get(name)
            source_path = source_dict.get("path")
            if expected_path and source_path != expected_path:
                errors.append(f"{CODEX_MARKETPLACE_PATH} plugin '{name}' has path {source_path!r}, expected {expected_path!r}")

        policy = plugin_dict.get("policy")
        if not isinstance(policy, dict):
            errors.append(f"{CODEX_MARKETPLACE_PATH} plugin '{name}' missing policy object")
        else:
            policy_dict = cast(dict[str, Any], policy)
            if policy_dict.get("installation") != "AVAILABLE":
                errors.append(f"{CODEX_MARKETPLACE_PATH} plugin '{name}' must have policy.installation = 'AVAILABLE'")
            if policy_dict.get("authentication") != "ON_INSTALL":
                errors.append(f"{CODEX_MARKETPLACE_PATH} plugin '{name}' must have policy.authentication = 'ON_INSTALL'")

        category = plugin_dict.get("category")
        if not isinstance(category, str) or not category:
            errors.append(f"{CODEX_MARKETPLACE_PATH} plugin '{name}' missing category")

    for name in codex_targets.keys() - marketplace_names:
        errors.append(f"Codex target plugin '{name}' missing from {CODEX_MARKETPLACE_PATH} plugins array")
    for name in marketplace_names - codex_targets.keys():
        errors.append(f"{CODEX_MARKETPLACE_PATH} lists plugin '{name}' with no matching Codex target config")

    return errors


def _collect_output_dirs(base_dir: Path) -> list[Path]:
    """Collect output directories from all configured targets."""
    configs = load_target_configs(base_dir)
    output_dirs: list[Path] = []
    for config in configs.values():
        source = config.get("plugin", {}).get("source", "./")
        if source == "./":
            output_dirs.append(base_dir)
        else:
            output_dirs.append(base_dir / str(source).rstrip("/"))
    return output_dirs


def check_stale_references(base_dir: Path) -> list[str]:
    """Check that generated SKILL.md files do not reference shared files via references/."""
    errors: list[str] = []
    for output_dir in _collect_output_dirs(base_dir):
        for skill_md in sorted(output_dir.glob("skills/*/SKILL.md")):
            for idx, line in enumerate(skill_md.read_text(encoding="utf-8").splitlines(), start=1):
                if STALE_REF_PATTERN.search(line):
                    rel = skill_md.relative_to(base_dir)
                    errors.append(f"{rel}:{idx}: stale references/ path (should use ../shared/)")
    return errors


def check_skill_argument_placeholders(base_dir: Path) -> list[str]:
    """Check that no generated SKILL.md carries a token Claude Code replaces with the invocation's arguments.

    Before the model reads a skill body, Claude Code substitutes `$ARGUMENTS` with the whole argument
    string and `$0`, `$1`, … with its whitespace-separated words, so shell code holding `"$1"` or
    `awk '{ print $9 }'` reaches the model as a different command whenever the skill was invoked with
    enough words. The pattern is wider than Claude Code's own, which spares `$1x` and leaves `$N` alone
    when there are too few words: a guard should not depend on either detail. Every target is scanned
    because the body is shared, and reference files are not, because a tool reads them unsubstituted.
    """
    errors: list[str] = []
    for output_dir in _collect_output_dirs(base_dir):
        for skill_md in sorted(output_dir.glob("skills/*/SKILL.md")):
            for idx, line in enumerate(skill_md.read_text(encoding="utf-8").splitlines(), start=1):
                for match in ARGUMENT_PLACEHOLDER_PATTERN.finditer(line):
                    rel = skill_md.relative_to(base_dir)
                    errors.append(f"{rel}:{idx}: `{match.group()}` is replaced by the skill's invocation arguments in Claude Code")
    return errors


def check_skill_frontmatter(base_dir: Path) -> list[str]:
    """Check that every rendered SKILL.md opens with frontmatter strict YAML accepts.

    Mistral Vibe parses a skill's frontmatter with `yaml.safe_load` and drops a skill that fails,
    with nothing but a warning in its log; Codex repairs such a line and Claude Code tolerates it,
    so the loss shows on one harness only. The usual cause is a `: ` inside an unquoted
    `description:`, which strict YAML reads as a second mapping. The frontmatter must also carry a
    string `name` equal to the skill's directory, which Mistral Vibe requires of a plugin's skill,
    and a string `description` with no square bracket: Vibe's slash-command completion renders a
    description as Textual markup, so a `[/selector]` reads as a closing tag that matches no open
    one, and typing `/` crashes Vibe (L-261015-445a4f).
    """
    errors: list[str] = []
    for output_dir in _collect_output_dirs(base_dir):
        for skill_md in sorted(output_dir.glob("skills/*/SKILL.md")):
            rel = skill_md.relative_to(base_dir)
            text = skill_md.read_text(encoding="utf-8")
            end = text.find("\n---\n", 4)
            if not text.startswith("---\n") or end == -1:
                errors.append(f"{rel}: no `---` frontmatter block at the top")
                continue
            try:
                data = yaml.safe_load(text[4:end])
            except yaml.YAMLError as exc:
                reason = str(exc).splitlines()[0]
                errors.append(f"{rel}: frontmatter is not valid YAML ({reason}); Mistral Vibe drops this skill")
                continue
            if not isinstance(data, dict):
                errors.append(f"{rel}: frontmatter is not a mapping")
                continue
            fields = cast(dict[str, Any], data)
            if fields.get("name") != skill_md.parent.name:
                errors.append(f"{rel}: frontmatter `name` is {fields.get('name')!r}, not the skill's directory {skill_md.parent.name!r}")
            description: object = fields.get("description")
            if not isinstance(description, str) or not description.strip():
                errors.append(f"{rel}: frontmatter carries no string `description`")
            elif "[" in description or "]" in description:
                errors.append(f"{rel}: frontmatter `description` holds a square bracket, which Mistral Vibe's slash completion reads as markup")
    return errors


def _generated_files(base_dir: Path, output_dir: Path) -> list[Path]:
    """Every file of a target's output: its whole directory, or at the root the directories the build writes into."""
    roots = [output_dir / name for name in ROOT_TARGET_OUTPUT_DIRS] if output_dir == base_dir else [output_dir]
    files: list[Path] = []
    for root in roots:
        if root.is_dir():
            files.extend(sorted(path for path in root.rglob("*") if path.is_file()))
    return files


def check_build_error_markers(base_dir: Path) -> list[str]:
    """Check that no generated file carries a template's build-error marker.

    A partial that selects one of several blocks by a parameter's value ends its chain in an
    `{% else %}` that emits `PIPELEX_BUILD_ERROR`, so a value naming no branch fails here rather
    than dropping the block from the output with every other gate green. Every text file of every
    target is read, not only the skills: a shared reference, a hook script and the MCP fragment are
    rendered from templates too, and a partial may be included by any of them.
    """
    errors: list[str] = []
    for output_dir in _collect_output_dirs(base_dir):
        for path in _generated_files(base_dir, output_dir):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue  # a binary file holds no rendered text
            if BUILD_ERROR_MARKER not in text:
                continue
            rel = path.relative_to(base_dir)
            for idx, line in enumerate(text.splitlines(), start=1):
                if BUILD_ERROR_MARKER in line:
                    errors.append(f"{rel}:{idx}: {line.strip()}")
    return errors


def check_skill_ceiling(base_dir: Path) -> list[str]:
    """Name every rendered SKILL.md longer than the compaction ceiling, on every target.

    Returned sorted by size, largest first, so the report reads as the diet's remaining work.
    """
    over: list[tuple[int, str]] = []
    for output_dir in _collect_output_dirs(base_dir):
        for skill_md in sorted(output_dir.glob("skills/*/SKILL.md")):
            size = len(skill_md.read_text(encoding="utf-8"))
            if size > SKILL_CEILING_CHARS:
                rel = skill_md.relative_to(base_dir)
                over.append((size, f"{rel}: {size} characters, {size - SKILL_CEILING_CHARS} over the {SKILL_CEILING_CHARS} ceiling"))
    return [line for _, line in sorted(over, key=lambda item: -item[0])]


def check_skill_links(base_dir: Path) -> list[str]:
    """Links resolve both ways in every target (box H of the size diet's design, L-260923-a9bdfe).

    The rule is `scripts/skill_links.py`'s, which an outside target's rendering is held to as well;
    here each in-repo target's directory is the boundary no link may leave.
    """
    errors: list[str] = []
    for output_dir in _collect_output_dirs(base_dir):
        errors.extend(skill_link_errors(output_dir / "skills", base_dir, boundary=output_dir))
    return errors


def load_version_floors(base_dir: Path) -> dict[str, str]:
    """Read `[vars.floors]` from the target defaults."""
    defaults_path = base_dir / TARGETS_DIR_NAME / DEFAULTS_FILE
    raw = tomllib.loads(defaults_path.read_text(encoding="utf-8"))
    floors = raw.get("vars", {}).get("floors", {})
    return {str(key): str(value) for key, value in floors.items()}


def check_version_floors(base_dir: Path) -> list[str]:
    """Check that every version floor reaches the built skills, and that the static
    references state the same numbers as the table.

    The misspelled-variable case belongs to the renderer now: it builds under
    `StrictUndefined`, so `{{ floors.typo }}` fails the build naming the template
    and the attribute, at every use site, instead of rendering as the empty string.

    What the first part still catches is a floor that reaches no generated skill at
    all — a table entry nothing states any more, or a sentence reworded until the
    number fell out of it. The second holds the verbatim-copied references under
    `skills/` to the table, since nothing renders those.

    The third is what neither of the others can see: a template that spells a floor
    as a LITERAL instead of reading it. Strict mode fires on an expression that is
    there and misspelled, never on one that was replaced by its own value, and the
    presence check reads the whole built output at once — so another sentence still
    reading the table keeps the value present while the hardcoded one waits to drift
    at the next bump. Two rows in `pipelex-integrate` were exactly that.
    """
    errors: list[str] = []
    floors = load_version_floors(base_dir)
    if not floors:
        return [f"{TARGETS_DIR_NAME}/{DEFAULTS_FILE}: [vars.floors] is missing or empty"]

    for output_dir in _collect_output_dirs(base_dir):
        rendered = "\n".join(skill_md.read_text(encoding="utf-8") for skill_md in sorted(output_dir.glob("skills/*/SKILL.md")))
        for key, value in sorted(floors.items()):
            if value not in rendered:
                rel = output_dir.relative_to(base_dir)
                errors.append(
                    f"{rel}: floor `{key}` = {value} reaches no generated skill — no skill states it any more, or its sentence was reworded"
                )

    for rel_path, pattern, key in VERSION_FLOOR_STATIC_REFS:
        path = base_dir / rel_path
        if not path.is_file():
            errors.append(f"{rel_path}: static reference is missing, but a version floor is pinned to it")
            continue
        expected = floors.get(key)
        if expected is None:
            errors.append(f"{rel_path}: pinned to floor `{key}`, which [vars.floors] does not define")
            continue
        text = path.read_text(encoding="utf-8")
        matches = list(re.finditer(pattern, text))
        if not matches:
            errors.append(
                f"{rel_path}: the sentence stating the `{key}` floor was reworded — re-anchor VERSION_FLOOR_STATIC_REFS in this same change"
            )
            continue
        # Every occurrence, not the first: a reference that states a floor twice, and a
        # second one left behind by a bump, is exactly the drift this rule exists to catch.
        for match in matches:
            if match.group(1) != expected:
                line = text[: match.start()].count("\n") + 1
                errors.append(f"{rel_path}:{line}: states {match.group(1)} for floor `{key}`, but [vars.floors] says {expected}")

    errors.extend(_hardcoded_floors_in_templates(base_dir, floors))
    return errors


def _hardcoded_floors_in_templates(base_dir: Path, floors: dict[str, str]) -> list[str]:
    """A template must READ a floor, never spell it.

    A literal renders to the right number today and to the wrong one after the next
    bump, and nothing else sees it: strict mode only fires on an expression that is
    present and misspelled, and the presence check reads every skill at once, so a
    second sentence still reading the table keeps the value present.

    This one IS a numeric sweep, which the static-reference rule above deliberately
    is not, and the difference is what each reads. `skills/` is prose about the whole
    ecosystem, where `3.14` is a JSON example and `3.11` is matplotlib's version, so
    a sweep there would be mostly false. `templates/` is ours, every floor in it
    belongs in the table, and demanding an anchor per sentence would rebuild the same
    hand-kept list whose omissions this rule exists to catch. The escape is
    `TEMPLATE_FLOOR_LOOKALIKES` instead: a number that genuinely means something else
    is named there once, with its reason.
    """
    errors: list[str] = []
    templates_dir = base_dir / "templates"
    if not templates_dir.is_dir():
        return errors

    for template in sorted(templates_dir.rglob("*.j2")):
        text = template.read_text(encoding="utf-8")
        rel = template.relative_to(base_dir)
        for key, value in sorted(floors.items()):
            if (rel.as_posix(), value) in TEMPLATE_FLOOR_LOOKALIKES:
                continue
            start = text.find(value)
            while start != -1:
                line = text[:start].count("\n") + 1
                errors.append(
                    f"{rel}:{line}: spells floor `{key}` as the literal {value} — write `{{{{ floors.{key} }}}}` so the next bump reaches it, "
                    "or name it in TEMPLATE_FLOOR_LOOKALIKES if it means something else here"
                )
                start = text.find(value, start + 1)

    return errors


def check_python_pin(base_dir: Path) -> list[str]:
    """Hold `.python-version` to the floors in `pyproject.toml`, and every workflow to the file.

    The repository develops on the floor of `requires-python`, which is also the version the type
    checkers and ruff check against and the one CI runs. Before the pin, three places named an
    interpreter, or failed to name one, and nothing compared them, so a new worktree was built on
    whatever Python was newest on the machine. So each disagreement is named with the file to change:
    the pin itself when it is missing or not a single `X.Y`, `pyproject.toml` when one of its four
    versions differs from the pin, and a workflow when its `actions/setup-python` step passes a
    literal `python-version` or does not read `.python-version`. Raising the floor is then a one-line
    edit of the pin followed by whatever this names.
    """
    errors: list[str] = []
    pin_path = base_dir / PYTHON_PIN_FILE
    if not pin_path.is_file():
        errors.append(f"{PYTHON_PIN_FILE} is missing: it names the Python the repository develops on, the floor of requires-python")
    else:
        pin = pin_path.read_text(encoding="utf-8").strip()
        if PYTHON_PIN_PATTERN.fullmatch(pin):
            errors.extend(_pyproject_pin_errors(base_dir, pin))
        else:
            errors.append(f"{PYTHON_PIN_FILE} holds {pin!r}, not a single X.Y version such as 3.13")
    errors.extend(_workflow_pin_errors(base_dir))
    return errors


def _requires_python_floor(spec: str) -> str | None:
    """The version of the `>=` (or `~=`) clause of a `requires-python` specifier, if it has one."""
    for raw_clause in spec.split(","):
        clause = raw_clause.strip()
        for operator in (">=", "~="):
            if clause.startswith(operator):
                return clause.removeprefix(operator).strip()
    return None


def _pyproject_pin_errors(base_dir: Path, pin: str) -> list[str]:
    """Each version `pyproject.toml` states that is not the pin."""
    pyproject_path = base_dir / PYPROJECT_FILE
    if not pyproject_path.is_file():
        return [f"{PYPROJECT_FILE} is missing, so nothing states the floor {PYTHON_PIN_FILE} pins"]
    raw = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project: dict[str, Any] = raw.get("project", {})
    tool: dict[str, Any] = raw.get("tool", {})
    mypy: dict[str, Any] = tool.get("mypy", {})
    pyright: dict[str, Any] = tool.get("pyright", {})
    ruff: dict[str, Any] = tool.get("ruff", {})

    errors: list[str] = []
    requires_python = project.get("requires-python")
    floor = _requires_python_floor(requires_python) if isinstance(requires_python, str) else None
    if floor is None:
        errors.append(f"{PYPROJECT_FILE}: [project] requires-python states no >= floor, so nothing holds {PYTHON_PIN_FILE}'s {pin} to it")
    elif ".".join(floor.split(".")[:2]) != pin:
        errors.append(f"{PYPROJECT_FILE}: the floor of [project] requires-python is {floor}, but {PYTHON_PIN_FILE} pins {pin}")

    stated = (
        ("[tool.mypy] python_version", mypy.get("python_version"), pin),
        ("[tool.pyright] pythonVersion", pyright.get("pythonVersion"), pin),
        ("[tool.ruff] target-version", ruff.get("target-version"), "py" + pin.replace(".", "")),
    )
    for label, value, expected in stated:
        if value is None:
            errors.append(f"{PYPROJECT_FILE}: {label} is not set; it should be {expected!r}, the version {PYTHON_PIN_FILE} pins")
        elif value != expected:
            errors.append(f"{PYPROJECT_FILE}: {label} is {value!r}, but {PYTHON_PIN_FILE} pins {pin}, so it should be {expected!r}")
    return errors


def _workflow_pin_errors(base_dir: Path) -> list[str]:
    """Each `actions/setup-python` step that does not read the pin file, in every workflow."""
    workflows_dir = base_dir / WORKFLOWS_DIR
    if not workflows_dir.is_dir():
        return []
    errors: list[str] = []
    for workflow in sorted([*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")]):
        rel = workflow.relative_to(base_dir).as_posix()
        try:
            parsed: Any = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"{rel}: is not valid YAML, so its Python cannot be checked against {PYTHON_PIN_FILE} ({exc})")
            continue
        if not isinstance(parsed, dict):
            continue
        jobs: Any = cast(dict[str, Any], parsed).get("jobs")
        if not isinstance(jobs, dict):
            continue
        for job_id, job in cast(dict[str, Any], jobs).items():
            steps: Any = cast(dict[str, Any], job).get("steps") if isinstance(job, dict) else None
            if not isinstance(steps, list):
                continue
            for index, step in enumerate(cast(list[Any], steps), start=1):
                if not isinstance(step, dict):
                    continue
                step_map = cast(dict[str, Any], step)
                uses = step_map.get("uses")
                if not isinstance(uses, str) or not uses.startswith(SETUP_PYTHON_ACTION + "@"):
                    continue
                with_block: Any = step_map.get("with")
                inputs = cast(dict[str, Any], with_block) if isinstance(with_block, dict) else {}
                where = f"{rel}: job `{job_id}`, step {index} ({uses})"
                if "python-version" in inputs:
                    errors.append(
                        f"{where} passes the literal python-version {inputs['python-version']!r}; "
                        f"pass python-version-file: {PYTHON_PIN_FILE} instead, so CI runs the version the repository pins"
                    )
                elif inputs.get("python-version-file") != PYTHON_PIN_FILE:
                    errors.append(f"{where} does not pass python-version-file: {PYTHON_PIN_FILE}, so CI does not run the version the repository pins")
    return errors


def check_hook_provenance(base_dir: Path) -> list[str]:
    """Refuse a vendored hook bundle whose provenance no published source can reproduce.

    The bundle is built in `pipelex-sdk`'s `js/` and its banner names what from, so two things are
    readable here with no sibling checkout and no network: an engine bundled from an unreleased
    `tools-wasm` build through `PIPELEX_TOOLS_WASM_PATH`, and an SDK built outside a git checkout,
    whose commit the banner spells `unknown`. Either ships a hook nobody can rebuild. Whether the
    bundle is *behind* its sources needs both, which is `make check-hook-fresh`, a release gate.

    Only the template copy is read: the freshness check holds every target's copy to it byte for byte.
    """
    rel = HOOK_BUNDLE_PATH.as_posix()
    bundle_path = base_dir / HOOK_BUNDLE_PATH
    if not bundle_path.is_file():
        return [f"{rel}: the vendored hook bundle is missing — run `make vendor-hook`, then `make build`"]
    provenance = read_provenance(read_bundle(bundle_path))
    if provenance is None:
        return [
            f"{rel}: line 3 is not the provenance line `npm run build:hook` writes, so nothing says what the bundle was built from "
            "— re-vendor it with `make vendor-hook`, then `make build`"
        ]
    return [
        f"{rel}: {problem} — re-vendor from the js/ directory of the pipelex-sdk main checkout with PIPELEX_TOOLS_WASM_PATH unset "
        "(`make vendor-hook`), then `make build`"
        for problem in unpublished_sources(provenance)
    ]


def check_hook_notices(base_dir: Path) -> list[str]:
    """Refuse a vendored hook bundle that inlines a package its notices file does not name.

    The bundle is MIT code inside an ELv2 plugin, so it ships with `THIRD-PARTY-NOTICES.md` beside
    it, and a re-vendor that brings in a new dependency brings a notice nobody has written yet. The
    packages are read from the comments esbuild writes above each inlined module, and each has to
    appear in the notices file in backticks. Only the template copies are read: the freshness check
    holds every target's copies to them byte for byte.
    """
    bundle_path = base_dir / HOOK_BUNDLE_PATH
    notices_path = base_dir / HOOK_NOTICES_PATH
    if not bundle_path.is_file():
        return []  # check_hook_provenance reports the missing bundle
    if not notices_path.is_file():
        return [f"{HOOK_NOTICES_PATH.as_posix()}: missing — the hook bundle ships MIT code and needs its notice beside it"]
    notices = notices_path.read_text(encoding="utf-8")
    return [
        f"{HOOK_NOTICES_PATH.as_posix()}: `{package}` is inlined into {HOOK_BUNDLE_PATH.name} but not named here "
        "— add its licence and copyright to the notices file"
        for package in sorted(inlined_packages(read_bundle(bundle_path)))
        if f"`{package}`" not in notices
    ]


def check_shared_files_exist(base_dir: Path) -> list[str]:
    """Check that all expected shared template source files are present."""
    shared_dir = base_dir / "templates" / "skills" / "shared"
    errors: list[str] = []
    for name in SHARED_TEMPLATE_FILES:
        if not (shared_dir / name).is_file():
            errors.append(f"MISSING: templates/skills/shared/{name}")
    return errors


def check_no_templates_in_output(base_dir: Path) -> list[str]:
    """Check that no .j2 files leaked into output directories."""
    errors: list[str] = []

    def _scan_dir(directory: Path) -> None:
        if directory.is_dir():
            for j2_file in sorted(directory.rglob("*.j2")):
                rel = j2_file.relative_to(base_dir)
                errors.append(f"LEAKED TEMPLATE: {rel} (should be in templates/)")

    # At the root: the static sources under skills/, and whatever a root target renders into hooks/ and mcp/.
    _scan_dir(base_dir / "skills")
    _scan_dir(base_dir / "hooks")
    _scan_dir(base_dir / "mcp")
    # A target's own output directory holds nothing but output, so all of it is scanned.
    for output_dir in _collect_output_dirs(base_dir):
        if output_dir == base_dir:
            continue
        _scan_dir(output_dir)

    return errors


def check_no_claude_artifacts(base_dir: Path) -> list[str]:
    """Check that the Codex and Mistral Vibe outputs carry none of Claude Code's own artifacts.

    The skill templates are shared, so a Claude-only frontmatter key that leaked past its
    `platform == "claude"` guard would ship on a harness that does not read it. `allowed-tools` is
    the one that matters: it lists `mcp__plugin_…` tool names that exist on Claude Code alone. A
    `.claude-plugin/` directory is refused too, since Vibe rejects a plugin with two manifests as
    ambiguous and Codex would ship a manifest it never reads.
    """
    errors: list[str] = []
    configs = load_target_configs(base_dir)
    defaults = load_defaults_vars(base_dir)
    for target_name, config in configs.items():
        platform = _platform_for_config(config, defaults)
        match platform:
            case Platform.CLAUDE | Platform.AGENT_SKILLS:
                continue
            case Platform.CODEX | Platform.MISTRAL_VIBE:
                pass
        source = config.get("plugin", {}).get("source", "./")
        if source == "./":
            continue
        output_dir = base_dir / str(source).rstrip("/")
        claude_dir = output_dir / ".claude-plugin"
        if claude_dir.is_dir():
            errors.append(f"[{target_name}] .claude-plugin/ found in {platform} output {source}")
        for skill_md in sorted(output_dir.glob("skills/*/SKILL.md")):
            text = skill_md.read_text(encoding="utf-8")
            parts = text.split("---", 2)
            frontmatter = parts[1] if len(parts) >= 3 else ""
            for key in CLAUDE_ONLY_SKILL_KEYS:
                if re.search(rf"^{re.escape(key)}:", frontmatter, flags=re.MULTILINE):
                    rel = skill_md.relative_to(base_dir)
                    errors.append(f"[{target_name}] {rel}: contains '{key}' (Claude Code only, not read on {platform})")
    return errors


def _vibe_manifest_errors(target_name: str, manifest_path: Path, plugin_name: str) -> list[str]:
    """Check the Vibe build's `plugin.json` against the fields Mistral Vibe's resolver accepts.

    Vibe parses an Agent Plugins 1.0 manifest strictly: an unknown key, a `$schema` other than the
    1.0.0 one, or an `ai.mistral.vibe` extension without `schemaVersion = 1` makes it refuse the
    whole plugin, skills included (`vibe/core/plugins/_native.py`, `_PluginManifest`). The fields
    are mirrored here so that the build fails before a user's Vibe does. The build declares no
    extension, needing none of the components it enables, but one added later is held to them.
    """
    rel = VIBE_MANIFEST_PATH
    manifest = _read_json_object(manifest_path)
    if manifest is None:
        return [f"[{target_name}] {rel} is missing, not valid JSON, or not an object"]
    errors: list[str] = []
    unknown = sorted(set(manifest) - VIBE_MANIFEST_KEYS)
    if unknown:
        errors.append(f"[{target_name}] {rel} carries {', '.join(unknown)}, which Vibe's manifest refuses")
    if manifest.get("$schema") != VIBE_MANIFEST_SCHEMA:
        errors.append(f"[{target_name}] {rel} must declare $schema {VIBE_MANIFEST_SCHEMA}")
    name: object = manifest.get("name")
    if not isinstance(name, str) or not VIBE_PLUGIN_NAME_PATTERN.fullmatch(name) or "--" in name or ".." in name:
        errors.append(f"[{target_name}] {rel} name {name!r} is not a name Vibe accepts (lowercase letters, digits, dots and single hyphens)")
    elif name != plugin_name:
        errors.append(f"[{target_name}] {rel} name is {name!r}, targets/{target_name}.toml has {plugin_name!r}")
    author: object = manifest.get("author")
    if author is not None:
        if not isinstance(author, dict):
            errors.append(f"[{target_name}] {rel} author must be an object")
        else:
            unknown_author = sorted(set(cast(dict[str, object], author)) - VIBE_AUTHOR_KEYS)
            if unknown_author:
                errors.append(f"[{target_name}] {rel} author carries {', '.join(unknown_author)}, which Vibe's manifest refuses")
    extensions: object = manifest.get("extensions")
    extension: object = cast(dict[str, object], extensions).get(VIBE_EXTENSION) if isinstance(extensions, dict) else None
    if extension is not None and not isinstance(extension, dict):
        errors.append(f"[{target_name}] {rel} {VIBE_EXTENSION} extension must be an object")
    elif isinstance(extension, dict):
        fields = cast(dict[str, object], extension)
        if fields.get("schemaVersion") != 1:
            errors.append(f"[{target_name}] {rel} {VIBE_EXTENSION} extension must set schemaVersion = 1")
        unknown_extension = sorted(set(fields) - VIBE_EXTENSION_KEYS)
        if unknown_extension:
            errors.append(f"[{target_name}] {rel} {VIBE_EXTENSION} extension carries {', '.join(unknown_extension)}, which Vibe refuses")
    return errors


def _vibe_hook_command(plugin_name: str) -> str:
    """The command of the Vibe hook entry: the wrapper, found through the link the install makes."""
    return f'"${{VIBE_HOME:-$HOME/.vibe}}/plugins/{plugin_name}/hooks/check-mthds-vibe.sh"'


def _vibe_hooks_errors(target_name: str, hooks_path: Path, plugin_name: str) -> list[str]:
    """Check that the Vibe hook entry declares the one post_tool hook, naming the wrapper through the plugin's link.

    The user appends the entry to their own hooks file, which Vibe runs through the shell with its
    own environment, so the command reaches the wrapper through `$VIBE_HOME/plugins/<plugin>`, the
    link the install makes, quoted so that a home directory holding a space stays one word.
    """
    rel = VIBE_HOOKS_PATH
    if not hooks_path.is_file():
        return [f"[{target_name}] {rel} missing"]
    try:
        data = tomllib.loads(hooks_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return [f"[{target_name}] {rel} is not valid TOML: {exc}"]
    hooks: object = data.get("hooks")
    if not isinstance(hooks, list) or len(cast(list[object], hooks)) != 1 or not isinstance(cast(list[object], hooks)[0], dict):
        return [f"[{target_name}] {rel} must declare exactly one [[hooks]] table"]
    hook = cast(dict[str, object], cast(list[object], hooks)[0])
    errors: list[str] = []
    if hook.get("type") != "post_tool":
        errors.append(f'[{target_name}] {rel} must use type = "post_tool"')
    if hook.get("match") != VIBE_HOOK_MATCH:
        errors.append(f"[{target_name}] {rel} must match {VIBE_HOOK_MATCH}")
    expected_command = _vibe_hook_command(plugin_name)
    if hook.get("command") != expected_command:
        errors.append(f"[{target_name}] {rel} command must be {expected_command}")
    return errors


def _vibe_mcp_fragment_errors(target_name: str, fragment: Path) -> list[str]:
    """Check that the Vibe MCP fragment declares the workshop launcher Vibe can load.

    The fragment must parse as TOML and hold exactly one `[[mcp_servers]]` entry: the `pipelex`
    server over stdio, which keeps the tool names stable and spawns locally. Its `command` is a
    one-element list, since Vibe splits a string command with `shlex` and a launcher path holding a
    space would split with it (L-260912-0d6469). It carries no `env` table: the workshop reads the
    key its login saved, and an empty `PIPELEX_API_KEY` there would only invite pasting one in.
    """
    rel = VIBE_MCP_FRAGMENT_PATH
    try:
        data = tomllib.loads(fragment.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return [f"[{target_name}] {rel} is not valid TOML: {exc}"]
    servers: object = data.get("mcp_servers")
    if not isinstance(servers, list) or len(cast("list[object]", servers)) != 1:
        return [f"[{target_name}] {rel} must declare exactly one [[mcp_servers]] entry"]
    server: object = cast("list[object]", servers)[0]
    if not isinstance(server, dict):
        return [f"[{target_name}] {rel} [[mcp_servers]] entry is not a table"]
    entry = cast("dict[str, object]", server)
    errors: list[str] = []
    if entry.get("name") != MCP_SERVER_NAME:
        errors.append(f'[{target_name}] {rel} must name the server "{MCP_SERVER_NAME}"')
    if entry.get("transport") != "stdio":
        errors.append(f'[{target_name}] {rel} must use transport = "stdio"')
    command: object = entry.get("command")
    if not isinstance(command, list) or len(cast("list[object]", command)) != 1 or not cast("list[object]", command)[0]:
        errors.append(f"[{target_name}] {rel} must set command as a one-element list, which Vibe never splits")
    if "env" in entry:
        errors.append(f"[{target_name}] {rel} carries an env table; the workshop reads the key its login saved, so the entry ships none")
    return errors


def check_vibe_target_artifacts(base_dir: Path) -> list[str]:
    """Check that each Mistral Vibe target is the native plugin Vibe's resolver loads.

    The build is an Agent Plugins 1.0 plugin: `plugin.json` at its root, the skills, and the
    executable hook wrapper, with no other harness's manifest, no `mcp.json` and no hooks file of
    the plugin's own: a second manifest makes Vibe refuse the plugin as ambiguous, an `mcp.json`
    would start a workshop in the plugin's directory, outside the project, and Vibe 2.26.1 runs no
    hook a plugin declares. The hook and the workshop ship as `hooks/vibe-hooks.toml` and
    `mcp/vibe-mcp.toml` instead, the entries the user appends (docs/decisions.md).
    """
    errors: list[str] = []
    configs = load_target_configs(base_dir)
    defaults = load_defaults_vars(base_dir)
    for target_name, config in configs.items():
        match _platform_for_config(config, defaults):
            case Platform.MISTRAL_VIBE:
                pass
            case Platform.CLAUDE | Platform.CODEX | Platform.AGENT_SKILLS:
                continue
        plugin_section = config.get("plugin", {})
        source = plugin_section.get("source", "./")
        output_dir = base_dir if source == "./" else base_dir / str(source).rstrip("/")

        for dirname in (".claude-plugin", ".codex-plugin"):
            if (output_dir / dirname).exists():
                errors.append(f"[{target_name}] {dirname}/ found in Vibe output {source}, which Vibe would refuse as ambiguous")
        if (output_dir / "mcp.json").exists():
            errors.append(f"[{target_name}] mcp.json found in Vibe output {source}; it would start the workshop outside the project")

        if (output_dir / VIBE_PLUGIN_HOOKS_PATH).exists():
            errors.append(
                f"[{target_name}] {VIBE_PLUGIN_HOOKS_PATH} found in Vibe output {source}; Vibe 2.26.1 runs no hook a plugin declares, "
                f"so the hook ships as {VIBE_HOOKS_PATH}"
            )
        plugin_name = str(plugin_section.get("name", target_name))
        errors.extend(_vibe_manifest_errors(target_name, output_dir / VIBE_MANIFEST_PATH, plugin_name))
        errors.extend(_vibe_hooks_errors(target_name, output_dir / VIBE_HOOKS_PATH, plugin_name))

        hook_script = output_dir / "hooks" / "check-mthds-vibe.sh"
        if not hook_script.is_file():
            errors.append(f"[{target_name}] hooks/check-mthds-vibe.sh missing")
        elif not hook_script.stat().st_mode & 0o111:
            errors.append(f"[{target_name}] hooks/check-mthds-vibe.sh is not executable")

        mcp_fragment = output_dir / VIBE_MCP_FRAGMENT_PATH
        if not mcp_fragment.is_file():
            errors.append(f"[{target_name}] {VIBE_MCP_FRAGMENT_PATH} missing")
        else:
            errors.extend(_vibe_mcp_fragment_errors(target_name, mcp_fragment))

        for filename in ("hooks.json", "codex-hooks.json", "check-mthds.sh", "check-mthds-codex.sh"):
            if (output_dir / "hooks" / filename).exists():
                errors.append(f"[{target_name}] hooks/{filename} is not an artifact of the native Vibe plugin")

        expected_prefix = f"/{plugin_name}:"
        try:
            prefix = resolve_target_var(base_dir, target_name, "skill_prefix")
        except ValueError:
            errors.append(f"[{target_name}] defines no skill_prefix, the prefix a skill names another skill by")
        else:
            if prefix != expected_prefix:
                errors.append(
                    f"[{target_name}] skill_prefix is {prefix!r}, but Vibe names a plugin's skill {expected_prefix}<skill>, "
                    "so a skill named another way is never found"
                )

    return errors


def load_mcp_server_defaults(base_dir: Path) -> dict[str, Any]:
    """Read `[vars.mcp_server]` from the target defaults: empty when they declare no workshop launcher."""
    defaults_path = base_dir / TARGETS_DIR_NAME / DEFAULTS_FILE
    raw = tomllib.loads(defaults_path.read_text(encoding="utf-8"))
    mcp_server: object = raw.get("vars", {}).get("mcp_server", {})
    return cast(dict[str, Any], mcp_server) if isinstance(mcp_server, dict) else {}


def check_credential_wiring(base_dir: Path) -> list[str]:
    """Check that every generated target still carries the credential wiring `targets/defaults.toml` declares.

    The expectation is read from the defaults and never from a target's merged variables. A target
    whose own `[vars]` lost `env_vars` or `user_config` renders manifests and wrappers that agree with
    those variables, so the freshness check passes them, and only the defaults still say what went
    missing: a table override used to replace the defaults' table whole and do exactly that.

    - Claude: the manifest's `userConfig` offers every option, a sensitive one still sensitive; its
      `pipelex` server spawns the `launch-pipelex-mcp.sh` launcher with each option substituted into
      `PIPELEX_PLUGIN_<KEY>`; the launcher promotes each to `PIPELEX_<KEY>` only when it is non-empty,
      and the hook wrapper promotes `CLAUDE_PLUGIN_OPTION_<KEY>` the same way.
    - Codex: the manifest's `pipelex` server forwards every `env_vars` name into the spawn.
    - Mistral Vibe: nothing to forward. The fragment carries no `env` table, which
      `check_vibe_target_artifacts` holds it to, because the workshop reads the key its login saved.

    A file that is missing or does not parse is left to the checks that report exactly that.
    """
    mcp_server = load_mcp_server_defaults(base_dir)
    if not mcp_server:
        return []
    raw_options: object = mcp_server.get("user_config", {})
    options: dict[str, dict[str, Any]] = {}
    if isinstance(raw_options, dict):
        for key, option in cast(dict[str, object], raw_options).items():
            if isinstance(option, dict):
                options[key] = cast(dict[str, Any], option)
    raw_env_vars: object = mcp_server.get("env_vars", [])
    env_vars = [str(name) for name in cast(list[object], raw_env_vars)] if isinstance(raw_env_vars, list) else []

    errors: list[str] = []
    defaults = load_defaults_vars(base_dir)
    for target_name, config in load_target_configs(base_dir).items():
        source = config.get("plugin", {}).get("source", "./")
        output_dir = base_dir if source == "./" else base_dir / str(source).rstrip("/")
        label = f"[{target_name}] {output_dir.relative_to(base_dir).as_posix()}"
        match _platform_for_config(config, defaults):
            case Platform.CLAUDE:
                errors.extend(_claude_credential_errors(label, output_dir, options))
            case Platform.CODEX:
                errors.extend(_codex_credential_errors(label, output_dir, env_vars))
            case Platform.MISTRAL_VIBE:
                pass  # Vibe passes the spawn no shell variable, so there is nothing to forward
            case Platform.AGENT_SKILLS:
                pass  # an in-repo target on it is refused by check_target_platforms, and it declares no workshop
    return errors


def _read_json_object(path: Path) -> dict[str, Any] | None:
    """A JSON file's top-level object, or None when the file is missing, invalid or not an object."""
    if not path.is_file():
        return None
    try:
        data: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return cast(dict[str, Any], data) if isinstance(data, dict) else None


def _mcp_server_entry(manifest: dict[str, Any]) -> dict[str, Any] | None:
    """The manifest's `pipelex` MCP server entry, or None when it declares none."""
    servers: object = manifest.get("mcpServers")
    if not isinstance(servers, dict):
        return None
    entry: object = cast(dict[str, object], servers).get(MCP_SERVER_NAME)
    return cast(dict[str, Any], entry) if isinstance(entry, dict) else None


def _promotes(text: str, source: str, target: str) -> bool:
    """Whether a shell script exports `target` from `source`, guarded so an empty `source` changes nothing."""
    pattern = re.escape(f'if [[ -n "${{{source}:-}}" ]]; then') + r"\s+" + re.escape(f'export {target}="${source}"') + r"\s+fi\b"
    return re.search(pattern, text) is not None


def _claude_credential_errors(label: str, output_dir: Path, options: dict[str, dict[str, Any]]) -> list[str]:
    """The Claude half of `check_credential_wiring`: userConfig, the launcher entry, and both promotions."""
    if not options:
        return []  # no user configuration declared: the manifest spawns the workshop directly
    errors: list[str] = []
    manifest = _read_json_object(output_dir / ".claude-plugin" / "plugin.json")
    if manifest is not None:
        where = f"{label}/.claude-plugin/plugin.json"
        raw_offered: object = manifest.get("userConfig")
        offered = cast(dict[str, object], raw_offered) if isinstance(raw_offered, dict) else {}
        for key, option in options.items():
            offer = offered.get(key)
            if not isinstance(offer, dict):
                errors.append(f"{where}: userConfig offers no `{key}` option, which [vars.mcp_server.user_config] declares")
            elif option.get("sensitive") is True and cast(dict[str, object], offer).get("sensitive") is not True:
                errors.append(f"{where}: userConfig `{key}` is no longer sensitive, so its value would be stored outside the keychain")
        entry = _mcp_server_entry(manifest)
        if entry is None:
            errors.append(f"{where}: declares no `{MCP_SERVER_NAME}` MCP server")
        else:
            if entry.get("command") != CLAUDE_MCP_LAUNCHER_COMMAND:
                errors.append(
                    f"{where}: the `{MCP_SERVER_NAME}` server does not spawn {CLAUDE_MCP_LAUNCHER_COMMAND}, the launcher that promotes the options"
                )
            raw_env: object = entry.get("env")
            env = cast(dict[str, object], raw_env) if isinstance(raw_env, dict) else {}
            for key in options:
                name = f"PIPELEX_PLUGIN_{key.upper()}"
                substitution = f"${{user_config.{key}}}"
                if env.get(name) != substitution:
                    errors.append(f"{where}: the `{MCP_SERVER_NAME}` server's env does not set {name} to {substitution}")
    for script, prefix in (("launch-pipelex-mcp.sh", "PIPELEX_PLUGIN_"), ("check-mthds.sh", "CLAUDE_PLUGIN_OPTION_")):
        script_path = output_dir / "hooks" / script
        if not script_path.is_file():
            continue
        text = script_path.read_text(encoding="utf-8")
        for key in options:
            source, target = f"{prefix}{key.upper()}", f"PIPELEX_{key.upper()}"
            if not _promotes(text, source, target):
                errors.append(f"{label}/hooks/{script}: does not promote {source} to {target} when it is non-empty")
    return errors


def _codex_credential_errors(label: str, output_dir: Path, env_vars: list[str]) -> list[str]:
    """The Codex half of `check_credential_wiring`: the names forwarded into the workshop's spawn."""
    manifest = _read_json_object(output_dir / ".codex-plugin" / "plugin.json")
    if manifest is None or not env_vars:
        return []
    where = f"{label}/.codex-plugin/plugin.json"
    entry = _mcp_server_entry(manifest)
    if entry is None:
        return [f"{where}: declares no `{MCP_SERVER_NAME}` MCP server"]
    raw_forwarded: object = entry.get("env_vars")
    forwarded = [str(name) for name in cast(list[object], raw_forwarded)] if isinstance(raw_forwarded, list) else []
    missing = [name for name in env_vars if name not in forwarded]
    if not missing:
        return []
    return [
        f"{where}: the `{MCP_SERVER_NAME}` server's env_vars forwards no {', '.join(missing)}; "
        "Codex spawns it with a whitelisted environment, so the workshop would never see it"
    ]


def _run_check(title: str, errors: list[str], failure_message: str, success_message: str) -> bool:
    """Print a formatted check result and return whether it failed."""
    print(title)
    if errors:
        for error in errors:
            if error.startswith("MISSING:") or error.startswith("LEAKED TEMPLATE:"):
                print(f"  {error}")
            else:
                print(f"  MISMATCH: {error}")
        print(failure_message)
        return True

    print(success_message)
    return False


def _report_skill_ceiling(base_dir: Path) -> bool:
    """Print the ceiling report, and fail when any SKILL.md is over the ceiling."""
    over = check_skill_ceiling(base_dir)
    print(f"Checking every SKILL.md against the {SKILL_CEILING_CHARS}-character compaction ceiling...")
    if not over:
        print("  Every SKILL.md fits under the ceiling.")
        return False
    for line in over:
        print(f"  OVER: {line}")
    print("FAIL: A SKILL.md is longer than the compaction ceiling.")
    return True


def run_shared_checks(base_dir: Path) -> bool:
    """Run platform-agnostic repository checks."""
    failed = False

    print("Checking target plugin versions...")
    try:
        errors, versions = check_target_plugin_versions(base_dir)
    except ValueError as exc:
        print(f"  {exc}")
        print("FAIL: Cannot read target configs.")
        return True

    if errors:
        for error in errors:
            print(f"  MISMATCH: {error}")
        print("FAIL: Target plugin versions are inconsistent.")
        failed = True
    else:
        for target_name, version in versions.items():
            print(f"  [{target_name}] version: {version}")
        print("  All target plugin versions consistent.")

    failed |= _run_check(
        "Checking every in-repo target renders for an in-repo platform...",
        check_target_platforms(base_dir),
        "FAIL: An in-repo target names a platform meant for outside targets only.",
        "  Every in-repo target renders for claude, codex or mistral-vibe.",
    )

    failed |= _run_check(
        "Checking target versions are in matched-version lockstep...",
        check_matched_target_versions(base_dir),
        "FAIL: Target versions have drifted — bump all of them together.",
        "  All target versions match.",
    )

    failed |= _run_check(
        "Checking version floors against targets/defaults.toml...",
        check_version_floors(base_dir),
        "FAIL: A version floor drifted from [vars.floors], or did not reach the built skills.",
        "  Version floors match [vars.floors] and reach every target.",
    )

    failed |= _run_check(
        f"Checking {PYTHON_PIN_FILE} against {PYPROJECT_FILE}'s floors and the workflows...",
        check_python_pin(base_dir),
        f"FAIL: The Python {PYTHON_PIN_FILE} pins disagrees with a floor in {PYPROJECT_FILE}, or a workflow does not read it.",
        f"  {PYTHON_PIN_FILE} matches every floor in {PYPROJECT_FILE}, and every workflow reads it.",
    )

    failed |= _run_check(
        "Checking for stale references/ paths to shared files...",
        check_stale_references(base_dir),
        "FAIL: Found stale references/ paths (should use ../shared/ instead).",
        "  No stale references found.",
    )
    failed |= _run_check(
        "Checking skill bodies for tokens Claude Code replaces with invocation arguments...",
        check_skill_argument_placeholders(base_dir),
        "FAIL: Found $ARGUMENTS or $<digit> in a SKILL.md. Rewrite without the token (an escape reaches Codex and Vibe verbatim).",
        "  No argument placeholders found.",
    )
    failed |= _run_check(
        "Checking every SKILL.md frontmatter parses as strict YAML...",
        check_skill_frontmatter(base_dir),
        "FAIL: A SKILL.md frontmatter is not valid YAML, or lacks its name or description. Quote the value or reword it.",
        "  Every SKILL.md frontmatter is valid YAML with its name and description.",
    )
    failed |= _run_check(
        "Checking every generated file for a build-error marker...",
        check_build_error_markers(base_dir),
        "FAIL: A template rendered its build-error branch: a parameter was given a value none of its branches names.",
        "  No generated file carries a build-error marker.",
    )
    failed |= _run_check(
        "Checking that links resolve both ways in every target...",
        check_skill_links(base_dir),
        "FAIL: A link names no file or heading, or a shipped reference, script or shared file is named by nothing.",
        "  Every link resolves, and every shipped reference, script and shared file is named.",
    )
    failed |= _report_skill_ceiling(base_dir)
    failed |= _run_check(
        "Checking all shared template files exist...",
        check_shared_files_exist(base_dir),
        "FAIL: Some shared template files are missing.",
        "  All shared template files present.",
    )
    failed |= _run_check(
        "Checking for leaked .j2 files in output directories...",
        check_no_templates_in_output(base_dir),
        "FAIL: Found .j2 template files in output directories (should be in templates/).",
        "  No leaked templates found.",
    )
    failed |= _run_check(
        "Checking the vendored hook bundle was built from published sources...",
        check_hook_provenance(base_dir),
        "FAIL: The vendored hook bundle names a source no published artifact reproduces.",
        "  The hook bundle was built from an SDK commit and @pipelex/tools-wasm from npm.",
    )
    failed |= _run_check(
        "Checking the hook bundle's notices name every package it inlines...",
        check_hook_notices(base_dir),
        "FAIL: The hook bundle inlines a package its notices file does not name.",
        "  Every package the hook bundle inlines is named in its notices file.",
    )
    failed |= _run_check(
        "Checking Codex and Mistral Vibe targets for Claude Code artifacts...",
        check_no_claude_artifacts(base_dir),
        "FAIL: A Codex or Mistral Vibe target contains a Claude Code artifact.",
        "  No Claude Code artifacts in Codex or Mistral Vibe targets.",
    )
    failed |= _run_check(
        "Checking Mistral Vibe target artifacts...",
        check_vibe_target_artifacts(base_dir),
        "FAIL: Mistral Vibe target artifacts are inconsistent.",
        "  Mistral Vibe target artifacts are consistent.",
    )
    failed |= _run_check(
        "Checking every target's credential wiring against targets/defaults.toml...",
        check_credential_wiring(base_dir),
        "FAIL: A generated target lost credential wiring [vars.mcp_server] in targets/defaults.toml declares.",
        "  Every target carries the credential wiring the defaults declare.",
    )

    return failed


def run_claude_checks(base_dir: Path) -> bool:
    """Run Claude-specific packaging checks."""
    return _run_check(
        "Checking Claude marketplace entries...",
        check_marketplace_plugins(base_dir),
        "FAIL: Claude marketplace entries are inconsistent with target configs.",
        "  Claude marketplace matches target configs.",
    )


def run_codex_checks(base_dir: Path) -> bool:
    """Run Codex-specific packaging checks."""
    return _run_check(
        "Checking Codex packaging marketplace entries...",
        check_codex_marketplace_plugins(base_dir),
        "FAIL: Codex packaging marketplace entries are inconsistent with target configs.",
        "  Codex packaging marketplace matches target configs.",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=("all", "shared", "claude", "codex"),
        default="all",
        help="Limit checks to a scope. Default: all.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base_dir = Path(__file__).resolve().parent.parent

    failed = False
    if args.scope in {"all", "shared"}:
        failed |= run_shared_checks(base_dir)
    if args.scope in {"all", "claude"}:
        failed |= run_claude_checks(base_dir)
    if args.scope in {"all", "codex"}:
        failed |= run_codex_checks(base_dir)

    if failed:
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
