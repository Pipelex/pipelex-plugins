"""The venv rung of pipelex-synthetic-inputs: a Python that renders the recipes where `uv` is absent.

Run it with any Python 3 that has its `venv` module, by path, in any shell:

    python3 <skill-dir>/scripts/synth_venv.py              # builds or reuses the venv, prints its interpreter
    python3 <skill-dir>/scripts/synth_venv.py <file>.py    # the same, then runs <file>.py with that interpreter
    python3 <skill-dir>/scripts/synth_venv.py -c "<code>"  # or any other arguments the interpreter takes

`py -3` or `python` start it as well as `python3`: the launcher only has to run this file. It owns one venv,
under `$XDG_CACHE_HOME/pipelex-plugins/synth-venv` when that variable is set, else under `%LOCALAPPDATA%` on
Windows and `~/.cache` elsewhere. It builds the venv once with the interpreter that started it, installs the
skill's whole package allowlist into it, and reuses it afterwards, rebuilding only a venv whose pip does not
answer and reinstalling only when the allowlist does not import. With arguments it hands them to the venv's
interpreter and exits with its code, so `python3 synth_venv.py` stands where `uv run … python` stands on the
other rung, and no caller ever has to spell the interpreter's path, which on Windows lives under `Scripts\\`
rather than `bin/` and, quoted, would need PowerShell's call operator.

Exit codes: the interpreter's own when it ran one, else 0 ready, 1 refused (the path is not a venv), 2 the venv
could not be built, 3 the packages could not be installed. Everything but the interpreter's path, and what the
handed-over program prints, goes to stderr.

It stays inside the standard library and runs on any Python 3 a user may have, so it uses no syntax newer
than the oldest one still about.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# The skill's package allowlist, all of it: one venv serves every format. The import names differ from the
# distribution names for three of them.
PACKAGES = ("reportlab", "pillow", "matplotlib", "numpy", "python-docx", "openpyxl", "python-pptx")
IMPORTS = ("reportlab", "PIL", "matplotlib", "numpy", "docx", "openpyxl", "pptx")

EXIT_REFUSED = 1
EXIT_VENV_FAILED = 2
EXIT_INSTALL_FAILED = 3


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


def _is_link(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)  # Python 3.12+: a Windows junction is no symlink
    return path.is_symlink() or bool(is_junction and is_junction())


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


def ensure(venv: Path) -> int:
    """Build or reuse the venv and fill it with the allowlist; 0 when it is ready."""
    reason = refusal(venv)
    if reason:
        print(reason, file=sys.stderr)
        return EXIT_REFUSED
    python = venv_python(venv)
    # `-m venv` leaves the interpreter behind even when ensurepip fails, so test for a working pip, not for the
    # file, and rebuild with --clear rather than trust a half-made venv.
    if not _quiet([str(python), "-m", "pip", "--version"]):
        print(f"building the venv {venv} with {sys.executable}", file=sys.stderr)
        built = subprocess.run([sys.executable, "-m", "venv", "--clear", str(venv)], check=False)
        if built.returncode != 0 or not _quiet([str(python), "-m", "pip", "--version"]):
            print(f"could not build a venv with pip at {venv} using {sys.executable}", file=sys.stderr)
            return EXIT_VENV_FAILED
    if not _quiet([str(python), "-c", "import " + ", ".join(IMPORTS)]):
        print(f"installing {' '.join(PACKAGES)} into {venv}", file=sys.stderr)
        installed = subprocess.run(
            [str(python), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", *PACKAGES],
            stdout=sys.stderr,
            check=False,
        )
        if installed.returncode != 0 or not _quiet([str(python), "-c", "import " + ", ".join(IMPORTS)]):
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
    return subprocess.run([str(python), *arguments], check=False).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
