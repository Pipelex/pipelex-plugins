# When the save could not write the link

Read this when `mthds_save_method` reports `link_file` with `written: false`, before saying anything about the link. The draft was saved all the same; what failed is the record that ties this directory to it. The skill's guard holds throughout: never tell this directory it is unlinked unless the tool says no link survives.

Give the tool's reason and the state it names, never one failing state for another. There are three.

- **Linked but stale**: the link names this method and only its `synced_updated_at` was not refreshed, so a save from here still writes this method's draft, yet is refused as a conflict with this session's own save until the link catches up. Once whatever blocked the write is fixed (for an inline save, the harness relaunched from a directory holding the bundle), a pull of this method's draft into this directory rewrites the link alone while the files still match what was saved.
- **Rewritten by another call**: another save or pull wrote the link while this one ran, so it describes what that call left in the directory, and the workshop kept it rather than write over it. Say so: the next save from here follows that link, and when it is refused, the conflict is read as the skill's stop table says.
- **Genuinely unlinked**: no link survives, and only then can the next save create a second method. Say so, and that the next save from here must name this method's id or it creates another.

Telling a directory that still holds a link that it is unlinked is the one answer to avoid: its advice, a `method_id` passed by hand, is how somebody else's method gets its draft overwritten.
