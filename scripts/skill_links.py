"""Links between rendered skill files resolve both ways (box H of the size diet's design, L-260923-a9bdfe).

Shared by `scripts/check.py`, which holds the in-repo targets to it, and `scripts/outside_render.py`,
which holds an outside target's rendering to it. It imports nothing outside the standard library,
because the outside render runs from an installed package whose only dependency is Jinja.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

# A Markdown link's target: `[text](target)`, the target running to the first `)` or space.
MARKDOWN_LINK_PATTERN = re.compile(r"\]\(([^)\s]+)\)")
# A fenced block, indented or not (a list item indents its fences), closed by a fence of the same
# character at least as long as the one that opened it, so a four-backtick fence can wrap a three.
FENCED_BLOCK_PATTERN = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,}).*?^[ \t]*(?P=fence)[`~]*[ \t]*$", re.MULTILINE | re.DOTALL)
INLINE_CODE_PATTERN = re.compile(r"`[^`\n]*`")
# Where a skill names one of its own scripts: after the skill-directory expression, whatever a
# target spells it as, so the check keys on the `/scripts/<name>` tail that every spelling shares.
SKILL_SCRIPT_MENTION_PATTERN = re.compile(r"/scripts/([A-Za-z0-9_.\-/]+)")
# The directory a skill's links find the shared files in, wherever it sits.
SHARED_DIR_NAME = "shared"


def without_fenced_blocks(text: str) -> str:
    """The text with fenced blocks blanked, line count kept, so a `#` comment in code is never a heading."""
    return FENCED_BLOCK_PATTERN.sub(lambda match: "\n" * match.group(0).count("\n"), text)


def markdown_prose(text: str) -> str:
    """The text with fenced blocks and inline code blanked, so an example is never read as a link."""
    return INLINE_CODE_PATTERN.sub("``", without_fenced_blocks(text))


def heading_slugs(text: str) -> set[str]:
    """The anchors GitHub-flavoured Markdown gives the file's headings.

    Lowercased, every character that is not a letter, a digit, a space, a hyphen or an underscore
    dropped, and each space turned into a hyphen — so `Step 8 — a method` becomes `step-8--a-method`.
    Inline code keeps its text and loses only its backticks, as on GitHub, so a heading naming a tool
    keeps the tool's name in its anchor.
    """
    slugs: set[str] = set()
    seen: dict[str, int] = {}
    for line in without_fenced_blocks(text).splitlines():
        match = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if match:
            slug = re.sub(r"[^\w\- ]", "", match.group(1).lower()).replace(" ", "-")
            # A repeated heading's later occurrences are `slug-1`, `slug-2`, … on GitHub.
            count = seen.get(slug, 0)
            seen[slug] = count + 1
            slugs.add(slug if count == 0 else f"{slug}-{count}")
    return slugs


def link_targets(text: str) -> list[str]:
    """Every relative link target in the prose of a Markdown file, anchors included."""
    targets: list[str] = []
    for match in MARKDOWN_LINK_PATTERN.finditer(markdown_prose(text)):
        target = match.group(1)
        if re.match(r"^[a-z][a-z0-9+.\-]*:", target) or target.startswith("/"):
            continue  # a URL, a mailto: or an absolute path is not a file of the plugin
        targets.append(target)
    return targets


def linked_paths(text: str, file_rel: str) -> list[str]:
    """The files a Markdown file links to, as normalised POSIX paths relative to the same root as `file_rel`.

    An anchor alone links the file to itself and is left out. A path that climbs above the root keeps
    its leading `..`, so a caller can tell it left.
    """
    paths: list[str] = []
    for target in link_targets(text):
        path_part = target.partition("#")[0]
        if path_part:
            paths.append(posixpath.normpath(posixpath.join(posixpath.dirname(file_rel), path_part)))
    return paths


def skill_link_errors(skills_dir: Path, label_root: Path, *, boundary: Path | None) -> list[str]:
    """Every link in a rendered skill tree that resolves to nothing, and every shipped file nothing names.

    `skills_dir` holds one directory per skill, with the shared files either beside them in
    `skills_dir/shared/` or copied into each skill as `<skill>/shared/`. Forward: every relative link
    in a skill, a reference or a shared file names a file that exists within `boundary`, or within
    its own skill's directory when `boundary` is None, and every anchor names a heading of the file
    it points into. Backward: every file a skill ships under `references/` or `scripts/` is named by
    something the model reads first — a reference by a SKILL.md link, a script by a SKILL.md or by a
    reference of its own skill — and every shared file by a skill or a reference. A pointer to
    nothing sends the model to a read that fails; a file named by nothing is a caveat no model will
    ever read. Each finding names its file relative to `label_root`.
    """
    errors: list[str] = []
    shared_files = sorted(skills_dir.glob(f"{SHARED_DIR_NAME}/*.md")) + sorted(skills_dir.glob(f"*/{SHARED_DIR_NAME}/*.md"))
    markdown_files = sorted(skills_dir.glob("*/SKILL.md")) + sorted(skills_dir.glob("*/references/**/*.md")) + shared_files
    leaves = "the target, whose installed copy" if boundary is not None else "its skill, whose uploaded copy"
    named: set[Path] = set()
    for md_file in markdown_files:
        text = md_file.read_text(encoding="utf-8")
        rel = md_file.relative_to(label_root)
        skill_root = skills_dir / md_file.relative_to(skills_dir).parts[0]
        root = (boundary if boundary is not None else skill_root).resolve()
        for target in link_targets(text):
            path_part, _, anchor = target.partition("#")
            resolved = (md_file.parent / path_part).resolve() if path_part else md_file.resolve()
            if path_part:
                if not resolved.is_relative_to(root):
                    errors.append(f"{rel}: link to `{target}` leaves {leaves} does not carry it")
                    continue
                if not resolved.is_file():
                    errors.append(f"{rel}: link to `{target}` names no file in this target")
                    continue
                if md_file.name == "SKILL.md" or resolved.parent.name in {"scripts", SHARED_DIR_NAME}:
                    named.add(resolved)
            if anchor and resolved.suffix == ".md" and anchor not in heading_slugs(resolved.read_text(encoding="utf-8")):
                errors.append(f"{rel}: anchor `#{anchor}` names no heading of {resolved.name}")
        for match in SKILL_SCRIPT_MENTION_PATTERN.finditer(text):
            script = (skill_root / "scripts" / match.group(1).rstrip(".")).resolve()
            if script.is_file():
                named.add(script)
    for asset in sorted(skills_dir.glob("*/references/**/*")) + sorted(skills_dir.glob("*/scripts/**/*")):
        if asset.is_file() and asset.resolve() not in named:
            errors.append(f"{asset.relative_to(label_root)}: shipped but named by nothing the model reads")
    for shared in shared_files:
        if shared.resolve() not in named:
            errors.append(f"{shared.relative_to(label_root)}: shipped but named by no skill and no reference")
    return errors
