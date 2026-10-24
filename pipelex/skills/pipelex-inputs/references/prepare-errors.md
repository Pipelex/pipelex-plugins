# When preparation fails

Read this when `mthds_prepare_inputs` answers `status: "error"` with a problem the inputs or the method's resolution must fix (its `domain` is `input` or `method`), before replying to the user or retrying. Unlike `mthds_inputs_template`, the tool has no produced-invalid arm: it never returns a verdict with `errors[]` of its own. **Read the problem's `code` first**, because the causes need opposite repairs; the location and the wording never tell them apart. A refusal at `kind` is not this file's: it is about recording test files, which the skill answers where it passes `kind`. The skill's file-fidelity guard holds throughout: nothing here is a reason to transform, derive or substitute a file, or to retry with one.

## `upload_too_large`: a file over the storage size limit

The workshop refuses a file over the upload ceiling before anything is sent, as `client.argument_invalid` at `inputs` whose `params.reason` is `upload_too_large`. This is a terminal branch for the current preparation attempt.

1. Report the affected input and file; quote the tool's exact `message` and `next_step` verbatim; and include the actual file size and the allowed limit whenever the response provides them, whether as fields or inside those diagnostics.
2. State explicitly that preparation failed, the inputs are not run-ready, and no run will be offered.
3. Make no follow-up file writes: preserve the user's original file, and a case's copy of it, unchanged, and write no `inputs.prepared.json` for a case (the skill's step 5 deleted any earlier one before the call) — nothing downstream then mistakes these inputs for run-ready, and `inputs.json` keeps its local-path form because step 5 writes the prepared values only on success.
4. Continue only after the user supplies a different acceptable input or reference, or the service limit changes.

## A file the walk could not read or take

Surface the exact `message` and `next_step`, then follow only the recovery they support.

- **For an unreadable local file**, `input.file_unreadable` naming the path, verify that the same file exists, resolve its path to absolute as step 5 does, and retry preparation with the file bytes unchanged. A relative path sent as-is fails this way, as `Local file cannot be read: "inputs/cv.pdf" (ENOENT)`, because the workshop resolves it against its own working directory. The correction is to the request alone, and it must not rewrite the local relative path in `inputs.json`.
- **For a value no file input takes**, `input.invalid` naming the input, such as a `data:` URL that does not decode, fix that value in the request from the user's own file or reference.
- **For any other asset failure**, retry only when the documented error policy explicitly permits a recovery that preserves the asset's content and identity: the problem's `retry` is `"yes"`, or its `next_step` names one.

The method is not at fault, so don't revalidate it: `mthds_validate` and `mthds_inputs_template` only inspect the method definition, and they will keep answering "valid" while the same asset keeps failing.

## The method or its pipe did not resolve

`method.invalid` is a closure that does not load, its `errors` the closure's faults; `request.pipe_not_found` and `request.pipe_ambiguous` are an unknown `pipe_ref` or a method that settles no entry pipe or several, with the pipes the route suggests in its `params`; `pipelex.catalog.not_found` is an id the organization does not hold; and an address that did not resolve is the runner's own problem, located at `method_ref`. This is the arm whose diagnostics the tool delegates: get the structured errors from `mthds_validate` or `mthds_inputs_template`, repair, then retry. For an address the repair is not yours to make: report it with the address and the tag.

