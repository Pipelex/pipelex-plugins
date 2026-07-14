#!/usr/bin/env python3
"""Generate skill docs, shared files, and hooks from Jinja2 templates.

Renders all .j2 templates under templates/ and writes the corresponding
output files (skills/, hooks/). Templates (.j2) are the source of truth;
output files are build artifacts checked into git.

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

import json
import os
import shutil
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError, UndefinedError


class Platform(StrEnum):
    CLAUDE = "claude"
    CODEX = "codex"
    MISTRAL_VIBE = "mistral-vibe"


TARGETS_DIR_NAME = "targets"
DEFAULTS_FILE = "defaults.toml"
TEMPLATES_DIR_NAME = "templates"

# Codex discovers plugin marketplaces at `.agents/plugins/marketplace.json`
# (preferred) or `.claude-plugin/marketplace.json` (fallback). We ship a
# Codex-discoverable copy of `packaging/codex-marketplace.json` at the repo
# root so `codex plugin marketplace add Pipelex/pipelex-plugins` works without
# an install script. The canonical file remains the single source of truth;
# this is a verbatim copy.
CODEX_DISCOVERY_MARKETPLACE_SRC = Path("packaging/codex-marketplace.json")
CODEX_DISCOVERY_MARKETPLACE_DST = Path(".agents/plugins/marketplace.json")

# Shared reference files, rendered standalone per target. These are the MTHDS
# language references that ground the skills. Paths are relative to the
# templates/ directory.
#
# `skills/shared/frontmatter.md.j2` is deliberately NOT listed here: it is an
# include-only partial ({% include %}-d by skill templates for their YAML
# frontmatter), so it must exist as a file but should not be rendered standalone
# (that would only ship a near-empty artifact).
SHARED_TEMPLATES = [
    "skills/shared/mthds-reference.md.j2",
    "skills/shared/native-content-types.md.j2",
]

# Hook templates rendered for the Claude target: the PostToolUse wiring plus the
# bundled `.mthds`-on-edit validation script. The CLI-free posture ports the
# validation pipeline but flips missing-CLI behavior from block-with-install-hint
# to silent pass — the hook no-ops when `plxt`/`mthds-agent`/`node` are absent
# instead of blocking every edit. The predecessor's session-start doctor hook is
# left behind (CLI-lifecycle territory).
HOOK_TEMPLATES = [
    "hooks/hooks.json.j2",
    "hooks/validate-mthds.sh.j2",
]

# Hook templates by platform:
# - Claude: hooks/hooks.json + the validate-mthds.sh wrapper.
# - Codex: hooks/codex-hooks.json (the plugin-bundled PostToolUse config,
#   referenced from the Codex manifest's `hooks` field; ${PLUGIN_ROOT} is
#   substituted by Codex's hook engine) + the validate-mthds-codex.sh wrapper.
# - Mistral Vibe: hooks/vibe-hooks.toml + the validate-mthds-vibe.sh wrapper.
# Each wrapper is a thin fail-open guard around the shared check.mjs bundle,
# invoked with the matching --platform flag.
HOOK_TEMPLATES_BY_PLATFORM: dict[Platform, list[str]] = {
    Platform.CLAUDE: HOOK_TEMPLATES,
    Platform.CODEX: ["hooks/codex-hooks.json.j2", "hooks/validate-mthds-codex.sh.j2"],
    Platform.MISTRAL_VIBE: ["hooks/vibe-hooks.toml.j2", "hooks/validate-mthds-vibe.sh.j2"],
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
EXECUTABLE_OUTPUTS = {"validate-mthds.sh", "validate-mthds-codex.sh", "validate-mthds-vibe.sh"}

# Name of the plugin-declared MCP server entry injected into the Claude
# manifest. Its tools reach the model as mcp__plugin_<plugin>_<server>__<tool>
# (e.g. mcp__plugin_pipelex_pipelex__mthds_validate).
MCP_SERVER_NAME = "pipelex"

# Env var that overrides the baked MCP server URL at session start. Claude Code
# expands ${VAR:-default} inside plugin MCP configs, which keeps the dev/prod
# switch rebuild-free.
MCP_URL_ENV_VAR = "PIPELEX_MCP_URL"


@dataclass
class TargetConfig:
    """Parsed build target configuration."""

    name: str
    plugin_name: str
    plugin_version: str
    plugin_description: str
    source: str
    template_vars: dict[str, str | bool]
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
    """Result of rendering templates for a target."""

    files: dict[Path, str] = field(default_factory=lambda: {})
    plugin_json: dict[str, object] | None = None


def load_defaults(targets_dir: Path) -> dict[str, str | bool]:
    """Load default template variables from defaults.toml."""
    defaults_path = targets_dir / DEFAULTS_FILE
    if not defaults_path.is_file():
        msg = f"Defaults file not found: {defaults_path}"
        raise SystemExit(msg)
    raw = tomllib.loads(defaults_path.read_text(encoding="utf-8"))
    defaults: dict[str, str | bool] = {}
    if "vars" in raw:
        for key, value in raw["vars"].items():
            defaults[key] = value if isinstance(value, bool) else str(value)
    return defaults


def load_target_config(targets_dir: Path, target_name: str, defaults: dict[str, str | bool] | None = None) -> TargetConfig:
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

    # Merge template vars: defaults → target overrides → derived values
    template_vars = dict(defaults)
    if "vars" in raw:
        for key, value in raw["vars"].items():
            template_vars[key] = value if isinstance(value, bool) else str(value)
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


def _render_or_die(env: Environment, template_name: str, template_vars: Mapping[str, str | bool]) -> str:
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
    template_vars: Mapping[str, str | bool],
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

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        keep_trailing_newline=True,
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

    # Collect skill templates (templates/skills/*/SKILL.md.j2)
    j2_paths = sorted(templates_dir.glob("skills/*/SKILL.md.j2"))
    if include_skills is not None:
        j2_paths = [path for path in j2_paths if path.parent.name in include_skills]

    all_j2_paths = j2_paths + shared_j2_paths + hook_j2_paths

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

    # Claude manifests declare the pipelex-mcp server inline (mcpServers) so the
    # harness connects it at session start. Codex/Vibe get no entry: plugin-bundled
    # MCP support is unverified there — their registration is a documented manual
    # step (see README). Skipped when the target defines no mcp_server_url.
    if config.platform == Platform.CLAUDE:
        mcp_server_url = str(config.template_vars.get("mcp_server_url", "") or "")
        if mcp_server_url:
            base["mcpServers"] = {
                MCP_SERVER_NAME: {
                    "type": "http",
                    "url": f"${{{MCP_URL_ENV_VAR}:-{mcp_server_url}}}",
                }
            }
    return base


def _refresh_copy(src: Path, dst: Path) -> None:
    """Replace whatever exists at dst with a fresh copy of src's contents.

    Handles the legacy symlink layout: an existing symlink at dst is unlinked
    before copytree runs. Plain files/dirs are removed too so the build is
    idempotent.
    """
    # is_symlink() must be checked before is_dir(): a symlink-to-dir is both,
    # and rmtree would chase the link and delete its target.
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.is_dir():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def setup_static_assets(
    base_dir: Path,
    output_dir: Path,
    templates_dir: Path,
    include_skills: list[str] | None,
) -> None:
    """Copy static skill assets (per-skill references/) into the output directory.

    The output dir must be self-contained: marketplace installs that copy a
    single plugin subdir (Codex's local marketplace, Claude's local plugin
    install) cannot follow symlinks pointing to siblings of the plugin root, so
    references are copied, not symlinked.
    """
    if include_skills is not None:
        skill_names = include_skills
    else:
        skill_names = sorted(path.parent.name for path in templates_dir.glob("skills/*/SKILL.md.j2"))

    output_skills_dir = output_dir / "skills"
    output_skills_dir.mkdir(parents=True, exist_ok=True)

    skills_dir = base_dir / "skills"
    for skill_name in skill_names:
        skill_output = output_skills_dir / skill_name
        skill_output.mkdir(parents=True, exist_ok=True)
        refs_src = skills_dir / skill_name / "references"
        refs_dst = skill_output / "references"
        if refs_src.is_dir():
            _refresh_copy(refs_src, refs_dst)


def build_target(base_dir: Path, config: TargetConfig, *, dry_run: bool = False) -> BuildResult:
    """Build a single target: render templates, set up output directory.

    Args:
        base_dir: Repository root.
        config: Target configuration.
        dry_run: If True, compute expected files without creating directories
            or writing anything to disk.
    """
    templates_dir = base_dir / TEMPLATES_DIR_NAME
    output_dir = resolve_output_dir(base_dir, config.source)
    is_root = config.is_root

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
        elif not dry_run:
            # Keep rebuilds idempotent if a target changed platform or stale
            # manifest dirs were left by an older generator.
            for manifest_dirname in (".claude-plugin", ".codex-plugin"):
                stale_dir = output_dir / manifest_dirname
                if stale_dir.is_dir():
                    shutil.rmtree(stale_dir)
                elif stale_dir.is_symlink() or stale_dir.is_file():
                    stale_dir.unlink()

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

        # Detect orphaned SKILL.md files with no corresponding template
        output_dir = resolve_output_dir(base_dir, config.source)
        output_skills_dir = output_dir / "skills"
        rendered_skill_parents = {path.parent for path in result.files if path.name == "SKILL.md"}
        if output_skills_dir.is_dir():
            for skill_md in sorted(output_skills_dir.glob("*/SKILL.md")):
                if skill_md.parent not in rendered_skill_parents:
                    rel = skill_md.relative_to(base_dir)
                    all_stale.append(f"  ORPHAN: {rel} (no corresponding .j2 template)")

        # Detect leaked .j2 files in output directories (should only be in templates/)
        if output_skills_dir.is_dir():
            for j2_file in sorted(output_skills_dir.rglob("*.j2")):
                rel = j2_file.relative_to(base_dir)
                all_stale.append(f"  LEAKED TEMPLATE: {rel} (should be in templates/)")
        output_hooks_dir = output_dir / "hooks"
        if output_hooks_dir.is_dir():
            for j2_file in sorted(output_hooks_dir.rglob("*.j2")):
                rel = j2_file.relative_to(base_dir)
                all_stale.append(f"  LEAKED TEMPLATE: {rel} (should be in templates/)")

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
        print("FAIL: Generated files are out of date. Run `make build` to regenerate.")
        return 1

    target_label = target_name if target_name != "all" else ", ".join(target_names)
    print(f"  All generated files are fresh (targets: {target_label}).")
    return 0


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
