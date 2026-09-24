---
name: pipelex-lab
description: Experiment with an MTHDS method the way a lab would — frame a use case into candidate methods, write the answer key of each test case before its first run, agree a budget, then run, score every run against its key and log it, fixing the method round after round until it meets the pass bar or a stop. Use when the user says "what could I build with Pipelex", "help me try Pipelex on our invoices", "help me pick where to start", "test this method", "set up test cases", "write an answer key", "check it against the answer key", "score this run", "is it getting better", "iterate until it passes", or wants to know whether a method is good enough. It designs, prepares inputs, runs and edits through the skills that own those steps, and keeps the brief, the keys and the log under lab/ in the project. A run spends inference credit, so the loop starts only on the user's go on a budget.
---

# Experiment with a method

This skill owns the loop around a method: [frame](#1-frame-the-use-case) a use case, [set up](#2-set-up-the-experiment) test cases whose right answers are written down before anything runs, and [run the loop](#3-run-the-loop) of run, score, log and fix within a budget. It writes the brief, the keys and the log. The method is designed by `/pipelex-design`, the inputs are prepared by `/pipelex-inputs` with files made by `/pipelex-synthetic-inputs`, each run is started by `/pipelex-run`, and each fix is made by `/pipelex-edit` or `/pipelex-design`. Codex has no cross-skill invocation, so wherever this skill hands a step to another, open that skill's `SKILL.md` beside this one and follow it.

Start where the project stands: when `lab/<method>/` exists, read it and take up the move it has reached. A log already there is continued, never restarted, and **a series it leaves without a scorecard is closed with one first: the loop runs again only on a new go.**

## Requirements

The loop needs the workshop: `/pipelex-run` starts and follows each run, and this skill reads each result with **`mthds_run_results`**, and with `mthds_run_status` and `mthds_download_artifacts`.

- **If those tools are absent from this session**, the Pipelex MCP server isn't connected: STOP, and tell the user in one line what [the connection reference](../shared/credentials.md#the-tool-is-absent) says for Codex. That stop comes at the loop: framing and setting up need no tool, so frame and set up, then stop before the loop.
- **If a call returns `status: "error"` with an error of class `config`** (missing or rejected `PIPELEX_API_KEY`, unreachable API), STOP the same way and surface the error's `hint` verbatim; when it is about the key, read [where the key comes from](../shared/credentials.md#where-the-key-comes-from) before saying anything more.

## The lab directory

The lab's subject is a bundle directory, and its lab is `<project>/lab/<method>/`: `<project>` is the nearest directory holding a `package.json`, a `pyproject.toml`, a `setup.py` or a `requirements.txt` at or above the working directory, or else the working directory, or the bundle's parent when the working directory is the bundle or inside it; `<method>` is the bundle directory's name.

```
lab/<method>/
  brief.md         the framing: the candidates, the choice, what right means
  cases/<case>/    inputs.json, its files under inputs/, and key.md
  log.md           one entry per run, newest last
```

**Never put the lab inside the bundle directory**: the catalog saves that directory and a Python package ships it, and a case's files can stand in for confidential documents. **The loop runs the directory, never an `mt_…` id or an address**: a fix lands in the files, and the saved method changes only when `/pipelex-catalog` saves it, which is a deployment the loop never makes. For a saved method, work in the directory linked to it, or one `/pipelex-catalog` pulls.

## Guards

- **A key is written and shown before the first run of its case, and never adjusted to fit an output.** It changes only when the user says so, and the reason goes in the log.
- **Every run is logged**, failed and unfinished ones included: each one spent credit, whatever the app or the workshop kept of it.
- **A failing line is checked against the case's inputs before the method is touched**: open the file and confirm that it shows the fact the key expects.

## 1. Frame the use case

Read [frame.md](references/frame.md) before asking anything: it holds the questions to ask, what the platform can and cannot do, the shape of a candidate, and the brief. **State no capability that frame.md does not state**: a method designed around one the platform lacks fails at its first run, after credit is spent.

For a use case with no method yet, propose two or three candidates, and recommend the one whose output can be checked against a key and whose inputs can be made safely. Once the user picks, write `lab/<method>/brief.md` with what "right" means for the chosen method, which seeds its keys, `<method>` being the `domain` you give `/pipelex-design` in the project language's casing. Hand the brief to `/pipelex-design`, and if the directory it makes is named otherwise, rename `lab/<method>/` to match. The setup follows once the method validates.

A method that already exists and has no brief gets the short form frame.md gives, with no candidates, before the setup.

## 2. Set up the experiment

Read [key.md](references/key.md) before writing a key.

1. **Cases.** At least two: one the method should pass cleanly, and one with traps it must not fall into. Name each in kebab-case.
2. **Inputs.** The user's own files, or files from `/pipelex-synthetic-inputs` with facts planted in them; copy the facts it planted into the key. Give `/pipelex-inputs` each case's directory, `cases/<case>/`, as its `<output_dir>`: `inputs.json` goes there and its files under `inputs/`, so no case writes over another. **Ask it to stop at run-ready, with no run offer**: the case has no key yet, and a yes to that offer would run it. **A case of the user's own files stays out of version control**: in a git repository, `git check-ignore -q` the case's paths before anything is copied into it. For a path not ignored, add `lab/<method>/cases/<case>/` to the nearest `.gitignore`, relative to that file's directory, say so, and check again: **git never ignores a tracked path, so one still not ignored is not written until the user says so.**
3. **Keys.** One `key.md` per case, in the format key.md gives.
4. **Budget.** A ceiling in dollars for the loop, proposed from a round's estimated cost (every case run once) times the rounds the fixes may need. Before any round has run, a round's estimate is the brief's rough cost of one run times the cases. The platform caps nothing, so say that the budget is checked against estimates, before each run.
5. **The go.** **Show every key, the budget and a round's estimated cost, then end the turn there**: the user's go on them is the only go the loop gets, and a notice written between two tool calls can land where the user never sees it. A key the user corrects now is corrected before anything runs.

## 3. Run the loop

Read [log.md](references/log.md) before the first entry: it holds the entry format, the regression rule, how a round is scored and the scorecard. The go opens a series in the log, with its budget. Then, round after round, until a stop:

1. **Run every case once** through `/pipelex-run`'s Start a run, naming `cases/<case>/` as the directory of its inputs. The go is the consent that skill needs.
2. **Read each whole output** from the `main_stuff.json` that `/pipelex-run` saved for the run, or with `mthds_run_results`, by its run id, when nothing was saved, and look at any file a key line is about beside it. **A line whose field was cut (`truncated: true`) or whose file was not seen is unscored, never passed.**
3. **Score every Must and Must not line** as pass, fail or partial, quoting the field and the value you relied on. A reading an Also acceptable line allows passes the line it names; planted facts serve the diagnosis and are not scored.
4. **Log each run** as log.md says: its id, its case, its cost, its duration, its score and the regressions.
5. **Diagnose**, the inputs first, as the guard above says, then the method: which pipe produced the wrong value, and why.
6. **Make one fix**: the change that addresses the most failing lines without touching the contract, through `/pipelex-edit` when it keeps the method's structure and through `/pipelex-design` when it changes it. Log it as the next round's "Changed" line before that round runs.

**The loop stops, and ends the turn on the scorecard**, when:

1. every case meets its pass bar;
2. **the next run would take the series' total past the budget**, its estimate being the highest cost its case has had in the series, or before that its share of the round's estimate: never start a run the budget does not cover;
3. a failing line traces to the inputs, because the inputs and the keys were part of the go, and changing either one changes the experiment;
4. there is no fix in sight, or the only one would change a key, the inputs, or what the main pipe takes or produces;
5. **a round passes fewer key lines than the best round so far, or two rounds in a row pass no more than it**: name the fix it followed, and leave keeping or undoing that fix to the user;
6. a run fails for a reason that is not the method's, ending `TIMED_OUT`, `CANCELLED` or `TERMINATED`, or with a failure that names a provider, a quota or the platform rather than a pipe; or a run is left unfinished;
7. the user interrupts.

A new go opens a new series, with its own budget.

**A run of a case that the lab did not start**, handed over by `/pipelex-run`, is read, scored and logged as steps 2 to 4 say, in an entry outside any round: read [log.md](references/log.md) first. It needs no go, since it has already run, and it starts no run and makes no fix.

## Stops

| Condition | Do this |
|---|---|
| The bundle has a `PipeFunc` over a `.py` of its own | no files run carries that Python, and the loop runs only files: stop before the go and say so; `/pipelex-catalog` saves it with its Python, outside the lab |
| `/pipelex-inputs` leaves one of a case's inputs unfilled | the case cannot run: ask for the file, or leave the case out of the go with the user's say-so |
| `/pipelex-run` stops waiting on a run that is still `RUNNING` | log the run as unfinished with its run id, which `/pipelex-run` can follow later, and stop the loop |

## References

- [frame.md](references/frame.md): at the first move, before asking anything.
- [key.md](references/key.md): at the second move, before writing a key.
- [log.md](references/log.md): at the third move, before the first entry, and when a stop writes the scorecard.
