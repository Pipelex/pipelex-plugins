---
name: pipelex-inputs
description: Prepare inputs for MTHDS methods. Use when user says "prepare inputs", "create inputs", "use my files", "generate test data", "template", "synthesize inputs", "mock inputs", "I have a PDF/image/document to use", "make sample data", or wants to create inputs.json for running a .mthds pipeline. Handles user-provided files, synthetic data generation, placeholder templates, and mixed approaches. Defaults to automatic mode.

---

# Prepare Inputs for MTHDS methods

Prepare input data for running MTHDS method bundles. This skill is the single entry point for all input preparation needs: extracting a placeholder template, generating synthetic test data, integrating user-provided files, or any combination.

## Requirements — the Pipelex MCP tool

This skill extracts the method's input template through the **`mthds_inputs_template`** tool, served by the plugin's `pipelex` MCP server. It is required — never hand-derive the template from the `.mthds` source.

- **If the tool is absent from this session** (the MCP server isn't connected), STOP and tell the user in one line: *"The Pipelex MCP server isn't connected — the plugin manifest spawns the local workshop (`npx -y @pipelex/mcp@latest`), so its absence usually means `node`/`npx` is unavailable or the spawn failed. Check the plugin's MCP connection."*
- **If a call returns `status: "error"` with an error of class `config`** (missing or rejected `PIPELEX_API_KEY`, unreachable API), STOP the same way and surface the error's `hint` verbatim. Never silently improvise a template.
- The server authenticates to the API with **`PIPELEX_API_KEY`** from the session environment — the same variable the plugin's validation hook documents.
- The **run tools** (`mthds_run`, `mthds_run_status`, `mthds_run_results`) are optional — they only power the closing [offer to run](#offer-to-run). When they are absent from the session, finish without the offer; never stop for them.

## Mode Selection

### How mode is determined

1. **Explicit override**: If the user states a preference, always honor it:
   - Automatic signals: "just do it", "go ahead", "automatic", "quick", "don't ask"
   - Interactive signals: "walk me through", "help me", "guide me", "step by step", "let me decide"

2. **Skill default**: Each skill defines its own default based on the nature of the task.

3. **Request analysis**: If no explicit signal and no strong skill default, assess the request:
   - Detailed, specific requirements → automatic
   - Brief, ambiguous, or subjective → interactive

### Mode behavior

**Automatic mode:**
- State assumptions briefly before proceeding
- Make reasonable decisions at each step
- Present the result when done
- Pause only if a critical ambiguity could lead to wasted work

**Interactive mode:**
- Ask clarifying questions at the start
- Present options at decision points
- Confirm before proceeding at checkpoints
- Allow the user to steer direction

### Mode switching

- If in automatic mode and the user asks a question or gives feedback → switch to interactive for the current phase
- If in interactive mode and the user says "looks good, go ahead" or similar → switch to automatic for remaining phases

**Default**: Automatic.

**Input strategy detection heuristics** (evaluated in order):

| Signal | Strategy |
|--------|----------|
| User provides file paths, folder paths, or mentions "my data" / "this file" / "use these images" / "here's my PDF" | **User Data** (or Mixed if some inputs remain unfilled) |
| User says "test data" / "generate inputs" / "synthesize" / "fake data" / "sample data" | **Synthetic** |
| User says "template" / "schema" / "placeholder" / "what inputs does it need?" | **Template** |
| No clear signal (e.g., called right after `/pipelex-design` with no further context) | **Template**, then offer to populate |

**Interactive additions**: Ask about:
- Which user files map to which inputs (when ambiguous)
- Domain/industry context for realistic synthetic data
- Whether to generate edge cases or happy-path data
- Specific values or constraints for certain fields

---

## Process

### Step 1: Identify the Target Method

Determine the `.mthds` bundle and its output directory (`<output_dir>`). This is usually the directory containing `main.mthds` (e.g., `pipelex-wip/pipeline_01/`).

The `inputs.json` file is saved directly in this directory (next to `main.mthds`):
- `<output_dir>/inputs.json`

If data files need to be generated or copied (images, PDFs, etc.), they go in a subdirectory:
- `<output_dir>/inputs/`

The `/inputs` subdirectory is only created when there are actual data files to store. Paths to these files are referenced from within `inputs.json`.

> **Path resolution rule**: URL/path values in `inputs.json` are resolved **relative to the `inputs.json` file itself** (i.e., relative to the bundle directory), NOT relative to the current working directory. When referencing local files, you MUST either:
> 1. **Copy files** into `<output_dir>/inputs/` and reference with a path relative to the `inputs.json` file, e.g., `inputs/the_doc.pdf` (preferred — keeps the bundle self-contained), or
> 2. **Use a URL or absolute path**, e.g., `https://example.com/doc.pdf` or `/Users/alice/data/invoice.pdf`

### Step 2: Get the Input Template

Call the **`mthds_inputs_template`** tool with the whole bundle: every `.mthds` file in `<output_dir>`, as `files: [{content: <file content>, uri: <path relative to the bundle dir>}]`. Pass no other arguments — the defaults resolve the method's declared `main_pipe` and return the canonical **light** template. (To target a different pipe, pass `pipe_ref` as a qualified `domain.pipe_code`.)

Branch on the structured verdict, never on transport:

- `status: "ok"`, `is_valid: true` → the template is in `inputs`, with the resolved `pipe_ref`. This template is **authoritative** — fill in its values; never invent shapes it doesn't have.
- `status: "ok"`, `is_valid: false` → the bundle itself doesn't validate: report `validation_errors[]` (and the summary) to the user; repair the bundle first (e.g. via `/pipelex-design` resumption), then retry.
- `status: "error"` → no verdict: class `config` → stop per the Requirements above; class `input_domain` → the call is malformed (an unknown `pipe_ref`, or `main_pipe` unresolvable — pass an explicit `pipe_ref`); class `runtime` → report and retry once.

**Example template** (light shape — the tool's default):

```json
{
  "document": "https://mock-xxxxxxxx.invalid/...",
  "context": "text_value"
}
```

Each value is an example shaped like what the runtime accepts: a bare string for a Text-refining input, a bare number / boolean / ISO date string for the other scalars, a bare URL-or-path string for a file-ish input (Image, Document), a content dict (fields directly, no envelope) for a structured concept, and the same wrapped in a list for a declared-multiple input (`Type[]` / `Type[N]`). Only inputs the signature genuinely can't shape (e.g. Dynamic) keep a `{concept, content}` envelope — leave those entries in the exact shape the template gives them.

### Step 3: Choose Input Strategy

Based on the heuristics above and what the user has provided, follow the appropriate strategy:

- [Template Strategy](#template-strategy) — placeholder JSON, no real data
- [Synthetic Strategy](#synthetic-strategy) — AI-generated realistic test data
- [User Data Strategy](#user-data-strategy) — integrate user-provided files
- [Mixed Strategy](#mixed-strategy) — user files + synthetic for the rest

---

## Template Strategy

The fastest path. Produces a placeholder `inputs.json` that the user can fill in manually.

1. Take the `inputs` template from Step 2
2. For file-ish values (Image, Document), replace the mock URLs (e.g., `https://mock-xxxxxxxx.invalid/...`) with descriptive placeholder strings that explicitly tell the path resolution is relative to inputs.json, e.g:
  good: `"<VARNAME-url-or-path-relative-to-this-inputs-file>"` ✅ do this
  bad:  `"<path-to-VARNAME>"` ❌ don't do that
This placeholder means "replace with either a real URL, an absolute path, or a path relative to the saved `inputs.json` file itself," not relative to the current working directory.
3. Save it to `<output_dir>/inputs.json` (next to `main.mthds`)
4. Report the saved file path and show the template content
5. Offer: "To populate this with realistic test data, re-run /pipelex-inputs and ask for synthetic data. Or provide your own files."

---

## Synthetic Strategy

Generate realistic fake data tailored to the method's purpose.

### Identify Input Types

Parse the template to identify what synthetic data each input needs. The light value to produce, by declared concept:

| Concept | Light value | Synthesis Method |
|---------|-------------|------------------|
| `native.Text` | bare string | Generate realistic text matching the method context |
| `native.Number` | bare number | Generate appropriate numeric values |
| `native.YesNo` | bare boolean | Generate a `true`/`false` answer |
| `native.Date` | bare ISO 8601 date string | Generate date/time values; never use epoch numbers |
| `native.Image` | bare URL-or-path string | Generate or source an image file (see [Document Generation](#document-generation) fallbacks) |
| `native.Document` | bare URL-or-path string | Use document generation below |
| `native.Page`, `native.TextAndImages`, `native.JSON` | content dict as given by the template | Fill the template's fields in place |
| Custom structured | content dict (fields directly) | Fill each field according to its type and description |

**List types** (`Type[]` or `Type[N]`): the template wraps the value in a list — generate multiple items. Variable lists typically need 2-5 items; fixed lists need exactly N items.

### Generate Text Content

Create realistic text that matches the method's purpose:
- If the method processes invoices, generate invoice-like text
- If it analyzes reports, generate report-style content
- Match expected length (short prompts vs long documents)

### Generate Numeric Content

Generate sensible values within expected ranges based on the method context.

### Generate Structured Concepts

Fill each field of the template's content dict according to its type and description.

### Generate File Inputs

When inputs require actual files (Image, Document), generate them — see [Document Generation](#document-generation) below — and reference each file by a path relative to `inputs.json` (files go in `<output_dir>/inputs/`).

### Assemble and Save

Fill the Step 2 template in place and save it to `<output_dir>/inputs.json` (next to `main.mthds`). Any generated data files go in `<output_dir>/inputs/`.

---

## User Data Strategy

Integrate the user's own files into the method's input template.

### Step A: Inventory User Files

Collect all files the user has provided (explicit paths, folders, or files mentioned earlier in conversation). For each file, determine its type:

| Extension(s) | Detected Type | Maps To |
|--------------|---------------|---------|
| `.pdf` | PDF document | `native.Document` |
| `.docx`, `.doc` | Word document | `native.Document` |
| `.xlsx`, `.xls` | Spreadsheet | `native.Document` |
| `.pptx`, `.ppt` | Presentation | `native.Document` |
| `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.svg`, `.tiff`, `.tif`, `.bmp` | Image | `native.Image` |
| `.txt` | Plain text | `native.Text` (read file content) |
| `.md` | Markdown text | `native.Text` (read file content) |
| `.json` | JSON data | `native.JSON` or custom structured concept |
| `.csv` | CSV data | `native.Text` (read as text) or `native.JSON` (parse to objects) |
| `.html`, `.htm` | HTML | `native.Html` |
| `http://...`, `https://...` | Web page URL | `native.Document` |

### Step B: Expand Folders

When the user provides a folder path:

1. List all files in the folder (non-recursive by default, recursive if user requests)
2. Filter to supported file types
3. Group files by detected type
4. Match to list-type inputs (`Image[]`, `Document[]`, etc.)

**Example**: User provides `./invoices/` containing 5 PDFs. The method expects `documents: Document[]`. Map all 5 PDFs to that list input.

### Step C: Match Files to Inputs

For each input variable in the template, attempt to match user-provided files:

**Matching rules** (applied in order):

1. **Exact name match**: Input variable `invoice` matches a file named `invoice.pdf`
2. **Type match (single candidate)**: If only one input expects `native.Image` and the user provided exactly one image file, match them
3. **Type match (multiple candidates)**: If multiple inputs of the same type exist:
   - In **automatic mode**: match by name similarity (variable name vs filename)
   - In **interactive mode**: ask the user which file goes where
4. **Folder to list**: If a folder contains files of a single type and an input expects a list of that type, map the folder contents to that input
5. **Unmatched files**: Report them and ask if they should be ignored or mapped to a specific input
6. **Unfilled inputs**: After matching, any inputs still without data can be left as placeholders or filled with synthetic data (see [Mixed Strategy](#mixed-strategy))

### Step D: Copy Files to Output Directory

Copy (or symlink) user files into `<output_dir>/inputs/` so `inputs.json` can reference them with paths **relative to the `inputs.json` file itself** (i.e., relative to the bundle directory where `inputs.json` lives). This keeps the pipeline directory self-contained. Only create the `inputs/` subdirectory if there are actual files to copy.

Use descriptive filenames: if the input variable is `invoice`, copy to `<output_dir>/inputs/invoice.pdf` (preserving original extension).

### Step E: Fill the Template Values

For each matched file, set the input's light value:

- **Document input** → the path string: `"invoice": "inputs/invoice.pdf"`
- **Web page Document input** → the URL string: `"page": "https://example.com/article"`
- **Image input** → the path string: `"photo": "inputs/photo.jpg"`
- **Text input** (from `.txt`/`.md`) → the file's actual content as the string value: `"context": "<content read from the file>"`
- **List input** (e.g. from a folder) → a list of those values: `"images": ["inputs/img_001.jpg", "inputs/img_002.jpg", "inputs/img_003.png"]`

### Step F: Assemble and Save

Fill all matched values into the Step 2 template and save it as `<output_dir>/inputs.json` (next to `main.mthds`).

### Step G: Report

Show the user:
- Which files were matched to which inputs
- Any unfilled inputs (offer synthetic or placeholder)
- The final `inputs.json` content
- Path to the saved file

---

## Mixed Strategy

Combines user data with synthetic generation for any remaining gaps.

1. Follow [User Data Strategy](#user-data-strategy) Steps A-F to match user files
2. For each unfilled input, apply [Synthetic Strategy](#synthetic-strategy)
3. Assemble the complete `inputs.json` combining both sources
4. Report which inputs came from user data and which were synthesized

---

## Document Generation

Generate test documents based on the document type needed. Nothing here assumes a Pipelex install — use whatever Python is available in the environment.

### PDF Documents

Use `reportlab` via an ephemeral environment (preferred):

```bash
uv run --with reportlab python << 'PYEOF'
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("<output_dir>/inputs/test_document.pdf", pagesize=letter)
width, height = letter

# Add text
c.drawString(100, height - 100, "Hello World!")
c.drawString(100, height - 120, "This is a PDF created with reportlab")

# Add a line
c.line(100, height - 140, 400, height - 140)

# Save
c.save()
PYEOF
```

If `uv` is not available, fall back to `python3` with `reportlab` installed (`python3 -m pip install reportlab` in a venv), with the same script.

For multi-page documents or reports with tables, use reportlab's Platypus API (`SimpleDocTemplate`, `Paragraph`, `Table`, `TableStyle`) instead of the raw canvas — same invocation pattern.

**Last resort** — use a public test PDF URL as the value directly:

```json
{
  "document": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/img/table-word.pdf"
}
```

### Word Documents (DOCX)

**If a `docx` skill is available:**
```
Use the /docx skill to create a Word document with the following content:
[Describe the document content, structure, and formatting]
Save to: <output_dir>/inputs/<filename>.docx
```

**If not**, create using Python:
```bash
uv run --with python-docx python << 'PYEOF'
from docx import Document

doc = Document()
doc.add_heading('Test Document', 0)
doc.add_paragraph('This is synthetic test content for method testing.')
# Add more content as needed
doc.save('<output_dir>/inputs/test_document.docx')
PYEOF
```

### Spreadsheets (XLSX)

**If an `xlsx` skill is available:**
```
Use the /xlsx skill to create a spreadsheet with the following data:
[Describe columns, rows, and sample data]
Save to: <output_dir>/inputs/<filename>.xlsx
```

**If not**, create using Python:
```bash
uv run --with openpyxl python << 'PYEOF'
from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws['A1'] = 'Column1'
ws['B1'] = 'Column2'
ws['A2'] = 'Value1'
ws['B2'] = 'Value2'
wb.save('<output_dir>/inputs/test_spreadsheet.xlsx')
PYEOF
```

---

**Fallback Strategy:**
1. For PDFs: `uv run --with reportlab python`, or a plain `python3` with reportlab installed
2. For DOCX/XLSX: use the `/docx` or `/xlsx` skill, or `uv run --with <package> python`
3. For any format: use public test file URLs as fallback
4. As last resort, ask user to provide test files

---

## Finish

After assembling the inputs, confirm readiness:

> Inputs are ready. `inputs.json` has been saved with real values — no placeholders remain.

(Or, for the Template strategy: point out which placeholders the user still needs to fill.)

### Offer to run

When the inputs are complete, close by offering to run the method. Offer — never start unprompted: a run executes on the hosted Pipelex API and **spends inference credit**.

Offer only when all of these hold:

- The `mthds_run` tool is present in the session (it is optional — when absent, just finish).
- No placeholders remain (a Template-strategy result has nothing to run yet).
- The inputs are **hosted-runnable**: every file-ish value (Image, Document) is a reachable `https` URL. The hosted API cannot read local disk, so a path — relative like `inputs/invoice.pdf` or absolute — does not reach it. When local paths are present, don't offer; instead state that the method can be run once those files are hosted at reachable URLs (text, scalar, and structured values are sent inline and are always fine).

On acceptance:

1. Call `mthds_run` with the same whole-bundle `files` submission as Step 2 and `inputs` set to the parsed content of `inputs.json` — the light shape is exactly what the tool takes. Omit `pipe_code` to run the method's declared main pipe; pass a pipe's code only when the user targeted a different pipe in Step 2.
2. The tool returns a durable `run_id` immediately and never blocks. Report the id, then check with `mthds_run_status`, honoring the summary's retry hint — don't poll in a tight loop.
3. Once terminal, fetch `mthds_run_results` and report the main output (or the failure message).

---

## Value shapes (light format)

`inputs.json` uses the **light** shape — the same shape the `mthds_inputs_template` template arrives in. Scalars are bare values; structured concepts are their content dict, with **no** `{concept, content}` envelope:

| Declared concept | Value in `inputs.json` |
|------------------|------------------------|
| `Text` (or refining it) | `"The actual text content"` |
| `Number` | `42` |
| `YesNo` | `true` |
| `Date` | `"2026-07-08"` |
| `Image` | `"inputs/image.jpg"` (URL, absolute path, or path relative to `inputs.json`) |
| `Document` | `"inputs/document.pdf"` or `"https://example.com/article"` |
| Structured concept | `{"field_a": "...", "field_b": 3}` — its fields directly |
| Any `Type[]` / `Type[N]` | a JSON list of the above |

For composite natives (`Page`, `TextAndImages`, `JSON`) and any structured concept, keep exactly the field structure the template gives you and fill the values in place. See [Native Content Types](../shared/native-content-types.md) for what each native content's attributes mean.

---

## Complete Examples

### Example 1: Template for a Haiku writer

**Method**: Haiku pipeline expecting `theme: Text`

Call `mthds_inputs_template` with the bundle files; the template comes back as:

```json
{
  "theme": "text_value"
}
```

Save it (with a placeholder or real theme) directly to `pipelex-wip/pipeline_01/inputs.json`.

### Example 2: Synthetic data for an image analysis pipeline

**Method**: Image analyzer expecting `image: Image` and `analysis_prompt: Text`

1. Get the template; identify needs: a test photograph + instruction text
2. Source or generate a test image into `<output_dir>/inputs/`
3. Write an analysis prompt matching the method context
4. Assemble:
```json
{
  "image": "inputs/city_street.jpg",
  "analysis_prompt": "Analyze this street scene. Count visible people and describe the atmosphere."
}
```

### Example 3: User-provided invoice PDF

**Method**: Invoice processor expecting `invoice: Document` and `instructions: Text`

User says: "Use my file `~/documents/invoice_march.pdf`"

1. Get the template: needs `invoice` (Document) + `instructions` (Text)
2. Inventory: user provided `invoice_march.pdf` (PDF = Document type)
3. Match: `invoice_march.pdf` maps to `invoice` input (name similarity + type match)
4. Copy: `cp ~/documents/invoice_march.pdf <output_dir>/inputs/invoice.pdf`
5. Unfilled: `instructions` has no user file. Generate synthetic text.
6. Assemble:
```json
{
  "invoice": "inputs/invoice.pdf",
  "instructions": "Extract all line items, totals, and vendor information from this invoice."
}
```

### Example 4: Folder of images for batch processing

**Method**: Batch image captioner expecting `images: Image[]`

User says: "Use the photos in `./product-photos/`"

1. Get the template: needs `images` (Image[])
2. Expand folder: `./product-photos/` contains `shoe.jpg`, `hat.png`, `bag.jpg`
3. Copy all to `<output_dir>/inputs/`
4. Assemble:
```json
{
  "images": ["inputs/shoe.jpg", "inputs/hat.png", "inputs/bag.jpg"]
}
```

---

## Reference

- [MTHDS Language Reference](../shared/mthds-reference.md) — read for concept definitions and syntax
- [Native Content Types](../shared/native-content-types.md) — read for the full attribute reference of each native content type when filling composite or structured values
