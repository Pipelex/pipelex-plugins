"""Execute the recipe blocks shipped by `pipelex-synthetic-inputs`.

The skill's know-how is prose the agent copies and adapts, which is the right
shape for content that differs every time — but prose rots silently. Its
predecessor's image recipe pointed at a bundle that no longer existed, and
nothing noticed because nothing ran it. These tests run every block.

Opt-in: `make test-recipes`, or `pytest -m recipes`. The default run deselects
them (`addopts` in pyproject.toml) because the first execution downloads
packages into uv's cache.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

pytestmark = pytest.mark.recipes

REPO_ROOT = Path(__file__).parents[2]
REFERENCES_DIR = REPO_ROOT / "skills" / "pipelex-synthetic-inputs" / "references"
RENDERED_SKILL = REPO_ROOT / "pipelex" / "skills" / "pipelex-synthetic-inputs" / "SKILL.md"

OUTPUT_DIR_PLACEHOLDER = "<output_dir>"
# A block carrying this placeholder is a template the agent fills in (the
# "Verify" snippets), not a runnable recipe — running it would open a file
# literally named "<name>.png".
TEMPLATE_PLACEHOLDER = "<name>"

MAGIC_BY_SUFFIX = {
    ".pdf": b"%PDF",
    ".png": b"\x89PNG",
    ".docx": b"PK",
    ".xlsx": b"PK",
}

BASH_BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)
HEADING = re.compile(r"^## (.+)$", re.MULTILINE)
OUT_ASSIGNMENT = re.compile(r'^OUT = "([^"]+)"', re.MULTILINE)
DECLARED_SIZE = re.compile(r"^WIDTH, HEIGHT(?:, DPI)? = (\d+), (\d+)", re.MULTILINE)
PDF_PAGE_OBJECT = re.compile(rb"/Type\s*/Page[^s]")

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


def _heading_above(text: str, position: int) -> str:
    """The nearest `##` heading before `position`, which names the recipe."""
    headings = [match for match in HEADING.finditer(text) if match.start() < position]
    return headings[-1].group(1) if headings else "(no heading)"


def _collect_recipes() -> list[RecipeBlock]:
    recipes: list[RecipeBlock] = []
    for reference in sorted(REFERENCES_DIR.glob("*.md")):
        text = reference.read_text(encoding="utf-8")
        for block in BASH_BLOCK.finditer(text):
            script = block.group(1)
            if not script.startswith("uv run") or TEMPLATE_PLACEHOLDER in script:
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


class TestRecipes:
    """Every recipe block runs and writes the file it declares, in the format
    and at the size it declares — on both rungs of the environment ladder."""

    def test_collection_found_every_reference(self) -> None:
        """A reference that stops contributing recipes — renamed, emptied, or
        with its fences broken — must fail here rather than silently shrink the
        suite to nothing."""
        assert {recipe.reference for recipe in RECIPES} == {"office.md", "pdf.md", "png.md"}

    @NEEDS_UV
    @pytest.mark.parametrize("recipe", RECIPES, ids=RECIPE_IDS)
    def test_recipe_writes_the_file_it_declares(self, recipe: RecipeBlock, tmp_path: Path) -> None:
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

    @NEEDS_UV
    @pytest.mark.parametrize("package_set", ["reportlab", "pillow --with matplotlib --with numpy", "python-docx", "openpyxl"])
    def test_preflight_resolves_every_package_set(self, package_set: str, tmp_path: Path) -> None:
        """A stale or renamed package in a `--with` list must fail here, not on
        a user's machine mid-flow."""
        result = _bash(f"uv run --quiet --with {package_set} python -c 'print(\"ok\")'", cwd=tmp_path)
        assert result.returncode == 0, f"package set '{package_set}' does not resolve\n{result.stderr}"
        assert result.stdout.strip() == "ok"

    @NEEDS_UV
    def test_skill_preflight_commands_run_as_written(self, tmp_path: Path) -> None:
        """The Environment section's own preflight commands, copied out of the
        shipped SKILL.md and run verbatim."""
        preflights = [block for block in self._skill_blocks() if block.startswith("command -v uv")]
        assert len(preflights) == 2, "expected a pdf and a png preflight in the skill's Environment section"
        for preflight in preflights:
            result = _bash(preflight, cwd=tmp_path)
            assert result.returncode == 0, f"preflight failed\n{preflight}\n{result.stderr}"
            assert "ready" in result.stdout

    def test_venv_rung_changes_only_the_runner_line(self, tmp_path: Path) -> None:
        """Rung 2, for a machine with no `uv` — deliberately not skipped when
        `uv` is present, since it is the rung a stock Python must reach.

        The skill promises that swapping the runner line is the *only*
        difference between the rungs. This creates the venv exactly as the skill
        says to, then runs a real PDF and a real PNG recipe through it with that
        one line changed and nothing else.
        """
        if shutil.which("python3") is None:
            pytest.skip("rung 2 needs python3 on PATH")

        setup = next(block for block in self._skill_blocks() if block.startswith('VENV="'))
        cache = tmp_path / "cache"
        cache.mkdir()

        created = _bash(setup, cwd=tmp_path, env={"XDG_CACHE_HOME": str(cache)})
        assert created.returncode == 0, f"the skill's venv setup failed\n{created.stderr}"
        assert "venv ready:" in created.stdout

        venv_python = cache / "pipelex-plugins" / "synth-venv" / "bin" / "python"
        assert venv_python.is_file(), "the venv landed somewhere other than the path the skill documents"

        for suffix in (".pdf", ".png"):
            recipe = next(candidate for candidate in RECIPES if candidate.output.endswith(suffix))
            body = recipe.script.split("\n", maxsplit=1)[1].replace(OUTPUT_DIR_PLACEHOLDER, str(tmp_path))
            result = _bash(f"\"{venv_python}\" << 'PYEOF'\n{body}", cwd=tmp_path)
            assert result.returncode == 0, f"{recipe.heading} failed on the venv rung\n{result.stderr}"
            assert (tmp_path / recipe.output).read_bytes().startswith(MAGIC_BY_SUFFIX[suffix])

    @staticmethod
    def _skill_blocks() -> list[str]:
        skill = RENDERED_SKILL.read_text(encoding="utf-8")
        return [block.group(1) for block in BASH_BLOCK.finditer(skill)]
