from __future__ import annotations

from pathlib import Path

import pytest

from scripts.gen_skill_docs import load_target_config, render_templates

TARGETS = ("prod", "codex", "mistral-vibe")
REPO_ROOT = Path(__file__).parents[2]
POINTER = "](../shared/file-roles.md)"


def rendered(target_name: str, skill: str) -> dict[str, str]:
    """Every file the named target renders with `skill`, keyed by its path below the target's root."""
    config = load_target_config(REPO_ROOT / "targets", target_name)
    files = render_templates(REPO_ROOT / "templates", REPO_ROOT, config.template_vars, include_skills=[skill], target_name=config.name)
    return {path.relative_to(REPO_ROOT).as_posix(): content for path, content in files.items()}


def skill_body(target_name: str, skill: str) -> str:
    return next(content for path, content in rendered(target_name, skill).items() if path.endswith(f"skills/{skill}/SKILL.md"))


def reference(target_name: str) -> str:
    return next(content for path, content in rendered(target_name, "pipelex-inputs").items() if path.endswith("skills/shared/file-roles.md"))


def section(body: str, heading: str) -> str:
    """The text under `heading`, up to the next heading of any level."""
    return body.split(f"\n{heading}\n", 1)[1].split("\n#", 1)[0]


def the_line(body: str, needle: str) -> str:
    """The one line carrying `needle`. Two of them is a duplicated rule, which is its own defect."""
    lines = [line for line in body.splitlines() if needle in line]
    assert len(lines) == 1, f"expected exactly one line containing {needle!r}, found {len(lines)}"
    return lines[0]


class TestFileRolesReference:
    @pytest.mark.parametrize("target_name", TARGETS)
    def test_it_opens_with_its_entry_condition(self, target_name: str) -> None:
        """A shared reference opens with the condition that sends the model to it: here, any file the user gives."""
        text = reference(target_name)
        assert text.startswith("# What a file the user gives is for\n\nRead this when the user gives a file")
        assert "attached to a message, named by its path or its URL, or picked from the team's files" in text, "every way a file arrives"

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_it_names_the_five_roles(self, target_name: str) -> None:
        roles = section(reference(target_name), "## The roles")
        for role in ("**A sample input**", "**A brief**", "**An example output**", "**A template**", "**Reference material**"):
            assert f"- {role} " in roles, f"{target_name}: the roles do not define {role}"
        assert "**Roles combine.**" in roles
        assert "An input sent with its expected output is a worked example" in roles

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_it_is_never_a_table_of_phrases(self, target_name: str) -> None:
        """Routing on phrases is the fault the reference corrects, so it teaches what the words do, never a lookup."""
        text = reference(target_name)
        assert not [line for line in text.splitlines() if line.startswith("|")], f"{target_name}: the reference holds a table"
        assert "Read the meaning, never a phrase alone" in text
        assert "The file's type, the weakest clue." in text

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_clues_come_strongest_first(self, target_name: str) -> None:
        clues = section(reference(target_name), "## How to tell")
        order = ["1. **The user's words.**", "2. **The file itself.**", "3. **Where the conversation stands.**", "4. **The file's type"]
        positions = [clues.index(clue) for clue in order]
        assert positions == sorted(positions), f"{target_name}: the clues are out of order"
        assert "Read every file before deciding" in clues

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_doubt_is_stated_or_asked(self, target_name: str) -> None:
        doubt = section(reference(target_name), "## When to ask")
        assert "**When the clues agree**, act on them, and state your reading in one plain line of your closing message" in doubt
        assert "**When they conflict, or when a wrong guess would change what the method takes in or gives back**, ask before" in doubt
        assert "through its question tool where it has one, and otherwise with a question that ends your reply" in doubt
        assert "**A role sticks.**" in doubt

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_each_role_says_what_it_asks_of_the_method(self, target_name: str) -> None:
        text = reference(target_name)
        asks = section(text, "## What each role asks of the method")
        assert "**The real data of an example stays out of the method.**" in asks
        assert "**A brief goes through [fit.md](fit.md).**" in asks
        assert "**A brief is not kept with the method.**" in asks
        assert "**An example output becomes a template too only when the user wants the result as that kind of file.**" in asks
        assert "It is written into the prompts when it is stable" in text and "made an input when it changes from one run to the next" in text

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_a_template_is_the_language_reference_s_to_describe(self, target_name: str) -> None:
        """What a template holds is `writing-mthds.md`'s, so the reference links its `PipeDocGen` section and repeats nothing."""
        text = reference(target_name)
        assert "](writing-mthds.md#pipedocgen--print-a-document-file)" in text
        assert "template_file" not in text

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_the_cases_contrast_and_one_is_a_question(self, target_name: str) -> None:
        cases = section(reference(target_name), "## Cases")
        for case in (
            '**A process document, with "build me this".**',
            '**A CV, with "match CVs to this job ad".**',
            '**A filled report, with "it should produce this".**',
            "**A contract, with no words.**",
        ):
            assert case in cases, f"{target_name}: the cases lack {case}"
        ambiguous = the_line(cases, "**A contract, with no words.**")
        assert "so ask before designing" in ambiguous and ambiguous.endswith('?"')

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_it_names_a_skill_as_the_target_does(self, target_name: str) -> None:
        prefix = load_target_config(REPO_ROOT / "targets", target_name).template_vars["skill_prefix"]
        assert f"`{prefix}pipelex-design`'s work" in reference(target_name)

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_design_reads_it_before_the_contract_and_at_a_re_entry(self, target_name: str) -> None:
        """The guard used to send every file the user gave to `pipelex-inputs`; now only a sample input goes there."""
        body = skill_body(target_name, "pipelex-design")
        contract = section(body, "### 1. Capture the contract")
        assert contract.strip().startswith(f"**Requirements may come as a file: read it and [file-roles.md{POINTER} before fixing the contract.**")
        assert f"[file-roles.md{POINTER} for a given file" in the_line(body, "**The baseline, before every edit**")
        guard = the_line(body, "**Never write `inputs.json`.**")
        assert "Only a sample input, or a run on real data, goes to" in guard
        assert "provides files or paths" not in body

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_edit_reads_it_before_classifying(self, target_name: str) -> None:
        classify = section(skill_body(target_name, "pipelex-edit"), "### Step 2: Classify the change")
        assert f"[file-roles.md{POINTER}, before classifying it**" in classify
        assert '"make it look like this", is an example output' in classify
        assert "the change is a contract change" in classify

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_inputs_takes_a_file_only_as_a_sample_input(self, target_name: str) -> None:
        """The strategy table picked User data on phrases such as "this file", whatever the file was for."""
        strategy = section(skill_body(target_name, "pipelex-inputs"), "### 3. The strategy")
        guard = the_line(strategy, "**A file fills an input only when its role is a sample input**")
        assert f"[file-roles.md{POINTER} before matching" in guard
        assert strategy.index(guard) < strategy.index("| Signal | Strategy |"), "the role is checked before the table picks a strategy"
        assert "| Files or folders the user gives as sample inputs |" in strategy
        for phrase in ('"this file"', '"here\'s my PDF"'):
            assert phrase not in strategy, f"{target_name}: the strategy table still routes on {phrase}"

    def test_the_user_data_inventory_leaves_other_roles_out(self) -> None:
        user_data = (REPO_ROOT / "skills" / "pipelex-inputs" / "references" / "user-data.md").read_text(encoding="utf-8")
        inventory = section(user_data, "## Inventory")
        assert "Collect every file the user has provided as a sample input" in inventory
        assert "A file given earlier as a brief, an example output, a template or reference material is left out" in inventory

    @pytest.mark.parametrize("target_name", TARGETS)
    def test_lab_reads_it_at_the_first_move(self, target_name: str) -> None:
        body = skill_body(target_name, "pipelex-lab")
        first_move = body.split("\n## 1. ", 1)[1].split("\n## ", 1)[0]
        assert f"When the user gives a file, read it and [file-roles.md{POINTER} before framing" in first_move
        assert f"- [file-roles.md{POINTER}: at the first move" in body.split("## References", 1)[1]

    def test_the_frame_reference_seeds_right_means_and_a_key_from_an_example(self) -> None:
        frame = (REPO_ROOT / "skills" / "pipelex-lab" / "references" / "frame.md").read_text(encoding="utf-8")
        files = section(frame, "## Files the user gives")
        assert "**An example output seeds Right means.**" in files
        assert "**An input given with its expected output seeds a case and its key.**" in files
        assert "never as its real names and amounts" in files
