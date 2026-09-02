---
name: pipelex-synthetic-inputs
description: Generate synthetic input files for MTHDS methods from code, without AI — PDF documents (letters, multi-page reports, tables, invoices) and PNG images (charts, diagrams, scanned-looking documents, app screenshots), plus Word and Excel files. Use when the user says "make a sample PDF", "generate a test image", "fake invoice", "synthetic document", "placeholder screenshot", "I need a chart to test with", "create test files", or when /pipelex-inputs needs a file for a native.Image or native.Document input and the user has none. Permissively licensed Python packages only; installs what it needs through uv or an isolated venv and stops with a clear message when it cannot.

---

# Generate synthetic input files

Make the files a method needs to run when the user has none: a PDF for a `native.Document` input, a PNG for a `native.Image` input, a Word or Excel file when the method asks for one. Everything is rendered by Python code this skill writes and runs — no image-generation model, no hosted method, no image API — from packages whose licences are compatible with MIT.

This skill is the plugin's file factory. `/pipelex-inputs` calls it whenever its synthetic strategy reaches a file-typed input; users call it directly for a one-off sample file. It writes files and reports on them. It never edits `inputs.json`, never uploads anything, and never starts a run — those belong to `/pipelex-inputs`.

## What this skill makes, and what it refuses

| Format | Good for | Recipes |
|---|---|---|
| `pdf` | letters and memos, multi-page reports, tables, invoices and statements — anything a `native.Document` input reads | [references/pdf.md](references/pdf.md) |
| `png` — `chart` | data visualizations: bar, line, pie, scatter | [references/png.md](references/png.md) |
| `png` — `diagram` | flowcharts, architecture and org charts, process diagrams | [references/png.md](references/png.md) |
| `png` — `document_scan` | scanned-looking pages for OCR and document-understanding methods: invoices, receipts, forms, letters | [references/png.md](references/png.md) |
| `png` — `screenshot` | app and web screens for UI-understanding methods: dashboards, settings pages, lists | [references/png.md](references/png.md) |
| `docx`, `xlsx` | Word and Excel inputs | [references/office.md](references/office.md) |

**Not covered, by design:** photographs and handwriting. Code cannot render either to a standard a vision model would mistake for the real thing, and a stand-in is worse than none — it lets a method run on the wrong kind of input and report success. When a request asks for one, say so plainly and ask the user for a real file for that input. Do not draw an approximation, and do not substitute a public image.

## Rules

- **No AI in the loop.** Files come from reportlab, Pillow and matplotlib code. If a request cannot be met that way, the answer is the refusal above, not a model.
- **Permissive packages only.** `reportlab` (BSD), `Pillow` (MIT-CMU), `matplotlib` (PSF-style), `numpy` (BSD), `python-docx` (MIT), `openpyxl` (MIT). Nothing else: no PyMuPDF (AGPL), nothing that needs a system binary (poppler, cairo, wkhtmltopdf, Ghostscript), nothing that reaches the network at runtime.
- **Content first, then render.** The realism is in what the file says, not how it is drawn. Draft the content from the brief before opening a recipe (Step 3). Entities are obviously fictional — "Acme Hardware Supply", "Jane Example", `INV-2026-0042` — never real people, companies or brands.
- **Deterministic.** Seed every source of randomness so a regenerated file is the same file.
- **Modest sizes.** PNGs default to 1200×800; document-shaped PNGs to A4 at 150 dpi (1240×1754); PDFs to a few pages. This keeps files well inside the storage-size limit `/pipelex-inputs` meets at upload time.
- **Nothing installed into the project, nothing installed onto the machine without asking.** Packages are fetched into `uv`'s cache or into a venv this skill owns under the user's cache directory (Step 2). Installing a *tool* — `uv` itself, a system package — always asks first, in every mode.
- **A failure leaves nothing behind.** A render that fails removes its partial output, so no `inputs.json` can ever point at a broken file.
- **Report what was done.** Every file gets one line: path, format, dimensions or page count, and what it contains. A fallback of any kind is named as one.

## The request

A request carries four things. When `/pipelex-inputs` calls this skill they arrive explicitly; when the user invokes it directly, infer them from the conversation and confirm only what is genuinely ambiguous.

| Field | Meaning | Default when absent |
|---|---|---|
| `format` | `pdf`, `png`, `docx`, `xlsx` — for `png`, also the category from the table above | from the target concept: `native.Document` → `pdf`, `native.Image` → `png`; the category from the brief ("a chart of…" → `chart`, "a scanned…" → `document_scan`) |
| `brief` | one or two sentences on what the file must contain or depict, in the vocabulary of the method that will read it | ask for it, or derive it from the method's purpose and the input's description |
| `target` | the path to write | `<output_dir>/inputs/<input_variable>.<ext>`; standalone, `./inputs/<name>.<ext>` |
| `constraints` | page count, pixel size, language, anything the method's input description pins | the per-format defaults in the recipes |

Mode follows the caller: a request from `/pipelex-inputs` runs in whatever mode that skill is in; a direct invocation defaults to **automatic** — state the assumptions in one line and proceed — unless the user asks to be walked through it.

## Process

### Step 1: Settle the request

Fill the four fields. If the format is one this skill refuses (a photograph, handwriting), stop here with the refusal and the ask for a real file. If the brief is missing and cannot be derived, ask for it — one question, then proceed.

### Step 2: Resolve the environment

Do this once per invocation, before any recipe. The outcome is the **runner line** — the first line of every recipe — and every recipe below it is identical whichever rung produced it.

**Package sets by format:** `pdf` → `reportlab`; `png` → `pillow matplotlib numpy`; `docx` → `python-docx`; `xlsx` → `openpyxl`.

**Rung 1 — `uv` is on `PATH`** (the normal case). Preflight the format's set once:

```bash
command -v uv >/dev/null && uv run --quiet --with reportlab python -c "import reportlab; print('pdf ready', reportlab.Version)"
```

```bash
command -v uv >/dev/null && uv run --quiet --with pillow --with matplotlib --with numpy python -c "import PIL, matplotlib, numpy; print('png ready', PIL.__version__, matplotlib.__version__)"
```

On success the runner line is `uv run --quiet --with <set> python << 'PYEOF'` — exactly as the recipes are written. Packages land in `uv`'s cache; the project is untouched. On a cold cache the first run downloads the packages and can take a minute: say so in one line, then continue.

**Rung 2 — no `uv`, but `python3` with `venv` and `pip`.** Create a venv this skill owns, once, fill it with the whole allowlist, and reuse it on every later invocation:

```bash
VENV="${XDG_CACHE_HOME:-$HOME/.cache}/pipelex-plugins/synth-venv"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/python" -c "import reportlab, PIL, matplotlib, numpy, docx, openpyxl" 2>/dev/null || "$VENV/bin/python" -m pip install --quiet reportlab pillow matplotlib numpy python-docx openpyxl
"$VENV/bin/python" -c "import reportlab, PIL, matplotlib, numpy, docx, openpyxl; print('venv ready:', '$VENV')"
```

On success the runner line becomes `"$VENV/bin/python" << 'PYEOF'` (with `VENV` set as above in the same shell call) — that substitution is the only difference between the rungs. This rung installs something durable, isolated from the project and from the system Python, so proceed in automatic mode and state it: the venv path and the packages installed into it.

**When a rung fails, say exactly what failed and what fixes it.** Quote the error, then:

| Situation | The message, and the way forward |
|---|---|
| `python3 -m venv` fails (typically `ensurepip` missing — Debian/Ubuntu without `python3-venv`) | give the platform cure (`sudo apt install python3-venv`) **and** the recommended one, the `uv` installer: `curl -LsSf https://astral.sh/uv/install.sh \| sh` (it also brings a managed Python where there is none). Both install a tool onto the machine: **ask before running either**, whatever the mode. Offer to continue once one has run |
| no `python3` at all | the same offer: install `uv`, asked first |
| a download fails on either rung (offline, proxy, registry down) | a warm `uv` cache still works — run the preflight anyway before concluding; if it fails too, say the machine needs network once, and stop |
| everything above failed, or the user declined | **stop gracefully**: state what is missing and the one command that fixes it; offer the user's own file for this input; for `pdf` only, offer the documented public last-resort URL in `references/pdf.md`, named as a substitution. Never fabricate a file. When called from `/pipelex-inputs`, return **no path** with the reason, so that input is left unfilled and the rest of its flow continues |

### Step 3: Draft the content

Write down what the file will say before rendering it — in the reply, briefly, so the user sees it and can redirect. Use the method's own vocabulary: if it extracts invoice fields, the file is an invoice with a seller, a buyer, an invoice number, a date, line items with quantities and unit prices, a subtotal, a tax line and a total that add up. Keep values internally consistent (totals sum, dates are in order, ids look like ids), because the method will read them and a checker may compare them. By format:

- **Document (`pdf`, `document_scan`)**: title, parties, identifiers and dates, the body paragraphs or the line items, the closing block.
- **`chart`**: the series and their values, axis labels with units, the title, the chart kind.
- **`diagram`**: the nodes and their labels, the edges, the reading direction.
- **`screenshot`**: the app and the screen, the sidebar entries, the visible records or cards.

Fictional throughout. Match the length the method expects: a two-line memo and a ten-page report are different briefs.

### Step 4: Render

Open the reference for the format and take the recipe that matches the content — the reference's opening table says which. Copy the recipe, replace its content block with what Step 3 drafted, set the output path to `target`, keep the runner line from Step 2, and run it. Write to `target` directly; the file lands in `<output_dir>/inputs/` when the caller is `/pipelex-inputs`.

If the run fails, remove any partial output before doing anything else:

```bash
rm -f "<target>"
```

then read the error. A recipe error is yours to fix and rerun; an environment error goes back to Step 2's table.

### Step 5: Verify

Reopen the file and confirm it is what the brief asked for:

- **PNG**: `uv run --quiet --with pillow python -c "from PIL import Image; im = Image.open('<target>'); print(im.format, im.size, im.mode)"` (or the venv's python) — expect `PNG`, the size the recipe declared, and `RGB` (`RGBA` from the matplotlib chart recipe, which is normal). Open it if the harness can display images; otherwise trust the Pillow check and the recipe's declared layout.
- **PDF**: `head -c 5 <target>` prints `%PDF-`, and `wc -c <target>` is not tiny. Page count, without extra packages: `python3 -c "import re, sys; print(len(re.findall(rb'/Type\s*/Page[^s]', open(sys.argv[1], 'rb').read())))" <target>`.
- **DOCX / XLSX**: reopen with the same library that wrote it and print the headings or the sheet dimensions.

### Step 6: Report

One line per file: path, format, dimensions or page count, and a sentence on its content. Name any fallback as one. Then:

- **Called from `/pipelex-inputs`**: hand the path back and stop — that skill writes `inputs.json`, uploads the file with `mthds_prepare_inputs`, and offers the run. On a graceful failure, hand back no path and the reason.
- **Direct invocation**: mention that `/pipelex-inputs` is where the file becomes a runnable input.

## Reference

- [references/pdf.md](references/pdf.md) — reportlab: canvas letters, multi-page Platypus reports, tables, a composed line-item document, verification, the last-resort URL.
- [references/png.md](references/png.md) — Pillow and matplotlib: the shared preamble and font helper, one recipe per category, the scanner post-process, verification.
- [references/office.md](references/office.md) — Word and Excel through a host `docx`/`xlsx` skill when one is available, otherwise `python-docx` / `openpyxl`.
- `/pipelex-inputs` — the flow that turns these files into a runnable `inputs.json`.
