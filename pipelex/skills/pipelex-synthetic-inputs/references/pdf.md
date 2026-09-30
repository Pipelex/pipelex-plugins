# PDF recipes — reportlab

Read this at step 4 of the skill when the format is `pdf`, before writing any code; its **Verify** section is step 5's check.

Recipes for the `pdf` format of `/pipelex-synthetic-inputs`. Each one is a complete, runnable block: the first line is the **runner line** resolved in the skill's Step 2 (`uv run --quiet --no-project --with reportlab python << 'PYEOF'` on the `uv` rung, `<the absolute venv path Step 2 printed>/bin/python << 'PYEOF'` on the venv rung — substitute the path, never the `$VENV` reference, which is unset in a fresh shell), and everything below it is plain Python. Copy the block, replace what sits between the `CONTENT` markers with what Step 3 drafted, set the output path, run.

`reportlab` is BSD-licensed and pure Python; every recipe below was executed under reportlab 4.5.1 and 5.0.1 before it was committed.

## Which recipe for which brief

| The brief asks for | Recipe |
|---|---|
| a short letter, memo, note, certificate — one page, free placement of text | [Basic PDF (canvas)](#basic-pdf-canvas) |
| a report with sections that flows over several pages | [Multi-page PDF (Platypus)](#multi-page-pdf-platypus) |
| a table — price list, schedule, roster, any grid of text | [Table report (Platypus)](#table-report-platypus) |
| measurements judged against limits — lab results, inspections, test reports | [Results table (Platypus)](#results-table-platypus) |
| an invoice, statement, order, receipt — a header block, line items, totals | [Line-item document (composed)](#line-item-document-composed) |

Page size: the recipes use `letter`; set `PAGE_SIZE = A4` in the content block when the method's audience is European or the brief says so.

## Conventions shared by every recipe

- Output path: `<output_dir>/inputs/<name>.pdf` — replace with the request's `target`.
- Built-in fonts (`Helvetica`, `Helvetica-Bold`, `Times-Roman`, `Courier`) cover Latin-1 text and need no files. For other scripts, register a TrueType font — matplotlib ships DejaVu Sans, which covers most of them: `from reportlab.pdfbase import pdfmetrics; from reportlab.pdfbase.ttfonts import TTFont; from matplotlib import font_manager; pdfmetrics.registerFont(TTFont("DejaVu", font_manager.findfont("DejaVu Sans")))` — adding `--with matplotlib` to the runner line.
- Language: every word a recipe prints, labels included, and the way it writes figures sit in its content block, so a brief in another language is an edit of that block alone.
- Fictional content only: made-up companies, people, ids, addresses.
- Numbers that the method will read must be consistent: totals sum, tax is a stated percentage of the subtotal.

## Basic PDF (canvas)

One page drawn with the canvas API, for letters, notes, notices and certificates. Coordinates are points (1/72 inch) up and right from the bottom-left corner; y is the text's baseline.

```bash
uv run --quiet --no-project --with reportlab python << 'PYEOF'
import os
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen.canvas import Canvas

OUT = "<output_dir>/inputs/test_document.pdf"
if "<" in OUT or ">" in OUT:
    sys.exit(f"Refusing to run: OUT still holds a placeholder: {OUT}")
Path(OUT).parent.mkdir(parents=True, exist_ok=True)

# ==== CONTENT: all printed text; edit only this block ====
# Built-in fonts: characters outside Latin-1 print as black boxes.
PAGE_SIZE = letter  # or A4
CLINIC = "Wrenfield Veterinary Clinic"
ADDRESS = ["214 Sorrel Street, Aldenmoor Springs", "Tel. 555-0147"]
DATE = "October 6, 2026"
RECIPIENT = ["Ms. Dana Whitlock", "88 Quarry Hill Road", "Aldenmoor Springs"]
SUBJECT = "Vaccination reminder for Biscuit (patient WVC-30412)"
BODY = [
    "Dear Ms. Whitlock,",
    "Biscuit is due for her yearly rabies and DHPP boosters. We have booked her in with Dr. Pascoe on "
    "Thursday, October 22, 2026, at 10:15 a.m. Please bring her vaccination card.",
    "If this time does not suit you, call us at least a day ahead.",
    "Kind regards,",
]
SIGNER = "Dr. Imogen Pascoe, DVM"
# ==== END CONTENT ====

MARGIN = 72


def render(path):
    width, height = PAGE_SIZE
    room = width - 2 * MARGIN
    y = height - MARGIN
    # invariant=1: byte-identical reruns.
    c = Canvas(path, pagesize=PAGE_SIZE, invariant=1)
    c.setTitle(SUBJECT)

    def put(text, font="Helvetica", size=11, right=False):
        # The canvas never wraps, clips or adds pages: overflow would vanish silently.
        nonlocal y
        if c.stringWidth(text, font, size) > room or y < MARGIN:
            raise ValueError(f"Does not fit the page; shorten it or use Platypus: {text!r}")
        c.setFont(font, size)
        if right:
            c.drawRightString(width - MARGIN, y, text)
        else:
            c.drawString(MARGIN, y, text)
        y -= size * 1.4  # the step grows with the font, or big lines touch

    put(CLINIC, "Helvetica-Bold", 20)
    for line in ADDRESS:
        put(line, size=9)
    c.line(MARGIN, y, width - MARGIN, y)
    y -= 36
    put(DATE, right=True)
    y -= 15
    for line in RECIPIENT:
        put(line)
    y -= 15
    put(SUBJECT, "Helvetica-Bold")
    y -= 10
    for paragraph in BODY:
        for line in simpleSplit(paragraph, "Helvetica", 11, room):
            put(line)
        y -= 8
    y -= 22
    put(SIGNER, "Helvetica-Bold")
    put(CLINIC)
    c.save()


PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))
try:
    render(PART)
    os.replace(PART, OUT)
finally:
    Path(PART).unlink(missing_ok=True)
print(f"wrote {OUT}")
PYEOF
```

The canvas never wraps, so the script wraps paragraphs and fails rather than let text run off the page; real paragraph wrapping belongs in Platypus. `PAGE_SIZE = A4` gives A4.

## Multi-page PDF (Platypus)

Headings and paragraphs that Platypus flows over numbered pages, for reports, policies, contracts and manuals; the title is also the PDF's title metadata.

```bash
uv run --quiet --no-project --with reportlab python << 'PYEOF'
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

OUT = "<output_dir>/inputs/test_report.pdf"
if "<" in OUT or ">" in OUT:
    sys.exit(f"Refusing to run: OUT still holds a placeholder: {OUT}")
Path(OUT).parent.mkdir(parents=True, exist_ok=True)

# ==== CONTENT: all printed text; edit only this block ====
# Built-in fonts: characters outside Latin-1 print as black boxes.
PAGE_SIZE = letter  # or A4
SECTIONS_START_ON_NEW_PAGE = False
TITLE = "Building Condition Inspection Report"
DETAILS = [("Property", "Corran Quay Residences, 40 Tidewater Lane, Port Aldery"),
           ("Prepared for", "Corran Quay Owners' Association"),
           ("Inspected", "September 14, 2026, by Priya Ostrander, Halvard & Moss Building Surveyors")]
REFERENCE, PAGE_LABEL = "HM-2026-0388", "Page"
# Items are paragraphs or (subheading, paragraph) pairs.
SECTIONS = [
    ("Overview", [
        "We visually inspected the roof, elevations, garage and common parts of this block of 24 "
        "apartments, built in 1988.",
        "The building is in fair condition. The most serious findings are water entering at the north-east "
        "parapet and corroded railing brackets on six south balconies, which should not be used until an engineer "
        "has assessed them.",
    ]),
    ("Findings by area", [
        ("Roof and drainage: Fair", "The membrane has blistered near the north-east corner, where the parapet "
         "coping joints have opened. Three of the five outlets were partly blocked, and the corridor ceiling "
         "below the corner is damp."),
        ("Elevations and balconies: Poor", "The brickwork is sound, but the railing brackets on six south "
         "balconies are rusting where they enter the slab, and the concrete around two of them has cracked."),
        ("Structure: Good", "There is no sign of settlement or movement."),
        ("Fire safety: Fair", "The alarm panel showed no faults, but the third-floor fire door to the east "
         "stairwell no longer closes on its own."),
    ]),
    ("Recommendations", [
        ("Within one week", "Keep residents off the six balconies and commission a structural engineer."),
        ("Within one month", "Repair the closer of the third-floor fire door."),
        ("Before winter", "Repoint the parapet coping, repair the membrane, clear the outlets, then repair the "
         "stained ceiling."),
        ("Within a year", "Budget for renewing the roof membrane, which is near the end of its life."),
    ]),
]
# ==== END CONTENT ====


def style(name, font="Times-Roman", size=12, **extra):
    # Leading follows size, or an enlarged font's wrapped lines touch.
    return ParagraphStyle(name, fontName=font, fontSize=size, leading=size * 1.35, **extra)


TITLE_STYLE = style("title", "Helvetica-Bold", 22, spaceAfter=10)
# keepWithNext: no heading left alone at the foot of a page.
H1 = style("h1", "Helvetica-Bold", 16, spaceBefore=14, spaceAfter=6, keepWithNext=1)
H2 = style("h2", "Helvetica-Bold", 12.5, spaceBefore=8, spaceAfter=2, keepWithNext=1)
BODY = style("body", spaceAfter=7)


def para(text, style):
    # Paragraph parses markup: an unescaped "<" or "&" raises or loses text.
    return Paragraph(escape(text), style)


def footer(canvas, doc):
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(doc.leftMargin + 6, 40, f"{TITLE}, {REFERENCE}")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin - 6, 40, f"{PAGE_LABEL} {canvas.getPageNumber()}")


def render(path):
    story = [para(TITLE, TITLE_STYLE)]
    story += [Paragraph(f"<b>{escape(k)}:</b> {escape(v)}", BODY) for k, v in DETAILS]
    for number, (heading, items) in enumerate(SECTIONS):
        if number and SECTIONS_START_ON_NEW_PAGE:
            story.append(PageBreak())
        story.append(para(heading, H1))
        for item in items:
            story += [para(item[0], H2), para(item[1], BODY)] if isinstance(item, tuple) else [para(item, BODY)]
    # invariant=1: byte-identical reruns.
    doc = SimpleDocTemplate(path, pagesize=PAGE_SIZE, title=TITLE, invariant=1)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))
try:
    render(PART)
    os.replace(PART, OUT)
finally:
    Path(PART).unlink(missing_ok=True)
print(f"wrote {OUT}")
PYEOF
```

Add items to `SECTIONS` to lengthen it. Sections flow on; `SECTIONS_START_ON_NEW_PAGE = True` gives each a new page, `PAGE_SIZE = A4` an A4 page.

## Table report (Platypus)

A titled table for price lists, schedules, rosters and any other grid of text; every cell wraps.

```bash
uv run --quiet --no-project --with reportlab python << 'PYEOF'
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table

OUT = "<output_dir>/inputs/test_table.pdf"
if "<" in OUT or ">" in OUT:
    sys.exit(f"Refusing to run: OUT still holds a placeholder: {OUT}")
Path(OUT).parent.mkdir(parents=True, exist_ok=True)

# ==== CONTENT: all printed text; edit only this block ====
# Built-in fonts: characters outside Latin-1 print as black boxes.
PAGE_SIZE = letter  # or A4; landscape(letter) when the columns cannot fit
HEADING = "Brackenwold Nursery"
TITLE = "Autumn price list 2026"
INFO = "Prices per plant in euros, VAT included, valid October 1 to November 30, 2026."
COLUMNS = ["Code", "Plant", "Pot size", "Price (€)"]
COL_WIDTHS = [58, 250, 70, 70]  # points, one per column; a word wider than its column breaks mid-word
RIGHT_ALIGNED = ["Price (€)"]  # headers of the columns to right-align
ROWS = [  # one value per column
    ("BW-1102", "Acer palmatum 'Copperwick' (Japanese maple)", "10 L", "42.00"),
    ("BW-1107", "Amelanchier lamarckii 'Harrow Mist' (snowy mespilus), multi-stemmed, 150 to 175 cm", "25 L", "68.50"),
    ("BW-1318", "Hydrangea paniculata 'Wintermoor' (panicle hydrangea)", "7.5 L", "24.00"),
    ("BW-1344", "Lavandula angustifolia 'Tollard Blue' (lavender), tray of six plugs for edging", "9 cm", "15.60"),
    ("BW-1402", "Malus domestica 'Farthing Russet' (dessert apple), two-year bush", "12 L", "36.00"),
    ("BW-1466", "Prunus laurocerasus (cherry laurel), hedging, 80 to 100 cm", "3 L", "11.25"),
    ("BW-1611", "Taxus baccata (yew), root-balled hedging, 60 to 80 cm", "Root ball", "14.80"),
    ("BW-1690", "Viburnum tinus 'Greyhollow' (laurustinus)", "5 L", "21.00"),
]
# ==== END CONTENT ====

NAVY, STRIPE, RULE = HexColor("#1F3B57"), HexColor("#EDF1F5"), HexColor("#B8C3CD")
# Cells are Paragraphs: they wrap, and ignore the table's FONT, TEXTCOLOR and ALIGN.
CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=11.5)
HEAD = ParagraphStyle("head", CELL, fontName="Helvetica-Bold", textColor=white)
TEXT = ParagraphStyle("text", CELL, fontSize=10, leading=14, spaceBefore=4)
BIG = ParagraphStyle("big", TEXT, fontName="Helvetica-Bold", fontSize=15, leading=20, textColor=NAVY)
GRID = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, STRIPE]),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE), ("BOX", (0, 0), (-1, -1), 0.6, NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]


def right(style):
    return ParagraphStyle(style.name + "-right", style, alignment=TA_RIGHT)


def cell(text, style):
    # Paragraph parses markup: an unescaped "<" or "&" raises or loses text.
    return Paragraph(escape(str(text)), style)


def render(path):
    # invariant=1: byte-identical reruns.
    doc = SimpleDocTemplate(path, pagesize=PAGE_SIZE, title=TITLE, invariant=1)
    frame = doc.width - 12  # 6 pt frame padding each side: 456 pt on Letter
    # Platypus checks only heights: a table too wide runs off the page silently.
    if len(COL_WIDTHS) != len(COLUMNS) or sum(COL_WIDTHS) > frame:
        raise ValueError(f"Need {len(COLUMNS)} widths totalling at most {frame:.0f} pt")
    if not set(RIGHT_ALIGNED) <= set(COLUMNS):
        raise ValueError(f"RIGHT_ALIGNED names a column that COLUMNS lacks: {RIGHT_ALIGNED}")
    head = [right(HEAD) if h in RIGHT_ALIGNED else HEAD for h in COLUMNS]
    body = [right(CELL) if h in RIGHT_ALIGNED else CELL for h in COLUMNS]
    rows = [[cell(h, s) for h, s in zip(COLUMNS, head)]]
    for n, row in enumerate(ROWS, 1):
        # reportlab pads a short row with blanks, and zip() drops extra values.
        if len(row) != len(COLUMNS):
            raise ValueError(f"Row {n} {row!r} has {len(row)} values for {len(COLUMNS)} columns")
        rows.append([cell(v, s) for v, s in zip(row, body)])
    doc.build([cell(HEADING, BIG), Paragraph(f"<b>{escape(TITLE)}</b>", TEXT), cell(INFO, TEXT),
               Table(rows, colWidths=COL_WIDTHS, repeatRows=1, hAlign="LEFT", style=GRID, spaceBefore=10)])


PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))
try:
    render(PART)
    os.replace(PART, OUT)
finally:
    Path(PART).unlink(missing_ok=True)
print(f"wrote {OUT}")
PYEOF
```

A table too wide for the page runs off it silently, so the widths are checked against the 456 pt Letter frame, and a row with the wrong number of values is refused. Use `landscape(letter)` when the columns cannot fit, `A4` for A4.

## Results table (Platypus)

Measurements judged against limits, for lab results, inspections and test reports: the script computes each verdict from the values as printed, highlights failing values and states the limits beneath the table. Widths are checked as in the table report; `A4` gives A4 and `landscape(letter)` room for more columns.

```bash
uv run --quiet --no-project --with reportlab python << 'PYEOF'
import os
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table

OUT = "<output_dir>/inputs/test_results.pdf"
if "<" in OUT or ">" in OUT:
    sys.exit(f"Refusing to run: OUT still holds a placeholder: {OUT}")
Path(OUT).parent.mkdir(parents=True, exist_ok=True)

# ==== CONTENT: all printed text; edit only this block ====
# Built-in fonts: characters outside Latin-1 print as black boxes.
PAGE_SIZE = letter  # or A4; landscape(letter) when the columns cannot fit
LAB = "Oxbury Vale Water Testing Laboratory"
TITLE = "Drinking-water results, August 2026"
INFO = "Client: Marrowby District Water Board. Report OVW-26-0913."
DESCRIPTORS = ["Sample", "Site", "Sampled"]
# (header, decimals shown, lower limit, upper limit); None means no limit on that side.
MEASURES = [("pH", 1, 6.5, 9.0), ("Turbidity (NTU)", 1, None, 4.0),
            ("Nitrate (mg/L)", 1, None, 50.0), ("Lead (µg/L)", 1, None, 10.0)]
VERDICT, PASS, FAIL = "Verdict", "Pass", "Fail"
COL_WIDTHS = [52, 108, 60, 34, 52, 44, 40, 46]  # points: descriptors, measures, verdict
# A word wider than its column breaks mid-word: give dates and long headers room.
SAMPLES = [  # (one value per descriptor, one value per measurement)
    (("L26-0801", "Ostry Reservoir outlet", "2026-08-11"), (7.6, 0.4, 12.3, 0.8)),
    (("L26-0802", "Kestrel Lane standpipe", "2026-08-11"), (7.5, 0.6, 12.9, 1.2)),
    (("L26-0803", "Marrowby Primary School, kitchen tap", "2026-08-11"), (7.3, 0.3, 12.1, 2.4)),
    (("L26-0804", "14 Weaver's Row", "2026-08-12"), (7.2, 0.4, 12.6, 14.2)),
    (("L26-0805", "Brackley Road hydrant", "2026-08-12"), (7.5, 5.6, 12.8, 1.9)),
    (("L26-0806", "Fenwick Farm borehole", "2026-08-13"), (6.3, 1.1, 61.4, 0.9)),
    (("L26-0807", "Low Moor pump house", "2026-08-13"), (7.8, 0.2, 13.0, 0.6)),
    (("L26-0808", "Upper Heath estate", "2026-08-14"), (7.6, 0.6, 12.0, 4.8)),
]
# The sentence under the table, which leaves out a measurement without limits.
RANGE, AT_LEAST, AT_MOST = "{name} {low} to {high}", "{name} at least {low}", "{name} at most {high}"
LIMITS = "Limits: {limits}. Highlighted values break a limit and fail the sample."
DECIMAL_MARK, THOUSANDS_SEP = ".", ","
# ==== END CONTENT ====

NAVY, STRIPE, RULE = HexColor("#1F3B57"), HexColor("#EDF1F5"), HexColor("#B8C3CD")
FAIL_FILL, FAIL_INK = HexColor("#F7D6D2"), HexColor("#9A1B10")
# Cells are Paragraphs: they wrap, and ignore the table's FONT, TEXTCOLOR and ALIGN.
CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=11.5)
HEAD = ParagraphStyle("head", CELL, fontName="Helvetica-Bold", textColor=white)
BAD = ParagraphStyle("bad", CELL, fontName="Helvetica-Bold", textColor=FAIL_INK)
TEXT = ParagraphStyle("text", CELL, fontSize=10, leading=14, spaceBefore=4)
BIG = ParagraphStyle("big", TEXT, fontName="Helvetica-Bold", fontSize=15, leading=20, textColor=NAVY)
GRID = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, STRIPE]),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE), ("BOX", (0, 0), (-1, -1), 0.6, NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]


def right(style):
    return ParagraphStyle(style.name + "-right", style, alignment=TA_RIGHT)


def cell(text, style):
    # Paragraph parses markup: an unescaped "<" or "&" raises or loses text.
    return Paragraph(escape(str(text)), style)


def shown(value, places):
    # Values and limits are both judged as printed, so no verdict contradicts the page.
    return Decimal(str(value)).quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP)


def figure(value, places):
    return f"{value:,.{places}f}".translate(str.maketrans({",": THOUSANDS_SEP, ".": DECIMAL_MARK}))


def render(path):
    # invariant=1: byte-identical reruns.
    doc = SimpleDocTemplate(path, pagesize=PAGE_SIZE, title=TITLE, invariant=1)
    first, ncols = len(DESCRIPTORS), len(DESCRIPTORS) + len(MEASURES) + 1
    frame = doc.width - 12  # 6 pt frame padding each side: 456 pt on Letter
    # Platypus checks only heights: a table too wide runs off the page silently.
    if len(COL_WIDTHS) != ncols or sum(COL_WIDTHS) > frame:
        raise ValueError(f"Need {ncols} widths totalling at most {frame:.0f} pt")
    bounds, limits = [], []
    for name, places, low, high in MEASURES:
        if None not in (low, high) and low > high:
            raise ValueError(f"{name}: lower limit {low} is above upper limit {high}")
        lo, hi = (None if v is None else shown(v, places) for v in (low, high))
        bounds.append((lo, hi))
        words = {k: figure(v, places) for k, v in (("low", lo), ("high", hi)) if v is not None}
        form = RANGE if len(words) == 2 else AT_LEAST if lo is not None else AT_MOST if words else None
        if form:
            limits.append(form.format(name=name, **words))
    rows = [[cell(h, HEAD) for h in DESCRIPTORS] + [cell(m[0], right(HEAD)) for m in MEASURES] + [cell(VERDICT, HEAD)]]
    marks = list(GRID)
    for r, (described, values) in enumerate(SAMPLES, 1):
        # reportlab pads a short row with blanks, and zip() drops extra values.
        if len(described) != first or len(values) != len(MEASURES):
            raise ValueError(f"Sample {r} {list(described)} needs {first} descriptor values and {len(MEASURES)} values")
        printed = [shown(v, m[1]) for v, m in zip(values, MEASURES)]
        bad = [i for i, (p, (lo, hi)) in enumerate(zip(printed, bounds))
               if (lo is not None and p < lo) or (hi is not None and p > hi)]
        rows.append([cell(d, CELL) for d in described]
                    + [cell(figure(p, m[1]), right(BAD if i in bad else CELL))
                       for i, (p, m) in enumerate(zip(printed, MEASURES))]
                    + [cell(FAIL if bad else PASS, BAD if bad else CELL)])
        # Highlights come after the stripes: backgrounds paint in command order.
        cols = [first + i for i in bad] + ([ncols - 1] if bad else [])
        marks += [("BACKGROUND", (c, r), (c, r), FAIL_FILL) for c in cols]
    story = [cell(LAB, BIG), Paragraph(f"<b>{escape(TITLE)}</b>", TEXT), cell(INFO, TEXT),
             Table(rows, colWidths=COL_WIDTHS, repeatRows=1, hAlign="LEFT", style=marks, spaceBefore=10)]
    if limits:
        story.append(cell(LIMITS.format(limits="; ".join(limits)), TEXT))
    doc.build(story)


PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))
try:
    render(PART)
    os.replace(PART, OUT)
finally:
    Path(PART).unlink(missing_ok=True)
print(f"wrote {OUT}")
PYEOF
```

## Line-item document (composed)

The shape of an invoice, statement, purchase order or receipt: header, parties, line items, totals and a closing line, every figure computed exactly with `Decimal`.

```bash
uv run --quiet --no-project --with reportlab python << 'PYEOF'
import os
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table

OUT = "<output_dir>/inputs/test_invoice.pdf"
if "<" in OUT or ">" in OUT:
    sys.exit(f"Refusing to run: OUT still holds a placeholder: {OUT}")
Path(OUT).parent.mkdir(parents=True, exist_ok=True)

# ==== CONTENT: all printed text; edit only this block ====
# Built-in fonts: characters outside Latin-1 print as black boxes.
PAGE_SIZE = letter  # or A4
KIND, NUMBER_LABEL, NUMBER = "Invoice", "Invoice no.", "TPW-2026-0187"
DATES = [("Issue date", "2026-09-15"), ("Due date", "2026-10-15")]
ISSUER_LABEL, ISSUER = "From", ["Tallowmere Print Works", "7 Grainstore Yard, Tallowmere", "VAT ID ZZ 481 209 336"]
CLIENT_LABEL, CLIENT = "Bill to", ["Kessling Vale Amateur Rugby Club", "Attn. Marit Olsberg", "Kessling Vale"]
COLUMNS = ["Description", "Qty", "Unit price", "Amount"]
COL_WIDTHS = [235, 44, 74, 80]  # points; a word wider than its column breaks mid-word
# (description, quantity, unit price); write numbers as strings, a fractional quantity as "2.5".
LINE_ITEMS = [
    ("Match-day programmes, 24 pages, saddle-stitched, full colour on 130 gsm silk, with a "
     "foil-stamped crest", "400", "1.85"),
    ("Membership cards, laminated, printed on both sides", "350", "0.62"),
    ("Redrawing the club crest as vector artwork, per hour", "2.5", "46.00"),
    ("Roll-up banner, 85 × 200 cm, with carry case", "2", "89.00"),
]
SUBTOTAL_LABEL, TOTAL_LABEL = "Subtotal", "Total due"
TAX_LABEL, TAX_RATE = "VAT {rate}%", "21"  # the rate in percent
# MONEY places the symbol: "{} €" puts it after. Write a space as "\u00a0", which never breaks.
MONEY, DECIMAL_MARK, THOUSANDS_SEP = "€{}", ".", ","
CLOSING = "Please pay by bank transfer to IBAN ZZ47 0012 3456 7890 1234 56 by the due date."
# ==== END CONTENT ====

CENT = Decimal("0.01")
LINES = []
for description, quantity, price in LINE_ITEMS:
    # The price is rounded to the cent it prints at, so each amount follows from the page.
    quantity, price = Decimal(str(quantity)), Decimal(str(price)).quantize(CENT, ROUND_HALF_UP)
    LINES.append((description, quantity, price, (quantity * price).quantize(CENT, ROUND_HALF_UP)))
SUBTOTAL = sum(line[3] for line in LINES)
TAX = (SUBTOTAL * Decimal(TAX_RATE) / 100).quantize(CENT, ROUND_HALF_UP)
TOTAL = SUBTOTAL + TAX

NAVY, STRIPE, RULE = HexColor("#1F3B57"), HexColor("#EDF1F5"), HexColor("#B8C3CD")
# Cells are Paragraphs: they wrap, and ignore the table's FONT, TEXTCOLOR and ALIGN.
CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=11.5)
HEAD = ParagraphStyle("head", CELL, fontName="Helvetica-Bold", textColor=white)
BOLD = ParagraphStyle("bold", CELL, fontName="Helvetica-Bold", fontSize=10.5, leading=13.5)
TEXT = ParagraphStyle("text", CELL, fontSize=10, leading=14)
BIG = ParagraphStyle("big", TEXT, fontName="Helvetica-Bold", fontSize=19, leading=24, textColor=NAVY)


def grid(last):
    return [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, last), [white, STRIPE]),
            ("LINEBELOW", (0, 1), (-1, last), 0.25, RULE), ("BOX", (0, 0), (-1, last), 0.6, NAVY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]


def right(style):
    return ParagraphStyle(style.name + "-right", style, alignment=TA_RIGHT)


def cell(text, style):
    # Paragraph parses markup: an unescaped "<" or "&" raises or loses text.
    return Paragraph(escape(str(text)), style)


def figure(value, places):
    return f"{value:,.{places}f}".translate(str.maketrans({",": THOUSANDS_SEP, ".": DECIMAL_MARK}))


def plain(value):
    return figure(value, max(0, -value.normalize().as_tuple().exponent))  # "400", "2.5"


def money(value):
    return MONEY.format(figure(value, 2))


def party(label, lines):
    first = f'<font size="8">{escape(label)}</font><br/><b>{escape(lines[0])}</b>'
    return Paragraph("<br/>".join([first] + [escape(line) for line in lines[1:]]), TEXT)


def render(path):
    # invariant=1: byte-identical reruns.
    doc = SimpleDocTemplate(path, pagesize=PAGE_SIZE, title=f"{KIND} {NUMBER}", invariant=1)
    frame, width = doc.width - 12, sum(COL_WIDTHS)  # 6 pt frame padding each side: 456 pt on Letter
    # Platypus checks only heights: a table too wide runs off the page silently.
    if len(COLUMNS) != 4 or len(COL_WIDTHS) != 4 or width > frame:
        raise ValueError(f"Need 4 columns and 4 widths totalling at most {frame:.0f} pt")
    rows = [[cell(h, right(HEAD) if i else HEAD) for i, h in enumerate(COLUMNS)]]
    rows += [[cell(d, CELL), cell(plain(q), right(CELL)), cell(money(p), right(CELL)), cell(money(a), right(CELL))]
             for d, q, p, a in LINES]
    n = len(rows) - 1
    tax = TAX_LABEL.format(rate=plain(Decimal(TAX_RATE)))
    rows += [[cell(label, right(s)), "", "", cell(money(v), right(s))]
             for label, v, s in [(SUBTOTAL_LABEL, SUBTOTAL, CELL), (tax, TAX, CELL), (TOTAL_LABEL, TOTAL, BOLD)]]
    meta = "<br/>".join(f"{escape(k)}  <b>{escape(v)}</b>" for k, v in [(NUMBER_LABEL, NUMBER)] + DATES)
    head = Table(
        [[cell(ISSUER[0], BIG), [cell(KIND, right(BIG)), Paragraph(meta, right(TEXT))]],
         [party(ISSUER_LABEL, ISSUER), party(CLIENT_LABEL, CLIENT)]],
        colWidths=[width * 0.55, width * 0.45], hAlign="LEFT",
        style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, NAVY),
               ("TOPPADDING", (0, 1), (-1, 1), 14)],
    )
    items = Table(rows, colWidths=COL_WIDTHS, repeatRows=1, hAlign="LEFT", spaceBefore=18, spaceAfter=18,
                  style=grid(n) + [("LINEABOVE", (2, -1), (-1, -1), 1, NAVY)]
                  + [("SPAN", (0, r), (2, r)) for r in range(n + 1, n + 4)])  # a long total label gets room
    doc.build([head, items, cell(CLOSING, TEXT)])


PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))
try:
    render(PART)
    os.replace(PART, OUT)
finally:
    Path(PART).unlink(missing_ok=True)
print(f"wrote {OUT} (total {TOTAL:.2f})")
PYEOF
```

Every printed word and the way figures are written sit in the content block, as in every recipe, so another language is an edit of that block alone, and `PAGE_SIZE = A4` gives A4. For a purchase order, credit note or receipt, edit `KIND`, `NUMBER_LABEL`, `DATES`, the party labels, `TOTAL_LABEL` and `CLOSING`, with the buyer as `ISSUER` on a purchase order.

## Verify

```bash
head -c 5 "<output_dir>/inputs/<name>.pdf"; echo; wc -c "<output_dir>/inputs/<name>.pdf"
uv run --quiet --no-project python -c "import re, sys; print('pages:', len(re.findall(rb'/Type\s*/Page[^s]', open(sys.argv[1], 'rb').read())))" "<output_dir>/inputs/<name>.pdf"
```

The page count needs no packages, so it runs under whichever interpreter Step 2 resolved — the `uv run` above on rung 1, the absolute venv interpreter path on rung 2. Do not reach for a bare `python3`: a machine that got `uv` from the installer has no such command.

Expect `%PDF-`, a size in the kilobytes, and the page count the brief asked for. A failed render is cleaned up as the skill's step 4 says, partial file included, before anything is rerun.
