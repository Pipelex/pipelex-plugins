"""Pin the shape of the pipelex-lab skill, its references, and the claims its capability map makes."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.check import SKILL_CEILING_CHARS
from scripts.gen_skill_docs import load_target_config, render_templates, resolve_output_dir

TARGETS = ("prod", "codex", "mistral-vibe")
REPO_ROOT = Path(__file__).parents[2]


def render(target_name: str, skill: str = "pipelex-lab") -> str:
    """The skill as the named target renders it — what a user of that harness installs."""
    config = load_target_config(REPO_ROOT / "targets", target_name)
    rendered = render_templates(
        REPO_ROOT / "templates",
        REPO_ROOT,
        config.template_vars,
        include_skills=[skill],
        target_name=config.name,
    )
    return next(content for path, content in rendered.items() if path.match(f"skills/{skill}/SKILL.md"))


def description(skill: str) -> str:
    """A skill's `description:` line, read from its template, which every target renders unchanged."""
    template = (REPO_ROOT / "templates" / "skills" / skill / "SKILL.md.j2").read_text(encoding="utf-8")
    return next(line for line in template.splitlines() if line.startswith("description: "))


def the_move(body: str, number: int) -> str:
    """Move `number`, from its heading to the next second-level heading."""
    return body.split(f"\n## {number}. ", 1)[1].split("\n## ", 1)[0]


class TestPipelexLabSkill:
    """`pipelex-lab` owns the loop around a method that the proof lab's driver ran by hand: frame a use case,
    write each case's answer key before its first run, agree a budget, then run, score and log every run,
    fixing the method until the pass bar or a stop (`wip/lab-skill/design.md`, ratified 2026-09-24). It is
    written to the read-before-act rule from the start: the three moves with their guards and the loop's stops in
    `SKILL.md`, and the branches — framing, the key's format, the log's format — in references read at their move.
    What these pin is that shape. The guards themselves are registered in `test_skill_guards.py`."""

    REFERENCES_DIR = REPO_ROOT / "skills" / "pipelex-lab" / "references"
    REFERENCES = ("frame.md", "key.md", "log.md")

    def reference(self, name: str) -> str:
        return (self.REFERENCES_DIR / name).read_text(encoding="utf-8")

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_each_reference_is_pointed_at_where_its_move_starts(self, target_name: str) -> None:
        """A pointer only in the closing index is a branch that will not be read, so each reference is named at
        the move that needs it, with the instruction to read it before acting."""
        body = render(target_name)
        assert "Read [frame.md](references/frame.md) before asking anything" in the_move(body, 1)
        assert "Read [key.md](references/key.md) before writing a key." in the_move(body, 2)
        assert "Read [log.md](references/log.md) before the first entry" in the_move(body, 3)
        index = body.split("## References", 1)[1]
        for name in self.REFERENCES:
            assert f"(references/{name})" in index, f"{target_name}: the reference index does not name {name}"

    def test_the_references_are_static_and_say_when_they_are_read(self) -> None:
        """References are copied verbatim into every target and never rendered, so a template expression in one
        ships as literal braces; and each opens by naming the condition that sends the model to it."""
        for name in self.REFERENCES:
            text = self.reference(name)
            assert "{{" not in text and "{%" not in text, f"references/{name} carries template syntax, which is never rendered"
            first_paragraph = text.split("\n\n")[1]
            assert first_paragraph.startswith("Read this "), f"references/{name} does not open with its entry condition"
            assert "cross-skill invocation" not in text, f"references/{name} carries a per-target sentence"

    def test_a_reference_never_sends_the_model_to_another(self) -> None:
        """References are one level deep: one read is enough to take a branch."""
        for name in self.REFERENCES:
            text = self.reference(name)
            for other in self.REFERENCES:
                if other != name:
                    assert other not in text, f"references/{name} sends the model on to references/{other}"
            assert not re.findall(r"\]\(([^)]+)\)", text), f"references/{name} links another file"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_target_ships_the_references_byte_for_byte(self, target_name: str) -> None:
        """The committed target copies are the ones a user installs, so compare against those."""
        config = load_target_config(REPO_ROOT / "targets", target_name)
        installed = resolve_output_dir(REPO_ROOT, config.source) / "skills" / "pipelex-lab" / "references"
        assert sorted(path.name for path in installed.iterdir()) == sorted(self.REFERENCES), f"{target_name}: stale or missing references"
        for name in self.REFERENCES:
            assert (installed / name).read_bytes() == (self.REFERENCES_DIR / name).read_bytes(), f"{target_name}: references/{name} is stale"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_skill_fits_what_a_compaction_keeps(self, target_name: str) -> None:
        """The loop runs long, so a compaction mid-loop is the expected case, and the stops must survive it."""
        size = len(render(target_name))
        assert size <= SKILL_CEILING_CHARS, f"{target_name}: pipelex-lab renders {size} characters, over the {SKILL_CEILING_CHARS} ceiling"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_every_platform_renders_the_skill(self, target_name: str) -> None:
        body = render(target_name)
        assert "# Experiment with a method" in body
        assert "{%" not in body
        assert "{{" not in body
        if target_name == "prod":
            assert "cross-skill invocation" not in body
        else:
            assert "mcp__" not in body
            assert "open that skill's `SKILL.md` beside this one and follow it" in body

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_each_case_is_its_own_inputs_directory(self, target_name: str) -> None:
        """Two cases written beside the bundle overwrite each other's `inputs.json`, inside the directory the lab
        must stay out of. So the lab names each case's directory to `/pipelex-inputs` and to `/pipelex-run`, and
        both of them take a directory the caller names for a local bundle."""
        body = render(target_name)
        assert "each case's directory, `cases/<case>/`, as its `<output_dir>`" in the_move(body, 2)
        assert "naming `cases/<case>/` as the directory of its inputs" in the_move(body, 3)
        assert "usually the one holding `main.mthds`, unless the caller names another" in render(target_name, "pipelex-inputs")
        assert "They sit beside the bundle unless the caller named another directory" in render(target_name, "pipelex-run")

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_a_case_is_kept_out_of_version_control_by_its_directory(self, target_name: str) -> None:
        """The case directory will hold the key, whose facts come from the user's files, and `inputs.json`, so it is
        the directory that is checked: a copied PDF under a `.gitignore` of `*.pdf` reads ignored, and a check of
        the copies would add no entry and leave the key and `inputs.json` to the next `git add .`."""
        move = the_move(render(target_name), 2)
        assert (
            "**A case of the user's own files stays out of version control**: in a git repository, "
            "`git check-ignore -q` `lab/<method>/cases/<case>/` itself, never a file in it, before anything is copied into it. "
            "For a path not ignored, add `lab/<method>/cases/<case>/` to the nearest `.gitignore`"
        ) in move
        assert "the case's paths" not in move

    @pytest.mark.skipif(shutil.which("git") is None, reason="the reading is git's")
    def test_git_reads_the_case_directory_as_the_lab_needs(self, tmp_path: Path) -> None:
        """The two readings the lab relies on: a rule that ignores the copies does not ignore the case directory, and
        a case directory not yet created reads ignored under a lab git already ignores, so it gains no second entry."""

        def ignored(path: str) -> bool:
            # This machine's excludes file is left out, so that a developer's own rules cannot change the reading.
            command = ["git", "-c", f"core.excludesFile={os.devnull}", "-C", str(tmp_path), "check-ignore", "-q", path]
            return subprocess.run(command, check=False).returncode == 0

        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pdf\n", encoding="utf-8")
        assert ignored("lab/m/cases/c/inputs/lease.pdf")
        assert not ignored("lab/m/cases/c/")
        gitignore.write_text("*.pdf\nlab/m/cases/c/\n", encoding="utf-8")
        assert ignored("lab/m/cases/c/")
        gitignore.write_text("lab/\n", encoding="utf-8")
        assert ignored("lab/m/cases/new-case/")

    def test_the_lab_reads_runs_and_never_starts_one(self) -> None:
        """The lab hands every run to `/pipelex-run`, which owns the credit guard and the run id, and every fix to
        `/pipelex-edit` or `/pipelex-design`. So on Claude it pre-approves the tools that read a run and none that
        starts one, saves a method or validates a bundle."""
        frontmatter = render("prod").split("\n---\n", 1)[0]
        tools = re.findall(r"mcp__plugin_pipelex_pipelex__(\w+)", frontmatter)
        assert sorted(tools) == ["mthds_download_artifacts", "mthds_run_results", "mthds_run_status"]

    def test_the_workshop_stops_only_the_loop(self) -> None:
        """Framing and setting up need only files, so an absent workshop stops the loop and nothing before it. That
        is not the hard stop `MCP_SKILLS` asserts in `test_gen_skill_docs.py`, and the stop's recovery is the shared
        connection reference."""
        requirements = render("prod").split("## Requirements", 1)[1].split("\n## ", 1)[0]
        assert "frame and set up, then stop before the loop" in requirements
        assert "](../shared/credentials.md#the-tool-is-absent)" in requirements

    def test_the_loop_has_every_stop_the_ruling_bounds_it_with(self) -> None:
        """DB5 was ruled an autonomous loop, bounded by stops rather than by a go per round. Each stop is one numbered
        item of the list that ends the turn, so none can drift into prose a model skims past."""
        loop = the_move(render("prod"), 3)
        stops = loop.split("**The loop stops, and ends the turn on the scorecard**, when:", 1)[1]
        numbered = re.findall(r"^(\d+)\. ", stops, flags=re.MULTILINE)
        assert numbered == [str(n) for n in range(1, 8)], f"the loop's stops are numbered {numbered}"
        for needle in (
            "pass bar",
            "past the budget",
            "traces to the inputs",
            "no fix in sight",
            "best round so far",
            "not the method's",
            "interrupts",
        ):
            assert needle in stops, f"the loop has no stop for {needle!r}"


class TestLabTriggers:
    """A trigger phrase has one owner (`docs/decisions.md`, 2026-09-21): a phrase in two descriptions recruits the
    wrong skill half the time. The lab arrived last, beside skills that already own "run it again", "generate test
    data" and "create test files", so each of its phrases is held to appear in no other description."""

    SKILLS_DIR = REPO_ROOT / "templates" / "skills"

    def test_no_lab_trigger_is_claimed_by_another_skill(self) -> None:
        lab_phrases = re.findall(r'"([^"]+)"', description("pipelex-lab"))
        assert lab_phrases, "the lab's description quotes no trigger phrase"
        others = [path.parent.name for path in self.SKILLS_DIR.glob("*/SKILL.md.j2") if path.parent.name != "pipelex-lab"]
        for skill in others:
            theirs = description(skill).lower()
            for phrase in lab_phrases:
                assert f'"{phrase.lower()}"' not in theirs, f"{phrase!r} is claimed by both pipelex-lab and {skill}"

    @pytest.mark.parametrize("phrase", ["run it again", "generate test data", "mock inputs", "create test files", "do a dry run first"])
    def test_the_lab_leaves_the_phrases_others_own(self, phrase: str) -> None:
        assert f'"{phrase}"' not in description("pipelex-lab")


class TestIntegrationPoints:
    """The other skills point at the lab where a builder reaches it without asking for it (phase 2 of
    `wip/lab-skill/plan.md`). Design's hand-off names it beside the test files it already offers. A run the lab did
    not start is still credit spent, and "run it again" belongs to `/pipelex-run`, so that skill offers the lab a run
    of a lab case, and the lab logs it outside its rounds. The file factory lists every file's planted facts, which a
    key takes as they are. Every one of those skills sits at the size ceiling, so each point is one sentence, pinned
    here so that a later trim cannot drop it without saying so."""

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_design_hands_off_to_the_lab(self, target_name: str) -> None:
        hand_off = render(target_name, "pipelex-design").split("5. **Hand off**:", 1)[1].split("\n", 1)[0]
        assert "`/pipelex-lab` writes answer keys and scores the runs" in hand_off

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_a_case_is_handed_to_inputs_with_no_run_offer(self, target_name: str) -> None:
        """The lab hands each case to `/pipelex-inputs` at its second setup item, before the third writes the case's
        key, and that skill ends by offering the run. A yes to the offer would run the case before its key exists,
        which breaks the lab's first guard. So the lab asks it to stop at run-ready, and the inputs skill waives the
        offer on a calling skill's request, the one exemption among the offer's conditions."""
        setup = the_move(render(target_name), 2)
        hand_off = next(line for line in setup.splitlines() if line.startswith("2. **Inputs.**"))
        assert "**Ask it to stop at run-ready, with no run offer**" in hand_off
        offer = render(target_name, "pipelex-inputs").split("### 6. Offer the run", 1)[1].split("\n## ", 1)[0]
        conditions = offer.split("Offer only when:", 1)[1]
        assert "- no calling skill asked to stop at run-ready" in conditions

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_a_run_of_a_case_the_lab_did_not_start_is_offered_to_it(self, target_name: str) -> None:
        """Only a run on a case's inputs is offered: a run on any other inputs has no key to be scored against, and
        the lab would have to improvise one with the output already in view."""
        results = render(target_name, "pipelex-run").split("### 7. ", 1)[1].split("\n### ", 1)[0]
        assert (
            "When the inputs came from a lab case, `lab/<method>/cases/<case>/`, and the lab did not start this run, offer `/pipelex-lab`" in results
        )

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_lab_logs_a_run_it_is_handed_outside_its_rounds(self, target_name: str) -> None:
        """A run the lab is handed has already spent its credit. It is scored and logged, and it starts nothing; it
        belongs to no round, so it moves neither a series' budget nor its best round."""
        loop = the_move(render(target_name), 3)
        assert "**A run of a case that the lab did not start**, handed over by `/pipelex-run`" in loop
        assert "it starts no run and makes no fix" in loop
        log = (REPO_ROOT / "skills" / "pipelex-lab" / "references" / "log.md").read_text(encoding="utf-8")
        assert "## A run the loop did not start" in log
        assert "in no round: a series' budget, its best round and the fifth stop read only the runs of its rounds" in log

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_factory_reports_every_files_planted_facts(self, target_name: str) -> None:
        """Only a photograph's report listed its planted facts, so the key of a code-rendered file had to take them
        from a draft in the scrollback. The report now lists them for every file, and the lab's key reference reads
        them from there."""
        report = render(target_name, "pipelex-synthetic-inputs").split("### Step 6: Report", 1)[1].split("\n## ", 1)[0]
        assert "the facts planted in it, from step 3's draft" in report
        key = (REPO_ROOT / "skills" / "pipelex-lab" / "references" / "key.md").read_text(encoding="utf-8")
        assert "take them from its report, which lists them for every file" in key


class TestCapabilityMap:
    """The capability map in `frame.md` is what the lab tells a builder the platform can do, before a method exists,
    and a wrong claim there sends a design to its first run to fail — as a Word-transcript method did in the proof
    lab. So each row names a pipe that the MTHDS reference documents, and the claims that carry a limit are held to
    the reference's own words, so the two cannot drift apart."""

    MTHDS_REFERENCE = REPO_ROOT / "templates" / "skills" / "shared" / "writing-mthds.md.j2"

    def rows(self) -> list[list[str]]:
        frame = (REPO_ROOT / "skills" / "pipelex-lab" / "references" / "frame.md").read_text(encoding="utf-8")
        table = frame.split("## What the platform can do", 1)[1].split("\n## ", 1)[0]
        lines = [line for line in table.splitlines() if line.startswith("| ") and not line.startswith("| In the builder")]
        return [[cell.strip() for cell in line.strip("|").split("|")] for line in lines]

    def test_every_row_names_a_pipe_the_reference_documents(self) -> None:
        reference = self.MTHDS_REFERENCE.read_text(encoding="utf-8")
        rows = self.rows()
        assert rows, "the capability map has no rows"
        for _, pipe, _ in rows:
            name = pipe.strip("`")
            assert f"\n### {name} — " in reference, f"frame.md's {name} row names a pipe the MTHDS reference does not document"

    OFFICE_LIMIT = (
        "Word, Excel or PowerPoint file fails the run at the extraction, so a method over Office documents takes the PDF exported from them."
    )

    @pytest.mark.parametrize(
        ("claim", "anchor"),
        [
            ("It reads a PDF, an image or a web page, and nothing else.", "`PipeExtract` reads a PDF, an image or a web page, and nothing else"),
            (f"A {OFFICE_LIMIT}", f"a {OFFICE_LIMIT}"),
        ],
    )
    def test_the_extraction_limit_is_the_references_own(self, claim: str, anchor: str) -> None:
        """The limit that failed a proof-lab run, said in the words the shared reference uses."""
        reference = " ".join(self.MTHDS_REFERENCE.read_text(encoding="utf-8").split())
        assert anchor in reference, f"the MTHDS reference no longer says {anchor!r}"
        assert any(claim in row[2] for row in self.rows()), f"frame.md no longer says {claim!r}"

    def test_the_web_page_model_and_the_search_output_are_the_references(self) -> None:
        reference = self.MTHDS_REFERENCE.read_text(encoding="utf-8")
        cells = {row[0]: row[2] for row in self.rows()}
        assert "`@default-extract-web-page`" in cells["Read a web page"] and "`@default-extract-web-page`" in reference
        assert "title, a URL and a snippet" in cells["Search the web"]
        assert "`sources` list with title, URL, and snippet" in reference
