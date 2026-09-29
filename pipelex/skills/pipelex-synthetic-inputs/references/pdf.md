# PDF recipes — reportlab

Read this at step 4 of the skill when the format is `pdf`, before writing any code; its **Verify** section is step 5's check.

Recipes for the `pdf` format of `/pipelex-synthetic-inputs`. Each one is a complete, runnable block: the first line is the **runner line** resolved in the skill's Step 2 (`uv run --quiet --no-project --with reportlab python << 'PYEOF'` on the `uv` rung, `<the absolute venv path Step 2 printed>/bin/python << 'PYEOF'` on the venv rung — substitute the path, never the `$VENV` reference, which is unset in a fresh shell), and everything below it is plain Python. Copy the block, replace what sits between the `CONTENT` markers with what Step 3 drafted, set the output path, run.

`reportlab` is BSD-licensed and pure Python; every recipe below was executed under reportlab 4.5.1 and 5.0.1 before it was committed.

## Which recipe for which brief

| The brief asks for | Recipe |
|---|---|
| a short letter, memo, note, certificate — one page, free placement of text | [Basic PDF (canvas)](#basic-pdf-canvas) |
| a report with sections that flows over several pages | [Multi-page PDF (Platypus)](#multi-page-pdf-platypus) |
| a table — price list, schedule, results | [Table report (Platypus)](#table-report-platypus) |
| an invoice, statement, order, receipt — a header block, line items, totals | [Line-item document (composed)](#line-item-document-composed) |

Page size: the recipes use `letter`; set `PAGE_SIZE = A4` in the content block when the method's audience is European or the brief says so.

## Conventions shared by every recipe

- Output path: `<output_dir>/inputs/<name>.pdf` — replace with the request's `target`.
- Built-in fonts (`Helvetica`, `Helvetica-Bold`, `Times-Roman`, `Courier`) cover Latin-1 text and need no files. For other scripts, register a TrueType font — matplotlib ships DejaVu Sans, which covers most of them: `from reportlab.pdfbase import pdfmetrics; from reportlab.pdfbase.ttfonts import TTFont; from matplotlib import font_manager; pdfmetrics.registerFont(TTFont("DejaVu", font_manager.findfont("DejaVu Sans")))` — adding `--with matplotlib` to the runner line.
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

# ==== CONTENT: edit only this block ====
# Built-in fonts: non-Latin-1 characters (emoji, subscripts) print as black boxes.
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
    # invariant=1: byte-identical reruns. No pagesize means A4.
    c = Canvas(path, pagesize=PAGE_SIZE, invariant=1)
    c.setTitle(SUBJECT)

    def put(text, font="Helvetica", size=11, gap=15, right=False):
        # The canvas never wraps, clips or adds pages: overflow would vanish silently.
        nonlocal y
        if c.stringWidth(text, font, size) > room or y < MARGIN:
            raise ValueError(f"Does not fit the page; shorten it or use Platypus: {text!r}")
        c.setFont(font, size)
        if right:
            c.drawRightString(width - MARGIN, y, text)
        else:
            c.drawString(MARGIN, y, text)
        y -= gap

    put(CLINIC, "Helvetica-Bold", 20, gap=18)
    for line in ADDRESS:
        put(line, size=9, gap=12)
    c.line(MARGIN, y, width - MARGIN, y)
    y -= 36
    put(DATE, right=True, gap=30)
    for line in RECIPIENT:
        put(line)
    y -= 15
    put(SUBJECT, "Helvetica-Bold", gap=26)
    for paragraph in BODY:
        for line in simpleSplit(paragraph, "Helvetica", 11, room):
            put(line)
        y -= 9
    y -= 24
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

# ==== CONTENT: edit only this block ====
# Built-in fonts: non-Latin-1 characters (emoji, subscripts) print as black boxes.
PAGE_SIZE = letter  # or A4
SECTIONS_START_ON_NEW_PAGE = False
TITLE = "Building Condition Inspection Report"
DETAILS = [("Property", "Corran Quay Residences, 40 Tidewater Lane, Port Aldery"),
           ("Prepared for", "Corran Quay Owners' Association"),
           ("Inspected", "September 14, 2026, by Priya Ostrander, Halvard & Moss Building Surveyors")]
REFERENCE = "HM-2026-0388"
# Items are paragraphs or (subheading, paragraph) pairs.
SECTIONS = [
    ("Overview", [
        "We visually inspected the roof, elevations, garage, plant room and common parts of this block of 24 "
        "apartments, built in 1988.",
        "The building is in fair condition. The most serious findings are water entering at the north-east "
        "parapet and corroded railing brackets on six south balconies, which residents should not use until an "
        "engineer has assessed them. A fire door that no longer closes also needs prompt repair.",
    ]),
    ("Findings by area", [
        ("Roof and drainage: Fair", "The membrane has blistered near the north-east corner, where the parapet "
         "coping joints have opened. Three of the five outlets were partly blocked, and the fourth-floor "
         "corridor ceiling below the corner is stained and damp."),
        ("Elevations and balconies: Poor", "The brickwork is sound, but the railing brackets on six of the "
         "twelve south balconies are rusting where they enter the slab, and the concrete around two of them "
         "has cracked."),
        ("Structure: Good", "There is no sign of settlement or movement. The garage slab shows only fine "
         "shrinkage cracks."),
        ("Services: Fair", "The water heater, installed in 2009, is near the end of its life, and a plant-room "
         "valve is weeping."),
        ("Fire safety: Fair", "The alarm panel showed no faults and the extinguishers are in date, but the "
         "third-floor fire door to the east stairwell no longer closes on its own."),
    ]),
    ("Recommendations", [
        ("Within one week", "Keep residents off the six balconies and commission a structural engineer."),
        ("Within one month", "Repair the closer of the third-floor fire door."),
        ("Before winter", "Repoint the parapet coping, repair the membrane, clear the outlets, then repair the "
         "stained ceiling."),
        ("Within a year", "Replace the weeping valve and budget for a new water heater."),
    ]),
]
# ==== END CONTENT ====


def style(name, font="Times-Roman", size=11, **extra):
    return ParagraphStyle(name, fontName=font, fontSize=size, leading=size * 1.35, **extra)


TITLE_STYLE = style("title", "Helvetica-Bold", 22, spaceAfter=10)
# keepWithNext: no heading left alone at the foot of a page.
H1 = style("h1", "Helvetica-Bold", 15, spaceBefore=14, spaceAfter=6, keepWithNext=1)
H2 = style("h2", "Helvetica-Bold", 11.5, spaceBefore=8, spaceAfter=2, keepWithNext=1)
BODY = style("body", spaceAfter=7)


def para(text, style):
    # Paragraph parses markup: an unescaped "<" or "&" raises or loses text.
    return Paragraph(escape(text), style)


def footer(canvas, doc):
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(doc.leftMargin + 6, 40, f"{TITLE}, {REFERENCE}")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin - 6, 40, f"Page {canvas.getPageNumber()}")


def render(path):
    story = [para(TITLE, TITLE_STYLE)]
    story += [Paragraph(f"<b>{escape(k)}:</b> {escape(v)}", BODY) for k, v in DETAILS]
    for number, (heading, items) in enumerate(SECTIONS):
        if number and SECTIONS_START_ON_NEW_PAGE:
            story.append(PageBreak())
        story.append(para(heading, H1))
        for item in items:
            story += [para(item[0], H2), para(item[1], BODY)] if isinstance(item, tuple) else [para(item, BODY)]
    # invariant=1: byte-identical reruns. No pagesize means A4.
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

A titled table for price lists, schedules and results: here, lab results whose verdicts and highlights are computed from limits stated beneath it.

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

OUT = "<output_dir>/inputs/test_table.pdf"
if "<" in OUT or ">" in OUT:
    sys.exit(f"Refusing to run: OUT still holds a placeholder: {OUT}")
Path(OUT).parent.mkdir(parents=True, exist_ok=True)

# ==== CONTENT: edit only this block ====
# Built-in fonts: non-Latin-1 characters (emoji, subscripts) print as black boxes.
PAGE_SIZE = letter  # or A4; landscape(letter) when the columns cannot fit
LAB = "Oxbury Vale Water Testing Laboratory"
TITLE = "Drinking-water results, August 2026"
INFO = "Client: Marrowby District Water Board. Report OVW-26-0913."
COLUMNS = ["Sample", "Site", "Sampled"]
# (header, decimals shown, low limit, high limit); None means no limit.
MEASURES = [("pH", 1, 6.5, 9.0), ("Turbidity (NTU)", 1, None, 4.0),
            ("Nitrate (mg/L)", 1, None, 50.0), ("Lead (µg/L)", 1, None, 10.0)]
VERDICT = "Verdict"
COL_WIDTHS = [52, 108, 60, 34, 52, 44, 40, 46]  # points, one per column
SAMPLES = [
    ("L26-0801", "Ostry Reservoir outlet", "2026-08-11", (7.6, 0.4, 12.3, 0.8)),
    ("L26-0802", "Kestrel Lane standpipe", "2026-08-11", (7.5, 0.6, 12.9, 1.2)),
    ("L26-0803", "Marrowby Primary School, kitchen tap", "2026-08-11", (7.3, 0.3, 12.1, 2.4)),
    ("L26-0804", "14 Weaver's Row", "2026-08-12", (7.2, 0.4, 12.6, 14.2)),
    ("L26-0805", "Brackley Road hydrant", "2026-08-12", (7.5, 5.6, 12.8, 1.9)),
    ("L26-0806", "Fenwick Farm borehole", "2026-08-13", (6.3, 1.1, 61.4, 0.9)),
    ("L26-0807", "Low Moor pump house", "2026-08-13", (7.8, 0.2, 13.0, 0.6)),
    ("L26-0808", "Upper Heath estate", "2026-08-14", (7.6, 0.6, 12.0, 4.8)),
]
# ==== END CONTENT ====

NAVY, STRIPE, RULE = HexColor("#1F3B57"), HexColor("#EDF1F5"), HexColor("#B8C3CD")
FAIL_FILL, FAIL_INK = HexColor("#F7D6D2"), HexColor("#9A1B10")
# Paragraphs in cells ignore the table's FONT, TEXTCOLOR and ALIGN; their style rules.
CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=11)
HEAD = ParagraphStyle("head", CELL, fontName="Helvetica-Bold", textColor=white)
HEAD_RIGHT = ParagraphStyle("head_right", HEAD, alignment=TA_RIGHT)
TEXT = ParagraphStyle("text", CELL, fontSize=10, leading=14, spaceBefore=4)


def grid(last=-1):
    return [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, last), [white, STRIPE]),
        ("LINEBELOW", (0, 1), (-1, last), 0.25, RULE),
        ("BOX", (0, 0), (-1, last), 0.6, NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]


def shown(value, decimals):
    # Judge values as printed: 4.04 shown as "4.0" must not fail a 4.0 limit.
    return Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), ROUND_HALF_UP)


def limit(header, decimals, low, high):
    lo, hi = (None if v is None else shown(v, decimals) for v in (low, high))
    return f"{header} " + (f"at most {hi}" if lo is None else f"at least {lo}" if hi is None else f"{lo} to {hi}")


def render(path):
    # invariant=1: byte-identical reruns. No pagesize means A4.
    doc = SimpleDocTemplate(path, pagesize=PAGE_SIZE, title=TITLE, invariant=1)
    ncols, first = len(COLUMNS) + len(MEASURES) + 1, len(COLUMNS)
    frame = doc.width - 12  # 6 pt frame padding each side: 456 pt on Letter
    # A too-wide table runs off the page silently (Platypus checks only heights), so check the widths.
    if len(COL_WIDTHS) != ncols or sum(COL_WIDTHS) > frame:
        raise ValueError(f"Need {ncols} widths totalling at most {frame:.0f} pt")
    rows = [[Paragraph(escape(h), HEAD) for h in COLUMNS] + [Paragraph(escape(m[0]), HEAD_RIGHT) for m in MEASURES]
            + [Paragraph(escape(VERDICT), HEAD)]]
    # Highlights come after the stripes: backgrounds paint in command order.
    marks = grid() + [("ALIGN", (first, 1), (-2, -1), "RIGHT")]
    for r, (sample, site, date, values) in enumerate(SAMPLES, 1):
        if len(values) != len(MEASURES):
            raise ValueError(f"{sample} needs one value per measurement")
        printed = [shown(v, m[1]) for v, m in zip(values, MEASURES)]
        bad = [first + i for i, (p, (_, _, low, high)) in enumerate(zip(printed, MEASURES))
               if (low is not None and p < Decimal(str(low))) or (high is not None and p > Decimal(str(high)))]
        rows.append([sample, Paragraph(escape(site), CELL), date, *map(str, printed), "Fail" if bad else "Pass"])
        for c in (bad + [ncols - 1] if bad else []):
            marks += [("BACKGROUND", (c, r), (c, r), FAIL_FILL), ("TEXTCOLOR", (c, r), (c, r), FAIL_INK)]
    limits = "; ".join(limit(*m) for m in MEASURES)
    doc.build([
        Paragraph(escape(LAB), ParagraphStyle("lab", TEXT, fontName="Helvetica-Bold", fontSize=15, textColor=NAVY)),
        Paragraph(f"<b>{escape(TITLE)}</b>", TEXT),
        Paragraph(escape(INFO), TEXT),
        Table(rows, colWidths=COL_WIDTHS, repeatRows=1, hAlign="LEFT", style=marks, spaceBefore=10),
        Paragraph(f"<b>Limits:</b> {escape(limits)}. Highlighted values break a limit and fail the sample.", TEXT),
    ])


PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))
try:
    render(PART)
    os.replace(PART, OUT)
finally:
    Path(PART).unlink(missing_ok=True)
print(f"wrote {OUT}")
PYEOF
```

A table too wide for the page runs off it silently, so the widths are fixed and checked against the 456 pt Letter frame; use `landscape(letter)` when they cannot fit, `A4` for A4.

## Line-item document (composed)

The shape of an invoice, statement, purchase order or receipt: header, parties, line items, totals and a closing line, every figure computed with `Decimal`.

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

# ==== CONTENT: edit only this block ====
# Built-in fonts: non-Latin-1 characters (emoji, subscripts) print as black boxes.
PAGE_SIZE = letter  # or A4
KIND, NUMBER = "Invoice", "TPW-2026-0187"
DATES = [("Issue date", "2026-09-15"), ("Due date", "2026-10-15")]
ISSUER = ["Tallowmere Print Works", "7 Grainstore Yard, Tallowmere", "VAT ID ZZ 481 209 336"]
RECIPIENT = ["Kessling Vale Amateur Rugby Club", "Attn. Marit Olsberg, secretary", "Kessling Vale"]
CURRENCY, VAT_PERCENT = "€", "21"
COLUMNS = ["Description", "Qty", "Unit price", "Amount"]
COL_WIDTHS = [247, 44, 70, 72]  # points, one per column
LINE_ITEMS = [  # prices are strings so Decimal reads them exactly
    ("Match-day programmes, 24 pages, saddle-stitched, full colour on 130 gsm silk, with a "
     "foil-stamped crest", 400, "1.85"),
    ("Membership cards, laminated, printed on both sides", 350, "0.62"),
    ("Roll-up banner, 85 × 200 cm, with carry case", 2, "89.00"),
]
TOTAL_LABEL = "Total due"
CLOSING = "Please pay by bank transfer to IBAN ZZ47 0012 3456 7890 1234 56 by the due date."
# ==== END CONTENT ====

NAVY, STRIPE, RULE = HexColor("#1F3B57"), HexColor("#EDF1F5"), HexColor("#B8C3CD")
# A plain cell string never wraps (it prints over the next column), so descriptions are
# Paragraphs, which ignore the table's FONT, TEXTCOLOR and ALIGN.
CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=11)
TEXT = ParagraphStyle("text", CELL, fontSize=10, leading=14)
RIGHT = ParagraphStyle("right", TEXT, alignment=TA_RIGHT)
BIG = ParagraphStyle("big", TEXT, fontName="Helvetica-Bold", fontSize=19, leading=24, textColor=NAVY)
CENT = Decimal("0.01")


def grid(last=-1):
    return [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, last), [white, STRIPE]),
        ("LINEBELOW", (0, 1), (-1, last), 0.25, RULE),
        ("BOX", (0, 0), (-1, last), 0.6, NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]


def money(value):
    return f"{CURRENCY}{value:,.2f}"


def party(label, lines):
    first = f'<font size="8">{label}</font><br/><b>{escape(lines[0])}</b>'
    return Paragraph("<br/>".join([first] + [escape(line) for line in lines[1:]]), TEXT)


def render(path):
    # invariant=1: byte-identical reruns. No pagesize means A4.
    doc = SimpleDocTemplate(path, pagesize=PAGE_SIZE, title=f"{KIND} {NUMBER}", invariant=1)
    frame, width = doc.width - 12, sum(COL_WIDTHS)  # 6 pt frame padding each side: 456 pt on Letter
    # A too-wide table runs off the page silently (Platypus checks only heights), so check the widths.
    if len(COL_WIDTHS) != len(COLUMNS) or width > frame:
        raise ValueError(f"Need {len(COLUMNS)} widths totalling at most {frame:.0f} pt")
    rows, subtotal = [COLUMNS], Decimal(0)
    for description, quantity, price in LINE_ITEMS:
        # Price rounded to the cent it prints at, so quantity x price = amount shown.
        price = Decimal(price).quantize(CENT, ROUND_HALF_UP)
        amount = (quantity * price).quantize(CENT, ROUND_HALF_UP)
        subtotal += amount
        rows.append([Paragraph(escape(description), CELL), f"{quantity:,}", money(price), money(amount)])
    vat = (subtotal * Decimal(VAT_PERCENT) / 100).quantize(CENT, ROUND_HALF_UP)
    total = subtotal + vat
    n = len(rows) - 1
    rows += [["", "", "Subtotal", money(subtotal)], ["", "", f"VAT {VAT_PERCENT}%", money(vat)],
             ["", "", TOTAL_LABEL, money(total)]]
    style = grid(n) + [("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 10.5),
                       ("LINEABOVE", (2, -1), (-1, -1), 1, NAVY)]
    meta = "<br/>".join(f"{escape(k)}  <b>{escape(v)}</b>" for k, v in [(f"{KIND} no.", NUMBER)] + DATES)
    kind = Paragraph(escape(KIND.upper()), ParagraphStyle("kind", BIG, alignment=TA_RIGHT))
    head = Table(
        [[Paragraph(escape(ISSUER[0]), BIG), [kind, Paragraph(meta, RIGHT)]],
         [party("FROM", ISSUER), party("TO", RECIPIENT)]],
        colWidths=[width * 0.55, width * 0.45], hAlign="LEFT",
        style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, NAVY),
               ("TOPPADDING", (0, 1), (-1, 1), 14)],
    )
    items = Table(rows, colWidths=COL_WIDTHS, repeatRows=1, hAlign="LEFT", style=style, spaceBefore=18, spaceAfter=18)
    doc.build([head, items, Paragraph(escape(CLOSING), TEXT)])
    return total


PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))
try:
    total = render(PART)
    os.replace(PART, OUT)
finally:
    Path(PART).unlink(missing_ok=True)
print(f"wrote {OUT} (total {total:,.2f})")
PYEOF
```

Descriptions wrap in their column; `PAGE_SIZE = A4` gives A4. For a purchase order, credit note or receipt, edit `KIND`, `DATES`, `TOTAL_LABEL` and `CLOSING`, with the buyer as `ISSUER` on a purchase order.

## Verify

```bash
head -c 5 "<output_dir>/inputs/<name>.pdf"; echo; wc -c "<output_dir>/inputs/<name>.pdf"
uv run --quiet --no-project python -c "import re, sys; print('pages:', len(re.findall(rb'/Type\s*/Page[^s]', open(sys.argv[1], 'rb').read())))" "<output_dir>/inputs/<name>.pdf"
```

The page count needs no packages, so it runs under whichever interpreter Step 2 resolved — the `uv run` above on rung 1, the absolute venv interpreter path on rung 2. Do not reach for a bare `python3`: a machine that got `uv` from the installer has no such command.

Expect `%PDF-`, a size in the kilobytes, and the page count the brief asked for. A failed render is cleaned up as the skill's step 4 says, partial file included, before anything is rerun.
