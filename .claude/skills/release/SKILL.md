---
name: release
description: >
  Cut a release of pipelex-plugins, the CLI-free plugin marketplace shipping the
  Pipelex skills and hooks to Claude Code, Codex and Mistral Vibe: the
  release/vX.Y.Z worktree, the matched version bump across every targets/*.toml
  and the Claude marketplace, the rebuild that restamps the generated manifests,
  the changelog entry, the local gates, one commit, and a pull request to main.
  Use when the user says "release", "cut a release", "bump version", "prepare a
  release", "make a release", "ship it", "create release branch", "promote dev to
  main", or any variation of shipping a new version of the plugins. Changelog
  content passed inline ("/release Added the pipelex-synthetic-inputs skill")
  becomes the entry. The merge is landed by /ledger-land, never by this skill.
---

# Releasing pipelex-plugins

The procedure is the workspace release play, [`docs/releasing.md`](../../../../docs/releasing.md) at the workspace root — `../docs/releasing.md` from this repo's own root, which resolves the same from the main checkout and from any worktree. Read it first, then run it with what follows. The repo key is `pipelex-plugins`, the base is `dev`, and the pull request targets `main`. The release worktree is `_pipelex-plugins--release`, made with `wt add pipelex-plugins release --branch release/vX.Y.Z`. The repo declares neither `.worktree.toml` nor `.worktreeinclude`, so `wt` resolves the base from `origin/dev` and provisions with the Makefile's `install` target — which is what creates the `.venv` that every gate below runs out of, since each Makefile check and test target depends on `install`.

## What ships

**Nothing is published to a registry: the repository itself is the artifact.** On Claude and Codex, install is a marketplace add against the GitHub repo — the README's Install section gives `claude plugin marketplace add Pipelex/pipelex-plugins` and `codex plugin marketplace add Pipelex/pipelex-plugins`, neither carrying a ref, so what is served is the repo's default branch, which is `main` (`origin/HEAD` points at `origin/main`). So the merge to `main` *is* the publish: when it lands, an install or a marketplace refresh hands users the `pipelex/` and `pipelex-codex/` trees exactly as the release branch left them, each carrying the new version in its own generated `plugin.json`. Mistral Vibe is served by no marketplace — the README has the user point `skill_paths` at a local checkout of `pipelex-vibe/` — so a Vibe user takes the release by pulling `main` themselves, and the tree they get names no version at all (see **Particulars**).

Nothing automated happens on the merge: the repo's workflows all run on a pull request (see **CI on the release pull request**), none of them publishes anything, and no tag is created — `git tag --list` is empty and this repo has never carried one. Say so when handing the merge to `/ledger-land`, so it does not go looking for a post-merge workflow run, a registry answer or a tag that do not exist. What it verifies instead is that `main` now carries the release:

```bash
git -C <main> fetch --prune origin
git -C <main> log origin/main -3 --oneline                                         # the merge, carrying the Release vX.Y.Z commit
git -C <main> show origin/main:targets/prod.toml | grep '^version'                 # X.Y.Z
git -C <main> show origin/main:.claude-plugin/marketplace.json | grep '"version"'  # the same number
git -C <main> show origin/main:pipelex/.claude-plugin/plugin.json | grep '"version"'
```

## Version files and the lock

The number to read as *the current version* — the one the play's pre-flight checks the changelog against, and the one the bump is computed from — is `targets/prod.toml`'s `[plugin].version`, which the repo's `CLAUDE.md` names the source of truth. Lockstep makes every file below carry that same string in a healthy tree; when they have drifted, prod is the one that wins and the release brings the rest up to it.

- **Every `targets/*.toml` but `defaults.toml`** — the `[plugin].version`. Enumerate the directory (`ls targets/*.toml`) instead of trusting a written list, so a target added since this page was written is never silently missed. Every target takes the **same** string: `scripts/check.py`'s `check_matched_target_versions` fails the release when they drift, with `Target versions must be in lockstep`.
- **`.claude-plugin/marketplace.json`** — `metadata.version`, set to that same number. What the check enforces is a floor rather than an equality: it fails when `metadata.version` is lower than the highest Claude target version (`metadata.version '…' lags behind Claude target version '…'`), so a forgotten bump is caught while a marketplace number that has run ahead is not.
- **The lock: none.** `uv.lock` locks `pipelex-plugins-tools`, the repo's internal tooling package, and its `pyproject.toml` version is not the plugin version — the file says so in its own comment: "Internal tooling version — not tied to the plugin version in plugin.json/marketplace.json. This package is not published; bump only when the tooling itself changes meaningfully." A release therefore touches neither `pyproject.toml` nor `uv.lock`, and there is no lock step to run.
- **Also stamped, by `make build` and never by hand:** `pipelex/.claude-plugin/plugin.json` and `pipelex-codex/.codex-plugin/plugin.json`. `scripts/gen_skill_docs.py` overlays each target's `[plugin]` name, description and version onto its platform's `plugin-base.json`, so those manifests only catch up with the TOMLs once the build has run. Run `make build` immediately after the version edits; it is what makes the second pass of the gates green.

## Gates

Run inside the worktree, in this order, before the commit. Every one is blocking: red stops the release, and the cure is to fix the cause, never to reach for a lighter target.

1. **`make agent-check`** — `fix-unused-imports`, `ruff format`, `ruff check --fix`, and then `make check`. **It rewrites files**, so whatever it touched joins the release commit. `make check` is the substantive part: `check-shared` re-renders every target with `scripts/gen_skill_docs.py --target all --check` and reports each generated file that is `MISSING`, an `ORPHAN`, or byte-different from what the templates produce — generated `SKILL.md` files, the per-skill `references/` copies, and the `.agents/plugins/marketplace.json` discovery copy alike — then runs `ruff format --check`, `ruff check`, `pyright` and `mypy`; `check-claude` and `check-codex` check the two marketplaces against the target configs. A freshness failure means someone edited a template or a shared reference without rebuilding, and the cure is `make build`, whose output then rides in the release commit.
2. **`make agent-test`** — the pytest suite, quiet unless it fails. `pyproject.toml`'s `addopts = "-m 'not recipes'"` deselects the suite that executes the shipped synthetic-inputs recipes, which is why that one is not a release gate: `make test-recipes` runs it, and it downloads packages on a cold `uv` cache.
3. **After the bump — `make build`, then `make agent-check` again.** Until the build has run, the generated manifests still carry the old number and `check_target_plugin_versions` fails with `plugin.json has A.B.C, targets/<name>.toml has X.Y.Z`. `Checks` runs the same `make check` on the pull request (see **CI on the release pull request**), so a half-stamped tree goes red there too — but no ruleset requires that check, so this pass is still what actually stops one reaching `main`.

## The release commit

Every `targets/*.toml` the enumeration turned up — `prod.toml`, `codex.toml` and `mistral-vibe.toml` today — plus `.claude-plugin/marketplace.json`, `CHANGELOG.md`, the two generated manifests `pipelex/.claude-plugin/plugin.json` and `pipelex-codex/.codex-plugin/plugin.json`, and anything else `make build` or `make agent-check` rewrote. Staged by name. A version-only release usually rewrites just those two manifests, which is exactly what the previous release commits carried, but stage what the build actually changed rather than that expectation.

## CI on the release pull request

**Checks report on a release pull request, and none of them blocks.** `docs/ci.md` is the full account; what a release run needs to know is this:

- `Checks` (`make check`) and `Unit tests` (`make agent-test`) run on every pull request, so the second pass of the local gates is repeated on the release branch — a tree pushed before `make build` caught up with the version bump fails `Checks` on the pull request as well as locally.
- `Version check` reads `targets/prod.toml`'s `[plugin].version` and requires it to equal the `X.Y.Z` in the `release/vX.Y.Z` branch name, and to be strictly greater than the version `main` carries.
- `Changelog entry` requires `CHANGELOG.md` to carry a `## [X.Y.Z] - …` heading for that same version — the heading shape this repo uses, with no `v`.
- `Gate main` refuses a pull request into `main` from anything but a `release/vX.Y.Z` branch of this repository. It runs on `pull_request_target`, so what executes is the copy of the workflow on `main` — the repository's *default* branch, which is why it is that copy and not the release branch's. **On the first release after the workflows landed it will not report at all**, because `main` does not carry `guard-branches.yml` until that very release merges. Expect it missing once, and present from the next release on.

The pull request that *fills* the release branch — `dev`, or a fix branch, into `release/vX.Y.Z` — is a different set: `Checks`, `Unit tests`, `Gate release` (under the same caveat), and `Version check` in its equality form only. `Changelog entry` fires on a pull request into `main` and nowhere else, so the cut pull request does not check the changelog.

What is still *only* this skill's job: nothing checks that the vendored hook bundle is current, and no ruleset requires any of the checks above, so a red one refuses no merge. Read them and stop on a failure rather than relying on GitHub to hold the line. `make test-recipes` does not run on this pull request either — `Recipes` is nightly, on demand, and on a pull request touching the recipe sources — which matches the gates above, where it is not a release gate.

## Particulars

- **The changelog headings carry no `v`.** Every entry in `CHANGELOG.md` reads `## [X.Y.Z] - YYYY-MM-DD` — `## [0.5.0] - 2026-08-01` — which is where the repo departs from the play's default `## [vX.Y.Z]`. The `v` still appears in the branch name, the commit subject and the pull request title. `Changelog entry` now enforces the no-`v` form on the pull request into `main` — it greps for `## [X.Y.Z] - ` anchored at the start of a line — but only for the version being shipped, so keeping the rest of the file consistent with itself is still this skill's job.
- **No pre-release form.** `scripts/check.py` parses a version as `tuple(int(part) for part in version.split("."))`, so anything that is not dotted integers fails `make check` with `invalid numeric version`. Ship a plain `X.Y.Z`.
- **The Vibe target has no manifest to stamp.** `targets/mistral-vibe.toml` builds `pipelex-vibe/`, which ships skills and hooks only; a plugin manifest is emitted for the Claude and Codex platforms alone. There is no `pipelex-vibe/**/plugin.json` to edit, and `make check` fails outright if a `.claude-plugin/` or `.codex-plugin/` directory turns up in that output. The Vibe version lives in its TOML and nowhere else.
- **The Codex marketplace specs carry no version field.** `packaging/codex-marketplace.json` is canonical and `.agents/plugins/marketplace.json` is its byte-for-byte discovery copy, kept in step by the build. Neither has a `version` key, so there is nothing in either to bump.
- **A release does not refresh the vendored hook bundle.** `templates/hooks/assets/check.mjs` is built in `pipelex-sdk-js` and copied in by `make vendor-hook` (from `SDK_JS_DIR`, defaulting to `../pipelex-sdk-js`), and no gate and no build step runs it. If a release is meant to ship a newer hook, run `make vendor-hook` and then `make build` deliberately, before the gates.
- **The `codex-use-local`, `codex-use-official`, `codex-refresh` and `codex-status` targets are dogfooding, not release steps.** They re-point a local Codex install at this checkout or back at the published marketplace, changing the developer's machine and never the repo, so none of them belongs in a release run.
