# When the verdict carries no signature

Read this at step 3 when the `mthds_validate` verdict has no `main_pipe` in its structured content, before choosing a target at step 4.

## Why it can be absent

The workshop omits `main_pipe` whole — never a partial signature, and the verdict is otherwise unaffected — in three cases:

- the method settles **no entry pipe**: the bundle declares no `main_pipe`, or a published package's `METHODS.toml` names a pipe the closure does not declare, or declares in several domains, which is exactly when a run with no pipe selector would fail too;
- the entry pipe's contract did not come back whole, which comes from the runner behind `/v1/validate` and which no refresh of the workshop fixes;
- the workshop **predates the signature** (the release the skill names at step 3, and earlier); `npx -y @pipelex/mcp@latest` refreshes it.

## First, the text summary

The verdict's text summary carries the same signature on one line, under `## Main pipe`, and it is missing in the same cases — so it is the **same fact on a second channel, not a fourth cause**, and that is what makes it useful. When the structured field did not reach you but that line did, read the signature from there rather than treating the method as unsignatured. A host that does not surface structured content, or a cached tool schema, is the usual reason, and it is not a property of the method.

## Then, by source

- **A files source.** Take the pipe the bundle declares as `main_pipe`, or ask which pipe to integrate when it declares none. Its `pipe_ref` is its code qualified by the domain of the file that defines it, which need not be the root file's and may be dotted (`legal.contracts.summarize`), and it is the value the sidecar's `pipe` record and the call site's `PIPE_CODE` hold. Call **`mthds_inputs_template`** with the selector, that `pipe_ref` and **`explicit: true`** — one of the two calls in this plugin that want the ceremonial `{concept, content}` envelope, because it is the concept ref per input you need (`/pipelex-explain` makes the other, for a method whose source it cannot read) — and read the pipe's `output` declaration from the bundle, with the MTHDS language reference the skill links for reading a bundle. Then carry on at step 4.
- **A `method_ref` or `method_id` source.** The output concept has no in-context channel. STOP and say the verdict carries no signature to type this integration exactly, naming the cause that fits and its remedy: a workshop that predates the signature is refreshed and the call retried; a method that settles no entry pipe is fixed where the method is authored; a contract that did not come back whole is the runner's, and no refresh fixes it.
