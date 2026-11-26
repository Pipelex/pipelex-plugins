"""Run a command a skill gives through the platform's own shell, and remove the temporary directory it printed.

Shared by the unit suite and the recipe suite, which both run commands as a skill writes them: `sh` on macOS and
Linux and Windows PowerShell on Windows, never bash, which a skill may not assume.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def run_in_platform_shell(command: str, *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run `command` as written through the platform's own shell: Windows PowerShell, the stricter of the two
    PowerShells, on Windows, and `sh` elsewhere."""
    if os.name == "nt":
        argv = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
    else:
        argv = ["/bin/sh", "-c", command]
    return subprocess.run(argv, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True, check=False)


def remove_printed_temp_dir(printed: Path, *, prefix: str) -> None:
    """Remove a directory a command made in the system temp folder and printed, and nothing else: the path must be
    absolute, named with `prefix`, and directly under the temp folder this process sees, which the command saw too."""
    assert printed.is_absolute(), f"refusing to remove {printed}: not an absolute path"
    assert printed.name.startswith(prefix), f"refusing to remove {printed}: its name does not start with {prefix!r}"
    system_temp = Path(tempfile.gettempdir()).resolve()
    assert printed.resolve().parent == system_temp, f"refusing to remove {printed}: not directly under {system_temp}"
    if printed.is_dir():
        shutil.rmtree(printed)
