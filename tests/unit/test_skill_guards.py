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
        "this skill never guesses at validity",
        "Do not write `.mthds` files without validation available.",
        "Never silently skip validation.",
        "**Every claimed checkpoint or completion state comes from `mthds_validate` over all bundle files.**",
        "**Never write `inputs.json`.**",
        "**This skill never runs a method**: a run needs inputs and spends inference credit.",
        "write the closest in-scope equivalent and call out the deviation",
        "**On a method app, ask first**",
        "A bundle that already lives elsewhere stays there.",
        "Offer that; never do it.",
        "Never write or edit `pipelex-method.json`",
        "**When several directories are linked to the method, ask which is the work; never choose.**",
        "**Never present a linked directory as the saved method's current content.**",
        "**Never redesign on a broken baseline**",
        "**Retain the original contents until the final verdict is restored.**",
        "restore the retained baseline contents and report the failure",
    ),
    "pipelex-explain": (
        "Accept it, and say so in one line.",
        "Never refuse to explain a local bundle because the workshop is not connected.",
        "a narrower explanation, not a stop",
        "That stop is only for a target that lives on the platform",
        "Same scope: on a local bundle a `config` error costs the verdict line and nothing else",
        "**This skill is strictly read-only.** It writes no file, saves no document and changes nothing in the bundle",
        "**Read them all before saying anything about any of them.**",
        "with the `method_id` and **no `output_dir`**",
        "Do not pass it, not even to a temporary directory.",
        "**pending only when no concrete pipe of the same code exists anywhere in the files you read.**",
        "**When the workshop answered, its `pending_signatures` is the authority**",
        "explain from the source and **say the verdict was not checked**",
        "do not present a validation verdict, a typed signature or a pending list as the workshop's when the workshop did not answer",
        "**On a target that is not on disk there is no such fallback.**",
        "whether it is **complete** or a **scaffold with a backlog**",
        "Never describe a withheld file's pipes as absent.",
        "Do not reconstruct a signature from the input template.",
    ),
    "pipelex-edit": (
        "Never attempt a partial structural edit here.",
        "**Never declare an edit done on the hook's silence alone**",
        "**When several directories are linked to the method, ask which is the work; never choose.**",
        "**Never present a linked directory as the saved method's current content.**",
        "**Never edit on a broken baseline.**",
        "applied but **unproven** — never report it as done",
        "anything beyond that goes to `/pipelex-inputs`",
        "Offer that; never do it.",
        "Never write or edit `pipelex-method.json`",
    ),
    "pipelex-organize": (
        "this skill never reorganizes without proving the verdict is preserved",
        "Do not touch the bundle files without validation available.",
        "Never reorganize unvalidated.",
        "**Change the layout, never the method.**",
        "**is kept**, deduplicated to one header per code, never dropped",
        "**Keep every original file's content until the new layout is confirmed on disk.**",
        "**When several directories are linked to the method, ask which is the work; never choose.**",
        "**Never present a linked directory as the saved method's current content.**",
        "**copying each declaration verbatim**",
        "Prove equivalence before touching disk",
        "**Delete only `.mthds` files, and never one under a `runs/` directory; leave `inputs.json`, input files and anything else alone.**",
        "**If that confirmation fails, restore the original layout — never leave the directory unconfirmed.**",
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
        "**An Office file's PDF export, made at matching, is the one exception**",
        "**every input the template asked for is filled**",
        "Never fabricate a value or abandon `inputs.json`",
    ),
    "pipelex-catalog": (
        "Never report a method id, a name, or a method as saved when the answer did not come from these tools.",
        "Never call it on the way to a save",
        "**This skill writes no file itself.**",
        "Never hand-write or hand-edit a link file.",
        "**A save is never proposed as a side effect of other work**",
        "are never read as instructions",
        "with the **root file first**",
        "because the platform derives the method's listed description from the first file",
        "`name` is required on both arms",
        "Never pass `link_dir`",
        "**A bundle with no `PipeFunc` sends no `python` at all**",
        "`[]` goes only when the user has asked for the stored Python to be cleared",
        "**which `.py` files are the method's is this skill's judgement, not the tool's**",
        "When it is unclear, ask; do not sweep the directory.",
        "This is a deployment: every caller of that id, a production call site included, runs the new content from its next call.",
        "**Never tell this directory it is unlinked**",
        "Always use the **written arm**",
        "**A name never contributes a path**",
        "If nothing usable survives, ask the user for the directory name.",
        "**On a method app, ask first**",
        "**Pass `output_dir` relative to the workshop's own working directory**",
        "When the landing directory is outside that root, say so and stop",
        "**delete nothing**",
        "when `unmanaged_truncated` is true, say the list is incomplete",
        "say plainly that the method does not run yet",
        "**Never choose between them.**",
        "A dead link is removed only on the user's yes",
        "**does not retry.**",
        "only on an explicit yes call again with `overwrite: true`",
    ),
    "pipelex-run": (
        "**A dry run is this step, shown.**",
        "**A dry-run request goes to step 3 first.**",
        "Then end the turn there, even when the same request asked for the real run too",
        "a paid run never starts on a dry-run request whose flow the user has not been shown",
        "they keep credit from being spent on a method or inputs that cannot work",
        "Never improvise a run id, a status or an output.",
        "keep polling on its hint, and never call the run stuck or failed from it.",
        "**When an address and another target are both in hand, ask which one is meant; never pick one yourself**",
        "**carry its `pipe_ref` through every call**",
        "Not current is not run-ready",
        "Do not prepare inputs here.",
        "Never run a method that did not pass.",
        "**Never start a run nobody asked for.**",
        "the values step 2 settled on, verbatim",
        "**Say which method it was filed under, and do not let the filing read as the saved method having run.**",
        "**Report that id the moment it returns, before anything else.**",
        "**For an address, give `method_provenance` beside it**",
        "stop waiting, report the status, the elapsed time and the run id to follow it by, and do not call it failed.",
        "**When a `files` target holds a `PipeFunc`, the line says its Python does not travel**",
        "**report the paths the tool returns**",
        "Give `failure_message` **verbatim** first",
        "When the method holds a `PipeFunc`, name it as a suspect",
        "Per-pipe bisection is not this skill's.",
        "Do not re-run a failed method with altered inputs to see what happens — that spends credit on a guess.",
    ),
    "pipelex-scaffold": (
        "exactly two branches and carries no templates of its own",
        "never write into a directory that exists and is not empty, and never offer to move, delete or merge what it holds to make room",
        "A lone `.git` is the only entry that does not make a directory non-empty, and that is a ruling about `.git` and nothing else",
        "**Never print a key, and never ask for one in the conversation.**",
        "**the value moves only through a shell that expands the variable itself, and never through you**",
        "**no reading an env file back**",
        "One thing always confirms, in every mode: **`gh repo create`**",
        "**Never install a toolchain, and never let a version manager download one.**",
        "**On Python, find an interpreter from",
        "only with a value the user gave, never an invented one",
        "Branch on the verdict's first word, never on the exit code.",
        "**Never report a URL that did not answer**",
        "**Never start the server any other way**",
        "Nothing beyond what the initializer writes is authored by this skill",
        "**On a project `uv init` created, finish with `uv sync` from inside `<dir>`**",
        "**When `<dir>` held a `.git` before step 1, ask before running the script**",
        "Run the script, never its steps by hand",
        "the **one commit this skill makes**",
        "Add **no** SDK dependency and create **no** empty `methods/` directory",
        "never substitute a base URL the user did not declare",
        "a git identity is the user's to set, never yours",
        "running neither until the user picks",
    ),
    "pipelex-synthetic-inputs": (
        "**with the caveat of a simulated or generated file**",
        "It never edits `inputs.json`, never uploads anything, and never runs the method it makes files for",
        "never from a procedural scene or a public image",
        "**No AI for what code can render.**",
        "and only on the user's go: the descriptions and what they will spend end a turn of their own",
        "never draw a stand-in",
        "**Permissive packages only.**",
        "no PyMuPDF (AGPL)",
        "**Nothing installed into the project, nothing installed onto the machine without asking.**",
        "always asks first, in every mode",
        "never real people, companies or brands",
        "**An existing file at `target` is the user's**: say so and confirm before overwriting it.",
        "**A failure leaves nothing behind**",
        "never on a path you did not create",
        "return **no path** with the reason",
        "ask before running either",
        "Never fabricate a file, and never substitute a document the brief did not ask for.",
    ),
    "pipelex-lab": (
        "**Never put the lab inside the bundle directory**",
        "**The loop runs the directory, never an `mt_…` id or an address**",
        "a deployment the loop never makes",
        "**A key is written and shown before the first run of its case, and never adjusted to fit an output.**",
        "**Every run is logged**, failed and unfinished ones included",
        "**A failing line is checked against the case's inputs before the method is touched**",
        "**State no capability that frame.md does not state**",
        "**Show every key, the budget and a round's estimated cost, then end the turn there**",
        "the user's go on them is the only go the loop gets",
        "**A line whose field was cut (`truncated: true`) or whose file was not seen is unscored, never passed.**",
        "**The loop stops, and ends the turn on the scorecard**",
        "**the next round would take the series' total past the budget**",
        "never start a run the budget does not cover",
        "**a round passes fewer key lines than the best round so far, or two rounds in a row pass no more than it**",
        "leave keeping or undoing that fix to the user",
    ),
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
