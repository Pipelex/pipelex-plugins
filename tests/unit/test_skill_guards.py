"""The guard registry (box H of `wip/skill-size-diet/design.md`).

A guard is a sentence a model must have read before it acts: skipping it loses something that
cannot be recovered, sends something off the machine, spends credit, or leaves a result wrong with
nothing later to say so. Box A keeps every guard in `SKILL.md`, once, at the step it governs — never
in a reference, which a model reads only when a branch sends it there.

So each guard is registered here by its canonical sentence, and the suite asserts, on every target,
that the sentence appears **exactly once** in the skill's rendered `SKILL.md` and in **none** of the
files the skill reads on demand: its own `references/` and the rendered `shared/` files. Presence
and uniqueness are one assertion because both failures are the ones the diet exists to prevent —
a guard moved into a reference is a guard that may not be read, and a guard stated twice is a guard
whose two copies drift.

A canonical sentence is the wording every target renders identically; where a platform branch
changes a sentence, register the part the branches share. A skill phase registers its guards in the
same change that places them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TARGET_OUTPUTS = ("pipelex", "pipelex-codex", "pipelex-vibe")

GUARDS: dict[str, tuple[str, ...]] = {
    "pipelex-design": (
        "Never silently skip validation.",
        "Offer that; never do it.",
        "Never write or edit `pipelex-method.json`",
    ),
    "pipelex-edit": (
        "Offer that; never do it.",
        "Never write or edit `pipelex-method.json`",
    ),
    "pipelex-organize": (
        "Offer that; never do it.",
        "Never write or edit `pipelex-method.json`",
    ),
    "pipelex-integrate": (
        (
            "Every `mthds_codegen` call passes `output_dir`; "
            "a refused or failed write is a refusal, never a reason to write the returned bytes yourself."
        ),
        "**Generated files are never opened for editing, never formatted, never linted**; a failure inside the tree is reported, never patched.",
        "**Never delete an orphan, and never offer to clean orphans up**",
        "**Never generate from one source and run from another**",
        "**A project that owns a codegen harness keeps it**: never a second generated layout beside its own.",
        "**A `method_ref` is recorded exactly as it was passed, an absent tag included**, in a sidecar or a harness's manifest.",
        "**No `dropWireNulls` / `wireOutput` helper**",
        "proceed only on the user's say-so",
        "**Check containment before writing anything**",
        "**Never write the tree into the workshop's directory and move it across.**",
        "never a signature derived from the source",
        "**`pipe_ref` is namespaced (`summarize.summarize_pdf`), the run's `pipe_code` is not**",
        "**A directory holding a `codegen.lock` is this method's only when a `sources.json` beside it names this method**",
        "never relocate silently or clear it",
        "**Do this before step 6**",
        "Read it off the two lists, never from `is_current`",
        "never delete, move or clear it, and never offer to",
        '**A list output (`variable`, `fixed`) arrives as `{"items": […]}`, never a bare array: narrow its `items`, as the template shows**',
        "The module never reads credentials and never uploads",
        "**Exactly one shared helper**",
        "never by rewriting it, and never format the copy",
        "**A file already there without the line `Copied verbatim into a project by /pipelex-integrate` is the user's: ask first.**",
        "Format **only the files you wrote**",
        "report `drifts[]` verbatim and stop; commit nothing",
        "never guess the output concept",
        "never add its hash to `sources` by hand",
    ),
    "pipelex-inputs": (
        "never hand-derive the template from the `.mthds` source",
        "Never silently improvise a template.",
        "never hand-fake a storage reference",
        "**The template is authoritative**: fill its values; never invent shapes it doesn't have.",
        "**A path in `inputs.json` resolves relative to `inputs.json` itself, never to the working directory**",
        "**Say what is about to leave the machine, before it does**",
        "If the user declines, stop before the call and report that the inputs stay local and are not runnable.",
        "**Send the exact file that was selected, generated, copied or referenced for an input — never a derived one**",
        "A preflight size check may inform the report, but it is never a reason to transform, derive, or substitute the asset.",
        "Do not compress, optimize, re-encode, resize, downsample, split, truncate, extract pages or content, or convert it.",
        "Do not replace it with synthetic data, a public sample, another local file, or any derived file.",
        "The same prohibition applies after an upload failure. Never retry preparation with altered or substitute content to evade a storage limit.",
        "**first delete any `inputs.prepared.json` an earlier prepare left in `<output_dir>`**",
        "step 2's `pipe_ref` if it passed one",
        "**every local file path resolved to an absolute path**",
        "**write `<output_dir>/inputs.prepared.json` with the returned `inputs`, and leave `inputs.json` exactly as it is**",
        'never "simplify" it back to a string',
        "Leave the copies in `<output_dir>/inputs/` alone.",
        "add `inputs.prepared.json` to the nearest `.gitignore`",
        "**prepare again whenever a file was replaced in place.**",
        "**Offer the run, never start it**",
        "never call a run tool here",
        "**every input the template asked for is filled**",
        "Never fabricate a value or abandon `inputs.json`",
    ),
    "pipelex-run": ("Never improvise a run id, a status or an output.",),
    "pipelex-scaffold": ("never report a URL",),
}

CASES = [(target, skill, guard) for target in TARGET_OUTPUTS for skill, guards in GUARDS.items() for guard in guards]


def _on_demand_files(target: str, skill: str) -> list[Path]:
    """What the skill reads only when a branch sends it there: its references and the shared files."""
    skills_dir = REPO_ROOT / target / "skills"
    references = [path for path in (skills_dir / skill / "references").rglob("*") if path.is_file()]
    return references + sorted((skills_dir / "shared").glob("*.md"))


@pytest.mark.parametrize(("target", "skill", "guard"), CASES)
def test_a_guard_is_stated_exactly_once_in_its_skill(target: str, skill: str, guard: str) -> None:
    skill_md = REPO_ROOT / target / "skills" / skill / "SKILL.md"
    count = skill_md.read_text(encoding="utf-8").count(guard)
    assert count == 1, f"{target}/skills/{skill}/SKILL.md states the guard {guard!r} {count} times; a guard lives in SKILL.md exactly once"


@pytest.mark.parametrize(("target", "skill", "guard"), CASES)
def test_a_guard_never_moves_to_a_file_read_on_demand(target: str, skill: str, guard: str) -> None:
    for path in _on_demand_files(target, skill):
        if path.suffix not in {".md", ".txt"}:
            continue
        assert guard not in path.read_text(encoding="utf-8"), (
            f"{path.relative_to(REPO_ROOT)} carries the guard {guard!r}; a guard stays in SKILL.md, where it is read before acting"
        )


def test_the_registry_names_shipped_skills() -> None:
    shipped = {path.parent.name for path in (REPO_ROOT / "templates" / "skills").glob("*/SKILL.md.j2")}
    assert set(GUARDS) <= shipped, f"the registry names skills that do not exist: {sorted(set(GUARDS) - shipped)}"
