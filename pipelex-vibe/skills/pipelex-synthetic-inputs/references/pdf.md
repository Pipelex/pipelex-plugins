# PDF recipes — reportlab

Recipes for the `pdf` format of `/pipelex-synthetic-inputs`. Each one is a complete, runnable block: the first line is the **runner line** resolved in the skill's Step 2 (`uv run --quiet --with reportlab python << 'PYEOF'` on the `uv` rung, `"$VENV/bin/python" << 'PYEOF'` on the venv rung), and everything below it is plain Python. Copy the block, replace the content at the top of the script with what Step 3 drafted, set the output path, run.

`reportlab` is BSD-licensed and pure Python; these recipes are checked against reportlab 5 by the repository's recipe test.

## Which recipe for which brief

| The brief asks for | Recipe |
|---|---|
| a short letter, memo, note, certificate — one page, free placement of text | [Basic PDF (canvas)](#basic-pdf-canvas) |
| a report with sections that flows over several pages | [Multi-page PDF (Platypus)](#multi-page-pdf-platypus) |
| a table — price list, schedule, results | [Table report (Platypus)](#table-report-platypus) |
| an invoice, statement, order, receipt — a header block, line items, totals | [Line-item document (composed)](#line-item-document-composed) |

Page size: the recipes use `letter`; use `A4` from the same import when the method's audience is European or the brief says so.

## Conventions shared by every recipe

- Output path: `<output_dir>/inputs/<name>.pdf` — replace with the request's `target`.
- Built-in fonts (`Helvetica`, `Helvetica-Bold`, `Times-Roman`, `Courier`) cover Latin-1 text and need no files. For other scripts, register a TrueType font — matplotlib ships DejaVu Sans, which covers most of them: `from reportlab.pdfbase import pdfmetrics; from reportlab.pdfbase.ttfonts import TTFont; from matplotlib import font_manager; pdfmetrics.registerFont(TTFont("DejaVu", font_manager.findfont("DejaVu Sans")))` — adding `--with matplotlib` to the runner line.
- Fictional content only: made-up companies, people, ids, addresses.
- Numbers that the method will read must be consistent: totals sum, tax is a stated percentage of the subtotal.

## Basic PDF (canvas)

The raw canvas: place text and lines at coordinates. Origin is the bottom-left corner, units are points (72 per inch).

```bash
uv run --quiet --with reportlab python << 'PYEOF'
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT = "<output_dir>/inputs/test_document.pdf"

# --- content -----------------------------------------------------------
TITLE = "Acme Hardware Supply — Internal Memo"
LINES = [
    "To: Warehouse team",
    "From: Jane Example, Operations",
    "Date: 2026-03-14",
    "",
    "Subject: Spring inventory count",
    "",
    "The spring count takes place on Friday 2026-03-20 from 07:00.",
    "Please close all open transfer orders by Thursday evening.",
]
# -----------------------------------------------------------------------

c = canvas.Canvas(OUT, pagesize=letter)
width, height = letter

c.setFont("Helvetica-Bold", 16)
c.drawString(72, height - 72, TITLE)
c.line(72, height - 80, width - 72, height - 80)

c.setFont("Helvetica", 11)
y = height - 110
for line in LINES:
    c.drawString(72, y, line)
    y -= 16

c.save()
print("wrote", OUT)
PYEOF
```

## Multi-page PDF (Platypus)

Platypus flows a list of elements (`Paragraph`, `Spacer`, `PageBreak`, …) across pages with margins and page breaks handled for you. This is the recipe for a report with sections.

```bash
uv run --quiet --with reportlab python << 'PYEOF'
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT = "<output_dir>/inputs/test_report.pdf"

# --- content -----------------------------------------------------------
TITLE = "Quarterly Operations Report — Q1 2026"
SECTIONS = [
    ("Summary", [
        "Order volume grew 12% quarter over quarter, driven by the new regional warehouse.",
        "On-time delivery held at 96.4%, within the 95% target.",
    ]),
    ("Warehouse", [
        "The Lyon site reached full capacity in February. Overflow is routed to Dijon.",
        "Two forklifts were replaced; no incidents were recorded.",
    ]),
    ("Outlook", [
        "Q2 focuses on the returns process and on reducing pick errors below 0.5%.",
    ]),
]
# -----------------------------------------------------------------------

styles = getSampleStyleSheet()
doc = SimpleDocTemplate(OUT, pagesize=letter, title=TITLE)
story = [Paragraph(TITLE, styles["Title"]), Spacer(1, 12)]

for index, (heading, paragraphs) in enumerate(SECTIONS):
    if index:
        story.append(PageBreak())  # one section per page; drop this to let sections flow
    story.append(Paragraph(heading, styles["Heading1"]))
    for text in paragraphs:
        story.append(Paragraph(text, styles["Normal"]))
        story.append(Spacer(1, 8))

doc.build(story)
print("wrote", OUT)
PYEOF
```

Long body text: `Paragraph("… " * 40, styles["Normal"])` wraps and paginates on its own, so a "ten-page report" is a longer `SECTIONS` list, not a layout problem.

## Table report (Platypus)

A titled table with a styled header row and a grid — the recipe for price lists, schedules and results.

```bash
uv run --quiet --with reportlab python << 'PYEOF'
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = "<output_dir>/inputs/test_table.pdf"

# --- content -----------------------------------------------------------
TITLE = "Quarterly Sales by Product"
DATA = [
    ["Product", "Q1", "Q2", "Q3", "Q4"],
    ["Widgets", "120", "135", "142", "158"],
    ["Gadgets", "85", "92", "98", "105"],
    ["Fasteners", "410", "398", "455", "470"],
]
# -----------------------------------------------------------------------

styles = getSampleStyleSheet()
doc = SimpleDocTemplate(OUT, pagesize=letter, title=TITLE)

table = Table(DATA, hAlign="LEFT")
table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f3e4e")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, 0), 11),
    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f4f1ea")),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
]))

doc.build([Paragraph(TITLE, styles["Title"]), Spacer(1, 12), table])
print("wrote", OUT)
PYEOF
```

## Line-item document (composed)

The two Platypus recipes together: a header block of paragraphs, a line-item table, a totals block. This is the shape of an invoice, a statement, a purchase order or a receipt — the most common document brief. The totals are computed from the items so they always agree.

```bash
uv run --quiet --with reportlab python << 'PYEOF'
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = "<output_dir>/inputs/test_invoice.pdf"

# --- content -----------------------------------------------------------
KIND = "INVOICE"
NUMBER = "INV-2026-0042"
DATE = "2026-03-14"
DUE = "2026-04-13"
SELLER = ["Acme Hardware Supply", "18 rue des Forges", "69007 Lyon, France", "VAT FR12345678901"]
BUYER = ["Example Constructions SARL", "4 avenue du Chantier", "21000 Dijon, France"]
ITEMS = [  # description, quantity, unit price
    ("M8 hex bolts, zinc, box of 100", 12, 14.90),
    ("Cordless drill 18V, 2 batteries", 2, 189.00),
    ("Safety goggles, clear", 25, 6.50),
    ("Wood screws 4x40, box of 200", 8, 11.20),
]
TAX_RATE = 0.20
CURRENCY = "EUR"
# -----------------------------------------------------------------------

styles = getSampleStyleSheet()
doc = SimpleDocTemplate(OUT, pagesize=letter, title=f"{KIND} {NUMBER}")
story = []

story.append(Paragraph(f"{KIND} {NUMBER}", styles["Title"]))
story.append(Paragraph(f"Date: {DATE} &nbsp;&nbsp; Due: {DUE}", styles["Normal"]))
story.append(Spacer(1, 12))

parties = Table(
    [[Paragraph("<b>From</b><br/>" + "<br/>".join(SELLER), styles["Normal"]),
      Paragraph("<b>Bill to</b><br/>" + "<br/>".join(BUYER), styles["Normal"])]],
    colWidths=[240, 240], hAlign="LEFT",
)
story.append(parties)
story.append(Spacer(1, 18))

rows = [["Description", "Qty", "Unit price", "Amount"]]
subtotal = 0.0
for description, quantity, unit_price in ITEMS:
    amount = quantity * unit_price
    subtotal += amount
    rows.append([description, str(quantity), f"{unit_price:,.2f}", f"{amount:,.2f}"])
tax = round(subtotal * TAX_RATE, 2)
total = round(subtotal + tax, 2)
rows += [
    ["", "", "Subtotal", f"{subtotal:,.2f}"],
    ["", "", f"VAT {TAX_RATE:.0%}", f"{tax:,.2f}"],
    ["", "", f"Total {CURRENCY}", f"{total:,.2f}"],
]

items = Table(rows, colWidths=[260, 50, 85, 85], hAlign="LEFT")
items.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f3e4e")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ("GRID", (0, 0), (-1, len(ITEMS)), 0.5, colors.black),
    ("LINEABOVE", (2, -3), (-1, -3), 0.5, colors.black),
    ("FONTNAME", (2, -1), (-1, -1), "Helvetica-Bold"),
]))
story.append(items)
story.append(Spacer(1, 24))
story.append(Paragraph("Payment within 30 days by bank transfer. Thank you for your business.", styles["Normal"]))

doc.build(story)
print("wrote", OUT, "total", f"{total:.2f}")
PYEOF
```

Swap `KIND`, the party blocks and the closing line to turn it into a purchase order, a credit note or a receipt; the arithmetic stays.

## Verify

```bash
head -c 5 "<output_dir>/inputs/<name>.pdf"; echo; wc -c "<output_dir>/inputs/<name>.pdf"
python3 -c "import re, sys; print('pages:', len(re.findall(rb'/Type\s*/Page[^s]', open(sys.argv[1], 'rb').read())))" "<output_dir>/inputs/<name>.pdf"
```

Expect `%PDF-`, a size in the kilobytes, and the page count the brief asked for. A failed run must leave no file: `[ -s "<target>" ] || rm -f "<target>"`.

## Last resort — a public test PDF

Only when the environment could not be resolved (the skill's Step 2 table, last row) and the user has no file to give: use a public PDF as the input value directly, and say in the report that this is a substitution, not a generated document.

```json
{
  "document": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/img/table-word.pdf"
}
```

It is a small table document; a method expecting an invoice will not find invoice fields in it, which is exactly why the substitution has to be named.
