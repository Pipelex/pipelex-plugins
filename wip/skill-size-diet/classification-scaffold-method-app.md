---
status: active
item: L-260923-0d9cb6
---

# Classification — `pipelex-scaffold`, phase 5b

Phase 5b of [`plan.md`](plan.md) under box A of [`design.md`](design.md): every paragraph of `templates/skills/pipelex-scaffold/SKILL.md.j2` as it stood at `c0b225d`, its class and where it goes. Line numbers are that file's. Phase 5a's account of the same file is [`classification-scaffold.md`](classification-scaffold.md); this one covers what box E's amendment left for this phase and the trim that brings the whole skill under the ceiling.

- **The method app becomes the family's two commands.** `pipelex-method-apps` published `@pipelex/create-method-app` and the template's `make serve` (`L-260922-12f302`). The skill runs `npm create --yes @pipelex/method-app@latest '<dir>' -- --method '<method>' --quiet`, then `make -C '<dir>' serve`, and keys its stop table on the verdict line each prints. The acquisition chain, the pristine commit of the copy, the `make create` block, the loopback check of the dev script and the dev-server start leave the skill with the tests that executed them.
- **A copy the initializer did not finish moves to a reference**, `references/uncreated-copy.md`, entered on `copied`, on `failed: create`, or when the user stands in a copy not yet made theirs. It carries the fresh-clone shortcut's git reading, the commit that confirms on the user's repository, and the `make create` block with its warnings and its refusal and failure readings, as they stood.
- **The rest of the skill is trimmed under the ceiling** by the same rule: branch B's report words for the env verdict move into `references/initializers.md`, which branch B reads before anything runs, and each rationale sentence goes to `docs/decisions.md`.

## The behaviour changes

Each is named in the pull request, as box G requires. The first four are the family's commands' own rules, which box E's amendment adopts; the last two are phase 5a's round-4 deferrals, noted on this phase's item.

- **The method app is created by the family's initializer and served by `make serve`.** What the user gets is the same project and the same running page, reached through the family's programs instead of the skill's.
- **A lone `.git` of the user's takes the method app's commit without a question.** The skill confirmed a pristine commit into a repository that already existed, because the commit landed on the user's branch, on top of their history, with `add -A` sweeping their worktree in. The initializer refuses a repository with commits (`repository-has-history`) or with a staged file (`repository-has-staged-files`) and commits the template's files alone, so none of the three grounds holds. Branch B still asks, since `commit-pristine.sh` commits on top of history.
- **A method app inside another repository's work tree gets no repository and no commit.** The skill made the copy a repository of its own there; the initializer leaves the project as new files of the enclosing repository and says so on its `git:` line, which the report relays.
- **The port is `make serve`'s to choose.** It takes the first port from 4300 to 4309 that no other directory holds, and refuses with `port-held` when all are; the skill stepped up one port at a time with `port-check`. A server the user started with `make dev` is reported as `already-serving` and left running, where the skill asked whether to stop it. The report's stop command is the one the verdict names, `make stop`, instead of an `lsof` loop, and `curl` and `pgrep` are no longer prerequisites.
- **`references/version-managers.md` looks for `uv` through `asdf` and `mise`**, and its warning that the harness must be restarted before `/pipelex-integrate` follows any runtime reached through a `PATH` prefix rather than naming `nvm` and `fnm` alone.
- **`commit-pristine.sh` unstages a `.env` or a `node_modules/` an initializer had staged** before the script's `.gitignore` lines, when the last commit does not hold it.

## Rows

| Lines | Text | Class | Destination |
|---|---|---|---|
| 1–5 | Frontmatter; the description says the method app is "created for that method in one command" and the fresh copy is finished "with the template's own gesture" | main path | stays, reworded for the family's initializer |
| 9 | "This skill has exactly two branches and carries no templates of its own" | guard | stays |
| 11 | Branch A: "You copy the directory, commit it once as it came, and run the copy's **own** `make create` … The create gesture lives in the template and is never reimplemented here" | main path | stays as the initializer and `make serve`: "Both are the family's commands, and nothing they do is reimplemented here" |
| 12 | Branch B: every other project to the ecosystem's initializer, "You run it; you never assemble a project by hand" | main path, guard | stays, shortened |
| 14 | "**The starters are not scaffolded from.**" | main path | stays |
| 16 | "Every path makes one pristine commit … **The method app ends with the app running** … The initializer ends with an env file … and the hand-off" | main path | the two endings are each branch's last step and the report's; "the one commit this skill makes" is branch B's step 2 |
| 18 | "What this skill is not" — no template engine, no bootstrap, not a runner or deployer; "The one server it starts is the method app's own dev server"; "It needs no MCP tool and never handles an API key itself" | guard, rationale | stays without "not a bootstrap" and the server sentence, which `make serve` and "Never start the server any other way" now carry |
| 20 | "**Never print a key, and never ask for one in the conversation.**" … "**the value moves only through a shell that expands the variable itself, and never through you**" … the presence test … "**no reading an env file back**" | guard | stays; the key's presence test leaves, since the initializer tests it and refuses `no-key`, and the plane test stays in the report where it is used |
| 24 | "A cheap, reliable signal decides; an inconclusive one asks one question" | main path | stays |
| 28, 29 | The Language and Which-branch rows, with the question offering the method app first | main path | stay, shortened |
| 30 | The Where row: the directory named, "here", a kebab-case name; the lone-`.git` ruling; branch B does not re-run `git init`; branch A "acquires beside it and moves in"; the non-empty refusal and "**A lone `.git` is the only entry …**" | main path, guard, rationale | the signals stay in the row; the ruling and the refusal move under the table as one paragraph; the acquisition sentence is deleted (the initializer's); why a lone `.git` arrives (`mkdir && git init`) and the git-init sentence go to rationale |
| 31 | GitHub or local, "read [references/github.md] before running any `gh` command" | guard, branch | stays |
| 33 | "**The method app needs the method first.**" and what a method is | main path | stays |
| 35 | The directory named after the method | main path | stays |
| 37 | "**The fresh-clone shortcut.**" — "branch A entered at step 4 … Do not clone again", and how a copy says what it is | branch | the recognition and a pointer stay: "is finished and never created again: read [references/uncreated-copy.md]"; the rest is the reference's |
| 39–55 | "**Read git before initializing anything.**", the `origin` and `--show-prefix` block, "**A directory another repository already tracks is not a fresh copy**", the pristine commit first when there is no commit, confirmed | branch, guard | `references/uncreated-copy.md`, "A copy the initializer did not make", verbatim; its tests follow it |
| 57 | "**Every placeholder is substituted as one shell word.**" and why | guard, rationale | stays, shortened; the `mkdir -p my app` illustration is dropped |
| 61 | Mode: automatic by default; "One thing always confirms, in every mode: **`gh repo create`**"; the pristine commit needs no confirmation on a directory this skill created; "**A pristine commit into a directory that already held a repository is the exception**, on either branch" | guard | stays; the exception names branch B alone, and why the method app's needs none goes to `docs/decisions.md` |
| 63 | Interactive mode runs `make create` with `DRY_RUN=1` first; the first run installs the dependencies and sets `core.hooksPath` | main path, branch | the initializer's `--dry-run` in `SKILL.md`; showing the plan and what the dry run cost go to `references/uncreated-copy.md`, which its `copied` verdict enters |
| 69 | Step 1: "**stop** on a missing piece … **Never install a toolchain, and never let a version manager download one.**" and the pointer to `version-managers.md` | guard, branch | one Prerequisites section for both branches, the guard once |
| 71 | Node at the `engines` floor, `npm`; `make`, `curl`, `lsof`, `pgrep` and why | main path | Node's floor and `npm` stay; the initializer refuses without `make` or `git` and `make serve` without `lsof`, each a stop row; `curl` and `pgrep` are no longer needed |
| 72 | `git`; the GitHub form needs `gh` | main path | `git` stays; `gh` is `references/github.md`'s |
| 74 | "**The method app also needs a key its gesture can read.**" — the presence test before step 2, the two ways a key reaches the gesture, `.env.local` written by the user, the base URL | guard, branch | the initializer refuses `no-key` before writing anything, and that row offers the two ways; the `.env.local` path after `--no-create` is `references/uncreated-copy.md`'s |
| 78–98 | Step 2, the acquisition: the chain, its properties, "**The `webapp-js/` test is load-bearing.**", the default-branch head | main path, guard | deleted: the initializer carries the template in its package and writes it exclusively, refusing a non-empty destination |
| 100–106 | Step 3, the pristine commit: the command, "This is the **one commit this skill makes**", the commit on the user's branch confirmed | main path, guard | the initializer's; for a copy made by hand, `references/uncreated-copy.md`, with the copy's `package.json` version in the message |
| 110–117 | Step 4: the `make create` block; `<method>` as an absolute path; `NAME`, `TITLE`, `DESCRIPTION` only from the conversation; `AUTHOR_…` and `LICENSE…` only when given; `METHOD_NAME`, `PIPE`, `LABEL` for a refusal | main path, guard | the initializer's options in `SKILL.md`: "only with a value the user gave, never an invented one"; the block and the absolute path go to `references/uncreated-copy.md`, since the initializer reads a relative path from where it runs |
| 119 | What the gesture does is the template's to say; several minutes; its log is safe to read, `.env.local` is not | main path, guard | "It takes several minutes" stays; the rest is `references/uncreated-copy.md`'s, and the key guard covers `.env.local` |
| 121 | "**The gesture's warnings are read from the whole log, not from its tail.**", the `LICENSE` warning and its answer | main path | the initializer prints the warnings above its verdict, and the report relays them with the `LICENSE` holder first; the block's reading is `references/uncreated-copy.md`'s |
| 123 | A refusal in the read-only half; a capability the plane does not serve, "never substitute a base URL the user did not declare" | branch, guard | the reading goes to `references/uncreated-copy.md`, entered on `failed: create`; the guard stays in the `failed: create` row |
| 124 | A failure after the scaffold, "never by editing `src/generated/`", "A red `make all` is fixed, never handed off" | branch | `references/uncreated-copy.md` |
| 128–134 | Step 5: `port-check`, the next port up, a port served by this checkout, "**Never start a second server while one this step started still runs**" | main path, guard | deleted: `make serve` chooses the port and reports its own server as `already-serving` |
| 136–142 | "**The server listens on this machine alone, and a copy that cannot promise it is not started.**", the dev-script check, the refusal and the hand-started server | guard | "**Never start the server any other way**" stays; `make serve` refuses a dev script that does not bind loopback as `not-loopback`, whose row says to report no URL; why goes to `docs/decisions.md` |
| 144–165 | The detached start, the wait, the process-tree stop, the holder and listener checks, the page request | main path | deleted: `make serve` |
| 167–173 | The three readings of a refusal, the retries, "**Never report a URL that did not answer.**", "Nothing is run through the method" | stop, guard | the readings are `make serve`'s verdict rows; both guards stay |
| 179 | Branch B's prerequisites and the Python interpreter range | guard | the shared Prerequisites section |
| 183–187 | Branch B step 2: read `initializers.md`, run it, an interactive one handed to the user, nothing authored beyond it, `uv sync` | main path, guard | stays as step 1, shortened |
| 191–199 | Branch B step 3: ask on a lone `.git`, run `commit-pristine.sh`, its verdicts | guard, main path | stays as step 2 |
| 203–207 | Branch B step 4: `write-env-file.sh` and what it writes | main path | stays as step 3, shortened |
| 211 | Branch B step 5: no SDK dependency, no `methods/` | guard | stays as step 4 |
| 215 | The method app's report: the URL first, the `lsof` stop loop, the `make dev` restart | main path | stays; the stop command is the one the verdict names, and the restart is `make serve` |
| 217–224 | The report's items: created, the template's version and SHA, the one commit, `make create`'s changes uncommitted, the warnings with the `LICENSE` holder first, the plane, a second method | main path | stay; the git outcome replaces the commit, and names no commit inside another repository's work tree |
| 226 | The plane read by a test; `.env.local` written by the user kept; `make add-method`; `npm run codegen` | main path, guard | stays; the kept `.env.local` is `references/uncreated-copy.md`'s |
| 228 | The initializer's report items | main path | stays |
| 230–236 | The words for `filled`, `kept`, `empty`, `base-url=copied`, `base-url=file`, and the production-key warning | main path | `references/initializers.md`, "The env verdict, in the report's words", which branch B reads before anything runs; "**and not validated**" stays in `SKILL.md` |
| 238–241 | The two closing lines, with the version-manager exception | main path | stay; the pointer names a `node` missing from the `PATH`, as phase 5a's smoke sessions required |
| 247 | A toolchain piece missing | stop | stays, joined by `refused: missing-tool` and `node-too-old` |
| 248 | The target directory not empty | stop, guard | stays, joined by `refused: not-empty` |
| 249–251 | The clone fails; a `.pipelex-method-apps-…` directory beside the destination; a clone with no `webapp-js/` | stop | deleted with the acquisition |
| 252 | `gh` absent or not authenticated | stop | `references/github.md`'s already; the row is deleted as a duplicate |
| 253 | The method app has no key for its gesture | stop | the `refused: no-key` row |
| 254, 255 | `make create` refuses; fails after its scaffold | stop | the `failed: create` row, which points at `references/uncreated-copy.md` and keeps the base-URL guard |
| 256 | The copy has no `make create` | stop | `references/uncreated-copy.md` |
| 257–263 | The port rows, the loopback row, nothing listening, a foreign holder, a page that is not `200`, a server beyond loopback | stop | `refused: not-loopback` keeps its row; the rest are `make serve`'s own verdicts, relayed in one row |
| 264 | An interactive initializer | stop | branch B's step 1 carries it; the row is deleted as a duplicate |
| 265–272 | The two scripts' refusals | stop | one row, which names the refusals that mean a mistyped command and relays the rest |
| 273 | A template's own checkout | stop | `refused: inside-template-checkout`, and an `origin` at `Pipelex/pipelex-method-apps` for a copy made by hand |
| 277–280 | The reference index | index | stays, with `references/uncreated-copy.md` added |
