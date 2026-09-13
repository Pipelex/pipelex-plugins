"""codegen_check.py — the offline drift gate for Pipelex-generated Python trees.

Copied verbatim into a project by /pipelex-integrate. Run it from the project root, with the project's
own environment (the one `pipelex-sdk` is installed in), and one generated directory per argument:

    uv run python scripts/codegen_check.py src/my_app/generated/summarize_pdf src/my_app/generated/extract_entities

For each directory it (1) runs `pipelex-sdk`'s `run_codegen_check` over the stamped files against
`codegen.lock` — pure hashing, no engine, no network, no API key, and no `pipelex` runtime — and (2)
compares the SHA-256 recorded for each .mthds source in `sources.json` against the file on disk, so a
bundle edited without a regeneration is caught as `stale-source`.

Exit codes: 0 current · 1 drift or stale source · 2 no verdict (no lock, a malformed or unreadable lock
or tree, a symlink at the generated directory or on an artifact's path, `pipelex-sdk` not importable).
Precedence across directories: 2 > 1 > 0.

It is the twin of `codegen-check.mjs`, which does the same for a TypeScript project over `@pipelex/sdk`,
and the two fail closed on the same malformed sidecars. It imports only the standard library and
`pipelex-sdk` (0.10.0 or later), and writes through `sys.stdout` / `sys.stderr` so a no-print lint rule
stays quiet. When `pipelex-sdk` ships this check as a command, replace this file with that one line.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import NamedTuple, NoReturn, cast

try:
    from pipelex_sdk.codegen_check import run_codegen_check
    from pipelex_sdk.errors import CodegenLockError
except ImportError as import_error:
    # A gate that cannot run has no verdict to give. Letting the import fail would exit 1, which reads as
    # drift, and the likeliest cause is an interpreter outside the project's environment, not the tree.
    sys.stderr.write(
        f"codegen-check: no verdict — pipelex-sdk 0.10.0 or later is not importable ({import_error}). "
        "Run this script with the project's own environment, e.g. `uv run python scripts/codegen_check.py …`.\n"
    )
    sys.exit(2)  # EXIT_NO_VERDICT, which a linter will not let this file define above its imports

EXIT_CURRENT = 0
EXIT_DRIFT = 1
EXIT_NO_VERDICT = 2

LOCK_FILENAME = "codegen.lock"
SIDECAR_FILENAME = "sources.json"
NO_SOURCES_LINE = f"  {SIDECAR_FILENAME} records no sources — a by-ref or by-id integration; source staleness does not apply"


class Outcome(NamedTuple):
    """One check's exit code and the lines explaining it."""

    code: int
    lines: tuple[str, ...]


def _out(line: str) -> None:
    sys.stdout.write(f"{line}\n")
    # Flushed line by line: under CI and `make` stdout is a block-buffered pipe, so without this a
    # directory's name would print after the drift lines that went to stderr about it.
    sys.stdout.flush()


def _err(line: str) -> None:
    sys.stderr.write(f"{line}\n")
    sys.stderr.flush()


def _reject_json_constant(value: str) -> NoReturn:
    # Python's `json` accepts `NaN`, `Infinity` and `-Infinity`; JSON does not, and neither does the
    # TypeScript twin's `JSON.parse`. A sidecar only this reader could parse is an unreadable sidecar.
    msg = f"non-standard JSON constant {value}"
    raise ValueError(msg)


def check_tree(*, directory: Path) -> Outcome:
    """Run the lock check. A state of the tree never raises: it is a verdict, or the absence of one."""
    try:
        report = run_codegen_check(root=directory)
    except CodegenLockError as exc:
        return Outcome(code=EXIT_NO_VERDICT, lines=(f"  no verdict: {exc}",))
    if not report.lock_found:
        return Outcome(code=EXIT_NO_VERDICT, lines=(f"  no verdict: {LOCK_FILENAME} — not found",))
    if report.is_current:
        fingerprint = (report.crate_fingerprint or "")[:12]
        return Outcome(code=EXIT_CURRENT, lines=(f"  tree current (crate {fingerprint}, engine {report.engine_version})",))
    return Outcome(code=EXIT_DRIFT, lines=tuple(f"  {drift.category}: {drift.path} — {drift.detail}" for drift in report.drifts))


def check_sources(*, directory: Path) -> Outcome:
    """Run the sidecar check: each recorded .mthds source, by its path relative to the project root."""
    try:
        # Strict UTF-8 over the raw bytes, and deliberately not `utf-8-sig`: a byte-order mark stays in the
        # text, so `json.loads` refuses it exactly as the TypeScript twin's `JSON.parse` does. Handing
        # `json.loads` the bytes instead would sniff the mark and strip it, and a sidecar the other gate calls
        # unreadable would pass here.
        text = (directory / SIDECAR_FILENAME).read_bytes().decode("utf-8")
        sidecar: object = json.loads(text, parse_constant=_reject_json_constant)
    except FileNotFoundError:
        return Outcome(code=EXIT_CURRENT, lines=(f"  no {SIDECAR_FILENAME} — source staleness not checked",))
    except (OSError, ValueError, RecursionError) as exc:
        # `UnicodeDecodeError` and `json.JSONDecodeError` are both `ValueError`s.
        return Outcome(code=EXIT_DRIFT, lines=(f"  stale-source: {SIDECAR_FILENAME} — unreadable ({exc}), so staleness cannot be ruled out",))
    recorded_sources = _recorded_sources(sidecar=sidecar)
    if isinstance(recorded_sources, Outcome):
        return recorded_sources
    return _compare_sources(recorded_sources=recorded_sources)


def _recorded_sources(*, sidecar: object) -> list[tuple[str, object]] | Outcome:
    """Return the sidecar's `sources` as sorted pairs, or the outcome that ends the check before any is read."""
    # A file whose whole content is `null`, `[]`, `"x"`, `42` or `true` is valid JSON and not an object. Read
    # through `.get()` or a truthiness test, every one of them looks like the legitimate absent case, and the
    # gate would announce "a by-ref or by-id integration" and exit 0 over a sidecar that says nothing of the
    # kind. So the sidecar is guarded first, and its `sources` second.
    if not isinstance(sidecar, dict):
        return Outcome(code=EXIT_DRIFT, lines=(f"  stale-source: {SIDECAR_FILENAME} — not a JSON object, so staleness cannot be ruled out",))
    fields = cast("dict[str, object]", sidecar)

    # A present-but-wrong-shaped `sources` must fail the way an unreadable sidecar does. Coerced to `{}` it
    # would check nothing, print nothing and exit 0 — the one input that is both silent and green. An explicit
    # `null` is why presence is tested with `in` rather than by reading the value: `None` is not absent.
    if "sources" not in fields:
        return Outcome(code=EXIT_CURRENT, lines=(NO_SOURCES_LINE,))
    sources = fields["sources"]
    if not isinstance(sources, dict):
        return Outcome(code=EXIT_DRIFT, lines=(f"  stale-source: {SIDECAR_FILENAME} — `sources` is not an object, so staleness cannot be ruled out",))
    recorded_sources = sorted(cast("dict[str, object]", sources).items())
    if not recorded_sources:
        return Outcome(code=EXIT_CURRENT, lines=(NO_SOURCES_LINE,))
    return recorded_sources


def _compare_sources(*, recorded_sources: list[tuple[str, object]]) -> Outcome:
    """Hash each recorded source on disk and compare it with the SHA-256 the sidecar recorded."""
    stale_lines: list[str] = []
    project_root = Path.cwd()
    for source, recorded in recorded_sources:
        try:
            on_disk = hashlib.sha256((project_root / source).read_bytes()).hexdigest()
        except FileNotFoundError:
            stale_lines.append(f"  stale-source: {source} — recorded as a source but no longer on disk")
            continue
        except (OSError, ValueError) as exc:
            stale_lines.append(f"  stale-source: {source} — recorded as a source but unreadable ({exc})")
            continue
        if on_disk != recorded:
            stale_lines.append(f"  stale-source: {source} — edited since the types were generated")
    return Outcome(code=EXIT_DRIFT if stale_lines else EXIT_CURRENT, lines=tuple(stale_lines))


def worse(first: int, second: int) -> int:
    """Precedence: no verdict > drift > current."""
    if EXIT_NO_VERDICT in (first, second):
        return EXIT_NO_VERDICT
    if EXIT_DRIFT in (first, second):
        return EXIT_DRIFT
    return EXIT_CURRENT


def main(argv: list[str]) -> int:
    """Check every generated directory named on the command line and return the worst exit code."""
    arguments = argv[1:]
    if not arguments:
        _err("usage: python scripts/codegen_check.py <generated-dir> [<generated-dir> ...]")
        return EXIT_NO_VERDICT

    exit_code = EXIT_CURRENT
    for argument in arguments:
        _out(argument)
        directory = Path(argument)
        tree = check_tree(directory=directory)
        sources = Outcome(code=EXIT_CURRENT, lines=()) if tree.code == EXIT_NO_VERDICT else check_sources(directory=directory)
        code = worse(tree.code, sources.code)
        write = _out if code == EXIT_CURRENT else _err
        for line in (*tree.lines, *sources.lines):
            write(line)
        if code == EXIT_DRIFT:
            _err("  Run /pipelex-integrate to refresh the generated types.")
        exit_code = worse(exit_code, code)

    verdicts = {EXIT_CURRENT: "current", EXIT_DRIFT: "drift", EXIT_NO_VERDICT: "no verdict"}
    _out(f"\ncodegen-check: {verdicts[exit_code]}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
