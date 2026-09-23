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

from scripts.gen_skill_docs import MCP_SERVER_NAME, SHARED_TEMPLATES, Platform

SHARED_TEMPLATE_FILES = [Path(template_path).name for template_path in SHARED_TEMPLATES]
_SHARED_STEMS = [Path(template_path).name.removesuffix(".md.j2") for template_path in SHARED_TEMPLATES]
STALE_REF_PATTERN = re.compile(r"references/(?:" + "|".join(re.escape(stem) for stem in _SHARED_STEMS) + r")")
# A shared include whose variant parameter is unset or misspelled emits this marker instead of
# rendering as the empty string: Jinja's default `Undefined` compares unequal without raising, so
# a typo would otherwise ship a skill with a whole block silently missing.
BUILD_ERROR_MARKER = "PIPELEX_BUILD_ERROR"
# Claude Code replaces `$ARGUMENTS`, `$ARGUMENTS[N]` and `$N` in a skill body with the invocation's arguments.
ARGUMENT_PLACEHOLDER_PATTERN = re.compile(r"\$(?:ARGUMENTS|\d+)")

# The compaction ceiling (box C of `wip/skill-size-diet/design.md`). After a compaction Claude
# Code re-attaches each invoked skill within 5,000 tokens, so a SKILL.md longer than that is
# carried forward as its head alone and loses whatever its tail guarded. The ceiling is counted
# in characters, which a check can count exactly, and derived from tokens in phase 0: 5,000
# times the lowest characters-per-token ratio measured over every rendered SKILL.md on every
# target (2.77, the Claude 5 tokenizer), less a margin — `wip/skill-size-diet/facts.md`.
SKILL_CEILING_CHARS = 13_000
# Report mode until the diet's last phase brings every skill under the ceiling; then it fails.
SKILL_CEILING_ENFORCED = False

# A Markdown link's target: `[text](target)`, the target running to the first `)` or space.
MARKDOWN_LINK_PATTERN = re.compile(r"\]\(([^)\s]+)\)")
FENCED_BLOCK_PATTERN = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
INLINE_CODE_PATTERN = re.compile(r"`[^`\n]*`")
# Where a skill names one of its own scripts: after the skill-directory expression, whatever a
# target spells it as, so the check keys on the `/scripts/<name>` tail that every spelling shares.
SKILL_SCRIPT_MENTION_PATTERN = re.compile(r"/scripts/([A-Za-z0-9_.\-/]+)")

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
# bare numeric sweep would read `writing-mthds.md`'s JSON `"number"` example of
# `3.14` as the Python ceiling and `png.md`'s matplotlib `3.11` as the Python
# floor. A reworded reference fails this check instead of passing silently, which
# is the right way round — re-anchor the pattern in the same change that rewords
# the sentence.
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
        "skills/pipelex-integrate/references/typescript.md",
        r"the SDK's own Node floor \(>= (\d+\.\d+)\)",
        "node",
    ),
    (
        "skills/pipelex-integrate/references/codegen-check.mjs",
        r'const SDK_MINIMUM = "(\d+\.\d+\.\d+)";',
        "pipelex_sdk_js",
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
        "skills/pipelex-scaffold/references/starters.md",
        "Node \u2265 the `engines\\.node` field of `package\\.json` \\((\\d+\\.\\d+) at writing\\)",
        "node",
    ),
    (
        "skills/pipelex-scaffold/references/starters.md",
        "a Python inside `requires-python` of `pyproject\\.toml` \\((\\d+\\.\\d+)\u2013\\d+\\.\\d+ at writing\\)",
        "python_min",
    ),
    (
        "skills/pipelex-scaffold/references/starters.md",
        "a Python inside `requires-python` of `pyproject\\.toml` \\(\\d+\\.\\d+\u2013(\\d+\\.\\d+) at writing\\)",
        "python_max",
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

        platform = _platform_for_config(config, defaults)
        if platform == Platform.MISTRAL_VIBE:
            versions[target_name] = str(config_version)
            continue
        manifest_dirname = ".codex-plugin" if platform == Platform.CODEX else ".claude-plugin"

        if source == "./":
            plugin_json_path = base_dir / manifest_dirname / "plugin.json"
        else:
            plugin_json_path = base_dir / str(source).rstrip("/") / manifest_dirname / "plugin.json"

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
    string `name` equal to the skill's directory and a string `description`.
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
            if not isinstance(fields.get("description"), str) or not fields["description"].strip():
                errors.append(f"{rel}: frontmatter carries no string `description`")
    return errors


def check_build_error_markers(base_dir: Path) -> list[str]:
    """Check that no generated file carries a shared include's build-error marker.

    A shared partial that branches on a variant parameter emits `PIPELEX_BUILD_ERROR` when the
    including template set no variant or misspelled one. Without it the branch would render as the
    empty string, and the block would vanish from the shipped skill with the build, the freshness
    check and the tests all green.
    """
    errors: list[str] = []
    for output_dir in _collect_output_dirs(base_dir):
        for skill_md in sorted(output_dir.glob("skills/*/SKILL.md")):
            for idx, line in enumerate(skill_md.read_text(encoding="utf-8").splitlines(), start=1):
                if BUILD_ERROR_MARKER in line:
                    rel = skill_md.relative_to(base_dir)
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


def _markdown_prose(text: str) -> str:
    """The text with fenced blocks and inline code blanked, so an example is never read as a link."""
    text = FENCED_BLOCK_PATTERN.sub(lambda match: "\n" * match.group(0).count("\n"), text)
    return INLINE_CODE_PATTERN.sub("``", text)


def _heading_slugs(text: str) -> set[str]:
    """The anchors GitHub-flavoured Markdown gives the file's headings.

    Lowercased, every character that is not a letter, a digit, a space, a hyphen or an underscore
    dropped, and each space turned into a hyphen — so `Step 8 — a method` becomes `step-8--a-method`.
    """
    slugs: set[str] = set()
    for line in _markdown_prose(text).splitlines():
        match = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if match:
            heading = re.sub(r"[^\w\- ]", "", match.group(1).lower())
            slugs.add(heading.replace(" ", "-"))
    return slugs


def _link_targets(text: str) -> list[str]:
    """Every relative link target in the prose of a Markdown file, anchors included."""
    targets: list[str] = []
    for match in MARKDOWN_LINK_PATTERN.finditer(_markdown_prose(text)):
        target = match.group(1)
        if re.match(r"^[a-z][a-z0-9+.\-]*:", target) or target.startswith("/"):
            continue  # a URL, a mailto: or an absolute path is not a file of the plugin
        targets.append(target)
    return targets


def check_skill_links(base_dir: Path) -> list[str]:
    """Links resolve both ways in every target (box H of `wip/skill-size-diet/design.md`).

    Forward: every relative link in a skill, a reference or a shared file names a file that
    exists in the same target, and every anchor names a heading of the file it points into.
    Backward: every file a skill ships under `references/` or `scripts/` is named by something the
    model reads first — a reference by a SKILL.md link, a script by a SKILL.md or by a reference of
    its own skill — and every shared file by a skill or a reference. A pointer to nothing sends the
    model to a read that fails; a file named by nothing is a caveat no model will ever read.
    """
    errors: list[str] = []
    for output_dir in _collect_output_dirs(base_dir):
        skills_dir = output_dir / "skills"
        markdown_files = sorted(skills_dir.glob("*/SKILL.md")) + sorted(skills_dir.glob("*/references/**/*.md")) + sorted(skills_dir.glob("shared/*.md"))
        named: set[Path] = set()
        for md_file in markdown_files:
            text = md_file.read_text(encoding="utf-8")
            rel = md_file.relative_to(base_dir)
            for target in _link_targets(text):
                path_part, _, anchor = target.partition("#")
                resolved = (md_file.parent / path_part).resolve() if path_part else md_file.resolve()
                if path_part:
                    if not resolved.is_file():
                        errors.append(f"{rel}: link to `{target}` names no file in this target")
                        continue
                    if md_file.name == "SKILL.md" or resolved.parent.name == "scripts":
                        named.add(resolved)
                    elif resolved.parent.name == "shared":
                        named.add(resolved)
                if anchor and resolved.suffix == ".md" and anchor not in _heading_slugs(resolved.read_text(encoding="utf-8")):
                    errors.append(f"{rel}: anchor `#{anchor}` names no heading of {resolved.name}")
            skill_root = md_file.parent if md_file.name == "SKILL.md" else md_file.parent.parent
            for match in SKILL_SCRIPT_MENTION_PATTERN.finditer(text):
                script = (skill_root / "scripts" / match.group(1).rstrip(".")).resolve()
                if script.is_file():
                    named.add(script)
        for asset in sorted(skills_dir.glob("*/references/**/*")) + sorted(skills_dir.glob("*/scripts/**/*")):
            if asset.is_file() and asset.resolve() not in named:
                errors.append(f"{asset.relative_to(base_dir)}: shipped but named by nothing the model reads")
        for shared in sorted(skills_dir.glob("shared/*.md")):
            if shared.resolve() not in named:
                errors.append(f"{shared.relative_to(base_dir)}: shipped but named by no skill and no reference")
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
        # Every occurrence, not the first: `starters.md` states the Node floor once per
        # template column, so a second one left behind by a bump is exactly the drift
        # this rule exists to catch.
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

    _scan_dir(base_dir / "skills")
    _scan_dir(base_dir / "hooks")
    for output_dir in _collect_output_dirs(base_dir):
        if output_dir == base_dir:
            continue
        _scan_dir(output_dir / "skills")
        _scan_dir(output_dir / "hooks")

    return errors


def check_codex_no_claude_artifacts(base_dir: Path) -> list[str]:
    """Check that Codex output directories do not contain Claude-only artifacts."""
    errors: list[str] = []
    configs = load_target_configs(base_dir)
    defaults = load_defaults_vars(base_dir)
    for target_name, config in configs.items():
        if _platform_for_config(config, defaults) != Platform.CODEX:
            continue
        source = config.get("plugin", {}).get("source", "./")
        if source == "./":
            continue
        output_dir = base_dir / str(source).rstrip("/")
        claude_dir = output_dir / ".claude-plugin"
        if claude_dir.is_dir():
            errors.append(f"[{target_name}] .claude-plugin/ found in Codex output {source}")
        for skill_md in sorted(output_dir.glob("skills/*/SKILL.md")):
            text = skill_md.read_text(encoding="utf-8")
            parts = text.split("---", 2)
            frontmatter = parts[1] if len(parts) >= 3 else ""
            if "allowed-tools:" in frontmatter:
                rel = skill_md.relative_to(base_dir)
                errors.append(f"[{target_name}] {rel}: contains 'allowed-tools' (not supported in Codex)")
    return errors


def _vibe_mcp_fragment_errors(target_name: str, fragment: Path) -> list[str]:
    """Check that the Vibe MCP fragment declares the workshop launcher Vibe can load.

    The fragment must parse as TOML and hold exactly one `[[mcp_servers]]` entry:
    the `pipelex` server over stdio with a command, which is the only shape that
    keeps tool names stable (`pipelex_mthds_validate` on Vibe) and spawns locally.
    """
    rel = "mcp/vibe-mcp.toml"
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
    if not entry.get("command"):
        errors.append(f"[{target_name}] {rel} must set a command")
    return errors


def check_vibe_target_artifacts(base_dir: Path) -> list[str]:
    """Check that Mistral Vibe targets emit Vibe-only hook and MCP artifacts.

    Vibe is not a Claude/Codex plugin platform: it loads skills via skill_paths,
    hooks from hooks.toml, and MCP servers from config.toml. The generated target
    must therefore not carry a plugin manifest, it must render the post_tool hook
    config/script pair, and it must render the workshop launcher as the
    `mcp/vibe-mcp.toml` config fragment.
    """
    errors: list[str] = []
    configs = load_target_configs(base_dir)
    defaults = load_defaults_vars(base_dir)
    for target_name, config in configs.items():
        if _platform_for_config(config, defaults) != Platform.MISTRAL_VIBE:
            continue
        source = config.get("plugin", {}).get("source", "./")
        output_dir = base_dir if source == "./" else base_dir / str(source).rstrip("/")

        for dirname in (".claude-plugin", ".codex-plugin"):
            if (output_dir / dirname).exists():
                errors.append(f"[{target_name}] {dirname}/ found in Vibe output {source}")

        hook_config = output_dir / "hooks" / "vibe-hooks.toml"
        hook_script = output_dir / "hooks" / "check-mthds-vibe.sh"
        if not hook_config.is_file():
            errors.append(f"[{target_name}] hooks/vibe-hooks.toml missing")
        else:
            text = hook_config.read_text(encoding="utf-8")
            if 'type = "post_tool"' not in text:
                errors.append(f'[{target_name}] hooks/vibe-hooks.toml must use type = "post_tool"')
            if 'match = "re:^(edit|write_file)$"' not in text:
                errors.append(f"[{target_name}] hooks/vibe-hooks.toml must match edit/write_file")
            if "check-mthds-vibe.sh" not in text:
                errors.append(f"[{target_name}] hooks/vibe-hooks.toml must call check-mthds-vibe.sh")

        if not hook_script.is_file():
            errors.append(f"[{target_name}] hooks/check-mthds-vibe.sh missing")
        elif not hook_script.stat().st_mode & 0o111:
            errors.append(f"[{target_name}] hooks/check-mthds-vibe.sh is not executable")

        mcp_fragment = output_dir / "mcp" / "vibe-mcp.toml"
        if not mcp_fragment.is_file():
            errors.append(f"[{target_name}] mcp/vibe-mcp.toml missing")
        else:
            errors.extend(_vibe_mcp_fragment_errors(target_name, mcp_fragment))

        for filename in ("hooks.json", "codex-hooks.json", "check-mthds.sh", "check-mthds-codex.sh"):
            if (output_dir / "hooks" / filename).exists():
                errors.append(f"[{target_name}] hooks/{filename} is not a Vibe artifact")

    return errors


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
    """Print the ceiling report; fail on it only once the ceiling is enforced."""
    over = check_skill_ceiling(base_dir)
    mode = "enforced" if SKILL_CEILING_ENFORCED else "report only"
    print(f"Checking every SKILL.md against the {SKILL_CEILING_CHARS}-character compaction ceiling ({mode})...")
    if not over:
        print("  Every SKILL.md fits under the ceiling.")
        return False
    for line in over:
        print(f"  OVER: {line}")
    if SKILL_CEILING_ENFORCED:
        print("FAIL: A SKILL.md is longer than the compaction ceiling.")
        return True
    print(f"  {len(over)} SKILL.md files over the ceiling; reporting only until the diet's last phase.")
    return False


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
        "Checking for unresolved shared-include variants...",
        check_build_error_markers(base_dir),
        "FAIL: A shared include rendered its build-error branch (the including template set no variant, or misspelled one).",
        "  Every shared include resolved its variant.",
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
        "Checking Mistral Vibe target artifacts...",
        check_vibe_target_artifacts(base_dir),
        "FAIL: Mistral Vibe target artifacts are inconsistent.",
        "  Mistral Vibe target artifacts are consistent.",
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
    """Run Codex-specific packaging and artifact checks."""
    failed = False
    failed |= _run_check(
        "Checking Codex packaging marketplace entries...",
        check_codex_marketplace_plugins(base_dir),
        "FAIL: Codex packaging marketplace entries are inconsistent with target configs.",
        "  Codex packaging marketplace matches target configs.",
    )
    failed |= _run_check(
        "Checking Codex targets for Claude artifacts...",
        check_codex_no_claude_artifacts(base_dir),
        "FAIL: Codex target contains Claude-specific artifacts.",
        "  No Claude artifacts in Codex targets.",
    )
    return failed


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
