---
name: pipelex-inputs
description: Prepare inputs for MTHDS methods. Use when user says "prepare inputs", "create inputs", "use my files", "generate test data", "template", "synthesize inputs", "mock inputs", "I have a PDF/image/document to use", "make sample data", or wants to create inputs.json for running a .mthds pipeline. Works from a local .mthds bundle or from a registered method's catalog id (mt_…) — also use when the user names a method id, e.g. "prepare inputs for mt_abc123" or "run method mt_abc123". Handles user-provided files, synthetic data generation, placeholder templates, and mixed approaches. Defaults to automatic mode.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob

  - mcp__plugin_pipelex_pipelex__mthds_inputs_template
  - mcp__plugin_pipelex_pipelex__mthds_prepare_inputs
  - mcp__plugin_pipelex_pipelex__mthds_run
  - mcp__plugin_pipelex_pipelex__mthds_run_status
  - mcp__plugin_pipelex_pipelex__mthds_run_results
---

# Prepare Inputs for MTHDS methods

Prepare input data for running MTHDS method bundles. This skill is the single entry point for all input preparation needs: extracting a placeholder template, generating synthetic test data, integrating user-provided files, or any combination.

The target method comes in two forms, and every MCP call in this skill takes whichever one applies: a **local bundle** (a directory of `.mthds` files, submitted as `files`) or a **registered method** from the Pipelex catalog (its `mt_…` id, passed as `method_id` — no local files needed).

**Submitting a local bundle.** Each `files` item is either a path or inline contents, and for workspace files the path form is preferred:

- `{path: <absolute path to the .mthds file>}` — **prefer this.** It keeps the real path as provenance in diagnostics, and it spares you copying entire bundles into the request. The workshop resolves a path against **its own** working directory — wherever the harness launched it, which is not necessarily your bundle — so pass an absolute path rather than trusting a relative one to line up. (Same rule as the file *inputs* further down; anything you hand the server as a path follows it.)
- `{content: <file content>, uri: <path relative to the bundle dir>}` — the inline fallback. Use it when the server can't read the path, and note it is the **only** form the hosted console accepts, since that deployment has no filesystem.

## Requirements — the Pipelex MCP tools

This skill extracts the method's input template through the **`mthds_inputs_template`** tool, served by the plugin's `pipelex` MCP server. It is required — never hand-derive the template from the `.mthds` source.

- **If the tool is absent from this session** (the MCP server isn't connected), STOP and tell the user in one line: *"The Pipelex MCP server isn't connected — the plugin manifest spawns the local workshop (`npx -y @pipelex/mcp@latest`), so its absence usually means `node`/`npx` is unavailable or the spawn failed. Check the plugin's MCP connection (`/mcp`)."*
- **If a call returns `status: "error"` with an error of class `config`** (missing or rejected `PIPELEX_API_KEY`, unreachable API), STOP the same way and surface the error's `hint` verbatim. Never silently improvise a template.
- The server authenticates to the API with **`PIPELEX_API_KEY`** from the session environment — the same variable the plugin's validation hook documents.
- **`mthds_prepare_inputs`** is also **required**, whenever the assembled inputs carry a file-ish value (Image, Document) that is not already an `http(s)` URL or a `pipelex-storage://` reference — a local path, a `data:` URL, or inline bytes. It uploads those assets to Pipelex storage and rewrites the values, which is what makes them runnable: see [Prepare the inputs for a run](#prepare-the-inputs-for-a-run). Same discipline as above — an absent tool or a `config`-class error stops the skill; never hand-fake a storage reference. When every file-ish value is already pass-through, the step has nothing to do and may be skipped.
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

**Local bundle** (the usual case): determine the `.mthds` bundle and its output directory (`<output_dir>`). This is usually the directory containing `main.mthds` (e.g., `pipelex-wip/pipeline_01/`).

**Registered method**: when the user targets a catalog method by its `mt_…` id (and no local bundle is in play), there is no bundle directory — use the id as `method_id` in every MCP call instead of submitting `files`. `<output_dir>` is then a directory the user names, defaulting to a new `./<method_id>/` directory, and `inputs.json` goes there. A by-id call reads the method's **current stored content** from the org-scoped catalog, so it requires the API key.

The `inputs.json` file is saved directly in this directory:
- `<output_dir>/inputs.json`

If data files need to be generated or copied (images, PDFs, etc.), they go in a subdirectory:
- `<output_dir>/inputs/`

The `/inputs` subdirectory is only created when there are actual data files to store. Paths to these files are referenced from within `inputs.json`.

> **Path resolution rule**: URL/path values in `inputs.json` are resolved **relative to the `inputs.json` file itself** (i.e., relative to the bundle directory), NOT relative to the current working directory. When referencing local files, you MUST either:
> 1. **Copy files** into `<output_dir>/inputs/` and reference with a path relative to the `inputs.json` file, e.g., `inputs/the_doc.pdf` (preferred — keeps the bundle self-contained), or
> 2. **Use a URL or absolute path**, e.g., `https://example.com/doc.pdf` or `/Users/alice/data/invoice.pdf`

### Step 2: Get the Input Template

Call the **`mthds_inputs_template`** tool with the target from Step 1 — for a local bundle, the whole bundle: every `.mthds` file in `<output_dir>`, submitted as `files`; for a registered method, `method_id: "mt_…"` alone (the template is projected from the method's current stored content — never supply both, files would win and `method_id` would be ignored). Pass **`explicit: false`** — the tool's own default is the ceremonial `{concept, content}` envelope, and this skill works in the **light** shape (bare example values) end to end. The remaining defaults resolve the method's declared `main_pipe`. (To target a different pipe, pass `pipe_ref` as a qualified `domain.pipe_code`.)

Branch on the structured verdict, never on transport:

- `status: "ok"`, `is_valid: true` → the template is in `inputs`, with the resolved `pipe_ref`. This template is **authoritative** — fill in its values; never invent shapes it doesn't have.
- `status: "ok"`, `is_valid: false` → the method itself doesn't validate: report `validation_errors[]` (and the summary) to the user. For a local bundle, repair it first (e.g. via `/pipelex-design` resumption), then retry; for a registered method, the stored content is broken — it must be fixed where the method is edited (e.g. the webapp editor), not here.
- `status: "error"` → no verdict: class `config` → stop per the Requirements above; class `input_domain` → the call is malformed (an unknown `pipe_ref`, or `main_pipe` unresolvable — pass an explicit `pipe_ref`; for a by-id call, an error located at `method_id` means the id is unknown to the key's organization — the catalog is org-scoped, so another org's method reads exactly like a miss — or the stored method has no MTHDS source yet); class `runtime` → report and retry once.

**Example template** (the light shape `explicit: false` returns):

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

Every strategy that produces **real** values (Synthetic, User Data, Mixed) continues into [Prepare the inputs for a run](#prepare-the-inputs-for-a-run) once `inputs.json` is assembled. The Template strategy is the exception — placeholders are not assets, so there is nothing to prepare.

---

## Template Strategy

The fastest path. Produces a placeholder `inputs.json` that the user can fill in manually.

1. Take the `inputs` template from Step 2
2. For file-ish values (Image, Document), replace the mock URLs (e.g., `https://mock-xxxxxxxx.invalid/...`) with descriptive placeholder strings that explicitly tell the path resolution is relative to inputs.json, e.g:
  good: `"<VARNAME-url-or-path-relative-to-this-inputs-file>"` ✅ do this
  bad:  `"<path-to-VARNAME>"` ❌ don't do that
This placeholder means "replace with either a real URL, an absolute path, or a path relative to the saved `inputs.json` file itself," not relative to the current working directory.
3. Save it to `<output_dir>/inputs.json`
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

Fill the Step 2 template in place and save it to `<output_dir>/inputs.json`. Any generated data files go in `<output_dir>/inputs/`.

Then continue with [Prepare the inputs for a run](#prepare-the-inputs-for-a-run) — generated files are local paths, which a run cannot reach until they are uploaded.

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

Fill all matched values into the Step 2 template and save it as `<output_dir>/inputs.json`.

### Step G: Prepare

Continue with [Prepare the inputs for a run](#prepare-the-inputs-for-a-run) — the copies in `<output_dir>/inputs/` are local paths, which a run cannot reach until they are uploaded.

### Step H: Report

Show the user:
- Which files were matched to which inputs
- Any unfilled inputs (offer synthetic or placeholder)
- The final `inputs.json` content (after preparation) and which files were uploaded
- Path to the saved file

---

## Mixed Strategy

Combines user data with synthetic generation for any remaining gaps.

1. Follow [User Data Strategy](#user-data-strategy) Steps A-F to match user files
2. For each unfilled input, apply [Synthetic Strategy](#synthetic-strategy)
3. Assemble the complete `inputs.json` combining both sources
4. Continue with [Prepare the inputs for a run](#prepare-the-inputs-for-a-run) — one call covers both sources' files
5. Report which inputs came from user data, which were synthesized, and which were uploaded

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

## Prepare the inputs for a run

A local file is not runnable as it stands: a run executes on the hosted Pipelex API, which cannot read your disk. The **`mthds_prepare_inputs`** tool closes that gap — it uploads every file-bearing value to Pipelex storage and rewrites it to a `pipelex-storage://` reference the run accepts. It is the step between assembly and execution: template → fill → **prepare** → run.

Run it once `inputs.json` holds real values (Synthetic, User Data, Mixed). **Skip it** for the Template strategy — placeholders are not assets — and when every file-ish value is already an `http(s)` URL or a `pipelex-storage://` reference, since there is then nothing to upload.

### File fidelity and the storage-size boundary

Once a file has been selected, generated, copied, or referenced for an input, send that exact asset to `mthds_prepare_inputs`. A preflight size check may inform the report, but it is never a reason to transform, derive, or substitute the asset before the call. Do not compress, optimize, re-encode, resize, downsample, split, truncate, extract pages or content, or convert it. Do not replace it with synthetic data, a public sample, another local file, or any derived file. This rule applies to every file-bearing input, not only PDFs.

The same prohibition applies after an upload failure. Never retry preparation with altered or substitute content to evade a storage limit. Continue only when the user supplies a different acceptable input or reference, or when the service limit changes. Resolving an unreadable local path to an absolute path is the one distinct recovery described below: it changes only the path sent to the tool, never the file, its bytes, the copied bundle asset, or the local-path form saved in `inputs.json`.

**Say what is about to leave the machine, before it does.** Preparation is the point where the user's own files go to remote storage, so name them and their destination *before* the call, not only in the report afterwards:

> Preparing 2 files for the run — uploading `inputs/invoice.pdf` and `inputs/cv.pdf` to Pipelex storage (your organization, via your API key).

In **interactive mode**, wait for the user to confirm. In **automatic mode**, state it and proceed — the user asked for run-ready inputs, and this is what makes them run-ready. Either way the user learns which files are involved while they can still say no, swap a file, or drop one. Name the files individually; for a folder batch too long to list, give the count and the folder. If the user declines, stop before the call and report that the inputs stay local and are not runnable as they are.

1. **Call `mthds_prepare_inputs`** with:
   - the **same target as Step 2** — the whole-bundle `files` submission, or `method_id: "mt_…"` for a registered method;
   - the same **`pipe_ref`**, if Step 2 passed one. The pipe's declared signature is what identifies which values are assets, so letting it fall back to `main_pipe` would inspect the wrong contract;
   - `inputs` — the parsed content of the `inputs.json` you just saved, with one adjustment: **resolve every local file path to an absolute path first**. `inputs.json` stores paths relative to itself, but the MCP server resolves a local path against **its own working directory** — wherever the host launched it, which is not your bundle. Sent as-is, a relative `inputs/cv.pdf` fails with `Local file cannot be read: "inputs/cv.pdf" (ENOENT)`. Send `<output_dir>/inputs/cv.pdf` expanded to an absolute path instead. `http(s)` URLs and `pipelex-storage://` references need no adjustment, and `inputs.json` itself keeps its relative paths — only what you send changes. There is no `explicit` flag here; the light shape is accepted as-is.
2. **Branch on the structured verdict.** Unlike `mthds_inputs_template`, this tool has **no produced-invalid arm** — it never returns a `validation_errors[]` list:
   - `status: "ok"` → the run-ready inputs are in `inputs`, and `uploads[]` carries the `pipelex-storage://` uris created by this call (`[]` when everything passed through).
   - `status: "error"`, class `input_domain` → **read the error's `location`** before reacting, because the two causes need opposite repairs:
     - `location: "inputs"` **and the response reports a storage size limit** → this is a terminal branch for the current preparation attempt. Report the affected input and file; quote the tool's exact `message` and `hint` verbatim; and include the actual file size and the allowed limit whenever the response provides them, whether as fields or inside those diagnostics. State explicitly that preparation failed, the inputs are not run-ready, and the method will not be offered or submitted for a run. Make no follow-up file writes: preserve the user's original file, the copied file in `<output_dir>/inputs/`, and the local-path form of `<output_dir>/inputs.json` unchanged. Do not transform or substitute the asset, do not retry `mthds_prepare_inputs` with altered content, and do not call `mthds_run`. Continue only after the user supplies a different acceptable input or reference, or the service limit changes.
     - `location: "inputs"` **and the response is not a size-limit failure** → surface the exact `message` and `hint`, then follow only the recovery they support. For an unreadable local file, verify that the same file exists, resolve its path to absolute per step 1, and retry preparation with the file bytes unchanged; this request-only path correction must not rewrite the local relative path in `inputs.json`. For any other asset failure, retry only when the documented error policy explicitly permits a recovery that preserves the asset's content and identity. The method is not at fault, so don't revalidate it: `mthds_validate` and `mthds_inputs_template` only inspect the method definition and will keep answering "valid" while the same asset keeps failing.
     - `location: "pipe_ref"` / `"method_id"` → the closure didn't resolve (invalid bundle, unknown `pipe_ref`, unresolvable `main_pipe`, or a method id with no stored source). This is the arm whose diagnostics the tool delegates: get the structured errors from `mthds_validate` / `mthds_inputs_template`, repair, then retry.
   - `status: "error"`, class `config` → stop per the Requirements above and surface the `hint` verbatim.
   - `status: "error"`, class `runtime` → report and retry once.
3. **Rewrite `<output_dir>/inputs.json` with the returned `inputs`.** Leave the copies in `<output_dir>/inputs/` on disk — they are the user's own reference, and the uploaded bytes no longer depend on them. Only the values in `inputs.json` change, and file-ish values change **shape** as well as content: a bare path or URL string becomes the canonical content dict `{"url": "…"}`. That is the run-ready form; don't "simplify" it back to a bare string.

   ```json
   {
     "invoice": {"url": "pipelex-storage://user/assets/1.pdf"},
     "instructions": "Extract all line items, totals, and vendor information."
   }
   ```

   Text, scalar, and structured values are untouched.
4. **Report it in one line**, e.g. *"2 files uploaded to Pipelex storage; `inputs.json` now references them."*

A prepared `inputs.json` stays runnable on later runs — `pipelex-storage://` references pass through both prepare and run unchanged.

---

## Finish

After assembling the inputs, confirm readiness:

> Inputs are ready. `inputs.json` has been saved with real values — no placeholders remain, and every file value is run-ready.

(Or, for the Template strategy: point out which placeholders the user still needs to fill.)

### Offer to run

When the inputs are complete, close by offering to run the method. Offer — never start unprompted: a run executes on the hosted Pipelex API and **spends inference credit**.

Offer only when all of these hold:

- The `mthds_run` tool is present in the session (it is optional — when absent, just finish).
- No placeholders remain (a Template-strategy result has nothing to run yet).
- The inputs are **run-ready**: [prepare](#prepare-the-inputs-for-a-run) succeeded on the final `inputs.json`, or was legitimately skipped because every file-ish value was already an `http(s)` URL or a `pipelex-storage://` reference. Local paths, `data:` URLs, and inline bytes are perfectly fine going *into* prepare — they just must not survive into the run. If prepare failed, don't offer: report the failure and what it would take to fix (text, scalar, and structured values are sent inline and are never the problem).

On acceptance:

1. For a **by-id** target: a run executes the method's **current stored content** (methods are not versioned — it does not pin what Step 2 projected), so re-call `mthds_inputs_template` with the same `method_id`, the same `explicit: false`, and the same `pipe_ref`, if Step 2 passed one, so the drift check compares against the pipe actually targeted rather than falling back to `main_pipe` — to catch drift since Step 2. Compare the fresh template against `inputs.json` on **both keys and value shapes**. A renamed, added, or dropped input changes the key set — but a *retyped or reshaped* one does not: `payload` going from `Text` to `Number`, or a structured concept gaining, losing, or renaming a field, leaves the keys identical while making every saved value stale. So also check, per key, that the JSON kind still matches (string / number / boolean / list / dict) and that a structured value's field names still match the template's.

   **One difference is expected and is not drift:** a file-ish input (Image, Document) arrives in the template as a bare URL-or-path string, while a *prepared* `inputs.json` holds the canonical content dict `{"url": "pipelex-storage://…"}`. That is the [prepare](#prepare-the-inputs-for-a-run) rewrite, not a signature change — for a file-ish input, treat a bare-string template value against a `{"url": …}` filled value as a match. Flagging it would refuse every legitimate by-id run that uploaded a file.

   On a genuine mismatch of either kind, the method changed underneath you — stop, report which inputs drifted and how, and send the user back to `/pipelex-inputs` to re-prepare before spending credit on a run that won't match. Keys and shapes both match → proceed. (A swap between two concepts of the same JSON kind — `Text` to `Date`, both strings — is invisible to this check; the run's own validation is what catches that.)
2. Call `mthds_run` with the same target as Step 2 — the whole-bundle `files` submission, or `method_id: "mt_…"` for a registered method — and `inputs` set to the parsed content of the **prepared** `inputs.json`, verbatim. Omit `pipe_code` to run the method's declared main pipe; pass a pipe's code only when the user targeted a different pipe in Step 2.
3. The tool returns a durable `run_id` immediately and never blocks. Report the id, then check with `mthds_run_status`, honoring the summary's retry hint — don't poll in a tight loop.
4. Once terminal, fetch `mthds_run_results` and report the main output (or the failure message).

---

## Value shapes (light format)

`inputs.json` is **filled** in the **light** shape — the same shape the Step 2 template arrives in when called with `explicit: false`. Scalars are bare values; structured concepts are their content dict, with **no** `{concept, content}` envelope:

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

That is the shape you *write*. After [prepare](#prepare-the-inputs-for-a-run) the file-ish values come back as canonical content dicts — `{"url": "pipelex-storage://…"}` instead of a bare path or URL string — and that rewritten form is what `inputs.json` holds from then on. Everything else keeps the shape above.

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
5. Prepare: `image` is a local path, so [prepare](#prepare-the-inputs-for-a-run) uploads it and rewrites `inputs.json` before the run is offered

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
7. Prepare: `invoice` is a local path, so call `mthds_prepare_inputs` with the same bundle `files` and these `inputs`. It uploads the PDF and returns the run-ready set, which is written back over `inputs.json`:
```json
{
  "invoice": {"url": "pipelex-storage://user/assets/1.pdf"},
  "instructions": "Extract all line items, totals, and vendor information from this invoice."
}
```
   `uploads` lists that one new uri; `inputs/invoice.pdf` stays on disk untouched. The method is now runnable — offer it.

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
5. Prepare: all three are local paths — one [prepare](#prepare-the-inputs-for-a-run) call uploads the whole list and rewrites it to `[{"url": "pipelex-storage://…"}, …]`

---

## Reference

- [MTHDS Language Reference](../shared/mthds-reference.md) — read for concept definitions and syntax
- [Native Content Types](../shared/native-content-types.md) — read for the full attribute reference of each native content type when filling composite or structured values
