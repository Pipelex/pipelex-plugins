# When a gate gives no verdict

Read this when a drift gate step 10 wired exits `2`, at step 11 or later. Exit `2` is no verdict: the gate could not reach one, which says nothing about the generated tree. It is never drift, so regeneration is never its remedy. Find the message below and act on it.

| The gate says | What it means, and what to do |
|---|---|
| the TypeScript gate: `@pipelex/sdk` is not importable, could not be loaded, or predates the offline check | the gate ran where the project's dependencies are not installed (a CI job that skips the install step), from a copy outside the project, or against an `@pipelex/sdk` below step 8's floor. Install the dependencies, run it through the package manager as step 10 registers it, and raise the pin as step 8 does. The tree is not what failed |
| either gate: `no verdict: the lock check failed` or `the source check failed` | a check threw or raised instead of reaching a verdict. Report the message verbatim; the tree is not what failed, so regenerating does not clear it |
| the Python gate: `pipelex-sdk` is not importable | the command runs outside the project's environment, or the project pins `pipelex-sdk` below step 8's floor. Run it the way step 10 says, in the project's own environment (`uv run python`, `poetry run python`, `pipenv run python`, or the active environment's `python`), and raise the pin as step 8 does |
| the Python gate: `pipelex-sdk` failed while loading | the SDK is installed but raised as it loaded (a pydantic-core that does not match pydantic, a corrupt file), so the project's environment is broken. Reinstall its dependencies rather than reaching for another interpreter, and report the exception the message names |

Whatever the Python gate says, never swap it for `pipelex codegen check`, which needs the `pipelex` runtime a `python-pydantic` consumer does not have and should not be given.
