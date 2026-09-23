# Signature-driven stepwise construction

Read this when step 3 of the skill chooses stepwise construction, before writing any file; when step 4's direct construction would need a placeholder or a guessed contract, or exposes an unresolved structural boundary, before changing any file; and when a re-entry is signature-driven, before building its scaffold. Stepwise is the mode wherever a direct write is not safe: nested controllers or multiple structural layers whose child contracts are not all fixed; uncertain sub-pipe contracts, intermediate concept ownership, branching, iteration, or wiring; shared concepts whose shapes depend on consumers in different branches; a large graph that benefits from independently valid review checkpoints; or an explicit request for a scaffold, partial design, staged work, or a resumable intermediate result. This file is the additive, breadth-first construction loop and its valid intermediate checkpoints. The skill's guards and its validation step hold throughout, and the syntax of `PipeSignature` and `signature_for` is the authoring reference's, read before writing.

Stepwise mode materializes uncertainty. Every not-yet-designed pipe is a reachable `PipeSignature`. Each refinement adds one concrete definition file, may introduce child signatures, and is validated immediately. The pending-signature verdict is the resumable backlog. Stepwise mode refines automatically, without per-layer approval: valid checkpoints are the review surface.

## Coming from a direct draft

When direct construction would need a placeholder or a guessed contract, or exposed an unresolved structural boundary, stop extending the direct draft and transition:

1. Keep the announced root contract and boundary concept shapes stable unless the evidence shows the client requirement itself was wrong.
2. Compose the replacement scaffold in memory. Its root keeps bundle metadata and boundary concepts, replaces the main concrete graph with one root `PipeSignature`, and removes abandoned direct-only intermediate concepts and concrete child definitions that the refinement files will own.
3. Replace the candidate file set as one consistent layout. Do **not** append signatures beside the abandoned concrete definitions: keeping both drafts would create duplicate concepts, conflicting concrete pipes, or falsely satisfied signatures. Re-gather the directory and confirm every pipe/concept code is declared only where the stepwise model permits it: one root header, then one later concrete per pending code; each concept exactly once.
4. Validate the root scaffold before adding definitions. It must be valid with the root pipe in `pending_signatures`; then continue at "Refine layer by layer" below.

This replacement is the construction-mode transition, not an additive refinement.

## The root scaffold

Write `main.mthds` in the bundle home (unless the user asks for another root name) with:

- `domain`, `description`, `main_pipe`, optional `system_prompt`;
- the fully specified boundary concepts;
- the top pipe as one `PipeSignature` whose code is `main_pipe`, with its precise `description`, explicit `inputs`, `output`, and `signature_for`.

The root is written once for this construction mode. Validate it: the one-signature library must pass with the top pipe listed as pending. An explicit partial-scaffold request may stop after any later valid checkpoint, but never before this first passing verdict.

## Refine layer by layer

Drain the signature backlog breadth-first, **serially** (one signature at a time — no parallel workers in this version):

1. Validate and read `pending_signatures[]` (the summary's `## Pending signatures` list). This verdict is the bundle's own todo list.
2. Expand each current pending signature one at a time. Every expansion adds exactly one new `<code>.mthds` definition file and never edits an existing construction file.
3. Re-validate after each expansion, recompute the backlog, and repeat until it is empty.

### Expand one signature

Given pending signature `S` with frozen `inputs`, `output`, `description`, and `signature_for`:

1. Decide operator or controller. A single cognitive/IO step is an operator; multiple steps, iteration, branching, or parallelism require a controller.
2. Add `<code>.mthds`, using `S`'s **bare** pipe code. The verdict names signatures as `domain.code`, but a namespaced `[pipe.domain.code]` would define a different pipe and never satisfy the header. A non-root file carries only `domain = "<same_domain>"` for membership. If the code is literally `main`, use a non-colliding filename such as `main_pipe.mthds`; filenames do not define pipe identity.
3. For a leaf, write the concrete operator (`PipeLLM`, `PipeExtract`, `PipeSearch`, `PipeImgGen`, `PipeCompose`, `PipeFunc`) with all type-specific fields. For a controller (`PipeSequence`, `PipeBatch`, `PipeParallel`, `PipeCondition`), wire one structural level, declare only intermediate concepts not already owned by the assembled library, and forward-declare every not-yet-designed child as a new `PipeSignature` in the same file. During re-entry, a reshaped concept may already be retained in the scaffold/common owner so signatures can validate; reference it from the new definition instead of redeclaring it.
4. Repeat `S`'s explicit `inputs` and `output` on the concrete definition. Contracts reconcile by concept identity (bare/qualified spellings and native equivalents), not textual coincidence.
5. Before introducing an intermediate concept, check its code across the assembled library. Derive a unique parent-based code if needed. Declare it once, in the controller that logically introduces it or in the re-entry scaffold that must freeze its changed contract, with a shape fixed from every wired consumer. If consumers in different branches field-read it, the common parent owns and structures it. Never duplicate a concept already retained by a direct→stepwise transition or signature-driven re-entry.

### If validation fails after an expansion

The new file bounds the ordinary fix:

- **Contract mismatch:** conform the definition to the frozen header. If the header itself is wrong, that is a propagating contract change; pause and revise the parent region deliberately rather than silently changing the header.
- **Other semantic errors:** use `validation_errors[]`, the Markdown locators, and the relevant section of the authoring reference; fix the added file and re-validate.

## Stopping early

Early stopping exists only in stepwise mode. When the user requested a partial scaffold or interrupts before convergence, confirm `is_valid: true`, report the exact pending-signature backlog, and explain that resuming means expanding those signatures. Do not claim it is runnable and do not auto-organize it; offer `/pipelex-organize` only if the user wants the valid scaffold regrouped.

## The rules of this mode

- **Additive refinement.** After the root scaffold (or a deliberate re-entry reopening), every refinement adds one concrete definition file; existing construction files and satisfied headers persist until organization.
- **One concrete definition per refinement file.** This keeps failures bounded and checkpoints resumable.
- **Backlog = `{signatures} − {concretes}`.** Recompute it from the structured verdict after every expansion; never hand-track it.
- **The root file is written once during new stepwise construction.** Direct construction and coherent direct re-entry are not subject to this construction-history rule.

A converged backlog goes on to the skill's runnable gate and delivery, step 6.
