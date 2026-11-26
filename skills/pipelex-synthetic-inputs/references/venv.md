# The venv rung — no `uv` on this machine

Read this at step 2 of the skill when `uv --version` fails, before creating or installing anything. The rung needs a Python 3 with its `venv` and `pip` modules; when none runs the script below, or the script fails, the skill's stop table sends you to the cures at the end of this file.

The skill's `scripts/synth_venv.py`, at the path step 2 names, does the whole rung, the same in every shell: it builds a venv this skill owns, once, under the user's cache directory (`$XDG_CACHE_HOME`, else `%LOCALAPPDATA%` on Windows and `~/.cache` elsewhere, then `pipelex-plugins/synth-venv`), fills it with the whole allowlist, and reuses it on every later invocation. It refuses to build over a path that exists and is not a venv, rebuilds a venv whose `pip` does not answer, forces a reinstall when a package's files are gone, and reports what it built and installed on stderr.

Start it with the first Python launcher that runs it, trying `python3`, then `py -3`, then `python`, and quote its path:

```shell
python3 "<the script's path from step 2>"
```

On success it prints the venv's interpreter, an absolute path, and that launcher with the quoted script path is the **runner**: given arguments, the script hands them to that interpreter and exits with its code, so `<runner> "<file>.py"` runs a recipe and `<runner> -c "…"` a verify command, each standing where `uv run … python` stands on rung 1. That is the only difference between the rungs. Make this invocation's temporary directory with it, as rung 1's preflight does:

```shell
python3 "<the script's path from step 2>" -c "import tempfile; print(tempfile.mkdtemp())"
```

Call the interpreter through the runner, never by its printed path: a quoted path is a string to PowerShell, not a command. This rung installs something durable, isolated from the project and from the system Python, so proceed in automatic mode and state it: the venv path and the packages installed into it.

## Cures, when the stop table sends you here

Each installs a tool, so ask before running one, and continue once it has run.

- **The `uv` installer**, the recommended cure, which also brings a Python where there is none and makes step 2 take rung 1: `curl -LsSf https://astral.sh/uv/install.sh | sh` on macOS and Linux, `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` on Windows.
- **The platform's `venv`**, for a script that could not build a venv with `pip` (exit code 2): `sudo apt install python3-venv` on Debian and Ubuntu, whose Python ships without it.
