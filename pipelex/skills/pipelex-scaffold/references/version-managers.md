# A runtime reached through a version manager

Read this when a prerequisite check of `/pipelex-scaffold` finds `node` or `uv` missing, or `node` below the floor, before stopping on it. A runtime the machine already has, where only the `PATH` is missing it, is not a missing piece: when a version manager on the machine carries one (`nvm`, `fnm`, `volta`, `asdf`, `mise`), use it for this work, and say in the report which one you used and that the user's own shell may not have it. Stop only when no usable runtime can be reached that way. The skill's guards hold throughout: nothing is installed, and no manager is let download a version.

## Resolve it to an absolute path, never source a shell

Your shell state does not survive from one command to the next. Each command starts again from the user's profile, which is the profile that did not have the runtime, so `. nvm.sh` or `eval "$(fnm env)"` in one call buys nothing in the next.

Resolve the binary once, keep its directory, and prefix **every** later command with it, as `PATH="<that dir>:$PATH" …`:

- `nvm`: `ls "$NVM_DIR"/versions/node/*/bin/node`
- `volta`: `volta which node`
- `mise`: `mise which node`
- `asdf`: `asdf which node`
- `fnm`: `fnm exec --using=<v> -- which node`

Every later command means every one: the method app's `make create` and `make dev`, the initializer and the commands after it, and the skill's own scripts. Each is a separate command, and each starts from the profile again.

Verify the runtime answers under that prefix **before** anything is created, so that a machine you cannot actually reach stops while nothing exists yet. Discovering it later means the pristine commit has already been spent.

## What this does not license

- **A shim is not a runtime.** `asdf` and `mise` put a `node` on the `PATH` that exists and then fails with "no version set". The test is that `node --version` *answers*, not that the binary resolves. A shim that does not answer is a stop, not a manager to activate.
- **The floor still applies.** A manager holding Node 18 does not satisfy the method app's `engines` floor, and "a runtime the machine already has" never means a version below it.
- **`volta` and `mise` install on first use.** `volta run`, `mise x` and `mise use` fetch a version they do not have, which is the toolchain install the skill forbids. Use only a version the manager already holds, and stop rather than let it download one.
- **`nvm`, `fnm` and `volta` manage Node alone.** None of them can supply `uv`.

## What it means for the hand-off

The Pipelex workshop that `/pipelex-integrate` uses is spawned with `npx` on the **harness's** own `PATH`, which no prefix of yours reaches. So a `node` that only `nvm` or `fnm` can reach means no workshop at all. The report says so instead of the usual hand-off: the harness must be restarted from a shell where the runtime is active before `/pipelex-integrate` can run.
