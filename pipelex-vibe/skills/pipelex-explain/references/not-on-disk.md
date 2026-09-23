# A method that is not on disk

Read this when the target is a registered method's catalog id (`mt_…`) or a published address, before the first call on it. It says how each is read and what the workshop's answers mean for the explanation. The skill's guards hold throughout, and so do its steps wherever a source comes back.

The two targets part company on ownership rather than convenience. **A catalog id names the user's own organization's method**, so its source is theirs to read and the skill reads it. **A published address names somebody else's package**, and its internals ride a channel only views see, so it is described by its contract alone. Exactly one selector per call: files, an address, or an id, never two.

## A catalog id: read it in full

Call `mthds_get_method` with the `method_id`, as the skill's step 1 says. The `files` it returns are explained **exactly as a bundle on disk is**, through the skill's steps 1 to 5, with the returned contents standing in for the files you would have read. The verdict of step 3 is one `mthds_validate` call with the same `method_id`.

Three things about the returned set are worth knowing before you describe it:

- **The read is bounded, and a bounded read is not a complete library.** When `truncated` is true, some files come back carrying their name and byte size with **no content**, so the files you hold are part of the method and not all of it; the skill's stop table says what to tell the user.
- **The stored Python comes back beside the sources.** A custom `PipeFunc`'s function is a registry key and no bundle file names its module, so this is the one reading where you can actually say which stored `.py` file defines it. Say it when it is clear from the code, and leave it at the pipe's `function_name` when it is not.
- **A method saved before the webapp's editor existed carries no file names.** It arrives as one unnamed file; explain it as a single-file method, which is what it is.

## Without `mthds_get_method`

When the other tools answer and `mthds_get_method` does not, read the id at contract level exactly as an address is read below, with `method_id` as the selector, and say that the source was not read rather than implying there was none to read. **Two causes present identically from here, so say both rather than picking one**: the hosted console, which reads no files and therefore serves neither catalog-write tool, and a local workshop that predates the tool, which `npx -y @pipelex/mcp@latest` refreshes. Naming only the console tells a workshop user to go looking for a host they are not on.

## A published address: its contract

- `mthds_validate` with `method_ref` in place of `files` gives the verdict and, **when the verdict carries one**, the `main_pipe` signature.
- `mthds_inputs_template` with the same selector and `explicit: true` gives the input shapes.
- Say plainly that the internals are not readable from here, so that the user knows they are getting the contract rather than a walkthrough and can ask the publisher for the bundle if they need one.

## Verdicts that leave nothing to explain

A published address has no source to fall back on, and neither has an id read at contract level, so these verdicts are said rather than filled in. An id read in full still has its source.

- **The verdict is positive but carries no `main_pipe`.** The method settles no entry pipe, the contract did not come back whole, or the workshop predates the field — the same three causes `/pipelex-integrate` names, and the one-line signature in the text summary is missing in all three. Say the verdict was positive and that it carries no signature to describe the contract with, and name which of the three the tool's own message points to.
- **The verdict is `is_valid: false`.** There is no `main_pipe` on an invalid verdict and `mthds_inputs_template` answers with `validation_errors[]` rather than shapes, so nothing about the method is readable **from the verdict** — though for an id read in full the source still is, and an invalid stored method is worth explaining from its source with the errors beside it. Report the errors as they came back. **Do not route a remote target to `/pipelex-edit` or `/pipelex-design`**: a stored method is fixed where it is edited — `/pipelex-catalog` is what brings it to disk first — and a published address is fixed in the repository it names.
- **The id is refused rather than read.** An unknown id and a method whose stored source is empty both arrive as `input_domain` at `method_id`: the first says no such method is visible to the API key's organization, which a method from another organization reads exactly like; the second says the row exists and holds no source yet. Give the one the tool gave, as the skill's stop table says.
