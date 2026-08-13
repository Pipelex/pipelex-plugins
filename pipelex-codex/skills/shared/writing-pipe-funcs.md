# Writing PipeFuncs

`PipeFunc` is the escape hatch: one pipe step whose body is Python you wrote, instead of a model call. Use it for deterministic work a model should not be guessing at — arithmetic, aggregation, table reshaping, date math, sorting and ranking, spreadsheet reading, deterministic formatting.

A PipeFunc method is **two artifacts that must agree**: the `[pipe.…]` entry in the `.mthds`, and a `.py` file shipped alongside it in the same bundle. The `.mthds` names a function; the Python defines it. Neither half is useful alone.

## 1. The two halves

```toml
# main.mthds
[pipe.rank_products]
type          = "PipeFunc"
description   = "Rank products by margin and keep the top ten"
inputs        = { rows = "ProductRow[]" }
output        = "ProductRanking"
function_name = "rank_products"
```

```python
# custom_pipe_funcs.py  — shipped in the same bundle
from pipelex.core.memory.working_memory import WorkingMemory
from pipelex.system.registries.func_registry import pipe_func

from structures import ProductRanking, ProductRow


@pipe_func()
async def rank_products(working_memory: WorkingMemory) -> ProductRanking:
    """Rank products by margin, highest first."""
    rows = working_memory.get_stuff_as_list("rows", item_type=ProductRow)
    ranked = sorted(rows.items, key=lambda row: row.margin, reverse=True)
    return ProductRanking(entries=ranked[:10])
```

`function_name` is the **registration name, not an import path**. It is a flat, unqualified name — never `my_package.module.rank_products`. Every `.py` in the bundle registers into one namespace, so two functions registered under the same name is a hard error naming both origins. Prefix with the domain when a name could collide (`@pipe_func(name="shop_summarize")`).

## 2. The function contract

Every one of these is required for the function to be eligible; miss one and it is silently not registered, and the pipe fails at run time with the function "not found".

- Decorated with `@pipe_func()` — the bare decorator, called. `@pipe_func` without parentheses does not register.
- Exactly one parameter, named `working_memory`, typed exactly `WorkingMemory` (not a subclass, not a differently-named parameter, not two parameters). The runtime passes it by keyword, so the name is load-bearing.
- A return type annotation that is a `StuffContent` subclass, or `ListContent[...]`. An unannotated return makes the function ineligible.
- `async def` or plain `def` both work — a sync function is run on a worker thread, so it does not block the pipeline.

Keep module-level code to a minimum. Registration **imports** the file holding the function, so anything at module scope executes before your pipe runs. (Discovery reads each file's syntax tree first and only imports the ones that declare a pipe func or a structure class, so a pure helper module is imported by its importer rather than by the scan — but the file your pipe func lives in is always imported.)

## 3. Structures — the return type must be the pipe's output concept

This is the rule that trips people up. The runtime checks the function's **declared return type** against the structure class of the pipe's `output` concept. A function returning a plain dict, a dataclass, or a hand-written Pydantic model fails, however correct the data is.

You do not hand-write those classes — **codegen** projects them from your concepts into a `structures.py` you ship in the bundle. Import from it by concept code:

```python
from structures import TicketStats
```

Class names are the concept codes verbatim: concept `TicketStats` becomes `class TicketStats`. Only a code that collides across two domains gets a domain-qualified spelling.

### Generating it

Two front doors onto one engine — same bytes, same `crate_fingerprint`, same `content_hash`:

```bash
pipelex codegen types --target python-structures -o . ./my_method/
```

```jsonc
POST /v1/codegen
{ "kind": "types", "target": "python-structures",
  "files": [{ "content": "<main.mthds contents>", "source": "main.mthds" }] }
```

The response carries `artifacts[]` (`structures.py`) plus a `codegen.lock`; write both into the bundle. `pipelex build structures` is a thin alias of the same command, so it is the same output under an older name.

The API route takes `.mthds` only and never imports your Python, so it generates for a bundle that already declares PipeFuncs. The local CLI does not: in `direct` mode it validates each `function_name` against the registry at load, which needs your `.py` imported, which needs the `structures` module you are trying to create. Generate through the API, or generate before the PipeFunc pipes exist.

### Living with it

The generated classes are ordinary Pydantic models — construct them by keyword, read fields by attribute.

**Never hand-edit `structures.py`.** It is stamped and regenerated; edits are overwritten, and `pipelex codegen check` reports the drift. To add validation or computed properties, subclass in a sibling module — subclasses survive regeneration.

Regenerate whenever a concept's shape changes, and re-run the check so the module and the method cannot silently disagree.

## 4. Reading inputs from working memory

The pipe's declared `inputs` are what the function may read, by the names declared there.

| Call | Returns |
|---|---|
| `get_stuff_as_str(name)` | `str` |
| `get_stuff_as_text(name)` | `TextContent` |
| `get_stuff_as_number(name)` | `NumberContent` |
| `get_stuff_as_yes_no(name)` | `YesNoContent` |
| `get_stuff_as_date(name)` | `DateContent` |
| `get_stuff_as_image(name)` | `ImageContent` |
| `get_stuff_as_document(name)` | `DocumentContent` |
| `get_stuff_as_text_and_image(name)` | `TextAndImagesContent` |
| `get_stuff_as_html(name)` / `get_stuff_as_mermaid(name)` | `HtmlContent` / `MermaidContent` |
| `get_stuff_as(name, content_type=Cls)` | one instance of `Cls` |
| `get_stuff_as_list(name, item_type=Cls)` | `ListContent[Cls]` — iterate `.items` |

`content_type` and `item_type` are keyword-only. For a structured concept, pass the generated class. A multiplicity input (`Concept[]`) is a `ListContent`, so read it with `get_stuff_as_list`.

Returning a list means returning `ListContent`:

```python
from pipelex.core.stuffs.list_content import ListContent

@pipe_func()
async def split_rows(working_memory: WorkingMemory) -> ListContent[ProductRow]:
    ...
    return ListContent(items=rows)
```

## 5. Only these libraries exist

The execution sandbox has **Python's standard library, `pipelex`, `pandas`, and `openpyxl`. Nothing else.** There is no package install at run time, and adding a `requirements.txt` to the bundle changes nothing — it is carried but never acted on.

An import of anything else fails when the module is imported for registration, which takes down the whole pipe, not just that one function.

**Your local virtualenv is not the contract.** Locally, a PipeFunc imports whatever you happen to have installed, so a method that runs clean on your machine can fail the moment it runs on the API. Write against the sandbox's set from the start, and treat a local run as a logic check rather than a portability check.

`pandas` and `openpyxl` cover the overwhelming majority of what PipeFuncs are actually for. If you reach for something outside the set, the fix is to express the work in those terms — not to bring the library.

## 6. No network

The sandbox runs with **egress blocked**. No HTTP calls, no API clients, no SDK that phones home, no fetching a file by URL, no database connection, no `pip install`. A PipeFunc is a pure function of its working-memory inputs.

If a step genuinely needs the outside world, it is not a PipeFunc: get the data in as a method input (see the inputs preparation flow), or use the operator built for it — `PipeSearch` for the web, `PipeExtract` for documents.

## 7. How to split the Python across files

Judgment, not ceremony:

- **A few short functions → one file.** `custom_pipe_funcs.py` next to the `.mthds`. Splitting three ten-line functions into three files buys nothing and costs the reader the overview.
- **Many functions → split by purpose, not by count.** One file per coherent job, named for that job (`compute_alerts.py`, `compute_segments.py`, `compute_comparisons.py`), each holding the pipe func plus the helpers only it uses. Grouping "all the small ones together" recreates the same undifferentiated file you were splitting.
- **Shared helpers get their own module**, imported by the files that need it (`_inputs.py`, `_shared_math.py`). A leading underscore reads as "not a pipe func, no registration here".
- **Keep file names flat and unique across the whole bundle** — the `.mthds` and every `.py` share one flat name space, and a duplicate name is rejected rather than silently collapsed.

Sibling imports work: a file can `from _shared_math import ...` its neighbour, because every directory holding a `.py` in the bundle is on the path when registration runs.

## 8. What validation does not catch

Bundle validation reads the `.mthds` only. **The Python never reaches the validator**, and in hosted execution the PipeFunc checks that would otherwise run — that the function exists, that its return type matches the output concept — are skipped, because the function is not in that process.

So a bundle whose PipeFunc is missing, misnamed, undecorated, unannotated, importing a forbidden library, or returning the wrong class **validates completely clean** and fails at run time. Validation confirms the `.mthds` is well-formed; it says nothing about whether your Python will run.

Before shipping, check each PipeFunc by hand against the contract above: decorator present and called, one `working_memory` parameter, annotated return type imported from `structures` and matching the pipe's `output`, imports inside the allowed set, no network, no heavy module-level code.

## 9. Running a method that has PipeFuncs

The Python travels with the method, not with the run request. A method **registered on the platform** stores its `.mthds` and its `.py` together, and the platform assembles them into a bundle server-side on every run — so a run by method id executes your Python.

Submitting file contents inline for a run sends the `.mthds` text only; the `.py` files do not cross that wire. A PipeFunc method run that way will start and then fail to find its function. Register the method to run it.

Custom Python also requires a sandbox-hosted deployment; a deployment without one refuses a bundle carrying `.py` outright rather than running it unsandboxed.
