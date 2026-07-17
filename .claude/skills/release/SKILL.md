---
name: release
description: >
  Automates the release workflow for the pipelex-plugins repo: runs `make check`,
  bumps the version in every target config and the Claude marketplace, finalizes
  CHANGELOG.md, creates a release/vX.Y.Z branch, runs `make build`, commits,
  pushes, and opens a PR to main. Use this skill when the user says "release",
  "cut a release", "bump version", "prepare a release", "make a release",
  "create release branch", or any variation of shipping a new version. The user
  can optionally provide changelog content inline when invoking the skill (e.g.
  "/release Added pipelex-edit skill"), which will be used as the changelog entry
  for this version.
---

# Release Workflow

Guides the user through preparing a new plugin release. Every step requires
explicit user confirmation before proceeding.

## Version files overview

This repo ships several build targets in **matched-version lockstep** -- one per
`targets/*.toml` config (excluding `defaults.toml`). At the time of writing these
are `prod`, `codex`, and `mistral-vibe`, but **do not trust that list**: always
enumerate `targets/*.toml` first, so a newly added target is never silently
missed. A release bumps **every** target to the same version string. The
canonical hand-edited files are:

- the `[plugin].version` of **each** `targets/<name>.toml` -- currently
  `prod.toml`, `codex.toml`, `mistral-vibe.toml`
- **`.claude-plugin/marketplace.json`** -- `metadata.version` (the Claude
  marketplace version; `make check` fails if it lags behind the highest target
  version)

The Codex marketplace specs (`packaging/codex-marketplace.json` and its generated
copy `.agents/plugins/marketplace.json`) carry **no** version field -- there is
nothing to bump there.

Each Claude-style target's `plugin.json` manifest is **generated** by `make build`
from its target TOML + the shared `plugin-base.json`:

- `pipelex/.claude-plugin/plugin.json` ← `targets/prod.toml` + `.claude-plugin/plugin-base.json`
- `pipelex-codex/.codex-plugin/plugin.json` ← `targets/codex.toml` + `.codex-plugin/plugin-base.json`

The **Vibe** target (`mistral-vibe.toml` → `pipelex-vibe/`) emits **no**
`plugin.json` -- it ships only hooks, so its version lives solely in
`targets/mistral-vibe.toml`. Don't go looking for a `pipelex-vibe/*/plugin.json`
to edit; there isn't one.

Never hand-edit a generated `plugin.json` -- it is overwritten on the next build.
`make check` enforces the per-target plugin.json/target.toml match, the
marketplace-version floor, and the matched-version lockstep across all targets.

## 1. Pre-flight checks

- Read the current version from `targets/prod.toml` `[plugin].version`.
- Read `CHANGELOG.md` to understand the current state (if it exists).
- Run `git status` and `git log origin/main..HEAD` to assess the working tree:
  - If there are **uncommitted changes** (staged or unstaged), warn the user and
    ask whether to commit them as part of the release, stash them, or abort.
  - If there are **unpushed commits** on the current branch, list them so the
    user is aware -- these will be included in the release branch.

## 2. Determine the bump type

Ask the user which kind of version bump they want -- **patch**, **minor**, or
**major** -- unless they already specified it. Show the current version and what
the new version would be for each option so the choice is concrete. The bump is
computed from **prod**'s current version; every other target (`codex`,
`mistral-vibe`, and any other `targets/*.toml`) is set to the same resulting
value regardless of its previous value (matched-version lockstep).

If the current branch already looks like `release/vA.B.C` and the version in
`targets/prod.toml` was already bumped, offer a **"Keep current (A.B.C)"** option.

Store the chosen version as `TARGET_VERSION` (no `v` prefix, e.g. `0.2.0`).

## 3. Run quality checks

Run `make check`. This is the gate -- if it fails, stop and report the errors so
they can be fixed before retrying. Do not proceed past this step on failure.

## 4. Ensure we're on the right branch

The release branch must be named `release/v{TARGET_VERSION}` where the version is
the **new** version. All file modifications (changelog, version bump) must happen
on this branch.

- If already on `release/v{TARGET_VERSION}` matching the new version, stay on it.
- If on `main`, `dev`, or any other branch, create and switch to
  `release/v{TARGET_VERSION}` from the current HEAD.
- If on a `release/` branch for a **different** version, warn the user and ask
  how to proceed.

## 5. Bump the version

First run `ls targets/*.toml` (ignore `defaults.toml`) so you edit **every**
target, not a hardcoded subset. Then set `TARGET_VERSION` in:

1. The `[plugin].version` of **each** `targets/<name>.toml` -- change
   `version = "OLD"` to `version = "NEW"`. Currently: `prod.toml`, `codex.toml`,
   `mistral-vibe.toml`.
2. **`.claude-plugin/marketplace.json`** -- change `metadata.version`.

They must all end up with the same value. Only change version fields -- don't
touch anything else in these files.

- If they already all match `TARGET_VERSION`: inform the user and skip.
- Otherwise: use the Edit tool to make the changes, then show the diff.

After editing, run `make build` to regenerate the generated plugin.json manifests
(`pipelex/.claude-plugin/plugin.json`, `pipelex-codex/.codex-plugin/plugin.json`)
and all derived SKILL.md / hook files across every target. Then verify with
`make check` -- it validates each plugin.json matches its target.toml, the
marketplace version is not lagging, and all target versions are in
matched-version lockstep.

## 6. Finalize the changelog

Add a new version entry at the top of the changelog for the release. If
`CHANGELOG.md` does not exist yet, create it with a `# Changelog` heading.

1. If there is an `## [Unreleased]` section, **remove it** (including any blank
   lines that follow it) and replace it with the new version heading. Any content
   that was under `[Unreleased]` becomes the content of the new version.
2. If there is no `[Unreleased]` section, insert the new version heading directly
   after the `# Changelog` title.
3. **Never add an `[Unreleased]` heading.** The changelog should only contain
   concrete version entries.
4. If the user provided changelog content when invoking the skill (e.g.
   `/release Added pipelex-edit skill`), **merge** that content with any existing
   `[Unreleased]` content (do not discard either source). Format the combined
   content properly under the appropriate headings (e.g. `### Added`,
   `### Changed`, `### Fixed`), inferring headings from the content when possible.
5. If the release has no changelog content yet (neither from an `[Unreleased]`
   section nor from inline user input), run `git log main..HEAD --oneline` (or
   `git log --oneline -20` if on `main`) to review recent commits. Draft a
   changelog entry from those commits and propose it to the user for approval.
6. The result should look like:

```markdown
# Changelog

## [vX.Y.Z] - YYYY-MM-DD

### Added

- Item one

### Changed

- Item two

### Fixed

- Item three

## [vPREVIOUS] - PREVIOUS-DATE

...
```

Use the appropriate subsections (Added, Changed, Fixed, Removed, Breaking
Changes) based on the content. Only include subsections that have entries. The
user may accept, edit, or rewrite the proposed entry.

Note: this repo's writing conventions apply to changelog wording -- write
"breaking" rather than "pre-1.0 breaking", never hardcode counts of items, and do
not mention changes to WIP docs (anything under a `wip/` path).

## 7. Commit, push & PR

Stage all release-related changes: every `targets/<name>.toml` you bumped
(`prod.toml`, `codex.toml`, `mistral-vibe.toml`),
`.claude-plugin/marketplace.json`, `CHANGELOG.md`, and the regenerated build
artifacts under each target's output dir (`pipelex/`, `pipelex-codex/`,
`pipelex-vibe/` -- including each generated `plugin.json` and any derived
SKILL.md / hook files), plus any other files the user chose to include in step 1.
A version-only bump usually regenerates just the `plugin.json` manifests, but
stage whatever `make build` actually changed. Never use `git add .` or
`git add -A` -- other concurrent sessions may share this checkout, so stage the
specific release files explicitly.

Commit with the message:

```
Release v{TARGET_VERSION}
```

Push the branch to origin with `-u` to set up tracking.

Create a pull request targeting `main` with:

- **Title:** `Release v{TARGET_VERSION}`
- **Body:**

```markdown
## Release v{TARGET_VERSION}

Bumps version from `{OLD_VERSION}` to `{TARGET_VERSION}`.

### Changelog

<paste the changelog entries for this version here>
```

Report the PR URL back to the user.

## Rules

- The version follows semver: `MAJOR.MINOR.PATCH`.
- The source of truth for each target's version is `targets/<name>.toml`; every
  target (`prod`, `codex`, `mistral-vibe`, and any future `targets/*.toml`) is
  kept in matched-version lockstep. Enumerate `targets/*.toml` rather than
  trusting this list -- a newly added target must not be missed.
- Every `targets/<name>.toml` and `.claude-plugin/marketplace.json` must have the
  same version after a release. Each Claude-style target's generated `plugin.json`
  is rebuilt from its TOML; the Vibe target has no `plugin.json`.
- The Codex marketplace specs (`packaging/codex-marketplace.json`,
  `.agents/plugins/marketplace.json`) have no version field -- do not try to bump
  them.
- Never hand-edit the generated `plugin.json` files under `pipelex/` or
  `pipelex-codex/` -- `make build` overwrites them.
- Always run `make build` after version changes to regenerate build artifacts.
- Always confirm the bump type with the user before making changes.
- If `make check` fails, the release is blocked -- help the user fix the issues
  rather than skipping the checks.
- Never use `git add .` or `git add -A` -- only stage the specific release files.
- The `v` prefix appears in branch names, changelog headers, and PR titles, but
  **not** in version files.
- Always use today's date for new changelog entries (format: `YYYY-MM-DD`).
- If any step fails or the user wants to abort, stop immediately -- do not
  continue the workflow.
- PR always targets `main`.
