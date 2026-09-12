# Continuous integration

Everything this repo runs on GitHub lives in `.github/workflows/`. Some of it runs on every pull request, some only on a release-shaped one, and the recipe suite stays off the ordinary pull request because it needs network and minutes. The table says which is which; the sections below say why.

| Workflow | Status check | Runs on | What it runs |
| --- | --- | --- | --- |
| `checks.yml` | `Checks` | every pull request | `make check` |
| `tests.yml` | `Unit tests` | every pull request | `make agent-test` |
| `guard-branches.yml` | `Gate main` / `Gate release` / `Gate dev` | a pull request opened, edited, reopened or pushed to (`pull_request_target`) | the branch-flow rules, no checkout |
| `changelog-check.yml` | `Changelog entry` | a pull request into `main` | `CHANGELOG.md` carries the version being shipped |
| `version-check.yml` | `Version check` | a pull request into `main` or into `release/vX.Y.Z` | the version in the files is the version in the branch name |
| `recipes.yml` | `Recipes` | nightly, on demand, and on a pull request touching the recipe sources | `make test-recipes` |

The status check column is the name GitHub reports, which is the job's name and not the workflow's — that is the string a branch ruleset has to name to make a gate blocking.

## The make targets on every pull request

**`Checks` runs `make check`, and template freshness is the part that matters.** The generated plugin trees — `pipelex/`, `pipelex-codex/`, `pipelex-vibe/` — are checked in, so a template edited without `make build` ships a plugin that disagrees with its own source. `scripts/gen_skill_docs.py --target all --check` re-renders every target and names each generated file that is missing, orphaned, or byte-different, the copied per-skill `references/` included. The same target then runs the Claude and Codex marketplace consistency checks, `ruff format --check`, `ruff check`, a second `ruff check --select=F401 --no-fix` (the config ignores `F401`, so the plain run is blind to an unused import while `agent-check` quietly repairs one), `pyright` and `mypy`.

It is `make check` and deliberately not `make agent-check`: the agent target begins with `fix-unused-imports`, `format` and `lint`, which rewrite files. A check reports; it does not repair. Run `make agent-check` locally, before pushing, and let CI run the read-only half — which now reports everything the agent target would have fixed, the unused imports included.

One thing `Checks` cannot see: the **vendored hook bundle**. `make check` compares each target's `hooks/check.mjs` against `templates/hooks/assets/check.mjs`, so a target that fell behind the template goes red — but nothing compares the template copy against what `npm run build:hook` in `pipelex-sdk-js` would produce today. `make vendor-hook` reaches into a sibling checkout and CI has none, so a stale bundle ships green. That remains a hand gesture, named in the release skill's gates.

**`Unit tests` runs `make agent-test`** — the pytest suite, quiet unless something fails, so a green run is a few lines rather than a screenful. `pyproject.toml`'s `addopts = "-m 'not recipes'"` deselects the recipe suite; `recipes.yml` is what runs that one.

## The branch-flow guard

`guard-branches.yml` enforces the workspace convention that a pull request targets `dev`, that only a `release/vX.Y.Z` branch targets `main`, and that a work branch is named with one of the closed set of prefixes — `fix`, `feature`, `refactor`, `chore`, `docs`, `ci-cd`, `changelog`, `codex`. It is convention enforcement and not security: what actually refuses a merge is the branch ruleset. It checks out nothing and reads every pull-request ref through an environment variable rather than interpolating it into a shell command, because a fork's branch name is text somebody else wrote.

Each of the three jobs is conditional on the base branch, so a pull request whose base is none of `dev`, `main` or `release/v*` runs no job and is refused nothing. That is deliberate: the workspace convention allows a stacked pull request, which targets the branch below it in the stack.

It triggers on `pull_request_target`, which means **GitHub runs the copy of the file that is on the repository's default branch — `main` — whatever branch the pull request targets.** It read the base branch's copy until GitHub changed that on 2025-12-08. That is what keeps a fork from editing its own gate, and it has a consequence worth knowing, because it is larger than it looks: the three gates report **nothing at all** — not a pass, not a skip, no check run — until `guard-branches.yml` has reached `main`, and `main` moves only when a release merges. So from the moment this workflow lands on `dev` until the first release after it, the branch convention is back to memory; and every later edit to the guard is inert in the same way, taking effect a release late. Whether `pull_request_target` is the right trade for a gate whose own header calls itself convention enforcement rather than security is a live question, not a settled one.

## The release-only gates

Neither `changelog-check.yml` nor `version-check.yml` does anything on an ordinary pull request into `dev`; both fire only where a version is being shipped.

The version of record is `targets/prod.toml`'s `[plugin].version`. `make check` is what holds the other targets and the Claude marketplace to it, so `Version check` checks the one relation nothing else can see: that the number in the files and the number in the branch name agree. Into `main` the version must also be strictly greater than the one `main` already carries; into or out of `release/vX.Y.Z` it must equal `X.Y.Z`. Both versions are required to be plain dotted integers before anything is compared, which matches `scripts/check.py` — there is no pre-release form here.

One shape it would refuse: a `dev → release/vX.Y.Z` pull request, because `dev` carries the previous version. `Gate release` allows that pull request and `Version check` would fail it, which is not a contradiction — the release play never opens one. The release branch is cut from `dev` and bumped in place, and the only pull request it opens is into `main`.

`Changelog entry` requires `CHANGELOG.md` to carry a `## [X.Y.Z] - …` heading for that version before the release reaches `main`. Note the shape: this repo's headings carry **no** `v`, which is where it departs from the sibling repos the workflow was ported from. The merge to `main` is the publish here — install is a marketplace add against the default branch — so that pull request is the last moment a release with no changelog entry can be stopped.

## The recipes

`make test-recipes` executes every runnable block the `pipelex-synthetic-inputs` references ship, on both rungs of the environment ladder, and it is the only thing that would catch a reference recipe rotting — the exact failure the suite was written for, after the predecessor's image recipe pointed at a bundle that no longer existed and nothing noticed. It needs network and downloads packages on a cold `uv` cache, so it stays off the ordinary pull request and runs on three triggers instead:

- **Nightly**, which is the backstop against a recipe that rots because a dependency moved rather than because anybody edited it.
- **On demand** (`workflow_dispatch`), for when a recipe is being worked on.
- **On a pull request that touches the recipe sources** — `skills/pipelex-synthetic-inputs/references/`, `templates/skills/pipelex-synthetic-inputs/`, `tests/recipes/`, or the workflow itself. That is the moment an edit can break a recipe, and the one case where waiting minutes for the answer is worth it.

GitHub reads `schedule` and `workflow_dispatch` from the default branch, so both of those stay inert until this file has reached `main` with a release; the path-filtered pull-request trigger works from the day it lands on `dev`. Two things follow from the default branch being where the cron lives. What it tests is `main`, not `dev`, so a recipe broken on `dev` is not caught nightly until it is released — defensible, since `main` is the published artifact, but worth knowing. And GitHub disables a scheduled workflow in a repository that has seen no activity for sixty days, which is exactly the stretch in which a nightly backstop earns its keep; it comes back by hand, from the Actions tab.

## Requiring a check

No ruleset on `dev`, `main` or `release/v*` requires a status check, so every gate above advises and none of them blocks a merge; `make check-github-rules` at the workspace root is what says whether that is still so, rather than this page. Making one blocking means naming its status check in the branch's ruleset on GitHub. Those *names* are deliberately absent from the workspace's `github-rules.toml` — which does govern this repository, as `pipelex-plugins = {}` — because the policy file carries each repository's *shape*, and the `github-rules` tool reads the required check names from the live ruleset and the branch's classic protection and carries them over unchanged. Adding a requirement is therefore an edit to the ruleset and never to that file; the workspace's `docs/github-rules.md` says why.

It also warns of the other direction, and two of the checks here walk straight into it: a required check that nothing posts leaves every merge pending while the branch looks perfectly healthy. `Recipes` posts nothing on a pull request that leaves the recipe sources alone, and the three `Gate *` checks post nothing at all until `guard-branches.yml` is on `main`. Require either before that is true and nothing merges.

The opposite trap is just as quiet. A job that GitHub *skips* because its `if:` was false counts as satisfying a required check, and each `Gate *` job is gated on the base branch — so requiring `Gate main` on `dev` would pass every pull request without testing anything. Require `Gate dev` on `dev`, `Gate main` on `main`, `Gate release` on `release/v*`, and no other pairing.

## Nothing deploys

There is no publish workflow and no tag. The repository is the artifact: on Claude and Codex install is `plugin marketplace add Pipelex/pipelex-plugins`, which serves the default branch, so the merge to `main` is the publish. Nothing runs on that merge.
