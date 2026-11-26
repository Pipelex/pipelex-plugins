"""Execute the recipes shipped by `pipelex-synthetic-inputs`.

The skill's know-how is prose the agent copies and adapts, which is the right
shape for content that differs every time — but prose rots silently. Its
predecessor's image recipe pointed at a bundle that no longer existed, and
nothing noticed because nothing ran it. These tests run every recipe.

Two properties matter as much as the execution itself, because a suite
parametrised over the artifact it checks can stop checking without going red:

* every recipe is pinned by name, so a deleted or unparsed one fails here
  rather than quietly shrinking the suite (`test_every_recipe_is_accounted_for`);
* the sources are the source of truth — the reference files, the skill
  *template* and the venv script, never a build artifact — so a stale
  `make build` cannot make a passing run mean nothing.

The recipes run as the skill says, in any shell: each is written to a `.py`
file and run with the command on its first line, and every command the skill
gives is run as written through the platform's own shell, `sh` on macOS and
Linux and Windows PowerShell on Windows, so a construct one of them lacks fails
here. Nothing in this suite needs bash.

Opt-in: `make test-recipes`, or `pytest -m recipes`. The default run deselects
them (`addopts` in pyproject.toml) because the first execution downloads
packages into uv's cache.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import NamedTuple, cast

import pytest

from tests.platform_shell import remove_printed_temp_dir, run_in_platform_shell

pytestmark = pytest.mark.recipes

REPO_ROOT = Path(__file__).parents[2]
SKILL_ROOT = REPO_ROOT / "skills" / "pipelex-synthetic-inputs"
REFERENCES_DIR = SKILL_ROOT / "references"
# The template, not the render: `make test-recipes` does not depend on `make build`,
# so reading a target directory would let this suite certify a stale copy. The
# blocks it reads carry no Jinja, which `test_skill_blocks_carry_no_jinja` pins.
SKILL_TEMPLATE = REPO_ROOT / "templates" / "skills" / "pipelex-synthetic-inputs" / "SKILL.md.j2"
# The venv rung, read when `uv` is absent: its blocks start the venv script, which
# the venv tests below create, reuse and repair; they are not recipes, so the recipe
# collectors skip this file.
VENV_REFERENCE = REFERENCES_DIR / "venv.md"
VENV_SCRIPT = SKILL_ROOT / "scripts" / "synth_venv.py"
VENV_SCRIPT_PLACEHOLDER = "<the script's path from step 2>"

OUTPUT_DIR_PLACEHOLDER = "<target_dir>"
RECIPE_FILE_PLACEHOLDER = '"<file>.py"'
# A command block carrying this placeholder is a template the agent fills in (the
# "Verify" snippets), not a runnable recipe — running it would open a file
# literally named "<name>.png".
TEMPLATE_PLACEHOLDER = "<name>"

# Every recipe the references ship, by the heading that names it. Pinned as an
# independent source: the parametrised tests below are built from the files
# themselves, so without this set a recipe could vanish — deleted, its fence
# retyped, its first line reworded — and the suite would just get smaller.
EXPECTED_RECIPES = {
    ("office.md", "Word documents (DOCX)"),
    ("office.md", "Spreadsheets (XLSX)"),
    ("office.md", "Presentations (PPTX)"),
    ("pdf.md", "Basic PDF (canvas)"),
    ("pdf.md", "Multi-page PDF (Platypus)"),
    ("pdf.md", "Table report (Platypus)"),
    ("pdf.md", "Results table (Platypus)"),
    ("pdf.md", "Line-item document (composed)"),
    ("png.md", "Chart (matplotlib)"),
    ("png.md", "Diagram (Pillow)"),
    ("png.md", "Scanned document (Pillow)"),
    ("png.md", "Handwritten marks (Pillow)"),
    ("png.md", "App screenshot (Pillow)"),
}

MAGIC_BY_SUFFIX = {
    ".pdf": b"%PDF",
    ".png": b"\x89PNG",
    ".docx": b"PK",
    ".xlsx": b"PK",
    ".pptx": b"PK",
}

# `PK` is two bytes any zip satisfies, including one holding no document at all.
# The Office formats get the same depth of check as the others: name the part
# that makes the package a document.
REQUIRED_ZIP_MEMBER = {".docx": "word/document.xml", ".xlsx": "xl/workbook.xml", ".pptx": "ppt/presentation.xml"}

PYTHON_BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)
# The blocks of commands the skill gives, written for any shell.
COMMAND_BLOCK = re.compile(r"```shell\n(.*?)```", re.DOTALL)
# A recipe's first line: the command that runs it on the `uv` rung.
RECIPE_COMMAND = re.compile(r'^# (uv run .+ "<file>\.py")$')
HEADING = re.compile(r"^## (.+)$", re.MULTILINE)
OUT_ASSIGNMENT = re.compile(r'^OUT = r"([^"]+)"', re.MULTILINE)
DECLARED_SIZE = re.compile(r"^WIDTH, HEIGHT(?:, DPI)? = (\d+), (\d+)", re.MULTILINE)
PDF_PAGE_OBJECT = re.compile(rb"/Type\s*/Page[^s]")
WITH_PACKAGE = re.compile(r"--with (\S+)")
PACKAGE_SETS_LINE = re.compile(r"^\*\*Package sets by format:\*\* (.+)$", re.MULTILINE)
PACKAGE_SET_ENTRY = re.compile(r"`(\w+)` → `([^`]+)`")
UV_RUN = re.compile(r"uv run(?P<arguments>[^`\n]*)")
# The interpreter every runner line starts: isolated from the project and PYTHON* variables, printing UTF-8.
ISOLATED_PYTHON = re.compile(r"\bpython -I -X utf8\b")
# Text no Windows ANSI code page holds whole, which a recipe may print: a name, an arrow, a check mark.
NOT_IN_A_CODE_PAGE = "Łódź → 東京 ✓"
JINJA = re.compile(r"\{[{%]")
# Constructs one of the shells the skill must run in lacks: a heredoc, a `&&` or `||`
# chain (Windows PowerShell 5.1 has neither), `command -v`, a POSIX parameter default,
# a redirection to /dev/null, and the POSIX tools the skill once called.
POSIX_ONLY = re.compile(r"<<|&&|\|\||command -v|\$\{|/dev/null|\bmktemp\b|\brm -f\b|\bhead -c\b|\bwc -c\b")

UV_MISSING = shutil.which("uv") is None
NEEDS_UV = pytest.mark.skipif(UV_MISSING, reason="the uv rung of the environment ladder needs uv on PATH")


class RecipeBlock(NamedTuple):
    """One runnable recipe extracted from a reference file."""

    reference: str
    heading: str
    script: str
    command: str
    output: str
    width: int | None
    height: int | None

    @property
    def packages(self) -> frozenset[str]:
        """The `--with` set of this recipe's command on the `uv` rung."""
        return frozenset(WITH_PACKAGE.findall(self.command))


def _heading_above(text: str, position: int) -> str:
    """The nearest `##` heading before `position`, which names the recipe."""
    headings = [match for match in HEADING.finditer(text) if match.start() < position]
    return headings[-1].group(1) if headings else "(no heading)"


def _recipe_references() -> list[Path]:
    """Every reference but the venv rung's, whose blocks set up the environment."""
    return [reference for reference in sorted(REFERENCES_DIR.glob("*.md")) if reference != VENV_REFERENCE]


def _collect_recipes() -> list[RecipeBlock]:
    recipes: list[RecipeBlock] = []
    for reference in _recipe_references():
        text = reference.read_text(encoding="utf-8")
        for block in PYTHON_BLOCK.finditer(text):
            script = block.group(1)
            command = RECIPE_COMMAND.match(script.split("\n", maxsplit=1)[0])
            if command is None:
                continue
            out = OUT_ASSIGNMENT.search(script)
            assert out is not None, f'{reference.name}: a recipe has no `OUT = r"…"` line to check'
            size = DECLARED_SIZE.search(script)
            recipes.append(
                RecipeBlock(
                    reference=reference.name,
                    heading=_heading_above(text, block.start()),
                    script=script,
                    command=command.group(1),
                    output=out.group(1).replace(f"{OUTPUT_DIR_PLACEHOLDER}/", ""),
                    width=int(size.group(1)) if size else None,
                    height=int(size.group(2)) if size else None,
                )
            )
    return recipes


RECIPES = _collect_recipes()
RECIPE_IDS = [f"{recipe.reference}:{recipe.heading}" for recipe in RECIPES]
# One entry per distinct `--with` set the shipped recipes actually use, derived
# from their commands rather than restated here — a renamed package in a
# reference must fail the preflight test, which is what that test claims to do.
PACKAGE_SETS = sorted({recipe.packages for recipe in RECIPES}, key=sorted)
PACKAGE_SET_IDS = [" ".join(sorted(packages)) for packages in PACKAGE_SETS]


def _png_size(data: bytes) -> tuple[int, int]:
    """Width and height straight out of the IHDR chunk — no Pillow needed."""
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def _shell(command: str, *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run `command` as written through the platform's own shell, never bash, which the skill may not assume."""
    return run_in_platform_shell(command, cwd=cwd, env=env)


def _write_recipe(script: str, *, tmp_path: Path, name: str = "recipe.py") -> Path:
    """Write a recipe as the agent's file tool does, with `<target_dir>` set to a real directory. The path keeps
    its native separators, so on Windows the recipe's raw `OUT` string is what holds its backslashes."""
    recipe_file = tmp_path / name
    recipe_file.write_text(script.replace(OUTPUT_DIR_PLACEHOLDER, str(tmp_path)), encoding="utf-8")
    return recipe_file


def _run_recipe(recipe: RecipeBlock, script: str, *, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Run a recipe on the `uv` rung exactly as its first line says."""
    recipe_file = _write_recipe(script, tmp_path=tmp_path)
    return _shell(recipe.command.replace(RECIPE_FILE_PLACEHOLDER, f'"{recipe_file}"'), cwd=tmp_path)


def _python3_on_path(shim_dir: Path) -> str:
    """A PATH whose `python3` is this interpreter, ahead of whatever `python3` the machine has, so the venv is built
    by the Python the suite runs on: a `sh` script on macOS and Linux, a `.cmd` file on Windows, which PowerShell
    finds through PATHEXT. Either passes its arguments on untouched, as a user's own `python3` takes them."""
    shim_dir.mkdir(exist_ok=True)
    if os.name == "nt":
        (shim_dir / "python3.cmd").write_text(f'@"{sys.executable}" %*\n', encoding="utf-8")
    else:
        shim = shim_dir / "python3"
        shim.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n', encoding="utf-8")
        shim.chmod(0o755)
    return f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def _venv_command(block: str, *, arguments: str = "") -> str:
    """A venv.md block as the agent fills it: the script's path in its placeholder, and what it runs after it."""
    command = block.strip().replace(VENV_SCRIPT_PLACEHOLDER, str(VENV_SCRIPT))
    return f"{command} {arguments}" if arguments else command


def _venv_script(command: str, *, cwd: Path, cache: Path) -> subprocess.CompletedProcess[str]:
    """Run a venv.md command as a user's shell runs it, `python3 "<script>" …` through `sh` or Windows PowerShell,
    with the venv under `cache`."""
    path = _python3_on_path(cache.parent / "python3-shim")
    return _shell(command, cwd=cwd, env={"XDG_CACHE_HOME": str(cache), "PATH": path})


def _venv_start() -> str:
    """venv.md's first block, the script started bare, filled in."""
    return _venv_command(_venv_blocks()[0])


def _venv_python(cache: Path) -> Path:
    venv = cache / "pipelex-plugins" / "synth-venv"
    return venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"


def _skill_blocks() -> list[str]:
    skill = SKILL_TEMPLATE.read_text(encoding="utf-8")
    return [block.group(1) for block in COMMAND_BLOCK.finditer(skill)]


def _venv_blocks() -> list[str]:
    return [block.group(1) for block in COMMAND_BLOCK.finditer(VENV_REFERENCE.read_text(encoding="utf-8"))]


def _script_packages() -> set[str]:
    """The allowlist the venv script installs, read from its source without running it."""
    tree = ast.parse(VENV_SCRIPT.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "PACKAGES" for target in node.targets):
            value: object = ast.literal_eval(node.value)
            assert isinstance(value, tuple), f"{VENV_SCRIPT.name}'s PACKAGES is not a tuple"
            return {str(package) for package in cast("tuple[object, ...]", value)}
    pytest.fail(f"{VENV_SCRIPT.name} no longer declares PACKAGES")


class TestRecipes:
    """Every recipe runs and writes the file it declares, in the format and at
    the size it declares — on both rungs of the environment ladder."""

    def test_every_recipe_is_accounted_for(self) -> None:
        """The suite cannot shrink without going red.

        Pinning the (file, heading) pairs catches a recipe that was deleted, and
        catches one that stopped being collected — a fence retyped, its first
        line reworded — which the collector would otherwise skip in silence.
        """
        assert {(recipe.reference, recipe.heading) for recipe in RECIPES} == EXPECTED_RECIPES

    def test_every_block_is_a_recipe_a_command_or_the_preamble(self) -> None:
        """No block may fall between the categories unnoticed: a ```python block is a recipe, opening with its
        command, or the PNG preamble shown for reference; a command block is for any shell, and a ```bash
        block, which a Windows shell cannot run, is gone."""
        for reference in [*_recipe_references(), VENV_REFERENCE]:
            text = reference.read_text(encoding="utf-8")
            assert "```bash" not in text and "```sh\n" not in text, f"{reference.name} gives a command for a POSIX shell alone"
            for block in PYTHON_BLOCK.finditer(text):
                script = block.group(1)
                if RECIPE_COMMAND.match(script.split("\n", maxsplit=1)[0]) or script.startswith("_FONTS = {}"):
                    continue
                pytest.fail(
                    f"{reference.name}: a ```python block under '{_heading_above(text, block.start())}' is neither a recipe "
                    f"opening with its `# uv run … <file>.py` command nor the PNG preamble.\n{script}"
                )
        assert "```bash" not in SKILL_TEMPLATE.read_text(encoding="utf-8")

    def test_no_command_needs_a_posix_shell(self) -> None:
        """Every command the skill and its references give runs in sh, bash and both PowerShells, so none may use a
        construct one of them lacks — Windows PowerShell 5.1 has no `&&` or `||` — and no recipe is a heredoc."""
        offenders: list[str] = []
        for path in [SKILL_TEMPLATE, *sorted(REFERENCES_DIR.glob("*.md"))]:
            text = path.read_text(encoding="utf-8")
            commands = [block.group(1) for block in COMMAND_BLOCK.finditer(text)]
            commands += [match.group(0) for match in re.finditer(r"`(?:uv run|<runner>|python3 \")[^`]*`", text)]
            commands += [script.split("\n", maxsplit=1)[0] for script in (block.group(1) for block in PYTHON_BLOCK.finditer(text))]
            for command in commands:
                found = POSIX_ONLY.search(command)
                if found:
                    offenders.append(f"{path.name}: `{found.group(0)}` in {command.strip()[:120]}")
        assert not offenders, "a command needs a POSIX shell:\n" + "\n".join(offenders)

    @NEEDS_UV
    @pytest.mark.parametrize("recipe", RECIPES, ids=RECIPE_IDS)
    def test_recipe_writes_the_file_it_declares(self, recipe: RecipeBlock, tmp_path: Path) -> None:
        # A recipe must stay inside the output directory it was given. An absolute
        # or climbing OUT would make the assertions below inspect a file on the
        # real filesystem while the recipe wrote somewhere else entirely.
        assert not Path(recipe.output).is_absolute(), f"{recipe.heading}: OUT escapes <target_dir> — {recipe.output}"
        assert ".." not in Path(recipe.output).parts, f"{recipe.heading}: OUT climbs out of <target_dir> — {recipe.output}"

        result = _run_recipe(recipe, recipe.script, tmp_path=tmp_path)
        assert result.returncode == 0, f"{recipe.reference}:{recipe.heading} failed\n{result.stderr}"

        written = tmp_path / recipe.output
        assert written.is_file(), f"{recipe.reference}:{recipe.heading} printed success but wrote no {recipe.output}"
        data = written.read_bytes()
        assert len(data) > 512, f"{recipe.output} is {len(data)} bytes — too small to be a real file"
        leftovers = sorted(path.name for path in written.parent.iterdir() if ".part" in path.name)
        assert not leftovers, f"{recipe.heading} left its partial file behind: {leftovers}"

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
    @pytest.mark.parametrize("reference", ["pdf.md", "png.md"])
    def test_verify_command_runs_as_written(self, reference: str, tmp_path: Path) -> None:
        """A reference's verify block, through the platform's shell, on a file its first recipe wrote."""
        recipe = next(candidate for candidate in RECIPES if candidate.reference == reference)
        rendered = _run_recipe(recipe, recipe.script, tmp_path=tmp_path)
        assert rendered.returncode == 0, rendered.stderr
        text = (REFERENCES_DIR / reference).read_text(encoding="utf-8").split("## Verify", 1)[1]
        (verify,) = [block.group(1) for block in COMMAND_BLOCK.finditer(text)]
        target = tmp_path / recipe.output
        result = _shell(verify.replace(f"{OUTPUT_DIR_PLACEHOLDER}/{TEMPLATE_PLACEHOLDER}{target.suffix}", str(target)), cwd=tmp_path)
        assert result.returncode == 0, f"{reference}'s verify command failed\n{result.stderr}"
        expected = "b'%PDF-" if reference == "pdf.md" else "PNG"
        assert expected in result.stdout, result.stdout

    @NEEDS_UV
    def test_office_verify_commands_run_as_written(self, tmp_path: Path) -> None:
        """The Office verify commands take the path as an argument, never inside the Python source, where a Windows
        path's backslashes would be escapes."""
        office = (REFERENCES_DIR / "office.md").read_text(encoding="utf-8")
        verifies = re.findall(r"Verify by reopening: `([^`]+)`", office)
        assert len(verifies) == 3, f"expected a verify command per Office format, found {len(verifies)}"
        for recipe in [candidate for candidate in RECIPES if candidate.reference == "office.md"]:
            rendered = _run_recipe(recipe, recipe.script, tmp_path=tmp_path)
            assert rendered.returncode == 0, rendered.stderr
            (verify,) = [command for command in verifies if WITH_PACKAGE.findall(command) == sorted(recipe.packages)]
            assert verify.endswith('"<target>"'), f"the {recipe.heading} verify command does not take the path as an argument"
            result = _shell(verify.replace("<target>", str(tmp_path / recipe.output)), cwd=tmp_path)
            assert result.returncode == 0, f"the {recipe.heading} verify command failed\n{result.stderr}"

    @classmethod
    def _run_plain_spreadsheet_recipe(
        cls, *, substitutions: tuple[tuple[str, str], ...], tmp_path: Path, layout: str = "plain"
    ) -> dict[str, list[object]]:
        """Run the spreadsheet recipe on its `layout` path, plain or named, with `substitutions`, and read the
        workbook back: its sheet names, its defined names, the Tables of its active sheet and that sheet's rows."""
        (recipe,) = [recipe for recipe in RECIPES if recipe.heading == "Spreadsheets (XLSX)"]
        script = recipe.script
        for constant, plain in (('LAYOUT = "table"', f'LAYOUT = "{layout}"'), *substitutions):
            assert script.count(constant) == 1, f"the spreadsheet recipe no longer sets `{constant}`, which this test substitutes"
            script = script.replace(constant, plain)
        result = _run_recipe(recipe, script, tmp_path=tmp_path)
        assert result.returncode == 0, f"the plain spreadsheet recipe failed\n{result.stderr}"
        inspect = (
            "import json, sys; from openpyxl import load_workbook; wb = load_workbook(sys.argv[1]); ws = wb.active; "
            "print(json.dumps({'sheets': wb.sheetnames, 'tables': list(ws.tables), "
            "'names': [[name, defined.attr_text] for name, defined in wb.defined_names.items()], "
            "'rows': [[cell.value for cell in row] for row in ws.iter_rows()]}))"
        )
        inspected = subprocess.run(
            ["uv", "run", "--quiet", "--no-project", "--with", "openpyxl", "python", "-c", inspect, str(tmp_path / recipe.output)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert inspected.returncode == 0, inspected.stderr
        workbook: dict[str, list[object]] = json.loads(inspected.stdout)
        return workbook

    @NEEDS_UV
    def test_spreadsheet_recipe_plain_path_lays_rows_out_for_a_sheet_range(self, tmp_path: Path) -> None:
        """The default run takes the Table path; a method using `sheet_range` takes the plain one, which a Table would
        hide, since a sheet holding a Table is read as that Table. Run with `LAYOUT = "plain"` and the header on row 3,
        the amount moved to the third column, so the totals line must follow `HEADER` rather than sit on column B."""
        workbook = self._run_plain_spreadsheet_recipe(
            substitutions=(
                ('SHEET, HEADER_ROW, NAME = "Data", 1,', 'SHEET, HEADER_ROW, NAME = "Feuil1", 3,'),
                ('HEADER = ["Item", "Amount"]', 'HEADER = ["Item", "Category", "Amount"]'),
                ("TOTALS_COLUMN = None", 'TOTALS_COLUMN = "Amount"'),
                (
                    'ROWS = [["Paper", 12.5], ["Toner", 48.0], ["Pens", 6.2]]',
                    'ROWS = [["Paper", "Office", 12.5], ["Toner", "Office", 48.0], ["Pens", "Office", 6.2]]',
                ),
            ),
            tmp_path=tmp_path,
        )
        rows = workbook["rows"]
        assert workbook["sheets"] == ["Feuil1"], f"a step naming its sheet reads it among: {workbook['sheets']}"
        assert workbook["tables"] == [], f"the plain path left a Table: {workbook['tables']}"
        assert rows[0] == ["Expenses", None, None], "no title row above a header on row 3"
        assert rows[1] == [None, None, None], "row 2 should stand empty between the title and the header"
        assert rows[2] == ["Item", "Category", "Amount"], f"the header is not on row 3: {rows[2]}"
        last_data_row = len(rows) - 1  # the sheet row of the last data row, the totals line being the last row
        assert rows[-1] == ["Total", None, f"=SUM(C4:C{last_data_row})"], f"no totals line under the amount column: {rows[-1]}"
        assert last_data_row - 3 >= 2, "a totals line needs two data rows above it"

    @NEEDS_UV
    def test_spreadsheet_recipe_plain_path_without_header_row_or_label_column(self, tmp_path: Path) -> None:
        """A `sheet_range` naming no `header_row` reads the first filled row as the header, so nothing stands above
        it, and one naming no `sheet` needs a workbook of one worksheet. With the amount as the header's only column,
        the totals line holds the formula alone: a label in the column beside it would be a column with no header."""
        workbook = self._run_plain_spreadsheet_recipe(
            substitutions=(
                ('HEADER = ["Item", "Amount"]', 'HEADER = ["Amount"]'),
                ("TOTALS_COLUMN = None", 'TOTALS_COLUMN = "Amount"'),
                ('ROWS = [["Paper", 12.5], ["Toner", 48.0], ["Pens", 6.2]]', "ROWS = [[12.5], [48.0], [6.2]]"),
            ),
            tmp_path=tmp_path,
        )
        assert len(workbook["sheets"]) == 1, f"a step naming no sheet needs one worksheet: {workbook['sheets']}"
        assert workbook["tables"] == []
        assert workbook["rows"] == [["Amount"], [12.5], [48], [6.2], ["=SUM(A2:A4)"]], workbook["rows"]

    @NEEDS_UV
    def test_spreadsheet_recipe_plain_path_writes_no_totals_line_unless_asked(self, tmp_path: Path) -> None:
        """Only `totals: yes` sets `TOTALS_COLUMN`, so a plain request without it ends on its data rows, and a header
        holding no `Amount` column is never looked up."""
        workbook = self._run_plain_spreadsheet_recipe(
            substitutions=(('HEADER = ["Item", "Amount"]', 'HEADER = ["Item", "Price"]'),),
            tmp_path=tmp_path,
        )
        assert workbook["rows"] == [["Item", "Price"], ["Paper", 12.5], ["Toner", 48], ["Pens", 6.2]], workbook["rows"]

    @NEEDS_UV
    def test_spreadsheet_recipe_named_path_defines_a_name_over_header_and_data(self, tmp_path: Path) -> None:
        """A `table` or a list filled by name reaches a named range too, and a Table in its place would test the
        Table path while the user's named range went untested: the named path writes plain rows and a defined name
        over the header and the data rows, which the engine reads as one rectangle whose first row is the header."""
        workbook = self._run_plain_spreadsheet_recipe(
            substitutions=(('SHEET, HEADER_ROW, NAME = "Data", 1, "DataTable"', 'SHEET, HEADER_ROW, NAME = "Data", 1, "Expenses"'),),
            tmp_path=tmp_path,
            layout="named",
        )
        assert workbook["tables"] == [], f"the named path left a Table: {workbook['tables']}"
        assert workbook["names"] == [["Expenses", "'Data'!$A$1:$B$4"]], workbook["names"]
        assert workbook["rows"] == [["Item", "Amount"], ["Paper", 12.5], ["Toner", 48], ["Pens", 6.2]], "nothing lies under a named range"

    @NEEDS_UV
    def test_spreadsheet_recipe_table_path_needs_no_amount_column(self, tmp_path: Path) -> None:
        """The totals column is looked up on the plain path alone, so a Table's header need not hold `Amount`."""
        (recipe,) = [recipe for recipe in RECIPES if recipe.heading == "Spreadsheets (XLSX)"]
        constant = 'HEADER = ["Item", "Amount"]'
        assert recipe.script.count(constant) == 1
        result = _run_recipe(recipe, recipe.script.replace(constant, 'HEADER = ["Item", "Price"]'), tmp_path=tmp_path)
        assert result.returncode == 0, f"the Table recipe failed without an Amount column\n{result.stderr}"

    @NEEDS_UV
    def test_a_failed_render_leaves_neither_target_nor_partial_file(self, tmp_path: Path) -> None:
        """Step 4 promises a failure leaves nothing behind, and the recipes keep it: each deletes its partial file
        when the save fails, and moves it onto `target` only on success. A save made to fail proves both."""
        for recipe in RECIPES:
            save = re.search(r"^    (\S.*\(PART[,)].*)$", recipe.script, re.MULTILINE)
            assert save is not None, f"{recipe.heading}: no save of PART inside a try"
            failing = recipe.script.replace(save.group(0), f"    open(PART, 'wb').write(b'half'); raise RuntimeError('mid-save'); {save.group(1)}")
            workdir = tmp_path / re.sub(r"\W+", "-", recipe.heading)
            workdir.mkdir()
            result = _run_recipe(recipe, failing, tmp_path=workdir)
            assert result.returncode != 0, f"{recipe.heading}: the sabotaged save did not fail"
            assert "mid-save" in result.stderr, result.stderr
            assert sorted(path.name for path in (workdir / recipe.output).parent.iterdir()) == ["recipe.py"], (
                f"{recipe.heading} left a file behind after a failed save"
            )

    @NEEDS_UV
    @pytest.mark.parametrize("package_set", PACKAGE_SETS, ids=PACKAGE_SET_IDS)
    def test_preflight_resolves_every_package_set(self, package_set: frozenset[str], tmp_path: Path) -> None:
        """A stale or renamed package in a `--with` list must fail here, not on
        a user's machine mid-flow. The sets come from the shipped recipe commands,
        so a package renamed in a reference reaches this test. The preflight is the
        skill's own, with the set swapped in, and it must print a fresh directory."""
        (preflight,) = [block for block in _skill_blocks() if block.startswith("uv run")]
        withs = " ".join(f"--with {package}" for package in sorted(package_set))
        result = _shell(preflight.replace("--with reportlab", withs), cwd=tmp_path)
        assert result.returncode == 0, f"package set '{withs}' does not resolve\n{result.stderr}"
        printed = Path(result.stdout.strip())
        assert printed.is_dir(), f"the preflight printed no temporary directory: {result.stdout!r}"
        remove_printed_temp_dir(printed, prefix=tempfile.template)

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
                    if not arguments.strip() or arguments.strip().startswith("…"):
                        continue  # prose naming the command, not running it
                    invocations += 1
                    if "--no-project" not in arguments:
                        offenders.append(f"{path.name}:{number}: {line.strip()}")
        assert invocations, "no `uv run` invocation found — the extractor stopped seeing the recipe commands"
        assert not offenders, "`uv run` without --no-project syncs the user's project:\n" + "\n".join(offenders)

    def test_every_runner_line_is_isolated_and_prints_utf8(self) -> None:
        """A recipe runs in the user's project, where a `reportlab.py` would shadow the package, and on Windows a
        piped stdout encodes in the ANSI code page, where printing a name outside it fails after a good render. So
        every `uv run` the skill gives starts `python -I -X utf8`, the same flags the venv rung's hand-over adds."""
        offenders: list[str] = []
        invocations = 0
        for path in [SKILL_TEMPLATE, *sorted(REFERENCES_DIR.glob("*.md"))]:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                for match in UV_RUN.finditer(line):
                    arguments = match.group("arguments")
                    if not arguments.strip() or arguments.strip().startswith("…"):
                        continue  # prose naming the command, not running it
                    invocations += 1
                    if not ISOLATED_PYTHON.search(arguments):
                        offenders.append(f"{path.name}:{number}: {line.strip()[:160]}")
        assert invocations, "no `uv run` invocation found — the extractor stopped seeing the recipe commands"
        assert not offenders, "`uv run … python` without `-I -X utf8`:\n" + "\n".join(offenders)

    @NEEDS_UV
    def test_the_uv_runner_ignores_a_shadowing_module_and_prints_utf8(self, tmp_path: Path) -> None:
        """Rung 1 as the recipes give it, in a directory holding a `reportlab.py` that exits 5 when imported: the
        recipe still renders, and a recipe printing text outside every code page exits 0 under
        `PYTHONIOENCODING=cp1252`, which stands in for a Windows code page where there is none."""
        recipe = next(candidate for candidate in RECIPES if candidate.reference == "pdf.md")
        marker = tmp_path / "shadow-ran"
        (tmp_path / "reportlab.py").write_text(f"open({str(marker)!r}, 'w').write('ran')\nraise SystemExit(5)\n", encoding="utf-8")
        rendered = _run_recipe(recipe, recipe.script, tmp_path=tmp_path)
        assert rendered.returncode == 0, rendered.stderr
        assert not marker.exists(), "the recipe imported the project's reportlab.py"

        printing = _write_recipe(f"print({NOT_IN_A_CODE_PAGE!r})\n", tmp_path=tmp_path, name="prints.py")
        command = recipe.command.replace(RECIPE_FILE_PLACEHOLDER, f'"{printing}"')
        result = _shell(command, cwd=tmp_path, env={"PYTHONIOENCODING": "cp1252"})
        assert result.returncode == 0, f"printing outside the code page failed on rung 1\n{result.stderr}"
        if os.name != "nt":
            assert result.stdout.strip() == NOT_IN_A_CODE_PAGE  # PowerShell re-encodes what passes through it

    def test_package_sets_stay_inside_the_documented_allowlist(self) -> None:
        """The recipe commands may not reach for a package the skill's Step 2 does
        not declare — the allowlist is a licence decision, not a convenience."""
        skill = SKILL_TEMPLATE.read_text(encoding="utf-8")
        sets_line = PACKAGE_SETS_LINE.search(skill)
        assert sets_line is not None, "Step 2 no longer states its package sets by format"

        by_format = {fmt: set(packages.split()) for fmt, packages in PACKAGE_SET_ENTRY.findall(sets_line.group(1))}
        assert set(by_format) == {"pdf", "png", "docx", "xlsx", "pptx"}, f"the package-set mapping no longer covers every format: {sorted(by_format)}"

        documented = {package for packages in by_format.values() for package in packages}
        used = {package for recipe in RECIPES for package in recipe.packages}
        assert used <= documented, f"recipes use packages Step 2 never declares: {sorted(used - documented)}"

        # Rung 2 fills one venv with the whole allowlist, so a package added to
        # Step 2 and not to the script is a format that works only on uv.
        assert _script_packages() == documented, f"the venv script installs {sorted(_script_packages())}, Step 2 declares {sorted(documented)}"

    def test_skill_blocks_carry_no_jinja(self) -> None:
        """This suite reads the template rather than a render, which is only
        safe while the Environment section's blocks are plain commands."""
        for block in _skill_blocks():
            assert not JINJA.search(block), f"a skill command block now carries Jinja and cannot be run as written:\n{block}"

    def test_the_venv_reference_starts_the_script_and_nothing_else(self) -> None:
        """venv.md's blocks are the script started by its launcher, bare and with the temporary-directory command;
        the procedure itself is the script's, so no block may spell a step of it again."""
        blocks = _venv_blocks()
        assert len(blocks) == 2, f"{VENV_REFERENCE.name} must hold the script's two calls; found {len(blocks)}"
        for block in blocks:
            assert block.startswith(f'python3 "{VENV_SCRIPT_PLACEHOLDER}"'), f"{VENV_REFERENCE.name}'s block does not start the script:\n{block}"

    def test_venv_rung_changes_only_the_runner(self, tmp_path: Path) -> None:
        """Rung 2, for a machine with no `uv` — deliberately not skipped when
        `uv` is present, since it is the rung a stock Python must reach.

        The skill promises that the runner is the *only* difference between the
        rungs. This builds the venv with the script, as venv.md says, then runs
        one recipe per output format through the script, the file unchanged.
        """
        cache = tmp_path / "cache"
        cache.mkdir()
        created = _venv_script(_venv_start(), cwd=tmp_path, cache=cache)
        assert created.returncode == 0, f"the venv script failed\n{created.stderr}"
        printed = Path(created.stdout.strip())
        assert printed == _venv_python(cache).absolute(), f"the script printed {printed}, not the venv's interpreter"
        assert printed.is_file(), "the venv landed somewhere other than the path the skill documents"

        (_, workdir_block) = _venv_blocks()
        workdir = _venv_script(_venv_command(workdir_block), cwd=tmp_path, cache=cache)
        assert workdir.returncode == 0, workdir.stderr
        made = Path(workdir.stdout.strip())
        assert made.is_dir(), f"the temporary-directory command printed {workdir.stdout!r}"
        remove_printed_temp_dir(made, prefix=tempfile.template)

        # Rung 2 installs the whole allowlist, so every format it covers must run, each recipe file started as
        # step 4 says, its path quoted after the runner.
        for suffix in sorted(MAGIC_BY_SUFFIX):
            recipe = next(candidate for candidate in RECIPES if candidate.output.endswith(suffix))
            recipe_file = _write_recipe(recipe.script, tmp_path=tmp_path, name=f"recipe{suffix.replace('.', '_')}.py")
            result = _venv_script(_venv_command(_venv_blocks()[0], arguments=f'"{recipe_file}"'), cwd=tmp_path, cache=cache)
            assert result.returncode == 0, f"{recipe.heading} failed on the venv rung\n{result.stderr}"
            assert (tmp_path / recipe.output).read_bytes().startswith(MAGIC_BY_SUFFIX[suffix])

        # The hand-over prints UTF-8 whatever the code page, `PYTHONIOENCODING=cp1252` standing in for one.
        printing = _write_recipe(f"print({NOT_IN_A_CODE_PAGE!r})\n", tmp_path=tmp_path, name="prints.py")
        shell_env = {"XDG_CACHE_HOME": str(cache), "PATH": _python3_on_path(cache.parent / "python3-shim"), "PYTHONIOENCODING": "cp1252"}
        printed_text = _shell(_venv_command(_venv_blocks()[0], arguments=f'"{printing}"'), cwd=tmp_path, env=shell_env)
        assert printed_text.returncode == 0, f"printing outside the code page failed on the venv rung\n{printed_text.stderr}"

    def test_venv_rung_is_created_once_and_reused(self, tmp_path: Path) -> None:
        """ "Create a venv this skill owns, once … and reuse it on every later
        invocation" — a regression that rebuilt or reinstalled on every call
        would be a slow, network-touching surprise, and nothing else would
        notice."""
        cache = tmp_path / "cache"
        cache.mkdir()
        venv = cache / "pipelex-plugins" / "synth-venv"

        first = _venv_script(_venv_start(), cwd=tmp_path, cache=cache)
        assert first.returncode == 0, first.stderr
        site = sorted(path.name for path in venv.rglob("site-packages/*"))
        assert site, "the first run installed nothing"

        second = _venv_script(_venv_start(), cwd=tmp_path, cache=cache)
        assert second.returncode == 0, f"the reuse path failed\n{second.stderr}"
        assert second.stderr == "", f"the reuse path built or installed again:\n{second.stderr}"
        assert sorted(path.name for path in venv.rglob("site-packages/*")) == site

    def test_venv_rung_repairs_a_venv_whose_pip_bootstrap_failed(self, tmp_path: Path) -> None:
        """`python3 -m venv` leaves the interpreter behind when ensurepip fails
        (Debian/Ubuntu without `python3-venv`), so a guard keyed on that file
        would skip creation forever and die on `-m pip` every time — with the
        documented cure, `apt install python3-venv`, unable to repair it."""
        cache = tmp_path / "cache"
        venv = cache / "pipelex-plugins" / "synth-venv"
        venv.parent.mkdir(parents=True)
        broken = subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], capture_output=True, text=True, check=False)
        assert broken.returncode == 0, broken.stderr
        assert _venv_python(cache).is_file(), "the simulated half-made venv has no interpreter to trip the guard"

        repaired = _venv_script(_venv_start(), cwd=tmp_path, cache=cache)
        assert repaired.returncode == 0, f"the ladder did not repair a pip-less venv\n{repaired.stderr}"
        assert Path(repaired.stdout.strip()) == _venv_python(cache).absolute()
