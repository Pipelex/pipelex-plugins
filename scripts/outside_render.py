#!/usr/bin/env python3
"""Render this plugin's skills for an outside target: a target file and templates kept in another repository.

An outside target is one TOML file in the consumer's repository. The directory holding it is the
target's **source root**, laid out like this repository: its own templates under
`templates/skills/…`, its own static assets under `skills/<skill>/references/` and
`skills/<skill>/scripts/`. The render reads this repository's templates, static assets and
defaults (the upstream), then the outside templates and static assets git does not ignore, and
writes one directory, the target's output, which it owns: one subdirectory per skill, the shared
files either beside them or copied into each skill, and the marker that says whose output it is.

The outside target may add anything. It may also replace any upstream template or static asset,
and drop any upstream static asset, but only what it declares, each declaration pinning the
upstream file by the SHA-256 of its bytes; and it may pin an upstream file it uses as it is. So an
upstream change to a file the consumer replaced, dropped or depends on stops the render until
somebody has read it and updated the hash. The rules, and why, are in docs/build-targets.md,
"Outside targets", and docs/decisions.md.

It renders for the `agent-skills` platform only, and writes no hooks, no manifest, no MCP
declaration and no marketplace file.

Usage, from the installed package (docs/development.md, "Rendering for an outside target"):
    pipelex-plugins-render <target file>           # render into the target's output
    pipelex-plugins-render <target file> --check   # compare the output, write nothing

and from a checkout, `python -m scripts.outside_render` with the same arguments.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import sys
import tempfile
import tomllib
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from scripts.gen_skill_docs import (
    GIT_DIR_NAME,
    STATIC_ASSET_DIRS,
    TARGETS_DIR_NAME,
    TEMPLATES_DIR_NAME,
    Platform,
    TemplateVarValue,
    git_ignored,
    list_targets,
    load_defaults,
    merge_template_vars,
    orphaned_outputs,
    remove_orphans,
    render_templates,
    skill_template_names,
)
from scripts.skill_links import SHARED_DIR_NAME, linked_paths, skill_link_errors

# The upstream: the templates, static assets and targets the render reads. The installed package
# carries them inside itself (pyproject's `[tool.hatch.build.targets.wheel]`); in a checkout they
# sit beside this package, at the repository's root.
PACKAGE_DIR = Path(__file__).resolve().parent
UPSTREAM_ROOT = PACKAGE_DIR if (PACKAGE_DIR / TEMPLATES_DIR_NAME).is_dir() else PACKAGE_DIR.parent

# The directory of upstream and outside static assets, one subdirectory per skill.
SKILLS_DIR_NAME = "skills"
# Where an installer writes the bytecode it compiles for a Python file, beside the wheel's own files.
INSTALLER_BYTECODE_DIR = "__pycache__"

# The keys an outside target file may hold. Anything else is refused, since a misspelled table
# (`[render.replace]`) would otherwise be ignored and its declarations with it.
TOP_LEVEL_KEYS = frozenset({"render", "skills", "vars"})
DECLARATION_TABLES = ("replaces", "drops", "pins")
RENDER_KEYS = frozenset({"output", "shared", *DECLARATION_TABLES})
SKILLS_KEYS = frozenset({"include"})

# The variables the render sets itself, which a target's `[vars]` may therefore not set.
DERIVED_VARS = ("plugin_name", "shared_dir")
# The variables whose defaults are Claude Code's, which an outside target must set itself.
REQUIRED_VARS = ("platform", "harness_name", "skill_dir")

# The upstream files a declaration may name: a template a skill renders or includes, or a skill's static asset.
DECLARABLE_PREFIXES = (f"{TEMPLATES_DIR_NAME}/{SKILLS_DIR_NAME}/", f"{SKILLS_DIR_NAME}/")
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

# The file each render writes at the top of its output, naming the target whose output it is. The
# render prunes its output to what it produces, so it writes only into a directory that is new or
# empty, or that carries this marker for the same target: anything else is somebody else's.
OWNER_MARKER_NAME = ".pipelex-plugins-render.toml"


class SharedLayout(StrEnum):
    """Where the shared files go: once beside the skills, as the plugin ships them, or into each skill that links one."""

    BESIDE = "beside"
    IN_EACH_SKILL = "in-each-skill"

    @property
    def shared_dir(self) -> str:
        """The `shared_dir` template variable: where a SKILL.md's links find the shared files."""
        match self:
            case SharedLayout.BESIDE:
                return f"../{SHARED_DIR_NAME}"
            case SharedLayout.IN_EACH_SKILL:
                return SHARED_DIR_NAME


@dataclass(frozen=True)
class OutsideTarget:
    """A parsed outside target file. Declaration keys are paths in this repository (`templates/…`, `skills/…`)."""

    name: str
    path: Path
    source_root: Path
    output_dir: Path
    shared_layout: SharedLayout
    replaces: dict[str, str]
    drops: dict[str, str]
    pins: dict[str, str]
    include_skills: list[str] | None
    template_vars: dict[str, TemplateVarValue]

    def declarations(self) -> dict[str, dict[str, str]]:
        """The declaration tables, by name."""
        return {"replaces": self.replaces, "drops": self.drops, "pins": self.pins}


@dataclass(frozen=True)
class OutputFile:
    """One file the render produces: its bytes, and whether it is executable (a skill's script)."""

    content: bytes
    executable: bool = False


def file_sha256(path: Path) -> str:
    """A declaration's hash of a file: `sha256:` and the hex digest of its bytes."""
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _refuse(target_file: Path, message: str) -> SystemExit:
    return SystemExit(f"{target_file.name}: {message}")


def _string_table(target_file: Path, raw: object, where: str) -> dict[str, str]:
    """A TOML table of strings, refused when it is anything else."""
    if not isinstance(raw, dict):
        raise _refuse(target_file, f"{where} must be a table")
    table: dict[str, str] = {}
    for key, value in cast("dict[object, object]", raw).items():
        if not isinstance(value, str):
            raise _refuse(target_file, f"{where} {key!r} must be a string")
        table[str(key)] = value
    return table


def _check_declared_path(target_file: Path, table: str, key: str) -> None:
    """A declaration names an upstream file by its POSIX path in this repository, under `templates/skills/` or `skills/`."""
    if "\\" in key or any(part in {"", ".", ".."} for part in key.split("/")):
        raise _refuse(target_file, f"[render.{table}] {key!r} is not a relative POSIX path in this repository")
    if not key.startswith(DECLARABLE_PREFIXES):
        message = f"[render.{table}] {key!r} names no skill template or static asset: a declaration starts with templates/skills/ or skills/"
        raise _refuse(target_file, message)


def load_outside_target(target_file: Path, upstream_root: Path = UPSTREAM_ROOT) -> OutsideTarget:
    """Read and validate an outside target file, laying its `[vars]` over the upstream defaults.

    Refused, each naming its cure: a file that is not TOML; a key the format does not have; a name
    an in-repo target already has, whose overlays it would pick up; a missing `output`, or one that
    holds or sits inside the source root or the upstream; a `shared` layout the render does not
    know; a malformed declaration, or one path in two tables; a target not on `agent-skills`, or one
    leaving `harness_name` or `skill_dir` to the defaults, which are Claude Code's; a variable the
    render derives itself; and an `include` naming a skill that exists neither upstream nor under
    the source root.
    """
    path = target_file.resolve()
    if not path.is_file():
        msg = f"Outside target file not found: {target_file}"
        raise SystemExit(msg)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise _refuse(path, f"not valid TOML: {exc}") from exc

    unknown = sorted(set(raw) - TOP_LEVEL_KEYS)
    if unknown:
        raise _refuse(path, f"unknown key(s) {', '.join(unknown)}: an outside target holds [render], [skills] and [vars]")
    render = _table(path, raw.get("render", {}), "[render]")
    unknown = sorted(set(render) - RENDER_KEYS)
    if unknown:
        raise _refuse(path, f"unknown [render] key(s) {', '.join(unknown)}: it holds output, shared, and the replaces, drops and pins tables")
    skills = _table(path, raw.get("skills", {}), "[skills]")
    unknown = sorted(set(skills) - SKILLS_KEYS)
    if unknown:
        raise _refuse(path, f"unknown [skills] key(s) {', '.join(unknown)}: it holds include")

    name = path.stem
    targets_dir = upstream_root / TARGETS_DIR_NAME
    if name in list_targets(targets_dir):
        raise _refuse(path, f"its name {name!r} is an in-repo target's, whose overlays it would pick up: rename the file")

    source_root = path.parent
    output = render.get("output")
    if not isinstance(output, str) or not output:
        raise _refuse(path, "[render] output is required: the directory the render owns, relative to this file")
    output_dir = (source_root / output).resolve()
    if output_dir.is_relative_to(source_root) or source_root.is_relative_to(output_dir):
        raise _refuse(path, f"[render] output {output!r} holds or sits inside the source root, whose templates the render would prune")
    upstream = upstream_root.resolve()
    if output_dir.is_relative_to(upstream) or upstream.is_relative_to(output_dir):
        raise _refuse(path, f"[render] output {output!r} overlaps pipelex-plugins itself, which the render never writes into")

    raw_layout = render.get("shared", SharedLayout.BESIDE.value)
    try:
        shared_layout = SharedLayout(str(raw_layout))
    except ValueError as exc:
        layouts = ", ".join(repr(layout.value) for layout in SharedLayout)
        raise _refuse(path, f"[render] shared {raw_layout!r} is not a layout: it is one of {layouts}") from exc

    declarations: dict[str, dict[str, str]] = {}
    seen: dict[str, str] = {}
    for table in DECLARATION_TABLES:
        entries = _string_table(path, render.get(table, {}), f"[render.{table}]")
        for key, value in entries.items():
            _check_declared_path(path, table, key)
            if not HASH_PATTERN.match(value):
                raise _refuse(path, f"[render.{table}] {key!r} = {value!r} is not a hash: write sha256: and the 64 hex digits of the upstream file")
            if key in seen:
                raise _refuse(path, f"{key!r} is declared in both [render.{seen[key]}] and [render.{table}]: a file is replaced, dropped or pinned")
            seen[key] = table
        declarations[table] = entries

    overrides = _table(path, raw.get("vars", {}), "[vars]")
    for derived in DERIVED_VARS:
        if derived in overrides:
            raise _refuse(path, f"[vars] {derived} is set by the render itself (the file's name, and the [render] shared layout)")
    missing = [key for key in REQUIRED_VARS if key not in overrides]
    if missing:
        message = f"[vars] must set {', '.join(missing)}: the defaults are Claude Code's, and an outside target renders for another harness"
        raise _refuse(path, message)
    template_vars = merge_template_vars(load_defaults(targets_dir), overrides)
    platform_value = str(template_vars["platform"])
    if platform_value not in {platform.value for platform in Platform if platform.is_outside_only}:
        raise _refuse(path, f"[vars] platform is {platform_value!r}: an outside target renders for {Platform.AGENT_SKILLS.value!r}")
    template_vars["plugin_name"] = name
    template_vars["shared_dir"] = shared_layout.shared_dir

    include_skills: list[str] | None = None
    if "include" in skills:
        raw_include: object = skills["include"]
        if not isinstance(raw_include, list) or not all(isinstance(item, str) for item in cast("list[object]", raw_include)):
            raise _refuse(path, "[skills] include must be a list of skill names")
        include_skills = [str(item) for item in cast("list[object]", raw_include)]

    target = OutsideTarget(
        name=name,
        path=path,
        source_root=source_root,
        output_dir=output_dir,
        shared_layout=shared_layout,
        replaces=declarations["replaces"],
        drops=declarations["drops"],
        pins=declarations["pins"],
        include_skills=include_skills,
        template_vars=template_vars,
    )
    known = set(_skill_names(upstream_root, _source_files(source_root, (TEMPLATES_DIR_NAME,))))
    if SHARED_DIR_NAME in known:
        raise _refuse(path, f"a skill may not be named {SHARED_DIR_NAME!r}, the directory the shared files go in")
    for skill in include_skills or []:
        if skill not in known:
            raise _refuse(path, f"[skills] include names {skill!r}, a skill that exists neither upstream nor under {TEMPLATES_DIR_NAME}/skills/ here")
    return target


def _table(target_file: Path, raw: object, where: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise _refuse(target_file, f"{where} must be a table")
    return {str(key): value for key, value in cast("dict[object, object]", raw).items()}


def _source_files(root: Path, subdirs: Sequence[str]) -> list[str]:
    """Every file under `root`'s `subdirs`, as POSIX paths relative to `root`, leaving out what git ignores there.

    This is the whole of what the render reads from a source root, templates included: a file git
    ignores is neither checked against the declarations nor rendered, so it can change nothing.
    """
    files = sorted(path for subdir in subdirs if (root / subdir).is_dir() for path in (root / subdir).rglob("*") if path.is_file())
    ignored = git_ignored(root, files)
    return [path.relative_to(root).as_posix() for path in files if path not in ignored]


def _upstream_files(upstream_root: Path, subdirs: Sequence[str]) -> list[str]:
    """The upstream's files under `subdirs`, as `_source_files` lists them when the upstream is a checkout.

    Git is asked only about a checkout, whose root holds `.git`. The installed package holds what
    its wheel was built with, which leaves out what `.gitignore` ignored then, and asking git about it would
    be asking whatever repository the environment happens to sit in: one inside a `.venv` its
    repository ignores would have every upstream file reported ignored, and none rendered. What the
    installer added beside the wheel's files is left out instead: the bytecode it compiles for a
    Python file a skill ships, as pip does by default, which git ignores in a checkout.
    """
    if (upstream_root / GIT_DIR_NAME).exists():
        return _source_files(upstream_root, subdirs)
    return sorted(
        path.relative_to(upstream_root).as_posix()
        for subdir in subdirs
        if (upstream_root / subdir).is_dir()
        for path in (upstream_root / subdir).rglob("*")
        if path.is_file() and INSTALLER_BYTECODE_DIR not in path.relative_to(upstream_root).parts
    )


def _skill_names(upstream_root: Path, outside_files: Sequence[str]) -> list[str]:
    """Every skill there is to render: the upstream ones, and those the outside files hold a `SKILL.md.j2` for."""
    outside = {
        parts[2]
        for parts in (rel.split("/") for rel in outside_files)
        if len(parts) == 4 and parts[:2] == [TEMPLATES_DIR_NAME, SKILLS_DIR_NAME] and parts[3] == "SKILL.md.j2"
    }
    return sorted(set(skill_template_names([upstream_root / TEMPLATES_DIR_NAME])) | outside)


@contextmanager
def _outside_templates(source_root: Path, outside_files: Sequence[str]) -> Generator[Path | None]:
    """The outside templates the render reads, copied into a scratch `templates/` directory; None when there are none.

    The template loader searches whole directories, so it is pointed at this copy of the files
    `_source_files` lists rather than at the source root, where it would also find what git ignores,
    which the declaration check never sees.
    """
    templates = [rel for rel in outside_files if rel.startswith(f"{TEMPLATES_DIR_NAME}/")]
    if not templates:
        yield None
        return
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        for rel in templates:
            destination = root / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_root / rel, destination)
        yield root / TEMPLATES_DIR_NAME


def _is_static_asset(rel: str) -> bool:
    """Whether a path under `skills/` is a skill's static asset, `skills/<skill>/references|scripts/…`."""
    parts = rel.split("/")
    return len(parts) >= 4 and parts[0] == SKILLS_DIR_NAME and parts[2] in STATIC_ASSET_DIRS


def declaration_errors(target: OutsideTarget, upstream_root: Path = UPSTREAM_ROOT) -> list[str]:
    """What the target changes upstream without saying so, or says it changes and no longer can.

    An outside file at an upstream path must be declared in `[render.replaces]`, and a declared
    replacement must have its file under the source root. Every declaration must name an upstream
    file, whose bytes must still hash to the declared value. A drop names a static asset and is
    not provided, and a pin is not replaced. An outside file the render would never read — under
    `templates/` but not a skill template, or under `skills/` but not a skill's `references/` or
    `scripts/` — is refused too, since it can only be a file in the wrong place.
    """
    errors: list[str] = []
    outside = _source_files(target.source_root, (TEMPLATES_DIR_NAME, SKILLS_DIR_NAME))
    outside_set = set(outside)
    for rel in outside:
        if rel.startswith(f"{TEMPLATES_DIR_NAME}/"):
            if not rel.startswith(DECLARABLE_PREFIXES[0]) or not rel.endswith(".j2"):
                errors.append(f"{rel}: the render reads only templates under {DECLARABLE_PREFIXES[0]} ending .j2; move it there, or delete it")
                continue
        elif not _is_static_asset(rel):
            errors.append(f"{rel}: the render copies only a skill's references/ and scripts/ from {SKILLS_DIR_NAME}/; move it there, or delete it")
            continue
        upstream_file = upstream_root / rel
        if upstream_file.is_file() and not any(rel in entries for entries in target.declarations().values()):
            errors.append(
                f"{rel}: replaces the upstream file at the same path without saying so; declare it in [render.replaces] "
                f'as "{rel}" = "{file_sha256(upstream_file)}" once you have read the upstream file'
            )
    for table, entries in target.declarations().items():
        for rel, declared in sorted(entries.items()):
            upstream_file = upstream_root / rel
            if not upstream_file.is_file():
                errors.append(f"[render.{table}] {rel}: names no upstream file; it was renamed or removed upstream, so find where its content went")
                continue
            actual = file_sha256(upstream_file)
            if actual != declared:
                errors.append(
                    f"[render.{table}] {rel}: the upstream file changed: declared {declared}, now {actual}. Read the change "
                    f"(`git diff <old-ref>..<new-ref> -- {rel}` in pipelex-plugins), carry it over or decide against it, then update the hash"
                )
            match table:
                case "replaces":
                    if rel not in outside_set:
                        errors.append(
                            f"[render.replaces] {rel}: no file at that path under the source root, or one git ignores; a file left out is a drop"
                        )
                case "drops":
                    if not _is_static_asset(rel):
                        errors.append(f"[render.drops] {rel}: only a static asset is dropped; replace a template, or leave its skill out")
                    elif rel in outside_set:
                        errors.append(f"[render.drops] {rel}: dropped, yet the source root holds a file at that path; replace it instead")
                case "pins":
                    if rel in outside_set:
                        errors.append(f"[render.pins] {rel}: pinned as used as it is, yet the source root holds a file there; replace it instead")
                case _:
                    pass
    return errors


def _rendered_skill_names(target: OutsideTarget, upstream_root: Path, outside_files: Sequence[str]) -> list[str]:
    names = _skill_names(upstream_root, outside_files)
    if target.include_skills is None:
        return names
    return [name for name in names if name in target.include_skills]


def _static_assets(target: OutsideTarget, sources: Sequence[tuple[Path, Sequence[str]]], skill: str) -> dict[str, OutputFile]:
    """A skill's static assets, by their path in the output: the upstream ones less the drops, then the outside ones over them.

    `sources` is each root with the files `_source_files` lists under it, the upstream first.
    """
    assets: dict[str, OutputFile] = {}
    prefixes = tuple(f"{SKILLS_DIR_NAME}/{skill}/{name}/" for name in STATIC_ASSET_DIRS)
    for root, files in sources:
        for rel in files:
            if not rel.startswith(prefixes) or rel in target.drops:
                continue
            source = root / rel
            executable = bool(source.stat().st_mode & stat.S_IXUSR)
            assets[rel.removeprefix(f"{SKILLS_DIR_NAME}/")] = OutputFile(source.read_bytes(), executable)  # <skill>/references/…
    return assets


def _shared_closure(files: Mapping[str, OutputFile], shared_prefix: str, shared: Mapping[str, str]) -> dict[str, OutputFile]:
    """The shared files that `files` link to under `shared_prefix`, followed through the shared files' own links."""
    closure: dict[str, OutputFile] = {}
    pending = [(rel, file.content.decode("utf-8")) for rel, file in files.items() if rel.endswith(".md")]
    while pending:
        rel, text = pending.pop()
        for linked in linked_paths(text, rel):
            directory, _, filename = linked.rpartition("/")
            if directory == shared_prefix and filename in shared and linked not in closure:
                closure[linked] = OutputFile(shared[filename].encode("utf-8"))
                pending.append((linked, shared[filename]))
    return closure


def render_outside(target: OutsideTarget, upstream_root: Path = UPSTREAM_ROOT) -> dict[str, OutputFile]:
    """Everything the outside target's output holds, by its POSIX path in the output directory, rendered in memory.

    Each skill is `<skill>/SKILL.md` with its static assets beside it. The shared files the skills
    link to, followed through their own links, go once in `shared/` (`beside`) or into each skill
    that links one (`in-each-skill`), and a shared file nothing links is left out. The owner marker
    goes at the top. Only what `_source_files` lists is read from the source root. The caller has
    checked the declarations (`declaration_errors`).
    """
    outside_files = _source_files(target.source_root, (TEMPLATES_DIR_NAME, SKILLS_DIR_NAME))
    upstream_assets = _upstream_files(upstream_root, (SKILLS_DIR_NAME,))
    skills = _rendered_skill_names(target, upstream_root, outside_files)
    with _outside_templates(target.source_root, outside_files) as outside_dir:
        rendered = render_templates(
            upstream_root / TEMPLATES_DIR_NAME,
            Path(),
            target.template_vars,
            include_skills=skills,
            target_name=target.name,
            outside_templates_dir=outside_dir,
        )
    shared: dict[str, str] = {}
    files: dict[str, OutputFile] = {}
    for output_path, content in rendered.items():
        parts = output_path.parts
        if len(parts) != 3 or parts[0] != SKILLS_DIR_NAME:
            msg = f"the agent-skills platform rendered {output_path}, which is neither a skill nor a shared file"
            raise SystemExit(msg)
        if parts[1] == SHARED_DIR_NAME:
            shared[parts[2]] = content
        else:
            files[f"{parts[1]}/{parts[2]}"] = OutputFile(content.encode("utf-8"))
    sources = ((upstream_root, upstream_assets), (target.source_root, outside_files))
    for skill in skills:
        files.update(_static_assets(target, sources, skill))
    match target.shared_layout:
        case SharedLayout.BESIDE:
            files.update(_shared_closure(files, SHARED_DIR_NAME, shared))
        case SharedLayout.IN_EACH_SKILL:
            for skill in skills:
                own = {rel: file for rel, file in files.items() if rel.startswith(f"{skill}/")}
                files.update(_shared_closure(own, f"{skill}/{SHARED_DIR_NAME}", shared))
    files[OWNER_MARKER_NAME] = OutputFile(_owner_marker(target.name, sorted(files)).encode("utf-8"))
    return dict(sorted(files.items()))


def _owner_marker(name: str, written: Sequence[str]) -> str:
    listed = "".join(f"    {json.dumps(rel)},\n" for rel in written)
    return (
        "# The output of pipelex-plugins' outside render for this target, which owns the directory: each render\n"
        "# rewrites it and removes whatever it no longer produces. Delete the whole directory to take it back.\n"
        f"target = {json.dumps(name)}\n"
        f"files = [\n{listed}]\n"
    )


def _marker_table(marker: Path) -> dict[str, object]:
    """What an owner marker says, or nothing when it cannot be read."""
    try:
        return tomllib.loads(marker.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
        return {}


def _marker_owner(marker: Path) -> str | None:
    """The target an owner marker names, or None when it names none."""
    owner = _marker_table(marker).get("target")
    return owner if isinstance(owner, str) else None


def _written_before(target: OutsideTarget) -> set[Path]:
    """The files the last render of this target wrote, as its owner marker lists them; none without a marker."""
    marker = target.output_dir / OWNER_MARKER_NAME
    if not marker.is_file() or marker.is_symlink():
        return set()
    listed = _marker_table(marker).get("files")
    if not isinstance(listed, list):
        return set()
    return {target.output_dir / rel for rel in cast(list[object], listed) if isinstance(rel, str)}


def _litter_is_ignored(target: OutsideTarget, files: Mapping[str, OutputFile]) -> bool:
    """Whether a file git ignores in an unmarked output is litter the render may write beside, as the in-repo build does.

    Only when git ignores none of the files the render produces. Where it ignores some of them, an
    ignored file there may be somebody else's at a path the render writes; where it ignores the
    output as a whole, an ignored directory of somebody else's skills would look empty. Either way
    an unmarked directory must hold nothing at all.
    """
    return not git_ignored(target.output_dir, [target.output_dir / rel for rel in files])


def _orphans(target: OutsideTarget, files: Mapping[str, OutputFile], written: set[Path]) -> list[Path]:
    """What the output holds that the render does not produce and removes: each file git does not ignore, and each one it wrote.

    A file git ignores that no render wrote is litter, a Finder `.DS_Store` the usual one, and stays,
    however much of the output the consumer ignores; the marker's list is what tells a skill the
    target stopped rendering, ignored with the rest, from that litter. The walk never descends a
    symbolic link, so nothing the list names beyond one is reached.
    """
    output_dir = target.output_dir
    candidates = orphaned_outputs(output_dir, output_dir, {output_dir / rel for rel in files}, skip_ignored=False)
    ignored = git_ignored(output_dir, candidates)
    return [path for path in candidates if path not in ignored or path in written]


def ownership_errors(target: OutsideTarget, files: Mapping[str, OutputFile]) -> list[str]:
    """Why the output directory is not this render's to write and prune; nothing when it is.

    The render removes everything in its output that it does not produce, so it writes only into a
    directory that is new or empty, or that carries the owner marker an earlier render of this same
    target left: a directory holding anything else is somebody else's, a checkout's `.git/` or a
    harness's other skills. A `.git` at any depth is refused even under the marker, since a repository
    made in the output after a render is not the render's either. And it writes through no symbolic
    link: a link on the path of a file it produces would carry the write outside the output, where
    the link points.
    """
    output_dir = target.output_dir
    if not output_dir.exists():
        return []
    label = _label(target, output_dir)
    if not output_dir.is_dir():
        return [f"{label}: the render's output is not a directory"]
    errors: list[str] = []
    marker = output_dir / OWNER_MARKER_NAME
    if marker.is_file() and not marker.is_symlink():
        owner = _marker_owner(marker)
        if owner != target.name:
            whose = f"the outside target {owner!r}" if owner is not None else "nobody this render can read"
            errors.append(f"{label}: its {OWNER_MARKER_NAME} names {whose}, not {target.name!r}; give each target an output directory of its own")
    else:
        foreign = orphaned_outputs(output_dir, output_dir, set(), skip_ignored=_litter_is_ignored(target, files))
        if foreign:
            named = ", ".join(_label(target, path) for path in foreign[:3]) + (", …" if len(foreign) > 3 else "")
            errors.append(
                f"{label}: holds files no render of this target wrote ({named}), and the render removes what it does not produce; "
                "name a new or empty directory as the output, or delete this one if it is an earlier rendering"
            )
    errors.extend(
        f"{_label(target, repository)}: a git repository inside the output, which the render owns whole; "
        "keep the repository outside the output, or render into a directory of its own and copy the skills in"
        for repository in _repositories(output_dir)
    )
    links: set[Path] = set()
    for rel in files:
        parts = rel.split("/")
        for depth in range(1, len(parts)):
            ancestor = output_dir.joinpath(*parts[:depth])
            if ancestor.is_symlink():
                links.add(ancestor)
                break
    errors.extend(
        f"{_label(target, link)}: a symbolic link, which the render would write through into {link.resolve()}; replace it with a directory"
        for link in sorted(links)
    )
    return errors


def _repositories(output_dir: Path) -> list[Path]:
    """Every `.git` in the output, a repository's own directory or a worktree's file, at any depth and never entered."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in output_dir.walk():
        if GIT_DIR_NAME in dirnames or GIT_DIR_NAME in filenames:
            found.append(dirpath / GIT_DIR_NAME)
        dirnames[:] = [name for name in dirnames if name != GIT_DIR_NAME]
    return sorted(found)


def link_errors(target: OutsideTarget, files: Mapping[str, OutputFile]) -> list[str]:
    """The link check of `scripts/skill_links.py` over a rendering, run in a scratch copy of it.

    Its boundary is the output directory in the `beside` layout, and each skill's own directory in
    the `in-each-skill` layout, where a link that leaves its skill names a file the skill's uploaded
    copy does not carry. Findings name files as `<output>/<path>`.
    """
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        output = root / target.output_dir.name
        _write_files(output, files)
        boundary = output if target.shared_layout == SharedLayout.BESIDE else None
        return skill_link_errors(output, root, boundary=boundary)


def _write_files(output_dir: Path, files: Mapping[str, OutputFile]) -> None:
    """Write each file whose bytes or executable bit differ, and leave the others untouched."""
    for rel, file in files.items():
        path = output_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.is_symlink() or path.read_bytes() != file.content:
            if path.is_symlink():
                path.unlink()
            path.write_bytes(file.content)
        mode = path.stat().st_mode
        wanted = mode | 0o111 if file.executable else mode & ~0o111
        if wanted != mode:
            path.chmod(stat.S_IMODE(wanted))


def _label(target: OutsideTarget, path: Path) -> str:
    return path.relative_to(target.output_dir.parent).as_posix()


def build(target: OutsideTarget, upstream_root: Path = UPSTREAM_ROOT) -> int:
    """Render the target into its output directory and prune what it no longer produces; write nothing on a refusal or a broken link."""
    problems = declaration_errors(target, upstream_root)
    if problems:
        return _fail(problems, "The target changes upstream files without declaring them, or a declaration no longer holds.")
    files = render_outside(target, upstream_root)
    problems = link_errors(target, files)
    if problems:
        return _fail(problems, "The rendering has a broken link, or ships a file nothing names; nothing was written.")
    problems = ownership_errors(target, files)
    if problems:
        return _fail(problems, "The output directory is not this render's to write; nothing was written.")
    written = _written_before(target)
    target.output_dir.mkdir(parents=True, exist_ok=True)
    _write_files(target.output_dir, files)
    for removed in remove_orphans(target.output_dir, _orphans(target, files, written)):
        print(f"  Removed {_label(target, removed)} (the render no longer produces it)")
    print(f"  [{target.name}] Rendered {len(files)} files into {target.output_dir}.")
    return 0


def check(target: OutsideTarget, upstream_root: Path = UPSTREAM_ROOT) -> int:
    """Render in memory and report every way the output directory differs from it, and every link error. Writes nothing."""
    problems = declaration_errors(target, upstream_root)
    if problems:
        return _fail(problems, "The target changes upstream files without declaring them, or a declaration no longer holds.")
    files = render_outside(target, upstream_root)
    problems = ownership_errors(target, files)
    if problems:
        return _fail(problems, "The output directory is not this render's; nothing was compared.")
    findings = [f"LINK: {error}" for error in link_errors(target, files)]
    for rel, file in files.items():
        path = target.output_dir / rel
        label = _label(target, path)
        if not path.is_file():
            findings.append(f"MISSING: {label}")
        elif path.read_bytes() != file.content:
            findings.append(f"STALE: {label}")
        elif bool(path.stat().st_mode & stat.S_IXUSR) != file.executable:
            findings.append(f"MODE: {label} (executable bit differs from its source)")
    for orphan in _orphans(target, files, _written_before(target)):
        label = _label(target, orphan)
        if orphan.suffix == ".j2":
            findings.append(f"LEAKED TEMPLATE: {label} (a template belongs under the source root's templates/: move it there, or delete it)")
        else:
            findings.append(f"ORPHAN: {label} (the render does not produce it, and removes it)")
    if findings:
        return _fail(findings, "The rendering is out of date. Render the target again, and apply any other cure a line above names.")
    print(f"  [{target.name}] All {len(files)} rendered files are fresh in {target.output_dir}.")
    return 0


def _fail(lines: Sequence[str], summary: str) -> int:
    for line in lines:
        print(f"  {line}")
    print(f"FAIL: {summary}")
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render pipelex-plugins' skills for an outside target.")
    parser.add_argument("target_file", type=Path, help="the outside target's TOML file")
    parser.add_argument("--check", action="store_true", help="compare the output directory with a fresh rendering; write nothing")
    args = parser.parse_args(argv)
    target = load_outside_target(cast("Path", args.target_file))
    if cast("bool", args.check):
        return check(target)
    return build(target)


if __name__ == "__main__":
    sys.exit(main())
