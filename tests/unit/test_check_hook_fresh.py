from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from scripts.check_hook_fresh import (
    BUILD_SCRIPT,
    EXIT_CURRENT,
    EXIT_STALE,
    EXIT_UNANSWERED,
    body_findings,
    engine_findings,
    main,
    sibling_refusals,
)
from scripts.hook_bundle import Provenance, first_body_difference, read_bundle, read_provenance

TITLE = "// check.mjs — .mthds PostToolUse hook (lint/format local via WASM, validate via Pipelex API)\n"
DO_NOT_EDIT = "// GENERATED FILE — do not edit. Rebuild with `npm run build:hook` in pipelex-sdk-js.\n"
BODY = "var __create = Object.create;\nvar __defProp = Object.defineProperty;\nexport { main };\n"
# A throwaway git identity and no hooks or signing, whatever this machine's global config says.
GIT_CONFIG = ("-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null")


def _bundle(*, sdk_commit: str = "63e9ba5", tools_wasm: str = "0.3.0", body: str = BODY) -> str:
    provenance = f"// Provenance: @pipelex/sdk 0.23.0 ({sdk_commit}) + @pipelex/tools-wasm {tools_wasm} (npm)\n"
    return TITLE + DO_NOT_EDIT + provenance + body


def _provenance(bundle: str) -> Provenance:
    provenance = read_provenance(bundle)
    assert provenance is not None
    return provenance


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *GIT_CONFIG, *args], cwd=cwd, capture_output=True, text=True, check=True)


def _commit(checkout: Path, name: str) -> None:
    (checkout / name).write_text(f"{name}\n")
    _git(checkout, "add", name)
    _git(checkout, "commit", "-m", name)


class TestCheckHookFresh:
    @pytest.fixture
    def sibling(self, tmp_path: Path) -> Path:
        """A pipelex-sdk-js stand-in on `dev`, clean and level with its origin, a local bare repository, so no test reaches the network."""
        seed = tmp_path / "seed"
        (seed / BUILD_SCRIPT.parent).mkdir(parents=True)
        (seed / BUILD_SCRIPT).write_text("// build\n")
        _git(tmp_path, "init", "--quiet", "-b", "dev", str(seed))
        _git(seed, "add", ".")
        _git(seed, "commit", "-m", "seed")
        _git(tmp_path, "clone", "--quiet", "--bare", str(seed), str(tmp_path / "origin.git"))
        _git(tmp_path, "clone", "--quiet", str(tmp_path / "origin.git"), str(tmp_path / "pipelex-sdk-js"))
        return tmp_path / "pipelex-sdk-js"

    def _run_gate(self, mocker: MockerFixture, tmp_path: Path, *, vendored: str, rebuilt: str, latest: str, refusals: list[str] | None = None) -> int:
        """The gate's wiring, with the sibling's state, npm and the rebuild replaced."""
        bundle = tmp_path / "check.mjs"
        bundle.write_text(vendored, encoding="utf-8")
        mocker.patch("scripts.check_hook_fresh.sibling_refusals", return_value=refusals or [])
        mocker.patch("scripts.check_hook_fresh.npm_latest_version", return_value=latest)
        mocker.patch("scripts.check_hook_fresh.rebuild_bundle", return_value=rebuilt)
        return main(["--sdk-js-dir", str(tmp_path), "--bundle", str(bundle)])

    # The comparison below the banner.

    def test_identical_bodies_pass_whatever_the_banner_says(self) -> None:
        """The banner names the SDK commit, which moves with commits that never touch the hook."""
        assert first_body_difference(_bundle(sdk_commit="63e9ba5"), _bundle(sdk_commit="72480d1")) is None

    @pytest.mark.parametrize(
        ("rebuilt_body", "line"),
        [
            (BODY.replace("Object.defineProperty", "Object.definePropertY"), 5),
            (BODY + "export { other };\n", 7),
            (BODY.rstrip("\n"), 6),
        ],
        ids=["one-byte", "line-added-at-the-end", "final-newline-dropped"],
    )
    def test_a_body_difference_is_caught_at_its_line(self, rebuilt_body: str, line: int) -> None:
        assert first_body_difference(_bundle(), _bundle(body=rebuilt_body)) == line

    def test_the_bundle_is_read_without_newline_translation(self, tmp_path: Path) -> None:
        """`read_text` would turn CRLF into LF and hide the one difference a byte comparison exists for."""
        path = tmp_path / "check.mjs"
        path.write_bytes(_bundle().replace("\n", "\r\n").encode("utf-8"))
        assert first_body_difference(_bundle(), read_bundle(path)) == 4

    # Question 1: the engine against npm's latest.

    def test_the_latest_engine_passes(self) -> None:
        assert engine_findings(_provenance(_bundle()), _provenance(_bundle()), "0.3.0") == []

    def test_an_engine_behind_a_current_sdk_pin_asks_for_a_re_vendor(self) -> None:
        findings = engine_findings(_provenance(_bundle(tools_wasm="0.1.0")), _provenance(_bundle(tools_wasm="0.3.0")), "0.3.0")
        assert len(findings) == 1
        assert "embeds @pipelex/tools-wasm 0.1.0, and npm's latest is 0.3.0" in findings[0]
        assert "already builds with 0.3.0" in findings[0]
        assert "`make vendor-hook`, then `make build`" in findings[0]

    def test_an_engine_behind_the_sdk_pin_asks_for_the_pin_first(self) -> None:
        findings = engine_findings(_provenance(_bundle(tools_wasm="0.3.0")), _provenance(_bundle(tools_wasm="0.3.0")), "0.4.0")
        assert len(findings) == 1
        assert "pipelex-sdk-js pins 0.3.0" in findings[0]
        assert "npm install --save-dev --save-exact @pipelex/tools-wasm@0.4.0" in findings[0]

    # Question 2: whether re-vendoring would change the bundle.

    def test_identical_bodies_find_nothing(self) -> None:
        assert body_findings(_bundle(), _bundle(sdk_commit="72480d1")) == []

    def test_a_difference_quotes_both_provenance_lines_and_the_cure(self) -> None:
        findings = body_findings(_bundle(tools_wasm="0.1.0"), _bundle(sdk_commit="72480d1", body=BODY + "export { other };\n"))
        assert len(findings) == 1
        assert "from line 7 on" in findings[0]
        assert "vendored: // Provenance: @pipelex/sdk 0.23.0 (63e9ba5) + @pipelex/tools-wasm 0.1.0 (npm)" in findings[0]
        assert "rebuilt:  // Provenance: @pipelex/sdk 0.23.0 (72480d1) + @pipelex/tools-wasm 0.3.0 (npm)" in findings[0]
        assert "`make vendor-hook`, then `make build`" in findings[0]

    # The sibling checkout the rebuild runs in.

    def test_a_clean_checkout_level_with_origin_can_stand_for_a_re_vendor(self, sibling: Path) -> None:
        assert sibling_refusals(sibling) == []

    def test_a_directory_without_the_build_script_is_refused(self, tmp_path: Path) -> None:
        refusals = sibling_refusals(tmp_path)
        assert len(refusals) == 1
        assert "is not a pipelex-sdk-js checkout" in refusals[0]

    def test_a_checkout_off_its_base_is_refused(self, sibling: Path) -> None:
        _git(sibling, "checkout", "--quiet", "-b", "feature/Other")
        refusals = sibling_refusals(sibling)
        assert len(refusals) == 1
        assert "is on feature/Other, not on its base dev" in refusals[0]

    def test_a_checkout_with_uncommitted_changes_is_refused(self, sibling: Path) -> None:
        (sibling / "scratch.ts").write_text("export {};\n")
        refusals = sibling_refusals(sibling)
        assert len(refusals) == 1
        assert "has uncommitted changes" in refusals[0]
        assert "scratch.ts" in refusals[0]

    def test_a_checkout_behind_origin_is_refused_with_the_fast_forward(self, sibling: Path, tmp_path: Path) -> None:
        """A checkout behind origin would rebuild an old hook and pass a bundle `dev` has moved past."""
        other = tmp_path / "other"
        _git(tmp_path, "clone", "--quiet", str(tmp_path / "origin.git"), str(other))
        _commit(other, "moved.ts")
        _git(other, "push", "--quiet", "origin", "dev")
        refusals = sibling_refusals(sibling)
        assert len(refusals) == 1
        assert "is behind origin/dev" in refusals[0]
        assert "pull --ff-only origin dev" in refusals[0]

    def test_a_checkout_ahead_of_origin_is_refused(self, sibling: Path) -> None:
        _commit(sibling, "unpushed.ts")
        refusals = sibling_refusals(sibling)
        assert len(refusals) == 1
        assert "holds commits origin/dev does not" in refusals[0]

    # The gate end to end, offline.

    def test_a_current_bundle_passes(self, mocker: MockerFixture, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = self._run_gate(mocker, tmp_path, vendored=_bundle(), rebuilt=_bundle(sdk_commit="72480d1"), latest="0.3.0")
        assert exit_code == EXIT_CURRENT
        assert "The vendored hook bundle is current." in capsys.readouterr().out

    def test_a_stale_bundle_fails_on_both_questions_in_one_run(
        self, mocker: MockerFixture, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = self._run_gate(
            mocker,
            tmp_path,
            vendored=_bundle(tools_wasm="0.1.0", body=BODY + "// old engine\n"),
            rebuilt=_bundle(tools_wasm="0.3.0"),
            latest="0.3.0",
        )
        output = capsys.readouterr().out
        assert exit_code == EXIT_STALE
        assert output.count("STALE:") == 2, output
        assert "FAIL: The vendored hook bundle is behind its sources." in output

    def test_a_refused_sibling_answers_nothing(self, mocker: MockerFixture, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = self._run_gate(mocker, tmp_path, vendored=_bundle(), rebuilt=_bundle(), latest="0.3.0", refusals=["the checkout is dirty"])
        output = capsys.readouterr().out
        assert exit_code == EXIT_UNANSWERED
        assert "REFUSED: the checkout is dirty" in output
        assert "STALE" not in output

    def test_a_bundle_without_a_provenance_answers_nothing(self, mocker: MockerFixture, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = self._run_gate(mocker, tmp_path, vendored=BODY, rebuilt=_bundle(), latest="0.3.0")
        assert exit_code == EXIT_UNANSWERED
        assert "carries no provenance line" in capsys.readouterr().out
