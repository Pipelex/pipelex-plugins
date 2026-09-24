# Framing a use case

Read this at the first move, before asking the user anything. It holds the questions that open the framing, what the platform can and cannot do in the builder's terms, the shape of a candidate, and the brief.

## The questions

Ask about the workflow, not about Pipelex, and ask no more than you need:

- **What arrives?** The documents, images, pages or messages the work starts from, how many at a time, and in what format.
- **What gets decided or written?** The output a person produces today: a verdict, a set of fields, a memo, a reply, a ranking.
- **Who checks it today, and how?** This is the seed of a key: whatever a reviewer compares against is what "right" means.
- **What does a mistake cost?** A missed clause, a wrong total, a reply sent to the wrong person. Mistakes that cost the most become the traps of a case.

## What the platform can do

Each row names the pipe that does it, whose section of the MTHDS reference is the authority. Say what a row says, in the builder's words, and nothing more.

| In the builder's terms | Pipe | What to say with it |
|---|---|---|
| Read a document or an image | `PipeExtract` | It reads a PDF, an image or a web page, and nothing else. A Word, Excel or PowerPoint file fails the run at the extraction, so a method over Office documents takes the PDF exported from them. |
| Read a web page | `PipeExtract` | A web page is a `Document` holding the page's URL, read with the `@default-extract-web-page` model. |
| Understand, decide, extract fields, write | `PipeLLM` | It reads text and images and produces text or structured fields that the method defines. |
| Search the web | `PipeSearch` | It returns an answer with its sources: a title, a URL and a snippet for each. |
| Generate images | `PipeImgGen` | It makes images from a prompt. These are the dearest runs. |
| Run over a list | `PipeBatch` | It applies one step to every item of a list, such as every receipt or every clause. |
| Route a case by a condition | `PipeCondition` | It sends each case down the branch its condition selects. |
| Do several things at once | `PipeParallel` | It runs independent steps side by side. |
| Fill a template | `PipeCompose` | It assembles a document or a message from the values earlier steps produced. |
| Run custom Python | `PipeFunc` | It is experimental on the hosted platform, so a first candidate does without it. |

**What the table does not name, the lab does not promise.** When a use case needs something else, such as a connection to the builder's own systems, memory from one run to the next, or an action in the world like sending an email, say that it has not been checked here, and let `/pipelex-design` settle whether a method can do it.

## The shape of a candidate

Give each candidate these points, in this order:

- **Name**, and one line on what it does.
- **Reads and produces**: its inputs and its output, in the builder's terms.
- **Relies on**: the rows of the table above that it uses.
- **Deliverable**: a method alone, which the builder runs from here or saves to the catalog; a web page for a team, which `/pipelex-scaffold` makes from the method-app template; or a command-line tool or code, which `/pipelex-scaffold` and `/pipelex-integrate` make.
- **Rough cost of one run**: an order of magnitude from the steps that call a model. A few text steps cost cents. Extraction adds cost with every page, and image generation outweighs the rest. In the proof lab of September 2026, runs cost from about $0.06 to $1.74, and the dear end was the runs that generated images. Say that this is a guess and that the first round replaces it.
- **Can a right answer be written down in advance?** Answer yes, partly or no, and say why.

## Choosing the first one

Recommend the candidate whose output can be checked against a key and whose inputs can be made safely, from code or with facts planted in them, without the builder's confidential files. A candidate whose right answer is a matter of taste, such as a tagline or a tone of voice, makes a poor first experiment: nothing in its key can fail cleanly. It can come second, once the loop has proved itself on a method that can be scored.

## The brief

`lab/<method>/brief.md`, written once the user picks:

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
