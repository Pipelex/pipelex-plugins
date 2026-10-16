# A failed run

Read this at step 8 when a run failed, after giving its `failure_message` verbatim and before routing it. Route once, on what the failure says, and stop; the guards of the skill's step 8 hold throughout.

| What the failure says | Where it goes |
|---|---|
| an input is missing, malformed or unreadable | `/pipelex-inputs` |
| `Could not identify file type of given bytes` on bytes that open like HTML, such as `<!doctype html>`: a sound web page, read by a `PipeExtract` without the web-page model | `/pipelex-edit`, to set that pipe's `model = "@default-extract-web-page"` |
| a pipe's prompt, model or operator settings are at fault | `/pipelex-edit` |
| the method's structure or a contract is at fault | `/pipelex-design` |

## A `PipeFunc` on a run of the directory

A folder, like listed `files`, sends `.mthds` files and the templates their steps name, never a `.py` file, and a linked id fetches nothing: a caller-supplied source takes precedence over the stored method, which is read only when no folder or files were sent at all, so a linked run gains its history entry and nothing else, the stored `.py` files included. A bundle whose `PipeFunc` names a module of its own folder therefore has **no channel for its Python on any run of the directory**, linked or not. The path that carries it is `/pipelex-catalog`: a saved method run by its id alone has its `.mthds` and `.py` assembled into the run bundle server-side, the draft's as `mt_…@draft` and a version's once it is published.

So on a run of the directory the suspicion sharpens, but only when the failure says so. Where `failure_message` implicates finding or importing that function or its module, say that as the cause rather than offering it as one candidate among several, and give the cure: `/pipelex-catalog` saves the bundle with its Python as the method's draft, and `mt_…@draft`, run by its id alone, gets both. **Where it says anything else, route on what it says** — a missing input, a model or prompt fault, a failure upstream of the custom pipe — and leave the `PipeFunc` a suspect rather than promoting it: a bundle holding one is not evidence that it is what failed, and saving it with its Python cures nothing but that.

## A published address

Only the first row routes. The method is not the user's to repair, so every row below the inputs one is reported rather than routed — the prompt-or-model row and the structure row included, which is where an address would otherwise be sent to `/pipelex-edit` for source the user does not have: give the failure with the address, the tag and the resolved commit SHA the skill's step 5 reported, and say the fix is upstream or another tag. A `PipeFunc` is still named as a suspect; it names a cause and sends nobody anywhere.
