# The venv rung — no `uv` on this machine

Read this at step 2 of the skill when the `uv` preflight fails and prints nothing, which means `uv` is not on `PATH`, before creating or installing anything. It needs `python3` with its `venv` and `pip` modules; when either is missing, or the program below fails, the skill's stop table says what to offer.

Create a venv this skill owns, once, fill it with the whole allowlist, and reuse it on every later invocation:

```bash
VENV="${XDG_CACHE_HOME:-$HOME/.cache}/pipelex-plugins/synth-venv"
# --clear empties the directory before building, so refuse anything that is not already
# a venv: on a symlink it would empty the link's target, and this rung runs unattended.
if [ -e "$VENV" ] && { [ -L "$VENV" ] || [ ! -f "$VENV/pyvenv.cfg" ]; }; then
  echo "refusing to build a venv over $VENV — it exists and is not one; move it aside" >&2; exit 1
fi
# `-m venv` leaves bin/python behind even when ensurepip fails, so test for a working pip,
# not for the file — and rebuild with --clear rather than trusting a half-made venv.
"$VENV/bin/python" -m pip --version >/dev/null 2>&1 || python3 -m venv --clear "$VENV"
"$VENV/bin/python" -c "import reportlab, PIL, matplotlib, numpy, docx, openpyxl" 2>/dev/null || "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check reportlab pillow matplotlib numpy python-docx openpyxl
"$VENV/bin/python" -c "import sys, reportlab, PIL, matplotlib, numpy, docx, openpyxl; print('venv ready:', sys.argv[1])" "$VENV"
```

On success the runner line becomes `"$VENV/bin/python" << 'PYEOF'` — and **substitute the absolute path this command printed**, not the `$VENV` reference: each later command runs in a fresh shell where `VENV` is unset, and `"$VENV/bin/python"` would then expand to `/bin/python`, which exists on some Linux distributions and silently runs the wrong interpreter. That substitution is the only difference between the rungs, and the same interpreter runs step 5's verify commands in place of their `uv run` prefix. This rung installs something durable, isolated from the project and from the system Python, so proceed in automatic mode and state it: the venv path and the packages installed into it.
