---
status: active
item: L-260906-8ac105
---

# `pipelex-scaffold` — findings review round 1 confirmed and did not fix

Round 1 of `/rev` on `pipelex-plugins#21` (branch `feature/Scaffold-skill`, 2026-09-13) ran cubic, the Codex review and adversarial passes, and the official `code-review`. What it fixed is in the pull request and the changelog. This file is the trace for what it confirmed and deliberately left, so none of it is a finding that merely evaporated.

Everything below was read and verified in the tree — none of it rests on a reviewer's word alone. Each entry says why it was not fixed, which is always either "real but not important" or "the fix is a decision, not an edit".

## Carried elsewhere

- **A directory holding only `.git` is one branch A cannot clone into** — the sharpest finding of the round, raised by three reviewers. It needed a ruling because every fix changes behaviour the founder ruled on, so it became its own decision item, `L-260913-f28d9d`. Ruled on 2026-09-13 — branch A acquires beside such a directory and leaves the user's repository standing — and implemented on this branch, so it is no longer carried.
- **A branch-B project writes `.env` that nothing loads into the process** — rediscovered by the Codex review, already open as `L-260912-059765`. No new trace needed.

## Deferred here

- **The report says "this skill made exactly one commit" on paths where it made none.** The GitHub form (`gh repo create --template`) and a self-committing initializer (`create-next-app`) both produce the pristine commit themselves, and the skill correctly says to adopt it rather than force a second one. The unconditional report line at the template's "The report" section then misstates provenance. Real, and cosmetic in effect: the same step already tells the agent to name the commit and its message, so the user sees the truth beside the wrong sentence. Worth one clause next time this file is opened.
- **Step 1 checks a version floor only step 2 can read.** Branch A's prerequisites check Node against "the floor the starter's `package.json` `engines` field names", but step 1 runs before the clone exists, so the authoritative value is unreadable and the check necessarily runs against the hardcoded `22.12` the text itself hedges as "at writing". Harmless while the floor is stable; it becomes wrong silently when a starter raises it.
- **"It is the plugin's third MCP-free skill" is a hardcoded count**, in `CHANGELOG.md` and `docs/decisions.md`. The workspace guide forbids counts in docs because they go stale silently. It is accurate today and the phrasing has precedent already on `dev`, so changing it here would be a lone deviation; it wants doing across the repo at once or not at all.
- **Branch B's ownership sentence is broader than the steps beneath it.** "Nothing beyond what the initializer writes is authored by this skill" is glossed immediately with "no example code, no folder layout of its own, no opinion the framework did not ship", which scopes it to project shape — but steps 3 and 4 then author a `.gitignore` and the env pair. An agent following the explicit imperatives is not actually misled, which is why this is a wording imprecision rather than a defect.
- **The minimal TypeScript recipe still defaults to `--module nodenext`.** Round 1 annotated the default row so the caveat is visible where the command is chosen, rather than twelve lines below it, but it did not change the command. Making the bundler form the default is a recipe change that should be executed before it ships — this campaign's own history is that recipes composed inside a review round became the next round's defects.
- **`.env.example` ships an empty `PIPELEX_API_KEY=`, so the gated append can still leave two assignments.** Round 1 closed the defect that mattered — an append landing *after* a key the user had already filled, which every dotenv reader resolves to the later line. What remains is only the placeholder case, where the later line is the one the skill intends and the value is correct. A user editing the first line and seeing nothing change is the cost; rewriting in place instead of appending would need a `sed -i` whose BSD/GNU spelling differs, which is not worth trading a portability trap for a tidiness gain.
