# A miss, or a problem at `method_id`

Read this when `mthds_save_method`, `mthds_publish_method` or a pull's `mthds_get_method` answers `pipelex.catalog.not_found`, or another problem located at `method_id`, before concluding anything about the directory's link. The skill's guard on the link holds throughout: it is removed only on the user's yes.

Several faults land on the same id, and **the problem's `code` tells them apart**, never its location or its wording. Only `pipelex.catalog.not_found` whose `params.resource` is `method` is a miss: the catalog is org-scoped, so a method from another organization reads exactly like one. Anything else is a different fault, the link is not dead, it stays where it is, and the fix is to the call:

- `client.target_exists` at `method_id` is the workshop's own refusal when this directory's link names a *different* method from the id being saved. Its `message` names both and what to pass instead.
- `client.argument_invalid` at `method_id` is a call the workshop refused before sending it, its `params.reason` saying why. **A version suffix is refused there, as `version_suffix`, and is not a miss.** A save and a publish take the bare id, since both act on the draft, so `mt_…@<n>` is refused before anything is sent: call again with the bare id, and to publish an old version's content again, pull that version, restore it as the draft and publish that.
- `pipelex.catalog.not_found` whose `params.resource` is `version` is a pull of a version the method never had. Its `message` names the versions it has: offer one of those, or the draft.
- `method.package_invalid` with `params.reason` `empty_tree` is a pull of a method whose stored source holds no file yet. It is not a miss: relay it as the pull's report step says.
- Any other code, such as a payload the platform rejected or a failure of the organization's context, is relayed with its `detail` and `next_step`.

**A save's miss is checked against a read first.** When a save answers `pipelex.catalog.not_found`, call `mthds_get_method` on the same bare id without `output_dir`: when it reads the method, the id is alive and this platform has no draft save yet, a platform older than drafts. Say so and stop; the link stays and nothing here creates a method.

When a read does not find it either, report the miss **with the `api_host` the link file records** — that is what makes it diagnosable: the link was made against another plane, or with another organization's key.

Then offer to save the directory as a **new** method. That needs the stale link gone first: the workshop refuses a create into a directory another link claims, rather than minting a duplicate nobody can delete. So ask, and on a yes remove `pipelex-method.json` and run the create, which writes a fresh link.

**A pull or a publish has no link to judge.** When the problem came from `mthds_get_method` or `mthds_publish_method`, nothing was written or published and nothing on disk is touched. Relay its `detail` and `next_step`, and on a miss say that a method saved from another organization, or on another plane, reads exactly like one, and offer to find the method by name, as the skill's "List and find" says.
