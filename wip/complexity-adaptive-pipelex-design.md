# Complexity-adaptive `pipelex-design`

## Goal

Keep top-down contract reasoning, but stop forcing every method through a
signature-only scaffold and one-file-per-refinement construction history.

Use the lightest workflow that preserves confidence:

- Build a simple, fully understood method directly as a runnable, coherent
  bundle.
- Use signature-driven stepwise refinement when the method is structurally
  deep, uncertain, intentionally incremental, or likely to benefit from valid
  intermediate checkpoints.
- Allow a direct design to graduate to stepwise refinement if hidden
  complexity appears.

This is a workflow change, not a relaxation of validation. Every completed
method must still pass `mthds_validate` with `is_valid: true`,
`is_runnable: true`, and no pending signatures.

## Design decisions to encode

- Separate **top-down reasoning** from **signature materialization**. Determine
  the client contract first in both modes, but create `PipeSignature` artifacts
  only when they provide useful decomposition or resumability.
- Choose the mode automatically. Announce the inferred client contract as
  today, but do not ask the user to select a construction strategy.
- Prefer direct construction when the complete graph can be confidently
  authored without placeholders. Strong signals include:
  - a single concrete operator; or
  - one top-level controller whose children are concrete leaf operators;
  - no nested controllers;
  - no unresolved branching, iteration, wiring, or ownership decisions;
  - boundary and intermediate concept shapes can all be fixed before writing;
  - the result has a natural coherent layout, normally one `main.mthds`.
- Prefer stepwise refinement when any useful boundary remains unresolved.
  Strong signals include:
  - nested controllers or multiple structural layers;
  - uncertain sub-pipe contracts or intermediate concept ownership;
  - shared concepts whose shapes depend on consumers in different branches;
  - a large flow that benefits from independent review checkpoints;
  - a user request for a scaffold, partial design, or resumable intermediate
    result.
- Treat pipe count as a secondary signal, not a hard threshold. “One
  controller” is a strong fast-path signal, not an unconditional rule.
- If the classification is borderline, choose the simplest path that can be
  written completely and validated confidently. Escalate to signatures as soon
  as placeholders or speculative contracts would otherwise be needed.

## Implementation plan

### 1. Reframe the canonical design skill

- Edit `templates/skills/pipelex-design/SKILL.md.j2`, never the generated skill
  copies directly.
- Update the frontmatter description, title, introduction, and autonomy text so
  they describe complexity-adaptive design rather than mandatory stepwise
  refinement.
- Preserve the current MTHDS scope, MCP availability/error handling, structured
  validation verdict handling, contract rules, and concept-shape rules.
- Add a short decision section before any files are written. Make its tests
  behavioral and observable rather than relying on vague labels such as
  “small” or “easy.”

### 2. Add the direct-build workflow

- Determine and announce the root inputs, output, and semantics before writing.
- Design the complete shallow graph and all concept shapes before creating the
  artifact.
- Write a coherent runnable bundle directly, normally as
  `pipelex-wip/<bundle_dir>/main.mthds`, containing:
  - bundle metadata and `main_pipe`;
  - fully specified boundary and intermediate concepts;
  - the concrete main operator/controller;
  - all concrete leaf operators;
  - no temporary signatures.
- Validate the whole bundle after the coherent write. Fix ordinary syntax or
  semantic errors in place and revalidate.
- If validation or design reasoning exposes unresolved structural boundaries,
  switch to the stepwise workflow instead of inventing speculative contracts.
  Document how to perform this transition without leaving duplicate concepts or
  conflicting pipe definitions.
- Skip `pipelex-organize` when the direct result is already coherent. Continue
  through the common runnable gate, input-template projection, graph/text-flow
  presentation, and `/pipelex-inputs` handoff.

### 3. Retain and scope the stepwise workflow

- Keep the current signature-first, additive, breadth-first refinement loop for
  complex or intentionally incremental methods.
- Move its construction-specific invariants under that mode:
  - one definition file per refinement;
  - additive writes;
  - pending signatures as the backlog;
  - validity and resumability after every layer;
  - organization after convergence.
- Keep early-stop scaffolds exclusive to this mode and preserve their current
  validation and resumption behavior.
- Make clear that contract stability and single declaration of concept shapes
  apply in both modes, while “the root file is written once” and
  “one concrete definition per file” apply only to stepwise construction.

### 4. Make existing-method re-entry adaptive too

- Preserve baseline validation before every structural edit.
- For a shallow method whose affected graph and propagated contracts can be
  understood together, edit the smallest coherent region directly and restore
  the runnable verdict.
- For nested, uncertain, cross-module, or intentionally staged changes, retain
  the current reopen-to-signatures and re-refine workflow.
- Preserve the rule that a contract change propagates through parent wiring and
  that a concept reshape includes every field-reading consumer.
- Run `pipelex-organize` only when re-entry produced a construction-shaped
  layout that needs regrouping.

### 5. Reconcile adjacent skill and repository documentation

- Update `templates/skills/pipelex-organize/SKILL.md.j2` so it no longer claims
  all `/pipelex-design` runs are additive or that organization is mandatory at
  every successful delivery. Keep it auto-invoked for converged stepwise
  layouts and available on explicit request.
- Review `templates/skills/pipelex-edit/SKILL.md.j2` for wording that assumes
  re-entry always reopens signatures; change only statements made inaccurate by
  the adaptive workflow.
- Update the skill summary in `README.md`.
- Update the `pipelex-design` ownership/re-entry statement in
  `docs/decisions.md` so it records both direct and signature-driven re-entry.
- Search again for “stepwise refinement,” “one-file-per-signature,” “Layer 0,”
  and similar unconditional language to catch stale assumptions.

### 6. Regenerate every packaged target

- Run the repository generator so the canonical templates produce matching
  Claude, Codex, and Mistral Vibe skills:
  - `pipelex/skills/pipelex-design/SKILL.md`
  - `pipelex-codex/skills/pipelex-design/SKILL.md`
  - `pipelex-vibe/skills/pipelex-design/SKILL.md`
  - the corresponding generated `pipelex-organize` files, if changed.
- Inspect the rendered platform differences, especially frontmatter and MCP
  connection guidance, to ensure the shared workflow text remains equivalent.

### 7. Add regression coverage

- Add focused generation/content tests where useful so future edits cannot
  silently restore the unconditional signature-first workflow.
- Exercise these behavioral cases in isolated temporary bundle directories:
  1. One concrete operator: direct, runnable `main.mthds`, no signatures.
  2. One `PipeSequence` plus a few leaf operators: direct, coherent, runnable,
     no construction-only files.
  3. One controller with complicated concept dependencies: use judgment based
     on whether the whole graph is confidently specifiable, not controller
     count alone.
  4. Nested controllers with unresolved child contracts: signature-first,
     valid scaffold, then resumable convergence.
  5. Explicit request for a partial scaffold: signature-first and valid with a
     reported pending backlog.
  6. A direct design that reveals hidden nesting: clean transition to stepwise
     refinement without duplicate declarations.
  7. A shallow existing-method structural change: direct baseline/edit/final
     validation.
  8. A nested existing-method contract change: reopen the sufficient region to
     signatures, re-refine, and reorganize.
- Forward-test the revised skill in fresh agents using neutral user-style
  prompts and isolated temporary directories. Give the agents the revised
  skill, not this diagnosis or the expected mode, then inspect their artifacts
  and validation verdicts.

### 8. Run repository verification

- Run `make build` and confirm generated files are fresh.
- Run the relevant focused unit tests while iterating.
- Run `make check` and `make test` before considering the change complete.
- Review the final diff to ensure generated outputs match their templates and
  no unrelated files changed.

## Acceptance criteria

- A clearly shallow method is produced directly as a runnable coherent bundle;
  it does not create a signature-only root, separate definition files, or an
  organization round trip solely for process compliance.
- A complex or uncertain method retains the current validated, resumable
  stepwise-refinement guarantees.
- Both modes determine the client contract first, validate through the Pipelex
  MCP tools, and use the same final runnable gate.
- The skill can escalate from direct construction to stepwise refinement
  without corrupting the bundle or losing contract stability.
- Existing-method re-entry uses the same complexity-sensitive choice.
- `/pipelex-organize` is conditional on layout need rather than universally
  invoked.
- Claude, Codex, and Mistral Vibe renderings describe equivalent behavior and
  pass repository checks.
- README and decision documentation no longer claim that every design is
  signature-first.

## Non-goals

- Do not weaken semantic validation or permit unvalidated `.mthds` delivery.
- Do not remove `PipeSignature` or the validated scaffold workflow.
- Do not impose a fixed maximum number of pipes for direct construction.
- Do not change the supported MTHDS feature subset as part of this work.
- Do not redesign `/pipelex-organize` beyond making its invocation and
  description compatible with the direct path.
