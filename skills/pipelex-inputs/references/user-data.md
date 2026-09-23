# The User data strategy

Read this at step 3 when the strategy is User data, or Mixed, before matching any file to an input. It covers finding the user's files, matching them to the template's inputs, copying them in and filling their values; the skill's guards hold throughout, the path rule of `inputs.json` included.

In interactive mode, ask which of the user's files goes to which input wherever that is ambiguous, and any specific values or constraints the user wants on a field.

## Inventory

Collect every file the user has provided: explicit paths, folders, and files mentioned earlier in the conversation. Determine each one's type:

| Extension | Detected type | Maps to |
|---|---|---|
| `.pdf` | PDF document | `native.Document` |
| `.docx`, `.doc` | Word document | `native.Document` |
| `.xlsx`, `.xls` | spreadsheet | `native.Document` |
| `.pptx`, `.ppt` | presentation | `native.Document` |
| `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.svg`, `.tiff`, `.tif`, `.bmp` | image | `native.Image` |
| `.txt` | plain text | `native.Text`, the file's content read in |
| `.md` | Markdown text | `native.Text`, the file's content read in |
| `.json` | JSON data | `native.JSON` or a custom structured concept |
| `.csv` | CSV data | `native.Text` read as text, or `native.JSON` parsed into objects |
| `.html`, `.htm` | HTML | `native.Html` |
| `http://…`, `https://…` | web page URL | `native.Document` |

**A folder**: list its files — non-recursively by default, recursively if the user asks — keep the supported types, group them by detected type, and match them to list inputs (`Image[]`, `Document[]`, …). A folder `./invoices/` holding five PDFs, for a method expecting `documents: Document[]`, maps all five to that one input.

## Match

For each input variable of the template, apply these rules in order:

1. **Exact name**: the input `invoice` matches a file named `invoice.pdf`.
2. **Type, one candidate**: if only one input expects `native.Image` and the user provided exactly one image, match them.
3. **Type, several candidates**: in automatic mode, match by name similarity, variable name against filename; in interactive mode, ask the user which file goes where.
4. **Folder to list**: a folder holding files of a single type goes to an input expecting a list of that type.
5. **An unmatched file**: report it, and ask whether it should be ignored or mapped to a specific input.
6. **An input still unfilled** after matching stays a placeholder or is filled with synthetic data, which is the Mixed strategy.

## Copy

Copy — or symlink — each file into `<output_dir>/inputs/`, so `inputs.json` names it with a path relative to itself and the directory stays self-contained. Name a single file's copy after its input, keeping the original extension: the input `invoice` becomes `<output_dir>/inputs/invoice.pdf`. A list input's files go in a directory named after the input and keep their own names (`inputs/images/shoe.jpg`), two that share a name getting an index (`inputs/images/shoe_1.jpg`): a single input's copy never lands in a list's directory, so no copy overwrites another's. Create `inputs/` only when there is a file to copy.

## Fill

Set each matched input's light value:

- a Document: the path string, `"invoice": "inputs/invoice.pdf"`;
- a web page Document: the URL string, `"page": "https://example.com/article"`;
- an Image: the path string, `"photo": "inputs/photo.jpg"`;
- a Text from a `.txt` or `.md` file: the file's actual content as the string value;
- a list, from a folder for instance: a list of those values, `"images": ["inputs/img_001.jpg", "inputs/img_002.jpg", "inputs/img_003.png"]`.

Fill the skill's step 2 template in place and save it as `<output_dir>/inputs.json` (the skill's step 4); the skill's step 5 then prepares it, since the copies in `<output_dir>/inputs/` are local paths, which a run cannot reach until they are uploaded. In the Mixed strategy, the inputs no file matched are filled with synthetic data before saving, and one prepare call then covers both sources' files.

## Report

After the skill's step 5, and before its step 6 offers the run, show the user which files were matched to which inputs; any input left unfilled, offering synthetic data or a placeholder; the final `inputs.json` content, which files were uploaded, and whether `inputs.prepared.json` was written beside it; and the path of the saved file. In the Mixed strategy, say which inputs came from the user's files, which were synthesized, and which were uploaded.

## Worked examples

**A user's invoice PDF.** An invoice processor expects `invoice: Document` and `instructions: Text`, and the user says "use my file `~/documents/invoice_march.pdf`".

1. The template needs `invoice` (Document) and `instructions` (Text).
2. The user provided `invoice_march.pdf`, a PDF, so a Document.
3. `invoice_march.pdf` maps to `invoice` by name similarity and type.
4. Copy it: `cp ~/documents/invoice_march.pdf <output_dir>/inputs/invoice.pdf`.
5. No file fills `instructions`, so its text is synthesized.
6. Save `inputs.json`:

   ```json
   {
     "invoice": "inputs/invoice.pdf",
     "instructions": "Extract all line items, totals, and vendor information from this invoice."
   }
   ```

7. `invoice` is a local path, so step 5 calls `mthds_prepare_inputs` with the same bundle `files` and these `inputs`, the path sent absolute. It uploads the PDF and returns the run-ready set, which is written to `inputs.prepared.json` beside an unchanged `inputs.json`:

   ```json
   {
     "invoice": {"url": "pipelex-storage://user/assets/1.pdf"},
     "instructions": "Extract all line items, totals, and vendor information from this invoice."
   }
   ```

   `inputs.json` still reads `"invoice": "inputs/invoice.pdf"`, `uploads` lists that one new uri, and `inputs/invoice.pdf` stays on disk untouched. The method is now runnable, so the run is offered.

**A folder of images.** A batch image captioner expects `images: Image[]`, and the user says "use the photos in `./product-photos/`", which holds `shoe.jpg`, `hat.png` and `bag.jpg`. All three are copied into `<output_dir>/inputs/images/`, and `inputs.json` is:

```json
{
  "images": ["inputs/images/shoe.jpg", "inputs/images/hat.png", "inputs/images/bag.jpg"]
}
```

All three are local paths, so one prepare call uploads the whole list: `inputs.prepared.json` holds it as `[{"url": "pipelex-storage://…"}, …]`, while `inputs.json` keeps the three paths.
