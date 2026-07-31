# Prevent automatic file-size workarounds in `pipelex-inputs`

## Goal

When `mthds_prepare_inputs` rejects an asset because it exceeds a storage size limit, stop the current preparation attempt and report the limitation. The skill must not modify, derive, replace, or retry the user's asset in order to evade the limit.

This applies to every file-bearing input, not only PDFs.

## Implementation plan

- [ ] Make the size-limit response an explicit terminal branch in `templates/skills/pipelex-inputs/SKILL.md.j2`.
  - Split `location: "inputs"` handling into size-limit failures and other asset failures instead of telling the agent to generically “fix that value.”
  - For a size-limit failure, surface the tool's exact message and hint, identify the affected input/file, and include the actual size and limit when the tool provides them.
  - State that preparation failed, the inputs are not run-ready, and the method will not be offered or submitted for a run.
  - Preserve the user's original file, the copied bundle file, and the local-path form of `inputs.json` unchanged.

- [ ] Add a hard prohibition against automatic workarounds, both before and after the upload attempt.
  - Do not compress, optimize, re-encode, resize, downsample, split, truncate, extract pages/content, or convert the file.
  - Do not replace it with synthetic data, a public sample, another local file, or a derived file.
  - Do not use a preflight size check as a reason to transform or substitute the asset before calling `mthds_prepare_inputs`.
  - Do not retry preparation with altered content. Continue only when the user supplies a different acceptable input/reference or the service limit changes.
  - Keep the existing recovery for non-size failures: resolve unreadable local paths to absolute paths and retry only where the documented error policy permits it.

- [ ] Regenerate every packaged skill from the canonical template with `make build`.
  - Verify the behavior appears in `pipelex/skills/pipelex-inputs/SKILL.md`.
  - Verify the behavior appears in `pipelex-codex/skills/pipelex-inputs/SKILL.md`.
  - Verify the behavior appears in `pipelex-vibe/skills/pipelex-inputs/SKILL.md`.
  - Do not edit those generated files directly.

- [ ] Add regression coverage in `tests/unit/test_gen_skill_docs.py`.
  - Pin the canonical template's terminal size-limit instruction and its prohibition on transformation, substitution, retry, and running.
  - Render all three targets and assert each contains the same guardrail.
  - Pin the distinction between a size-limit stop and the existing absolute-path recovery for unreadable files.

- [ ] Run a fresh-session behavioral regression using a simulated `mthds_prepare_inputs` size-limit response.
  - Use a prompt equivalent to “run this method with this PDF,” without revealing the expected behavior.
  - Expect exactly one preparation attempt, a concise report of the storage rejection, no derivative file, no mutation of the copied input or `inputs.json`, and no `mthds_run` call or offer.
  - Also exercise an unreadable-relative-path response to confirm that legitimate path recovery still works.

- [ ] Record the policy in project documentation.
  - Replace the current Unreleased changelog wording that says the skill “addresses” a size limit with wording that says it stops without altering or substituting the asset.
  - Add the no-workaround boundary to `docs/decisions.md` beside the `mthds_prepare_inputs` decision so a later cleanup does not reintroduce the ambiguity.

- [ ] Validate the completed change.
  - Run the focused unit tests for skill generation and failure discipline.
  - Run `make check` to verify rendering freshness, packaging, formatting, linting, and type checks.
  - Review the final diff to confirm only the template, generated outputs, regression tests, and relevant documentation changed.

## Acceptance criteria

- An oversized asset produces a terminal report, not a workaround.
- No transformed, reduced, split, converted, synthetic, or substitute asset is created or selected automatically.
- The original and copied files remain byte-for-byte unchanged, and `inputs.json` is not rewritten to disguise the failed upload.
- The skill neither offers nor starts a run with unprepared inputs.
- Unreadable-path and other non-size error recovery remains intact.
- The rule is identical across Claude, Codex, and Mistral Vibe generated skills and is protected by regression tests.

## Out of scope

- Raising or changing Pipelex storage limits.
- Adding a PDF compression or conversion utility.
- Silently uploading the asset through a different storage provider or URL as a bypass.
