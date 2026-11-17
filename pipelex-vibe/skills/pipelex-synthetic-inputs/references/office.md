# Word, Excel and PowerPoint recipes — python-docx, openpyxl, python-pptx

Read this at step 4 of the skill when the format is `docx`, `xlsx` or `pptx`, before writing any code; each recipe ends with step 5's verify command.

Recipes for the `docx`, `xlsx` and `pptx` formats of `/pipelex-synthetic-inputs`, the first two carried over from `/pipelex-inputs` and brought into line with the other references — an `OUT` variable, directory creation, a `--no-project` runner line, and a verify step. The content they produce is the same. A host skill for the format, when one is installed, is the better tool — it knows the format's conventions — and the Python recipe is the fallback. Either way the content comes from the skill's Step 3 draft.

## Word documents (DOCX)

**If a `docx` skill is available:**

```
Use the /docx skill to create a Word document with the following content:
[Describe the document content, structure, and formatting]
Save to: <target>
```

**If not**, create it with `python-docx` (MIT). Runner line per the skill's Step 2; the package set is `python-docx`:

```bash
uv run --quiet --no-project --with python-docx python << 'PYEOF'
import os
from pathlib import Path

from docx import Document

OUT = "<target_dir>/test_document.docx"
assert "<" not in OUT and ">" not in OUT, f"OUT still holds a placeholder: {OUT}"
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
# Render beside the target and rename on success, so a crash never truncates an existing file.
PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))

doc = Document()
doc.add_heading("Test Document", 0)
doc.add_paragraph("This is synthetic test content for method testing.")
# Add more content as needed: doc.add_heading("Section", 1), doc.add_paragraph("…"), doc.add_table(rows=2, cols=3)
doc.save(PART)
os.replace(PART, OUT)
print("wrote", OUT)
PYEOF
```

Verify by reopening: `uv run --quiet --no-project --with python-docx python -c "from docx import Document; d = Document('<target>'); print([p.text for p in d.paragraphs][:5])"`.

## Spreadsheets (XLSX)

**If an `xlsx` skill is available:**

```
Use the /xlsx skill to create a spreadsheet with the following data, laid out as described:
[Describe columns, rows, and sample data. The layout is the request's `constraints` layout. `layout: plain`: plain rows with no Excel Table, on a sheet named as its `sheet`, or, for `sheet: none`, in a workbook holding that one worksheet; the header on its `header_row` under a title, or, for `header_row: none`, on the first filled row with nothing above it; and, for `totals: yes`, a totals line such as `=SUM(...)` under two data rows at least, every cell of it within the header's columns. `layout: table`: the rows formatted as an Excel Table of its `name`. `layout: named`: the rows with no Table, and a defined name (Formulas > Define Name) of its `name` over the header and the data rows, nothing under them. With no layout given: a Table]
Save to: <target>
```

A sheet holding a Table is read and filled as that Table, so a Table in a workbook a `sheet_range` takes leaves the plain-range path untested. A method taking two workbooks may need one of each.

**If not**, create it with `openpyxl` (MIT). The package set is `openpyxl`:

```bash
uv run --quiet --no-project --with openpyxl python << 'PYEOF'
import os
from pathlib import Path

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.table import Table

OUT = "<target_dir>/test_spreadsheet.xlsx"
assert "<" not in OUT and ">" not in OUT, f"OUT still holds a placeholder: {OUT}"
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
# Render beside the target and rename on success, so a crash never truncates an existing file.
PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))

# The request's `constraints` layout sets these. LAYOUT is its `layout`: "table" (also when none is given), "plain"
# or "named". plain: SHEET its `sheet` (any name for `none`: the workbook holds that one sheet), HEADER_ROW its
# `header_row` (1 for `none`, nothing above the header), TOTALS_COLUMN a numeric column's header for `totals: yes`,
# else None. table and named: NAME its `name`; a named range covers the header and the data rows, nothing under them.
LAYOUT = "table"
SHEET, HEADER_ROW, NAME = "Data", 1, "DataTable"
HEADER = ["Item", "Amount"]
ROWS = [["Paper", 12.5], ["Toner", 48.0], ["Pens", 6.2]]
TOTALS_COLUMN = "Amount"  # plain rows only: the header of the column a totals line sums, or None for no totals line

wb = Workbook()
ws = wb.active
ws.title = SHEET
if HEADER_ROW > 1:
    ws.cell(row=1, column=1, value="Expenses")  # a title above the header, only with an explicit `header_row`
for offset, values in enumerate([HEADER, *ROWS]):
    for column, value in enumerate(values, start=1):
        ws.cell(row=HEADER_ROW + offset, column=column, value=value)
last = HEADER_ROW + len(ROWS)
last_col = get_column_letter(len(HEADER))
if LAYOUT == "table":
    ws.add_table(Table(displayName=NAME, ref=f"A{HEADER_ROW}:{last_col}{last}"))
elif LAYOUT == "named":
    wb.defined_names[NAME] = DefinedName(NAME, attr_text=f"'{SHEET}'!$A${HEADER_ROW}:${last_col}${last}")
elif TOTALS_COLUMN is not None and len(ROWS) >= 2:  # a total over one data row reads as a data row
    # openpyxl stores no value for the formula, but the range rules tell a totals line by its formula text.
    total = HEADER.index(TOTALS_COLUMN) + 1
    letter = get_column_letter(total)
    ws.cell(row=last + 1, column=total, value=f"=SUM({letter}{HEADER_ROW + 1}:{letter}{last})")
    if len(HEADER) > 1:  # the label goes in another of the header's columns, never past them
        ws.cell(row=last + 1, column=1 if total > 1 else 2, value="Total")
# A second sheet, never for a `sheet_range` naming no `sheet`: wb.create_sheet("Summary")
wb.save(PART)
os.replace(PART, OUT)
print("wrote", OUT)
PYEOF
```

Verify by reopening: `uv run --quiet --no-project --with openpyxl python -c "from openpyxl import load_workbook; wb = load_workbook('<target>'); ws = wb.active; print(ws.title, ws.dimensions, list(ws.tables))"`.


## Presentations (PPTX)

**If a `pptx` skill is available:**

```
Use the /pptx skill to create a presentation with the following content:
[Describe each slide: its title, body text, any table, and any speaker notes]
Save to: <target>
```

**If not**, create it with `python-pptx` (MIT). The package set is `python-pptx`:

```bash
uv run --quiet --no-project --with python-pptx python << 'PYEOF'
import os
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

OUT = "<target_dir>/test_presentation.pptx"
assert "<" not in OUT and ">" not in OUT, f"OUT still holds a placeholder: {OUT}"
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
# Render beside the target and rename on success, so a crash never truncates an existing file.
PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))

prs = Presentation()

# Title slide (layout 0: title and subtitle).
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = "Quarterly Review"
slide.placeholders[1].text = "Northwind Supplies, second quarter"

# Body text (layout 1: title and content), one paragraph per bullet.
slide = prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text = "Highlights"
body = slide.placeholders[1].text_frame
body.text = "Revenue grew 12% over the quarter"
for bullet in ("Two new customers signed", "Churn held at 3%"):
    body.add_paragraph().text = bullet
# Speaker notes only when the brief needs them: a conversion to PDF leaves them out.
slide.notes_slide.notes_text_frame.text = "Mention that the warehouse move slipped to July."

# A simple table (layout 5: title only).
slide = prs.slides.add_slide(prs.slide_layouts[5])
slide.shapes.title.text = "Figures"
rows = [("Metric", "Q1", "Q2"), ("Revenue", "1.20M", "1.34M"), ("Customers", "40", "42")]
table = slide.shapes.add_table(len(rows), len(rows[0]), Inches(1), Inches(2), Inches(8), Inches(1.5)).table
for row_index, row in enumerate(rows):
    for column_index, value in enumerate(row):
        table.cell(row_index, column_index).text = value
# Add more slides as needed: prs.slides.add_slide(prs.slide_layouts[1])
prs.save(PART)
os.replace(PART, OUT)
print("wrote", OUT)
PYEOF
```

Verify by reopening: `uv run --quiet --no-project --with python-pptx python -c "from pptx import Presentation; p = Presentation('<target>'); print(len(p.slides), [s.shapes.title.text for s in p.slides if s.shapes.title is not None])"`.
