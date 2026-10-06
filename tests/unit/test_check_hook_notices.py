from __future__ import annotations

from pathlib import Path

from scripts.check import check_hook_notices
from scripts.hook_bundle import inlined_packages


class TestHookNotices:
    BUNDLE = (
        "// check.mjs — .mthds PostToolUse hook\n"
        "var __create = Object.create;\n"
        "// node_modules/@pipelex/tools-wasm/dist/index.js\n"
        "var engine = {};\n"
        "// ../node_modules/mthds/dist/client.js\n"
        "var client = {};\n"
        "// src/hooks/check.ts\n"
        "var hook = {};\n"
    )

    def _assets(self, tmp_path: Path, bundle: str, notices: str | None) -> Path:
        assets = tmp_path / "templates" / "hooks" / "assets"
        assets.mkdir(parents=True)
        (assets / "check.mjs").write_text(bundle, encoding="utf-8")
        if notices is not None:
            (assets / "THIRD-PARTY-NOTICES.md").write_text(notices, encoding="utf-8")
        return tmp_path

    def test_inlined_packages_are_read_from_esbuild_module_comments(self) -> None:
        """Scoped and unscoped packages, at any depth of `node_modules`; the bundle's own `src/` is not a package."""
        assert inlined_packages(self.BUNDLE) == {"@pipelex/tools-wasm", "mthds"}

    def test_a_notice_naming_every_package_passes(self, tmp_path: Path) -> None:
        base = self._assets(tmp_path, self.BUNDLE, "- `mthds`\n- `@pipelex/tools-wasm`\n")
        assert check_hook_notices(base) == []

    def test_a_package_the_notice_does_not_name_is_refused(self, tmp_path: Path) -> None:
        """What a re-vendor that brings in a new dependency produces."""
        base = self._assets(tmp_path, self.BUNDLE + "// node_modules/yaml/dist/index.js\nvar yaml = {};\n", "- `mthds`\n- `@pipelex/tools-wasm`\n")
        errors = check_hook_notices(base)
        assert len(errors) == 1, errors
        assert "`yaml` is inlined into check.mjs but not named here" in errors[0]

    def test_a_missing_notices_file_is_refused(self, tmp_path: Path) -> None:
        errors = check_hook_notices(self._assets(tmp_path, self.BUNDLE, None))
        assert len(errors) == 1, errors
        assert "THIRD-PARTY-NOTICES.md: missing" in errors[0]

    def test_a_missing_bundle_is_left_to_the_provenance_check(self, tmp_path: Path) -> None:
        assert check_hook_notices(tmp_path) == []

    def test_the_vendored_bundle_and_its_notice_pass(self) -> None:
        """The copies this repo ships, so a re-vendor cannot land a package with no notice behind a green unit run."""
        repo = Path(__file__).parents[2]
        assert inlined_packages((repo / "templates" / "hooks" / "assets" / "check.mjs").read_text(encoding="utf-8"))
        assert check_hook_notices(repo) == []
