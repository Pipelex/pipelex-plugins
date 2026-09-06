"""Execute the recipe blocks shipped by `pipelex-synthetic-inputs`.

The skill's know-how is prose the agent copies and adapts, which is the right
shape for content that differs every time — but prose rots silently. Its
predecessor's image recipe pointed at a bundle that no longer existed, and
nothing noticed because nothing ran it. These tests run every block.

Two properties matter as much as the execution itself, because a suite
parametrised over the artifact it checks can stop checking without going red:

* every recipe is pinned by name, so a deleted or unparsed one fails here
  rather than quietly shrinking the suite (`test_every_recipe_is_accounted_for`);
* the sources are the source of truth — the reference files and the skill
  *template*, never a build artifact — so a stale `make build` cannot make a
  passing run mean nothing.

Opt-in: `make test-recipes`, or `pytest -m recipes`. The default run deselects
them (`addopts` in pyproject.toml) because the first execution downloads
packages into uv's cache.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import NamedTuple

import pytest

pytestmark = pytest.mark.recipes

REPO_ROOT = Path(__file__).parents[2]
REFERENCES_DIR = REPO_ROOT / "skills" / "pipelex-synthetic-inputs" / "references"
# The template, not the render: `make test-recipes` does not depend on `make build`,
# so reading a target directory would let this suite certify a stale copy. The
# blocks it reads carry no Jinja, which `test_skill_blocks_carry_no_jinja` pins.
SKILL_TEMPLATE = REPO_ROOT / "templates" / "skills" / "pipelex-synthetic-inputs" / "SKILL.md.j2"

OUTPUT_DIR_PLACEHOLDER = "<output_dir>"
# A block carrying this placeholder is a template the agent fills in (the
# "Verify" snippets), not a runnable recipe — running it would open a file
# literally named "<name>.png".
TEMPLATE_PLACEHOLDER = "<name>"

# Every recipe the references ship, by the heading that names it. Pinned as an
# independent source: the parametrised tests below are built from the files
# themselves, so without this set a recipe could vanish — deleted, its fence
# retyped, its runner line reworded — and the suite would just get smaller.
EXPECTED_RECIPES = {
    ("office.md", "Word documents (DOCX)"),
    ("office.md", "Spreadsheets (XLSX)"),
    ("pdf.md", "Basic PDF (canvas)"),
    ("pdf.md", "Multi-page PDF (Platypus)"),
    ("pdf.md", "Table report (Platypus)"),
    ("pdf.md", "Line-item document (composed)"),
    ("png.md", "Chart (matplotlib)"),
    ("png.md", "Diagram (Pillow)"),
    ("png.md", "Scanned document (Pillow)"),
    ("png.md", "App screenshot (Pillow)"),
}

MAGIC_BY_SUFFIX = {
    ".pdf": b"%PDF",
    ".png": b"\x89PNG",
    ".docx": b"PK",
    ".xlsx": b"PK",
}

# `PK` is two bytes any zip satisfies, including one holding no document at all.
# The Office formats get the same depth of check as the others: name the part
# that makes the package a document.
REQUIRED_ZIP_MEMBER = {".docx": "word/document.xml", ".xlsx": "xl/workbook.xml"}

BASH_BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)
HEADING = re.compile(r"^## (.+)$", re.MULTILINE)
OUT_ASSIGNMENT = re.compile(r'^OUT = "([^"]+)"', re.MULTILINE)
DECLARED_SIZE = re.compile(r"^WIDTH, HEIGHT(?:, DPI)? = (\d+), (\d+)", re.MULTILINE)
PDF_PAGE_OBJECT = re.compile(rb"/Type\s*/Page[^s]")
WITH_PACKAGE = re.compile(r"--with (\S+)")
PACKAGE_SETS_LINE = re.compile(r"^\*\*Package sets by format:\*\* (.+)$", re.MULTILINE)
PACKAGE_SET_ENTRY = re.compile(r"`(\w+)` → `([^`]+)`")
UV_RUN = re.compile(r"uv run(?P<arguments>[^`\n]*)")
JINJA = re.compile(r"\{[{%]")

UV_MISSING = shutil.which("uv") is None
NEEDS_UV = pytest.mark.skipif(UV_MISSING, reason="the uv rung of the environment ladder needs uv on PATH")


class RecipeBlock(NamedTuple):
    """One runnable recipe extracted from a reference file."""

    reference: str
    heading: str
    script: str
    output: str
    width: int | None
    height: int | None

    @property
    def packages(self) -> frozenset[str]:
        """The `--with` set on this recipe's runner line."""
        return frozenset(WITH_PACKAGE.findall(self.script.split("\n", maxsplit=1)[0]))


def _heading_above(text: str, position: int) -> str:
    """The nearest `##` heading before `position`, which names the recipe."""
    headings = [match for match in HEADING.finditer(text) if match.start() < position]
    return headings[-1].group(1) if headings else "(no heading)"


def _is_runnable(script: str) -> bool:
    return script.startswith("uv run") and TEMPLATE_PLACEHOLDER not in script


def _collect_recipes() -> list[RecipeBlock]:
    recipes: list[RecipeBlock] = []
    for reference in sorted(REFERENCES_DIR.glob("*.md")):
        text = reference.read_text(encoding="utf-8")
        for block in BASH_BLOCK.finditer(text):
            script = block.group(1)
            if not _is_runnable(script):
                continue
            out = OUT_ASSIGNMENT.search(script)
            assert out is not None, f'{reference.name}: a recipe block has no `OUT = "…"` line to check'
            size = DECLARED_SIZE.search(script)
            recipes.append(
                RecipeBlock(
                    reference=reference.name,
                    heading=_heading_above(text, block.start()),
                    script=script,
                    output=out.group(1).replace(f"{OUTPUT_DIR_PLACEHOLDER}/", ""),
                    width=int(size.group(1)) if size else None,
                    height=int(size.group(2)) if size else None,
                )
            )
    return recipes


RECIPES = _collect_recipes()
RECIPE_IDS = [f"{recipe.reference}:{recipe.heading}" for recipe in RECIPES]
# One entry per distinct `--with` set the shipped recipes actually use, derived
# from the runner lines rather than restated here — a renamed package in a
# reference must fail the preflight test, which is what that test claims to do.
PACKAGE_SETS = sorted({recipe.packages for recipe in RECIPES}, key=sorted)
PACKAGE_SET_IDS = [" ".join(sorted(packages)) for packages in PACKAGE_SETS]


def _png_size(data: bytes) -> tuple[int, int]:
    """Width and height straight out of the IHDR chunk — no Pillow needed."""
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def _bash(script: str, *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", script],
        cwd=cwd,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        check=False,
    )


def _skill_blocks() -> list[str]:
    skill = SKILL_TEMPLATE.read_text(encoding="utf-8")
    return [block.group(1) for block in BASH_BLOCK.finditer(skill)]


class TestRecipes:
    """Every recipe block runs and writes the file it declares, in the format
    and at the size it declares — on both rungs of the environment ladder."""

    def test_every_recipe_is_accounted_for(self) -> None:
        """The suite cannot shrink without going red.

        Pinning the (file, heading) pairs catches a recipe that was deleted, and
        catches one that stopped being collected — a fence retyped to ```sh, a
        runner line reworded, a content block that happens to contain the
        `<name>` placeholder — which the collector would otherwise skip in
        silence.
        """
        assert {(recipe.reference, recipe.heading) for recipe in RECIPES} == EXPECTED_RECIPES

    def test_every_bash_block_is_runnable_or_a_template(self) -> None:
        """No block may fall between the two categories unnoticed."""
        for reference in sorted(REFERENCES_DIR.glob("*.md")):
            text = reference.read_text(encoding="utf-8")
            for block in BASH_BLOCK.finditer(text):
                script = block.group(1)
                if _is_runnable(script) or TEMPLATE_PLACEHOLDER in script:
                    continue
                pytest.fail(
                    f"{reference.name}: a ```bash block under "
                    f"'{_heading_above(text, block.start())}' is neither run as a recipe nor "
                    f"marked as a template with `{TEMPLATE_PLACEHOLDER}`. Did the runner line "
                    f"change?\n{script}"
                )

    @NEEDS_UV
    @pytest.mark.parametrize("recipe", RECIPES, ids=RECIPE_IDS)
    def test_recipe_writes_the_file_it_declares(self, recipe: RecipeBlock, tmp_path: Path) -> None:
        # A recipe must stay inside the output directory it was given. An absolute
        # or climbing OUT would make the assertions below inspect a file on the
        # real filesystem while the recipe wrote somewhere else entirely.
        assert not Path(recipe.output).is_absolute(), f"{recipe.heading}: OUT escapes <output_dir> — {recipe.output}"
        assert ".." not in Path(recipe.output).parts, f"{recipe.heading}: OUT climbs out of <output_dir> — {recipe.output}"

        result = _bash(recipe.script.replace(OUTPUT_DIR_PLACEHOLDER, str(tmp_path)), cwd=tmp_path)
        assert result.returncode == 0, f"{recipe.reference}:{recipe.heading} failed\n{result.stderr}"

        written = tmp_path / recipe.output
        assert written.is_file(), f"{recipe.reference}:{recipe.heading} printed success but wrote no {recipe.output}"
        data = written.read_bytes()
        assert len(data) > 512, f"{recipe.output} is {len(data)} bytes — too small to be a real file"

        magic = MAGIC_BY_SUFFIX[written.suffix]
        assert data.startswith(magic), f"{recipe.output} does not start with {magic!r}"

        if written.suffix == ".png":
            assert recipe.width is not None and recipe.height is not None, f"{recipe.heading}: a PNG recipe must declare WIDTH, HEIGHT"
            assert _png_size(data) == (recipe.width, recipe.height)

        if written.suffix == ".pdf":
            # `%PDF` is cheap to satisfy; a page object is not.
            assert PDF_PAGE_OBJECT.search(data) is not None, f"{recipe.heading}: no page objects in {recipe.output}"

        if written.suffix in REQUIRED_ZIP_MEMBER:
            member = REQUIRED_ZIP_MEMBER[written.suffix]
            with zipfile.ZipFile(written) as package:
                names = package.namelist()
            assert member in names, f"{recipe.output} is a zip with no {member} — not a document: {names}"

    @NEEDS_UV
    @pytest.mark.parametrize("package_set", PACKAGE_SETS, ids=PACKAGE_SET_IDS)
    def test_preflight_resolves_every_package_set(self, package_set: frozenset[str], tmp_path: Path) -> None:
        """A stale or renamed package in a `--with` list must fail here, not on
        a user's machine mid-flow. The sets come from the shipped runner lines,
        so a package renamed in a reference reaches this test."""
        withs = " ".join(f"--with {package}" for package in sorted(package_set))
        result = _bash(f"uv run --quiet --no-project {withs} python -c 'print(\"ok\")'", cwd=tmp_path)
        assert result.returncode == 0, f"package set '{withs}' does not resolve\n{result.stderr}"
        assert result.stdout.strip() == "ok"

    def test_runner_lines_never_touch_the_users_project(self) -> None:
        """`uv run` discovers the nearest project and syncs it — creating a
        `.venv/` and writing `uv.lock` in the user's repo. The skill promises
        the opposite ("the project is untouched"), and `--no-project` is what
        makes that true. Every recipe and every documented `uv run` must carry
        it; recipes execute from a temp dir here, where the bug is invisible."""
        offenders: list[str] = []
        invocations = 0
        for path in [SKILL_TEMPLATE, *sorted(REFERENCES_DIR.glob("*.md"))]:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                for match in UV_RUN.finditer(line):
                    arguments = match.group("arguments")
                    if not arguments.strip():
                        continue  # prose naming the command, not running it
                    invocations += 1
                    if "--no-project" not in arguments:
                        offenders.append(f"{path.name}:{number}: {line.strip()}")
        assert invocations, "no `uv run` invocation found — the extractor stopped seeing the runner lines"
        assert not offenders, "`uv run` without --no-project syncs the user's project:\n" + "\n".join(offenders)

    def test_package_sets_stay_inside_the_documented_allowlist(self) -> None:
        """The runner lines may not reach for a package the skill's Step 2 does
        not declare — the allowlist is a licence decision, not a convenience."""
        skill = SKILL_TEMPLATE.read_text(encoding="utf-8")
        sets_line = PACKAGE_SETS_LINE.search(skill)
        assert sets_line is not None, "Step 2 no longer states its package sets by format"

        by_format = {fmt: set(packages.split()) for fmt, packages in PACKAGE_SET_ENTRY.findall(sets_line.group(1))}
        assert set(by_format) == {"pdf", "png", "docx", "xlsx"}, f"the package-set mapping no longer covers every format: {sorted(by_format)}"

        documented = {package for packages in by_format.values() for package in packages}
        used = {package for recipe in RECIPES for package in recipe.packages}
        assert used <= documented, f"recipes use packages Step 2 never declares: {sorted(used - documented)}"

        # Rung 2 fills one venv with the whole allowlist, so a package added to
        # Step 2 and not to that install line is a format that works only on uv.
        install = next(line for block in _skill_blocks() for line in block.splitlines() if "pip install" in line)
        assert documented <= set(install.split()), f"the venv rung never installs: {sorted(documented - set(install.split()))}"

    def test_skill_blocks_carry_no_jinja(self) -> None:
        """This suite reads the template rather than a render, which is only
        safe while the Environment section's blocks are plain shell."""
        for block in _skill_blocks():
            assert not JINJA.search(block), f"a skill bash block now carries Jinja and cannot be run as written:\n{block}"

    @NEEDS_UV
    def test_skill_preflight_commands_run_as_written(self, tmp_path: Path) -> None:
        """The Environment section's own preflight commands, copied out of the
        skill template and run verbatim."""
        preflights = [block for block in _skill_blocks() if block.startswith("command -v uv")]
        assert len(preflights) == 2, "expected a pdf and a png preflight in the skill's Environment section"
        announced: set[str] = set()
        for preflight in preflights:
            result = _bash(preflight, cwd=tmp_path)
            assert result.returncode == 0, f"preflight failed\n{preflight}\n{result.stderr}"
            assert "ready" in result.stdout
            announced.add(result.stdout.split()[0])
        assert announced == {"pdf", "png"}, f"preflights announced {sorted(announced)}"

    def test_preflight_falls_through_quietly_when_uv_is_absent(self, tmp_path: Path) -> None:
        """Rung 1's guard is `command -v uv >/dev/null && …`, and the whole Step 2
        decision table depends on that failing *silently* so the agent drops to
        rung 2 instead of reading a shell error as a package problem. Needs
        neither uv nor the network, so it runs everywhere."""
        bash = shutil.which("bash")
        assert bash is not None, "these tests already require bash"
        for preflight in [block for block in _skill_blocks() if block.startswith("command -v uv")]:
            # An absolute bash: subprocess resolves the executable against the
            # child's PATH, so a scrubbed PATH would hide bash itself.
            result = subprocess.run(
                [bash, "-c", preflight],
                cwd=tmp_path,
                env={"PATH": str(tmp_path / "empty-bin")},
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode != 0, "the preflight must report failure when uv is missing"
            assert result.stdout.strip() == "", f"the preflight printed noise the agent would misread: {result.stdout!r}"

    def test_venv_rung_changes_only_the_runner_line(self, tmp_path: Path) -> None:
        """Rung 2, for a machine with no `uv` — deliberately not skipped when
        `uv` is present, since it is the rung a stock Python must reach.

        The skill promises that swapping the runner line is the *only*
        difference between the rungs. This creates the venv exactly as the skill
        says to, then runs one recipe per output format through it with that one
        line changed and nothing else.
        """
        if shutil.which("python3") is None:
            pytest.skip("rung 2 needs python3 on PATH")

        cache = tmp_path / "cache"
        cache.mkdir()
        created = _bash(self._venv_setup(), cwd=tmp_path, env={"XDG_CACHE_HOME": str(cache)})
        assert created.returncode == 0, f"the skill's venv setup failed\n{created.stderr}"
        assert "venv ready:" in created.stdout

        venv_python = cache / "pipelex-plugins" / "synth-venv" / "bin" / "python"
        assert venv_python.is_file(), "the venv landed somewhere other than the path the skill documents"

        # Rung 2 installs the whole allowlist, so every format it covers must run.
        for suffix in sorted(MAGIC_BY_SUFFIX):
            recipe = next(candidate for candidate in RECIPES if candidate.output.endswith(suffix))
            body = recipe.script.split("\n", maxsplit=1)[1].replace(OUTPUT_DIR_PLACEHOLDER, str(tmp_path))
            result = _bash(f"\"{venv_python}\" << 'PYEOF'\n{body}", cwd=tmp_path)
            assert result.returncode == 0, f"{recipe.heading} failed on the venv rung\n{result.stderr}"
            assert (tmp_path / recipe.output).read_bytes().startswith(MAGIC_BY_SUFFIX[suffix])

    def test_venv_rung_is_created_once_and_reused(self, tmp_path: Path) -> None:
        """ "Create a venv this skill owns, once … and reuse it on every later
        invocation" — a regression that rebuilt or reinstalled on every call
        would be a slow, network-touching surprise, and nothing else would
        notice."""
        if shutil.which("python3") is None:
            pytest.skip("rung 2 needs python3 on PATH")

        setup = self._venv_setup()
        cache = tmp_path / "cache"
        cache.mkdir()
        env = {"XDG_CACHE_HOME": str(cache)}

        first = _bash(setup, cwd=tmp_path, env=env)
        assert first.returncode == 0, first.stderr
        site = sorted(path.name for path in (cache / "pipelex-plugins" / "synth-venv").rglob("site-packages/*"))
        assert site, "the first run installed nothing"

        second = _bash(setup, cwd=tmp_path, env=env)
        assert second.returncode == 0, f"the reuse path failed\n{second.stderr}"
        assert "venv ready:" in second.stdout
        assert sorted(path.name for path in (cache / "pipelex-plugins" / "synth-venv").rglob("site-packages/*")) == site

    def test_venv_rung_repairs_a_venv_whose_pip_bootstrap_failed(self, tmp_path: Path) -> None:
        """`python3 -m venv` leaves `bin/python` behind when ensurepip fails
        (Debian/Ubuntu without `python3-venv`), so a guard keyed on that file
        would skip creation forever and die on `-m pip` every time — with the
        documented cure, `apt install python3-venv`, unable to repair it."""
        if shutil.which("python3") is None:
            pytest.skip("rung 2 needs python3 on PATH")

        cache = tmp_path / "cache"
        venv = cache / "pipelex-plugins" / "synth-venv"
        venv.parent.mkdir(parents=True)
        broken = subprocess.run(["python3", "-m", "venv", "--without-pip", str(venv)], capture_output=True, text=True, check=False)
        assert broken.returncode == 0, broken.stderr
        assert (venv / "bin" / "python").is_file(), "the simulated half-made venv has no bin/python to trip the guard"

        repaired = _bash(self._venv_setup(), cwd=tmp_path, env={"XDG_CACHE_HOME": str(cache)})
        assert repaired.returncode == 0, f"the ladder did not repair a pip-less venv\n{repaired.stderr}"
        assert "venv ready:" in repaired.stdout

    @staticmethod
    def _venv_setup() -> str:
        return next(block for block in _skill_blocks() if block.startswith('VENV="'))
