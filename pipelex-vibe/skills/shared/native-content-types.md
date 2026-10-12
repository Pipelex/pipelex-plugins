# Native Content Types Reference

Each native concept maps to a content class with specific attributes. Understanding these attributes helps when:

- Writing `$var.field` references in prompts or PipeCompose templates
- Building `construct` blocks with `from = "input.field"`
- Writing a binding step's path in a PipeSequence (`{ from = "page.page_view", result = "page_view" }`) or a dotted `batch_over`, whose result takes the concept of the attribute it reaches
- Interpreting pipeline outputs (e.g., what comes out of PipeExtract)
- Preparing input JSON for running a method

A path never goes into an input name: an input is a plain name holding one whole value, and `"page.page_view" = "Image"` is refused as `invalid_input_name`. A pipe reads an attribute through the whole value it declares (`$page.page_view`), or receives the attribute under a plain name from a binding step in its sequence.

## Content Type Summary

| Native Concept | Content Class | Key Attributes |
|----------------|---------------|----------------|
| `Text` | TextContent | `text` |
| `Markdown` | MarkdownContent | `text` (the Markdown source) |
| `Number` | NumberContent | `number` |
| `YesNo` | YesNoContent | `yes_no`, `probability` (only when the producer reports one) |
| `Choice` | ChoiceContent | `choice`, `confidence`, `probabilities` |
| `Rating` | RatingContent | `level`, `label` (only when the scale declares labels), `confidence`, `probabilities`, `position` |
| `Date` | DateContent | `date`, `time` (only when the source states one) |
| `Time` | TimeContent | `time` |
| `Image` | ImageContent | `url`, `filename`, `caption`, `mime_type`, `width`, `height` |
| `Document` | DocumentContent | `url`, `public_url`, `filename`, `mime_type`, `title`, `snippet` |
| `Html` | HtmlContent | `inner_html`, `css_class` |
| `TextAndImages` | TextAndImagesContent | `text` (TextContent), `images` (list of ImageContent), `raw_html` (str) |
| `Page` | PageContent | `text_and_images` (TextAndImagesContent), `page_view` (ImageContent, only with `page_views = true` on a PDF) |
| `JSON` | JSONContent | `json_obj` |
| `SearchResult` | SearchResultContent | `answer`, `sources` (list of DocumentContent) |
| `Anything` | *(any content)* | depends on actual content |
| `Dynamic` | DynamicContent | user-defined fields |
| `Composite` | CompositeContent | one field per component, named when the composition is made (a `PipeParallel`'s branch `result` names) |

**In a binding step's path**, a native whose value is its one attribute, `Text` (`text`), `Markdown` (`text`), `Number` (`number`), `Time` (`time`) or `JSON` (`json_obj`), is a leaf: bind it whole, `from = "note"`, since `from = "note.text"` is refused as `binding_path_unresolved`, even though `$note.text` works in a prompt. A native with several attributes is walked through them, and the binding copies everything the path reaches: `page.page_view` binds an `Image`, its `caption` included, and `page.page_view.caption` a `Text`. `Dynamic`, `Anything` and `Composite` declare no attributes, so a path cannot go into them.

## Detailed Attribute Reference

### Text — `TextContent`

| Attribute | Type | Description |
|-----------|------|-------------|
| `text` | `str` | The text content |

**Access**: `$var` or `$var.text` in prompts.

---

### Markdown — `MarkdownContent`

A text written in Markdown. `Markdown` refines `Text` and keeps its one field.

| Attribute | Type | Description |
|-----------|------|-------------|
| `text` | `str` | The Markdown source |

A `Markdown` value goes wherever a `Text` does, and a pipe taking `Text` receives its source; a `Text` is not accepted where a `Markdown` is required, since nothing says it was written as Markdown. What sets it apart is how it is shown: an HTML template and a PDF a `PipeDocGen` lays out format it, with its headings, lists, tables and links, where a `Text` prints as it is.

**Access**: `$var` or `$var.text` in prompts, both the source as it is. Inside an HTML template, `{{ var }}` and `$var` print it converted to HTML, with no filter, and `{{ var.text }}` prints the source, escaped.

---

### Number — `NumberContent`

| Attribute | Type | Description |
|-----------|------|-------------|
| `number` | `int \| float` | The numeric value |

**Access**: `$var` or `$var.number` in prompts.

---

### YesNo — `YesNoContent`

| Attribute | Type | Description |
|-----------|------|-------------|
| `yes_no` | `bool` | Whether the answer is yes (`true`) or no (`false`) |
| `probability` | `float` or `None` | The probability that the answer is yes, from 0 to 1, when the producer reports one |

**Access**: `$var.yes_no` in prompts.

---

### Choice — `ChoiceContent`

One option picked out of a set.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `choice` | `str` | yes | The key of the selected option |
| `confidence` | `float \| None` | no | The producer's confidence in the choice, from 0 to 1, when it reports one |
| `probabilities` | `dict[str, float] \| None` | no | The probability of each option, keyed by option key, when the producer measures a distribution |

**Access**: `$var` renders the key alone, as does `$var.choice`. A `PipeCondition` routes by it with `expression = "team.choice"`.

---

### Rating — `RatingContent`

A position on an ordered scale of described levels.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `level` | `int` | yes | The index of the selected level, 0 being the first level declared |
| `label` | `str \| None` | no | The selected level's label, when the scale declares labels |
| `confidence` | `float \| None` | no | The producer's confidence in the level, from 0 to 1, when it reports one |
| `probabilities` | `dict[str, float] \| None` | no | The probability of each level, keyed by the level's index written as text (`"0"`, `"1"`, …), when the producer measures a distribution |
| `position` | `float \| None` | no | A continuous position on the scale, from 0 to the last level's index, when the producer measures one |

**Access**: `$var` renders the label when there is one and the level otherwise; `$var.level` is always the index. A `PipeCondition` branches on the level, which every rating has: `expression = "'severe' if severity.level >= 2 else 'mild'"`.

**`YesNo`, `Choice` and `Rating` are verdicts, and each requires its verdict and nothing else**: the boolean, the key, the level. Every measure beside it is optional, and a producer that measures nothing leaves it absent, never at 1. A `PipeLLM` whose output is one of them may fill the measures with its own estimate. A condition that gates on a measure guards against its absence, as in `approved.probability is not none and approved.probability >= 0.8`.

---

### Date — `DateContent`

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `date` | `date` | yes | The calendar date, in ISO 8601 (e.g. `2026-07-07`) |
| `time` | `time \| None` | no | The time of day, in ISO 8601 (e.g. `15:40:00`, or `15:40:00+02:00` with a UTC offset) — present only when the source states a time, never an invented midnight |

**Access**: `$var.date`, and `$var.time` when the source stated one.

---

### Time — `TimeContent`

| Attribute | Type | Description |
|-----------|------|-------------|
| `time` | `time` | The time of day, in ISO 8601 (e.g. `15:40:00`, or `15:40:00+02:00` with a UTC offset) |

**Access**: `$var.time` in prompts.

---

### Image — `ImageContent`

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | `str` | yes | Image location: storage URL, HTTP/HTTPS URL, or base64 data URL |
| `filename` | `str \| None` | no | Original filename (auto-populated from URL if not set) |
| `caption` | `str \| None` | no | Image caption or description |
| `mime_type` | `str \| None` | no | MIME type (e.g., `image/jpeg`, `image/png`) |
| `width` | `int \| None` | no | Width in pixels; set together with `height`, or neither is |
| `height` | `int \| None` | no | Height in pixels; set together with `width`, or neither is |
| `public_url` | `str \| None` | no | Public HTTPS URL for display |
| `source_prompt` | `str \| None` | no | The prompt used to generate this image (if AI-generated) |
| `source_negative_prompt` | `str \| None` | no | The negative prompt used to generate this image (if AI-generated) |

**Access**: `$image.filename`, `$image.caption`, `$image.url` in prompts. Use `$image` alone in PipeLLM prompts for vision (image is sent to the LLM as a visual input).

---

### Document — `DocumentContent`

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | `str` | yes | Document location: storage URL, HTTP/HTTPS URL (including web page URLs for extraction), or base64 data URL |
| `public_url` | `str \| None` | no | Public HTTPS URL for display |
| `mime_type` | `str \| None` | no | MIME type (defaults to `application/pdf`) |
| `filename` | `str \| None` | no | Original filename (auto-populated from URL if not set) |
| `title` | `str \| None` | no | Title of the document or source |
| `snippet` | `str \| None` | no | Text snippet or excerpt from the document |

**Access**: `$document.filename`, `$document.url` in prompts. A PipeLLM whose prompt names the document (`@document` or `$document`) sends it to its model, which must read the document's format: a run whose document reaches a model that cannot read it is refused before it starts. Otherwise extract it first with PipeExtract, which gives `Page[]`. For web page URLs, use PipeExtract with the `@default-extract-web-page` model.

**Produced by PipeDocGen**, whose output is the file it printed: a PDF, an Excel workbook, a Word document or a PowerPoint deck, its `filename` carrying the suffix.

---

### Html — `HtmlContent`

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `inner_html` | `str` | yes | The inner HTML content |
| `css_class` | `str \| None` | no | CSS class for a wrapping div; without one, the HTML is not wrapped |

**Access**: `$html.inner_html` in prompts.

---

### TextAndImages — `TextAndImagesContent`

Composite content holding text and associated images. Typically produced by PipeExtract.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `text` | `TextContent \| None` | no | The text portion (has `.text` attribute) |
| `images` | `list[ImageContent] \| None` | no | List of images extracted alongside the text |
| `raw_html` | `str \| None` | no | The fetched page's raw HTML — set only by a web-page `PipeExtract` with `include_raw_html = true` |

**Access**: `$var.text` gets the TextContent, `$var.images` gets the image list. When used with `@var` in a prompt, the text is auto-rendered.

---

### Page — `PageContent`

Represents a single page extracted from a document. Produced by PipeExtract when output is `Page[]`.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `text_and_images` | `TextAndImagesContent` | yes | The text and images extracted from the page |
| `page_view` | `ImageContent \| None` | no | An image of the whole page — set only when the `PipeExtract` that produced the page has `page_views = true`, which works on PDFs only |

**Access**: When `@page` is used in a PipeLLM prompt, the text content is auto-rendered and images are sent as visual inputs. `$page.text_and_images.text.text` drills to the raw text.

---

### JSON — `JSONContent`

| Attribute | Type | Description |
|-----------|------|-------------|
| `json_obj` | `dict[str, Any]` | The JSON object (must be a valid JSON-serializable dict) |

**Access**: `$var.json_obj` in prompts. Fields within the JSON object can be accessed with dot notation if the concept is structured.

---

### SearchResult — `SearchResultContent`

Represents the result of a web search query. Produced by PipeSearch.

| Attribute | Type | Description |
|-----------|------|-------------|
| `answer` | `str` | The synthesized answer text from the search |
| `sources` | `list[DocumentContent]` | List of source citations (each is a DocumentContent with `url`, `title`, `snippet`) |

Each source is a `DocumentContent` with:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | `str` | yes | Source URL |
| `title` | `str \| None` | no | Source title |
| `snippet` | `str \| None` | no | Relevant excerpt from the source |

**Access**: `$result.answer` for the answer text, `$result.sources` for the source list. When used with `@result` in a prompt, the answer and sources are auto-rendered.

**Pattern — fetch source content**: Since sources are `DocumentContent`, you can feed them into PipeExtract with `@default-extract-web-page` to extract the full page into `Page[]` content (pages can contain images and text, most often formatted as markdown). Use `batch_over` with dot notation to iterate over all sources in a PipeSequence:

```toml
# Step 1: Search the web
[pipe.search_topic]
type = "PipeSearch"
description = "Search the web for information"
inputs = { topic = "Text" }
output = "SearchResult"
model = "$standard"
prompt = "What is $topic?"

# Step 2: Extract full content from a single source URL
[pipe.fetch_source]
type = "PipeExtract"
description = "Fetch full page content from a source URL"
inputs = { document = "Document" }
output = "Page[]"
model = "@default-extract-web-page"

# Step 3: Analyze the fetched content
[pipe.analyze_source]
type = "PipeLLM"
description = "Analyze the fetched source content"
inputs = { pages = "Page[]" }
output = "SourceAnalysis"
prompt = """
Analyze the following web page content:

@pages
"""

# Controller: search, then batch-fetch and analyze each source
[pipe.research_topic]
type = "PipeSequence"
description = "Search the web, fetch each source, and analyze"
inputs = { topic = "Text" }
output = "SourceAnalysis[]"
steps = [
    { pipe = "search_topic", result = "search_result" },
    { pipe = "fetch_source", batch_over = "search_result.sources", batch_as = "document", result = "fetched_pages" },
    { pipe = "analyze_source", batch_over = "fetched_pages", batch_as = "pages", result = "analysis" }
]
```

The key insight: `batch_over = "search_result.sources"` is a dotted `batch_over`, which runs as a binding step of `search_result.sources`, the `Document[]` inside the SearchResult, followed by the batch over that list. Each source is a `DocumentContent` with a `url` field, so it can be passed directly to PipeExtract as a web page URL. A dotted `batch_over` belongs on a PipeSequence step: a PipeParallel branch takes a plain one, so a parallel that needs the sources gets them from a binding step before it. Batching does not propagate automatically — each step that should iterate needs its own `batch_over`.

---

### Composite — `CompositeContent`

A named composition of contents with no declared structure: its fields are chosen when the composition is made, which is how a `PipeParallel` whose `output` is `Composite` combines its branches — each branch's `result` name becomes a field holding that branch's content.

**Access**: `$var.<name>` reads the component stored under that name, such as `$analysis.sentiment` for a branch whose `result` is `sentiment`.

---

### ListContent (multiplicity `[]`)

When a concept has `[]` multiplicity (e.g., `Page[]`, `Image[]`), the content is a `ListContent` wrapping a list of items:

| Attribute | Type | Description |
|-----------|------|-------------|
| `items` | `list[StuffContent]` | The list of content items |
| `nb_items` | `int` (property) | Number of items in the list |

ListContent supports iteration (`for item in list_content`), indexing (`list_content[0]`), and `len()`.

---

## Common Patterns

### PipeExtract output chain

PipeExtract produces `Page[]` — a list of pages. Each page contains `text_and_images` (text + images from OCR/extraction) and, when the `PipeExtract` sets `page_views = true` on a PDF, a `page_view` (an image of the whole page). To use extracted content in an LLM prompt:

```toml
# Extract pages from a document
[pipe.extract_pages]
type = "PipeExtract"
inputs = { document = "Document" }
output = "Page[]"

# Extract pages from a web page URL
[pipe.extract_web_content]
type = "PipeExtract"
inputs = { web_page = "Document" }
output = "Page[]"
model = "@default-extract-web-page"

# Analyze the extracted pages — @pages auto-renders all page text
[pipe.analyze]
type = "PipeLLM"
inputs = { pages = "Page[]" }
output = "Analysis"
prompt = """
Analyze this document:

@pages
"""
```

### Handing a pipe one attribute: a binding step

A pipe that needs only the image of each page declares `page_view = "Image"`, never `"page.page_view"`, and the sequence binds the attribute for it:

```toml
[pipe.describe_page_views]
type        = "PipeSequence"
description = "Extract a PDF's pages with their views, then describe each view"
inputs      = { document = "Document" }
output      = "Text[]"
steps = [
    { pipe = "extract_pages_with_views", result = "pages" },
    { from = "pages.page_view", result = "page_views" },
    { pipe = "describe_view", batch_over = "page_views", batch_as = "page_view", result = "descriptions" },
]

[pipe.extract_pages_with_views]
type        = "PipeExtract"
description = "Extract the pages of a PDF, with an image of each page"
inputs      = { document = "Document" }
output      = "Page[]"
page_views  = true

[pipe.describe_view]
type        = "PipeLLM"
description = "Describe how one page looks"
inputs      = { page_view = "Image" }
output      = "Text"
prompt      = "Describe the layout of this page in two sentences: $page_view"
```

`pages.page_view` crosses the `Page[]` list, so it binds an `Image[]`, one image per page that has a view. The last two steps can also be one, `{ pipe = "describe_view", batch_over = "pages.page_view", batch_as = "page_view", result = "descriptions" }`, whose dotted `batch_over` binds the list and batches over it.

### Accessing nested fields in PipeCompose

```toml
[pipe.build_summary.construct]
source_file = { from = "document.filename" }
image_count = { template = "$report.images" }
page_text = { from = "page.text_and_images.text.text" }
```

### Input JSON structure for each type

```json
{
  "my_text": {"concept": "native.Text", "content": {"text": "Hello"}},
  "my_markdown": {"concept": "native.Markdown", "content": {"text": "# Roof\n\n- two cracked tiles"}},
  "my_number": {"concept": "native.Number", "content": {"number": 42}},
  "my_yes_no": {"concept": "native.YesNo", "content": {"yes_no": true}},
  "my_choice": {"concept": "native.Choice", "content": {"choice": "billing"}},
  "my_rating": {"concept": "native.Rating", "content": {"level": 2}},
  "my_date": {"concept": "native.Date", "content": {"date": "2026-07-07"}},
  "my_time": {"concept": "native.Time", "content": {"time": "15:40:00"}},
  "my_image": {"concept": "native.Image", "content": {"url": "/path/to/img.jpg", "mime_type": "image/jpeg"}},
  "my_document": {"concept": "native.Document", "content": {"url": "/path/to/doc.pdf"}},
  "my_json": {"concept": "native.JSON", "content": {"json_obj": {"key": "value"}}},
  "my_search_result": {"concept": "native.SearchResult", "content": {"answer": "The answer text", "sources": [{"url": "https://example.com", "title": "Source 1", "snippet": "Relevant excerpt"}]}}
}
```

A `Choice` or `Rating` input is always an object, never a bare value: a bare `"billing"` would read as a text.
