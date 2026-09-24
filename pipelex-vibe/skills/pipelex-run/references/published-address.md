# A published address

Read this at step 1 when the target is a published method's address, passed as `method_ref`, before the first call. An address is passed exactly as a catalog id is, so every step runs as the skill says, its guards included; what follows is where an address is genuinely not like an id.

## It floats without a tag

An address with no tag is accepted, and it floats: it resolves to the default branch at its head, so what runs is whatever that branch holds at the moment of the call, and a run tomorrow can execute different content under the same address. Say that in one line, recommend the tag, and start the run. The `method_provenance` the skill's step 5 reports is what records which content actually ran: an untagged address floats, and even a tag can be moved.

## Its inputs, and its pipe

An address has no bundle beside it, so its inputs are in the directory `/pipelex-inputs` wrote them to: the one the user named, by default the address's last path segment with its tag dropped — `github.com/Pipelex/methods/documents@v0.1.0` gives `./documents/`. Read the skill's "beside the bundle" as "in that directory".

The declared main pipe is the published package's manifest's, which can differ from the bundle's own declaration; `pipe_code` overrides it there exactly as it does anywhere else.

## It is not the user's to repair

The method belongs to whoever published it. A verdict that fails at step 3 is reported with the address and its tag, and is not routed to `/pipelex-design` or `/pipelex-edit`: another tag, or the publisher, is the fix.
