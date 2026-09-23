# The Synthetic strategy

Read this at step 3 when the strategy is Synthetic, or Mixed with inputs the user's files leave unfilled, before generating any value. It says what to generate for each input and what to hand the file factory; step 3 of the skill says how to invoke the factory on this harness, and the skill's guards hold throughout.

In interactive mode, ask first for the domain or industry context that makes the data realistic, whether to generate edge cases or happy-path data, and any specific values or constraints the user wants on a field.

## What each input needs

The light value to produce, by declared concept:

| Concept | Light value | How to make it |
|---|---|---|
| `native.Text` | bare string | realistic text matching the method's purpose: invoice-like text for a method that processes invoices, report-style content for one that analyzes reports, at the expected length (a short prompt is not a long document) |
| `native.Number` | bare number | a sensible value within the range the method's context implies |
| `native.YesNo` | bare boolean | a `true` or `false` answer |
| `native.Date` | bare ISO 8601 date string | a date or time value; never an epoch number |
| `native.Image` | bare URL-or-path string | the file factory, below |
| `native.Document` | bare URL-or-path string | the file factory, below |
| `native.Page`, `native.TextAndImages`, `native.JSON` | the content dict the template gives | fill the template's fields in place |
| a custom structured concept | its fields directly | fill each field according to its type and description |

A list input (`Type[]` or `Type[N]`) arrives wrapped in a list: generate several items, usually 2 to 5 for a variable list and exactly N for a fixed one.

## A file input

When an input needs an actual file — `native.Image`, `native.Document`, a Word or Excel file — the skill does not make it. The `pipelex-synthetic-inputs` skill renders PDFs and PNGs from code, no AI involved, and installs the Python packages it needs on its own. Hand it one request per file:

| Field | What to pass |
|---|---|
| `format` | `pdf` for `native.Document`, `png` for `native.Image` — plus the PNG category when the method implies one (`chart`, `diagram`, `document_scan`, `screenshot`); `docx` / `xlsx` when the method asks for those |
| `brief` | one or two sentences in the method's own vocabulary — "an invoice from a hardware store with ten line items and a VAT total", not "a document" |
| `target` | `<output_dir>/inputs/<input_variable>.<ext>`; a list input's items go in a directory named after it, one index each (`<output_dir>/inputs/<input_variable>/1.<ext>`), so an item never takes another input's name |
| `constraints` | whatever the input's description pins: page count, pixel size, language |

It writes the file, verifies it, and returns the path. Put that path into the template as a bare string, relative to `inputs.json` — `inputs/invoice.pdf` — and step 5 uploads it later, unchanged.

It returns no path when it cannot make the file — no `uv`, no usable Python, or a brief it refuses, such as a photograph or handwriting — and says why. That is not a failure of the flow; the skill's stop table says what to do with that one input.

## Then

Fill the step 2 template in place and save it as `<output_dir>/inputs.json` (step 4), with any generated file in `<output_dir>/inputs/`. Then go on to step 5: a generated file is a local path, which a run cannot reach until it is uploaded.

## A worked example

A sales-chart reader expects `chart: Image` and `analysis_prompt: Text`.

1. Get the template; the method needs an image it can read as a chart, and instruction text.
2. `chart` is `native.Image`, so it goes to the factory: `format: png` with category `chart`, `brief: "a grouped bar chart of quarterly units shipped for three regions, with a legend and axis labels"`, `target: <output_dir>/inputs/chart.png`. It returns that path.
3. Write an analysis prompt matching the method's context.
4. Save `inputs.json`:

   ```json
   {
     "chart": "inputs/chart.png",
     "analysis_prompt": "Read this chart. Report the trend per region and name the strongest quarter."
   }
   ```

5. `chart` is a local path, so step 5 uploads it and writes the run-ready form to `inputs.prepared.json`, leaving `inputs.json` as saved, before the run is offered.

Had the method wanted a photograph of a street scene, the factory would have come back with no path and an ask for a real file, since code cannot render a photograph honestly. `analysis_prompt` would still be filled, `inputs.json` still written, and the report would say which input is waiting on the user and why.
