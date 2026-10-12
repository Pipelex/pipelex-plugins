# MTHDS Language Reference

The reference for the MTHDS language, with copy-pasteable examples: read it before writing or editing a `.mthds` file, and for any syntax question while reading one.

**Write and edit a `.mthds` file with your agent's file tools, never through the shell.** The plugin's hook runs after each write or edit those tools make: it lints the file, formats it in place and validates the method, and returns a failure with the line to fix. A file written or changed by a heredoc, `sed` or a script run in the shell is never checked. The format can reorder the file, so read it again before a change that matches its text.

## 1. Bundle Skeleton

```toml
domain = "snake_case_domain"          # required — namespace for all concepts and pipes
description = "What this bundle does" # optional
main_pipe = "main_pipe_code"          # optional but recommended — entry point

# system_prompt = """                 # optional — default system prompt for all PipeLLM pipes
# You are a careful assistant.
# """

[concept]
# Simple concepts go here (one-liner descriptions)

# [concept.StructuredConcept]
# Structured concepts go in their own table

[pipe.main_pipe_code]
# Each pipe gets its own [pipe.<pipe_code>] table
```

**Naming rules:**
- `domain` — `snake_case`, may have dots (e.g. `legal.contracts`). Reserved first segments: `native`, `mthds`, `pipelex`.
- Concept codes — `PascalCase`, singular, no adjectives (`Invoice`, not `Invoices` or `LargeInvoice`).
- Pipe codes — `snake_case`.
- Input names — plain `snake_case`, never dotted (section 5).
- Names starting with `_bound_` are reserved: never start a step's or a branch's `result`, `batch_as` or `batch_over`, or a `PipeBatch`'s `input_item_name`, with it. Validation refuses them as `invalid_input_name`, and a binding step's `result`, which must be a plain `snake_case` name, as `binding_step_invalid`.

**A bundle split across files shares its header by domain.** Every file that declares the same `domain` is one domain at run time: the `system_prompt` written once in the root is the default of every `PipeLLM` of that domain, whichever file defines it, the root's `description` is the domain's, and a sibling file declares only `domain`. Two files giving different values keep the first loaded, with a warning, so write each once. A file with another `domain` is another domain and inherits nothing.

**Ordering convention:** main pipe (controller) first, then sub-pipes in execution order. Concepts can come before or after pipes.

## 2. Concepts

Two ways to declare a concept. Pick one per concept.

### 2a. Simple Concept (no structure)

Use the flat `[concept]` table, one line per concept:

```toml
[concept]
Topic = "A subject or theme that can be used as the basis for a joke"
Joke = "A humorous one-liner intended to make people laugh"
```

A simple concept has no fields. It's just a named type.

### 2b. Concept that Refines a Native Concept

A refining concept gets a `[concept.<Code>]` table with `refines`:

```toml
[concept.Topic]
description = "A subject or theme that can be used as the basis for a joke"
refines = "Text"
```

Refinement means substitutability: any pipe that accepts `Text` also accepts `Topic`.

`refines` accepts:
- bare code: `"Text"`
- domain-qualified: `"legal.ContractClause"`
- cross-package: `"acme->legal.ContractClause"`

### 2c. Structured Concept (fields)

Define fields in a `[concept.<Code>.structure]` sub-table:

```toml
[concept.Invoice]
description = "A commercial invoice"

[concept.Invoice.structure]
invoice_number = { type = "text", description = "Unique identifier", required = true }
issue_date     = { type = "date", description = "Issue date", required = true }
total_amount   = { type = "number", description = "Total amount due", required = true }
vendor_name    = "The vendor's name"   # shorthand: a REQUIRED text field
notes          = { type = "text", description = "Free-text notes" }
```

**A bare string is a required text field.** `vendor_name = "The vendor's name"` declares exactly `{ type = "text", required = true, description = "The vendor's name" }`. The shorthand carries a description and nothing else, so an optional text field, or a field needing any other key, is written as a table.

**Constraint:** `refines` and `structure` are mutually exclusive — pick one.

### 2d. Field Blueprint Reference

| Attribute | Required | Description |
|-----------|----------|-------------|
| `description` | Yes | Human-readable description of the field. |
| `type` | Conditional | Field type. Required unless `choices` is given. |
| `required` | No | Default `false`. |
| `default_value` | No | Must match `type`. Not allowed on `concept` or `list`. |
| `choices` | No | List of allowed string values (enum-like). |
| `concept_ref` | Conditional | Required when `type = "concept"`. |
| `item_type` | Conditional | Required when `type = "list"`. |
| `item_concept_ref` | Conditional | Required when `item_type = "concept"`. |

**Supported field types** (use exactly these strings):

| Type | Default value example |
|------|----------------------|
| `"text"` | `"hello"` |
| `"integer"` | `42` |
| `"number"` | `2.5` |
| `"boolean"` | `true` |
| `"date"` | (datetime literal) |
| `"concept"` | not allowed |
| `"list"` | not allowed |

> **Outside the authoring subset:** `dict` is a valid field type, which takes `key_type` and `value_type`, so a bundle you read may carry one; never write one. Model the data as a structured concept instead.

### 2e. Concept References in Fields

```toml
[concept.Order.structure]
customer = { type = "concept", concept_ref = "Customer", description = "The buying customer" }
items    = { type = "list", item_type = "concept", item_concept_ref = "LineItem", description = "Order line items" }
tags     = { type = "list", item_type = "text", description = "Free-form tags" }
```

Rules:
- `concept_ref` only when `type = "concept"`.
- `item_concept_ref` only when `item_type = "concept"`.
- Bare codes resolve to the current bundle's domain. Use `domain.ConceptCode` for cross-domain refs.

### 2f. Choices (enum-like)

```toml
[concept.Order.structure]
status   = { choices = ["pending", "processing", "shipped", "delivered"], description = "Order status", required = true }
priority = { type = "text", choices = ["low", "medium", "high"], description = "Priority" }
score    = { type = "number", choices = ["0", "0.5", "1"], description = "Half-point score" }
```

When `choices` is set and `type` is omitted, type defaults to `text`. `choices` is only valid with `text`, `integer`, or `number`. Not valid with `boolean`, `date`, `concept`, or `list`. The field takes only the listed values, and generated Python types it as a `Literal`.

## 3. Native Concepts (always available)

Use bare or qualified (`native.Text`) — bare wins on resolution. Never redeclare a native concept code.

| Code | When to use |
|------|-------------|
| `Text` | A string. |
| `Image` | A binary image (JPEG, PNG, ...). |
| `Document` | A document file or a web page URL. `PipeExtract` reads a PDF, an image or a web page, and nothing else: a Word, Excel or PowerPoint file fails the run at the extraction, so a method over Office documents takes the PDF exported from them. See its section before designing over Office files. |
| `Page` | A single extracted page (`text_and_images`, `page_view` — the latter only when the `PipeExtract` that produced it set `page_views = true` on a PDF). |
| `Html` | HTML content. |
| `TextAndImages` | Mixed text + images. |
| `Number` | A numeric value. |
| `YesNo` | A yes/no answer (`yes_no`). |
| `Date` | A calendar date with optional time (`date`, `time`). |
| `Time` | A time of day with an optional UTC offset (`time`). |
| `JSON` | A JSON value. |
| `SearchResult` | Web search output (`answer`, `sources`). |
| `Anything` | Any type. |
| `Dynamic` | Dynamically typed value. |
| `Composite` | Named components, usually from PipeParallel. |

> File formats like "PDF" or "JPEG" are NOT concepts. Use `Document` and `Image` respectively.

Each native concept has a content class with its own attributes: an `Image` has `url`, `filename` and `caption`, a `Page` has `text_and_images` and `page_view`. [Native Content Types](native-content-types.md) lists them all, for writing `$var.field` in a prompt or `from = "input.field"` in a construct.

## 4. Multiplicity and Presence

Applies to `inputs` values and `output`:

| Syntax | Meaning |
|--------|---------|
| `ConceptName` | Single item. |
| `ConceptName[]` | Variable-length list. |
| `ConceptName[N]` | Exactly N items. |
| `ConceptName?` | Optional single item: it may resolve as a recorded absence. |
| `ConceptName!` | Forced single input: the run fails if it is absent. Inputs only. |

Examples: `Text`, `Text[]`, `Image[3]`, `legal.Clause[]`, `Text?`. Nesting is forbidden — no `Text[][]` — and a presence marker never combines with a count: `Text[]?` is invalid, since a list that received nothing is empty.

## 5. Pipe Skeleton

Every pipe gets a `[pipe.<pipe_code>]` table with these base fields:

```toml
[pipe.my_pipe]
type        = "PipeLLM"         # one of the types below
description = "What it does"
inputs      = { x = "Text", y = "Document[]" }
output      = "Summary"
# ...plus type-specific fields
```

- `type`, `description`, `output` are required for every pipe.
- `inputs` is optional in the schema but almost always present. Keys are plain `snake_case` names, each naming one whole value; values are concept refs with optional multiplicity. Keep on a single line.
- **An input name never holds a dot.** A key such as `"invoice.total" = "Number"` does not declare a field of `invoice`: validation refuses it as `invalid_input_name`. A pipe that needs one field of a value either declares the whole value and reads the field in its template (`invoice = "Invoice"`, read as `$invoice.total`), or declares the field's concept under a plain name (`total_amount = "Number"`) and lets the calling sequence hand the field over with a binding step (section 6, `PipeSequence`).

## 6. Pipe Type Reference

### PipeLLM — generate text or structured output via an LLM

```toml
[pipe.summarize]
type        = "PipeLLM"
description = "Summarize a document"
inputs      = { document = "Document" }
output      = "Summary"
prompt      = """
Summarize the following document:

@document
"""
# system_prompt = "You are a careful summarizer."   # optional, overrides bundle-level
# model = "$writing-factual"                        # optional
```

**Type-specific fields:** `prompt` (almost always required), `system_prompt` (optional), `model` (optional).

**Multi-output:** `output = "Idea[3]"` (exactly 3), `output = "Idea[]"` (variable).

**Vision:** put an `Image` in `inputs` and reference it as `$image` or `@image` in the prompt.

### Model references

Every pipe with a `model` field (`PipeLLM`, `PipeExtract`, `PipeSearch`, `PipeImgGen`, `PipeJudge`) takes a reference of one of four kinds, told apart by its sigil:

| Kind | Sigil | Example | What it names |
|---|---|---|---|
| Preset | `$` | `$writing-factual` | a model with the settings suited to a kind of task; the kind to prefer |
| Alias | `@` | `@default-text-from-pdf` | a stable name the deployment points at one model |
| Waterfall | `~` | `~<name>` | fallback models, tried in order |
| Handle | none | `<handle>` | one model, by its own name |

On a `PipeLLM`, `model` may instead be an inline table of settings, whose `temperature` is required: `model = { model = "@default-general", temperature = 0.2 }`. The table's own `model` is an alias, a waterfall or a handle, never a preset.

**Omit `model` unless the user asks for a model, a setting such as a temperature, or a kind of behaviour such as factual writing**: the default is one the user's account can run, while a reference nobody asked for pins a model the account's gateway may refuse, which validation cannot see, so every run fails.

**A pipe whose input the default model cannot read names the model that can**, whether or not the user asked: a `PipeExtract` over a web page sets `model = "@default-extract-web-page"`, as its section says. Validation cannot see this one either, since it never knows what a `Document` will hold.

**Look a reference up before writing it**, with the `mthds_models` tool. It reads the deck, the presets, aliases and waterfalls the runner serves, by category: `llm` for a `PipeLLM`, `extract` for a `PipeExtract`, `img_gen` for a `PipeImgGen`, `search` for a `PipeSearch` and `judgment` for a `PipeJudge`. It spends no credit.

- **A kind of behaviour**: list the pipe's category and write the preset whose name fits it, saying which one you chose.
- **A model or a reference the user typed**: check it, passing it as `reference` with the pipe's `category`, and act on the first of these that fits the answer. On `resolved`, write it, unless its match in that category has a `null` `resolves_to`: say that it reaches no model the runner can call now, so a run through it fails after validation passes, and write it only if the user still wants it. When `other_kinds` holds the same name under another sigil (`$best-gpt` exists as `@best-gpt`), write that one and say so. When `other_categories` is non-empty, the reference serves another kind of pipe: say so rather than write it on this one. On `not_found`, offer the `suggestions` and write only what the user picks.
- **A model and a setting**: the setting needs an inline table, whose model must answer `resolved`, reach a model and not be a preset. When the model the user named falls short, say so and offer the choice between the setting on an alias the deck lists and the model without the setting, written as the bullet above allows.
- **A setting but no model**: offer the category's presets, which carry settings for a kind of task, or put the setting in an inline table on an alias the deck lists. Never invent a handle.

**Validation never looks inside an inline table**: a reference there that does not resolve, or reaches no model, fails only when a run reaches the pipe, after credit is spent, so write one only once `mthds_models` answers `resolved` for a reference that is not a preset and reaches a model.

**The deck is what the runner can serve, not what the account may use**: a gateway can still refuse a listed model when a run starts, after the method validated. A listed model is no promise, and leaving `model` out stays the safest choice.

**Without `mthds_models`**, on a workshop older than the release that brought it, nothing can be looked up. The same holds for one pipe when the tool refuses its category, on a workshop older than that category. Write a model or a reference the user typed only as a pipe's `model` string, where `mthds_validate` checks it, and never in an inline table, which nothing would check: a setting asked with it is left out, and you say so. When the user named no model, offer a preset this reference names, or ask which model, and never invent a reference.

### PipeSequence — execute steps in order

```toml
[pipe.process_invoice]
type        = "PipeSequence"
description = "Extract then analyze"
inputs      = { document = "Document" }
output      = "InvoiceData"
steps = [
    { pipe = "extract_text", result = "pages" },
    { pipe = "analyze_invoice", result = "invoice_data" },
]
```

**A step is a pipe step or a binding step.** A step carrying `pipe` runs a pipe; a step carrying `from` binds a value already in working memory to a new name (below). A step carries exactly one of the two: one carrying both is refused as `binding_step_invalid`.

**Pipe step:**
- `pipe` — the pipe reference: bare (`extract_text`) for a pipe of this domain, domain-qualified (`finance.extract_text`) for a pipe of another domain (section 8).
- `result` — optional: the working-memory name for this step's output, which is how a later step refers to it.
- `nb_output` or `multiple_output` — optional, never both: how many items the step's output is expected to hold (`nb_output`, an integer), or that it holds several (`multiple_output = true`).
- `batch_over` + `batch_as` — optional inline batch (see below). Must both be present or both absent.

**Steps have NO `inputs` field.** Each step automatically sees the sequence's inputs and all earlier steps' `result` values, and its pipe receives them by name: an input `x` reads the value stored as `x`. When the value is stored under another name, or the pipe needs one field of it, a binding step hands it over.

**Binding step** — hand a pipe one field of a value, or a value under the name its input declares:

```toml
[concept.Invoice]
description = "An invoice received from a supplier"

[concept.Invoice.structure]
supplier_name = { type = "text", description = "The supplier's name", required = true }
total         = { type = "number", description = "The total amount due", required = true }

[pipe.review_invoice]
type        = "PipeSequence"
description = "Say whether an invoice needs a manager's approval"
inputs      = { invoice = "Invoice" }
output      = "Text"
steps = [
    { from = "invoice.total", result = "total_amount" },
    { pipe = "assess_amount", result = "assessment" },
]

[pipe.assess_amount]
type        = "PipeLLM"
description = "Say whether an amount needs a manager's approval"
inputs      = { total_amount = "Number" }
output      = "Text"
prompt      = "Does an invoice total of $total_amount need a manager's approval? Answer in one sentence."
```

The first step binds the invoice's `total` under the plain name `total_amount`, as a `Number`, and `assess_amount` declares exactly that input, so it receives the amount and nothing else of the invoice.

- `from` — a path: its root names a value in working memory, a sequence input or an earlier step's `result`, and each following segment names a field of the value reached so far, separated by single dots. Segments are identifiers: no subscript (`lines[0]`), expression or whitespace, since anything computed is a pipe's job.
- `result` — required, a plain `snake_case` name.
- Nothing else: a binding step carries no `pipe`, `batch_over`, `batch_as`, `nb_output` or `multiple_output`. Any of them, a missing `result`, or a `from` outside the path grammar is refused as `binding_step_invalid`.
- **A bare name renames.** `{ from = "departure_board", result = "board" }` binds a copy of the whole value, with its concept and multiplicity, under the name the next pipe's input declares: this is how a sequence adapts a name between two pipes.
- **The result's concept comes from the declared structures**, before any run. A `concept` field gives its `concept_ref`; a `text` field or one declared by `choices` alone gives `Text`; `number` and `integer` give `Number`, with or without `choices`; `boolean` gives `YesNo`; `date` gives `Date`; a `list` field gives a list of its items' concept. A native concept is walked through its attributes ([Native Content Types](native-content-types.md)), so `page.page_view` is an `Image`. The step reading the result declares that concept and multiplicity, or validation refuses it.
- **Crossing a list maps and flattens.** When the path crosses a list, the rest of the path applies to every item and the result is one flat list: `pages.page_view` over `Page[]` gives `Image[]`, `order.lines.amount` gives `Number[]`. An item that holds nothing contributes nothing.
- **A path the structures cannot walk is refused** as `binding_path_unresolved`: a segment naming no field, a segment after a plain field (`invoice.total.number`), and a segment into a concept with no structure, or into `Text`, `Markdown`, `Number`, `Time` or `JSON`, whose value is their one field. Bind such a value whole (`from = "note"`).
- **The value is a copy**, taken when the step runs and never an alias of the root, with every field of what the path reaches.
- **Only in a `PipeSequence`'s `steps`.** A `PipeParallel` branch is always a pipe step: a binding step in `branches` is refused as `binding_step_invalid`, so bind the value in a sequence step before the parallel.

**The absence rule.** A structure field that is not `required` and has no `default_value` may be missing from the data, and fields default to `required = false`. A binding whose path walks such a field, or whose root may be absent, binds a **maybe-absent** value: when the field holds nothing, the step records an absence, not an error. The step reading it must handle that, or the author must:

- declare the input optional and guard its read, `courier_note = "Text?"` read as `@?courier_note`, and the step runs either way; or
- keep a plain input, which skips the step when the value is missing, so the step's output may be absent in turn, and a sequence whose output that step produces declares its output optional (`output = "Text?"`).

A maybe-absent value reaching a sequence output without `?` is refused as `optional_not_handled`. A path through required fields only, from a root that is always there, binds a value that is always there, and a list result is never absent: it is shorter, or empty.

```toml
[concept.Delivery]
description = "A parcel delivery"

[concept.Delivery.structure]
address = { type = "text", description = "The delivery address", required = true }
note    = { type = "text", description = "A note the sender left for the courier" }

[pipe.brief_courier]
type        = "PipeSequence"
description = "Write the courier's briefing for a delivery"
inputs      = { delivery = "Delivery" }
output      = "Text"
steps = [
    { from = "delivery.address", result = "address" },
    { from = "delivery.note", result = "courier_note" },
    { pipe = "write_briefing", result = "briefing" },
]

[pipe.write_briefing]
type        = "PipeLLM"
description = "Write a short briefing for the courier"
inputs      = { address = "Text", courier_note = "Text?" }
output      = "Text"
prompt      = """
Write a one-paragraph briefing for a courier delivering to $address.

@?courier_note
"""
```

`note` is not required, so `courier_note` may be absent, and `write_briefing` takes it as `Text?` and guards it with `@?`. `address` is required, so its binding is always there.

**Inline batch step:**

```toml
steps = [
    { pipe = "process_item", batch_over = "items", batch_as = "item", result = "processed" },
]
```

`batch_as` (singular) MUST differ from `batch_over` (plural). `batch_over` names a list in working memory, or is a dotted path to a list held in a field (`"catalog.pages"`, `"search_result.sources"`). **A dotted `batch_over` runs as a binding step of that path followed by the batch** over the bound list, so the path follows every rule of a binding step above, and it must reach a list, through a list root or a list field along or at the end of the path: one deriving a single value is refused. Only a sequence step may carry one: on a `PipeParallel` branch a dotted `batch_over` is refused as `binding_step_invalid`, so bind the list in a sequence step before the parallel and give the branch a plain `batch_over`.

### PipeBatch — map one pipe over each item in a list

```toml
[pipe.process_all_documents]
type             = "PipeBatch"
description      = "Process each document in the list"
inputs           = { documents = "Document[]", context = "Context" }
output           = "Summary[]"
branch_pipe_code = "summarize_document"
input_list_name  = "documents"
input_item_name  = "document"
```

**Required:** `branch_pipe_code` (the pipe applied to each item, a pipe reference like a step's `pipe`), `input_list_name` (the input holding the list, declared with `[]`), `input_item_name` (the name each item is passed to the branch pipe under).

**Constraints:**
- `input_list_name` is a plain input name, never a path into a field: `"catalog.pages"` is refused as `invalid_input_name`. To map a pipe over a list held in a field, declare the list itself (`pages = "CatalogPage[]"`, `input_list_name = "pages"`) and have the calling sequence bind the field to it (`{ from = "catalog.pages", result = "pages" }`), or run the branch pipe in a sequence step with a dotted `batch_over` instead of a `PipeBatch`.
- `input_item_name` MUST differ from `input_list_name`: name the list in the plural and the item in the singular (`documents` and `document`; for a compound name, `report_data` and `single_report_data`).
- `input_item_name` MUST NOT match any other key in `inputs`.
- For non-batched inputs (passed through to the branch), use singular types (e.g. `context = "Context"`, NOT `"Context[]"`): the branch pipe receives one item at a time, and declares singular inputs.

Items run in parallel, and the output list keeps the input order.

### PipeParallel — run branches concurrently

```toml
[pipe.analyze_all_aspects]
type            = "PipeParallel"
description     = "Run sentiment and topics analyses in parallel"
inputs          = { document = "Document" }
output          = "Composite"
add_each_output = true
branches = [
    { pipe = "analyze_sentiment", result = "sentiment" },
    { pipe = "extract_topics", result = "topics" },
]
```

**Required:** `branches`, each a sub-pipe written like a sequence's pipe step: never a binding step, and with a plain `batch_over` if it batches, never a dotted one. Both are refused as `binding_step_invalid`, because a branch runs alongside the others and cannot bind: bind what the branches need in a sequence step before the parallel. The declared `output` is always the combined result and MUST be `Composite` or a structured concept whose field names match the branches' `result` names. Do not use `[]` or `[N]` on `output`. There is no `combined_output` field: the declared `output` is the combination.

Each branch runs on its own deep copy of working memory. `add_each_output = true` is optional and only exposes branch results individually in working memory.

### PipeCondition — route to a pipe based on an expression

```toml
[pipe.route_by_category]
type                       = "PipeCondition"
description                = "Route based on category"
inputs                     = { input_data = "CategorizedInput" }
output                     = "Text"
expression_template        = "{{ input_data.category }}"
default_outcome            = "process_medium"

[pipe.route_by_category.outcomes]
small  = "process_small"
medium = "process_medium"
large  = "process_large"
```

**Required:** `expression_template` (Jinja2) or `expression` (bare value) — exactly one. Plus `outcomes` and `default_outcome`.

`default_outcome`, like each value of `outcomes`, accepts a pipe reference OR the special values `"fail"` (abort) or `"continue"` (pass-through, no sub-pipe).

**`"continue"` leaves the output absent**, so a condition that can reach it, as its `default_outcome` or as an outcome, MUST declare its output optional with `?` (`output = "Text?"`). Validation rejects it otherwise.

> **Always set `default_outcome`**, even when outcomes appear exhaustive (e.g. yes/no). Validation rejects pipes without one.

### PipeCompose — template or construct output

**Template mode** (produces text):

```toml
[pipe.compose_email]
type        = "PipeCompose"
description = "Compose an email body"
inputs      = { customer = "Customer", deal = "Deal" }
output      = "Text"
template = """
Hi $customer.name,

Following up on $deal.product_name:

@deal.details
"""
```

**Template table form:** `template` may be a table instead of a string, carrying `template` and `category`, and optionally `templating_style` and `extra_context`. That table is where a category is set, never a field of the pipe:

```toml
[pipe.render_report]
type        = "PipeCompose"
description = "Render the report as Markdown"
inputs      = { report = "Report" }
output      = "Text"

[pipe.render_report.template]
category = "markdown"
template = """
# $report.title

@report.body
"""
```

| Category | Use when | Key filters |
|----------|----------|-------------|
| `basic` | General-purpose text; a string `template` is `basic` | `format`, `tag` |
| `expression` | Simple expressions | *(none)* |
| `html` | Web content (autoescaped) | `format`, `tag`, `escape_script_tag` |
| `markdown` | Markdown output | `format`, `tag`, `escape_script_tag` |
| `mermaid` | Mermaid diagrams | *(none)* |
| `llm_prompt` | LLM prompt composition | `format`, `tag`, `with_images` |
| `img_gen_prompt` | Image generation prompts | `format`, `tag`, `with_images` |

**Construct mode** (assembles a structured concept field-by-field):

```toml
[pipe.build_invoice]
type        = "PipeCompose"
description = "Assemble an Invoice from order data"
inputs      = { order = "Order", customer = "Customer" }
output      = "Invoice"

[pipe.build_invoice.construct]
invoice_number = { template = "INV-$order.id" }
customer_name  = { from = "customer.name" }
total          = { from = "order.total" }
status         = "pending"     # literal
tags           = ["urgent"]    # literal list
```

Each construct field is one of:
- `{ from = "input.path" }` — variable reference: a whole input variable or a dotted path into it, read inside the pipe through an input it declares (this is not a sequence's binding step).
- `{ template = "..." }` — Jinja2 template string with shorthands.
- A literal value (string, number, boolean, list), assigned directly and never wrapped in `{ value = ... }`.

**Output** in construct mode MUST be a single concept (no `[]` or `[N]`).

**Copying whole inputs into native fields:** `from` is not limited to dotted paths — it can name a whole input variable. When that input is a native stuff (`Text`, `Number`, `YesNo`, `Date`, or a list of them) and the target field is native-typed (`text`, `number`, `boolean`, `date`, or a `list` of them), the composer converts the value automatically — for required and optional fields alike:

```toml
[concept.ScreeningReport]
description = "The final screening report"

[concept.ScreeningReport.structure]
match_score         = { type = "number", description = "The match score", required = true }
rejection_email     = { type = "text", description = "The rejection email, if any" }
interview_questions = { type = "list", item_type = "text", description = "Questions to ask, if any" }

[pipe.assemble_report]
type        = "PipeCompose"
description = "Assemble the screening report from previously generated pieces"
inputs      = { score = "Number", email = "Text", questions = "Text[]" }
output      = "ScreeningReport"

[pipe.assemble_report.construct]
match_score         = { from = "score" }      # whole Number stuff → required number field
rejection_email     = { from = "email" }      # whole Text stuff → optional text field
interview_questions = { from = "questions" }  # whole Text[] stuff → optional list of text
```

When the target field expects a content object (a concept-typed field), the object is kept as-is — the conversion fires only when the field expects the native type.

### PipeExtract — extract pages from a Document or Image

**It reads a PDF, an image or a web page, and nothing else.** A Word, Excel or PowerPoint file passes validation and preparation, then fails the run at this step with an extraction error naming the formats it accepts. When the user's files are Office documents, say so at the contract and design for the PDF they export from them (Word's *Save as PDF*, or `soffice --headless --convert-to pdf` where LibreOffice is installed): the input stays a `Document`, its description says PDF, and the test inputs are PDFs too.

```toml
[pipe.extract_document]
type        = "PipeExtract"
description = "Extract content from a document"
inputs      = { document = "Document" }
output      = "Page[]"
# model               = "@default-text-from-pdf"  # optional
# page_views          = true                      # optional, PDFs only: fills each Page's page_view
# page_views_dpi      = 150                       # optional, with page_views
# max_page_images     = 0                         # optional: 0 keeps no embedded images
# page_image_captions = true                      # optional, caption-capable models only
# render_js           = true                      # optional, web pages only
# include_raw_html    = true                      # optional, web pages only
```

**Constraints:**
- Exactly one input. Input concept SHOULD be `Document` (or refine it) or `Image`.
- Output MUST be `"Page[]"`.

**Optional fields:**

| Field | What it does |
|-------|--------------|
| `model` | Which extraction model to use, e.g. `"@default-text-from-pdf"` or `"@default-extract-web-page"`. |
| `page_views` | PDFs only: renders every page as an image and puts it in that `Page`'s `page_view`. **Off by default, and `page_view` stays unset without it** — a method that shows a page, or sends one to a vision model, must set `page_views = true`. On a web page, the run fails when it reaches the render, after the extraction has been paid for. |
| `page_views_dpi` | Resolution of those renders; omitted, the runtime's `default_page_views_dpi` applies (72 unless configured otherwise). Only has an effect alongside `page_views = true`. |
| `max_page_images` | How many of the images embedded in the pages the extraction keeps: `0` keeps none, and a positive `N` caps them — per page on some models, across the whole document on others. Omitted, the model preset's own limit applies; the default models have none, so every image is kept. |
| `page_image_captions` | Requires a model that captions the images it pulls out: on any other, the run fails with a capability error. It does not switch captioning on — a caption-capable model returns its captions whether or not this is set — so it only guards a method that depends on captions against the wrong model. |
| `render_js` | Web pages only: runs the page's JavaScript before reading it. The web-page model (`@default-extract-web-page`) honours it; other models ignore it or refuse the run. |
| `include_raw_html` | Web pages only: also keeps the fetched page's raw HTML, readable as `$page.text_and_images.raw_html`. The web-page model honours it; other models ignore it or refuse the run. |

**With an `Image` input**, `page_views` and `page_image_captions` cannot be turned on, and `page_views_dpi` and `max_page_images` cannot be set at all: they describe a document's pages, and validation rejects them on an image.

**A web page is read only with `model = "@default-extract-web-page"`.** Its input is still a `Document`, the page's URL in the `url` field, but the default extraction model reads PDFs and images: given a web page, it fails the run at this step with `Could not identify file type of given bytes`, after validation has passed. A URL to a PDF is a PDF, which the default reads.

### PipeSearch — search the web

```toml
[pipe.search_topic]
type        = "PipeSearch"
description = "Search the web for information on a topic"
inputs      = { topic = "Text" }
output      = "SearchResult"
prompt      = "What is $topic?"
# model           = "$standard"                # optional: "$standard" or "$deep"
# from_date       = "2026-01-01"               # optional, YYYY-MM-DD
# to_date         = "2026-06-30"               # optional, YYYY-MM-DD
# include_domains = ["reuters.com", "bbc.com"] # optional: only these domains
# exclude_domains = ["example.com"]            # optional: never these domains
# max_results     = 5                          # optional: omitted, the provider's default
```

**Required:** `prompt`, a query template that takes `$variable` shorthands. **Output** MUST be `SearchResult` or a concept that refines `SearchResult`: an `answer` text and a `sources` list with title, URL, and snippet for each source.

### PipeImgGen — generate images

```toml
[pipe.generate_image]
type         = "PipeImgGen"
description  = "Generate an image from a prompt"
inputs       = { img_prompt = "Text" }
output       = "Image"
prompt       = "$img_prompt"
# model       = "$gen-image"           # optional, e.g. "$gen-image" or "@default-premium"
# aspect_ratio = "landscape_16_9"      # optional, model-dependent (below)
```

**Required:** `prompt` (even if it's just a passthrough like `"$img_prompt"`). Declared `inputs` are injected into the `prompt` template.

**Image-to-image:** declare an `Image` (or `Image[]`) input and reference it in the `prompt`:

```toml
inputs = { ref = "Image", instruction = "Text" }
prompt = "Apply this change to $ref: $instruction"
```

Each referenced image is injected as an `[Image N]` token (reference image), bounded by the model's `max_prompt_images`.

**Aspect ratio values** (enum names, not ratios): `square`, `landscape_4_3`, `landscape_3_2`, `landscape_16_9`, `landscape_21_9`, `portrait_3_4`, `portrait_2_3`, `portrait_9_16`, `portrait_9_21`.

Aspect-ratio support is model-dependent, and only `square` works on every model. The newest models cover the full range: `gpt-image-2` supports all of them, `nano-banana-2` nearly all. The older `gpt-image-1` and `gpt-image-1.5` accept only `square`, `landscape_3_2` and `portrait_2_3`. For a specific shape such as `landscape_16_9` or `portrait_9_16`, choose a model that supports it rather than assuming the default does.

### PipeFunc — call a registered Python function

```toml
[pipe.capitalize_text]
type          = "PipeFunc"
description   = "Uppercase the input text"
inputs        = { text = "Text" }
output        = "Text"
function_name = "capitalize"
```

Only use this when the user has a registered function. Otherwise prefer PipeCompose or PipeLLM.

**`function_name` is a registry key, not an import path.** It names an entry in the runtime's flat, process-wide function registry — by default the decorated function's own name, and otherwise whatever string `@pipe_func(name=…)` was given — and resolution is a lookup with no import. So nothing in a bundle says which module defines a registered function, a dotted name is just a key that happens to contain dots, and on the hosted plane the stored `.py` files are flat importable module names beside each other. Name the function, not a path to it.

**`PipeFunc` is experimental on the hosted plane.** Its Python runs in a sandbox with no network access, and the feature is still in development, so a method that validates can still fail when it runs. The function must already be registered in the runtime that executes the method: a `function_name` naming something the plane cannot import fails at run time, not at validation.

### PipeSignature — a contract-only header (forward declaration)

A `PipeSignature` declares a pipe by its **contract only** — `description`, `inputs`, `output`, and an optional `signature_for` hint — with **no implementation**. It is the C-style *forward declaration* that top-down design relies on: commit to what a pipe takes and returns before writing how it works.

```toml
[pipe.summarize_doc]
description   = "Produce a summary of a document (contract only)."
inputs        = { doc = "Document" }
output        = "Summary"
signature_for = "PipeLLM"   # optional hint: the intended implementation type
```

**Rules:**
- **No `type` field** — a pipe entry *is* a signature because it omits `type`. Writing `type = "PipeSignature"` is invalid and gets rejected at lint time; never write it.
- **No implementation fields** — no `prompt`, `steps`, `branch_pipe_code`, `outcomes`, etc. The signature is purely the contract.
- `inputs` and `output` are declared **explicitly**, exactly as any pipe — pipes never infer `inputs` from prompt sigils. Multiplicity (`[]`, `[N]`) works as usual.
- `signature_for` records the *intended* next-level type. It is a **hint, not a binding contract** — the implementation may override it. It may **not** be `"PipeSignature"`. Omit it if unsure.

**`signature_for` → operator or controller** (the next-level decision when you expand a signature):
- **Operator (leaf)** — a single step: `PipeLLM`, `PipeExtract`, `PipeSearch`, `PipeImgGen`, `PipeCompose`, `PipeFunc`. Replace the signature with the concrete operator; that branch is done.
- **Controller (composite)** — multiple steps, iteration, branching, or parallelism: `PipeSequence`, `PipeBatch`, `PipeParallel`, `PipeCondition`. Replace the signature with the controller, wire its sub-pipes, and forward-declare each not-yet-built sub-pipe as its own `PipeSignature`.

**Header ↔ definition contract.** A concrete pipe satisfies a signature of the same code when their `inputs`/`output` match **by concept identity** — bare↔qualified (`Brief` ≡ `thisdomain.Brief`) and native (`Text` ≡ `native.Text`) spellings are equivalent, multiplicity compared structurally. Spelling need not be byte-identical, but both sides must declare `inputs`/`output` explicitly. A definition whose contract differs from its header is a hard error.

**Validation and the runnable gate:** validation (the `mthds_validate` MCP tool) always accepts reachable signatures — each mints a mock of its declared output — so a design scaffold with pending signatures still passes. A produced verdict reports `pending_signatures` — the library-wide list of pipes still declared as contract-only signatures (empty when the method is complete). It is the design's todo list. The method is **runnable** only when the verdict reports `is_runnable: true` with an empty `pending_signatures`. Live execution of a signature always fails (`PipeSignatureNotExecutableError`), so drain the backlog before running.

## 7. Prompt Template Shorthands

Applies to: `prompt` (PipeLLM, PipeImgGen, PipeSearch), `system_prompt` (PipeLLM), `template` (PipeCompose), and `{ template = "..." }` in construct fields.

| Shorthand | Expands to | Use |
|-----------|-----------|-----|
| `$variable` | `{{ variable\|format() }}` | Inline substitution. |
| `@variable` | `{{ variable\|tag("variable") }}` | Block insertion (put on its own line). |
| `@?variable` | `{% if variable %}{{ variable\|tag("variable") }}{% endif %}` | Conditional block. |

- Dotted paths work: `$user.name`, `@doc.summary`.
- Dollar amounts (`$100`) and version-like strings (`@2.0`) are NOT matched — must start with a letter or underscore.
- Trailing dots are treated as punctuation: `$amount.` → `{{ amount|format() }}.`
- Raw Jinja2 (`{{ ... }}`, `{% ... %}`) always works alongside the shorthands.

**Validation:** every variable in a prompt MUST be a declared input (root name), and every declared input MUST be referenced in the prompt at least once.

**Structured inputs auto-expand:** `@theme` formats ALL fields of `theme`. Don't manually enumerate fields unless you need a specific one inline (`$theme.palette.primary`).

## 8. Cross-Domain References

| Item | Same domain | Another domain |
|------|-------------|----------------|
| Concept | `"Invoice"` | `"finance.Invoice"` |
| Pipe (in `steps`, `branches`, `outcomes`, `default_outcome`, `branch_pipe_code`) | `"extract_text"` | `"finance.extract_text"` |

Both forms are valid wherever a concept or a pipe is referenced: a bare reference resolves within the bundle's own domain, and a domain-qualified one within the named domain. A third form, `alias->domain.code`, reaches a domain of a dependency. A pipe's definition key, `[pipe.<pipe_code>]`, is always bare.

When the bundle stays in one domain (the common case), use bare names everywhere.

## 9. Formatting Rules

- Keep `inputs = { ... }` on a single line.
- Use double-quoted strings; triple-quoted `"""..."""` for multi-line prompts.
- Put the main pipe (controller) before its sub-pipes for top-down readability.
- Don't redeclare a native concept code.

## 10. Common Mistakes to Avoid

- ❌ `inputs` field on a `PipeSequence` step — steps see the sequence's inputs automatically.
- ❌ A dotted input name (`"invoice.total" = "Number"`) — refused as `invalid_input_name`; declare the whole value and read `$invoice.total`, or bind the field in the calling sequence under a plain name.
- ❌ A binding step in a `PipeParallel`'s `branches`, or a dotted `batch_over` on a branch — bind in a sequence step before the parallel.
- ❌ A binding step carrying `pipe`, `batch_over`, `batch_as`, `nb_output` or `multiple_output`, or lacking `result`.
- ❌ A binding over a field that is not `required`, read through a plain input by the step producing the sequence's output, with no `?` on that output — refused as `optional_not_handled`; take the input as `X?` and guard it, or declare the output optional.
- ❌ A `result`, `batch_as`, `batch_over` or `input_item_name` starting with `_bound_` — the prefix is reserved.
- ❌ Adjectives or circumstances in concept names (`LongArticle`, `CounterArgument`).
- ❌ Plural concept names (`Invoices` — use `Invoice` plus multiplicity).
- ❌ An optional field written as a bare string — the shorthand is always a required text field.
- ❌ Omitting `prompt` on `PipeImgGen` because "the input is already a prompt" — `prompt = "$img_prompt"` is still required.
- ❌ Omitting `default_outcome` on `PipeCondition` because outcomes "look exhaustive" — still required.
- ❌ A `PipeCondition` that can reach `"continue"` with an output lacking `?`.
- ❌ `PipeParallel` output that is not `Composite` or a structured concept matching branch `result` names.
- ❌ A `combined_output` field on `PipeParallel` — there is none; the declared `output` is the combination.
- ❌ A `category` field on a `PipeCompose` — it belongs in the `template` table.
- ❌ Wrapping a construct literal in `{ value = ... }` — assign it directly.
- ❌ Writing a `dict` field — outside the authoring subset.
- ❌ Writing a `PipeStructure` — outside the authoring subset; use `PipeLLM` with a structured output concept instead.
- ❌ `default_value` on `concept`- or `list`-typed fields — not allowed.
- ❌ Referencing a variable in a prompt without declaring it in `inputs` — validation will fail.
- ❌ Declaring an `input` that no prompt references — also rejected.
- ❌ Adding implementation fields (`prompt`, `steps`, …) to a `PipeSignature` — it is contract-only.
- ❌ Writing `type = "PipeSignature"` — a signature header has NO `type` field at all; omitting `type` is what makes it a signature.
- ❌ `signature_for = "PipeSignature"` — must name a real implementation type, or omit it entirely.
- ❌ A definition whose `inputs`/`output` contract differs from its header's — they must match by concept identity.

## 11. End-to-End Example

```toml
domain      = "joke_generation"
description = "Generating one-liner jokes from topics"
main_pipe   = "generate_jokes_from_topics"

[concept.Topic]
description = "A subject or theme that can be used as the basis for a joke"
refines     = "Text"

[concept.Joke]
description = "A humorous one-liner intended to make people laugh"
refines     = "Text"

[pipe.generate_jokes_from_topics]
type        = "PipeSequence"
description = "Generate 3 joke topics and create a joke for each"
output      = "Joke[]"
steps = [
    { pipe = "generate_topics", result = "topics" },
    { pipe = "batch_generate_jokes", result = "jokes" },
]

[pipe.generate_topics]
type        = "PipeLLM"
description = "Generate 3 distinct topics suitable for jokes"
output      = "Topic[3]"
prompt      = "Generate 3 distinct and varied topics for crafting one-liner jokes."

[pipe.batch_generate_jokes]
type             = "PipeBatch"
description      = "Generate a joke for each topic"
inputs           = { topics = "Topic[]" }
output           = "Joke[]"
branch_pipe_code = "generate_joke"
input_list_name  = "topics"
input_item_name  = "topic"

[pipe.generate_joke]
type        = "PipeLLM"
description = "Write a clever one-liner joke about the given topic"
inputs      = { topic = "Topic" }
output      = "Joke"
prompt      = "Write a clever one-liner joke about $topic. Be concise and witty."
```
