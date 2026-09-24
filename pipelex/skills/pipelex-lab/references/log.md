# Keeping the log

Read this at the third move, before the first entry, and again when a stop writes the scorecard. The log is `lab/<method>/log.md`. Entries are appended, newest last, and never rewritten: each one records credit spent.

## A series

Each go opens a series, which runs until a stop:

```
# Series 2 · 2026-09-24 · budget $5.00
Cases: clean-invoice, problem-invoice. Estimate: $0.40 a round, from series 1's last round. Start: commit abc1234.
```

`Start` is `git rev-parse --short HEAD` when the project is a git repository, so that `git diff <start>` shows every fix the series made. Leave it out when the project is not a repository.

## A round and its runs

```
## Round 3 · 2026-09-24
Changed: the term-length rule counts from the commencement date, by /pipelex-edit on extract_terms.

### run_… · problem-invoice
$0.21 · 64 s · 9 of 11 lines · pass bar met: no
Failed: M3 (the memo puts the relocation clause below the medium items). Partial: M7 (names the landlord, not the guarantor). Regressed: M5, which passed at run_….
```

- **Changed** says in one line what the fix changed and through which skill. In the first round of a series it says what changed since the last series, or "baseline" in the first series.
- **The cost** is `usage.cost_usd` from `mthds_run_results`. When it is `null`, write "cost unknown" and count the round's estimate in its place, so that the budget is never checked against a zero nobody measured.
- **The duration** runs from the status's `created_at` to its `finished_at`.
- **The score** is the lines passed out of the key's lines. Partial and unscored lines count as not passed, toward the pass bar and toward the round's score alike.
- **A cut output** adds a line: "Output cut at the size cap: M4 and M6 unscored."
- **A failed run** is logged with the status and the first line of its `failure_message`, as `FAILED · …`, and scores nothing.
- **An unfinished run** is logged as `UNFINISHED · still RUNNING after …`, with its run id, so that `/pipelex-run` can follow it later.

## Regressions and the best round

- **A regression** is a line of a case that passed in an earlier run of that case and does not pass now. Name the run where it last passed. Compare only with runs made since the case's key last changed.
- **A round's score** is the number of key lines passed across all its cases. The best round is the one with the highest score in the series. The loop's fifth stop compares each new round with it.

## A key changes

When the user changes a key, append an entry before the next run:

```
## Key changed · 2026-09-24 · problem-invoice
M4 now reads "…", because ….
```

Rounds before it are no longer compared with rounds after it: regressions and the best round count from here.

## The scorecard

The last message of the turn when the loop stops, and the last entry of the series in the log:

- per case, the lines passed out of the total, whether its pass bar is met, and each line that is still failing, with its label;
- the rounds run in the series, what they spent against the budget, and the total spent over the whole log;
- the stop that ended the series, in one line;
- what the user decides next: keep or undo the last fix, correct an input, change a key, raise the budget, or move on to the deliverable. Where there is a `Start` commit, `git diff <start>` shows every fix.
