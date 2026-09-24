# Writing an answer key

Read this at the second move, before writing a case's key. A key lists the right answers for one case's inputs, and it is written before the method runs on them. It is what every run of that case is scored against, and the only thing that makes one run comparable with the next.

## The format

`lab/<method>/cases/<case>/key.md`, with fixed sections. Every line carries a label, so that the log can cite it: "M3 failed", "N2 regressed".

```
# Key: <case>

Inputs: what the case holds, in one or two sentences, and where it came from: the user's files, or `/pipelex-synthetic-inputs`.

## Planted facts
F1. …

## Must
M1. …

## Must not
N1. …

## Also acceptable
A1. …, for M…

## Pass bar
Which lines must pass for the case to pass.
```

## The lines

- **Planted facts** are what the case's inputs hold that the method must find. For files from `/pipelex-synthetic-inputs`, take them from its report, which lists them for every file, then open each file and confirm that it shows them. For the user's own files, read the files and write down what they show. A diagnosis checks a failing line against these first.
- **One checkable fact per line**, stated as what the output shows: a field and its value, a count, an order, something present or something absent. "The totals are right" is not a line, but "`total_approved` is 786.57" is.
- **Name the output field** wherever the method's output concept has one. Read the bundle's output concept first. A line that names its field can be scored by quoting that field, and later by a judge method, without the session that wrote the key.
- **Give a tolerance** where rounding or wording can vary: "within 0.01", "in any wording that names both parties".
- **Must not** lines name the plausible wrong answers, which are the traps: a misread total, a duplicate that is not flagged, an item that must not exist. A method that avoids them has read the case rather than guessed at it.
- **Also acceptable** lists the readings that are defensible too, each with the lines it satisfies, so that a sound alternative is not scored as a failure.
- **Pass bar**: usually every Must and Must not line. Name any line that may be partial, and why.

## A clean case and a trap case

The clean case is the one the method should pass cleanly: ordinary inputs, no tricks, and its key mostly Must lines. The trap case plants the mistakes that cost the most, from the brief's "Right means", and its key leans on Must not lines. A fix for the trap case that breaks the clean case shows up as a regression in the same round.

## A worked example

This is adapted from an expense-audit method that the proof lab keyed. The case is a three-day trip.

```
# Key: chicago-trip

Inputs: six receipts from one trip — a hotel folio, a restaurant bill with a handwritten tip, a taxi, a deli lunch photographed twice, and a client dinner for two, made by `/pipelex-synthetic-inputs`.

## Planted facts
F1. Receipt 2's total is handwritten, 105.40, over a printed subtotal of 90.40.
F2. Receipts 4 and 6 are the same deli order, #0457.
F3. Receipt 5 says "client dinner" for two guests, and names nobody.

## Must
M1. `total_claimed` is 878.07.
M2. `total_approved` is 786.57, and `total_pending` is 44.75.
M3. Receipt 6 is rejected, with `duplicate_of` set to 4.
M4. Receipt 2 rejects the wine, 28.00, and approves 77.40.
M5. The note to the employee asks for the attendees' names and the client's name.

## Must not
N1. Receipt 2 read as 90.40.
N2. Receipt 5 approved in full, or rejected outright.
N3. The day's excess computed with the deli lunch counted twice, as 63.50 instead of 44.75.

## Also acceptable
A1. Receipt 6 kept and receipt 4 rejected as the duplicate: the same money and the same outcome, for M3.

## Pass bar
Every Must and Must not line.
```
