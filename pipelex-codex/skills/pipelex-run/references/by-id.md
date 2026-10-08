# A catalog id

Read this at step 1 when the target is a registered method's catalog id (`mt_…`), passed as `method_id`, before the first call. Every step runs as the skill says, its guards included; what follows is what an id adds.

## Which content it names

A saved method has a draft, which every save writes, and published versions numbered from 1, which only a publish makes and which never change. The id says which one every call reads, the validation and the inputs template as well as the run, so carry the same form through every call:

- a bare `mt_…` is the latest published version, what the method's callers run, and it moves whenever somebody publishes;
- `mt_…@<n>` is version n, for good;
- `mt_…@draft` is the draft, what the last save holds, including a save `/pipelex-catalog`, `/pipelex-edit` or `/pipelex-design` just made.

Pass the form the user meant, which is not always the one they typed: "run what I just saved" or "run the draft" is `mt_…@draft`, and "run version 3" is `mt_…@3`, even when the request names the bare id.

Its inputs are looked for under the bare id whatever the suffix: `./mt_abc123/`, or the directory whose `pipelex-method.json` names `mt_abc123`, since a link records the bare id.

## A method never published

A bare id of a method with no published version is refused at step 2 as `method_not_published`, and nothing is spent. Its only content is its draft: say so, carry `mt_…@draft` through every call from step 2 on, and name it in step 4's line, so the user sees that the draft is what runs. Publishing is `/pipelex-catalog`'s, on the user's request, and never a way to make a bare id run.

## A version the method never had

`mt_…@<n>` for a version that does not exist is refused at `method_id` as `method_version_not_found`, and the message names the versions the method has. Nothing is spent: report it and ask which one to run.

## A platform that does not resolve versions yet

Such a platform refuses `@draft` and `@<n>`, and the hint says that a bare id reads the draft there. Report it in the tool's words; on that platform the bare id runs the draft.

## Which version ran

`mthds_run`'s result carries `method_version`, a number or `draft`, and says it in its summary. Report it beside the run id at step 5, above all for a bare id, since the latest version may have moved since the user last looked: *ran version 4 of `mt_abc123`, its latest published version*.
