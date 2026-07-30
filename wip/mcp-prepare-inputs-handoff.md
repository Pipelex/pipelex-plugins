# Handoff: adapt pipelex-plugins to pipelex-mcp's mthds_prepare_inputs + explicit-default flip

## Background

`pipelex-mcp` (sibling repo) has a release staged under `[Unreleased]` in
`../pipelex-mcp/CHANGELOG.md` (adopting `@pipelex/sdk` 0.9.0) that changes the
MCP surface this plugin's skills depend on:

1. **New tool: `mthds_prepare_inputs`.** Turns a pipe's *filled* inputs
   run-ready by uploading file-bearing values (local paths, `data:` URLs,
   inline bytes) to Pipelex storage and rewriting them to `pipelex-storage://`
   references that `mthds_run` accepts. On the bundled **local workshop**
   server (`npx -y @pipelex/mcp@latest` — what this plugin's skills always run
   against), uploads work with the user's own `PIPELEX_API_KEY`. It sits
   between `mthds_inputs_template` (empty template) and `mthds_run` (execute):
   template → fill → **prepare** → run.
2. **Breaking: `mthds_inputs_template`'s `explicit` now defaults to `true`.**
   Any call that doesn't pass `explicit: false` now gets the ceremonial
   `{concept, content}` envelope per input instead of the light/compact shape
   (bare example values) the skills currently assume.

Read these as ground truth before touching anything:
- `../pipelex-mcp/CHANGELOG.md` → `## [Unreleased]` (both entries above, verbatim)
- `../pipelex-mcp/SPEC.md` → "Inputs Template Scope (`mthds_inputs_template`)"
  and "Prepare Inputs Scope (`mthds_prepare_inputs`)" — full input/output
  shapes, error taxonomy, the "Signature-driven asset identification" table
- `../pipelex-mcp/SPEC.md` → the prepare-then-run example flow (search
  "After filling the `mthds_inputs_template` output")

pipelex-mcp is holding its release until this repo is either updated to match
or there's an explicit decision that the light-shape default isn't worth
chasing right now — check back with the pipelex-mcp release owner once done,
don't merge silently.

## What's actually broken today

`templates/skills/pipelex-inputs/SKILL.md.j2` (source of truth — rendered into
`pipelex/skills/pipelex-inputs/SKILL.md`, `pipelex-codex/...`,
`pipelex-vibe/...`; never edit the generated copies directly) is written
entirely around:
- The **light** template shape as `mthds_inputs_template`'s default (Step 2,
  the "Value shapes" section, all four strategies write bare/compact values).
- An `## Offer to run` gate that requires every file-ish value to already be a
  reachable `https` URL, explicitly telling the agent NOT to offer to run when
  local paths are present ("state that the method can be run once those files
  are hosted at reachable URLs"). That restriction is now obsolete on the
  workshop — `mthds_prepare_inputs` is exactly the tool that turns local paths
  into runnable references.
- No mention of `mthds_prepare_inputs` anywhere; its frontmatter tool
  allowlist doesn't include it either.

`templates/skills/pipelex-design/SKILL.md.j2` (~line 157) and
`templates/skills/pipelex-edit/SKILL.md.j2` call `mthds_inputs_template` too,
but only to *show* the template to the user (never fill/run it) — lower
stakes, but their prose ("the defaults resolve the method's `main_pipe` and
return the light template") is now factually wrong.

`docs/decisions.md` (~line 53) and `CLAUDE.md`'s "Key dependency" section both
enumerate the plugin's declared MCP tools without `mthds_prepare_inputs`.

## Required changes

### 1. Decide how to handle the `explicit` default flip, then apply it everywhere

Two options — pick one, state the reasoning in the commit/PR body:

- **(a) Pin `explicit: false`** on every `mthds_inputs_template` call the
  skills make, preserving today's light-shape behavior and prose unchanged.
  Minimal diff.
- **(b) Adopt the new ceremonial default**, rewriting Step 2's example
  template, the "Value shapes (light format)" section, and all four
  strategies to fill `content` inside the `{concept, content}` envelope and
  preserve `concept`. More churn, but exposes concept-identity info the flip
  was designed to give agents (useful for matching synthetic data to concept
  names, and for structured/composite inputs).

**Recommendation: (a)** for this pass — smaller, lower-risk, unblocks the
pipelex-mcp release. Nothing about the upload feature depends on this choice:
`mthds_prepare_inputs` accepts both shapes identically either way (SPEC.md:
"Both filled template shapes are accepted... An envelope's inner content is
interpreted exactly as the compact value would be"). Revisit (b) later as its
own focused pass if concept-identity turns out to matter for synthetic
generation quality.

Apply the choice consistently across `pipelex-inputs`, `pipelex-design`, and
`pipelex-edit`'s templates — don't leave one skill on the old assumption.

### 2. Add `mthds_prepare_inputs` as a real step in `pipelex-inputs`

- Add `mcp__plugin_pipelex_pipelex__mthds_prepare_inputs` to the skill's Claude
  `allowed-tools` frontmatter, alongside the existing four.
- Add it to the "Requirements" section as **required** (not optional like the
  run family) whenever the assembled inputs contain any file-ish value that
  isn't already an `http(s)` URL or `pipelex-storage://` reference — same
  stop-on-`config`-error discipline the section already specifies for the
  other tools.
- Insert a new step between "Assemble and Save" and "Finish" — applies to
  Synthetic, User Data, and Mixed strategies (Template strategy is the
  exception: it has no real values yet, nothing to prepare). After
  `inputs.json` is assembled with real values, call `mthds_prepare_inputs` with
  the same target (`files`/`method_id`, and `pipe_ref` if Step 2 passed one —
  same drift-safety reasoning the "Offer to run" section already applies to
  by-id targets) plus the filled `inputs`. Rewrite the saved `inputs.json`
  with the returned `inputs` (now `pipelex-storage://` for anything that was
  local) and report the `uploads` list to the user (e.g. "2 files uploaded to
  Pipelex storage"). Keep the local copies in `<output_dir>/inputs/` for the
  user's own reference — only the `inputs.json` values change.
- Branch on the result per SPEC's "Verdict discipline": unlike
  `mthds_inputs_template`, **there is no produced-invalid arm** — an
  unresolvable closure is `status: "error"`, `class: "input_domain"` (not a
  `validation_errors[]` list). Route that to `mthds_validate` /
  `mthds_inputs_template` for repair, per SPEC's stated recovery path.
  `class: "config"` stops the same way Requirements already specifies.
  `class: "runtime"` reports and retries once.
- **Rewrite `## Offer to run`.** Drop the blanket "local paths block offering
  to run" rule. New rule: offer once `mthds_prepare_inputs` has succeeded on
  the final inputs (local paths, `data:` URLs, inline bytes are all fine now —
  they were uploaded in the step above). The only remaining reasons not to
  offer: unfilled placeholders (Template strategy), or a prepare failure.
- Update "Complete Examples" (Example 3, invoice PDF) to show the prepare call
  and the resulting `pipelex-storage://` value — a local `inputs/invoice.pdf`
  path is exactly the case that changes.

### 3. Update `pipelex-design` / `pipelex-edit` prose

Only fix the "return the light template" phrasing to match whatever choice you
made in (1) — they don't fill or run inputs, so they don't need
`mthds_prepare_inputs`.

### 4. Update cross-cutting docs

- `CLAUDE.md` → "Key dependency": add `mthds_prepare_inputs` to the tool list
  and a one-line description of what it's for.
- `docs/decisions.md` (~line 53): same tool-list update.
- `CHANGELOG.md`: new `[Unreleased]` entry describing the skill changes
  (breaking, since behavior/prose changes) — match this repo's existing
  Keep-a-Changelog style.

### 5. Regenerate and verify

```bash
make build           # regenerate pipelex/, pipelex-codex/, pipelex-vibe/ — never hand-edit those
make check           # or make agent-check — full quality gate
make agent-test
```

Diff the generated `pipelex/skills/pipelex-inputs/SKILL.md` (and the
codex/vibe siblings) to confirm they actually reflect the new step and tool
list before committing — don't just trust the template edit.

## Out of scope / don't touch

- The hosted console's pass-through-only upload behavior is irrelevant here —
  this plugin only ever talks to the bundled **local workshop** launcher,
  where uploads are always allowed. Don't add console-specific branching.
- Don't touch the `mthds_run` family's own prose beyond what the offer-to-run
  gate above needs — its contract didn't change.
- Plugins-side change only; don't touch anything under `../pipelex-mcp/`.
