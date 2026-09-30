# Framing a use case

Read this at the first move, before asking the user anything. It holds the questions that open the framing, the shape of a candidate, and the brief. What the platform can and cannot do, in the builder's terms, is in the shared fit reference the lab reads beside this one.

## The questions

Ask about the workflow, not about Pipelex, and ask no more than you need:

- **What arrives?** The documents, images, pages or messages the work starts from, how many at a time, and in what format.
- **What gets decided or written?** The output a person produces today: a verdict, a set of fields, a memo, a reply, a ranking.
- **Who checks it today, and how?** This is the seed of a key: whatever a reviewer compares against is what "right" means.
- **What does a mistake cost?** A missed clause, a wrong total, a reply sent to the wrong person. Mistakes that cost the most become the traps of a case.

## The shape of a candidate

Give each candidate these points, in this order:

- **Name**, and one line on what it does.
- **Reads and produces**: its inputs and its output, in the builder's terms.
- **Relies on**: the rows of the fit reference's capability table that it uses.
- **Deliverable**: a method alone, which the builder runs from here or saves to the catalog; a web page for a team, which `/pipelex-scaffold` makes from the method-app template; or a command-line tool or code, which `/pipelex-scaffold` and `/pipelex-integrate` make.
- **Rough cost of one run**: an order of magnitude from the steps that call a model. A few text steps cost cents. Extraction adds cost with every page, and image generation outweighs the rest. In the proof lab of September 2026, runs cost from about $0.06 to $1.74, and the dear end was the runs that generated images. Say that this is a guess and that the first round replaces it.
- **Can a right answer be written down in advance?** Answer yes, partly or no, and say why.

## Choosing the first one

Recommend the candidate whose output can be checked against a key and whose inputs can be made safely, from code or with facts planted in them, without the builder's confidential files. A candidate whose right answer is a matter of taste, such as a tagline or a tone of voice, makes a poor first experiment: nothing in its key can fail cleanly. It can come second, once the loop has proved itself on a method that can be scored.

## A method that already exists

A method the user brings with no brief gets one before its keys, and no candidates. Read the bundle's main pipe, its inputs and its output concept, then ask the last two questions above: who checks the output today, and what a mistake costs. Write the brief's use case, Right means and rough cost of one run, counting the cost from the method's steps that call a model, and leave out Candidates and Chosen.

## The brief

`lab/<method>/brief.md`, written once the user picks, or in the short form above for a method that already exists:

```
# Brief: <method>

Use case: the builder's own words.

## Candidates
The two or three proposed, each in the shape above.

## Chosen
The candidate and why.

## Right means
The facts a correct output gets right, and the mistakes that cost the most. These seed the keys.

Rough cost of one run: $… (an estimate until the first round).
Deliverable: …
```
