"""The vendored hook bundle: what its banner says it was built from, and the code below the banner.

`templates/hooks/assets/check.mjs` is built in `pipelex-sdk-js` by `npm run build:hook`, whose
`scripts/build-hook.mjs` writes a three-line comment banner above the bundled code. The third line
names the sources the bundle was built from:

    // Provenance: @pipelex/sdk 0.23.0 (63e9ba5) + @pipelex/tools-wasm 0.3.0 (npm)

Two guards read it. `scripts/check.py` refuses, offline and in CI, a provenance that no published
source can reproduce. `scripts/check_hook_fresh.py`, the release gate, compares the vendored engine
with npm's latest and the code below the banner with a fresh build in the sibling checkout.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

HOOK_BUNDLE_PATH = Path("templates") / "hooks" / "assets" / "check.mjs"
# The banner `scripts/build-hook.mjs` writes: a title, the do-not-edit line, then the provenance.
BANNER_LINE_COUNT = 3
PROVENANCE_PATTERN = re.compile(
    r"^// Provenance: @pipelex/sdk (?P<sdk_version>\S+) \((?P<sdk_commit>[^)]+)\)"
    r" \+ @pipelex/tools-wasm (?P<tools_wasm_version>\S+) \((?P<tools_wasm_origin>[^)]+)\)$"
)
# The engine origin the build writes when it bundled the npm devDependency. Anything else is
# `local checkout <sha>`, which `PIPELEX_TOOLS_WASM_PATH` produces from an unreleased engine build.
NPM_ORIGIN = "npm"
# `git rev-parse --short HEAD`, which `core.abbrev` can shorten to four characters, up to a full
# SHA-256 object name. Outside a git checkout the build writes `unknown` instead.
COMMIT_PATTERN = re.compile(r"[0-9a-f]{4,64}")


class Provenance(NamedTuple):
    sdk_version: str
    sdk_commit: str
    tools_wasm_version: str
    tools_wasm_origin: str


def read_provenance(bundle: str) -> Provenance | None:
    """The provenance line of a bundle's banner, or None when the banner's third line is not one."""
    lines = bundle.splitlines()
    if len(lines) < BANNER_LINE_COUNT:
        return None
    match = PROVENANCE_PATTERN.match(lines[BANNER_LINE_COUNT - 1])
    if match is None:
        return None
    return Provenance(**match.groupdict())


def provenance_line(bundle: str) -> str:
    """The banner's third line as written, for a message that has to quote it."""
    lines = bundle.splitlines()
    return lines[BANNER_LINE_COUNT - 1] if len(lines) >= BANNER_LINE_COUNT else ""


def unpublished_sources(provenance: Provenance) -> list[str]:
    """What in a provenance no published source can reproduce, one sentence per problem."""
    problems: list[str] = []
    if provenance.tools_wasm_origin != NPM_ORIGIN:
        problems.append(
            f"the engine is @pipelex/tools-wasm {provenance.tools_wasm_version} from `{provenance.tools_wasm_origin}`, not from npm: "
            "an engine built with PIPELEX_TOOLS_WASM_PATH is unreleased, and no published package holds it"
        )
    if COMMIT_PATTERN.fullmatch(provenance.sdk_commit) is None:
        problems.append(
            f"the SDK commit is `{provenance.sdk_commit}`, not a commit: the bundle was built outside a git checkout of pipelex-sdk-js, "
            "so no branch holds the source it was built from"
        )
    return problems


def bundle_body(bundle: str) -> str:
    """Everything below the banner: the code a rebuild of the same sources reproduces.

    The banner names the SDK commit, which moves with every commit to `pipelex-sdk-js`, including
    the ones that leave the hook alone, so it is left out of the comparison.
    """
    return "".join(bundle.splitlines(keepends=True)[BANNER_LINE_COUNT:])


def first_body_difference(vendored: str, rebuilt: str) -> int | None:
    """The line number, counted in the whole file, of the first line below the banner where the
    two bundles differ, or None when their bodies are identical byte for byte."""
    vendored_body = bundle_body(vendored)
    rebuilt_body = bundle_body(rebuilt)
    if vendored_body == rebuilt_body:
        return None
    vendored_lines = vendored_body.splitlines(keepends=True)
    rebuilt_lines = rebuilt_body.splitlines(keepends=True)
    for index, (vendored_line, rebuilt_line) in enumerate(zip(vendored_lines, rebuilt_lines, strict=False)):
        if vendored_line != rebuilt_line:
            return BANNER_LINE_COUNT + index + 1
    # One body is the other plus lines at its end.
    return BANNER_LINE_COUNT + min(len(vendored_lines), len(rebuilt_lines)) + 1


def read_bundle(path: Path) -> str:
    """A bundle read byte for byte: decoded without the newline translation `read_text` applies."""
    return path.read_bytes().decode("utf-8")
