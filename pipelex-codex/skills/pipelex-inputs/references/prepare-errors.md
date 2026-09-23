# When preparation fails

Read this when `mthds_prepare_inputs` answers `status: "error"` with class `input_domain` located at `inputs`, `pipe_ref`, `method_id` or `method_ref`, before replying to the user or retrying. Unlike `mthds_inputs_template`, the tool has no produced-invalid arm: it never returns a `validation_errors[]` list. **Read the error's `location` first**, because the causes need opposite repairs. The skill's file-fidelity guard holds throughout: nothing here is a reason to transform, derive or substitute a file, or to retry with one.

## `location: "inputs"` and the response reports a storage size limit

This is a terminal branch for the current preparation attempt.

1. Report the affected input and file; quote the tool's exact `message` and `hint` verbatim; and include the actual file size and the allowed limit whenever the response provides them, whether as fields or inside those diagnostics.
2. State explicitly that preparation failed, the inputs are not run-ready, and no run will be offered.
3. Make no follow-up file writes: preserve the user's original file and the copied file in `<output_dir>/inputs/` unchanged, and write no `inputs.prepared.json` (the skill's step 5 deleted any earlier one before the call) — without one nothing downstream mistakes these inputs for run-ready, and `inputs.json` keeps its local-path form because prepare never rewrites it.
4. Continue only after the user supplies a different acceptable input or reference, or the service limit changes.

## `location: "inputs"` and the response is not a size-limit failure

Surface the exact `message` and `hint`, then follow only the recovery they support.

- **For an unreadable local file**, verify that the same file exists, resolve its path to absolute as step 5 does, and retry preparation with the file bytes unchanged. A relative path sent as-is fails this way, as `Local file cannot be read: "inputs/cv.pdf" (ENOENT)`, because the workshop resolves it against its own working directory. The correction is to the request alone, and it must not rewrite the local relative path in `inputs.json`.
- **For any other asset failure**, retry only when the documented error policy explicitly permits a recovery that preserves the asset's content and identity.

The method is not at fault, so don't revalidate it: `mthds_validate` and `mthds_inputs_template` only inspect the method definition, and they will keep answering "valid" while the same asset keeps failing.

## `location: "pipe_ref"`, `"method_id"` or `"method_ref"`

The closure did not resolve: an invalid bundle, an unknown `pipe_ref`, an unresolvable `main_pipe`, a method id with no stored source, or an address that did not resolve. This is the arm whose diagnostics the tool delegates: get the structured errors from `mthds_validate` or `mthds_inputs_template`, repair, then retry. For an address the repair is not yours to make: report it with the address and the tag.
