# A published address

Read this at step 1 when the target is a published method's address, passed as `method_ref`, before the first call; and again when `mthds_prepare_inputs` refuses the address in one of the two ways only an address meets. An address is passed exactly as a catalog id is, so every step runs as the skill says; what follows is where an address is genuinely not like an id.

## Where the inputs go

The server fetches the repository at the tag and locates the package there, so there is no bundle directory and nothing is cloned onto the user's disk. `<output_dir>` is a directory the user names, defaulting to a new directory named after the **address's last path segment with its tag dropped** — `github.com/Pipelex/methods/documents@v0.1.0` gives `./documents/`, and an address with no selector gives the repository's own name — and `inputs.json` goes there. An address with no tag resolves to the default branch at its head, so the template filled here is the one that branch held today, and the same address can answer with a different signature tomorrow; step 1 says to tell the user so, and it is never a reason to refuse the work.

## A template that does not validate

When `mthds_inputs_template` answers `is_valid: false` on an address, the package at that address does not validate: report `validation_errors[]` with the address and its tag, and say the fix is upstream or another tag — never a local repair of source the user does not have.

## Prepare, `input_domain` at `files`: a workshop older than the selector

`mthds_prepare_inputs` took `files` and `method_id` alone until the release that gave it the address, so a workshop cached from before then does not know `method_ref` — and a host that validates a call against that older tool schema drops the argument before it is ever sent. The tell is the error itself: `input_domain` located at **`files`**, saying *"Provide MTHDS files or a method_id"*, on a call that did supply a selector — the message lists what the tool accepts and leaves `method_ref` out of it. Read it as a workshop that predates the selector, not as a missing target. The same address goes on templating normally throughout, because `mthds_inputs_template` has taken it for longer — which is what makes the pair of answers the diagnosis.

Give the cure with both of its conditions: the launcher fetches the newest workshop only on its next spawn, so `npx -y @pipelex/mcp@latest` changes nothing until the host restarts the server and reloads its tool schema — and a refresh only reaches the selector once a published workshop carries `method_ref` on prepare at all. Where none does yet, say that this one leg is unavailable rather than leaving them refreshing in a loop, and never fall back to submitting files you do not have.

## Prepare, class `config`: the credential first, then the deployment

The skill's `config` stop applies as written: surface the `hint` verbatim and deal with the credential first, since it is the one thing the user can act on. But a by-address target has one further cause here, and nothing in the answer yet tells you which of them you met. Preparation resolves an address's signature through the run route, which refuses a published package shipping in-process Python where the deployment hosts no sandbox — and that refusal arrives in this same `config` arm wearing the deployment's authentication wording. A template call that just succeeded on the same address rules nothing out, because preparation also uploads with the key and templating never exercises that. So once the key proves good, name the other cause rather than leaving the user with a mystery: a published package can be refused by the deployment itself, and one carrying no in-process Python is not affected.
