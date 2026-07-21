# PR #4 review notes — deferred items

Deferred findings from the SWE-agent review pass on [PR #4](https://github.com/Pipelex/pipelex-plugins/pull/4) (release/v0.2.0). Fixed and false-positive items were handled on the PR threads directly; this file records the one item deferred for a later judgment call.

## Partial `[vars.mcp_server]` override silently discards launcher defaults

- **Reporter:** cubic-dev-ai (P2), `scripts/gen_skill_docs.py` `load_target_config` (the `template_vars[key] = _coerce_var(value)` overwrite).
- **Issue:** target-level `[vars]` overrides replace defaults wholesale. For the nested `[vars.mcp_server]` table, a future target that writes a *partial* override (say only `env_vars`) would silently drop `command`/`args`; `make_plugin_json` then bakes `"command": ""` into a checked-in manifest, and neither the freshness check nor any packaging check in `scripts/check.py` catches it — the failure only surfaces when a host tries to spawn the server on a user's machine.
- **Why deferred:** confirmed as a real latent footgun, but with **zero current trigger** — no target overrides `mcp_server` at all (codex/mistral-vibe override only `platform`/`harness_name`), and the repo's posture is deliberately lean ("in case of doubt, defer", "don't port dead switches"). This is defense against a config shape nobody writes yet.
- **Recommendation when it becomes relevant** (first target that overrides any dict var): apply the ~4-line deep-merge in `load_target_config` (`if isinstance(template_vars.get(key), dict) and isinstance(override, dict): merge`) plus a build-time guard in `make_plugin_json` that dies on an empty `command`, with a unit test asserting a partial `[vars.mcp_server]` override keeps inherited keys. PR thread: [cubic comment](https://github.com/Pipelex/pipelex-plugins/pull/4) (thread `PRRT_kwDOTEJdYc6Skqo2`) — left unresolved on purpose.
