"""The edit hook's offline stages, swept over every entry of the MTHDS Test Corpus.

The hook blocks an edit on any lint diagnostic, and its lint embeds the MTHDS JSON Schema frozen
into the vendored `check.mjs` when the bundle was built. A bundle built before a language feature
therefore refuses that feature to every builder, which is how the expanded input slot and intent
hints came to be refused while the hosted validator accepted them. This suite is the gate that
catches it: `tests/data/mthds-corpus/` is a vendored copy of the whole corpus, written by the
workspace's corpus sync and never edited here, and every entry in it is run through the hook.

The rule is the corpus contract's (`docs/specs/mthds-test-corpus.md` in the workspace, "`fails_at`"):
an entry blocks exactly when its `error.*` tag has `fails_at = "schema"` in the vendored
`vocabulary.toml`, and every other entry passes silently. The suite never branches on `validity`,
and it keeps no list of entries or faults of its own, so a newly synced entry is swept with no change
here. It runs `templates/hooks/assets/check.mjs`, the copy every target carries byte for byte, on a
copy of each entry in a temporary directory, because the format stage writes back in place, and with
the Pipelex credentials stripped, so the validate stage never runs and the sweep stays offline.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any, NamedTuple

import pytest

REPO_ROOT = Path(__file__).parents[2]
CHECK_MJS = REPO_ROOT / "templates" / "hooks" / "assets" / "check.mjs"
CORPUS = REPO_ROOT / "tests" / "data" / "mthds-corpus"
ENTRIES = CORPUS / "entries"
VOCABULARY = CORPUS / "vocabulary.toml"
MANIFEST_NAME = "entry.toml"

# What reaches the validate stage, and so the network: the shell's credentials, and on Claude the
# plugin options the wrapper would promote to them.
CREDENTIAL_PREFIXES = ("PIPELEX_", "CLAUDE_PLUGIN_OPTION_")
# The category the lint renders a schema diagnostic under, the same word as `fails_at = "schema"`.
SCHEMA_DIAGNOSTIC = "[schema/"
HOOK_TIMEOUT_SECONDS = 60


class HookVerdict(NamedTuple):
    method: str
    blocked: bool
    reason: str
    stdout: str
    stderr: str


def _schema_fault_tags() -> frozenset[str]:
    vocabulary: dict[str, Any] = tomllib.loads(VOCABULARY.read_text(encoding="utf-8"))
    errors: dict[str, dict[str, Any]] = vocabulary.get("error", {})
    return frozenset(f"error.{name}" for name, spec in errors.items() if spec.get("fails_at") == "schema")


def _entry_directories() -> list[Path]:
    """Every entry, found by recursion over the vendored tree rather than read from a list."""
    if not ENTRIES.is_dir():
        return []
    return sorted(manifest.parent for manifest in ENTRIES.rglob(MANIFEST_NAME))


def _covers(entry: Path) -> frozenset[str]:
    manifest: dict[str, Any] = tomllib.loads((entry / MANIFEST_NAME).read_text(encoding="utf-8"))
    return frozenset(manifest["covers"])


def _expects_block(entry: Path) -> bool:
    return bool(_schema_fault_tags() & _covers(entry))


@pytest.fixture(scope="module")
def node() -> str:
    """The `node` the hook runs on. Skipped without one on a developer machine, never in CI.

    A gate that skips in CI is a green light for nothing, so under `CI` a missing `node` is a failure
    and `tests.yml` installs one.
    """
    found = shutil.which("node")
    if found is None:
        if os.environ.get("CI"):
            pytest.fail("no node on the PATH under CI: the hook corpus sweep must run there, and tests.yml installs Node for it")
        pytest.skip("no node on the PATH")
    return found


@pytest.fixture(scope="module")
def offline_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if not key.startswith(CREDENTIAL_PREFIXES)}


def run_hook(*, node: str, method: Path, environment: dict[str, str]) -> HookVerdict:
    """One PostToolUse `Write` of `method`, as Claude Code hands it to the hook."""
    payload = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": str(method)}})
    result = subprocess.run(
        [node, str(CHECK_MJS), "--platform=claude"],
        input=payload,
        capture_output=True,
        text=True,
        env=environment,
        timeout=HOOK_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, f"{method.name}: the hook exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    blocked = False
    reason = ""
    if result.stdout.strip():
        decision: dict[str, Any] = json.loads(result.stdout)
        blocked = decision.get("decision") == "block"
        reason = str(decision.get("reason", ""))
    return HookVerdict(method=method.name, blocked=blocked, reason=reason, stdout=result.stdout, stderr=result.stderr)


class TestHookCorpus:
    def test_the_vendored_corpus_holds_entries(self) -> None:
        assert VOCABULARY.is_file(), f"no {VOCABULARY.relative_to(REPO_ROOT)}: the corpus copy is missing, re-run the workspace's corpus sync"
        assert _entry_directories(), f"no entry under {ENTRIES.relative_to(REPO_ROOT)}: the sweep below would pass having run nothing"

    def test_every_entry_holds_a_method(self) -> None:
        empty = [entry.name for entry in _entry_directories() if not any(entry.rglob("*.mthds"))]
        assert not empty, f"entries with no .mthds file, which the sweep would pass without running the hook: {empty}"

    def test_both_verdicts_are_exercised(self) -> None:
        """The vocabulary declares a schema fault, and the corpus holds entries on both sides of it.

        Without a schema-fault entry the sweep only ever expects a pass, and a hook whose schema
        quietly stopped rejecting something would go unnoticed.
        """
        assert _schema_fault_tags(), 'the vocabulary declares no `fails_at = "schema"` tag, so no entry is expected to block'
        expectations = {_expects_block(entry) for entry in _entry_directories()}
        assert expectations == {True, False}, f"every entry expects the same verdict ({expectations}), so one branch of the sweep is never run"

    @pytest.mark.parametrize("entry", _entry_directories(), ids=lambda entry: entry.name)
    def test_the_hook_blocks_exactly_the_schema_faults(self, entry: Path, node: str, offline_environment: dict[str, str], tmp_path: Path) -> None:
        """A schema-fault entry blocks with a schema diagnostic; any other entry passes with nothing said."""
        copy = tmp_path / entry.name
        shutil.copytree(entry, copy)
        verdicts = [run_hook(node=node, method=method, environment=offline_environment) for method in sorted(copy.rglob("*.mthds"))]

        if _expects_block(entry):
            schema_blocks = [verdict for verdict in verdicts if verdict.blocked and SCHEMA_DIAGNOSTIC in verdict.reason]
            assert schema_blocks, (
                f"{entry.name} covers a fault the schema catches ({sorted(_schema_fault_tags() & _covers(entry))}), "
                f"but the hook raised no schema diagnostic on it: {[(verdict.method, verdict.reason or 'pass') for verdict in verdicts]}"
            )
        else:
            refused = [
                (verdict.method, verdict.reason or verdict.stdout, verdict.stderr)
                for verdict in verdicts
                if verdict.stdout.strip() or verdict.stderr.strip()
            ]
            assert not refused, f"{entry.name} is a form the schema allows, but the hook did not pass it silently: {refused}"
