# PNG recipes — Pillow and matplotlib

Read this at step 4 of the skill when the format is `png`, before writing any code; its **Verify** section is step 5's check.

Recipes for the `png` format of `/pipelex-synthetic-inputs`. Each one is a complete, runnable block: the first line is the **runner line** resolved in the skill's Step 2 (`uv run --quiet --no-project --with pillow --with matplotlib --with numpy python << 'PYEOF'` on the `uv` rung, `<the absolute venv path Step 2 printed>/bin/python << 'PYEOF'` on the venv rung — substitute the path, never the `$VENV` reference, which is unset in a fresh shell), and everything below it is plain Python. Copy the block, replace the content at the top of the script with what Step 3 drafted, set the output path, run.

`Pillow` is MIT-CMU, `matplotlib` PSF-style and `numpy` BSD; every recipe below was executed and looked at under Pillow 12.3.0, matplotlib 3.11.1 and numpy 2.5.2 before it was committed.

## Which recipe for which brief

| The brief asks for | Category | Recipe |
|---|---|---|
| a bar, line, pie or scatter chart of some data | `chart` | [Chart (matplotlib)](#chart-matplotlib) |
| a flowchart, process, architecture or org chart | `diagram` | [Diagram (Pillow)](#diagram-pillow) |
| a scanned or photographed page — an invoice, receipt, form, letter — for OCR or document understanding | `document_scan` | [Scanned document (Pillow)](#scanned-document-pillow) |
| a printed form someone wrote on — ticks, a corrected quantity, a remark, a signature | `document_scan` | [Handwritten marks (Pillow)](#handwritten-marks-pillow) |
| an app or web screen — a dashboard, a list, a settings page — for UI understanding | `screenshot` | [App screenshot (Pillow)](#app-screenshot-pillow) |

## Conventions shared by every recipe

- Output path: `<output_dir>/inputs/<name>.png` — replace with the request's `target`.
- Sizes: charts, diagrams and screenshots at **1200×800**; a `document_scan` at **1240×1754**, which is A4 at 150 dpi. Raise them only when the method's input description asks. Pixel size is not file size here: the first three come out in the tens of kilobytes, while a `document_scan` lands in the low megabytes because `scannerize()`'s grain is noise and noise does not compress. Drop to 100 dpi (827×1169) or lower `grain` if the upload limit is the problem.
- Every Pillow recipe opens with the same **preamble** — the `font()` helper and, where labels are laid out, `wrap()`. No recipe ever names a system font path: `font()` takes DejaVu Sans from matplotlib's own bundled copy and falls back to the face Pillow ships. Both are always present, because both packages are in the `png` set.
- Randomness is seeded (`SEED` in the content block), so regenerating a file produces the same file.
- Fictional content only: made-up companies, people, ids, addresses.
- Numbers the method will read must be consistent — the recipes compute totals from the line items rather than restating them.

The preamble, for reference; it is already inside each recipe below, so there is nothing to paste separately:

```python
_FONTS = {}


def font(size, bold=False):
    """DejaVu Sans, bundled with matplotlib; Pillow's built-in face as a fallback."""
    key = (size, bold)
    if key not in _FONTS:
        try:
            path = font_manager.findfont("DejaVu Sans:bold" if bold else "DejaVu Sans")
            _FONTS[key] = ImageFont.truetype(path, size)
        except Exception:
            _FONTS[key] = ImageFont.load_default(size=size)
    return _FONTS[key]
```

## Chart (matplotlib)

Charts are the one category where the honest tool is the one real charts are made with. The content block carries the kind, the labels and the series; the four kinds are branches of the same script.

```bash
uv run --quiet --no-project --with pillow --with matplotlib --with numpy python << 'PYEOF'
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "<output_dir>/inputs/test_chart.png"
assert "<" not in OUT and ">" not in OUT, f"OUT still holds a placeholder: {OUT}"
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
# Render beside the target and rename on success, so a crash never truncates an existing file.
PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))

# --- content -----------------------------------------------------------
KIND = "bar"                      # bar | line | pie | scatter
TITLE = "Units shipped by region"
XLABEL = "Quarter"
YLABEL = "Units shipped (thousands)"
LABELS = ["Q1", "Q2", "Q3", "Q4"]
SERIES = [                        # name, values (one per label)
    ("North", [12.4, 13.8, 15.1, 16.7]),
    ("South", [9.2, 9.9, 11.4, 12.0]),
    ("Export", [4.1, 5.6, 5.2, 7.3]),
]
# -----------------------------------------------------------------------

WIDTH, HEIGHT, DPI = 1200, 800, 150
COLORS = ["#2f6f9f", "#c25e3a", "#4f9d69", "#8a6bb1", "#c9a227"]

fig, ax = plt.subplots(figsize=(WIDTH / DPI, HEIGHT / DPI), dpi=DPI)

if KIND == "bar":
    step = 0.8 / len(SERIES)
    for index, (name, values) in enumerate(SERIES):
        offset = -0.4 + step * (index + 0.5)
        ax.bar([x + offset for x in range(len(LABELS))], values, width=step * 0.9,
               label=name, color=COLORS[index % len(COLORS)])
    ax.set_xticks(range(len(LABELS)), LABELS)
elif KIND == "line":
    for index, (name, values) in enumerate(SERIES):
        ax.plot(LABELS, values, marker="o", label=name, color=COLORS[index % len(COLORS)])
elif KIND == "scatter":
    for index, (name, values) in enumerate(SERIES):
        ax.scatter(range(len(values)), values, label=name, s=60,
                   color=COLORS[index % len(COLORS)])
    ax.set_xticks(range(len(LABELS)), LABELS)
elif KIND == "pie":
    ax.pie([values[-1] for _, values in SERIES], labels=[name for name, _ in SERIES],
           autopct="%1.1f%%", colors=COLORS[: len(SERIES)])
    ax.set_aspect("equal")

if KIND != "pie":
    ax.set_xlabel(XLABEL)
    ax.set_ylabel(YLABEL)
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend()

ax.set_title(TITLE, fontsize=14, fontweight="bold")
fig.tight_layout()
fig.savefig(PART, dpi=DPI, format="png")
os.replace(PART, OUT)
print("wrote", OUT)
PYEOF
```

`figsize=(WIDTH / DPI, HEIGHT / DPI)` with `fig.tight_layout()` is what makes the output exactly the declared pixel size. Do not add `bbox_inches="tight"` to `savefig` — it crops the figure and the size no longer matches what the report claims. matplotlib writes PNGs with an alpha channel, so this recipe's file opens as `RGBA` where the Pillow recipes give `RGB`; both are fine.

A pie chart takes one number per slice, so this branch uses the last value of each series. Give it the series you actually mean when the brief is a breakdown rather than a trend.

## Diagram (Pillow)

Nodes on a grid, arrows between them. The content block is a node list — id, label, column, row, role — and an edge list; the layout, the arrowheads and the label wrapping are handled below it. `role` picks the colour: `start`, `step`, `decision`, `end`.

```bash
uv run --quiet --no-project --with pillow --with matplotlib --with numpy python << 'PYEOF'
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager

OUT = "<output_dir>/inputs/test_diagram.png"
assert "<" not in OUT and ">" not in OUT, f"OUT still holds a placeholder: {OUT}"
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
# Render beside the target and rename on success, so a crash never truncates an existing file.
PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))

# --- content -----------------------------------------------------------
TITLE = "Order fulfilment"
NODES = [                         # id, label, column, row, role
    ("intake",  "Order received",      0, 1, "start"),
    ("check",   "Stock available?",    1, 1, "decision"),
    ("pick",    "Pick and pack",       2, 0, "step"),
    ("backord", "Create back order",   2, 2, "step"),
    ("ship",    "Ship to customer",    3, 0, "step"),
    ("done",    "Order closed",        4, 1, "end"),
]
EDGES = [                         # from, to, label
    ("intake", "check", ""),
    ("check", "pick", "yes"),
    ("check", "backord", "no"),
    ("pick", "ship", ""),
    ("ship", "done", ""),
    ("backord", "done", "when restocked"),
]
# -----------------------------------------------------------------------

WIDTH, HEIGHT = 1200, 800
BACKGROUND = "#f7f7f4"
ROLE_COLORS = {                   # fill, outline
    "start":    ("#dbe8f2", "#2f6f9f"),
    "step":     ("#ffffff", "#5a6470"),
    "decision": ("#fdf0e2", "#c25e3a"),
    "end":      ("#e2efe6", "#4f9d69"),
}

_FONTS = {}


def font(size, bold=False):
    """DejaVu Sans, bundled with matplotlib; Pillow's built-in face as a fallback."""
    key = (size, bold)
    if key not in _FONTS:
        try:
            path = font_manager.findfont("DejaVu Sans:bold" if bold else "DejaVu Sans")
            _FONTS[key] = ImageFont.truetype(path, size)
        except Exception:
            _FONTS[key] = ImageFont.load_default(size=size)
    return _FONTS[key]


image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
draw = ImageDraw.Draw(image)


def wrap(draw, text, face, max_width):
    """Greedy wrap on measured width, so a label never spills out of its box."""
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=face) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    return lines + [current] if current else lines


def fit_label(text, max_width, max_height, bold=False):
    """The largest size at which the wrapped label fits the box, both ways.

    Box height shrinks as the graph gains rows, so a two-line label that is
    comfortable in a four-row diagram overflows a seven-row one. Measuring
    beats guessing: step down until it fits, and keep the smallest size rather
    than drawing outside the box.
    """
    for size in (19, 17, 15, 13, 11):
        face = font(size, bold=bold)
        lines = wrap(draw, text, face, max_width)
        line_h = face.getbbox("Ag")[3] + 6
        if line_h * len(lines) <= max_height and all(draw.textlength(line, font=face) <= max_width for line in lines):
            return face, lines, line_h
    return face, lines, line_h


def border_point(box, towards):
    """Where the segment from the box centre to `towards` leaves the box."""
    x0, y0, x1, y1 = box[:4]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = towards[0] - cx, towards[1] - cy
    if dx == 0 and dy == 0:
        return cx, cy
    scale = min(
        abs((x1 - cx) / dx) if dx else math.inf,
        abs((y1 - cy) / dy) if dy else math.inf,
    )
    return cx + dx * scale, cy + dy * scale


draw.text((60, 44), TITLE, font=font(30, bold=True), fill="#20262e")

# Two nodes in one cell overdraw exactly and the edge between them becomes a
# zero-length arrow: the diagram loses a step and still reads as correct. Same for a
# reused id, which `boxes` collapses. Both happen when a step is added to a branch.
cells = [(node[2], node[3]) for node in NODES]
assert len(set(cells)) == len(cells), f"two nodes share a grid cell: {sorted(c for c in set(cells) if cells.count(c) > 1)}"
ids = [node[0] for node in NODES]
assert len(set(ids)) == len(ids), f"duplicate node id: {sorted(i for i in set(ids) if ids.count(i) > 1)}"
assert all(edge[0] in ids and edge[1] in ids for edge in EDGES), "an edge names a node that is not in NODES"

columns = max(node[2] for node in NODES) + 1
rows = max(node[3] for node in NODES) + 1
left, top, right, bottom = 60, 130, WIDTH - 60, HEIGHT - 60
cell_w = (right - left) / columns
cell_h = (bottom - top) / rows
box_w, box_h = min(cell_w * 0.78, 220), min(cell_h * 0.52, 96)

boxes = {}
for node_id, label, column, row, role in NODES:
    cx = left + cell_w * (column + 0.5)
    cy = top + cell_h * (row + 0.5)
    boxes[node_id] = (cx - box_w / 2, cy - box_h / 2, cx + box_w / 2, cy + box_h / 2, role, label)

for source, target, label in EDGES:
    a, b = boxes[source], boxes[target]
    a_center = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
    b_center = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    start = border_point(a, b_center)
    end = border_point(b, a_center)
    draw.line([start, end], fill="#5a6470", width=3)

    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    head = 15
    draw.polygon(
        [
            end,
            (end[0] - head * math.cos(angle - 0.4), end[1] - head * math.sin(angle - 0.4)),
            (end[0] - head * math.cos(angle + 0.4), end[1] - head * math.sin(angle + 0.4)),
        ],
        fill="#5a6470",
    )

    if label:
        mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
        text_box = draw.textbbox((mx, my), label, font=font(16), anchor="mm")
        draw.rectangle([text_box[0] - 6, text_box[1] - 3, text_box[2] + 6, text_box[3] + 3],
                       fill=BACKGROUND)
        draw.text((mx, my), label, font=font(16), fill="#3c4450", anchor="mm")

for node_id, (x0, y0, x1, y1, role, label) in boxes.items():
    fill, outline = ROLE_COLORS.get(role, ROLE_COLORS["step"])
    draw.rounded_rectangle([x0, y0, x1, y1], radius=12, fill=fill, outline=outline, width=3)
    face, lines, line_h = fit_label(label, box_w - 28, box_h - 12, bold=role in ("start", "end"))
    cy = (y0 + y1) / 2 - line_h * (len(lines) - 1) / 2
    for index, line in enumerate(lines):
        draw.text(((x0 + x1) / 2, cy + line_h * index), line, font=face, fill="#20262e", anchor="mm")

image.save(PART, format="PNG")
os.replace(PART, OUT)
print("wrote", OUT, image.size)
PYEOF
```

Labels are sized to fit: `fit_label()` steps the font down until the wrapped label fits its box in both directions, because box height shrinks as the graph gains rows and a two-line label comfortable in a four-row diagram will spill out of a seven-row one. Keep labels to a few words anyway — a diagram whose boxes are set in 11px is telling you the graph wants fewer nodes or shorter names.

Columns are the reading direction and rows are the lanes, so a left-to-right flow numbers columns 0, 1, 2… and a top-to-bottom one numbers rows. Branches sit on different rows of the same column, as `pick` and `backord` do above. The grid is spaced from the largest column and row index, so leaving a gap in the numbering widens the drawing.

## Scanned document (Pillow)

A page rendered crisply and then put through `scannerize()` — a slight skew, a paper tint, grain, a soft vignette. This is the recipe for anything a method will OCR. The content block below is an invoice, the most common brief; the same layout serves a receipt, a delivery note or a statement with different labels, and a letter by dropping the table.

`scannerize()` is a plain function on an image, so another recipe can end with it — a `screenshot` printed and scanned, a `chart` pasted into a report page. It is not free-standing, though: copy the function **and** its two imports (`import numpy as np`, and `ImageFilter` in the `PIL` import line), because the `diagram` and `screenshot` recipes carry neither. A `chart` is a matplotlib figure rather than a PIL image, so save it first and reopen it with `Image.open(OUT)` before passing it in.

```bash
uv run --quiet --no-project --with pillow --with matplotlib --with numpy python << 'PYEOF'
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from matplotlib import font_manager

OUT = "<output_dir>/inputs/test_scan.png"
assert "<" not in OUT and ">" not in OUT, f"OUT still holds a placeholder: {OUT}"
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
# Render beside the target and rename on success, so a crash never truncates an existing file.
PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))

# --- content -----------------------------------------------------------
SELLER = ["Acme Hardware Supply", "18 rue des Forges", "69007 Lyon, France",
          "VAT FR12345678901", "contact@acme-hardware.example"]
BUYER = ["Bill to", "Example Constructions SARL", "4 avenue du Chantier", "21000 Dijon, France"]
TITLE = "INVOICE"
META = [("Invoice no.", "INV-2026-0042"), ("Date", "2026-03-14"), ("Due date", "2026-04-13")]
INTRO = ("Goods delivered to the Dijon site on 2026-03-12 against purchase order "
         "PO-8841. Payment is due within 30 days by bank transfer.")
COLUMNS = ["Description", "Qty", "Unit price", "Amount"]
ITEMS = [                         # description, quantity, unit price
    ("M8 hex bolts, zinc plated, box of 100", 12, 14.90),
    ("Cordless drill 18V with two batteries", 2, 189.00),
    ("Safety goggles, clear polycarbonate", 25, 6.50),
    ("Wood screws 4x40, box of 200", 8, 11.20),
    ("Delivery to site, Dijon", 1, 45.00),
]
TAX_RATE = 0.20
CURRENCY = "EUR"
FOOTER = ("Acme Hardware Supply SAS - share capital EUR 50,000 - RCS Lyon 812 345 678 - "
          "IBAN FR76 3000 1007 9412 3456 7890 185")
SEED = 20260902
# -----------------------------------------------------------------------

WIDTH, HEIGHT = 1240, 1754       # A4 at 150 dpi
MARGIN = 96
PAPER = "#ffffff"
INK = "#1b1b1b"

_FONTS = {}


def font(size, bold=False):
    """DejaVu Sans, bundled with matplotlib; Pillow's built-in face as a fallback."""
    key = (size, bold)
    if key not in _FONTS:
        try:
            path = font_manager.findfont("DejaVu Sans:bold" if bold else "DejaVu Sans")
            _FONTS[key] = ImageFont.truetype(path, size)
        except Exception:
            _FONTS[key] = ImageFont.load_default(size=size)
    return _FONTS[key]


def wrap(draw, text, face, max_width):
    """Greedy wrap on measured width."""
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=face) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    return lines + [current] if current else lines


def scannerize(image, seed=0, angle=0.7, grain=7.0, blur=0.7, tint=(1.0, 0.985, 0.955)):
    """Make a crisply rendered page look photocopied: skew, paper tint, grain, vignette.

    Takes any PIL image. The convert is what lets a chart through: matplotlib
    writes RGBA, and the tint below is a 3-channel multiply that would raise
    a broadcast error on a 4-channel array.
    """
    image = image.convert("RGB")
    rng = np.random.default_rng(seed)
    skew = rng.uniform(-angle, angle)
    image = image.rotate(skew, resample=Image.BICUBIC, fillcolor=(246, 244, 238))
    image = image.filter(ImageFilter.GaussianBlur(blur))

    pixels = np.asarray(image, dtype=np.float32)
    pixels *= np.array(tint, dtype=np.float32)
    pixels += rng.normal(0.0, grain, pixels.shape).astype(np.float32)

    height, width = pixels.shape[:2]
    ys, xs = np.mgrid[0:height, 0:width]
    radius = np.sqrt(((xs / width - 0.5) * 2) ** 2 + ((ys / height - 0.5) * 2) ** 2)
    pixels *= (1.0 - 0.16 * np.clip(radius - 0.35, 0, None) ** 2)[..., None]

    return Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8), "RGB")


page = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
draw = ImageDraw.Draw(page)
right = WIDTH - MARGIN
y = MARGIN

draw.text((MARGIN, y), SELLER[0], font=font(30, bold=True), fill=INK)
y += 44
for line in SELLER[1:]:
    draw.text((MARGIN, y), line, font=font(19), fill=INK)
    y += 27

draw.text((right, MARGIN), TITLE, font=font(40, bold=True), fill=INK, anchor="ra")
meta_y = MARGIN + 62
meta_key_x = right - max(draw.textlength(value, font=font(19, bold=True)) for _, value in META) - 24
for key, value in META:
    draw.text((meta_key_x, meta_y), key, font=font(19), fill="#444444", anchor="ra")
    draw.text((right, meta_y), value, font=font(19, bold=True), fill=INK, anchor="ra")
    meta_y += 28

y = max(y, meta_y) + 30
draw.line([(MARGIN, y), (right, y)], fill=INK, width=2)
y += 30

for index, line in enumerate(BUYER):
    draw.text((MARGIN, y), line, font=font(20, bold=index == 0), fill=INK)
    y += 28
y += 24

for line in wrap(draw, INTRO, font(20), right - MARGIN):
    draw.text((MARGIN, y), line, font=font(20), fill=INK)
    y += 30
y += 26

WIDTHS = [560, 110, 180, 190]
xs = [MARGIN]
for width in WIDTHS[:-1]:
    xs.append(xs[-1] + width)

header_bottom = y + 38
draw.rectangle([MARGIN, y, right, header_bottom], fill="#ececec")
for index, title in enumerate(COLUMNS):
    anchor_x = xs[index] + 10 if index == 0 else xs[index] + WIDTHS[index] - 10
    draw.text((anchor_x, y + 10), title, font=font(19, bold=True), fill=INK,
              anchor="la" if index == 0 else "ra")
y = header_bottom

subtotal = 0.0
for description, quantity, unit_price in ITEMS:
    amount = quantity * unit_price
    subtotal += amount
    # The description is the one cell that can be long. Drawn unwrapped it runs into the
    # Qty column and destroys the number the method is there to read, so wrap it and let
    # the row grow instead.
    description_lines = wrap(draw, description, font(19), WIDTHS[0] - 20)
    row_bottom = y + max(36, 9 + 27 * len(description_lines))
    for offset, line in enumerate(description_lines):
        draw.text((xs[0] + 10, y + 9 + 27 * offset), line, font=font(19), fill=INK, anchor="la")
    for index, cell in enumerate([str(quantity), f"{unit_price:,.2f}", f"{amount:,.2f}"], start=1):
        draw.text((xs[index] + WIDTHS[index] - 10, y + 9), cell, font=font(19), fill=INK, anchor="ra")
    draw.line([(MARGIN, row_bottom), (right, row_bottom)], fill="#b6b6b6", width=1)
    y = row_bottom

tax = round(subtotal * TAX_RATE, 2)
total = round(subtotal + tax, 2)
print("total", f"{total:.2f}")
# The footer sits at a fixed y, and Pillow discards anything drawn past the canvas
# without a word — so a long ITEMS list pushes the totals off the page and the script
# still exits 0 printing a total the image does not contain. Fail loudly instead.
assert y + 110 < HEIGHT - MARGIN - 56, (
    f"{len(ITEMS)} items overrun the page (table ends at y={y:.0f}); "
    "split them across several pages, each rendered as its own file"
)
y += 14
for label, value, bold in [
    ("Subtotal", f"{subtotal:,.2f}", False),
    (f"VAT {TAX_RATE:.0%}", f"{tax:,.2f}", False),
    (f"Total due ({CURRENCY})", f"{total:,.2f}", True),
]:
    draw.text((xs[2] + WIDTHS[2] - 10, y), label, font=font(20, bold=bold), fill=INK, anchor="ra")
    draw.text((right, y), value, font=font(20, bold=bold), fill=INK, anchor="ra")
    y += 32
draw.line([(xs[2], y - 38), (right, y - 38)], fill=INK, width=2)

footer_y = HEIGHT - MARGIN - 40
draw.line([(MARGIN, footer_y - 16), (right, footer_y - 16)], fill="#b6b6b6", width=1)
for line in wrap(draw, FOOTER, font(16), right - MARGIN):
    draw.text((MARGIN, footer_y), line, font=font(16), fill="#555555")
    footer_y += 22

scannerize(page, seed=SEED).save(PART, format="PNG")
os.replace(PART, OUT)
print("wrote", OUT, (WIDTH, HEIGHT))
PYEOF
```

Turn the dials in `scannerize()` down to `angle=0.2, grain=3, blur=0.4` for a clean office scan, and up to `angle=1.6, grain=14, blur=1.2` for a bad phone photo of a crumpled receipt. Leave them alone unless the method's difficulty is the point — a page nobody can read is not a better test.

To render a letter or a form instead of an invoice, drop the column-header block (`WIDTHS` through the `COLUMNS` loop), the item loop and the totals block, and keep the letterhead, the paragraph flow and the footer — nothing below them depends on any of the three. Drop the column header too, not just the rows: keeping it leaves a grey `Description | Qty | Unit price | Amount` bar with nothing under it. `SELLER` and `BUYER` are then just the sender and the addressee; rename them if it helps you keep the content straight, since only the content block names them. To fill several pages, render each page and save them as separate files; a multi-page TIFF is not covered here.

## Handwritten marks (Pillow)

A printed form that someone has written on: ticks in a column, a corrected quantity, a remark, a signature. This is a `document_scan` whose brief has handwriting in it — a delivery note checked at the goods-in door, a signed form, an annotated receipt. The handwriting is simulated: each glyph of a handwriting-style font gets its own size, tilt, baseline and ink pressure, the line is slanted, and the page is then scanned like any other. It reads more easily than a real hand, and the skill says so to the user in one line.

The font comes from the first family of `HAND_FAMILIES` the machine has: macOS ships Bradley Hand, Noteworthy and Chalkboard SE, Windows Segoe Print, Ink Free and Comic Sans MS. A machine with none of them, which is most Linux machines, falls back to DejaVu Sans Oblique, bundled with matplotlib; the recipe prints a note when it does, and the report must pass it on, because slanted print is a weaker test than a hand. To write on another recipe's page — the invoice of [Scanned document (Pillow)](#scanned-document-pillow), say — copy `hand_font()`, `ink()`, `handwrite()` and `tick()` with their imports (`ImageChops` joins the `PIL` line), and paste their layers onto the page before `scannerize()`.

```bash
uv run --quiet --no-project --with pillow --with matplotlib --with numpy python << 'PYEOF'
import logging
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from matplotlib import font_manager

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)  # several hand fonts ship a bold face only
OUT = "<output_dir>/inputs/test_handwritten.png"
assert "<" not in OUT and ">" not in OUT, f"OUT still holds a placeholder: {OUT}"
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
# Render beside the target and rename on success, so a crash never truncates an existing file.
PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))

# --- content -----------------------------------------------------------
TITLE = "GOODS RECEIVED NOTE"
HEADER = [("Supplier", "Acme Hardware Supply"), ("Delivery note", "DN-2026-0117"),
          ("Received at", "Example Constructions, Dijon site")]
COLUMNS = ["Item", "Description", "Shipped", "Received"]
ROWS = [                      # item, description, quantity shipped, quantity received by hand (None = a tick)
    ("AHS-1001", "M8 hex bolts, zinc plated, box of 100", 12, None),
    ("AHS-2210", "Safety goggles, clear polycarbonate", 25, 22),
    ("AHS-3002", "Wood screws 4x40, box of 200", 8, None),
]
REMARK = "3 goggles cracked - sent back"
SIGNATURE = "J. Example"
DATE = "12.03.26"
INK = (22, 42, 156)           # blue ballpoint; (35, 35, 40) for black
SEED = 20260924
# -----------------------------------------------------------------------

WIDTH, HEIGHT = 1240, 874     # A5 landscape at 150 dpi
MARGIN = 80
TEXT = "#1b1b1b"
HAND_FAMILIES = ["Bradley Hand", "Noteworthy", "Chalkboard SE", "Segoe Print", "Ink Free", "Comic Sans MS"]

_FONTS = {}


def font(size, bold=False):
    """DejaVu Sans, bundled with matplotlib; Pillow's built-in face as a fallback."""
    key = (size, bold)
    if key not in _FONTS:
        try:
            path = font_manager.findfont("DejaVu Sans:bold" if bold else "DejaVu Sans")
            _FONTS[key] = ImageFont.truetype(path, size)
        except Exception:
            _FONTS[key] = ImageFont.load_default(size=size)
    return _FONTS[key]


def hand_font():
    """The first handwriting family installed, or DejaVu Sans Oblique with a note to pass on."""
    for family in HAND_FAMILIES:
        try:
            return font_manager.findfont(font_manager.FontProperties(family=family), fallback_to_default=False)
        except ValueError:
            continue
    print("note: no handwriting font on this machine; the marks fall back to DejaVu Sans Oblique, "
          "which reads as slanted print rather than a hand")
    return font_manager.findfont("DejaVu Sans:italic")


HAND = hand_font()


def ink(mask, rng, slant):
    """Turn a coverage mask into pen ink: a slant, a soft edge, uneven pressure, cropped to the strokes."""
    mask = mask.transform(mask.size, Image.AFFINE, (1, slant, -slant * mask.height, 0, 1, 0), resample=Image.BICUBIC)
    alpha = np.asarray(mask.filter(ImageFilter.GaussianBlur(0.55)), dtype=np.float32)
    pressure = rng.normal(0.0, 1.0, alpha.shape).astype(np.float32)
    pressure = np.asarray(Image.fromarray(np.clip(128 + 60 * pressure, 0, 255).astype(np.uint8))
                          .filter(ImageFilter.GaussianBlur(3)), dtype=np.float32) / 255.0
    alpha *= 0.7 + 0.5 * pressure
    rgba = np.zeros(alpha.shape + (4,), dtype=np.uint8)
    rgba[..., :3] = INK
    rgba[..., 3] = np.clip(alpha, 0, 255).astype(np.uint8)
    layer = Image.fromarray(rgba, "RGBA")
    return layer.crop(layer.getbbox())


def handwrite(text, size, rng, slant=0.18):
    """Write text glyph by glyph, each with its own size, tilt, baseline and darkness."""
    mask = Image.new("L", (int(size * 0.9 * len(text)) + 4 * size, 3 * size), 0)
    x, wander = float(size), 0.0
    for character in text:
        face = ImageFont.truetype(HAND, max(10, int(round(size * rng.uniform(0.92, 1.08)))))
        advance = face.getlength(character)
        if not character.isspace():
            glyph = Image.new("L", (int(advance) + 2 * size, 3 * size), 0)
            ImageDraw.Draw(glyph).text((size, 2 * size), character, font=face, anchor="ls",
                                       fill=int(255 * rng.uniform(0.8, 1.0)))
            glyph = glyph.rotate(rng.uniform(-5, 5), resample=Image.BICUBIC, center=(size + advance / 2, 2 * size))
            wander = float(np.clip(wander + rng.normal(0, 0.8), -3, 3))
            placed = Image.new("L", mask.size, 0)
            placed.paste(glyph, (int(x - size), int(wander)))
            mask = ImageChops.lighter(mask, placed)
        x += advance * rng.uniform(0.9, 1.03)
    return ink(mask, rng, slant)


def tick(rng, size=30):
    """A quick check mark: a short stroke down, a long flick up to the right."""
    mask = Image.new("L", (3 * size, 3 * size), 0)
    start, turn, end = (0.7 * size, 1.6 * size), (1.1 * size, 2.2 * size), (2.4 * size, 0.6 * size)
    points = [(start[0] + (turn[0] - start[0]) * t, start[1] + (turn[1] - start[1]) * t) for t in np.linspace(0, 1, 8)]
    points += [(turn[0] + (end[0] - turn[0]) * t + rng.normal(0, 0.5), turn[1] + (end[1] - turn[1]) * t + 3 * np.sin(np.pi * t))
               for t in np.linspace(0, 1, 14)]
    ImageDraw.Draw(mask).line(points, fill=235, width=3, joint="curve")
    return ink(mask, rng, slant=0.05)


def scannerize(image, seed=0, angle=0.7, grain=7.0, blur=0.7, tint=(1.0, 0.985, 0.955)):
    """Make a crisply rendered page look photocopied: skew, paper tint, grain, vignette."""
    image = image.convert("RGB")
    rng = np.random.default_rng(seed)
    image = image.rotate(rng.uniform(-angle, angle), resample=Image.BICUBIC, fillcolor=(246, 244, 238))
    image = image.filter(ImageFilter.GaussianBlur(blur))
    pixels = np.asarray(image, dtype=np.float32)
    pixels *= np.array(tint, dtype=np.float32)
    pixels += rng.normal(0.0, grain, pixels.shape).astype(np.float32)
    height, width = pixels.shape[:2]
    ys, xs = np.mgrid[0:height, 0:width]
    radius = np.sqrt(((xs / width - 0.5) * 2) ** 2 + ((ys / height - 0.5) * 2) ** 2)
    pixels *= (1.0 - 0.16 * np.clip(radius - 0.35, 0, None) ** 2)[..., None]
    return Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8), "RGB")


rng = np.random.default_rng(SEED)
page = Image.new("RGB", (WIDTH, HEIGHT), "#ffffff")
draw = ImageDraw.Draw(page)
right = WIDTH - MARGIN
y = MARGIN

draw.text((MARGIN, y), TITLE, font=font(32, bold=True), fill=TEXT)
y += 56
for key, value in HEADER:
    draw.text((MARGIN, y), f"{key}:", font=font(19), fill="#444444")
    draw.text((MARGIN + 190, y), value, font=font(19, bold=True), fill=TEXT)
    y += 28
y += 20

WIDTHS = [170, 570, 170, 170]
xs = [MARGIN]
for width in WIDTHS[:-1]:
    xs.append(xs[-1] + width)
draw.rectangle([MARGIN, y, right, y + 38], fill="#ececec")
for index, title in enumerate(COLUMNS):
    draw.text((xs[index] + 10, y + 10), title, font=font(19, bold=True), fill=TEXT)
y += 38
for item, description, shipped, received in ROWS:
    draw.text((xs[0] + 10, y + 12), item, font=font(19), fill=TEXT)
    draw.text((xs[1] + 10, y + 12), description, font=font(19), fill=TEXT)
    draw.text((xs[2] + 10, y + 12), str(shipped), font=font(19), fill=TEXT)
    mark = tick(rng) if received is None else handwrite(str(received), 42, rng)
    page.paste(mark, (xs[3] + 30 + int(rng.uniform(-6, 6)), y + 26 - mark.height // 2 + int(rng.uniform(-3, 3))), mark)
    y += 52
    draw.line([(MARGIN, y), (right, y)], fill="#b6b6b6", width=1)
y += 40

for label, text, size in [("Remarks:", REMARK, 30), ("Signature:", SIGNATURE, 40), ("Date:", DATE, 28)]:
    draw.text((MARGIN, y + 8), label, font=font(19), fill=TEXT)
    draw.line([(MARGIN + 150, y + 36), (right - 300, y + 36)], fill="#9a9a9a", width=1)
    mark = handwrite(text, size, rng, slant=0.3 if label == "Signature:" else 0.18)
    page.paste(mark, (MARGIN + 165 + int(rng.uniform(0, 20)), y + 36 - int(mark.height * 0.8)), mark)
    y += 64
assert y < HEIGHT - MARGIN // 2, f"the form overruns the page (ends at y={y}); drop rows or raise HEIGHT"

scannerize(page, seed=SEED).save(PART, format="PNG")
os.replace(PART, OUT)
print("wrote", OUT, (WIDTH, HEIGHT))
PYEOF
```

Keep the marks where a person would put them: a number in the cell it corrects, a remark on the remarks line, a signature over its line. A mark the method must read is only a fact of the test if it is legible to a person looking at the page, so look at it at step 5 before handing it back.

## App screenshot (Pillow)

Window chrome, a sidebar, a header with an action button, a row of stat tiles, and either a table or a card grid. `LAYOUT` chooses the last one.

```bash
uv run --quiet --no-project --with pillow --with matplotlib --with numpy python << 'PYEOF'
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager

OUT = "<output_dir>/inputs/test_screenshot.png"
assert "<" not in OUT and ">" not in OUT, f"OUT still holds a placeholder: {OUT}"
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
# Render beside the target and rename on success, so a crash never truncates an existing file.
PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))

# --- content -----------------------------------------------------------
APP = "Northwind Ops"
SCREEN = "Shipments"
SIDEBAR = ["Dashboard", "Orders", "Shipments", "Inventory", "Suppliers", "Reports"]
ACTIVE = "Shipments"
ACTION = "New shipment"
STATS = [("Open shipments", "128"), ("Late", "7"), ("Delivered today", "342")]
LAYOUT = "table"                  # table | cards
COLUMNS = ["Reference", "Destination", "Carrier", "Status", "ETA"]
ROWS = [
    ["SHP-4412", "Dijon, FR", "Transalp", "In transit", "2026-03-16"],
    ["SHP-4413", "Turin, IT", "Transalp", "Delayed", "2026-03-18"],
    ["SHP-4414", "Lyon, FR", "RapidFret", "Delivered", "2026-03-14"],
    ["SHP-4415", "Geneva, CH", "RapidFret", "In transit", "2026-03-17"],
    ["SHP-4416", "Nantes, FR", "Cargolix", "In transit", "2026-03-19"],
    ["SHP-4417", "Bilbao, ES", "Cargolix", "Delayed", "2026-03-21"],
]
BADGE_COLUMN = 3                  # column whose values are drawn as status badges
BADGES = {"In transit": "#2f6f9f", "Delayed": "#c25e3a", "Delivered": "#4f9d69"}
CARDS = [                         # used when LAYOUT == "cards"
    ("Transalp", "Road freight", "48 shipments"),
    ("RapidFret", "Express", "31 shipments"),
    ("Cargolix", "Road freight", "27 shipments"),
    ("Nordwind", "Sea freight", "12 shipments"),
]
# -----------------------------------------------------------------------

WIDTH, HEIGHT = 1200, 800
CHROME, SIDEBAR_W = 38, 220
DARK, MUTED, INK, LINE = "#212934", "#8d97a4", "#1d232b", "#e2e5ea"

_FONTS = {}


def font(size, bold=False):
    """DejaVu Sans, bundled with matplotlib; Pillow's built-in face as a fallback."""
    key = (size, bold)
    if key not in _FONTS:
        try:
            path = font_manager.findfont("DejaVu Sans:bold" if bold else "DejaVu Sans")
            _FONTS[key] = ImageFont.truetype(path, size)
        except Exception:
            _FONTS[key] = ImageFont.load_default(size=size)
    return _FONTS[key]


image = Image.new("RGB", (WIDTH, HEIGHT), "#ffffff")
draw = ImageDraw.Draw(image)

# window chrome
draw.rectangle([0, 0, WIDTH, CHROME], fill="#e9ebee")
draw.line([(0, CHROME), (WIDTH, CHROME)], fill="#d2d6dc", width=1)
for index, colour in enumerate(("#ec6a5e", "#f4bf4f", "#61c554")):
    cx = 22 + index * 22
    draw.ellipse([cx - 7, CHROME / 2 - 7, cx + 7, CHROME / 2 + 7], fill=colour)
draw.text((WIDTH / 2, CHROME / 2), f"{APP} — {SCREEN}", font=font(16), fill="#5c646f", anchor="mm")

# sidebar
draw.rectangle([0, CHROME, SIDEBAR_W, HEIGHT], fill=DARK)
draw.text((26, CHROME + 30), APP, font=font(21, bold=True), fill="#ffffff")
y = CHROME + 88
for entry in SIDEBAR:
    if entry == ACTIVE:
        draw.rounded_rectangle([12, y - 9, SIDEBAR_W - 12, y + 29], radius=8, fill="#31404f")
    draw.rectangle([26, y + 5, 38, y + 17], outline="#7fb2dd" if entry == ACTIVE else "#6f7b89", width=2)
    draw.text((52, y + 2), entry, font=font(17, bold=entry == ACTIVE),
              fill="#ffffff" if entry == ACTIVE else MUTED)
    y += 46

# header
left = SIDEBAR_W
draw.text((left + 34, CHROME + 34), SCREEN, font=font(28, bold=True), fill=INK)
button = [WIDTH - 34 - 176, CHROME + 30, WIDTH - 34, CHROME + 70]
draw.rounded_rectangle(button, radius=8, fill="#2f6f9f")
draw.text(((button[0] + button[2]) / 2, (button[1] + button[3]) / 2), ACTION,
          font=font(17, bold=True), fill="#ffffff", anchor="mm")

# stat tiles
y = CHROME + 96
tile_w = (WIDTH - left - 68 - (len(STATS) - 1) * 18) / len(STATS)
for index, (label, value) in enumerate(STATS):
    x0 = left + 34 + index * (tile_w + 18)
    draw.rounded_rectangle([x0, y, x0 + tile_w, y + 86], radius=10, fill="#f6f7f9", outline=LINE, width=1)
    draw.text((x0 + 18, y + 16), label, font=font(15), fill="#69727d")
    draw.text((x0 + 18, y + 40), value, font=font(28, bold=True), fill=INK)
y += 116

if LAYOUT == "table":
    x0, x1 = left + 34, WIDTH - 34
    widths = [(x1 - x0) * share for share in (0.20, 0.22, 0.20, 0.22, 0.16)]
    xs = [x0]
    for width in widths[:-1]:
        xs.append(xs[-1] + width)
    draw.rectangle([x0, y, x1, y + 38], fill="#f0f2f5")
    for index, title in enumerate(COLUMNS):
        draw.text((xs[index] + 14, y + 10), title, font=font(15, bold=True), fill="#5c646f")
    y += 38
    assert y + 46 * len(ROWS) <= HEIGHT, (
        f"{len(ROWS)} rows run off the {HEIGHT}px canvas — a real screen scrolls, an image "
        "does not, and Pillow drops the overflow silently. Trim ROWS or raise HEIGHT."
    )
    for row in ROWS:
        for index, cell in enumerate(row):
            if index == BADGE_COLUMN and cell in BADGES:
                colour = BADGES[cell]
                width = draw.textlength(cell, font=font(14, bold=True)) + 22
                draw.rounded_rectangle([xs[index] + 12, y + 10, xs[index] + 12 + width, y + 36],
                                       radius=13, fill=colour)
                draw.text((xs[index] + 12 + width / 2, y + 23), cell, font=font(14, bold=True),
                          fill="#ffffff", anchor="mm")
            else:
                draw.text((xs[index] + 14, y + 14), cell, font=font(16), fill=INK)
        y += 46
        draw.line([(x0, y), (x1, y)], fill=LINE, width=1)
else:
    x0 = left + 34
    card_w = (WIDTH - x0 - 34 - 18) / 2
    for index, (title, subtitle, value) in enumerate(CARDS):
        cx = x0 + (index % 2) * (card_w + 18)
        cy = y + (index // 2) * 130
        draw.rounded_rectangle([cx, cy, cx + card_w, cy + 112], radius=10, fill="#ffffff",
                               outline=LINE, width=1)
        draw.text((cx + 20, cy + 20), title, font=font(19, bold=True), fill=INK)
        draw.text((cx + 20, cy + 48), subtitle, font=font(15), fill="#69727d")
        draw.text((cx + 20, cy + 76), value, font=font(17, bold=True), fill="#2f6f9f")

image.save(PART, format="PNG")
os.replace(PART, OUT)
print("wrote", OUT, image.size)
PYEOF
```

The `widths` shares must add up to 1 and match the number of columns. Six or seven table rows fill the screen at this size; more will run off the bottom, which is what a real screen does too — but do not let the content the method must read fall outside the image.

Column widths are fixed shares, not measured, so a long cell will overlap its neighbour. Widen that column's share rather than shortening the content when the content is what the method reads.

## Verify

```bash
uv run --quiet --no-project --with pillow python -c "from PIL import Image; import os, sys; im = Image.open(sys.argv[1]); print(im.format, im.size, im.mode, os.path.getsize(sys.argv[1]) // 1024, 'KB')" "<output_dir>/inputs/<name>.png"
```

Expect `PNG`, the size the recipe declares, and `RGB` — or `RGBA` from the chart recipe, which is matplotlib's doing and not a fault. Then look at the file: on Claude Code, open it with the `Read` tool and check it reads as its category — a chart with the series drafted, a diagram whose arrows go where the process goes, a page that looks scanned and whose totals add up, a screen that looks like an app. Fix the content block and rerun if it does not; the recipes are seeded, so nothing else moves.

A failed render is cleaned up as the skill's step 4 says, partial file included, before anything is rerun.
