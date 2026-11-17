"""The edit hook's verdict on the Office-editing forms the MTHDS reference teaches, held by the vendored engine's schema.

The reference the skills read, `templates/skills/shared/writing-mthds.md.j2`, teaches a `PipeStructure` that reads
an Excel Table into records with `table` and `row_field`, and a `PipeDocGen` that fills the caller's own workbook
with `template_input`, appending under `table_fill = "append"` or updating the rows it matches under
`table_fill = "update"`, with `match_on` or `match_row` and `cells`, and both reading and filling the rows typed on a
plain sheet with `sheet_range`. The MTHDS JSON Schema frozen into a `@pipelex/tools-wasm` before 0.6.2 refuses every one
of the Table fields, and one before 0.6.3 refuses `sheet_range`, so a session following the skills had its write
blocked by the plugin's own hook. These tests take the reference's examples as they are written, so a re-vendor onto
an engine that refuses them, or a reference that changes them into a form the engine refuses, fails here.
They run `templates/hooks/assets/check.mjs`, the copy every target carries byte for byte, as a Claude `PostToolUse`
`Write` on a method in a temporary directory, since the format stage writes back in place, and with the Pipelex
credentials stripped, so the validate stage never runs.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]
CHECK_MJS = REPO_ROOT / "templates" / "hooks" / "assets" / "check.mjs"
WRITING_MTHDS = REPO_ROOT / "templates" / "skills" / "shared" / "writing-mthds.md.j2"
HOOK_TIMEOUT_SECONDS = 60
# What reaches the validate stage, and so the network: removed so that only the offline stages run.
CREDENTIAL_PREFIXES = ("PIPELEX_", "CLAUDE_PLUGIN_OPTION_")
TOML_FENCE = re.compile(r"^```toml\n(.*?)^```$", re.MULTILINE | re.DOTALL)

METHOD_HEADER = """domain      = "expenses"
description = "Reading and filling the caller's expense workbook"
main_pipe   = "read_expenses"
"""

# An update by row position, in the form the reference's bullets under `update` teach: `match_row = "row"` names the
# field the `PipeStructure`'s `row_field` filled, and `cells = "overwrite"` lets a correction write a filled cell.
UPDATE_BY_ROW_POSITION = """[concept.ExpenseCorrection]
description = "A category corrected for one expense, keyed by its row's position"

[concept.ExpenseCorrection.structure]
row      = { type = "integer", description = "The row's position, copied from the row read", required = true }
category = { type = "text", description = "The corrected expense category" }

[pipe.correct_expenses]
type           = "PipeDocGen"
description    = "Write the corrected categories into the caller's expense workbook"
inputs         = { workbook = "ExpenseWorkbook", expenses = "ExpenseCorrection[]" }
output         = "ExpenseWorkbook"
format         = "xlsx"
template_input = "workbook"
table_fill     = "update"
match_row      = "row"
cells          = "overwrite"
"""


def taught_example(*, holding: tuple[str, ...]) -> str:
    """The one TOML example of the reference that holds every line of `holding`."""
    examples: list[str] = [
        example for example in TOML_FENCE.findall(WRITING_MTHDS.read_text(encoding="utf-8")) if all(line in example for line in holding)
    ]
    assert len(examples) == 1, f"expected one TOML example in {WRITING_MTHDS.name} holding {holding}, found {len(examples)}"
    example = examples[0]
    assert "{%" not in example and "{{" not in example, f"the example holding {holding} carries Jinja, so it is not the text the skills read"
    return example


@pytest.fixture(scope="module")
def spreadsheet_read() -> str:
    """The reference's `PipeStructure` example, which declares the `ExpenseWorkbook` and `ExpenseRow` the fills take."""
    return taught_example(holding=('type        = "PipeStructure"', 'table       = "Expenses"', 'row_field   = "row"'))


@pytest.fixture(scope="module")
def workbook_fills() -> str:
    """The reference's `PipeDocGen` example: an `append`, and an `update` matching on a key."""
    return taught_example(
        holding=('template_input = "workbook"', 'table_fill     = "append"', 'table_fill     = "update"', 'match_on       = ["invoice_number"]')
    )


@pytest.fixture(scope="module")
def offline_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if not key.startswith(CREDENTIAL_PREFIXES)}


def assert_the_hook_passes_silently(*, node: str, method_text: str, directory: Path, environment: dict[str, str]) -> None:
    """One PostToolUse `Write` of `method_text`, which must exit 0 having said nothing."""
    method = directory / "expenses.mthds"
    method.write_text(method_text, encoding="utf-8")
    payload = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": str(method)}})
    result = subprocess.run(
        [node, str(CHECK_MJS), "--platform=claude"],
        input=payload,
        capture_output=True,
        text=True,
        env=environment,
        timeout=HOOK_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, f"the hook exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    assert not (result.stdout.strip() or result.stderr.strip()), (
        f"the hook did not pass a form the skills teach silently\nstdout: {result.stdout}\nstderr: {result.stderr}\nmethod:\n{method_text}"
    )


@pytest.fixture(scope="module")
def sheet_range_read_and_fill() -> str:
    """The reference's two `sheet_range` examples: the `PipeStructure` reading a plain sheet, and the `PipeDocGen` appending to it."""
    sheet_read = taught_example(holding=('type        = "PipeStructure"', 'sheet_range = { sheet = "Expenses", header_row = 3 }'))
    sheet_fill = taught_example(holding=('type           = "PipeDocGen"', 'sheet_range    = { list = "expenses" }'))
    return f"{sheet_read}\n{sheet_fill}"


class TestHookOfficeEditing:
    def test_the_hook_passes_the_spreadsheet_read_silently(
        self, spreadsheet_read: str, node: str, offline_environment: dict[str, str], tmp_path: Path
    ) -> None:
        """`PipeStructure` with `table` and `row_field`."""
        assert_the_hook_passes_silently(
            node=node, method_text=f"{METHOD_HEADER}\n{spreadsheet_read}", directory=tmp_path, environment=offline_environment
        )

    def test_the_hook_passes_the_append_and_the_update_by_key_silently(
        self, spreadsheet_read: str, workbook_fills: str, node: str, offline_environment: dict[str, str], tmp_path: Path
    ) -> None:
        """`PipeDocGen` with `template_input`, under `table_fill = "append"` and under `"update"` with `match_on`."""
        assert_the_hook_passes_silently(
            node=node,
            method_text=f"{METHOD_HEADER}\n{spreadsheet_read}\n{workbook_fills}",
            directory=tmp_path,
            environment=offline_environment,
        )

    def test_the_hook_passes_the_update_by_row_position_silently(
        self, spreadsheet_read: str, node: str, offline_environment: dict[str, str], tmp_path: Path
    ) -> None:
        """`PipeDocGen` with `template_input`, under `table_fill = "update"` with `match_row` and `cells`."""
        reference = WRITING_MTHDS.read_text(encoding="utf-8")
        for taught in ('`match_row = "row"`', "`cells`", "`overwrite`"):
            assert taught in reference, f"{WRITING_MTHDS.name} no longer teaches {taught}, which this case writes"
        assert_the_hook_passes_silently(
            node=node,
            method_text=f"{METHOD_HEADER}\n{spreadsheet_read}\n{UPDATE_BY_ROW_POSITION}",
            directory=tmp_path,
            environment=offline_environment,
        )

    def test_the_hook_passes_the_sheet_range_read_and_fill_silently(
        self, spreadsheet_read: str, sheet_range_read_and_fill: str, node: str, offline_environment: dict[str, str], tmp_path: Path
    ) -> None:
        """`PipeStructure` and `PipeDocGen` with `sheet_range`, beside the Table read that declares their concepts."""
        assert_the_hook_passes_silently(
            node=node,
            method_text=f"{METHOD_HEADER}\n{spreadsheet_read}\n{sheet_range_read_and_fill}",
            directory=tmp_path,
            environment=offline_environment,
        )
