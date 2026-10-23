"""The edit hook's validate stage sends the method's tree, the tree a run of the method would send.

The vendored `check.mjs` validates the edited file's method as the MTHDS protocol's `files` map: the edited file's
directory listed by the `mthds` package's lister under the standard's membership rule, rooted at the nearest
`METHODS.toml` at or above it, so every file the rule keeps travels at its tree path, every bundle of the method and
every file a step reads, such as the template a `PipeDocGen` step names in `template_file`, among them, while names
starting with a dot, a run's inputs file and what a `.gitignore` inside the tree or the manifest's `exclude` keeps out
stay home. A `.gitignore` above the tree root keeps nothing out. Before anything is sent, the hook screens every file
for secrets: one named like a key or credentials file, or holding a well-known key format, stays home under a note,
and a bundle or manifest that looks like a secret sends nothing. These tests run `templates/hooks/assets/check.mjs`,
the copy every target carries byte for byte, as a Claude `PostToolUse` `Write`, against a stand-in API on a loopback
port (`stub_api` in `conftest.py`, run by `run_write_hook` in `stub_api.py`), and read what the validate stage sent.
The stand-in answers the version handshake as a runner keeping no blob store, so the tree always travels inline and
every file sent is in the request's body. The key they give the hook is a placeholder the stand-in never checks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.unit.stub_api import StubApiServer, run_write_hook

TEMPLATE_FILE = "templates/notice.html"
TEMPLATE_HTML = "<h1>$notice.shop_name</h1>\n<p>Weekdays: $notice.weekdays</p>\n<p>Weekend: $notice.weekend</p>\n"
GRAPH_PAGE = "<html><body>the graph page</body></html>\n"
NOTICE_METHOD = f"""domain      = "shop_notices"
description = "Printing the notice a shop tapes to its door"
main_pipe   = "print_notice"

[concept.OpeningNotice]
description = "What a shop wants passers-by to know about its opening hours"

[concept.OpeningNotice.structure]
shop_name = {{ type = "text", description = "The name painted above the shop's door", required = true }}
weekdays  = {{ type = "text", description = "The opening hours from Monday to Friday", required = true }}
weekend   = {{ type = "text", description = "The opening hours on Saturday and Sunday", required = true }}

[concept.PrintedNotice]
description = "The notice laid out as a page to print and tape to the door"
refines     = "Document"

[pipe.print_notice]
type          = "PipeDocGen"
description   = "Prints the opening hours from the shop's template"
inputs        = {{ notice = "OpeningNotice" }}
output        = "PrintedNotice"
format        = "pdf"
template_file = "{TEMPLATE_FILE}"
"""
# A second file whose step names the same path, which leads from its own directory to a different file.
BACK_DOOR_METHOD = (
    NOTICE_METHOD.replace('domain      = "shop_notices"', 'domain      = "shop_back_door"')
    .replace('main_pipe   = "print_notice"', 'main_pipe   = "print_back_notice"')
    .replace("[pipe.print_notice]", "[pipe.print_back_notice]")
)
BACK_DOOR_HTML = TEMPLATE_HTML.replace("Weekdays", "Back door, weekdays")
MANIFEST = '[package]\naddress = "github.com/acme/shop-notices"\nversion = "0.1.0"\ndescription = "The notices a shop tapes to its doors"\n'
# What `/pipelex-inputs` leaves beside a local bundle: the user's document copied under `inputs/`, the `inputs.json`
# naming it, and the run-ready `inputs.prepared.json` that step 5 writes. The document is a stand-in for a scanned
# lease, its bytes not UTF-8 text, as a real PDF's are not.
COPIED_DOCUMENT = "inputs/lease.pdf"
COPIED_DOCUMENT_BYTES = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"
INPUTS_JSON = '{"notice": {"shop_name": "The shop on the lease", "weekdays": "9-18", "weekend": "closed"}, "lease": "inputs/lease.pdf"}\n'
PREPARED_INPUTS = '{"notice": {"shop_name": "The shop on the lease", "weekdays": "9-18", "weekend": "closed"}, "lease": {"url": "pipelex-storage://user/assets/1.pdf"}}\n'
# The marks both skills write: `*` in the `inputs/` folder's own `.gitignore`, and an anchored line in the bundle
# directory's `.gitignore`, which is always inside the tree root, unlike the repository's own above it.
INPUTS_MARK = "*\n"
PREPARED_MARK = "/inputs.prepared.json\n"
# An invalid verdict, its fault a problem item, as a runner speaking the problem document answers it.
INVALID_VERDICT: dict[str, Any] = {
    "is_valid": False,
    "errors": [
        {
            "code": "method.template_invalid",
            "detail": "The stand-in refuses every bundle it is sent.",
            "params": {"pipe": "print_notice", "template": TEMPLATE_FILE, "finding": "refused by the stand-in"},
            "location": {"pipe": "print_notice", "file": "notice.mthds"},
        }
    ],
    "pending_signatures": [],
    "is_runnable": False,
    "message": "The method does not validate.",
    "rendered_markdown": "# Validation failed\n\nRefused by the stand-in.",
}


def _write_bundle(bundle: Path) -> Path:
    """The notice bundle with its template beside it, and the graph page a validation leaves there, which no step names."""
    (bundle / "templates").mkdir(parents=True)
    method = bundle / "notice.mthds"
    method.write_text(NOTICE_METHOD, encoding="utf-8")
    (bundle / TEMPLATE_FILE).write_text(TEMPLATE_HTML, encoding="utf-8")
    (bundle / "method-graph.html").write_text(GRAPH_PAGE, encoding="utf-8")
    return method


def _fake_pem_block(label: str) -> str:
    """A PEM block of `label`, its body one repeated Base64 character as long as a key's lines, assembled at run time
    so that no literal in the repository looks like a key to a scanner reading it. It is no key, but the hook's secret
    guard finds it as it finds one, as the SDK's own suites build theirs."""
    return "\n".join(["".join(["-----BEGIN ", label, "-----"]), "M" * 64, "Q" * 40, "".join(["-----END ", label, "-----"])]) + "\n"


def _fake_service_account_export() -> str:
    """A cloud console's service-account export, its private key a fake PEM block written into JSON as such exports are."""
    return json.dumps({"type": "service_account", "project_id": "acme-notices", "private_key": _fake_pem_block("PRIVATE KEY")}) + "\n"


def _sent_tree(stub_api: StubApiServer) -> dict[str, Any]:
    """The `files` map of the one validation the hook sent, after the version handshake that precedes it."""
    assert stub_api.routes == ["GET /v1/version", "POST /v1/validate"]
    body = stub_api.recorded[1].body
    assert "mthds_contents" not in body, "the method travels as its tree, never as the retired list of bundle texts"
    assert "resources" not in body, "a file a step reads rides the tree, never the retired `resources` map"
    files: dict[str, Any] = body["files"]
    return files


class TestHookMethodTree:
    def test_a_templated_bundle_is_sent_as_its_tree(self, node: str, stub_api: StubApiServer, tmp_path: Path) -> None:
        """Every file of the directory travels at its tree path: the bundle, the template its step names, and the graph page."""
        method = _write_bundle(tmp_path / "bundle")

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        assert result.stdout.strip() == "", f"a valid verdict passes silently, but the hook said: {result.stdout}"
        assert _sent_tree(stub_api) == {
            "notice.mthds": method.read_text(encoding="utf-8"),
            TEMPLATE_FILE: TEMPLATE_HTML,
            "method-graph.html": GRAPH_PAGE,
        }
        assert "markdown" in stub_api.recorded[1].body["render"], "the hook must ask for the Markdown it forwards"

    def test_the_tree_is_rooted_at_the_manifest_and_leaves_inputs_hidden_and_ignored_files_home(
        self, node: str, stub_api: StubApiServer, tmp_path: Path
    ) -> None:
        """An edit in a package's subdirectory sends the whole package, and the membership rule keeps out what never travels."""
        package = tmp_path / "package"
        method = _write_bundle(package / "notices")
        (package / "METHODS.toml").write_text(MANIFEST, encoding="utf-8")
        (package / ".gitignore").write_text("scratch.txt\n", encoding="utf-8")
        (package / "notices" / "inputs.json").write_text('{"notice": {"shop_name": "A shop with a secret"}}\n', encoding="utf-8")
        (package / "notices" / ".env").write_text("SHOP_KEY=never-sent\n", encoding="utf-8")
        (package / "notices" / "scratch.txt").write_text("kept out by the .gitignore\n", encoding="utf-8")

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        assert result.stdout.strip() == "", f"a valid verdict passes silently, but the hook said: {result.stdout}"
        assert sorted(_sent_tree(stub_api)) == [
            "METHODS.toml",
            "notices/method-graph.html",
            "notices/notice.mthds",
            f"notices/{TEMPLATE_FILE}",
        ]

    def test_a_manifest_holding_a_secret_sends_nothing_and_says_so(self, node: str, stub_api: StubApiServer, tmp_path: Path) -> None:
        """Every validation reads the method's bundles and its manifest, so a tree without one is not the method: when
        either looks like a secret, the hook sends nothing at all, not even the version handshake, and a non-blocking
        note names the tree and the file in place of a verdict."""
        package = tmp_path / "package"
        method = _write_bundle(package / "notices")
        description = _fake_pem_block("PRIVATE KEY").replace("\n", "\\n")
        (package / "METHODS.toml").write_text(
            MANIFEST.replace('description = "The notices a shop tapes to its doors"', f'description = "{description}"'), encoding="utf-8"
        )

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        assert stub_api.routes == [], "a tree whose manifest looks like a secret must not reach the API"
        output: dict[str, Any] = json.loads(result.stdout)
        assert "decision" not in output, f"a validation the hook did not send must not block: {output}"
        note: str = output["hookSpecificOutput"]["additionalContext"]
        assert "The .mthds hook did not validate the method at" in note, note
        assert "METHODS.toml" in note and "M" * 40 not in note, note

    def test_secret_files_stay_home_while_a_gitignore_above_the_tree_still_keeps_nothing_out(
        self, node: str, stub_api: StubApiServer, tmp_path: Path
    ) -> None:
        """What `docs/hooks.md` and the README say leaves the machine. The hook screens every file of the tree before it
        sends anything, so a file named like a secret file or holding a well-known key format stays home, and the
        verdict comes with a note naming it, never quoting it. The lister still reads only the `.gitignore` files
        inside the tree, so a repository's root `.gitignore` above a bundle with no manifest keeps nothing out: a file
        it lists that holds no secret travels with the method."""
        repository = tmp_path / "repository"
        (repository / ".git").mkdir(parents=True)
        (repository / ".gitignore").write_text("*.pem\ncredentials.json\nservice-account.json\nscratch.txt\n", encoding="utf-8")
        bundle = repository / "methods" / "notices"
        method = _write_bundle(bundle)
        (bundle / "key.pem").write_text(_fake_pem_block("PRIVATE KEY"), encoding="utf-8")
        (bundle / "credentials.json").write_text("{}\n", encoding="utf-8")
        (bundle / "service-account.json").write_text(_fake_service_account_export(), encoding="utf-8")
        (bundle / "scratch.txt").write_text("a draft the repository ignores and that holds no secret\n", encoding="utf-8")

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        assert sorted(_sent_tree(stub_api)) == ["method-graph.html", "notice.mthds", "scratch.txt", TEMPLATE_FILE]
        # A valid verdict still passes: the note rides as context for the agent, never as a block.
        output: dict[str, Any] = json.loads(result.stdout)
        assert "decision" not in output, f"a valid verdict reached without the secret files must not block: {output}"
        note: str = output["hookSpecificOutput"]["additionalContext"]
        assert "The .mthds hook kept these files of the method's tree on this machine" in note, note
        for kept_home in ("key.pem", "credentials.json", "service-account.json"):
            assert kept_home in note, f"the note does not name {kept_home}: {note}"
        assert "scratch.txt" not in note, "a file holding no secret is never named as one"
        assert "M" * 40 not in note, "the note must never quote what a file holds"

    @pytest.mark.parametrize(
        ("marked", "expected_tree"),
        [
            pytest.param(False, ["inputs.prepared.json", COPIED_DOCUMENT, "method-graph.html", "notice.mthds", TEMPLATE_FILE], id="unmarked"),
            pytest.param(True, ["method-graph.html", "notice.mthds", TEMPLATE_FILE], id="marked"),
        ],
    )
    def test_the_inputs_beside_a_bundle_stay_home_once_marked(
        self, node: str, stub_api: StubApiServer, tmp_path: Path, marked: bool, expected_tree: list[str]
    ) -> None:
        """`L-261022-b695eb`: `/pipelex-inputs` copies the user's documents into `inputs/` beside a local bundle and
        writes `inputs.prepared.json` there, and the membership rule keeps out only `inputs.json`, so unmarked both
        travel with every validation, run and save of the method. The repository's own `.gitignore`, which the
        ignore guard used to write their entries into, sits above the tree root and keeps nothing out. The two marks
        the skills now write, `*` in `inputs/.gitignore` and `/inputs.prepared.json` in the bundle directory's
        `.gitignore`, are read by the lister itself, so the tree carries neither, while the method's own files still
        travel, a dot file being out of the tree by its name."""
        repository = tmp_path / "repository"
        (repository / ".git").mkdir(parents=True)
        (repository / ".gitignore").write_text("methods/notices/inputs/\nmethods/notices/inputs.prepared.json\n", encoding="utf-8")
        bundle = repository / "methods" / "notices"
        method = _write_bundle(bundle)
        (bundle / "inputs").mkdir()
        (bundle / COPIED_DOCUMENT).write_bytes(COPIED_DOCUMENT_BYTES)
        (bundle / "inputs.json").write_text(INPUTS_JSON, encoding="utf-8")
        (bundle / "inputs.prepared.json").write_text(PREPARED_INPUTS, encoding="utf-8")
        if marked:
            (bundle / "inputs" / ".gitignore").write_text(INPUTS_MARK, encoding="utf-8")
            (bundle / ".gitignore").write_text(PREPARED_MARK, encoding="utf-8")

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        assert result.stdout.strip() == "", f"a valid verdict passes silently, but the hook said: {result.stdout}"
        assert sorted(_sent_tree(stub_api)) == sorted(expected_tree)

    def test_two_steps_naming_one_path_each_send_their_own_file(self, node: str, stub_api: StubApiServer, tmp_path: Path) -> None:
        """A path two files of the bundle name leads to a different file from each, and the tree carries both."""
        stub_api.verdict = INVALID_VERDICT
        bundle = tmp_path / "bundle"
        method = _write_bundle(bundle)
        back_door = bundle / "back-door"
        (back_door / "templates").mkdir(parents=True)
        (back_door / "back-door.mthds").write_text(BACK_DOOR_METHOD, encoding="utf-8")
        (back_door / TEMPLATE_FILE).write_text(BACK_DOOR_HTML, encoding="utf-8")

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        files = _sent_tree(stub_api)
        assert files[TEMPLATE_FILE] == TEMPLATE_HTML
        assert files[f"back-door/{TEMPLATE_FILE}"] == BACK_DOOR_HTML
        assert result.stdout.strip() == '{"decision":"block","reason":"# Validation failed\\n\\nRefused by the stand-in."}'

    def test_a_tree_holding_a_symbolic_link_passes_the_validation_stage_silently(self, node: str, stub_api: StubApiServer, tmp_path: Path) -> None:
        """The standard's lister refuses a tree holding a link, so no request leaves and a stand-in refusing everything never blocks."""
        stub_api.verdict = INVALID_VERDICT
        bundle = tmp_path / "bundle"
        method = _write_bundle(bundle)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        outside = elsewhere / "notice.html"
        outside.write_text(TEMPLATE_HTML, encoding="utf-8")
        (bundle / TEMPLATE_FILE).unlink()
        (bundle / TEMPLATE_FILE).symlink_to(outside)

        result = run_write_hook(node=node, method=method, stub_api=stub_api)

        assert stub_api.recorded == [], f"the hook sent a tree the standard refuses: {stub_api.routes}"
        assert result.stdout.strip() == "", f"the validation stage should pass silently, but the hook said: {result.stdout}"
