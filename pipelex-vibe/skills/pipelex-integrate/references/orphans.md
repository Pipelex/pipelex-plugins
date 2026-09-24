# Reporting orphans

Read this when `mthds_codegen` succeeds with `orphans[]` non-empty and `drifts[]` empty, at step 6 or on a refresh: the one non-current result the run carries on past. It says what the report owes the user about them. The skill's guard on orphans holds throughout, and nothing here relaxes it.

## What the signal means

An orphan is a stamped file in the generated directory that the new lock does not list. The directory holds artifacts this generation does not list, and the causes are benign: an earlier generation of this method, a target switch, an engine version that renamed an artifact, or another method's tree in a directory that was never dedicated. The empty `drifts[]` is what makes the case benign — every fault the check found is an orphan, so nothing the write itself produced is broken.

## What the report says

At step 12, restated there rather than left behind at step 6, because that is where the user reads it:

- the orphan paths, by name, and that none of them were deleted;
- that the directory holds artifacts this generation does not list;
- that the gate of step 10, where the project has one, counts each one as a drift in either language, so that check exits non-zero on this directory until it holds one generation — which is the red gate step 11 meets and reports rather than fixes;
- a dedicated directory per generation as the fix, in the tool's own words, and the user's to take;
- `orphans_truncated: true` → that orphan detection was partial, rather than reporting a clean tree.

## What it never claims

Never say the write may have overwritten another method's files: an orphan cannot indicate that. Every method of a target emits the same file names, so a write into another method's directory overwrites its stamped files without reporting them as orphans at all, and step 4's refusal is what guards that case.
