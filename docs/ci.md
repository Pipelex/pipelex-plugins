# Continuous integration

Everything this repo runs on GitHub lives in `.github/workflows/`. Three things run on every pull request, two more only on a release-shaped one, and one is kept off pull requests entirely because it needs network and minutes.

| Workflow | Status check | Runs on | What it runs |
| --- | --- | --- | --- |
| `checks.yml` | `Checks` | every pull request | `make check` |
| `tests.yml` | `Unit tests` | every pull request | `make agent-test` |
| `guard-branches.yml` | `Gate main` / `Gate release` / `Gate dev` | a pull request opened, edited, reopened or pushed to (`pull_request_target`) | the branch-flow rules, no checkout |
| `changelog-check.yml` | `Changelog entry` | a pull request into `main` | `CHANGELOG.md` carries the version being shipped |
| `version-check.yml` | `Version check` | a pull request into `main` or into `release/vX.Y.Z` | the version in the files is the version in the branch name |
| `recipes.yml` | `Recipes` | nightly, on demand, and on a pull request touching the recipe sources | `make test-recipes` |

The status check column is the name GitHub reports, which is the job's name and not the workflow's — that is the string a branch ruleset has to name to make a gate blocking.

## The two gates on every pull request

**`Checks` runs `make check`, and template freshness is the part that matters.** The generated plugin trees — `pipelex/`, `pipelex-codex/`, `pipelex-vibe/` — are checked in, so a template edited without `make build` ships a plugin that disagrees with its own source. `scripts/gen_skill_docs.py --target all --check` re-renders every target and names each generated file that is missing, orphaned, or byte-different, the copied per-skill `references/` included. The same target then runs the Claude and Codex marketplace consistency checks, `ruff format --check`, `ruff check`, `pyright` and `mypy`.

It is `make check` and deliberately not `make agent-check`: the agent target begins with `fix-unused-imports`, `format` and `lint`, which rewrite files. A check reports; it does not repair. Run `make agent-check` locally, before pushing, and let CI run the read-only half.

**`Unit tests` runs `make agent-test`** — the pytest suite, quiet unless something fails, so a green run is a few lines rather than a screenful. `pyproject.toml`'s `addopts = "-m 'not recipes'"` deselects the recipe suite; `recipes.yml` is what runs that one.

## The branch-flow guard

`guard-branches.yml` enforces the workspace convention that a pull request targets `dev`, that only a `release/vX.Y.Z` branch targets `main`, and that a work branch is named with one of the closed set of prefixes — `fix`, `feature`, `refactor`, `chore`, `docs`, `ci-cd`, `changelog`, `codex`. It is convention enforcement and not security: what actually refuses a merge is the branch ruleset. It checks out nothing and reads every pull-request ref through an environment variable rather than interpolating it into a shell command, because a fork's branch name is text somebody else wrote.

It triggers on `pull_request_target`, which means **GitHub runs the copy of the file that is on the base branch, not the copy on the pull request's head.** That is what keeps a fork from editing its own gate, and it has one consequence worth knowing: a change to this workflow — its first appearance included — does nothing until it has landed on the branch it protects.

## The release-only gates

Neither `changelog-check.yml` nor `version-check.yml` does anything on an ordinary pull request into `dev`; both fire only where a version is being shipped.

The version of record is `targets/prod.toml`'s `[plugin].version`. `make check` is what holds the other targets and the Claude marketplace to it, so `Version check` checks the one relation nothing else can see: that the number in the files and the number in the branch name agree. Into `main` the version must also be strictly greater than the one `main` already carries; into or out of `release/vX.Y.Z` it must equal `X.Y.Z`.

`Changelog entry` requires `CHANGELOG.md` to carry a `## [X.Y.Z] - …` heading for that version before the release reaches `main`. Note the shape: this repo's headings carry **no** `v`, which is where it departs from the sibling repos the workflow was ported from. The merge to `main` is the publish here — install is a marketplace add against the default branch — so that pull request is the last moment a release with no changelog entry can be stopped.

## The recipes

`make test-recipes` executes every runnable block the `pipelex-synthetic-inputs` references ship, on both rungs of the environment ladder, and it is the only thing that would catch a reference recipe rotting — the exact failure the suite was written for, after the predecessor's image recipe pointed at a bundle that no longer existed and nothing noticed. It needs network and downloads packages on a cold `uv` cache, so it stays off every pull request and runs on three triggers instead:

- **Nightly**, which is the backstop against a recipe that rots because a dependency moved rather than because anybody edited it.
- **On demand** (`workflow_dispatch`), for when a recipe is being worked on.
- **On a pull request that touches the recipe sources** — `skills/pipelex-synthetic-inputs/references/`, `templates/skills/pipelex-synthetic-inputs/`, `tests/recipes/`, or the workflow itself. That is the moment an edit can break a recipe, and the one case where waiting minutes for the answer is worth it.

GitHub reads `schedule` and `workflow_dispatch` from the default branch, so both of those stay inert until this file has reached `main` with a release; the path-filtered pull-request trigger works from the day it lands on `dev`.

## Nothing is required yet

As of this writing the `dev`, `main` and `release/v*` rulesets require **no** status check, so every gate above advises and none of them blocks a merge. Making one blocking means naming its status check in the branch's ruleset on GitHub. That name is deliberately absent from the workspace's `github-rules.toml`: the policy file carries each repository's *shape* and the `github-rules` tool reads the required check names from the live ruleset and carries them over unchanged, so adding a requirement is an edit to the ruleset and never to that file. The workspace's `docs/github-rules.md` says why, and warns of the other direction too — a required check that nothing posts refuses every merge into the branch while looking perfectly healthy.

## Nothing deploys

There is no publish workflow and no tag. The repository is the artifact: on Claude and Codex install is `plugin marketplace add Pipelex/pipelex-plugins`, which serves the default branch, so the merge to `main` is the publish. Nothing runs on that merge.
