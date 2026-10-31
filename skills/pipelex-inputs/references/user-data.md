# The User data strategy

Read this at step 3 when the strategy is User data, or Mixed, before matching any file to an input. It covers finding the user's files, matching them to the template's inputs and filling their values with the files where they lie, and the copies a case of `pipelex-lab` asks for; the skill's guards hold throughout, the path rule of `inputs.json` included.

In interactive mode, ask which of the user's files goes to which input wherever that is ambiguous, and any specific values or constraints the user wants on a field.

## Inventory

Collect every file the user has provided as a sample input: explicit paths, folders, and files mentioned earlier in the conversation whose role was settled as one. A file given earlier as a brief, an example output, a template or reference material is left out, however the later request is worded, unless it is reference material the method takes as an input, and a file whose role was never settled is settled first, as the skill's step 3 says, before it is matched. A file the user names that is not on disk, such as one already uploaded to Pipelex, is looked up among the team's files as the skill's step 3 says, and fills its input by its address, with nothing to upload. Determine each one's type:

| Extension | Detected type | Maps to |
|---|---|---|
| `.pdf` | PDF document | `native.Document` |
| `.docx`, `.doc` | Word document | `native.Document`, exported to PDF first (below) |
| `.xlsx`, `.xls` | spreadsheet | `native.Document`, exported to PDF first (below) |
| `.pptx`, `.ppt` | presentation | `native.Document`, exported to PDF first (below) |
| `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.svg`, `.tiff`, `.tif`, `.bmp` | image | `native.Image` |
| `.txt` | plain text | `native.Text`, the file's content read in |
| `.md` | Markdown text | `native.Markdown` or `native.Text`, whichever the input declares, the file's content read in |
| `.json` | JSON data | `native.JSON` or a custom structured concept |
| `.csv` | CSV data | `native.Text` read as text, or `native.JSON` parsed into objects |
| `.html`, `.htm` | HTML | `native.Html` |
| `http://…`, `https://…` | web page URL | `native.Document` |

**An Office file goes in as the PDF exported from it.** Extraction reads a PDF, an image or a web page, and nothing else, so a Word, Excel or PowerPoint file under a `Document` input fails the run at its first step. Where `soffice` is on PATH, convert each file on its own into a fresh temporary directory (`soffice --headless --convert-to pdf --outdir "$(mktemp -d)" <file>`), never beside the method or the original: LibreOffice names the PDF after the source file and replaces a file of that name without asking, so two sources sharing a stem would overwrite each other, and an export beside the method would travel as one of its files. Say so, and from then on treat that PDF as the file selected for the input: `inputs.json` names it where it lies, in its temporary directory, a case's copy names it after its input like any other, and step 5 of the skill sends it as it is, in place of the original. Without `soffice`, ask the user to export it to PDF, and leave that input unfilled until they do. Never rename an Office file to `.pdf`.

**A folder, or files given together**: list a folder's files — non-recursively by default, recursively if the user asks — and take files given together, attached to one message or named in one breath, as the user gave them; keep the supported types, group them by detected type, and match them to list inputs (`Image[]`, `Document[]`, …). A folder `./invoices/` holding five PDFs, or five PDFs attached to one message, for a method expecting `documents: Document[]`, maps all five to that one input.

## Match

For each input variable of the template, apply these rules in order:

1. **Exact name**: the input `invoice` matches a file named `invoice.pdf`. A list input named like one file of several given together never takes that file alone: they go to it by rule 4, all of them when the list is the method's only input of that type.
2. **Type, one candidate**: if only one input expects `native.Image` and the user provided exactly one image, match them.
3. **Type, several candidates**: for an input that takes a single file, in automatic mode, match by name similarity, variable name against filename; in interactive mode, ask the user which file goes where.
4. **Files to list**: a folder holding files of a single type, or several files of one type given together, goes to an input expecting a list of that type, in the order given, a folder's files in the order listed. When that list is the method's only input of that type, they go to it whole, and rules 1 to 3 never take one of them alone, not even by its exact name: a list input `invoices` given `march.pdf`, `invoices.pdf` and `may.pdf` together takes all three, in that order, and rule 5 reports none of them as unmatched. When several inputs could take them, a list beside an input that takes one file or two lists of that type, no file goes to two inputs. An input that takes one file takes its file by rules 1 to 3 and the list takes the rest, in the order given: for `job_ad: Document` and `cvs: Document[]`, given `job-ad.pdf`, `alice.pdf` and `bob.pdf` together, `job_ad` gets `job-ad.pdf` and `cvs` the other two. Between two lists, split the files by name similarity only where it places every file beyond doubt, and otherwise ask the user which files go to which input, in automatic mode too, since a wrong split changes the run without a sign.
5. **An unmatched file**: report it, and ask whether it should be ignored or mapped to a specific input. Files of one type given together when the method's only input of that type takes one file are the exception: they are cases of that input, as the shared file-roles reference says, so the one rules 1 to 3 matched fills it and the report names the others as cases to try next.
6. **An input still unfilled** after matching stays a placeholder or is filled with synthetic data, which is the Mixed strategy.

## Where the files lie

Each matched file stays where the user keeps it, and is never copied, moved or changed: `inputs.json` names it by its absolute path, and step 5 uploads it from there and writes its address in its place. For a local bundle `<output_dir>` is the method's folder, which every surface that hands over the method sends whole, the workshop's validation and run, a catalog save, the edit hook and an integrated call site, and which a Python package that holds the method ships in its wheel. A copy there would travel as a file of the method, so none is made. Uploading the same bytes again under the same name finds the same file among the team's files, so preparing again costs nothing.

## A case's copies

When the calling skill asks for a case's copies, as `pipelex-lab` does for each case of its own, or `<output_dir>` is a lab case, `lab/<method>/cases/<case>/`, as when the user prepares one directly or `pipelex-run` hands one back, `<output_dir>` is the case's directory, outside every method, and the files are copied in so that the case runs from any clone. Copy each file into `<output_dir>/inputs/`, so `inputs.json` names it with a path relative to itself, and leave that folder unmarked: the lab commits a case made only of synthetic files, and keeps a case of the user's own files out of git itself. Create `inputs/` only when there is a file to copy.

**Never link it there**: a link names a path on this machine, which no other clone holds. A link an earlier preparation left in `inputs/` is replaced by a copy of the file it points to, under the same name, saying so. Name a single file's copy after its input, keeping the original extension: the input `invoice` becomes `<output_dir>/inputs/invoice.pdf`. A list input's files go in a directory named after the input, each named by its position in the list with its original extension (`inputs/images/1.jpg`, `inputs/images/2.png`): no two positions share a name, and a single input's copy never lands in a list's directory, so no copy overwrites another's.

## Fill

Set each matched input's light value:

- a Document: the file's absolute path, `"invoice": "/Users/jane/documents/invoice_march.pdf"`, or a case's copy, `"invoice": "inputs/invoice.pdf"`;
- a web page Document: the URL string, `"page": "https://example.com/article"`;
- an Image: the file's absolute path, `"photo": "/Users/jane/photos/storefront.jpg"`, or a case's copy, `"photo": "inputs/photo.jpg"`;
- a Text from a `.txt` or `.md` file: the file's actual content as the string value;
- a list, from a folder or from files given together: a list of those values in the order given, `"images": ["/Users/jane/product-photos/shoe.jpg", "/Users/jane/product-photos/hat.png"]`, or a case's copies, `["inputs/images/1.jpg", "inputs/images/2.png"]`;
- a file from the team's files: its address as listed, `"invoice": "pipelex-storage://…"`, which step 5 passes through.

Fill the skill's step 2 template in place and save it as `<output_dir>/inputs.json` (the skill's step 4); the skill's step 5 then prepares it, since a local path is one a run cannot reach until it is uploaded. In the Mixed strategy, the inputs no file matched are filled with synthetic data before saving, and step 5 then uploads both sources' files, in two calls when the user's files need an upload too, since only the factory's go up as test files.

## Report

After the skill's step 5, and before its step 6 offers the run, show the user which files were matched to which inputs; any input left unfilled, offering synthetic data or a placeholder; which files were uploaded, from where; the final `inputs.json` content, which names each uploaded file by its address, or for a case's copies the `inputs.prepared.json` written beside it; and the path of the saved file. In the Mixed strategy, say which inputs came from the user's files, which from the team's files, which were synthesized, and which were uploaded.

## Worked examples

**A user's invoice PDF.** An invoice processor expects `invoice: Document` and `instructions: Text`, and the user says "use my file `~/documents/invoice_march.pdf`".

1. The template needs `invoice` (Document) and `instructions` (Text).
2. The user provided `invoice_march.pdf`, a PDF, so a Document.
3. `invoice_march.pdf` maps to `invoice` by name similarity and type.
4. It stays where it is, and its path is resolved to an absolute one: `/Users/jane/documents/invoice_march.pdf`.
5. No file fills `instructions`, so its text is synthesized.
6. Save `inputs.json`:

   ```json
   {
     "invoice": "/Users/jane/documents/invoice_march.pdf",
     "instructions": "Extract all line items, totals, and vendor information from this invoice."
   }
   ```

7. `invoice` is a local path, so step 5 says that the PDF is about to go to Pipelex storage, then calls `mthds_prepare_inputs` with the same `method_dir` and these `inputs`. It uploads the PDF from where it lies and returns the run-ready set, which is written over `inputs.json`:

   ```json
   {
     "invoice": {"url": "pipelex-storage://user/assets/1.pdf"},
     "instructions": "Extract all line items, totals, and vendor information from this invoice."
   }
   ```

   `uploads` lists that one new uri, the PDF stays in `~/documents/` untouched, and nothing was copied beside the method. The method is now runnable, so the run is offered.

**A folder of images.** A batch image captioner expects `images: Image[]`, and the user says "use the photos in `./product-photos/`", which holds `shoe.jpg`, `hat.png` and `bag.jpg`. All three stay where they are, and `inputs.json` names them by their absolute paths:

```json
{
  "images": ["/Users/jane/shop/product-photos/shoe.jpg", "/Users/jane/shop/product-photos/hat.png", "/Users/jane/shop/product-photos/bag.jpg"]
}
```

All three are local paths, so one prepare call uploads the whole list, and `inputs.json` then holds it as `[{"url": "pipelex-storage://…"}, …]`. Had `pipelex-lab` asked for a case's copies, the three would have been copied into `<output_dir>/inputs/images/` as `1.jpg`, `2.png` and `3.jpg`, `inputs.json` would name those copies, and the run-ready list would go to `inputs.prepared.json` beside it.
