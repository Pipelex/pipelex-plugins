# What a method does, and what carries the rest

Read this when a request says where its input comes from, where the result goes, when it runs or what it does in the world ("every morning", "when an email arrives", "from our Drive", "post it to Slack", "update the CRM", "reply to the customer"), and at the lab's first move. It says what a method can and cannot do, how to split a request between the method and whatever carries it, which code you may write around a method, and how to answer.

## What a method is

A method reads the values and files it is given, and the public web, and returns its results. It does not fetch from a mailbox, a drive, a chat or a business system; it does not run on a schedule or when something arrives; and it does not write back, send or act. That is by design: a method is a function of its inputs, so it can be checked against an answer key, run by any agent, platform or application, and approved by IT. Whatever calls the method brings its inputs and takes its results where they go.

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
| Run custom Python | `PipeFunc` | It is experimental on the hosted platform, where it runs with no network, so a first candidate does without it. |

**What the table does not name, a method does not do.** A connection to the builder's own systems, memory from one run to the next, a schedule, or an action such as sending an email belongs to a carrier, below.

## The parts of a request

- **Trigger**: what starts it, whether a person, a clock, or an arrival such as an email or a file.
- **Source**: where the input lives: in hand, in a mailbox, a drive or a business system, or on the public web.
- **Transformation**: reading, judging, extracting, writing. **This part is the method.**
- **Destination**: where the result lands: in front of a person, in a system, or in a message.
- **Action**: what is done in the world with it, such as sending, filing, updating or paying.
- **Checkpoint**: who approves before an action.

## The kinds of request

The test is whether the method can be stated as "given X in hand, produce Y". If it can, there is a method, whatever surrounds it. If the only verbs left are move, copy, send, sync and notify, there is none. One request can mix kinds, so judge each part.

| Kind | The sign | What to do |
|---|---|---|
| **Fits** | The inputs are in hand (files, text, public URLs) and the output is a deliverable | Build it |
| **A method and its carriers** | A transformation with a trigger, a source, a destination or an action around it | Build the method, name the carrier, and offer to wire it with what already exists |
| **Mostly plumbing** | Moving, copying, syncing or notifying, with no judgement | Say in one sentence that an automation platform or a connector hub does this, and offer the judgement if there is one, such as naming and filing each document by what it is |
| **Agent work** | Initiative, conversation, memory, open-ended exploration | Say that the assistant the user is talking to does this, and offer a method for the procedural core if it recurs |
| **Beyond the runtime today** | Audio or video in, a Word or PDF file out, retrieval over a large corpus | Name the workaround (the recording platform's transcript, a PDF export, a result rendered from HTML, a batch over a modest pile) and name the gap |

## The carriers

A carrier fetches the inputs, starts the run and does something with the result. Nothing on the Pipelex platform runs a method on a schedule or when something arrives: that is always a carrier's job.

| Carrier | Fits when | How |
|---|---|---|
| **You, in this session, with the host's connectors** | Once or now and then, with a person present and the input in a system the host already reaches | Fetch with the connector (the host's own, such as the claude.ai connectors Claude Code loads, an MCP server, or a connector hub such as Zapier MCP or Composio), save the file to a temporary directory outside the project and give that path to `/pipelex-inputs`, which copies it in under its ignore guard; run it with `/pipelex-run`, and deliver with the connector once the user approves. Before promising a `Document` input, check that the connector hands you the file and not only its text |
| **An automation platform** | Recurring and unattended, started by a clock or an arrival | n8n with the Pipelex node, between the platform's own trigger and destination nodes; Make, Zapier or any platform that can call an HTTP API, through `POST /v1/start` and the run's results. The Pipelex node takes a file from an earlier node through its Binary Inputs, in a node version that has them; on another platform, the file must sit at a URL the run can fetch |
| **A method app** | A team drops a file in a browser and reads the result | `/pipelex-scaffold` makes one from the method's contract |
| **Application code** | A product owns the data and calls the method as a function | `/pipelex-integrate` writes the typed call; the application fetches the inputs and delivers the result |
| **A scheduler** | A watch or a weekly report | Cron, CI or a platform's schedule calls the SDK; state such as last week's result goes back in as an input |

**Choosing one.** Ask only the question the request leaves open: how often it runs, who starts it, where the input lives, where the result must land, and whether a person approves before anything is sent or changed. The usual answers:

- Once, with files in hand: run it here.
- Once or now and then, with the input in a system the host reaches: you, with the host's connector.
- A team, over and over: a method app.
- Recurring and unattended: an automation platform with the method as one step, and a person approving before any action.
- Inside a product: the SDK.

## The code you write

- **Inside a method, nothing that reaches another service.** That means no network call, no credential and no client for another service, in a `PipeFunc` or anywhere else in the bundle. The hosted sandbox runs a `PipeFunc` with no network, so such a method validates and then fails, and a credential in a bundle travels wherever the bundle goes. Reading a web page is `PipeExtract`'s job and searching the web is `PipeSearch`'s.
- **Around a method, by default, glue to Pipelex's own surfaces**: the typed call site, a method app, an n8n workflow built from the platform's nodes and Pipelex's, a short script that runs the method over a folder of exported files, or the host's connectors for a one-off run.
- **A client for another service only when the user asks for one after hearing what it entails**: registering an OAuth app and its consent screen, storing and refreshing tokens, scopes, paging and rate limits, and upkeep whenever the service changes its API. Name the automation platform or connector hub that would do it without code first. If the user still wants it, it is their own code, outside the bundle, calling the method through the SDK, and read-only unless they ask for writes: a read-only client carries a test that fails when a write call appears.
- **Promise nothing that nothing runs**: no schedule, trigger, write-back or sent message unless a carrier does it. A link that needs the user's sign-in reaches a run as a sign-in page, so a file behind a private Drive, OneDrive, SharePoint or Notion link is downloaded or exported first.

## The answer

A few sentences, in this order:

1. **What you will build**: the method, as "from X to Y".
2. **What carries it**, and what the user needs for that: their n8n, their Gmail connector, a page for their team.
3. **What you will not do**, in one line with the reason.
4. **One question** when a choice is needed; otherwise go on and build.

State the limit once, as a property of the product, and neither lecture nor apologise. For "summarise my unread Gmail every morning and post the digest to Slack":

> I'll build the part Pipelex does: a method that takes a batch of emails and returns a digest ranked by what needs your answer, with the reason for each. Pipelex methods don't read mailboxes or post to Slack, on purpose: that part belongs to whatever runs the digest every morning. If you use n8n, I'll lay out the workflow: a schedule, the Gmail node, the Pipelex node and the Slack node. If you just want today's digest, I can fetch your mail with your Gmail connector and run it here. Which one?
