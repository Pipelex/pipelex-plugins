# An error at `method_id`

Read this when `mthds_save_method` or a pull's `mthds_get_method` answers an `input_domain` error at `method_id`, before concluding anything about the directory's link. The skill's guard on the link holds throughout: it is removed only on the user's yes.

An unknown `method_id` comes back at that location, and so do several other faults: a payload the platform rejected, an organization-context failure, and the workshop's own refusal when this directory's link names a *different* method from the id being saved. **The location alone never tells them apart**, so read the message and the hint before doing anything: only the not-found answer names `pipelex-method.json` and the `api_host` and explains that the catalog is org-scoped, so a method from another organization reads exactly like a miss. Anything else is a different fault: the link is not dead, it stays where it is, and the fix is to the call.

When the hint does say the id is not visible, report it **with the `api_host` the link file records** — that is what makes it diagnosable: the link was made against another plane, or with another organization's key.

Then offer to save the directory as a **new** method. That needs the stale link gone first: the workshop refuses a create into a directory another link claims, rather than minting a duplicate nobody can delete. So ask, and on a yes remove `pipelex-method.json` and run the create, which writes a fresh link.

**A pull has no link to judge.** When the error came from `mthds_get_method`, nothing was written and nothing on disk is touched: relay the answer and its hint, say that a method saved from another organization, or on another plane, reads exactly like a miss, and offer to find the method by name, as the skill's "List and find" says.
