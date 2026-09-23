# Re-entering an existing method

Read this when the request is a structural or contract change to an existing method — adding, removing, or rewiring steps; changing a pipe contract; reshaping a concept — once the skill has its bundle directory and has recorded the baseline, before editing any file. It maps the change and chooses how to make it. The skill's guards hold throughout, its baseline and recovery rules included.

## 1. Map the full affected region

- A pipe contract change includes every parent controller whose wiring must adapt: a definition preserves the contract its parent relies on, matched by concept identity, and an intentional contract change propagates through every affected parent mapping before delivery.
- A main-pipe contract change includes root boundary concepts and invalidates any saved `inputs.json`.
- A concept reshape includes its introducing declaration and every consumer that field-reads it.

## 2. Choose the re-entry mode from the affected graph, not the whole method's size

- **Direct coherent edit:** when the affected region is shallow and its complete graph, propagated contracts, mappings, ownership, and concept shapes can be understood together, edit the smallest coherent region directly. Validate the whole bundle after the coherent edit and restore the baseline runnable/scaffold state.
- **Signature-driven re-entry:** when the affected region is nested, uncertain, cross-module, cross-branch, or intentionally staged, reopen the smallest sufficient region to signatures. Internals-only changes may replace one concrete with a same-contract signature; contract changes reopen the child and sufficient parent wiring; concept reshapes reopen the declaration and every field-reading consumer.

## 3. Build a reachable re-entry scaffold atomically

For a signature-driven re-entry:

- Keep or coherently edit the smallest unaffected concrete ancestor whose wiring reaches the affected region; it is the scaffold anchor.
- Replace only the directly affected concrete children reachable from that anchor with signatures, and remove their old concrete definitions before validating. A signature left beside its old concrete is already satisfied and is not a backlog item.
- Reshape or declare each changed concept exactly once in the scaffold at its common logical owner, so the new signatures' contracts resolve. Later refinements reference that declaration; they do not redeclare it.
- Do not predeclare deeper descendants while their parent is only a signature. Introduce those child signatures when that parent receives its concrete controller definition, keeping every pending signature reachable.
- Validate the atomic scaffold, then drain its structured backlog with the stepwise refinement loop, layer by layer.

## 4. Converge and deliver

Restore at least the baseline verdict, then deliver as the skill's step 6 says, with two things particular to a re-entry: run `/pipelex-organize` only if a signature-driven re-entry produced a construction-shaped layout that needs regrouping, and when you re-project the input template, if an `inputs.json` exists and the client surface changed, flag the drift and hand the refresh to `/pipelex-inputs`.
