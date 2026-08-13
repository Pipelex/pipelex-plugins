# support_digest — a worked PipeFunc example

A weekly support digest: aggregate the week's tickets, find the SLA breaches, read the tickets for themes, recommend actions, render the result. Six pipes — **three `PipeFunc`, two `PipeLLM`, one `PipeSequence`**.

It exists to make [`writing-pipe-funcs.md`](../../templates/skills/shared/writing-pipe-funcs.md.j2) concrete: every rule in that reference is exercised here, and the bundle was validated and executed against the `pipelex` runtime rather than written from memory.

## The graph

```
build_support_digest            PipeSequence   tickets: TicketRow[]  →  SupportDigest
  ├─ compute_ticket_stats       PipeFunc       → stats
  ├─ detect_sla_breaches        PipeFunc       → breaches
  ├─ summarize_themes           PipeLLM        → themes
  ├─ recommend_actions          PipeLLM        → actions
  └─ assemble_digest            PipeFunc       → digest
```

The split is deliberate: the two PipeLLMs do the judgment (what themes are these, what should we do), and the three PipeFuncs do everything that must be exactly right — medians, SLA thresholds, table rendering. A model should not be guessing at arithmetic.

## The files

| File | Why it is its own file |
|---|---|
| `main.mthds` | the bundle: concepts and the six pipes |
| `compute_stats.py` | `compute_ticket_stats` + `detect_sla_breaches` — both aggregate the same ticket frame, so they belong together |
| `_tickets.py` | the shared frame builder and the SLA table. No pipe funcs here; the underscore says "nothing registers from this module" |
| `assemble.py` | `assemble_digest` — reads no raw tickets, does formatting only |
| `inputs.json` | five tickets to run it with |

This is the reference's file-organization rule applied honestly. Three functions is not automatically three files: two of them share a frame and sit together, and the one with a different job gets its own.

## Things to notice

**Return types come from `structures`.** Every pipe func returns the structure class of its pipe's `output` concept, imported by concept code from the codegen'd module:

```python
from structures import TicketStats

@pipe_func()
async def compute_ticket_stats(working_memory: WorkingMemory) -> TicketStats:
```

**A list output is a `ListContent`.** `detect_sla_breaches` declares `output = "SlaBreach[]"` and returns `ListContent[SlaBreach]`.

**Sibling imports work.** `compute_stats.py` does `from _tickets import ...`; every directory holding a `.py` in the bundle is on the path when registration runs.

**Only allowed libraries.** `pandas` and the standard library. No network, no other dependency.

## `structures.py` and `codegen.lock`

Exactly what `POST /v1/codegen` returned for this bundle (`kind: types`, `target: python-structures`), stamp and lock included. The same bytes come out of `pipelex codegen types --target python-structures` locally — identical `crate_fingerprint` and `content_hash` — so the CLI and the hosted API are one engine reached two ways.

The concepts are declared as one-liners in `[concept]` and their shapes live in these generated classes, which is what lets the pipe funcs import `TicketStats` and satisfy the return-type check. Never hand-edit the file: it is stamped, regeneration overwrites it, and `pipelex codegen check` reports drift. Subclass in a sibling module if you need custom validation or computed properties.

## Running it locally

`structures.py` is already here, so nothing to generate:

```bash
pipelex validate bundle .
pipelex run bundle . --pipe compute_ticket_stats -i inputs.json
```

The two `PipeLLM` steps need inference configured; the `PipeFunc` steps do not.

To regenerate after changing a concept, use the API — it reads `.mthds` only and never imports your Python, so it works on a bundle that already declares PipeFuncs:

```bash
curl -sX POST https://api-dev.pipelex.com/v1/codegen \
  -H "Authorization: Bearer $PIPELEX_API_KEY" -H 'Content-Type: application/json' \
  -d "$(python3 -c 'import json;print(json.dumps({"kind":"types","target":"python-structures","files":[{"content":open("main.mthds").read(),"source":"main.mthds"}]}))')"
```

Write `artifacts[0].content` to `structures.py` and `lock` to `codegen.lock`. The local `pipelex codegen types --target python-structures` emits the same bytes, but in `direct` mode it validates `function_name` against the registry at load, so it cannot run on a bundle whose PipeFuncs are already declared.

## What validation will not tell you

`pipelex validate bundle` here runs the full local checks — the functions are in this process, so their existence and return types are verified. **The hosted API skips both**, because the Python is not in the runner's process. On the API this bundle would validate clean even with a missing function, a wrong return type, or a forbidden import, and fail only at run time. Check the pipe funcs by hand before shipping.
