---
name: pipelex-organize
description: Reorganize a designed method bundle into a clear, browsable layout. Use when a top-down design left one .mthds file per refined signature and the library should be regrouped into coherent module files (or a single file, when the method is simple) — auto-invoked at the end of /pipelex-design once the runnable verdict holds, or when the user says "organize the bundle", "organize the method", "regroup the files", "clean up the bundle layout". Pure reorganization — never changes what the method does.

---

# Organize a designed MTHDS bundle

Top-down design (`/pipelex-design`) is deliberately additive: every refinement **adds** a new `<code>.mthds` file, and satisfied `PipeSignature` headers linger in the files that declared them. The finished library is correct but shaped by construction history — one file per pipe, contracts duplicated as stale headers, no relationship between file layout and how the method reads.

This skill regroups that library into a layout organized for **comprehension** — the way source code is spread across files in any language: related pipes gathered into one file per coherent unit, so a reader (human or agent) can discover the method progressively — open the root to see the contract and the top-level flow, then descend into just the module they care about. **The layout scales with the method:** a simple method fits entirely in `main.mthds`; a complex method with many pipes gets one file per subtree or functional area. Consolidation into fewer files is the usual *effect*, but the goal is grouping, not a single file.

It is a **content-preserving transformation** — the method's semantics never change, and the validation verdict before and after must be identical. That equivalence is proven with the `mthds_validate` tool, never assumed.

## Requirements — the Pipelex MCP tool

Equivalence is checked through the **`mthds_validate`** tool, served by the plugin's `pipelex` MCP server. It is required — this skill never reorganizes without proving the verdict is preserved.

- **If the tool is absent from this session** (the MCP server isn't connected), STOP and tell the user in one line: *"The Pipelex MCP server isn't connected — check the plugin's MCP connection; the plugin manifest must point at a running `pipelex-mcp` server."* Do not touch the bundle files without validation available.
- **If a call returns `status: "error"` with an error of class `config`** (server unreachable, upstream API misconfigured, auth), STOP the same way and surface the error's `hint`. Never reorganize unvalidated.
- No API key is needed on your side — the MCP server authenticates to the validation API itself.

**Formatting is automatic.** Every write of a `.mthds` file triggers the plugin's validation hook: it lints, rewrites the file in canonical formatting, and blocks on syntax errors. Don't hand-format, and re-read a file before editing it again after the hook reformatted it.

---

## What this skill may and may not change

**May change (layout only):**

- Which file a concept or pipe declaration lives in, and the file names of non-root files.
- The order of declarations.
- Dropping a `PipeSignature` header whose code has a concrete definition anywhere in the library (the definition supersedes it — the header is construction scaffolding).
- Absorbing per-file `domain = "..."` membership lines into whichever files survive.

**Must NOT change (semantics):**

- Pipe codes, concept codes, the `domain`, `main_pipe`, `description`, `system_prompt`.
- Any pipe's `inputs`/`output` contract, `type`, prompts, steps, branches, outcomes, or any other body field.
- Any concept's `description`, `refines`, or structure fields.
- **Unsatisfied signatures.** A `PipeSignature` with no concrete definition (an early-stopped scaffold's backlog) is kept — deduplicated to one header per code, never dropped. The bundle stays its own todo list.

If reorganizing seems to require a semantic edit (a rename, a contract fix, a missing declaration), STOP and report it — that is `/pipelex-design` territory, not organization.

---

## The target layout — group for comprehension

Think of it exactly like organizing source code across files. The unit of grouping is a **coherent piece of the method**: a controller together with the sub-pipes only it wires (its private subtree), or a functional area several small pipes serve.

- **Root `main.mthds` is the entry point and table of contents.** It carries the bundle header (`domain`, `description`, `main_pipe`, `system_prompt`), the boundary concepts (the client-facing contract), and the main pipe. Reading it alone tells you what the method does, what goes in and out, and what the top-level steps are. **The root file is always named `main.mthds`** unless the user says otherwise — a root inherited under another name (e.g. a legacy `bundle.mthds`) is renamed as part of organizing.
- **One file per module.** Each top-level subtree (or clearly-named functional area) gets its own `<snake_case_name>.mthds` file — named after the controller that heads it or the area it implements — containing that subtree's pipes in flow order (controller first, then the pipes it wires) plus the intermediate concepts introduced for that subtree. Each non-root file starts with `domain = "<same_domain>"` only.
- **Shared declarations go up.** A pipe or concept used by several modules lives in the root file (or, if the shared surface is large, a dedicated `shared.mthds`), never duplicated.
- **Scale the file count to the method, in both directions.** A simple method — a handful of pipes — belongs entirely in `main.mthds`; don't scatter it. A complex method with tens of pipes needs several module files; don't cram it into one. And never keep a file per pipe: that is the construction sprawl this skill exists to clean up. Each file should read like a chapter, not a line.
- **Progressive discovery is the test.** An agent that needs to understand or modify one step should be able to read the root plus one module file and have everything relevant — nothing important hidden in an unrelated file, no file that can't be understood without opening all the others.

Within every file: satisfied signature headers are dropped; a still-pending signature (scaffold case) sits in the module of the controller that wires it.

---

## Procedure

### Step 1 — Baseline verdict

1. Gather **all** `.mthds` files in the bundle directory (e.g. `pipelex-wip/<bundle_dir>/`).
2. Call `mthds_validate` with `files: [{content: <file content>, uri: <path relative to the bundle dir>}]` for every file.
3. Record the **baseline**: `is_valid`, `is_runnable`, and the exact `pending_signatures` set.

Branch on the structured verdict:

- `is_valid: true` → proceed (runnable or scaffold — both are organizable).
- `is_valid: false` → STOP. Do not reorganize a broken library — report the verdict and point to `/pipelex-design` to fix it first. Organization must start from, and preserve, a passing verdict.
- `status: "error"` → class `input_domain`: fix the call; class `config`: stop per the rule above; class `runtime`: report and retry once before stopping.

### Step 2 — Plan the layout, compose the files

1. **Map the structure**: from the main pipe down, identify the subtrees and which pipes/concepts belong to each; identify shared declarations.
2. **Decide the file set** using the target-layout rules above — possibly just `main.mthds`, possibly root + several module files. State the plan in one line (e.g. `main.mthds + extract.mthds + analyze.mthds + report.mthds`).
3. **Compose every file in memory** (do not write yet): copy each declaration verbatim into its assigned file, one declaration per concept, one entry per pipe, ordered for top-down reading within each file.

### Step 3 — Prove equivalence before touching disk

Call `mthds_validate` with **the composed candidate set** (all planned files, nothing else). The verdict must match the baseline exactly: `is_valid: true`, the same `is_runnable`, and an identical `pending_signatures` set.

- **Match** → proceed to Step 4.
- **Mismatch or failure** → the composition dropped or duplicated something; fix the *composition* (never the semantics) and re-validate. If it still fails after two fix attempts, STOP, leave the original layout untouched, and report the discrepancy.

### Step 4 — Swap the layout

Only after the candidate verdict matches:

1. **Write every file of the new layout** (Write tool — the hook lints and reformats each in place; a new file may legitimately reuse an old file's name, e.g. `main.mthds`).
2. **Delete every `.mthds` file that is not part of the new layout.** Delete only `.mthds` files; leave `inputs.json`, input files, and anything else in the directory alone.
3. **Confirm on disk**: re-gather the directory's `.mthds` files and validate once more — this catches anything the formatting hook changed.

### Step 5 — Report

One short summary: the layout (which files, what each contains, one line per file), the preserved verdict (runnable, or valid scaffold with its pending list). No approval prompts — by the time you report, the bundle is organized and proven equivalent.

---

## Autonomy

This skill is **fully automatic** — no per-step approval, including the layout decision (announce it, don't ask). It is designed to be auto-invoked by `/pipelex-design` at delivery time, and it can be invoked directly on any designed bundle directory. The only stops are the ones above: missing/misconfigured MCP tool, a failing baseline verdict, or a candidate that cannot be proven equivalent. If the user has expressed a layout preference (single file, specific grouping), honor it — the equivalence proof works the same for any layout.
