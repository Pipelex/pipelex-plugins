# Word and Excel recipes — python-docx, openpyxl

Recipes for the `docx` and `xlsx` formats of `/pipelex-synthetic-inputs`, carried over from `/pipelex-inputs` as they were. A host skill for the format, when one is installed, is the better tool — it knows the format's conventions — and the Python recipe is the fallback. Either way the content comes from the skill's Step 3 draft.

## Word documents (DOCX)

**If a `docx` skill is available:**

```
Use the /docx skill to create a Word document with the following content:
[Describe the document content, structure, and formatting]
Save to: <output_dir>/inputs/<filename>.docx
```

**If not**, create it with `python-docx` (MIT). Runner line per the skill's Step 2; the package set is `python-docx`:

```bash
uv run --quiet --with python-docx python << 'PYEOF'
from pathlib import Path

from docx import Document

OUT = "<output_dir>/inputs/test_document.docx"
Path(OUT).parent.mkdir(parents=True, exist_ok=True)

doc = Document()
doc.add_heading("Test Document", 0)
doc.add_paragraph("This is synthetic test content for method testing.")
# Add more content as needed: doc.add_heading("Section", 1), doc.add_paragraph("…"), doc.add_table(rows=2, cols=3)
doc.save(OUT)
print("wrote", OUT)
PYEOF
```

Verify by reopening: `uv run --quiet --with python-docx python -c "from docx import Document; d = Document('<target>'); print([p.text for p in d.paragraphs][:5])"`.

## Spreadsheets (XLSX)

**If an `xlsx` skill is available:**

```
Use the /xlsx skill to create a spreadsheet with the following data:
[Describe columns, rows, and sample data]
Save to: <output_dir>/inputs/<filename>.xlsx
```

**If not**, create it with `openpyxl` (MIT). The package set is `openpyxl`:

```bash
uv run --quiet --with openpyxl python << 'PYEOF'
from pathlib import Path

from openpyxl import Workbook

OUT = "<output_dir>/inputs/test_spreadsheet.xlsx"
Path(OUT).parent.mkdir(parents=True, exist_ok=True)

wb = Workbook()
ws = wb.active
ws.title = "Data"
ws.append(["Column1", "Column2"])
ws.append(["Value1", "Value2"])
# Add more rows as needed: ws.append([...]); a second sheet: wb.create_sheet("Summary")
wb.save(OUT)
print("wrote", OUT)
PYEOF
```

Verify by reopening: `uv run --quiet --with openpyxl python -c "from openpyxl import load_workbook; wb = load_workbook('<target>'); ws = wb.active; print(ws.title, ws.dimensions)"`.
