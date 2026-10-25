# Integrating into a Python project

Companion to `/pipelex-integrate` for a project that has a `pyproject.toml` (or `setup.py` / `requirements.txt`). The SDK facts were checked against `pipelex-sdk` 0.48.0, the floor step 8 installs for `python-pydantic`, and move only when that package does.

**A `python-structures` project runs on the `pipelex-sdk` its `pipelex` pins exactly, so settle at step 1 which `pipelex-sdk` it will run on once step 8 has run**, not only which one is installed now. When step 8 keeps the project's `pipelex`, that is the one installed with it: read it in the project's own environment (`importlib.metadata.version("pipelex-sdk")`, under `uv run python` for a uv project). A read that raises `PackageNotFoundError` means the environment is not synced, or its `pipelex` is below step 8's floor and brings no `pipelex-sdk` at all, as **Where `pipelex_sdk` comes from** below says: sync the environment with the project's package manager (`uv sync`, `poetry install`) and read again. When step 8 will raise `pipelex`, the installed version says nothing of the run: resolve the requirement step 8 will write without installing it, `echo 'pipelex>=<the version step 8 raises to>' | uv pip compile -`, which prints the `pipelex-sdk` that `pipelex` pins (without uv, the `pipelex-sdk` that release lists among its requirements on PyPI), and read that one. At step 8's `python-pydantic` floor or later, the call site below applies as written. Below it, **or when no read succeeds**, the module sends the bundle the older way, as the branch after the call site shows, and **a bundle whose `PipeDocGen` steps name template files stops the integration**: such a release takes no method tree and sends no template file, so a module written now would type-check and pass the gate, and every call would be refused, the step's template file not supplied. Generate nothing and write no module. Tell the user the integration waits on a `pipelex` release that pins a `pipelex-sdk` at that floor or later, and that until then the method runs through the run skill, which submits the bundle with its template files, or from a `python-pydantic` or TypeScript project, naming that skill to the user the way this skill's own hand-offs name a sibling. On a refresh, regenerate nothing either, and say that the module already there fails on every call until that release. At step 9, once step 8 has run, read the version once more: the module follows the one installed then, and when it falls below the floor over a templated bundle, the stop applies there, writing no module and naming the generated tree in the report.

## Detecting the project

| Question | Signals, in order | When inconclusive |
|---|---|---|
| **Audience → target** | `pipelex` **not** among the dependencies (`[project].dependencies`, `requirements*.txt`) → `python-pydantic`, no question: `python-structures` imports the runtime and would not even load; `pipelex` present → `python-structures` if `@pipe_func` or `from pipelex.core.stuffs.structured_content import StructuredContent` appears in the code, else one question with `python-structures` offered first | the user's explicit request wins over all of this |
| **Import package** | the package `[project].name` names (dashes → underscores), or the setuptools `packages` list, or the top-level directory holding `__init__.py` (`src/<package>/` in a src layout) | ask |
| **Package manager** | the lockfile: `uv.lock` → uv (`uv add`), `poetry.lock` → poetry, `Pipfile.lock` → pipenv | none → `pip install` into the active environment, stated |
| **Generated root** | an existing directory already holding generated code → beside it; else `<package>/generated/` | ask |
| **Formatter and linter** | `[tool.ruff]` → add the generated directory and the gate script `scripts/codegen_check.py` to `exclude` (or `extend-exclude`); `[tool.black]` → `extend-exclude`, one regex matching both; `[tool.isort]` → both in `skip` / `extend_skip_glob` — the exact entries follow this table | a tool this table does not name: read its config, add the equivalent for both paths, say so |
| **Type checker still covers the tree** | `[tool.pyright]` `include` / `exclude`; `[tool.mypy]` `packages` / `files` / `exclude` | an exclusion that would drop it is **not** added; generated code stays type-checked |
| **Packaged for distribution** | a `[build-system]` table and an import package | the bundle goes **inside** the package (`<package>/methods/<name>/main.mthds`) and `*.mthds` plus `codegen.lock` are registered as package data, as the Python starter does — a wheel that ships the call site must ship the bundle it loads at call time. A bundle already in the project but outside the package is moved there: propose the move, say why, and make it with `git mv` so it reads as one rename. An unpackaged app keeps `methods/<name>/` at the project root |
| **Aggregate gate** | a Makefile `check` target; `.github/workflows/*.yml`; `.pre-commit-config.yaml`; a `nox`/`tox` session | none: the gate script alone, and a sentence in the report saying where to call it |
| **Call-site location** | the project's existing service / client layer (`services/`, `clients/`, `api/`) → beside it | `<package>/pipelex/` |
| **Not gitignored** | the generated root and `sources.json` must be committable | reported and un-ignored on confirmation |
| **Owns a codegen harness** | a `codegen` Makefile target; `docs/codegen.md` or `docs/add-method.md`; an `add-method` Makefile target; `<package>/generated/` beside `<package>/methods/` | the skill's harness branch, entered at step 1, then the harness section below |

Why the Ruff exclusion is not optional: `ruff format` rewrites the generated bytes, breaks every stamp, and makes the drift check report the tree as hand-edited. The exclusion goes in before generation, so the first project-wide format after it is already safe. The gate script's entry goes in at the same time, before the script exists, because the script is copied verbatim and a refresh compares it byte for byte with this reference, so a reformat would make every refresh re-copy it and leave the project's own format check failing on `scripts/`. A `python-structures` project gets no script, so only its generated directory is excluded. With the generated root at `<package>/generated/`, the entries are:

```toml
[tool.ruff]
extend-exclude = ["<package>/generated", "scripts/codegen_check.py"]

[tool.black]
extend-exclude = '^/(<package>/generated/|scripts/codegen_check\.py$)'

[tool.isort]
extend_skip_glob = ["<package>/generated/*", "scripts/codegen_check.py"]
```

A project that already sets `exclude`, `skip` or a Black regex adds the two paths to what is there. The type checker is told nothing about either: the tree stays covered, and so does the script.

## The generated tree

`mthds_codegen` with `target: "python-pydantic"` and `output_dir: "<package>/generated/<method>"` writes:

- `models.py` — stamped; `from __future__ import annotations`, `from pydantic import BaseModel, Field`; one plain `BaseModel` subclass per concept, natives included, with `Field(..., description=…)`; no Pipelex import. Non-required fields are `T | None = None`.
- `codegen.lock` — TOML with the crate fingerprint, the engine version and one `[[artifacts]]` entry per stamped file.

With `target: "python-structures"` the file is `structures.py` — `StructuredContent` subclasses from `pipelex.core.stuffs.structured_content`, natives not re-emitted — for a Pipelex host whose `@pipe_func` functions return them.

**The skill creates the `__init__.py` files** the tree needs to be importable: `<package>/generated/__init__.py` (once per project, a one-line docstring) and `<package>/generated/<method>/__init__.py` (empty). Codegen never emits them and they are never artifacts: they carry no stamp, so the writer does not touch them and the check does not count them as orphans. When the project is packaged, list the generated subpackages where the project lists its packages and add `codegen.lock` as package data, as the Python starter's `pyproject.toml` does. Beside the lock the skill writes `sources.json`, unstamped.

## The call site

One module per method. `summarize_pdf` with a `document: native.Document` input, an optional `context: native.Text`, and a `summarize.DocumentSummary` output, from a committed bundle inside the package:

```python
# <package>/pipelex/summarize_pdf.py
"""Run the summarize_pdf method through the hosted Pipelex API.

`document` is an http(s) URL or a pipelex-storage:// reference, as ``{"url": ...}``. For a
local file or bytes, call ``client.prepare_inputs(tree=BUNDLE_DIR, inputs=...)`` first: it uploads
and rewrites the value. It treats any string it does not recognise as data:, http(s):// or
pipelex-storage:// as a LOCAL FILE PATH it reads and uploads, so gate schemes before handing
values from an untrusted caller to it.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipelex_sdk.client import PipelexAPIClient
from pipelex_sdk.runs import RunResults

from <package>.generated.summarize_pdf.models import DocumentSummary

PIPE_CODE = "summarize.summarize_pdf"
# The method's tree, sent whole with every run. A bundle is one closure: a main file that imports a
# sibling needs that sibling sent with it, or the run fails to load what the generated models were
# projected from. The SDK lists this directory under the MTHDS standard's membership rule and sends
# every file it keeps, the `.mthds` files and the files a step reads, such as a `PipeDocGen` step's
# template, among them. Names starting with a dot, a run's `inputs.json` and what a `.gitignore`
# inside the tree keeps out stay home; nothing screens the rest for secrets. A missing or empty
# directory is refused before any run starts, naming the path.
BUNDLE_DIR = Path(__file__).resolve().parent.parent / "methods" / "summarize_pdf"


@dataclass(frozen=True)
class SummarizePdfRun:
    """The narrowed output beside the whole results the run returned.

    ``output`` is what the method produced; ``results`` is everything else the run carries —
    ``pipeline_run_id``, the usage pair, the graph, and the references of any file it produced.
    A caller who wants only the output reads ``.output``.
    """

    output: DocumentSummary
    results: RunResults


async def summarize_pdf(*, document: dict[str, Any], context: str | None = None) -> SummarizePdfRun:
    inputs: dict[str, Any] = {"document": document}
    if context is not None:
        inputs["context"] = context
    async with PipelexAPIClient() as client:
        results = await client.start_and_wait(
            pipe_code=PIPE_CODE,
            tree=BUNDLE_DIR,
            inputs=inputs,
        )
    return SummarizePdfRun(output=DocumentSummary.model_validate(results.main_stuff), results=results)


def summarize_pdf_sync(*, document: dict[str, Any], context: str | None = None) -> SummarizePdfRun:
    """The blocking wrapper for a synchronous caller."""
    return asyncio.run(summarize_pdf(document=document, context=context))
```

**`PIPE_CODE` is the verdict's `main_pipe.pipe_ref`, verbatim**: the value the sidecar's `pipe` record holds, with the whole of its domain, even a dotted one (`legal.contracts.summarize`). The run resolves it as an exact `domain.pipe_code`. Stripped to the bare code, it still runs until two domains of the bundle declare that code, and from then on every run fails as ambiguous, which neither the type checker nor the gate can see.

**A list output is narrowed through its envelope.** The template above is right for an output whose `multiplicity` is `single`. A `variable` or `fixed` output arrives as the envelope `{"items": [...]}` — the runtime's `ListContent` serialised — and not as a top-level list, so `Model.model_validate(results.main_stuff)` rejects it and a run that succeeded fails in the narrowing. Validate the `items` as a list of the model, so `output` is `list[T]`:

```python
from pydantic import TypeAdapter


# An extract_invoices method whose output concept is a list of `Invoice`.
@dataclass(frozen=True)
class ExtractInvoicesRun:
    output: list[Invoice]
    results: RunResults


# In the async function, in place of the single-concept `Model.model_validate(results.main_stuff)`:
output = TypeAdapter(list[Invoice]).validate_python(results.main_stuff["items"])
return ExtractInvoicesRun(output=output, results=results)
```

Codegen emits a model per concept and no wrapper for the envelope, so nothing in the generated tree names it. `main_stuff` is `Any`, so the type checker does not catch a wrong narrowing either. For `fixed`, the declared `item_count` is not checked unless you check it, and the report says so.

Follow the project's conventions where you can see them — module style, quoting, error handling — and the SDK's defaults where you cannot.

**A `python-structures` project on a `pipelex-sdk` below step 8's `python-pydantic` floor** (the version step 1 settles for after step 8, read again at step 9, or none read) has no `tree` argument to send, so its module reads the bundle's `.mthds` texts itself and sends them as `mthds_contents`, the closure kept whole by reading every file, and its docstring names `prepare_inputs` with them as a list of `MthdsFileItem`. A bundle naming template files has already stopped at step 1. In place of the comment and the `tree=` argument above:

```python
from pipelex_sdk.crate_models import MthdsFileItem  # for the docstring's prepare_inputs call


def _read_bundle() -> list[str]:
    """Every `.mthds` file of the bundle, sorted, as the run's `mthds_contents`."""
    contents = [path.read_text(encoding="utf-8") for path in sorted(BUNDLE_DIR.rglob("*.mthds"))]
    if not contents:
        # `rglob` on a missing or empty directory returns nothing and raises nothing, so without
        # this the run goes out with `mthds_contents=[]` and fails server-side, naming the pipe
        # rather than the path that is actually wrong.
        raise FileNotFoundError(f"no .mthds files under {BUNDLE_DIR}")
    return contents


# In the async function: `mthds_contents=_read_bundle(),` in place of `tree=BUNDLE_DIR,`.
# In the docstring: ``client.prepare_inputs(files=[MthdsFileItem(content=text) for text in _read_bundle()], inputs=...)``.
```

Its `_read_bundle` reads every `.mthds` file under the bundle, a rule of its own that the folder step 1 passes does not follow: a `.mthds` file a `.gitignore` inside the bundle keeps out, or one under a hidden directory, is sent by this module though the types were not generated from it, so keep no such file in a bundle this module runs. That module fails once the project's `pipelex` brings a `pipelex-sdk` at that floor, which takes no `mthds_contents`, and a refresh then rewrites it to the template above, as the refresh reference says.

Variants by selector, replacing the `tree=` argument and dropping `BUNDLE_DIR`, the docstring's `prepare_inputs` call taking the same selector in its place (`prepare_inputs(method_ref="…", inputs=...)`, `prepare_inputs(method_id="…", inputs=...)`):

- **`method_ref`**, a published address: `method_ref="github.com/<owner>/<repo>[/<selector>][@<tag>]"`, with `pipe_code=PIPE_CODE` or omitted to run the package's declared pipe. The tag is optional and is the pin; without one the address resolves to the default branch at its head on every run, so the call site can run a method the committed types were never generated from; when the address carries no tag, the module docstring says it floats.
- **`method_id`**: `method_id="mt_…@<n>"` — the platform resolves the id: `mt_…@<n>` runs published version n for good, a bare `mt_…` the latest published version and `mt_…@draft` the draft. The module docstring names the id it runs and, for a bare or `@draft` id, says that a publish or a save changes what runs under the committed types.

Facts the module leans on: `PipelexAPIClient()` reads `PIPELEX_API_KEY` and `PIPELEX_BASE_URL` (default `https://api.pipelex.com`) itself; it is async-only and used as an async context manager; there is **no barrel** in `pipelex_sdk` by design, so every import is a full module path (`pipelex_sdk.client`, `pipelex_sdk.runs`, `pipelex_sdk.errors`); `start_and_wait(...)` takes the durable path on the hosted API (default 2 s poll, 20 min budget, `wait_options=WaitForResultOptions(...)` to change them) and falls back to blocking on a bare runner, returning `RunResults` whose `main_stuff` is always present for a completed run. `tree=BUNDLE_DIR` is listed under the standard's membership rule, rooted at the nearest `METHODS.toml` at or above it, else at the directory itself. **Step 1 stops over a `METHODS.toml` above the bundle**, since the workshop roots the folder step 1 passes at the folder itself: the run would send files the types were not generated from, and no refresh could record them, so the gate would report `stale-source` until the bundle moves. Look for it as Manifest Discovery does, in each parent of the resolved `BUNDLE_DIR` in turn, stopping after the one holding a `.git` entry, or at the filesystem root, and count only a regular file named `METHODS.toml`; then tell the user to move the bundle out from under it, or to integrate the package's own directory as the bundle. The tree travels inline when small and by hash otherwise; a missing directory raises `TreeSourceError` and an empty one `EmptyMethodTreeError`, both from `mthds.method_tree.exceptions`, before any run starts. Let the typed errors from `pipelex_sdk.errors` propagate — `RunFailedError`, `RunTimeoutError` (the run keeps going; resume by `pipeline_run_id`), `ApiResponseError` (branch on `.code`), `ApiUnreachableError`, `MissingMainStuffError` — and add the project's own handling only where it already wraps its other clients. Their common base, for a command that catches them all at its top, is `PipelineRequestError`, imported from `mthds.protocol.exceptions`: `pipelex_sdk.errors` uses it without re-exporting it.

**Where `pipelex_sdk` comes from.** A `python-pydantic` project gets it from the `pipelex-sdk` step 8 installs. A `python-structures` project gets it from `pipelex` itself, which depends on `pipelex-sdk`, at one exact version, starting from the `pipelex` 0.79.0 that step 8 raises the project to; an older `pipelex` does not bring it, so this module fails on its first import there. Add no `pipelex-sdk` requirement of the project's own: pipelex's exact pin decides the version, and a second requirement adds nothing but a place for the two to disagree.

**Raising `pipelex`.** Step 8 raises a `python-structures` project's `pipelex` to at least the floor as it raises the SDKs, with no question. If the raised runtime then refuses, with `FormerReleaseConfigError`, a configuration written for a former release, run `pipelex migrate --yes` from the project root in the project's environment (`uv run pipelex migrate --yes` under uv), which brings the project's `.pipelex/` and the home configuration directory (`~/.pipelex/`, or `PIPELEX_HOME`) to the current release, keeping a copy of each file it changes beside it, and name it in the report.

**The module returns the results beside the output.** The frozen dataclass keeps the narrowed output and the whole `RunResults` together, so a caller reaches `pipeline_run_id` — the durable handle a `RunTimeoutError` leaves in hand while the run carries on server-side — and the run's `tokens_usages` / `usage_assembly_error` pair without the module being edited or the method being run again. `pipelex-sdk`'s `docs/run-usage.md` is the page that states how to read that pair, including why an unrated cost is not a cost of zero; it is not shipped in the wheel, so the address to read it at — and the one to write into the report or the module's docstring — is `https://github.com/Pipelex/pipelex-sdk/blob/main/python/docs/run-usage.md`. Every other page named below is published the same way, at `https://github.com/Pipelex/pipelex-sdk/blob/main/python/docs/<page>.md`, and each field of `RunResults` has its own section in `docs/run-results.md`: point the user at the page rather than restating it, name the fields the method actually produces rather than reciting the list, and write none of what follows into the project as a helper. Each has the same name as its TypeScript twin, in snake case, and the report names them for a Python project exactly as it would for TypeScript, from these pages.

**Produced files — a `pipelex-storage://` reference, and a signed link that expires.** A run that produces an image, a PDF or a document puts the file's durable reference in the content's `url`, beside a `public_url` the storage provider signed when the file was written. The reference is permanent and is what belongs in a record; the signed link is short-lived, so one persisted in a database or baked into a cached page stops working without warning. Bringing the bytes down is the SDK's job and not something to re-implement over `client.resolve_storage_url`: `client.download_artifacts` saves everything a run produced under a directory, `client.resolve_artifacts` mints fresh links for a whole list of references in one bulk call, and `pipelex_sdk.artifacts.fetch_artifact` streams one within bounded limits. **The first two are methods on the client** — each one calls the API, so it needs the key the client holds — while `pipelex_sdk.artifacts.collect_artifacts` lists a result's references without touching the network and `pipelex_sdk.artifacts.artifact_filename` names a saved file; there is no barrel, so each import is the full module path. A release that also has `pipelex_sdk.artifacts.locate_artifacts`, which returns the paths in a result where each reference sits without touching the network, names each saved file after the field it fills (`$.rooms[3].staged_photo.url` is saved as `rooms-3-staged_photo.png`) and gives each entry of the download's verdict those paths as `found_at`; its `artifact_filename` takes a location, a content type and a scope rather than a reference. An older release names the file after its storage key. Match a saved file to its field by `found_at`, never by parsing its name. Their page is `docs/artifact-download.md`.

**`summarize_usage(results)` — what the run cost.** `pipelex_sdk.usage.summarize_usage` folds the `tokens_usages` / `usage_assembly_error` pair into one run-level reading with a per-pipe rollup, applying the rules `docs/run-usage.md` states — an unrated cost is not a cost of zero, and a partial sum says so — and it is pure: no client, no network, no mutation of its argument. Never add the records up by hand.

**`results.graph_spec` — the graph the run executed.** One node per pipe with its status, its timings and the models and cost attributed to it: the same document a local `pipelex` run writes as `graphspec.json`, carried on both paths. `results.graph_assembly_error` says why a graph is missing when one is — on the blocking path, which is what a bare runner answers on; the hosted results body does not carry it yet. The three I/O artifacts beside it, `pipe_io_contracts`, `input_form` and `output_form`, parse through the standard's own `mthds.protocol` shapes.

**`results.working_memory` — every named stuff of the run.** The whole memory the run finished with, typed as the standard's `DictWorkingMemoryAbstract`: `root` keyed by stuff name, `aliases` naming which entry is the `main_stuff`. It is the whole run, the inputs and the intermediates included, where `main_stuff` is the output alone; its section is in `docs/run-results.md`.

Parameters are keyword-only, typed from the signature: `str` for Text and Date (ISO 8601), `float` for Number, `bool` for YesNo, `dict[str, Any]` with a `url` key for Image and Document, the generated model for a structured concept or a composite native, `list[T]` for a list, `T | None = None` for a non-required input. Names are the pipe's input names as declared. A project that already constructs a `PipelexAPIClient` somewhere gets that construction reused instead of a fresh `async with` per call; an async-native project (FastAPI, an existing async codebase) gets the async function alone, without the `_sync` wrapper.

## The offline gate

**`python-pydantic`.** Copy `references/codegen_check.py` to `scripts/codegen_check.py` with step 10's `cp`, never by reading and rewriting it, at the project root and never inside the import package, where a wheel would ship it, and never format or lint it: step 5 put it in the formatter and linter exclusions beside the generated directory. It imports only the standard library, `pipelex-sdk` and the `mthds` package that SDK depends on, and runs `pipelex_sdk.codegen_check.run_codegen_check` over each generated directory — the SDK's mirror of `pipelex codegen check`, pure hashing with no engine, no network, no key and no `pipelex` runtime, present in the `pipelex-sdk` 0.48.0 that step 8 installs — then compares the SHA-256 recorded for each source in `sources.json` against the `.mthds` file on disk, and the recorded sources against every `.mthds` file of the tree the call site sends from the sidecar's `bundle_dir`, listed by `mthds.method_tree.lister.list_method_tree`, the lister of the `mthds` package `pipelex-sdk` depends on and lists `tree=` with, so the gate keeps out what the run keeps out — so a file added to the bundle, or one a `.gitignore` inside the tree or the manifest's `exclude` now keeps out or lets in, is `stale-source` too, although every recorded hash still matches, and so is a recorded template file the tree no longer carries. Do not add `pipelex` as a dependency to get a gate: that reverses the decision the target expresses, and this gate needs nothing the consumer does not already have. The script writes through `sys.stdout` / `sys.stderr`, so a no-print rule (Ruff's `T201`) does not fire, and it passes pyright's strict mode, so leave it inside the type checker's coverage.

Run it from the project root with **the project's own environment**, the one step 8 put `pipelex-sdk` in: `uv run python scripts/codegen_check.py …` under uv, `poetry run python …` under poetry, `pipenv run python …` under pipenv, and the active environment's `python` otherwise. An interpreter without the SDK does not guess: it exits `2` and names the fix. An SDK that is installed but raises something else while it loads — a pydantic-core that does not match pydantic, a corrupt file — is `2` as well, naming the exception and pointing at a reinstall of the project's dependencies, because that environment is broken rather than the wrong one. A check that raises instead of reaching a verdict — a lock `tomllib` refuses, a directory the process cannot search — is `2` too, for that directory, with the error on stderr, and the directories after it are still checked. The SDK import and each check are the only two places the script catches `Exception`, and a project whose Ruff selects `BLE001` needs no per-file ignore for them: the step-5 exclusion keeps the script out of Ruff altogether, and the script is never edited to satisfy a rule. Extend the project's existing gate rather than inventing one — for a Makefile, a target the `check` target depends on:

```make
codegen-check: ## Offline drift check over the generated trees
	uv run python scripts/codegen_check.py <package>/generated/summarize_pdf

check: lint typecheck codegen-check
```

and otherwise the same command as a step of an existing workflow job, as a `repo: local` hook in `.pre-commit-config.yaml` (`language: system`, `pass_filenames: false`), or as a line of the `nox` / `tox` session that already lints. Add every method's directory to that command as it is integrated, and on a refresh add the refreshed method's directory when it is missing, leaving the others as they are. A refresh also re-copies the script, with the same `cp`, when the project's copy differs from this reference, and installs it when the project has none, so a project integrated by an older version of the skill gets the current gate. Exit codes: `0` current, `1` drift or stale source, `2` no verdict (no lock, a malformed or unreadable lock or tree, a symlink at the generated directory or on an artifact's path, a check that raises, `pipelex-sdk` not importable or failing while it loads). It runs from the project root because `sources.json` records its source paths and `bundle_dir` relative to it, and `bundle_dir` is the call site's `BUNDLE_DIR` expressed that way. When `pipelex-sdk` ships this as a command of its own, the script is replaced by that one line.

**`python-structures`.** The project already depends on `pipelex`, so wire `pipelex codegen check <package>/generated/<method>` into its existing gate (a Makefile `check` target, a workflow step). Exit codes: `0` current, `1` drift, `2` no lock or an unreadable lock. Offline: no engine boot, no network, no key.

## A project that owns a codegen harness

A project made from `pipelex-starter-python` has three codegen targets. `make codegen` regenerates every method under `<package>/methods/` through the hosted `/v1/codegen` with `pipelex-sdk`, and needs `PIPELEX_API_KEY` from `.env` or the shell and no `pipelex` install. `make codegen-check`, the offline drift check, is the one target still shelling out to a `pipelex` CLI the starter deliberately does not depend on (`PIPELEX=` in its Makefile); its test suite runs `pipelex-sdk`'s own check over every tree, so `make agent-test` gates them without that CLI. `make add-method` scaffolds a method that lives elsewhere. Each method directory `<package>/methods/<name>/` holds one of two source kinds, never both: the bundle's `.mthds` files, or a `method.json` holding exactly one of `method_id` / `method_ref`. Nothing in the Makefile or `pyproject.toml` names a method, because the generator and the packaging discover them. Trees go under `<package>/generated/<module>/`, where `<module>` is `<name>` with its dashes turned into underscores (`summarize-pdf` → `summarize_pdf`), each with an `__init__.py` codegen never emits, and the typed CLI commands live under the mode sub-packages. On such a project:

- **a local bundle** goes under `<package>/methods/<name>/`, every `.mthds` file of it, with its entry file named `main.mthds`, which the starter's tests open. Run `make codegen`, then add the empty `<package>/generated/<module>/__init__.py` when it is missing, and add the bundle's entry to `CLI_INPUTS` in `tests/unit/test_generated_clients.py`, the one list in the starter that names a method by hand, which `make agent-test` fails until the new bundle is in it;
- **a catalog id or a published address** goes through `make add-method METHOD=<mt_…|github.com/…>` (with `PIPE=`, `NAME=` and `MODE=` as `docs/add-method.md` gives them), which writes the `method.json`, the tree with its `__init__.py`, and one Typer command in one execution mode, all from the method's own contract. When it refuses an input kind it cannot spell on a command line, or the call belongs somewhere other than a CLI command, write the `method.json` yourself, holding the selector and nothing else (`{"method_ref": "github.com/<owner>/<repo>[/<package>][@<tag>]"}`), then run `make codegen` and add the `__init__.py` as for a bundle. Never generate a tree beside the manifest by hand. A refusal about the selector itself, where the deployment does not resolve that kind, is not worked around this way, because `make codegen` sends the same selector to the same deployment;
- when `make codegen` stops because no `PIPELEX_API_KEY` reaches the project (the workshop holds a key of its own that the project does not), call `mthds_codegen` with the directory's own source (its files, or the manifest's `method_id` / `method_ref`) and `output_dir` set to `<package>/generated/<module>`, never the dashed `<name>`. That is the harness's own layout, and the result is byte-identical (same engine, same stamps, same lock, no sidecar in this starter). Say that `make codegen` is the refresh once the project's `.env` carries a key;
- write the CLI command the way `docs/cli-architecture.md` and the existing commands do, importing the generated model from `<package>.generated.<module>.models`; a command `make add-method` wrote already does;
- verify with `make agent-check` and `make agent-test`. There is no `sources.json` of this skill's shape, no `scripts/codegen_check.py` and no second generated directory.
