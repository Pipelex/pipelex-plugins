---
status: active
item: L-260901-9dea4e
---

# Plan: `pipelex-synthetic-inputs` — a skill that generates synthetic input files

Written on 2026-09-02 in the `_pipelex-plugins--synthetic-inputs` worktree (branch `feature/Synthetic-inputs`), after auditing `pipelex-inputs` against its predecessor `mthds-plugins/mthds/skills/mthds-inputs`. This is the plan for the **first version of the skill**: the version that knows how to build a PDF the way `mthds-inputs` did, and how to produce PNG images without AI, from permissively licensed Python packages. Later formats get their own phase at the end, deliberately left thin.

Two scope rulings taken on 2026-09-02 before ratification: the skill ships only the image categories it can render to a real standard — no procedural "photo-like" stand-in and no jittered "handwritten" imitation — and it owns the installation of what it needs, with a graceful, explicit failure when the machine cannot provide it.

## The gap this closes

`pipelex-inputs` carries the full synthetic-strategy skeleton from `mthds-inputs` — the concept-to-value table, the text/number/structured guidance, the DOCX and XLSX recipes — but two things fell out of the CLI-free rewrite. Image generation vanished entirely: the Synthetic Strategy table sends `native.Image` to "Document Generation fallbacks", and Document Generation covers only PDF, DOCX and XLSX; Example 2 says "source or generate a test image" and gives no method. And the PDF know-how was compressed from runnable reportlab recipes for the canvas, multi-page Platypus and table-report cases to one canvas recipe plus a sentence pointing at Platypus.

The old image recipe cannot come back as it was. It ran `mthds-agent run bundle pipelex/builder/synthetic_inputs/synthesize_image.mthds`, which is CLI-bound — against this plugin's posture — and dead: that bundle no longer exists in the `pipelex` repo. So the image capability has to be authored fresh, and the user's constraint settles how: **no AI, basic Python packages, licenses compatible with MIT**.

Rather than growing `pipelex-inputs` back to its predecessor's size, file synthesis becomes its own skill. `pipelex-inputs` stays the input-preparation flow (template → fill → prepare → run) and delegates to the new skill whenever a file has to be made. The new skill is also useful on its own ("make me a sample invoice PDF", "I need a test screenshot").

## What the skill is

**Name:** `pipelex-synthetic-inputs` (decision D1 below). Invoked as `/pipelex-synthetic-inputs` by a user, or by `pipelex-inputs` mid-flow.

**Its contract, as seen by a caller.** A request carries the fields below, inferred from conversation when the user invokes the skill directly and passed explicitly when `pipelex-inputs` does:

| Field | Meaning | Default when absent |
|---|---|---|
| `format` | `pdf`, `png` (v0.1.0); `docx`, `xlsx` carried over as-is | inferred from the target concept: `native.Document` → `pdf`, `native.Image` → `png` |
| `brief` | one or two sentences on what the file must contain or depict, in the vocabulary of the method that will consume it ("an invoice from a hardware store with ten line items and a VAT total") | asked for, or derived from the method's purpose and the input's description |
| `target` | the path to write | `<output_dir>/inputs/<input_variable>.<ext>` |
| `constraints` | page count, pixel size, the PNG category (see D5), language, anything the method's inputs description pins | sensible per-format defaults |

The skill writes the file, verifies it, and reports one line per file: path, format, dimensions or page count, and a short content summary. When called from `pipelex-inputs`, the path is what flows back into `inputs.json` as a bare path string, and the existing prepare step (`mthds_prepare_inputs`) uploads it unchanged.

**Its rules.** These are the skill's identity, and they go at the top of its `SKILL.md`:

- **No AI in the loop.** Files are rendered from code the agent writes: reportlab for PDF, Pillow and matplotlib for PNG. No image-generation model, no hosted method, no image API. (A future opt-in AI path is listed under "Later versions"; it is not a fallback of this skill.)
- **Only what renders to standard.** The skill makes the kinds of files that code can make convincingly. When a request asks for something outside that set — a photograph, handwriting — the skill says so plainly, asks for the user's own file, and does not produce an imitation. A stand-in that a vision model would read as "a synthetic drawing" is worse than an honest refusal, because it lets a method run on the wrong kind of input.
- **Permissive packages only.** The allowlist is `reportlab` (BSD), `Pillow` (MIT-CMU), `matplotlib` (PSF-style, BSD-compatible), `numpy` (BSD), plus `python-docx` (MIT) and `openpyxl` (MIT) for the carried-over formats. Explicitly out: PyMuPDF (AGPL), anything that needs a system binary the user may not have (poppler, cairo, wkhtmltopdf, Ghostscript), and any package that reaches the network at runtime. Verified on 2026-09-02 with `uv run --with pillow --with matplotlib --with reportlab`: Pillow 12.3.0 (`MIT-CMU`), matplotlib 3.11.1, reportlab 5.0.1 (BSD), numpy (BSD-3-Clause).
- **The skill owns its environment.** It never assumes the packages are there and never leaves the user to install them. It resolves a Python runner once per invocation through the ladder in D8 — `uv` with ephemeral `--with` packages first, then a skill-owned venv it creates and fills itself — and when neither rung is possible it stops with the exact missing piece and the command that supplies it. Nothing is installed into the user's project, and nothing is installed onto the machine outside that ladder without asking.
- **Content first, then render.** The realism lives in the content, not the rendering: before choosing a recipe, the skill drafts what the file says (title, parties, line items, figures, labels) from the brief and the method's context, exactly the way `pipelex-inputs` already tells the agent to "generate invoice-like text if the method processes invoices". Entities are obviously fictional — "Acme Hardware Supply", "Jane Example" — never real people or brands.
- **Deterministic.** Recipes seed their randomness (`random.seed(…)`, `numpy.random.default_rng(…)`) so a regenerated file is the same file.
- **Modest sizes.** PNGs default to 1200×800, document-shaped PNGs to A4 at 150 dpi (1240×1754); PDFs to a few pages. This keeps generated assets well inside the storage-size boundary `pipelex-inputs` enforces at prepare time; the boundary itself stays where it is.
- **Verified before reported, and a failure leaves nothing behind.** After rendering, the skill reopens the file (Pillow for PNG; `%PDF` header and size for PDF) and, on Claude Code, views the PNG with `Read` to eyeball it. A render that fails removes any partial output, so `inputs.json` can never point at a broken file. The PDF last-resort public URL inherited from `mthds-inputs` is never substituted silently — the report says what was done.

The skill needs no MCP tool and nothing from the Pipelex API. It is the plugin's second MCP-free skill after `pipelex-explain`, and it stays out of the `MCP_SKILLS` tuple in the tests.

## Decisions to take

Each item is a decision with variants and a recommendation. Ratified on 2026-09-02 with every recommendation as written, D5 and D8 as ruled.

### D1 — Name

- **`pipelex-synthetic-inputs` (recommended).** Matches the worktree topic and the `pipelex-inputs` family; the description carries the trigger phrases ("sample PDF", "test image", "fake invoice", "placeholder document").
- `pipelex-synthesize` — shorter, but it reads as if it synthesizes *methods*.
- `pipelex-fixtures` — the software-testing word; accurate but not the vocabulary users reach for.

### D2 — Shape: one file, references per format, or sub-skills per format

- **One router `SKILL.md` plus one static reference file per format (recommended).** `templates/skills/pipelex-synthetic-inputs/SKILL.md.j2` holds the contract, the rules, the environment ladder, the content-first step, the format dispatch table and the failure posture — short enough to read on every invocation. The recipes live in `skills/pipelex-synthetic-inputs/references/pdf.md` and `references/png.md`, loaded only when that format is being made. This is exactly the mechanism `pipelex-design` already uses for `references/writing-mthds.md`: static Markdown under the repo-root `skills/<name>/references/`, copied verbatim into every target by `setup_static_assets`, no build change needed. The recipes contain no platform-specific content, so they do not need to be templates.
- Sub-skills per format (`pipelex-synthetic-pdf`, `pipelex-synthetic-png`, …) — each would need its own frontmatter, trigger description and README entry, the skill list grows with every format, and `pipelex-inputs` would have to route by format itself. Rejected: the format is one field of a request, not a different job.
- One long `SKILL.md` with everything inline — the `mthds-inputs` shape. Rejected: every invocation would pay for every format's recipes, and Claude Code's own guidance is to keep a `SKILL.md` under a few hundred lines and split reference material out.

### D3 — Prose recipes, shipped scripts, or both

- **Prose recipes, executed by a test (recommended).** The reference files carry complete, runnable blocks that the agent copies and adapts — the `mthds-inputs` idiom, and the right one, because the content of a synthetic file is different every time and a parameterized script would become a JSON DSL for documents. Every block opens with the **runner line**, `uv run --quiet --with <pkgs> python << 'PYEOF'`; the venv rung of D8 replaces that one line with `"$VENV/bin/python" << 'PYEOF'` and nothing else. (A `PY="uv run …"` variable was considered and dropped: an unquoted `$PY` does not word-split under zsh, which is the default shell on macOS, so the runner would silently fail there.) What was missing from `mthds-inputs` is the guard: a test that extracts every such block from the reference files, substitutes `<output_dir>` with a temporary directory, runs it, and asserts the output exists with the right magic bytes (`\x89PNG` / `%PDF`) and, for PNG, the expected dimensions. The old image recipe rotted because nothing executed it; this one cannot rot quietly. The test is opt-in (`make test-recipes`, a `recipes` pytest marker, skipped when `uv` is absent) because it downloads packages on first run; there is no GitHub Actions workflow in this repo today, so nothing in CI changes.
- Shipped generator scripts (`skills/<name>/scripts/synth_png.py --kind chart …`) — testable and consistent, but they need the agent to know the plugin's on-disk path (`${CLAUDE_PLUGIN_ROOT}` is substituted in hook and MCP manifests, not in skill prose, and Codex and Vibe differ), the build would need a `scripts/` copy alongside `references/`, and the parameter surface is the DSL problem above. Not for v0.1.0; a later version may ship small *helpers* (a font loader, a "scanner" post-process) if the recipes keep repeating them.
- Both — the same maintenance cost twice. Rejected.

### D4 — What moves out of `pipelex-inputs` now

- **All of Document Generation moves (recommended).** PDF and PNG move and get the new depth; the DOCX and XLSX subsections move verbatim into `references/office.md`, unchanged in substance, so that `pipelex-inputs` points at exactly one place for "make a file". The Synthetic Strategy table rows for `native.Image` and `native.Document` and the "Generate File Inputs" step become a delegation; the "Fallback Strategy" block and Example 2 follow. `pipelex-inputs` loses its longest section and nothing else.
- Move PDF only, leave DOCX/XLSX in place until a later version deepens them — keeps the diff to `pipelex-inputs` smaller, at the price of a section that says "PDF and images: that skill; Word and Excel: below". Two homes for one concern is the thing D2 rejects; not recommended.

### D5 — The PNG category set for v0.1.0

The category table was the real know-how in the old skill: it taught *what kind* of picture a method wants. It comes back, restricted to what code renders convincingly. **Ruled on 2026-09-02: only the categories in this table ship; `photograph` and `handwritten` are out** — a procedural scene or jittered type is not up to par, and the skill would rather say "I cannot make that; give me a file" than hand a method an imitation.

| Category | Rendered with | What it is good for |
|---|---|---|
| `chart` | matplotlib (`Agg` backend, bar/line/pie/scatter from the brief's data, `dpi=150`) | data-visualization inputs; this *is* how real charts are made |
| `diagram` | Pillow boxes, arrows and labels from a small node/edge list | flowcharts, architecture and org charts, process diagrams |
| `document_scan` | Pillow renders a page (title, paragraphs, a table grid) then post-processes it: slight rotation, paper tint, noise, mild blur, vignette | OCR and document-understanding inputs — invoices, receipts, forms, letters |
| `screenshot` | Pillow draws window chrome (title bar, sidebar, header, a table or card grid) | UI-understanding inputs — dashboards, app screens, settings pages |

The reference file opens with this table plus a short "not covered" line naming `photograph` and `handwritten` and what to do instead (ask for the user's file; the opt-in AI path under "Later versions" if it ever ships). There is no public-URL last resort for images in v0.1.0: the honest answer to "I need a photo" is a real photo from the user.

### D6 — Fonts

Text in a PNG needs a scalable font, and hunting system fonts is what makes image recipes break across machines. Two bundled sources, both verified on 2026-09-02: Pillow ≥ 10.1 ships a bundled TrueType face behind `ImageFont.load_default(size=…)` (returns a `FreeTypeFont`), and matplotlib bundles DejaVu Sans at `matplotlib.font_manager.findfont("DejaVu Sans")`, which Pillow's `ImageFont.truetype` can open when a heavier or bolder face is wanted. **Recommendation:** the reference file defines one small `font(size, bold=False)` helper on top of these two and every recipe uses it; no recipe ever names a system font path.

### D7 — How `pipelex-inputs` invokes the skill on each platform

On Claude Code the skill is invoked through the `Skill` tool. Codex and Mistral Vibe load skills from disk and have no equivalent tool call, so the template branches on `platform`: "invoke `/pipelex-synthetic-inputs`" on Claude, "open `../pipelex-synthetic-inputs/SKILL.md` and follow it" elsewhere. Both are one sentence in the "Generate File Inputs" step; the reference files are reachable by relative path from either skill in every target because the output directories are self-contained.

### D8 — The environment ladder: how packages get there, and how the skill fails when they cannot

This is the second ruling of 2026-09-02, and it is a section of `SKILL.md` in its own right, run once per invocation before any recipe. The ladder, top rung first:

| Rung | Detect | Do | Say |
|---|---|---|---|
| **`uv` on `PATH`** (the normal case) | `command -v uv` | preflight the format's package set once: `uv run --with <pkgs> python -c "import …"`; on success every recipe runs with its runner line as written, `uv run --quiet --with <pkgs> python << 'PYEOF'`. Packages land in uv's cache, nothing in the project | nothing on success; on a cold cache, one line that the first run downloads packages and may take a minute |
| **no `uv`, but `python3` with `venv` and `pip`** | `command -v python3` and `python3 -m venv <cache>/synth-venv` succeeds | create the skill-owned venv once at `${XDG_CACHE_HOME:-$HOME/.cache}/pipelex-plugins/synth-venv`, `pip install` the allowlist into it, verify the imports, then the runner line becomes `"$VENV/bin/python" << 'PYEOF'` for every recipe — the only line that changes. Reused on later invocations; the preflight re-checks the imports and installs only what is missing | one line naming the venv path and the packages installed into it — this is the rung that installs something durable, and it is isolated from the project, so the skill proceeds in automatic mode and states it, exactly as `pipelex-inputs` does for an upload |
| **`venv` creation fails** (`ensurepip` missing — Debian/Ubuntu without `python3-venv`) | the error text | stop, quote the error, give the platform cure (`sudo apt install python3-venv`) **and** the `uv` installer as the recommended one (`curl -LsSf https://astral.sh/uv/install.sh \| sh`, which also brings a managed Python when there is none). **Installing a tool onto the machine always asks first, in every mode** — a tool is not a package | the two commands, and an offer to continue once one has run |
| **no `python3` at all** | `command -v python3` | stop; same offer: install `uv` (asks first) | the command, the offer |
| **download fails** (offline, proxy, registry down) on either rung | the `uv`/`pip` error | a warm uv cache still works — try the preflight anyway before concluding; otherwise stop, quote the error, say the machine needs network once | the error, the retry hint |
| **everything above failed, or the user declined** | — | **fail gracefully**: state what is missing and the exact command that fixes it, offer the user's own file for this input, and for **PDF only** offer the documented public last-resort URL, reported as a substitution. Never fabricate a file, never leave a partial one, and — when called from `pipelex-inputs` — return with no path so the caller leaves the input unfilled and says why, rather than aborting the whole inputs flow | what is missing, what was tried, the two ways forward |

Why this shape: `uv run --with` is the one-command answer everywhere it exists, and it is what the recipe test exercises; the venv rung makes the skill work on a machine that has only a stock Python, without touching the project or the user's global site-packages; the "ask before installing a tool" line keeps automatic mode from silently changing the machine. A permanent failure is a report the user can act on in one paste, not a stack trace.

Per-format package sets keep the first-run download proportional to the request: `pdf` needs `reportlab` alone; `png` needs `pillow`, `matplotlib`, `numpy`; the office formats need `python-docx` or `openpyxl`. The venv rung installs the whole allowlist at once, since it is a one-time cost.

## Layout

```
templates/skills/pipelex-synthetic-inputs/SKILL.md.j2   # new — router: contract, rules, environment ladder (D8), content-first step, dispatch table, failure posture, report
skills/pipelex-synthetic-inputs/references/pdf.md       # new — reportlab recipes (canvas, Platypus multi-page, table report), verify, last resort
skills/pipelex-synthetic-inputs/references/png.md       # new — category table + "not covered", preamble + font helper, one recipe per category, scanner post-process, verify
skills/pipelex-synthetic-inputs/references/office.md    # new — DOCX/XLSX moved verbatim from pipelex-inputs
templates/skills/pipelex-inputs/SKILL.md.j2             # changed — delegation replaces Document Generation; unfilled-input outcome on a graceful failure
tests/unit/test_gen_skill_docs.py                       # changed — TestSyntheticInputsSkill
tests/recipes/test_recipes.py                           # new — opt-in recipe execution (D3), both ladder rungs (D8)
pyproject.toml, Makefile                                # changed — `recipes` marker, `make test-recipes`
README.md, CLAUDE.md, docs/decisions.md, CHANGELOG.md   # changed
pipelex/, pipelex-codex/, pipelex-vibe/                 # regenerated by `make build`
```

Skills are discovered from `templates/skills/*/SKILL.md.j2`, so nothing registers the new skill by name; it appears in every target on the next build, and `check_freshness` flags any orphan or leak.

## Phases

### Phase 0 — Ratify

Settle D1–D8 (defaults: the recommendations, with D5 and D8 already ruled). File the ledger item, put its id in this document's frontmatter and add the `plan:` ref on the item, flip `status` to `active`. Nothing else in this phase.

### Phase 1 — Skeleton, the environment ladder, and the PDF reference

1. Write `templates/skills/pipelex-synthetic-inputs/SKILL.md.j2`: frontmatter (name, trigger-rich description, the shared `frontmatter.md.j2` include, no MCP tools), the contract table, the rules, the **Environment** section carrying the D8 ladder with its preflight commands and the failure table, the content-first step, the dispatch table (`pdf` → `references/pdf.md`, `png` → `references/png.md`, `docx`/`xlsx` → `references/office.md`), the verify step, the report shape, and a "when called from `pipelex-inputs`" paragraph that says to return the path — or no path, with the reason, on a graceful failure — and stop.
2. Write `references/pdf.md` by porting the `mthds-inputs` recipes — basic canvas, multi-page Platypus, professional report with `Table`/`TableStyle` — in the runner-line block form of D3, checked against reportlab 5.0.1 (the API used is unchanged, but the check is the point). Add the content-first guidance in PDF terms: which recipe fits which brief (a letter or memo → canvas; a multi-section report → Platypus; anything with line items → the table recipe, composed with Platypus paragraphs for the header block). Keep the last-resort URL and the `%PDF` verify step.
3. `make build`, confirm every target carries the skill and the copied `references/`, `make agent-check`.

**Phase 1 landed on 2026-09-02.** The skill template, `references/pdf.md` and `references/office.md` (the DOCX/XLSX text, already moved so the skill's Reference list has no dangling link — `pipelex-inputs` keeps its copy until Phase 3 replaces it) render into every target with the references copied; `make agent-check` and `make agent-test` pass. Every PDF recipe was executed under reportlab 5.0.1 before the build — canvas, Platypus, table and the composed invoice all produce a `%PDF-` file with the expected page count, and the invoice totals reconcile. The composed line-item recipe is an addition to the ported set: it is the shape of the most common document brief and reuses the two Platypus recipes without new API surface.

### Phase 2 — The PNG reference

1. Write `references/png.md`: the D5 category table and the "not covered" line, the shared runner line (`uv run --quiet --with pillow --with matplotlib --with numpy python << 'PYEOF'`), the seed, the size defaults, the font helper (D6), and one complete recipe per category, each producing a file from a small content block at the top of the script that the agent edits (the data for a chart, the nodes and edges for a diagram, the lines and table rows for a document, the sections and rows of a screen). The `document_scan` recipe carries the "scanner" post-process as a named function so a later category can reuse it.
2. Run every recipe locally, view each output, and iterate until each reads as its category to a vision model — the practical test is to describe each generated image back and check the description matches the brief.
3. `make build`, `make agent-check`.

**Phase 2 landed on 2026-09-02.** `references/png.md` carries all four categories of D5, each executed and looked at before the commit under Pillow 12.3.0, matplotlib 3.11.1 and numpy 2.5.2, and each rendered again from the block as extracted from the Markdown — which is how Phase 4 will run them. `make build`, `make agent-check` and `make agent-test` pass; the reference is copied into all three targets.

- **`chart`** — one matplotlib script with `bar`, `line`, `pie` and `scatter` as branches of a `KIND` field, so the agent edits one line rather than choosing a recipe. `figsize=(WIDTH / DPI, HEIGHT / DPI)` plus `fig.tight_layout()` gives exactly the declared pixel size; `bbox_inches="tight"` would break that and the reference says so.
- **`diagram`** — a node list with explicit grid positions and an edge list; the layout, the border-clipped arrows and the arrowheads are computed. Roles (`start`, `step`, `decision`, `end`) colour the boxes.
- **`document_scan`** — an A4-at-150-dpi invoice whose totals are computed from the items, then `scannerize()`: seeded skew, paper tint, grain, soft vignette. The post-process is a plain function on an image, so any other recipe can end with it, and the reference gives dial settings for a clean office scan and for a bad phone photo.
- **`screenshot`** — window chrome, sidebar, header with an action button, stat tiles, and a `LAYOUT` field choosing a status-badged table or a card grid. Both branches were rendered and viewed.

Three things the work taught, all now written into the files rather than only here:

- **Character-count wrapping overflows boxes.** `textwrap.wrap(label, width=18)` spilled every node label past its box edge; the recipes wrap on `draw.textlength` instead. The screenshot table is the one place that still lays out on fixed column shares rather than measurement — a deliberate simplification, called out in the reference with the cure (widen the share, do not shorten content the method must read).
- **matplotlib writes `RGBA`, Pillow writes `RGB`.** The chart recipe's file is `RGBA` and there is no flag to change it, so `SKILL.md`'s Step 5 verify line and the reference both name both as correct. Converting in the recipe would have been code added only to satisfy a sentence.
- **A collector rule for Phase 4.** The PNG "Verify" block starts with `uv run`, like every recipe, but it is a template carrying `<name>` rather than a runnable recipe — extracting it fails on a file that does not exist. The Phase 4 collector must take blocks whose first line starts with `uv run` **and** which contain no `<name>` placeholder. The equivalent block in `pdf.md` starts with `head -c 5` and so was never at risk; the rule makes both safe.

**Checkpoint A** — the skill exists and works standalone in every target.

### Phase 3 — Wire `pipelex-inputs`

1. In `templates/skills/pipelex-inputs/SKILL.md.j2`: replace the `native.Image` and `native.Document` rows' synthesis method with "delegate to `pipelex-synthetic-inputs`"; rewrite "Generate File Inputs" as the delegation (D7), spelling out the request fields, that the returned path goes into `inputs.json` as a bare path string, and that a graceful failure (D8, last rung) leaves that input unfilled with the reason in the report — the rest of the inputs flow continues; delete Document Generation and the Fallback Strategy block; fix Example 2 to show the delegation; add the skill to the Reference list.
2. Move the DOCX/XLSX text into `references/office.md` (D4).
3. Tests in `tests/unit/test_gen_skill_docs.py`, `TestSyntheticInputsSkill`, parametrized over every target like the neighbouring classes: the skill renders in every target; `references/pdf.md`, `png.md` and `office.md` are present in every output directory; the rendered `SKILL.md` states the no-AI rule, the package allowlist, and the ask-before-installing-a-tool line; the rendered `pipelex-inputs` names `pipelex-synthetic-inputs` and no longer contains a "### PDF Documents" heading; the platform branch of D7 renders the right sentence per target; the new skill declares no MCP tool and is absent from `MCP_SKILLS`.
4. `make build`, `make agent-check`, `make agent-test`.

### Phase 4 — Executed recipes and the ladder (D3, D8)

1. `tests/recipes/test_recipes.py`: collect the fenced ```` ```bash ```` blocks whose first line starts with `uv run` from `skills/pipelex-synthetic-inputs/references/*.md`, one test per block (ids from the file and the nearest heading), substitute `<output_dir>` with `tmp_path`, run under `bash`, assert the file the block names exists, is non-empty and starts with the right magic bytes; for PNG, open it with Pillow (available in the test's own `uv run`) and assert the dimensions the recipe declares. Mark `@pytest.mark.recipes`; skip when `uv` is not on `PATH`.
2. The **venv rung** gets its own test: run the `SKILL.md` venv-creation and install commands with `XDG_CACHE_HOME` pointed at `tmp_path`, then run one PDF recipe and one PNG recipe with the runner line rewritten to the venv's interpreter, exactly as the ladder says. This is the proof that the second rung is real and that the runner line is genuinely the only thing that changes.
3. The **preflight** commands from the Environment section run as a test too, so a stale package name in the `--with` list fails here rather than on a user's machine.
4. Register the marker in `pyproject.toml`; make the default `pytest` run deselect it (`-m "not recipes"` in `addopts`) so `make test`, `make agent-test` and `gha-tests` stay fast; add `make test-recipes`.
5. Run it, fix whichever recipe it catches.

### Phase 5 — Documentation, changelog, dogfood

1. `README.md` "What's inside": add the skill; note it is MCP-free and installs its own packages through `uv` or an isolated venv. `CLAUDE.md`: the structure tree, the skill list, and a sentence under "Key dependency" saying the synthetic-inputs skill depends on nothing but Python and `uv`, and creates a venv when `uv` is absent. `docs/decisions.md`: one entry — "File synthesis is its own skill: no AI, only what renders to standard, permissive packages only, prose recipes guarded by execution, an environment ladder that asks before installing a tool" — with the D2/D3/D5/D8 rationale in a paragraph each and the date. `docs/build-targets.md`: no change unless Phase 4 touched the build. `CHANGELOG.md` under `## [Unreleased]`: an **Added** entry for the skill and a **Changed** entry for `pipelex-inputs` delegating file generation (breaking for anyone who relied on the old inline section — say "breaking").
2. Dogfood end to end from the main checkout's marketplace pointing at this worktree: `make build`, `/reload-plugins`, then on a method that takes a document and one that takes an image, run `/pipelex-inputs` in synthetic mode and confirm the delegation fires, the files land in `<output_dir>/inputs/`, `mthds_prepare_inputs` uploads them, and the run offer follows. Then `/pipelex-synthetic-inputs` standalone with a bare brief. Then the ladder's failure posture, by invoking the skill with `PATH` stripped of `uv` and once more with `python3` hidden as well, and reading the message it produces as the user would.
3. Repeat on Codex (`make codex-use-local`, `make codex-refresh`) at least for the standalone path.

**Phases 3, 4 and 5 landed on 2026-09-02.** `pipelex-inputs` delegates (its Document Generation section and Fallback Strategy block are gone, Example 2 is a chart-reading method that names what would have happened had it asked for a photograph, and `TestSyntheticInputsSkill` pins the identity rules, the ladder, the MCP-free posture and the per-platform delegation sentence). `tests/recipes` executes every shipped recipe on both rungs, opt-in behind `make test-recipes`. README, CLAUDE.md, `docs/decisions.md` and the changelog are updated; `docs/build-targets.md` needed nothing, since the build was untouched.

Three things the dogfood changed, and one it could not do here:

- **The diagram recipe overflowed its boxes on a tall graph.** Box height is derived from the row count, so a seven-row escalation flow gave 45px boxes that a two-line label spilled out of, top and bottom — invisible in the four-row default. The recipe now sizes labels with `fit_label()`, which steps the font down until the wrapped label fits both ways, and the reference says a diagram set in 11px is telling you the graph wants fewer nodes. The four-row default renders identically to before.
- **`pip install` printed a version-upgrade notice** on the venv rung, which reads like an error to an agent scanning the output. The command carries `--disable-pip-version-check` now.
- **The letter variant works exactly as the reference claims** — dropping the item loop and the totals block leaves nothing dangling — and the harsher scanner dials (`angle=1.4, grain=11, blur=1.0`) read as a phone photo while staying legible. The reference gained one line saying `SELLER`/`BUYER` are then simply the sender and the addressee.
- **Not done here: the plugin-install dogfood.** The `pipelex-plugins` marketplace on this machine points at the main checkout, so the branch's skill cannot be loaded in a session without repointing global config and reloading plugins — a gesture that belongs to the person at the keyboard. What that pass still has to check is the delegation firing end to end from `/pipelex-inputs`, and the same standalone path on Codex (`make codex-use-local`, `make codex-refresh`). Everything the skill's own prose promises has been executed and looked at.

**Checkpoint B** — ready for a PR against `dev` with `Closes <item>` in the body. Version stays at `0.5.0` and the entries stay under `[Unreleased]` until the `/release` skill cuts the next plugin release; the skill's "v0.1.0" is the scope named above, not a number in a manifest.

## Later versions (out of scope now)

- **Deeper office formats**: DOCX with headings, tables and images; XLSX with several sheets and formulas; CSV/JSON/Markdown text files as `native.Text`/`native.JSON` fixtures.
- **Image variants**: JPEG and WebP (one `save` argument away once PNG exists), multi-page TIFF for scanner-shaped methods, SVG diagrams.
- **`handwritten`, done properly**: feasible without AI only with a real handwriting typeface under a permissive licence (an OFL font bundled as a static asset) rendered onto the `document_scan` page. Deferred until that asset question is settled; not approximated meanwhile.
- **HTML pages** for `native.Html` / web-page documents.
- **An opt-in AI path for `photograph`**: a hosted Pipelex image-generation method run through `mthds_run` — the old `synthesize_image` idea reborn on the MCP workshop. It costs money and needs a key, so it would be a separate, explicitly requested mode, never a fallback of the no-AI skill.
- **Shipped helpers** (D3, second variant) if the recipes keep repeating the same font loader and scanner post-process.

## Risks and open questions

- **First-run latency.** `uv run --with matplotlib` downloads tens of megabytes the first time on a machine; afterwards it is cached. The preflight is where that cost lands, and the skill says so once. If this proves annoying, `chart` can fall back to a Pillow-drawn bar chart, at some loss of realism.
- **Cross-skill invocation on Codex and Vibe** is "read the file and follow it" (D7). Verify during Phase 5 dogfood that the relative path resolves from the installed cache copy on Codex (`$CODEX_HOME/plugins/cache/…`), where the plugin directory is copied whole, so it should.
- **The venv rung on locked-down machines.** A corporate Python may forbid `pip install` to any location, or block PyPI. The ladder's answer is the last row of D8 — report and offer — and the Phase 5 dogfood with `uv` hidden is what checks that the message is usable rather than a stack trace.
- **Last-resort URL rot.** The PDF URL inherited from `mthds-inputs` (`w3.org`) has been stable for years; the recipe test does not fetch it. Images have no URL fallback by decision (D5).
- **reportlab 5** shipped recently (5.0.1 at the time of writing); the ported recipes use canvas and Platypus APIs that did not change, and the executed-recipe test is what proves it rather than this sentence.
