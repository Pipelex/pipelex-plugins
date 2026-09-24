#!/usr/bin/env python3
"""Refuse a release whose vendored hook bundle is behind its sources: `make check-hook-fresh`.

It answers two questions, and answers both on every run so that a stale bundle is described whole:

1. Is the vendored engine npm's latest? The `@pipelex/tools-wasm` version in the bundle's
   provenance line is compared with `npm view @pipelex/tools-wasm version`.
2. Would re-vendoring change the bundle? `npm ci` and `npm run build:hook` run in the
   `pipelex-sdk-js` checkout, and everything below the three-line banner of the rebuilt bundle is
   compared with the vendored one byte for byte. That is exact where a guess at which source files
   feed the bundle would not be, and it leaves out the banner's SDK commit, which moves with commits
   that never touch the hook.

It needs that sibling checkout and the network, and CI has neither, so it is a gate the `/release`
skill runs rather than a part of `make check`. It refuses to answer unless the checkout is on its
base, clean, and level with origin's base after a fetch, since a rebuild of anything else says
nothing about what re-vendoring would produce. `npm ci` rewrites the checkout's `node_modules` and
the build writes `dist-hooks/`, both ignored by git, which is exactly what `make vendor-hook` does.

Exit status: 0 when the bundle is current, 1 when it is behind, 2 when the gate could not answer.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from scripts.hook_bundle import (
    HOOK_BUNDLE_PATH,
    Provenance,
    first_body_difference,
    provenance_line,
    read_bundle,
    read_provenance,
)

SDK_JS_BASE = "dev"
TOOLS_WASM_PACKAGE = "@pipelex/tools-wasm"
# What identifies a pipelex-sdk-js checkout, and where its build writes the bundle.
BUILD_SCRIPT = Path("scripts") / "build-hook.mjs"
REBUILT_BUNDLE = Path("dist-hooks") / "check.mjs"
# `npm ci` on a cold cache is the slow step; this is a ceiling, not an expectation.
NPM_TIMEOUT_SECONDS = 600
GIT_TIMEOUT_SECONDS = 120
# How much of a failed command's output a refusal quotes.
OUTPUT_TAIL_LINES = 30
REVENDOR = "`make vendor-hook`, then `make build`, on a branch into dev"
# Set, it makes `npm run build:hook` bundle an unreleased engine build instead of the npm package,
# so the rebuild would describe something no re-vendor from published sources produces.
LOCAL_ENGINE_VARIABLE = "PIPELEX_TOOLS_WASM_PATH"

EXIT_CURRENT = 0
EXIT_STALE = 1
EXIT_UNANSWERED = 2


class GateError(Exception):
    """The gate could not answer: a command failed, or its answer could not be read."""


def _tail(output: str) -> str:
    return "\n".join(output.strip().splitlines()[-OUTPUT_TAIL_LINES:])


def _git(sdk_js_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(sdk_js_dir), *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GateError("no `git` on the PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GateError(f"`git {' '.join(args)}` did not finish within {GIT_TIMEOUT_SECONDS} seconds in {sdk_js_dir}") from exc


def sibling_refusals(sdk_js_dir: Path) -> list[str]:
    """Why the checkout cannot stand for what re-vendoring would produce, or nothing when it can.

    It must be a pipelex-sdk-js checkout on its base with nothing uncommitted, and level with
    origin's base once fetched: a checkout behind origin would rebuild an old hook and pass a bundle
    that `dev` has already moved past.
    """
    if not (sdk_js_dir / BUILD_SCRIPT).is_file():
        return [f"{sdk_js_dir} is not a pipelex-sdk-js checkout: it has no {BUILD_SCRIPT.as_posix()}. Point SDK_JS_DIR at one."]

    branch = _git(sdk_js_dir, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch.returncode != 0:
        return [f"{sdk_js_dir} is not on a branch. Check out {SDK_JS_BASE} there."]
    if branch.stdout.strip() != SDK_JS_BASE:
        return [f"{sdk_js_dir} is on {branch.stdout.strip()}, not on its base {SDK_JS_BASE}. Point SDK_JS_DIR at the main checkout."]

    status = _git(sdk_js_dir, "status", "--porcelain")
    if status.returncode != 0:
        return [f"git could not read the state of {sdk_js_dir}: {_tail(status.stderr)}"]
    if status.stdout.strip():
        return [f"{sdk_js_dir} has uncommitted changes, so a build there is not a build of {SDK_JS_BASE}:\n{_tail(status.stdout)}"]

    fetch = _git(sdk_js_dir, "fetch", "--quiet", "origin", SDK_JS_BASE)
    if fetch.returncode != 0:
        return [f"`git fetch origin {SDK_JS_BASE}` failed in {sdk_js_dir}, so the gate cannot tell whether it is current: {_tail(fetch.stderr)}"]
    head = _git(sdk_js_dir, "rev-parse", "HEAD").stdout.strip()
    upstream = _git(sdk_js_dir, "rev-parse", f"origin/{SDK_JS_BASE}").stdout.strip()
    if not head or not upstream:
        return [f"git could not resolve HEAD and origin/{SDK_JS_BASE} in {sdk_js_dir}."]
    if head != upstream:
        behind = _git(sdk_js_dir, "merge-base", "--is-ancestor", head, upstream).returncode == 0
        if behind:
            return [f"{sdk_js_dir} is behind origin/{SDK_JS_BASE}. Fast-forward it first: `git -C {sdk_js_dir} pull --ff-only origin {SDK_JS_BASE}`."]
        return [f"{sdk_js_dir} holds commits origin/{SDK_JS_BASE} does not, so a build there is not a build of {SDK_JS_BASE}."]
    return []


def _npm_env() -> dict[str, str]:
    """This environment without the local-engine override, so the rebuild bundles what `npm ci` installed."""
    return {name: value for name, value in os.environ.items() if name != LOCAL_ENGINE_VARIABLE}


def _run_npm(sdk_js_dir: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["npm", *args],
            cwd=sdk_js_dir,
            env=_npm_env(),
            capture_output=True,
            text=True,
            timeout=NPM_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GateError("no `npm` on the PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GateError(f"`npm {' '.join(args)}` did not finish within {NPM_TIMEOUT_SECONDS} seconds") from exc
    if result.returncode != 0:
        raise GateError(f"`npm {' '.join(args)}` failed in {sdk_js_dir}:\n{_tail(result.stdout + result.stderr)}")
    return result.stdout


def npm_latest_version(sdk_js_dir: Path) -> str:
    """The version npm's `latest` tag names for the engine, asked from the checkout so its `.npmrc` applies."""
    version = _run_npm(sdk_js_dir, "view", TOOLS_WASM_PACKAGE, "version").strip()
    if not version or len(version.split()) != 1:
        raise GateError(f"`npm view {TOOLS_WASM_PACKAGE} version` answered {version!r}, which is not one version")
    return version


def rebuild_bundle(sdk_js_dir: Path) -> str:
    """The bundle `make vendor-hook` would copy in, built from the checkout's lockfile."""
    print(f"  Running `npm ci` in {sdk_js_dir}...", flush=True)
    _run_npm(sdk_js_dir, "ci")
    print(f"  Running `npm run build:hook` in {sdk_js_dir}...", flush=True)
    _run_npm(sdk_js_dir, "run", "build:hook")
    rebuilt_path = sdk_js_dir / REBUILT_BUNDLE
    if not rebuilt_path.is_file():
        raise GateError(f"`npm run build:hook` succeeded but wrote no {REBUILT_BUNDLE.as_posix()}")
    return read_bundle(rebuilt_path)


def engine_findings(vendored: Provenance, rebuilt: Provenance | None, latest: str) -> list[str]:
    """Question 1: the vendored engine against npm's latest, with the cure for the case at hand."""
    if vendored.tools_wasm_version == latest:
        return []
    finding = f"the bundle embeds {TOOLS_WASM_PACKAGE} {vendored.tools_wasm_version}, and npm's latest is {latest}."
    if rebuilt is not None and rebuilt.tools_wasm_version == latest:
        return [f"{finding} pipelex-sdk-js already builds with {latest}: re-vendor with {REVENDOR}."]
    pinned = rebuilt.tools_wasm_version if rebuilt is not None else "an older version"
    return [
        f"{finding} pipelex-sdk-js pins {pinned}, so bump the pin there first "
        f"(`npm install --save-dev --save-exact {TOOLS_WASM_PACKAGE}@{latest}`), merge it to {SDK_JS_BASE}, "
        f"then re-vendor with {REVENDOR}."
    ]


def body_findings(vendored: str, rebuilt: str) -> list[str]:
    """Question 2: whether the code below the banner would change on a re-vendor."""
    line = first_body_difference(vendored, rebuilt)
    if line is None:
        return []
    return [
        f"a rebuild of pipelex-sdk-js at {SDK_JS_BASE} differs from the vendored bundle from line {line} on.\n"
        f"    vendored: {provenance_line(vendored)}\n"
        f"    rebuilt:  {provenance_line(rebuilt)}\n"
        f"    Re-vendor with {REVENDOR}."
    ]


def _report(title: str, findings: list[str], success: str) -> bool:
    print(title)
    for finding in findings:
        print(f"  STALE: {finding}")
    if not findings:
        print(f"  {success}")
    return bool(findings)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--sdk-js-dir", required=True, type=Path, help="The pipelex-sdk-js checkout to rebuild in (the Makefile's SDK_JS_DIR).")
    parser.add_argument("--bundle", type=Path, default=None, help=f"The vendored bundle to judge. Default: {HOOK_BUNDLE_PATH.as_posix()}.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base_dir = Path(__file__).resolve().parent.parent
    bundle_path: Path = args.bundle if args.bundle is not None else base_dir / HOOK_BUNDLE_PATH
    sdk_js_dir: Path = args.sdk_js_dir.resolve()

    if not bundle_path.is_file():
        print(f"REFUSED: there is no vendored bundle at {bundle_path}.")
        return EXIT_UNANSWERED
    vendored = read_bundle(bundle_path)
    vendored_provenance = read_provenance(vendored)
    if vendored_provenance is None:
        print(f"REFUSED: {bundle_path} carries no provenance line, so nothing says what it was built from. Re-vendor with {REVENDOR}.")
        return EXIT_UNANSWERED

    print(f"Checking that {sdk_js_dir} can stand for what re-vendoring would produce...")
    try:
        refusals = sibling_refusals(sdk_js_dir)
    except GateError as exc:
        refusals = [str(exc)]
    if refusals:
        for refusal in refusals:
            print(f"REFUSED: {refusal}")
        return EXIT_UNANSWERED
    print(f"  On {SDK_JS_BASE}, clean, and level with origin/{SDK_JS_BASE}.")

    try:
        latest = npm_latest_version(sdk_js_dir)
        rebuilt = rebuild_bundle(sdk_js_dir)
    except GateError as exc:
        print(f"REFUSED: {exc}")
        return EXIT_UNANSWERED

    stale = _report(
        f"Checking the vendored engine against npm's latest {TOOLS_WASM_PACKAGE}...",
        engine_findings(vendored_provenance, read_provenance(rebuilt), latest),
        f"The bundle embeds {vendored_provenance.tools_wasm_version}, which is npm's latest.",
    )
    stale |= _report(
        "Checking whether re-vendoring would change the bundle...",
        body_findings(vendored, rebuilt),
        f"A rebuild at {SDK_JS_BASE} is identical below the banner.",
    )
    if stale:
        print("FAIL: The vendored hook bundle is behind its sources. Re-vendor it before the release.")
        return EXIT_STALE
    print("The vendored hook bundle is current.")
    return EXIT_CURRENT


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
