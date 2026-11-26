"""The venv rung of pipelex-synthetic-inputs: a Python that renders the recipes where `uv` is absent.

Run it with any Python 3 that has its `venv` module, by path, in any shell:

    python3 "<skill-dir>/scripts/synth_venv.py"               # builds or reuses the venv, prints its interpreter
    python3 "<skill-dir>/scripts/synth_venv.py" "<file>.py"   # the same, then runs <file>.py with that interpreter
    python3 "<skill-dir>/scripts/synth_venv.py" -c "<code>"   # or any other arguments the interpreter takes

`py -3` or `python` start it as well as `python3`: the launcher only has to run this file. It owns one venv,
under `$XDG_CACHE_HOME/pipelex-plugins/synth-venv` when that variable is set, else under `%LOCALAPPDATA%` on
Windows and `~/.cache` elsewhere. It builds the venv once with the interpreter that started it, installs the
skill's whole package allowlist into it, and reuses it afterwards, rebuilding only a venv whose pip does not
answer and installing only when the allowlist does not import, with `--force-reinstall` when a plain install
leaves it broken. With arguments it hands them to the venv's
interpreter and exits with its code, so `python3 synth_venv.py` stands where `uv run … python -I -X utf8` stands on the
other rung, and no caller ever has to spell the interpreter's path, which on Windows lives under `Scripts\\`
rather than `bin/` and, quoted, would need PowerShell's call operator.

Every interpreter it starts runs with `-I`, isolated from the working directory, which is the user's project,
and from `PYTHON*` variables such as `PYTHONPATH`, so a `pip.py` or a `reportlab.py` lying there never runs in
place of the real module. The hand-over adds `-X utf8`, since a piped stdout on Windows otherwise encodes in the
ANSI code page and a recipe printing a character outside it would fail after writing a good file; `-I` ignores
`PYTHONUTF8`, so the flag is the only way to ask. An exclusive lock on `synth-venv.lock`, beside the venv, makes a
second invocation wait while the first builds or installs, and then find the venv ready.

Exit codes: the interpreter's own when it ran one, else 0 ready, 1 refused (the path is not a venv), 2 the venv
could not be built, 3 the packages could not be installed. They are distinguishable only outside PowerShell, whose
`-Command` turns every native exit code but 0 and 1 into 1, so a caller tells the failures apart by the stderr
line each prints: "refusing to build a venv over", "could not build a venv with pip at", "could not install".
Everything but the interpreter's path, and what the handed-over program prints, goes to stderr.

It stays inside the standard library and runs on any Python 3 a user may have, so it uses no syntax newer
than the oldest one still about.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

# The skill's package allowlist, all of it: one venv serves every format. The import names differ from the
# distribution names for three of them.
PACKAGES = ("reportlab", "pillow", "matplotlib", "numpy", "python-docx", "openpyxl", "python-pptx")
IMPORTS = ("reportlab", "PIL", "matplotlib", "numpy", "docx", "openpyxl", "pptx")

EXIT_REFUSED = 1
EXIT_VENV_FAILED = 2
EXIT_INSTALL_FAILED = 3

# `stat.FILE_ATTRIBUTE_REPARSE_POINT`, which the standard library defines on every OS but the type stubs declare on
# Windows alone.
FILE_ATTRIBUTE_REPARSE_POINT = 0x400

# Every interpreter this script starts is isolated: no working directory or script directory on `sys.path`, no
# `PYTHON*` variable, no user site-packages.
ISOLATED = "-I"


def venv_dir() -> Path:
    """Where the venv lives: the user's cache directory, never the project."""
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        cache = Path(xdg)
    elif os.name == "nt":
        cache = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        cache = Path.home() / ".cache"
    return cache / "pipelex-plugins" / "synth-venv"


def venv_python(venv: Path) -> Path:
    """The venv's interpreter: `Scripts\\python.exe` on Windows, `bin/python` elsewhere, as `venv` lays them out."""
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def is_reparse_point(path: Path, *, windows: bool = sys.platform == "win32") -> bool:
    """Whether `path` is a Windows reparse point, a junction among them, which is no symlink to `is_symlink` and
    which `Path.is_junction` reports only from Python 3.12. Read from the file's own attributes, on every version."""
    if not windows:
        return False
    try:
        attributes: int = getattr(os.lstat(path), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)


def _is_link(path: Path) -> bool:
    return path.is_symlink() or is_reparse_point(path)


def refusal(venv: Path) -> str | None:
    """Why `venv` may not be built over, or None. Building runs with `--clear`, which empties the directory
    first: on a link it would empty the link's target, and on anything that is not already a venv it would
    delete someone's files, and this rung runs unattended."""
    if _is_link(venv):
        return f"refusing to build a venv over {venv}: it is a link; move it aside"
    if venv.exists() and not (venv / "pyvenv.cfg").is_file():
        return f"refusing to build a venv over {venv}: it exists and is not a venv; move it aside"
    return None


def _quiet(command: list[str]) -> bool:
    """Whether `command` succeeds; an interpreter that is not there fails rather than raises."""
    if not Path(command[0]).is_file():
        return False
    return subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0


def _has_pip(python: Path) -> bool:
    return _quiet([str(python), ISOLATED, "-m", "pip", "--version"])


def _imports(python: Path) -> bool:
    """Whether the whole allowlist imports in the venv."""
    return _quiet([str(python), ISOLATED, "-c", "import " + ", ".join(IMPORTS)])


def _install(python: Path, *options: str) -> bool:
    """Install the allowlist into the venv, pip's output on stderr so stdout carries only the interpreter's path."""
    installed = subprocess.run(
        [str(python), ISOLATED, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", *options, *PACKAGES],
        stdout=sys.stderr,
        check=False,
    )
    return installed.returncode == 0


@contextmanager
def _locked(lock: Path) -> Generator[None, None, None]:
    """Hold an exclusive lock on `lock`, waiting for another invocation that holds it."""
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as handle:
        if sys.platform == "win32":
            handle.seek(0)
            while True:
                try:
                    # Locking past the end of the file is allowed; LK_LOCK gives up after about ten seconds.
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    continue
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def lock_path(venv: Path) -> Path:
    """The lock file, beside the venv rather than in it, which a rebuild empties."""
    return venv.with_name(f"{venv.name}.lock")


def ensure(venv: Path) -> int:
    """Build or reuse the venv and fill it with the allowlist; 0 when it is ready. The state is read once the lock
    is held, so an invocation that waited finds what the other built."""
    with _locked(lock_path(venv)):
        return _ensure_locked(venv)


def _ensure_locked(venv: Path) -> int:
    reason = refusal(venv)
    if reason:
        print(reason, file=sys.stderr)
        return EXIT_REFUSED
    python = venv_python(venv)
    # `-m venv` leaves the interpreter behind even when ensurepip fails, so test for a working pip, not for the
    # file, and rebuild with --clear rather than trust a half-made venv.
    if not _has_pip(python):
        print(f"building the venv {venv} with {sys.executable}", file=sys.stderr)
        built = subprocess.run([sys.executable, ISOLATED, "-m", "venv", "--clear", str(venv)], stdout=sys.stderr, check=False)
        if built.returncode != 0 or not _has_pip(python):
            print(f"could not build a venv with pip at {venv} using {sys.executable}", file=sys.stderr)
            return EXIT_VENV_FAILED
    if _imports(python):
        return 0
    print(f"installing {' '.join(PACKAGES)} into {venv}", file=sys.stderr)
    if not _install(python):
        print(f"could not install {' '.join(PACKAGES)} into {venv}", file=sys.stderr)
        return EXIT_INSTALL_FAILED
    if _imports(python):
        return 0
    # A package whose files are gone but whose install record is intact counts as installed, so the plain
    # install above changed nothing; only a forced one writes its files again.
    print(f"the allowlist still does not import; reinstalling it into {venv} with --force-reinstall", file=sys.stderr)
    if not _install(python, "--force-reinstall") or not _imports(python):
        print(f"could not install {' '.join(PACKAGES)} into {venv}", file=sys.stderr)
        return EXIT_INSTALL_FAILED
    return 0


def main(arguments: list[str]) -> int:
    venv = venv_dir()
    status = ensure(venv)
    if status != 0:
        return status
    python = venv_python(venv).absolute()
    if not arguments:
        print(python)
        return 0
    sys.stdout.flush()
    return subprocess.run(handover_command(python, arguments), check=False).returncode


def handover_command(python: Path, arguments: list[str]) -> list[str]:
    """The venv's interpreter running `arguments`, isolated from the project and printing UTF-8 into any pipe."""
    return [str(python), ISOLATED, "-X", "utf8", *arguments]


if __name__ == "__main__":
    # The interpreter's path holds the user's name, which a Windows code page may not encode: print it in UTF-8,
    # as the handed-over interpreter prints under `-X utf8`.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
