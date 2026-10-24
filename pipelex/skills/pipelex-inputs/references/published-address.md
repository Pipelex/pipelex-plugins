# A published address

Read this at step 1 when the target is a published method's address, passed as `method_ref`, before the first call; and again when `mthds_prepare_inputs` refuses the address, before naming a cause. An address is passed exactly as a catalog id is, so every step runs as the skill says; what follows is where an address is genuinely not like an id.

## Where the inputs go

The server fetches the repository at the tag and locates the package there, so there is no bundle directory and nothing is cloned onto the user's disk. `<output_dir>` is a directory the user names, defaulting to a new directory named after the **address's last path segment with its tag dropped** — `github.com/Pipelex/methods/documents@v0.1.0` gives `./documents/`, and an address with no selector gives the repository's own name — and `inputs.json` goes there. An address with no tag resolves to the default branch at its head, so the template filled here is the one that branch held today, and the same address can answer with a different signature tomorrow; step 1 says to tell the user so, and it is never a reason to refuse the work.

## A template that does not validate

When `mthds_inputs_template` answers `is_valid: false` on an address, the package at that address does not validate: report its `errors[]` with the address and its tag, and say the fix is upstream or another tag — never a local repair of source the user does not have.

## Prepare refused at `files`: a workshop older than the selector

`mthds_prepare_inputs` took `files` and `method_id` alone until the release that gave it the address, so a workshop cached from before then does not know `method_ref` — and a host that validates a call against that older tool schema drops the argument before it is ever sent. The tell is the error itself: located at **`files`**, saying *"Provide MTHDS files or a method_id"*, on a call that did supply a selector — the message lists what the tool accepts and leaves `method_ref` out of it. Read it as a workshop that predates the selector, not as a missing target. The same address goes on templating normally throughout, because `mthds_inputs_template` has taken it for longer — which is what makes the pair of answers the diagnosis.

Give the cure with both of its conditions: the launcher fetches the newest workshop only on its next spawn, so `npx -y @pipelex/mcp@latest` changes nothing until the host restarts the server and reloads its tool schema — and a refresh only reaches the selector once a published workshop carries `method_ref` on prepare at all. Where none does yet, say that this one leg is unavailable rather than leaving them refreshing in a loop, and never fall back to submitting files you do not have.

## Prepare, a problem in the `account` domain: the credential, and only the credential

The skill's account stop applies as written: relay the `next_step` verbatim and deal with the credential first, since it is the one thing the user can act on. A template call that just succeeded on the same address rules nothing out, because preparation also uploads with the key and templating never exercises that. What the problem names is the whole cause: preparation reads an address's signature from the package's `.mthds` files alone, so the deployment's refusal of a package shipping in-process Python never reaches it. That refusal, `pipelex.deployment.custom_code_requires_sandbox`, meets the run instead, which says so in its own words.
