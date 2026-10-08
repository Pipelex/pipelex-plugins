# When a save cannot write the link

Read this when the workshop refuses a bundle's path, before offering to save inline, and when `mthds_save_method` reports `link_file` with `written: false`, before saying anything about the link. The skill's guard holds throughout: never tell this directory it is unlinked unless the tool says no link survives.

## The workshop refuses the path

An inline save gets no link file, since the workshop writes `pipelex-method.json` only beside a `{ path }` root file. Say that this session cannot write the link, and what that costs: after a create, the next save from here makes a second method; after an update, the next save from here is refused as a conflict with this one, this session's own save. Relaunching the harness from a directory holding the bundle cures both. Save inline only on the user's yes.

An inline update also loses the workshop's guard, which sends the link's token only beside a path. So pass the link's `synced_updated_at` as `expected_updated_at` yourself, which keeps the save from replacing a draft somebody saved since the directory synced, and still never its `name`. Never save inline from a link recording a `synced_version` unless the user asked for that restore, as the skill's Pull step says: such a save replaces the draft with the version.

## The link was not written

The draft was saved all the same; what failed is the record that ties this directory to it. Give the tool's reason and the state it names, never one failing state for another. The states are these.

- **Linked but stale**: the link names this method and only its `synced_updated_at` was not refreshed, so a save from here still writes this method's draft, yet is refused as a conflict with this session's own save until the link catches up. Once whatever blocked the write is fixed (for an inline save, the harness relaunched from a directory holding the bundle), a pull of this method's draft into this directory rewrites the link alone while the files still match what was saved.
- **Rewritten by another call**: another save or pull wrote the link while this one ran, so it describes what that call left in the directory, and the workshop kept it rather than write over it. Say so: the next save from here follows that link, and when it is refused, the conflict is read as the skill's stop table says.
- **Unreadable**: the link file is there but cannot be read, so it was not refreshed, and every save from here is refused until it is repaired or removed. Say so in the tool's words: repairing or removing it is the user's, and a pull of this method into the directory then relinks it.
- **Genuinely unlinked**: no link survives, and only then can the next save create a second method. Say so, and that the next save from here must name this method's id or it creates another.

Telling a directory that still holds a link that it is unlinked is the one answer to avoid: its advice, a `method_id` passed by hand, is how somebody else's method gets its draft overwritten.
