# Pin what the shared MTHDS language reference teaches about `PipeDocGen`, `PipeFunc` and the natives.
#
# `writing-mthds.md` is the reference `pipelex-design` reads before every write and the other authoring
# skills read for a syntax question; `native-content-types.md` beside it gives each native's attributes. An
# agent reaches only for what they teach: until `PipeDocGen` had a section, no designed method printed a
# document, and a natives table without `Choice` and `Rating` invited a concept of either name, which the
# runtime refuses. These tests hold the two files to each other and to the places that enumerate the
# operators again, so a pipe or a native added to one cannot go missing from the rest. The rationale is
# `docs/decisions.md`, "PipeDocGen is taught whole, and the runner says what it cannot print", and
# "A `PipeFunc` names its function by import path" for the `function_name` sweep.


from __future__ import annotations

import keyword
import re
import unicodedata
from pathlib import Path

import pytest

from scripts.gen_skill_docs import load_target_config, render_templates

TARGETS = ("prod", "codex", "mistral-vibe")
REPO_ROOT = Path(__file__).parents[2]
PAID_PLUGIN_NAMES = ("docgen-template", "pipelex-doc-gen", "document generation plugin", "Docgen")


def rendered_shared(target_name: str, name: str) -> str:
    """A shared reference as the named target renders it."""
    config = load_target_config(REPO_ROOT / "targets", target_name)
    rendered = render_templates(
        REPO_ROOT / "templates",
        REPO_ROOT,
        config.template_vars,
        include_skills=["pipelex-edit"],
        target_name=config.name,
    )
    return next(content for path, content in rendered.items() if path.match(f"skills/shared/{name}"))


def section(text: str, heading: str) -> str:
    """The text under `heading`, up to the next heading of its level or above. A TOML example holds `# `
    comments, so only a `##` or `###` line ends a section."""
    assert text.count(f"\n{heading}") == 1, f"expected one {heading!r} heading"
    _, rest = text.split(f"\n{heading}", 1)
    return re.split(r"\n#{2,3} ", rest, maxsplit=1)[0]


def import_path_violation(function_name: str) -> str | None:
    """Why a `function_name` is not an import path by MTHDS standard 7.0.0's rules, or None when it is one."""
    name = unicodedata.normalize("NFC", function_name)
    if "." not in name:
        return "it holds no dot"
    for segment in name.split("."):
        if not segment.isidentifier():
            return f"`{segment}` is not a Python identifier"
        if keyword.iskeyword(segment):
            return f"`{segment}` is a Python keyword"
        if unicodedata.normalize("NFKC", segment) != segment:
            return f"`{segment}` changes under NFKC normalization"
    return None


def shipped_text_files() -> list[Path]:
    """Every Markdown and Jinja source the plugin ships from or renders, the vendored corpus and the hook bundle
    aside, which this repository never edits."""
    roots = [REPO_ROOT / "templates" / "skills", REPO_ROOT / "skills"]
    roots += [REPO_ROOT / output / "skills" for output in ("pipelex", "pipelex-codex", "pipelex-vibe")]
    return sorted(path for root in roots for path in root.rglob("*") if path.is_file() and path.suffix in {".md", ".j2"})


def table_codes(table: str) -> list[str]:
    """The backticked code in the first cell of each body row of a Markdown table."""
    codes: list[str] = []
    for line in table.splitlines():
        match = re.match(r"\| `([A-Za-z]+)` \|", line)
        if match:
            codes.append(match.group(1))
    return codes


class TestLanguageReference:
    @pytest.mark.parametrize("target_name", TARGETS)
    def test_both_tables_name_the_same_natives(self, target_name: str) -> None:
        reference_table = section(rendered_shared(target_name, "writing-mthds.md"), "## 3. Native Concepts")
        summary = section(rendered_shared(target_name, "native-content-types.md"), "## Content Type Summary")
        in_reference = table_codes(reference_table)
        in_summary = table_codes(summary)
        assert in_reference, "the reference's natives table has no rows"
        assert sorted(in_reference) == sorted(in_summary), (
            f"{target_name}: the natives differ between the reference ({sorted(set(in_reference) - set(in_summary))} only there) "
            f"and the content types summary ({sorted(set(in_summary) - set(in_reference))} only there)"
        )

    @pytest.mark.parametrize("native", ["Markdown", "Choice", "Rating"])
    def test_the_newer_natives_are_taught(self, native: str) -> None:
        """A native missing from the tables is a concept an author may declare, and the runtime refuses that."""
        reference = rendered_shared("prod", "writing-mthds.md")
        assert f"| `{native}` |" in section(reference, "## 3. Native Concepts")
        assert "`native_concept_redeclaration`" in reference
        content_types = rendered_shared("prod", "native-content-types.md")
        assert f"\n### {native} — `{native}Content`\n" in content_types, f"native-content-types.md gives {native} no section"
        assert f'"concept": "native.{native}"' in content_types, f"native-content-types.md shows no {native} input"

    def test_a_rating_carries_its_label(self) -> None:
        """`RatingContent` has an optional `label`, the selected level's name, which is what `$var` renders."""
        content_types = rendered_shared("prod", "native-content-types.md")
        summary = section(content_types, "## Content Type Summary")
        rating_row = next(line for line in summary.splitlines() if line.startswith("| `Rating` |"))
        for attribute in ("`level`", "`label`", "`confidence`", "`probabilities`", "`position`"):
            assert attribute in rating_row, f"the summary's Rating row lacks {attribute}"
        assert "| `label` |" in section(content_types, "### Rating — `RatingContent`")

    def test_a_document_reaches_a_model_that_reads_it(self) -> None:
        """A `PipeLLM` sends a `Document` named in its prompt to its model, as the reference's own `PipeLLM`
        example does; the content types reference used to say a document could not reach a model at all."""
        content_types = rendered_shared("prod", "native-content-types.md")
        assert "Documents cannot be sent directly to LLMs" not in content_types
        document = section(content_types, "### Document — `DocumentContent`")
        assert "A PipeLLM whose prompt names the document" in document
        assert "is refused only when that step runs, after the steps before it may have spent credit" in document, (
            "the pre-run format check walks the entry pipe's inputs alone, so a document made mid-run is refused at its step"
        )
        assert "**Produced by PipeDocGen**" in document

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_section_teaches_every_field(self, target_name: str) -> None:
        docgen = section(rendered_shared(target_name, "writing-mthds.md"), "### PipeDocGen — ")
        assert 'type        = "PipeDocGen"' in docgen
        assert "**Required:** `format`, one of `pdf`, `xlsx`, `docx` or `pptx`" in docgen
        for field in ("template", "template_file", "filename", "model"):
            assert f"| `{field}` |" in docgen, f"{target_name}: the fields table lacks `{field}`"
        assert "**Output** MUST be `Document` or a concept refining it" in docgen
        assert "{% raw %}" not in docgen and "{{ invoice.invoice_number }}" in docgen, "the Jinja examples must render literally"

    def test_a_report_for_a_document_is_markdown(self) -> None:
        """A `Text` report prints its Markdown marks as they are; the canonical case declares `Markdown`."""
        docgen = section(rendered_shared("prod", "writing-mthds.md"), "### PipeDocGen — ")
        assert 'output      = "Markdown"' in docgen
        assert 'inputs      = { report = "Markdown" }' in docgen
        assert "**So the report an LLM writes for a document is declared `Markdown`**" in docgen

    def test_a_pdf_without_a_template_is_laid_out_and_pptx_never_is(self) -> None:
        docgen = section(rendered_shared("prod", "writing-mthds.md"), "### PipeDocGen — ")
        assert "**Without a template, the step lays its inputs out itself**, for `pdf`, `xlsx` and `docx`" in docgen
        assert "`pptx` has no layout of its own and always takes a `template_file`" in docgen

    def test_a_template_file_sits_beside_the_bundle_and_travels_with_it(self) -> None:
        """A bundle loaded from a string, as a runner receiving submitted files does, has no directory to find a
        template file in, so every submission sends the template files beside the `.mthds` files. The skills pass the
        bundle directory as `method_dir`, and the workshop finds each template from the step naming it, keyed by
        that step, and lists what it sent; listed in `files`, a template goes as a path. The section used to fall
        back to an inline template when the runner refused the file; the workshop now takes it, so a refusal names
        an older workshop and its refresh, never a rewrite of the step."""
        docgen = section(rendered_shared("prod", "writing-mthds.md"), "### PipeDocGen — ")
        assert "A template file beside the bundle, its path relative to the `.mthds` file that names it" in docgen
        assert "#### Template files" in docgen
        assert "**A template file travels with the bundle**" in docgen
        assert "**The workshop finds it**: given the bundle directory as `method_dir`" in docgen
        assert "lists every file it sent in `files_sent`" in docgen
        assert "**Listed in `files` instead**, a template file goes as a `{path}` item beside the `.mthds` files, never inline" in docgen
        assert "the `method-graph.html` page `mthds_validate` writes beside the bundle" in docgen
        assert "about 7.4 MiB beside a small bundle" in docgen
        assert "**The limits are the workshop's and the runner's today**" in docgen
        assert "at most 16 `.mthds` files of at most 1 MiB each, which a folder is held to before anything is sent" in docgen
        assert "its `.html` templates at most 512 KiB in all, which the runner refuses past that as too large" in docgen
        assert "**A workshop older than template files refuses one** as *Path is not a .mthds file*" in docgen
        assert "refresh with `npx -y @pipelex/mcp@latest`" in docgen
        assert "Never rewrite the step to do without its template to get past it." in docgen
        assert "write an inline `template` for a `pdf`, or none for the layout, in its place" not in docgen

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_what_belongs_to_the_folder_is_said_and_a_saved_run_is_kept_out(self, target_name: str) -> None:
        """The workshop's membership rule decides what a `method_dir` sends, and it reads the `.gitignore` files
        inside the folder, which is how a saved run is kept out of the method: `mthds_download_artifacts` writes a
        `.gitignore` of `*` into a `runs/` it creates. A symbolic link refuses the folder, so a file is copied in.
        The reference is rendered for an outside target too, which may not ship `/pipelex-run`, so the section
        names no skill."""
        docgen = section(rendered_shared(target_name, "writing-mthds.md"), "### PipeDocGen — ")
        assert "**What belongs to the folder**" in docgen
        assert "a `.gitignore` inside the folder excludes, read as git reads it; a `.gitignore` above the folder does not count" in docgen
        assert "A symbolic link the rule does not exclude refuses the folder, so a file is copied into it, never linked." in docgen
        assert "`mthds_download_artifacts` writes one holding `*` into each `runs/` it creates" in docgen
        assert "/pipelex-" not in section(docgen, "#### Template files")

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_an_older_workshop_is_refreshed_and_the_files_listed_meanwhile_said_aloud(self, target_name: str) -> None:
        """A workshop older than the folder form drops `method_dir`, an argument it does not know, and answers that
        no method was given. The cure is the cached release's refresh, which needs the host to restart the server;
        until then the skills list the files, the convention the folder replaced, and say that they do. The listing
        is the include's listing form, never a second copy of it, and a run never pairs the dropped folder with a
        `method_id`, which would run the saved method instead."""
        docgen = section(rendered_shared(target_name, "writing-mthds.md"), "### PipeDocGen — ")
        older = docgen[docgen.index("**A workshop older than the folder form does not take `method_dir`**") :]
        older = older[: older.index("\n\n")]
        assert "*Provide MTHDS files, a method_ref address, or a method_id.*" in older
        assert "refresh with `npx -y @pipelex/mcp@latest`, which takes effect once the host restarts the server" in older
        assert "Say so, and until then list the bundle's files, saying that you do." in older
        listing = (
            "Submit every `.mthds` file beneath the bundle directory **except anything under a `runs/` directory**,"
            " and every template file a `PipeDocGen` step names."
        )
        assert listing in older
        assert "Prefer the path form `{path: <absolute path>}`, **the root `.mthds` file first**" in older
        assert "least of all beside a `method_id` on a run: it drops the folder and runs the saved method instead." in older
        source = (REPO_ROOT / "templates" / "skills" / "shared" / "writing-mthds.md.j2").read_text(encoding="utf-8")
        assert '{% set validate_call_folder = false %}{% include "skills/shared/validate-call.md.j2" %}' in source
        assert "Prefer the path form" not in source, "the listing reaches the reference through the include alone"

    @pytest.mark.parametrize("target_name", ["prod", "codex", "mistral-vibe"])
    def test_a_template_is_written_before_the_step_that_names_it(self, target_name: str) -> None:
        """The edit hook sends no template it cannot find, so the API refuses a step whose template is not written
        yet and blocks the edit, and writing the template afterwards runs no hook. The order is said, and the cure
        when the block came first, which is a save of the `.mthds` file again, never an edit of the step."""
        docgen = section(rendered_shared(target_name, "writing-mthds.md"), "### PipeDocGen — ")
        assert "**Write the template file before the `.mthds` file that names it.**" in docgen
        assert "writing the template afterwards does not run the hook again" in docgen
        assert "save the `.mthds` file again once the template exists; never edit the step to get past it." in docgen
        source = (REPO_ROOT / "templates" / "skills" / "shared" / "writing-mthds.md.j2").read_text(encoding="utf-8")
        branch = source[: source.index("**Write the template file before")]
        assert branch.rstrip().endswith('{% if platform != "agent-skills" %}'), "an outside target has no hook, so it has no such block"

    def test_the_catalog_and_the_template_check_are_said_where_template_files_are(self) -> None:
        """`mthds_save_method` takes `.mthds` and `.py` files alone, so a saved method whose step names a template
        file does not load by its id; and a valid verdict's `template_check_warning` is acted on by whoever wrote
        the template, which the skills that report a verdict point at."""
        docgen = section(rendered_shared("prod", "writing-mthds.md"), "### PipeDocGen — ")
        assert "**The catalog stores no template file yet**" in docgen
        assert "does not load by its id, while its directory still validates and runs as `method_dir`" in docgen
        assert "**A `template_check_warning` in a valid verdict's `warnings`**" in docgen
        assert "It never changes `is_valid`, but the printed file may show it." in docgen
        assert "a template the user supplied is theirs, so name the finding and ask before changing it" in docgen

    def test_a_missing_engine_is_reported_by_validation_and_told(self) -> None:
        """On the hosted plane on 2026-10-12 a templated `pdf` validated as refused at load, naming its engine;
        the PDF laid out from the inputs validated. The section says which prints where, and that the user is told."""
        docgen = section(rendered_shared("prod", "writing-mthds.md"), "### PipeDocGen — ")
        assert "A `pdf` laid out from its inputs prints on the built-in engine." in docgen
        assert "so `mthds_validate` reports it before any run spends credit" in docgen
        assert "Tell the user, and offer the PDF laid out from the inputs rather than changing the format in silence." in docgen

    def test_the_engine_is_checked_never_listed(self) -> None:
        """The workshop's lookup takes `doc_gen` in a check alone: the listing holds no document engines."""
        reference = rendered_shared("prod", "writing-mthds.md")
        models = section(reference, "### Model references")
        model_field = next(line for line in models.splitlines() if line.startswith("Every pipe with a `model` field"))
        assert "`PipeDocGen`" in model_field
        assert "A `PipeDocGen`'s document engine is only ever checked, with `doc_gen`" in models

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_pipefunc_names_its_function_by_import_path(self, target_name: str) -> None:
        """MTHDS standard 7.0.0 reads `function_name` as the function's import path from the method tree's root,
        and the pipelex release that retired the function registry refuses a flat name and `@pipe_func(name=…)`.
        The section teaches that reading, its rules, the marker without its argument and the migration, and none
        of the registry's."""
        pipefunc = section(rendered_shared(target_name, "writing-mthds.md"), "### PipeFunc — ")
        assert "**`function_name` is the function's Python import path from the root of the method's tree" in pipefunc
        assert 'function_name = "funcs.text_utils.capitalize"' in pipefunc
        assert "@pipe_func()\ndef capitalize(working_memory: WorkingMemory) -> TextContent:" in pipefunc
        assert "**Never write `@pipe_func(name=…)`**" in pipefunc
        assert "The name holds at least one dot." in pipefunc
        assert "that NFKC normalization leaves unchanged" in pipefunc
        assert "is refused as ambiguous" in pipefunc
        assert "`pipe_func_function_refused`" in pipefunc
        assert "`pipelex fix function-names <method dir>`" in pipefunc
        assert "a step keeps its `function_name` when its bundle file moves, unlike a `template_file`" in pipefunc
        for retired in ("is a registry key, not an import path", "must already be registered", "call a registered Python function"):
            assert retired not in pipefunc, f"{target_name}: the registry reading is retired: {retired!r}"
        assert "`PipeFunc` is experimental on the hosted plane." in pipefunc

    def test_every_shipped_function_name_is_an_import_path(self) -> None:
        """An agent copies the examples it reads, so every `function_name = "…"` a shipped source shows is an import
        path the runtime accepts, and no `@pipe_func(…)` call passes an argument; the retired forms are named only in
        prose, as what not to write."""
        assignments = 0
        for path in shipped_text_files():
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r'^function_name\s*=\s*"([^"]*)"', text, flags=re.MULTILINE):
                assignments += 1
                violation = import_path_violation(match.group(1))
                assert violation is None, f"{path.relative_to(REPO_ROOT)}: `{match.group(1)}` is no import path: {violation}"
            for match in re.finditer(r"^@pipe_func\((.*)\)", text, flags=re.MULTILINE):
                assert match.group(1) == "", f"{path.relative_to(REPO_ROOT)}: `@pipe_func({match.group(1)})` takes no argument"
        assert assignments > 0, "the sweep found no `function_name` example: the reference's PipeFunc example moved"

    @pytest.mark.parametrize(
        ("function_name", "is_import_path"),
        [
            ("funcs.text_utils.capitalize", True),
            ("text_utils.capitalize", True),
            ("capitalize", False),
            ("funcs.text-utils.capitalize", False),
            ("funcs.class.capitalize", False),
            ("ﬁles.load", False),
        ],
    )
    def test_the_sweep_reads_the_standard_s_rules(self, function_name: str, is_import_path: bool) -> None:
        assert (import_path_violation(function_name) is None) is is_import_path

    def operators(self) -> list[str]:
        """The operators the reference documents, each a `### PipeX — ` heading of section 6 that is neither a
        controller nor the signature: every place that enumerates the operators again names each of them."""
        reference = rendered_shared("prod", "writing-mthds.md")
        pipe_types = reference.split("\n## 6. Pipe Type Reference\n", 1)[1].split("\n## 7. ", 1)[0]
        names = re.findall(r"^### (Pipe[A-Za-z]+) — ", pipe_types, flags=re.MULTILINE)
        controllers = {"PipeSequence", "PipeBatch", "PipeParallel", "PipeCondition", "PipeSignature"}
        operators = [name for name in names if name not in controllers]
        assert {"PipeLLM", "PipeExtract", "PipeCompose", "PipeFunc"} <= set(operators), f"section 6 reads as {names}"
        return operators

    def test_the_operators_include_pipedocgen(self) -> None:
        assert "PipeDocGen" in self.operators()

    def test_the_signature_leaf_list_names_every_operator(self) -> None:
        reference = rendered_shared("prod", "writing-mthds.md")
        leaves = next(line for line in reference.splitlines() if line.startswith("- **Operator (leaf)**"))
        for name in self.operators():
            assert f"`{name}`" in leaves, f"the signature's leaf list lacks `{name}`"

    def test_the_stepwise_leaf_list_names_every_operator(self) -> None:
        stepwise = (REPO_ROOT / "skills" / "pipelex-design" / "references" / "stepwise.md").read_text(encoding="utf-8")
        leaves = next(line for line in stepwise.splitlines() if line.startswith("3. For a leaf, write the concrete operator"))
        for name in self.operators():
            assert f"`{name}`" in leaves, f"stepwise.md's leaf list lacks `{name}`"

    def test_explain_names_every_operator(self) -> None:
        explain = (REPO_ROOT / "templates" / "skills" / "pipelex-explain" / "SKILL.md.j2").read_text(encoding="utf-8")
        leaves = next(line for line in explain.splitlines() if line.startswith("Name every pipe with its type"))
        for name in self.operators():
            assert f"`{name}`" in leaves, f"pipelex-explain's list of leaves lacks `{name}`"

    def test_no_shipped_source_names_the_paid_plugin(self) -> None:
        """Whether this public plugin names the paid Docgen plugin or its `docgen-template` skill is an unruled
        product question, so no source the plugin ships from names either; the runtime's own refusal may."""
        sources = [*(REPO_ROOT / "templates" / "skills").rglob("*.j2"), *(REPO_ROOT / "skills").rglob("*.md")]
        assert sources
        for path in sources:
            text = path.read_text(encoding="utf-8")
            for term in PAID_PLUGIN_NAMES:
                assert term not in text, f"{path.relative_to(REPO_ROOT)} names {term!r}"
