# A catalog id or a published address as the target

Read this when a skill that works on files is given a registered method's catalog id (`mt_…`) or a published method's address as its target, before reading or writing any file, and then return to the skill that sent you here and continue just after its pointer to this file. Below, "this skill" is the skill that sent you here and "this one" its `SKILL.md`, and that skill's guards hold throughout.

This skill works on files, so a **catalog id** (`mt_…`) is not a target it can act on directly: it is resolved to a directory on disk first, and everything after that is the ordinary file-based flow.

1. **Look for a directory already linked to that method.** One search over the link files, from the working directory down: `grep -rl '<the mt_… id>' --include=pipelex-method.json .`. Exactly one hit is the directory to work in — say which one, and go to **the skill that sent you here, just after its pointer to this file**.
2. **Several hits are the user's choice, never yours.** More than one directory can legitimately hold the same link: `/pipelex-catalog`'s conflict path tells the user to pull a comparison copy into a sibling directory, and that copy carries the same link and is meant for reading, not for editing. Name the directories and ask which one is the work.
3. **No hit — hand the pull to `/pipelex-catalog`**. It brings the method's sources to disk and the workshop writes the link beside them; then carry on with that directory. The search only sees the working directory and below, so a bundle linked somewhere else reads as no hit — if the user knows where it is, ask for the path rather than pulling a second copy.

**What the search proves, and what it does not.** It answers where this method lives locally and nothing else. A linked directory can be behind the catalog, ahead of it, or both at once, and the link records no hashes to tell them apart — so do not present the local files as the saved method's current content. `/pipelex-catalog` is what compares the two, and it is also the only way the work done here reaches the saved copy.

**A published address is not a target for this skill.** `github.com/<owner>/<repo>[/<selector>][@<tag>]` names somebody else's published package: nothing of it is on disk, and there is nowhere to write a change back. Say so and point at `/pipelex-explain`, which reads such an address at the level of its contract.
