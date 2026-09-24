from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check import check_hook_provenance


class TestHookProvenance:
    BANNER_HEAD = (
        "// check.mjs — .mthds PostToolUse hook (lint/format local via WASM, validate via Pipelex API)\n"
        "// GENERATED FILE — do not edit. Rebuild with `npm run build:hook` in pipelex-sdk-js.\n"
    )

    def _bundle(self, tmp_path: Path, provenance: str) -> Path:
        assets = tmp_path / "templates" / "hooks" / "assets"
        assets.mkdir(parents=True)
        (assets / "check.mjs").write_text(f"{self.BANNER_HEAD}{provenance}\nvar __create = Object.create;\n", encoding="utf-8")
        return tmp_path

    def test_a_bundle_built_from_published_sources_passes(self, tmp_path: Path) -> None:
        base = self._bundle(tmp_path, "// Provenance: @pipelex/sdk 0.23.0 (63e9ba5) + @pipelex/tools-wasm 0.3.0 (npm)")
        assert check_hook_provenance(base) == []

    def test_an_engine_from_a_local_checkout_is_refused(self, tmp_path: Path) -> None:
        """What `PIPELEX_TOOLS_WASM_PATH` writes: an unreleased engine no npm package holds."""
        base = self._bundle(tmp_path, "// Provenance: @pipelex/sdk 0.23.0 (63e9ba5) + @pipelex/tools-wasm 0.4.0 (local checkout 1a2b3c4)")
        errors = check_hook_provenance(base)
        assert len(errors) == 1, errors
        assert "`local checkout 1a2b3c4`, not from npm" in errors[0]
        assert "`make vendor-hook`" in errors[0]

    def test_an_unknown_sdk_commit_is_refused(self, tmp_path: Path) -> None:
        """What the build writes outside a git checkout of pipelex-sdk-js: a source no branch holds."""
        base = self._bundle(tmp_path, "// Provenance: @pipelex/sdk 0.23.0 (unknown) + @pipelex/tools-wasm 0.3.0 (npm)")
        errors = check_hook_provenance(base)
        assert len(errors) == 1, errors
        assert "the SDK commit is `unknown`, not a commit" in errors[0]

    def test_both_forgeries_are_named_at_once(self, tmp_path: Path) -> None:
        base = self._bundle(tmp_path, "// Provenance: @pipelex/sdk 0.23.0 (unknown) + @pipelex/tools-wasm 0.4.0 (local checkout unknown)")
        assert len(check_hook_provenance(base)) == 2

    @pytest.mark.parametrize(
        "line",
        [
            "var __create = Object.create;",
            "// Provenance: @pipelex/sdk 0.23.0 + @pipelex/tools-wasm 0.3.0 (npm)",
            "// Provenance: @pipelex/sdk 0.23.0 (63e9ba5) + @pipelex/tools-wasm 0.3.0",
        ],
        ids=["no-banner", "no-sdk-commit", "no-engine-origin"],
    )
    def test_a_third_line_that_is_not_a_provenance_is_refused(self, tmp_path: Path, line: str) -> None:
        errors = check_hook_provenance(self._bundle(tmp_path, line))
        assert len(errors) == 1, errors
        assert "line 3 is not the provenance line" in errors[0]

    def test_a_missing_bundle_is_refused(self, tmp_path: Path) -> None:
        errors = check_hook_provenance(tmp_path)
        assert len(errors) == 1, errors
        assert "the vendored hook bundle is missing" in errors[0]

    def test_the_vendored_bundle_passes(self) -> None:
        """The copy this repo ships, so a forged header cannot sit on `dev` behind a green unit run either."""
        assert check_hook_provenance(Path(__file__).parents[2]) == []
