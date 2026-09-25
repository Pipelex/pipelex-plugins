#!/usr/bin/env python3
"""Generate skill docs, shared files, and hooks from Jinja2 templates.

Renders all .j2 templates under templates/ and writes the corresponding
output files (skills/, hooks/, mcp/). Templates (.j2) are the source of truth;
output files are build artifacts checked into git. The build owns each
target's output directory, so it also removes from it whatever no template or
source produces any more, and `--check` compares the directory's whole file
set, not only the files it renders.

Supports multiple build targets (prod, codex, mistral-vibe) defined in
targets/*.toml. Each target can override template variables, filter skills,
and write output to a different directory.

This is the CLI-free plugin generation: there is no install/upgrade/env-check
machinery, so the renderer carries none of the `env_check` / `can_run_methods`
/ `session_start_hook` switches or the `bin/` self-install assets that the
`mthds-plugins` predecessor had.

Usage:
    python scripts/gen_skill_docs.py                    # build prod target
    python scripts/gen_skill_docs.py --target prod      # build prod target
    python scripts/gen_skill_docs.py --target codex     # build codex target
    python scripts/gen_skill_docs.py --target all       # build all targets
    python scripts/gen_skill_docs.py --target prod --check  # verify freshness
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import stat
import subprocess
import sys
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TypeAlias, cast

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound, TemplateSyntaxError, UndefinedError


class Platform(StrEnum):
    CLAUDE = "claude"
    CODEX = "codex"
    MISTRAL_VIBE = "mistral-vibe"


# A template variable is a scalar (coerced to str), a bool switch, a list, or a
# nested TOML table (e.g. [vars.mcp_server] carrying the launcher command).
TemplateVarValue: TypeAlias = "str | bool | list[str] | dict[str, object]"


TARGETS_DIR_NAME = "targets"
DEFAULTS_FILE = "defaults.toml"
TEMPLATES_DIR_NAME = "templates"

# The repository's own directories, relative to its root: the build's sources, the files it writes
# outside any target (`.agents/`), and everything else that is nobody's output. The build prunes
# each target's output directory down to what it produces, so a target whose `source` held one of
# these, or sat inside one, would have its files deleted as output nothing produces:
# `check_output_dir` refuses such a target instead.
REPOSITORY_OWN_PATHS = (
    ".agents",
    ".claude",
    ".claude-plugin",
    ".codex-plugin",
    ".git",
    ".github",
    ".venv",
    "docs",
    "packaging",
    "scripts",
    "skills",
    TARGETS_DIR_NAME,
    TEMPLATES_DIR_NAME,
    "tests",
    "wip",
)

# Codex discovers plugin marketplaces at `.agents/plugins/marketplace.json`
# (preferred) or `.claude-plugin/marketplace.json` (fallback). We ship a
# Codex-discoverable copy of `packaging/codex-marketplace.json` at the repo
# root so `codex plugin marketplace add Pipelex/pipelex-plugins` works without
# an install script. The canonical file remains the single source of truth;
# this is a verbatim copy.
CODEX_DISCOVERY_MARKETPLACE_SRC = Path("packaging/codex-marketplace.json")
CODEX_DISCOVERY_MARKETPLACE_DST = Path(".agents/plugins/marketplace.json")

# The per-skill static asset directories under the repo-root `skills/<skill>/`, copied
# verbatim into every target beside the rendered SKILL.md: `references/` holds what a
# branch reads on demand, `scripts/` the programs a skill runs by path.
STATIC_ASSET_DIRS = ("references", "scripts")

# Shared reference files, rendered standalone per target: the MTHDS language
# reference (`writing-mthds.md`, the one every skill that reads or writes a bundle
# points at) and the native content types that ground the skills, and the files a
# skill reads when one of its stops fires or one of its branches is taken, such as
# `credentials.md` and `catalog-id.md`. Paths are relative to the templates/
# directory.
#
# The include-only partials under `skills/shared/` — `frontmatter.md.j2` and the
# shared blocks — are deliberately NOT listed here: they are {% include %}-d by
# skill templates, so they must exist as files but should not be rendered
# standalone (that would only ship a fragment).
SHARED_TEMPLATES = [
    "skills/shared/writing-mthds.md.j2",
    "skills/shared/native-content-types.md.j2",
    "skills/shared/credentials.md.j2",
    "skills/shared/catalog-id.md.j2",
]

# Hook templates rendered for the Claude target: the PostToolUse wiring plus the
# bundled `.mthds`-on-edit validation script. The CLI-free posture ports the
# validation pipeline but flips missing-CLI behavior from block-with-install-hint
# to silent pass — the hook no-ops when `plxt`/`mthds-agent`/`node` are absent
# instead of blocking every edit. The predecessor's session-start doctor hook is
# left behind (CLI-lifecycle territory).
HOOK_TEMPLATES = [
    "hooks/hooks.json.j2",
    "hooks/check-mthds.sh.j2",
    "hooks/launch-pipelex-mcp.sh.j2",
]

# Hook templates by platform:
# - Claude: hooks/hooks.json + the check-mthds.sh wrapper, and the
#   launch-pipelex-mcp.sh launcher the manifest's MCP entry spawns.
# - Codex: hooks/codex-hooks.json (the plugin-bundled PostToolUse config,
#   referenced from the Codex manifest's `hooks` field; ${PLUGIN_ROOT} is
#   substituted by Codex's hook engine) + the check-mthds-codex.sh wrapper.
# - Mistral Vibe: hooks/vibe-hooks.toml + the check-mthds-vibe.sh wrapper.
# Each wrapper is a thin fail-open guard around the shared check.mjs bundle,
# invoked with the matching --platform flag.
HOOK_TEMPLATES_BY_PLATFORM: dict[Platform, list[str]] = {
    Platform.CLAUDE: HOOK_TEMPLATES,
    Platform.CODEX: ["hooks/codex-hooks.json.j2", "hooks/check-mthds-codex.sh.j2"],
    Platform.MISTRAL_VIBE: ["hooks/vibe-hooks.toml.j2", "hooks/check-mthds-vibe.sh.j2"],
}

# MCP templates by platform: the workshop launcher's declaration where a
# platform has no plugin manifest to carry it. Mistral Vibe gets
# mcp/vibe-mcp.toml, a [[mcp_servers]] config fragment the user copies into
# ~/.vibe/config.toml, as with vibe-hooks.toml. The Claude and Codex manifests
# declare the server themselves (make_plugin_json).
MCP_TEMPLATES_BY_PLATFORM: dict[Platform, list[str]] = {
    Platform.CLAUDE: [],
    Platform.CODEX: [],
    Platform.MISTRAL_VIBE: ["mcp/vibe-mcp.toml.j2"],
}

# Static hook assets by platform: prebuilt files copied VERBATIM (no Jinja
# rendering) from templates/hooks/assets/ to the target's hooks/ directory.
# Today that is the vendored `check.mjs` bundle — the .mthds validation hook
# built in pipelex-sdk-js (`npm run build:hook`, see docs/hooks.md for the
# re-vendor procedure). It carries a provenance header and inlines a WASM
# engine, so it must never pass through the template engine. One bundle
# serves all three platforms behind its --platform flag.
STATIC_HOOK_ASSETS_BY_PLATFORM: dict[Platform, list[str]] = {
    Platform.CLAUDE: ["hooks/assets/check.mjs"],
    Platform.CODEX: ["hooks/assets/check.mjs"],
    Platform.MISTRAL_VIBE: ["hooks/assets/check.mjs"],
}

# Files that should be made executable after rendering (hook scripts). A chmod
# only touches files that were produced.
EXECUTABLE_OUTPUTS = {"check-mthds.sh", "check-mthds-codex.sh", "check-mthds-vibe.sh", "launch-pipelex-mcp.sh"}

# Name of the plugin-declared MCP server entry injected into the Claude and
# Codex manifests. Its tools reach the model as
# mcp__plugin_<plugin>_<server>__<tool> on Claude Code
# (mcp__plugin_pipelex_pipelex__mthds_validate) and mcp__<server>__<tool> on
# Codex (mcp__pipelex__mthds_validate).
MCP_SERVER_NAME = "pipelex"

# What the Claude manifest's MCP entry spawns when the target declares plugin
# user configuration: the launcher that promotes the user's options to their
# PIPELEX_* names (make_plugin_json, and scripts/check.py's credential check).
CLAUDE_MCP_LAUNCHER_COMMAND = "${CLAUDE_PLUGIN_ROOT}/hooks/launch-pipelex-mcp.sh"


@dataclass
class TargetConfig:
    """Parsed build target configuration."""

    name: str
    plugin_name: str
    plugin_version: str
    plugin_description: str
    source: str
    template_vars: dict[str, TemplateVarValue]
    include_skills: list[str] | None = None

    @property
    def is_root(self) -> bool:
        """Whether this target writes output to the repo root."""
        return self.source == "./"

    @property
    def platform(self) -> Platform:
        """Target platform: claude, codex, or mistral-vibe."""
        return Platform(str(self.template_vars.get("platform", Platform.CLAUDE)))

    @property
    def has_plugin_manifest(self) -> bool:
        """Whether this platform emits a Claude/Codex plugin manifest."""
        return self.platform in {Platform.CLAUDE, Platform.CODEX}


@dataclass
class BuildResult:
    """Result of rendering templates for a target.

    `files` holds what the build writes, rendered or copied from a static hook asset, with its
    content; `copied` names the per-skill `references/` and `scripts/` files `setup_static_assets`
    copies whole; `pruned` names what a build (never a dry run) removed from the output directory
    because nothing produces it any more.
    """

    files: dict[Path, str] = field(default_factory=lambda: {})
    plugin_json: dict[str, object] | None = None
    copied: set[Path] = field(default_factory=lambda: set[Path]())
    pruned: list[Path] = field(default_factory=lambda: list[Path]())

    @property
    def produced(self) -> set[Path]:
        """Every file the build puts in the target's output directory."""
        return set(self.files) | self.copied


def _coerce_var(value: object) -> TemplateVarValue:
    """Coerce a TOML value to a template variable: bools, lists, and nested
    tables pass through; scalars become strings."""
    if isinstance(value, bool):
        return value
    if isinstance(value, list):
        return [str(item) for item in cast("list[object]", value)]
    if isinstance(value, dict):
        return {str(key): item for key, item in cast("dict[object, object]", value).items()}
    return str(value)


def load_defaults(targets_dir: Path) -> dict[str, TemplateVarValue]:
    """Load default template variables from defaults.toml."""
    defaults_path = targets_dir / DEFAULTS_FILE
    if not defaults_path.is_file():
        msg = f"Defaults file not found: {defaults_path}"
        raise SystemExit(msg)
    raw = tomllib.loads(defaults_path.read_text(encoding="utf-8"))
    defaults: dict[str, TemplateVarValue] = {}
    if "vars" in raw:
        for key, value in raw["vars"].items():
            defaults[key] = _coerce_var(value)
    return defaults


def merge_template_vars(defaults: Mapping[str, TemplateVarValue], overrides: Mapping[str, object]) -> dict[str, TemplateVarValue]:
    """Lay a target's `[vars]` over the defaults: a table merges key by key, recursively; any other value replaces.

    So a target that sets only `[vars.mcp_server] command` and `args`, the dev override, keeps the
    defaults' `env_vars` and `user_config`, and with them the credential wiring the manifests and the
    hook wrappers are rendered from. Replacing the table whole dropped them with every check green.
    A target can give a key the defaults define another value, but cannot remove it. The defaults are
    copied, never shared: no target's variables alias another's.
    """
    merged: dict[str, TemplateVarValue] = copy.deepcopy(dict(defaults))
    for key, value in overrides.items():
        override = _coerce_var(value)
        base = merged.get(key)
        if isinstance(base, dict) and isinstance(override, dict):
            merged[key] = _merge_tables(base, override)
        else:
            merged[key] = override
    return merged


def _merge_tables(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    """One level of `merge_template_vars`: `override`'s keys laid over `base`'s, tables merged in turn."""
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _merge_tables(cast("dict[str, object]", existing), cast("dict[str, object]", value))
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_target_config(targets_dir: Path, target_name: str, defaults: dict[str, TemplateVarValue] | None = None) -> TargetConfig:
    """Load a target config, merging defaults with target-specific overrides.

    Args:
        targets_dir: Path to the targets/ directory.
        target_name: Name of the target (stem of the .toml file).
        defaults: Pre-loaded defaults to avoid re-reading defaults.toml.
            If None, defaults are loaded from disk.
    """
    target_path = targets_dir / f"{target_name}.toml"
    if not target_path.is_file():
        msg = f"Target config not found: {target_path}"
        raise SystemExit(msg)

    if defaults is None:
        defaults = load_defaults(targets_dir)
    raw = tomllib.loads(target_path.read_text(encoding="utf-8"))

    plugin = raw.get("plugin", {})
    if not plugin.get("name"):
        msg = f"{target_path.name}: [plugin].name is required"
        raise SystemExit(msg)

    # Merge template vars: defaults → target overrides (tables merged key by key) → derived values
    template_vars = merge_template_vars(defaults, raw.get("vars", {}))
    template_vars["plugin_name"] = plugin["name"]

    include_skills: list[str] | None = None
    skills_section = raw.get("skills", {})
    if "include" in skills_section:
        include_skills = list(skills_section["include"])

    return TargetConfig(
        name=target_name,
        plugin_name=plugin["name"],
        plugin_version=plugin.get("version", "0.0.0"),
        plugin_description=plugin.get("description", ""),
        source=plugin.get("source", "./"),
        template_vars=template_vars,
        include_skills=include_skills,
    )


def list_targets(targets_dir: Path) -> list[str]:
    """List all target names (excluding defaults.toml)."""
    if not targets_dir.is_dir():
        msg = f"Targets directory not found: {targets_dir}"
        raise SystemExit(msg)
    return sorted(path.stem for path in targets_dir.glob("*.toml") if path.name != DEFAULTS_FILE)


def resolve_output_dir(base_dir: Path, source: str) -> Path:
    """Resolve the output directory for a target."""
    if source == "./":
        return base_dir
    return base_dir / source.rstrip("/")


def _render_or_die(env: Environment, template_name: str, template_vars: Mapping[str, TemplateVarValue]) -> str:
    """Render one template by name, turning Jinja errors into a clean SystemExit."""
    try:
        return env.get_template(template_name).render(**template_vars)
    except TemplateNotFound as exc:
        msg = f"{template_name}: include file not found: {exc.name}"
        raise SystemExit(msg) from exc
    except TemplateSyntaxError as exc:
        msg = f"{template_name}: syntax error at line {exc.lineno}: {exc.message}"
        raise SystemExit(msg) from exc
    except UndefinedError as exc:
        msg = f"{template_name}: undefined variable: {exc.message} — add it to targets/defaults.toml or the target config"
        raise SystemExit(msg) from exc


def render_templates(
    templates_dir: Path,
    base_dir: Path,
    template_vars: Mapping[str, TemplateVarValue],
    include_skills: list[str] | None = None,
    target_name: str | None = None,
) -> dict[Path, str]:
    """Render all .j2 templates and return {output_path: rendered_content}.

    Templates live in templates/ and output goes to the repo root (skills/, hooks/).
    The output path is derived by stripping the templates/ prefix and removing the
    .j2 suffix.

    Args:
        templates_dir: Path to the templates/ directory (Jinja2 FileSystemLoader root).
        base_dir: Repository root — output paths are relative to this.
        template_vars: Variables to inject into all templates.
        include_skills: If set, only render skill templates in these directories.
        target_name: Build target name. When set, a per-skill overlay
            `SKILL.<target_name>.md.j2` (next to a skill's `SKILL.md.j2`) is
            appended to that skill's output — so a target can add content without
            touching the shared template. Targets with no overlay are unaffected.

    Raises:
        SystemExit: On missing include files or template syntax errors.
    """
    if not templates_dir.is_dir():
        msg = f"Templates directory not found: {templates_dir}"
        raise SystemExit(msg)

    # `StrictUndefined`, because the default `Undefined` renders a misspelled key as
    # the empty string without raising: `{{ floors.pipelex_sdk_jss }}` would ship a
    # sentence with a hole where the version floor belongs, past every other gate.
    # Strict mode turns that into a build failure naming the template and the
    # attribute, at the use site — which is the only check that sees EVERY use, and
    # so the only one a second, correctly spelled occurrence cannot hide.
    #
    # It reaches every template, not only the floors, and that is the point: the
    # hazard is the mechanism, not one variable. The consequence for an author is
    # that a variable which may legitimately be absent must SAY so — `{% if x is
    # defined %}`, or `{{ x | default(...) }}` — rather than leaning on an
    # undefined name being falsy or empty. Every template rendered byte-identically
    # when this was turned on, so nothing was migrated; the rule is for what comes
    # next.
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )

    # Collect shared templates (must all exist — fail loudly if missing)
    shared_j2_paths: list[Path] = []
    for name in SHARED_TEMPLATES:
        path = templates_dir / name
        if not path.is_file():
            msg = f"Declared shared template not found: {name}"
            raise SystemExit(msg)
        shared_j2_paths.append(path)

    # Collect hook templates (platform-specific — must all exist)
    platform = Platform(str(template_vars.get("platform", Platform.CLAUDE)))
    hook_template_list = HOOK_TEMPLATES_BY_PLATFORM.get(platform, HOOK_TEMPLATES_BY_PLATFORM[Platform.CLAUDE])
    hook_j2_paths: list[Path] = []
    for name in hook_template_list:
        path = templates_dir / name
        if not path.is_file():
            msg = f"Declared hook template not found: {name}"
            raise SystemExit(msg)
        hook_j2_paths.append(path)

    # Collect MCP templates (platform-specific — must all exist)
    mcp_j2_paths: list[Path] = []
    for name in MCP_TEMPLATES_BY_PLATFORM.get(platform, []):
        path = templates_dir / name
        if not path.is_file():
            msg = f"Declared MCP template not found: {name}"
            raise SystemExit(msg)
        mcp_j2_paths.append(path)

    # Collect skill templates (templates/skills/*/SKILL.md.j2)
    j2_paths = sorted(templates_dir.glob("skills/*/SKILL.md.j2"))
    if include_skills is not None:
        j2_paths = [path for path in j2_paths if path.parent.name in include_skills]

    all_j2_paths = j2_paths + shared_j2_paths + hook_j2_paths + mcp_j2_paths

    # No templates at all (no skills found and no shared/hook templates)
    if not all_j2_paths:
        return {}

    # Collect static hook assets (copied verbatim, no rendering — must all exist)
    static_asset_paths: list[Path] = []
    for name in STATIC_HOOK_ASSETS_BY_PLATFORM.get(platform, []):
        path = templates_dir / name
        if not path.is_file():
            msg = f"Declared static hook asset not found: {name} — re-vendor it (see docs/hooks.md)"
            raise SystemExit(msg)
        static_asset_paths.append(path)

    skill_j2_set = set(j2_paths)
    results: dict[Path, str] = {}
    for j2_path in all_j2_paths:
        template_name = j2_path.relative_to(templates_dir).as_posix()
        rendered = _render_or_die(env, template_name, template_vars)

        # Per-target skill overlay: a `SKILL.<target_name>.md.j2` next to a skill
        # is appended to that skill's output ONLY when building <target_name>. The
        # shared `SKILL.md.j2` is never modified, so every other target stays
        # byte-identical — target-specific content lives in a target-only file.
        if target_name is not None and j2_path in skill_j2_set:
            overlay_path = j2_path.parent / f"SKILL.{target_name}.md.j2"
            if overlay_path.is_file():
                overlay_name = overlay_path.relative_to(templates_dir).as_posix()
                rendered += _render_or_die(env, overlay_name, template_vars)

        # Map template path to output path:
        # templates/skills/X/SKILL.md.j2 -> skills/X/SKILL.md
        # templates/hooks/X.sh.j2 -> hooks/X.sh
        output_rel = j2_path.relative_to(templates_dir).with_suffix("")  # strip .j2
        output_path = base_dir / output_rel
        results[output_path] = rendered

    # Static hook assets: templates/hooks/assets/X -> hooks/X (verbatim copy,
    # the assets/ segment is dropped — the asset ships beside the hook scripts).
    for asset_path in static_asset_paths:
        output_path = base_dir / "hooks" / asset_path.name
        results[output_path] = asset_path.read_text(encoding="utf-8")

    return results


def make_plugin_json(base_dir: Path, config: TargetConfig) -> dict[str, object]:
    """Create a plugin.json dict by overlaying target-specific fields on the base template.

    Uses platform-specific plugin-base.json for shared fields:
    - Claude: .claude-plugin/plugin-base.json
    - Codex: .codex-plugin/plugin-base.json
    """
    if not config.has_plugin_manifest:
        msg = f"{config.name}: platform {config.platform} does not use plugin.json"
        raise SystemExit(msg)
    base_dirname = ".codex-plugin" if config.platform == Platform.CODEX else ".claude-plugin"
    base_plugin_path = base_dir / base_dirname / "plugin-base.json"
    base: dict[str, object] = json.loads(base_plugin_path.read_text(encoding="utf-8"))
    base["name"] = config.plugin_name
    base["description"] = config.plugin_description
    base["version"] = config.plugin_version

    # Claude and Codex manifests declare the pipelex-mcp server inline
    # (mcpServers) so the harness connects it at session start. The declared
    # server is the LOCAL WORKSHOP LAUNCHER (stdio, from the [vars.mcp_server]
    # block) — the hosted console is never baked: a plugin is a shared literal
    # artifact with no channel for a hardcoded per-user key. Credential
    # delivery differs per platform:
    # - Claude: the [vars.mcp_server.user_config] tables become the manifest's
    #   `userConfig` (prompted at enable time; sensitive values go to the OS
    #   keychain) and the entry spawns the launch-pipelex-mcp.sh wrapper with
    #   each option injected as PIPELEX_PLUGIN_<KEY> via `${user_config.*}`
    #   substitution. The wrapper promotes non-empty values to their real
    #   PIPELEX_* names, keeping the session env as fallback — GUI launches
    #   (Claude Desktop) carry no shell env, so userConfig is the only
    #   credential channel there. Without a user_config block the entry
    #   spawns the workshop command directly (full shell env passthrough).
    #   The non-empty guard is load-bearing, not indirection: injecting
    #   ${user_config.*} straight into PIPELEX_* means an unfilled option
    #   substitutes to "" and SHADOWS a working shell credential. The
    #   workshop does treat "" as absent, but an absent key still sends an
    #   unauthenticated request, so the MCP tools surface a config-class
    #   "Unauthorized" and every MCP-backed skill hard-stops. Fail-open is a
    #   property of the hook, never of the tools. Removing this wrapper in
    #   0.3.1 on the opposite assumption regressed the bug 0.3.0 fixed.
    # - Codex: spawns with a minimal whitelist env, so its entry carries
    #   `env_vars` — variable NAMES forwarded from each user's own env,
    #   never values.
    # Dev override: point command/args at a local checkout (e.g.
    # command = "node",
    # args = ["../pipelex-mcp/packages/workshop/dist/main.js"]) in
    # targets/defaults.toml, or in a target's own [vars.mcp_server], which
    # merges into the defaults' table and so keeps env_vars and user_config
    # (merge_template_vars), + `make build` on Claude; a same-named
    # [mcp_servers.pipelex] entry in ~/.codex/config.toml outranks the plugin
    # tier on Codex. Vibe gets no manifest entry because it has no manifest:
    # its target renders the same launcher as the mcp/vibe-mcp.toml config
    # fragment instead (see MCP_TEMPLATES_BY_PLATFORM). Skipped when the
    # target defines no mcp_server block.
    mcp_server = config.template_vars.get("mcp_server")
    if isinstance(mcp_server, dict):
        raw_command = mcp_server.get("command", "")
        command = str(raw_command)
        raw_args = mcp_server.get("args", [])
        launcher_args = [str(item) for item in cast("list[object]", raw_args)] if isinstance(raw_args, list) else []
        raw_env_vars = mcp_server.get("env_vars", [])
        env_var_names = [str(item) for item in cast("list[object]", raw_env_vars)] if isinstance(raw_env_vars, list) else []
        raw_user_config = mcp_server.get("user_config")
        match config.platform:
            case Platform.CLAUDE:
                if isinstance(raw_user_config, dict):
                    user_config = cast("dict[str, object]", raw_user_config)
                    base["userConfig"] = user_config
                    option_env: dict[str, str] = {}
                    for option_key in user_config:
                        option_env[f"PIPELEX_PLUGIN_{option_key.upper()}"] = f"${{user_config.{option_key}}}"
                    base["mcpServers"] = {
                        MCP_SERVER_NAME: {
                            "type": "stdio",
                            "command": CLAUDE_MCP_LAUNCHER_COMMAND,
                            "args": [],
                            "env": option_env,
                        }
                    }
                else:
                    base["mcpServers"] = {
                        MCP_SERVER_NAME: {
                            "type": "stdio",
                            "command": command,
                            "args": launcher_args,
                        }
                    }
            case Platform.CODEX:
                codex_entry: dict[str, object] = {
                    "command": command,
                    "args": launcher_args,
                }
                if env_var_names:
                    codex_entry["env_vars"] = env_var_names
                base["mcpServers"] = {MCP_SERVER_NAME: codex_entry}
            case Platform.MISTRAL_VIBE:
                pass
    return base


def _remove(path: Path) -> None:
    """Delete whatever is at `path`, without following a symlink to its target."""
    # is_symlink() must be checked before is_dir(): a symlink-to-dir is both, and
    # rmtree would chase the link and delete its target.
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _refresh_copy(src: Path, dst: Path) -> None:
    """Replace whatever exists at dst with a fresh copy of src's contents.

    Handles the legacy symlink layout: an existing symlink at dst is unlinked
    before copytree runs. Plain files/dirs are removed too so the build is
    idempotent.
    """
    _remove(dst)
    shutil.copytree(src, dst)


def setup_static_assets(
    base_dir: Path,
    output_dir: Path,
    templates_dir: Path,
    include_skills: list[str] | None,
) -> None:
    """Copy static skill assets (per-skill `references/` and `scripts/`) into the output directory.

    The output dir must be self-contained: marketplace installs that copy a
    single plugin subdir (Codex's local marketplace, Claude's local plugin
    install) cannot follow symlinks pointing to siblings of the plugin root, so
    the assets are copied, not symlinked. `shutil.copytree` copies with
    `copy2`, which keeps a script's executable bit — a skill runs its scripts
    by path, so a copy that lost the bit would fail on every target.
    """
    output_skills_dir = output_dir / "skills"
    output_skills_dir.mkdir(parents=True, exist_ok=True)

    skills_dir = base_dir / "skills"
    for skill_name in _built_skill_names(templates_dir, include_skills):
        skill_output = output_skills_dir / skill_name
        skill_output.mkdir(parents=True, exist_ok=True)
        for asset_dir in STATIC_ASSET_DIRS:
            asset_src = skills_dir / skill_name / asset_dir
            asset_dst = skill_output / asset_dir
            if asset_src.is_dir():
                _refresh_copy(asset_src, asset_dst)
            elif asset_dst.is_dir() or asset_dst.is_symlink():
                # A retired source directory must take its copies with it. Without this the
                # build leaves stale assets shipping in every target and `--check`
                # reports an ORPHAN no rebuild can clear.
                _remove(asset_dst)


def _built_skill_names(templates_dir: Path, include_skills: list[str] | None) -> list[str]:
    """The skills a target builds: its `[skills] include` list, or every skill with a template."""
    if include_skills is not None:
        return include_skills
    return sorted(path.parent.name for path in templates_dir.glob("skills/*/SKILL.md.j2"))


def static_asset_outputs(
    base_dir: Path,
    output_dir: Path,
    templates_dir: Path,
    include_skills: list[str] | None,
) -> set[Path]:
    """Every file `setup_static_assets` copies into a target, at its place in the output directory."""
    outputs: set[Path] = set()
    for skill_name in _built_skill_names(templates_dir, include_skills):
        for asset_dir in STATIC_ASSET_DIRS:
            asset_src = base_dir / "skills" / skill_name / asset_dir
            if not asset_src.is_dir():
                continue
            asset_dst = output_dir / "skills" / skill_name / asset_dir
            outputs.update(asset_dst / path.relative_to(asset_src) for path in asset_src.rglob("*") if path.is_file())
    return outputs


def check_output_dir(base_dir: Path, config: TargetConfig) -> None:
    """Refuse a target whose output directory the build could not prune without deleting what it does not own.

    The build removes every file of a target's output directory that it does not produce, so that
    directory must hold nothing else: it must sit inside the repository, and neither hold nor sit
    inside one of the repository's own directories (`REPOSITORY_OWN_PATHS`) or another target's
    output directory. A target written to the repository root is the one exception, and the build
    prunes nothing there; its output is instead every top-level directory its templates render
    into, one per directory directly under `templates/` (`skills/`, `hooks/`, `mcp/`), so another
    target may neither hold nor sit inside one of those, or its pruning would delete the root
    target's files.
    """
    if config.is_root:
        return
    root = base_dir.resolve()
    output_dir = resolve_output_dir(base_dir, config.source).resolve()
    if not output_dir.is_relative_to(root) or output_dir == root:
        msg = f"{config.name}: [plugin].source {config.source!r} is not a directory inside the repository, so the build cannot own it"
        raise SystemExit(msg)
    others: dict[str, Path] = {f"the repository's {name}/": root / name for name in REPOSITORY_OWN_PATHS}
    templates_dir = base_dir / TEMPLATES_DIR_NAME
    root_output_names = sorted(path.name for path in templates_dir.iterdir() if path.is_dir()) if templates_dir.is_dir() else []
    targets_dir = base_dir / TARGETS_DIR_NAME
    if targets_dir.is_dir():
        for other_name in list_targets(targets_dir):
            if other_name == config.name:
                continue
            other_source = tomllib.loads((targets_dir / f"{other_name}.toml").read_text(encoding="utf-8")).get("plugin", {}).get("source", "./")
            if other_source != "./":
                others[f"the output of target {other_name!r}"] = resolve_output_dir(root, str(other_source)).resolve()
                continue
            # A root target writes each of these at the repository root and prunes none of them.
            for name in root_output_names:
                others[f"the output of target {other_name!r}, which writes {name}/ at the repository root"] = root / name
    for label, other in others.items():
        if output_dir.is_relative_to(other) or other.is_relative_to(output_dir):
            msg = (
                f"{config.name}: [plugin].source {config.source!r} overlaps {label}; the build prunes a target's output "
                "directory down to what it produces, so the two must not share a directory"
            )
            raise SystemExit(msg)


def orphaned_outputs(base_dir: Path, output_dir: Path, produced: set[Path]) -> list[Path]:
    """Every file under a target's output directory that the build does not produce, sorted.

    A symlink counts as a file and is never followed, unless the build writes through it. A file git
    ignores is left out: it never ships, so it is neither the build's to delete nor the check's to
    report — a `.DS_Store` that Finder leaves behind is the usual one.
    """
    if not output_dir.is_dir():
        return []
    produced_dirs = {parent for path in produced for parent in path.parents}
    candidates: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(output_dir):
        current = Path(dirpath)
        candidates.extend(current / name for name in filenames if current / name not in produced)
        # os.walk lists a symlink to a directory among the directories and never descends it.
        candidates.extend(current / name for name in dirnames if (current / name).is_symlink() and current / name not in produced_dirs)
    ignored = _git_ignored(base_dir, candidates)
    return sorted(path for path in candidates if path not in ignored)


def _git_ignored(base_dir: Path, paths: list[Path]) -> set[Path]:
    """The paths among `paths` that git ignores in the work tree holding `base_dir`.

    None outside a work tree or without git, where every file is the build's like any other. Asked
    only about files the build would otherwise report or remove, so a clean target costs no call.
    """
    git = shutil.which("git")
    by_rel: dict[str, Path] = {}
    for path in paths:
        if path.is_relative_to(base_dir):
            by_rel[path.relative_to(base_dir).as_posix()] = path
    if git is None or not by_rel:
        return set()
    completed = subprocess.run(
        [git, "-C", str(base_dir), "check-ignore", "-z", "--stdin"],
        input="".join(f"{rel}\0" for rel in by_rel),
        capture_output=True,
        text=True,
        check=False,
    )
    # 0: some paths are ignored; 1: none is; anything else, 128 outside a work tree among them, says nothing.
    if completed.returncode not in {0, 1}:
        return set()
    return {by_rel[item] for item in completed.stdout.split("\0") if item in by_rel}


def prune_orphans(base_dir: Path, output_dir: Path, produced: set[Path]) -> list[Path]:
    """Remove every orphaned output of a target (see `orphaned_outputs`) and return what went.

    A `.j2` file is left where it is: a template is a source, never an output, and one that
    leaked into a target may be somebody's work written in the wrong place, so `--check` names
    it for its author to move. A directory goes only when removing an orphan left it empty; a
    symlink is unlinked, never followed. The caller has checked the directory is one the build
    owns (`check_output_dir`).
    """
    removed = [path for path in orphaned_outputs(base_dir, output_dir, produced) if not _is_template(path)]
    for path in removed:
        path.unlink()
    for path in removed:
        parent = path.parent
        while parent != output_dir and parent.is_relative_to(output_dir) and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    return removed


def _is_template(path: Path) -> bool:
    """Whether a file is a Jinja template, which belongs under templates/ and never in a target."""
    return path.suffix == ".j2"


def static_asset_mismatches(
    base_dir: Path,
    output_dir: Path,
    templates_dir: Path,
    include_skills: list[str] | None,
) -> list[str]:
    """Compare the copied per-skill `references/` and `scripts/` against their source.

    `setup_static_assets` copies rather than renders, so these files never enter
    a BuildResult and freshness checking used to skip them entirely — a source
    reference edited without `make build` shipped stale while `--check` reported
    everything fresh. The assets are executable know-how, so a stale copy is
    a plugin whose recipes differ from the ones the test suite ran. A script is
    compared by its executable bit as well as its bytes: the skill runs it by
    path, so a copy that lost the bit is as broken as one that lost a line.

    A copy with no source is not this function's to report: it is an orphan like
    any other file of the output directory, and `orphaned_outputs` names it.
    """
    if output_dir == base_dir:
        return []  # root target: source and destination are the same tree

    def label(path: Path) -> str:
        """Repo-relative when it can be, absolute otherwise — a caller may point
        the comparison at a directory outside the repo."""
        try:
            return str(path.relative_to(base_dir))
        except ValueError:
            return str(path)

    problems: list[str] = []
    for skill_name in _built_skill_names(templates_dir, include_skills):
        for asset_dir in STATIC_ASSET_DIRS:
            problems.extend(_asset_dir_mismatches(base_dir, output_dir, skill_name, asset_dir, label))
    return problems


def _asset_dir_mismatches(
    base_dir: Path,
    output_dir: Path,
    skill_name: str,
    asset_dir: str,
    label: Callable[[Path], str],
) -> list[str]:
    """The freshness findings for one skill's copy of one static asset directory: missing, stale or mode-changed copies."""
    asset_src = base_dir / "skills" / skill_name / asset_dir
    asset_dst = output_dir / "skills" / skill_name / asset_dir
    problems: list[str] = []
    if not asset_src.is_dir():
        return problems

    expected: set[Path] = {path.relative_to(asset_src) for path in asset_src.rglob("*") if path.is_file()}
    actual: set[Path] = set()
    if asset_dst.is_dir():
        actual = {path.relative_to(asset_dst) for path in asset_dst.rglob("*") if path.is_file()}

    for rel in sorted(expected - actual):
        problems.append(f"  MISSING: {label(asset_dst / rel)}")
    for rel in sorted(expected & actual):
        # An unreadable file is a finding, not a traceback: check_freshness runs
        # under `make check`, where an OSError escaping here kills the whole gate.
        try:
            differs = (asset_src / rel).read_bytes() != (asset_dst / rel).read_bytes()
            mode_differs = _is_executable(asset_src / rel) != _is_executable(asset_dst / rel)
        except OSError as exc:
            problems.append(f"  UNREADABLE: {label(asset_dst / rel)} ({exc.strerror})")
            continue
        if differs:
            problems.append(f"  STALE: {label(asset_dst / rel)}")
        elif mode_differs:
            problems.append(f"  MODE: {label(asset_dst / rel)} (executable bit differs from its source)")
    return problems


def _is_executable(path: Path) -> bool:
    """Whether the owner may execute the file — the bit a skill's script is run by."""
    return bool(path.stat().st_mode & stat.S_IXUSR)


def build_target(base_dir: Path, config: TargetConfig, *, dry_run: bool = False) -> BuildResult:
    """Build a single target: render templates, set up output directory.

    The build owns a target's output directory: after it, the directory holds what
    the build produces and nothing else, so a file no template or source produces
    any more — a retired template's output, a manifest left by a platform change, a
    stray file — is removed (`prune_orphans`), except a template that leaked there
    and a file git ignores. A target written to the repository root is never pruned.

    Args:
        base_dir: Repository root.
        config: Target configuration.
        dry_run: If True, compute expected files without creating directories
            or writing anything to disk.
    """
    templates_dir = base_dir / TEMPLATES_DIR_NAME
    output_dir = resolve_output_dir(base_dir, config.source)
    is_root = config.is_root
    check_output_dir(base_dir, config)

    result = BuildResult()

    # Render templates — output paths are relative to base_dir
    rendered = render_templates(templates_dir, base_dir, config.template_vars, config.include_skills, target_name=config.name)
    if not rendered:
        return result

    if is_root:
        # Root target: write in place (output paths already point to base_dir/...)
        result.files = rendered
    else:
        # Non-root target: write to output directory
        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)
            setup_static_assets(base_dir, output_dir, templates_dir, config.include_skills)
        result.copied = static_asset_outputs(base_dir, output_dir, templates_dir, config.include_skills)

        for src_path, content in rendered.items():
            # Map base_dir-relative output to target output dir
            # e.g. base_dir/skills/X/SKILL.md -> output_dir/skills/X/SKILL.md
            rel = src_path.relative_to(base_dir)
            dst_path = output_dir / rel
            if not dry_run:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
            result.files[dst_path] = content

        # Generate plugin.json for platforms that have a plugin manifest.
        # Mistral Vibe uses skill_paths plus hooks.toml wiring instead.
        if config.has_plugin_manifest:
            plugin_json = make_plugin_json(base_dir, config)
            result.plugin_json = plugin_json
            manifest_dirname = ".codex-plugin" if config.platform == Platform.CODEX else ".claude-plugin"
            plugin_dir = output_dir / manifest_dirname
            if not dry_run:
                plugin_dir.mkdir(parents=True, exist_ok=True)
            plugin_json_path = plugin_dir / "plugin.json"
            result.files[plugin_json_path] = json.dumps(plugin_json, indent=2) + "\n"

        # Everything else in the output directory goes, the other platform's
        # manifest after a platform change included, so that `--check` never
        # reports an ORPHAN a rebuild cannot clear.
        if not dry_run:
            result.pruned = prune_orphans(base_dir, output_dir, result.produced)

    return result


def render_codex_discovery_marketplace(base_dir: Path) -> str | None:
    """Return the Codex-discoverable marketplace.json text from the canonical source.

    Codex's marketplace loader scans `.agents/plugins/marketplace.json` and
    `.claude-plugin/marketplace.json` for plugin listings. We ship a copy of
    `packaging/codex-marketplace.json` at `.agents/plugins/marketplace.json`
    so `codex plugin marketplace add Pipelex/pipelex-plugins` resolves without
    an install script. The contents are byte-identical — no transformation.

    Returns None when the canonical source is absent — repos without a Codex
    target (e.g. unit-test fixtures) don't need the discovery copy either.
    """
    source_path = base_dir / CODEX_DISCOVERY_MARKETPLACE_SRC
    if not source_path.is_file():
        return None
    return source_path.read_text(encoding="utf-8")


def generate(base_dir: Path, target_name: str = "prod") -> int:
    """Render templates and write output files for one or all targets."""
    targets_dir = base_dir / TARGETS_DIR_NAME

    if target_name == "all":
        target_names = list_targets(targets_dir)
    else:
        target_names = [target_name]

    defaults = load_defaults(targets_dir)

    total_files = 0
    for name in target_names:
        config = load_target_config(targets_dir, name, defaults)
        result = build_target(base_dir, config)

        if not result.files:
            print(f"  [{name}] No templates found.")
            continue

        for output_path, content in result.files.items():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            # Make hook scripts executable
            if output_path.name in EXECUTABLE_OUTPUTS:
                output_path.chmod(0o755)
            rel = output_path.relative_to(base_dir)
            print(f"  [{name}] Generated {rel}")
        for pruned_path in result.pruned:
            print(f"  [{name}] Removed {pruned_path.relative_to(base_dir)} (no template or source produces it any more)")

        file_count = len(result.files)
        total_files += file_count
        print(f"  [{name}] Generated {file_count} files.")

    # Sync the Codex-discoverable marketplace copy whenever any target builds
    # — both files live at the repo root and stay in lockstep. Skip silently
    # in repos without a Codex packaging file (test fixtures, Claude-only forks).
    discovery_content = render_codex_discovery_marketplace(base_dir)
    if discovery_content is not None:
        discovery_dst = base_dir / CODEX_DISCOVERY_MARKETPLACE_DST
        discovery_dst.parent.mkdir(parents=True, exist_ok=True)
        discovery_dst.write_text(discovery_content, encoding="utf-8")
        rel = discovery_dst.relative_to(base_dir)
        print(f"  [codex-discovery] Synced {rel}")

    if total_files == 0:
        print("No templates found.")
        return 1

    return 0


def check_freshness(base_dir: Path, target_name: str = "prod") -> int:
    """Verify that all generated files match their template output."""
    targets_dir = base_dir / TARGETS_DIR_NAME

    if target_name == "all":
        target_names = list_targets(targets_dir)
    else:
        target_names = [target_name]

    defaults = load_defaults(targets_dir)
    all_stale: list[str] = []

    for name in target_names:
        config = load_target_config(targets_dir, name, defaults)
        result = build_target(base_dir, config, dry_run=True)

        if not result.files:
            all_stale.append(f"  [{name}] No templates found.")
            continue

        for output_path, rendered in result.files.items():
            rel = output_path.relative_to(base_dir)
            if not output_path.is_file():
                all_stale.append(f"  MISSING: {rel}")
            elif output_path.read_text(encoding="utf-8") != rendered:
                all_stale.append(f"  STALE: {rel}")
            elif output_path.name in EXECUTABLE_OUTPUTS and not os.access(output_path, os.X_OK):
                all_stale.append(f"  NOT EXECUTABLE: {rel}")

        # The whole file set: whatever the output directory holds that the build does not produce.
        # Each line names the cure that clears it, since `make build` removes an orphan but never
        # a template, and prunes nothing at the repository root.
        output_dir = resolve_output_dir(base_dir, config.source)
        if config.is_root:
            all_stale.extend(_root_target_leftovers(base_dir, result))
        else:
            for orphan in orphaned_outputs(base_dir, output_dir, result.produced):
                rel = orphan.relative_to(base_dir)
                if _is_template(orphan):
                    all_stale.append(f"  LEAKED TEMPLATE: {rel} (a template belongs under templates/: move it there, or delete it)")
                else:
                    all_stale.append(f"  ORPHAN: {rel} (no template or source file produces it: `make build` removes it)")

        # Copied static assets (per-skill references/ and scripts/) are not rendered, so their bytes
        # and executable bits need their own comparison — see static_asset_mismatches.
        all_stale.extend(static_asset_mismatches(base_dir, output_dir, base_dir / TEMPLATES_DIR_NAME, config.include_skills))

    # Cross-target check: when a Codex packaging source exists, its
    # `.agents/plugins/marketplace.json` discovery copy must match byte-for-byte.
    expected_discovery = render_codex_discovery_marketplace(base_dir)
    if expected_discovery is not None:
        discovery_dst = base_dir / CODEX_DISCOVERY_MARKETPLACE_DST
        if not discovery_dst.is_file():
            all_stale.append(f"  MISSING: {CODEX_DISCOVERY_MARKETPLACE_DST}")
        elif discovery_dst.read_text(encoding="utf-8") != expected_discovery:
            all_stale.append(f"  STALE: {CODEX_DISCOVERY_MARKETPLACE_DST} (does not match {CODEX_DISCOVERY_MARKETPLACE_SRC})")

    if all_stale:
        for msg in all_stale:
            print(msg)
        print("FAIL: Generated files are out of date. Run `make build` to regenerate them, and apply any other cure a line above names.")
        return 1

    target_label = target_name if target_name != "all" else ", ".join(target_names)
    print(f"  All generated files are fresh (targets: {target_label}).")
    return 0


def _root_target_leftovers(base_dir: Path, result: BuildResult) -> list[str]:
    """What a target written to the repository root no longer produces, with the cure that works there.

    The root holds every source of the repository beside the build's output, so the build prunes
    nothing there and cannot compare the whole file set: only a skill whose template is gone, and
    a template outside `templates/`, are recognisable as leftovers, and each is the author's to delete.
    """
    findings: list[str] = []
    rendered_skill_parents = {path.parent for path in result.files if path.name == "SKILL.md"}
    for skill_md in sorted((base_dir / "skills").glob("*/SKILL.md")):
        if skill_md.parent not in rendered_skill_parents:
            rel = skill_md.relative_to(base_dir)
            findings.append(f"  ORPHAN: {rel} (no template produces it: delete it, since the build prunes nothing at the repository root)")
    for dirname in ("skills", "hooks", "mcp"):
        for j2_file in sorted((base_dir / dirname).rglob("*.j2")):
            rel = j2_file.relative_to(base_dir)
            findings.append(f"  LEAKED TEMPLATE: {rel} (a template belongs under templates/: move it there, or delete it)")
    return findings


def main() -> int:
    base_dir = Path(__file__).resolve().parent.parent

    # Parse arguments
    args = sys.argv[1:]
    target_name = "prod"
    check_mode = False

    idx = 0
    while idx < len(args):
        if args[idx] == "--target" and idx + 1 < len(args):
            target_name = args[idx + 1]
            idx += 2
        elif args[idx] == "--check":
            check_mode = True
            idx += 1
        else:
            msg = f"Unknown argument: {args[idx]}"
            raise SystemExit(msg)

    if check_mode:
        return check_freshness(base_dir, target_name)
    return generate(base_dir, target_name)


if __name__ == "__main__":
    sys.exit(main())
