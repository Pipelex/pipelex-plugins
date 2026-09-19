# Integrating into a TypeScript project

Companion to `/pipelex-integrate` for a project that has a `package.json`. Everything here follows the shape the Pipelex JS starter converged on; the SDK facts were checked against `@pipelex/sdk` 0.18.0, the floor the skill's step 8 installs, and move only when that package does.

## Detecting the project

| Question | Signals, in order | When inconclusive |
|---|---|---|
| **TypeScript build** | a `tsconfig.json`; a `typescript` dev dependency; a bundler or runtime that strips types (Next.js, Vite, tsx, Bun, Deno) | a plain JavaScript project is asked — `types.ts` needs a TypeScript build; the alternative is `python-pydantic`'s sibling in this language, which does not exist yet, so the honest answer is "add TypeScript or skip codegen" |
| **Package manager** | the lockfile: `package-lock.json` → npm, `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lock` / `bun.lockb` → bun | none → npm, stated |
| **Generated root** | an existing directory already holding generated code (`generated/`, `gen/`, `__generated__/`) → beside it; else `src/generated/` when `src/` exists; else `generated/` | ask |
| **Formatter** | `.prettierrc*` or a `prettier` dev dependency → add `src/generated/` and the gate script `scripts/codegen-check.mjs` to `.prettierignore`, one line each (create the file if absent); `biome.json*` → both paths under the files-ignore key its version uses (`files.ignore` with `"src/generated/**"` and `"scripts/codegen-check.mjs"` before Biome 2, `files.includes` with a `!` negation of each, `"!src/generated"` and `"!scripts/codegen-check.mjs"`, from Biome 2 on) | a formatter this table does not name: read its config, add the equivalent for both paths, say so |
| **Linter** | `eslint.config.*` (flat config) → add `"src/generated/**"` and `"scripts/codegen-check.mjs"` to `globalIgnores([...])` or an `{ ignores: [...] }` entry; legacy `.eslintrc*` → the same two lines in `.eslintignore`; Biome as above | same |
| **Type checker still covers the tree** | `tsconfig.json` `include` / `exclude` — the generated directory must stay inside `include` and outside `exclude` | an exclusion that would drop it is **not** added; the report says the typecheck is the check that covers generated code |
| **Aggregate gate** | `package.json` `scripts.check` / `ci` / `validate` / `verify`; a Makefile `check` target; a `.github/workflows/*.yml` job with a lint or test step; `.pre-commit-config.yaml` | none: the `codegen:check` script alone, and a sentence in the report saying where to call it |
| **Call-site location** | the project's existing service / action / client layer (`src/actions/`, `src/services/`, `src/lib/`, `src/server/`) → beside it | `src/pipelex/` |
| **Not gitignored** | the generated root and `sources.json` must be committable | a `.gitignore` pattern that swallows them is reported and un-ignored on confirmation |
| **Owns a codegen harness** | `scripts.codegen` in `package.json`; `sources.json` with a `derived` map; `docs/codegen.md`; `make add-method` | either of the first two → the harness section below, but **read the script before believing it**: `"codegen": "graphql-codegen"` or a protobuf generator satisfies the name and generates no MTHDS types, and deferring to it would skip the dependencies, the exclusions, the sidecar and the gate while generating nothing. Pipelex-specific evidence — it calls `mthds_codegen`, a `pipelex` CLI, or reads `methods/` — is what makes it this method's harness; without that, integrate normally and leave the unrelated harness alone |

Why the exclusions are not optional: the ts-zod emitter prints at Prettier's defaults (80 columns). A project that prints at another width, or a linter with an autofix, rewrites the bytes, breaks every stamp, and makes the offline check report the whole tree as hand-edited. The type checker, by contrast, must keep covering the tree — that is the check that catches a call site drifting from its types. The gate script is excluded from the formatter and the linter too, before it exists, because it is copied verbatim and a refresh compares it byte for byte with this reference, so a reformat would make every refresh re-copy it and leave the project's own format check failing on `scripts/`; nothing about it changes for the type checker.

## The generated tree

`mthds_codegen` with `target: "ts-zod"` and `output_dir: "src/generated/<method>"` writes:

- `types.ts` — stamped; `import { z } from "zod"`; one `export const XSchema = z.object({...})` and `export type X = z.infer<typeof XSchema>` per concept, natives included; non-required fields are `.nullish()`, so the schema parses the runtime's explicit `null`s directly.
- `binder.ts` — stamped; `export function parseX(wire: unknown): X` and `export function serializeX(value: X): X` per concept, over the pure schemas. Field keys are wire-native snake_case.

  **Known defect:** `binder.ts` imports its sibling as `from "./types"`, with no extension. On a plain Node ESM project (`"type": "module"` with `moduleResolution` `nodenext` or `node16`) that fails the type check with `TS2835` and the compiled code with `ERR_MODULE_NOT_FOUND`; a bundler resolution (`bundler`, `node10`) is unaffected, which is why the JS starter never meets it. The fix belongs to the emitter. Say so plainly and leave the file alone: it is stamped and hashed, so a patch breaks the trust chain and the next regeneration drops it. Whether to move the project to a bundler resolution meanwhile is the user's decision.
- `codegen.lock` — TOML: `lock_version`, `crate_fingerprint`, `engine_version`, one `[[artifacts]]` entry per stamped file with its `content_hash`.

Beside them the skill writes `sources.json`, unstamped; it is never an artifact and never an orphan. Everything stamped is read-only and formatter-free. A consumer imports the type from `types.ts` and the parser from `binder.ts`; anything it wants to add goes in its own module, never in the generated one.

## The call site

One module per method. `summarize-pdf` with a `document: native.Document` input, an optional `context: native.Text`, and a `summarize.DocumentSummary` output, from a committed bundle:

```ts
// src/pipelex/summarizePdf.ts
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import type { RunResults } from "@pipelex/sdk";
import { parseDocumentSummary } from "../generated/summarize-pdf/binder";
import type { DocumentSummary } from "../generated/summarize-pdf/types";
import { getPipelexClient } from "./client";

const PIPE_CODE = "summarize_pdf";
const BUNDLE_DIR = path.join(process.cwd(), "methods", "summarize-pdf");

/** Every `.mthds` file of the bundle, sorted, as the run's `mthds_contents`. A bundle is one
 *  closure: a main file that imports a sibling needs that sibling submitted with it, or the
 *  run fails to load what the generated types were projected from. `recursive` needs Node
 *  >= 20.1, which the SDK's own Node floor (>= 22.12) already guarantees, and the
 *  drift gate lists the bundle with this same call, so keep it rather than a walk of your own. */
async function readBundle(): Promise<string[]> {
  const names = (await readdir(BUNDLE_DIR, { recursive: true })).filter((name) => name.endsWith(".mthds")).sort();
  return Promise.all(names.map((name) => readFile(path.join(BUNDLE_DIR, name), "utf8")));
}

export type SummarizePdfInputs = {
  /** An http(s) URL or a pipelex-storage:// reference. For a local file or bytes,
   *  run `getPipelexClient().prepareInputs({ files: (await readBundle()).map((c) => ({ content: c })), inputs })` first —
   *  it uploads and rewrites the value. Note: prepareInputs treats any string it does not
   *  recognise as data:, http(s):// or pipelex-storage:// as a LOCAL FILE PATH it reads and
   *  uploads, so a public endpoint must gate schemes before handing values to it. */
  document: { url: string };
  context?: string;
};

/** The narrowed output beside the whole results the run returned: `output` is what the method
 *  produced, `results` is everything else the run carries — the run id, the usage, the graph,
 *  and the references of any file it produced. A caller who wants only the output reads `.output`. */
export type SummarizePdfRun = { output: DocumentSummary; results: RunResults };

export async function summarizePdf(inputs: SummarizePdfInputs): Promise<SummarizePdfRun> {
  const results: RunResults = await getPipelexClient().startAndWaitForResult({
    pipe_code: PIPE_CODE,
    mthds_contents: await readBundle(),
    inputs,
  });
  return { output: parseDocumentSummary(results.main_stuff), results };
}
```

**`SummarizePdfInputs` is a `type`, not an `interface`, and that is load-bearing.** The SDK takes `inputs: Record<string, unknown>`, and TypeScript gives a type alias of an object type an implicit index signature while an `interface` gets none — so an interface here fails with `TS2322: Index signature for type 'string' is missing`. It fails on every resolution, bundler included, and it is the first thing a `tsc --noEmit` would have caught. Keep it a `type`.

**The three relative imports above are extensionless, which is correct only on a bundler resolution.** On the plain Node ESM shape that meets the emitter's `TS2835` defect (`"type": "module"` with `moduleResolution` `nodenext` or `node16`) this module needs `.js` on each of them — `"../generated/summarize-pdf/binder.js"`, `"../generated/summarize-pdf/types.js"`, `"./client.js"`. That is your own module and so your own fix, unlike the stamped `binder.ts`: write the extensions when the project's resolution demands them, and do not report your own module's `TS2835` as the emitter's defect.

Variants by selector, replacing the `mthds_contents` line and dropping `BUNDLE_DIR` and `readBundle`:

- **`method_ref`** at a tag: `{ method_ref: "github.com/<owner>/<repo>[/<selector>]@<tag>", pipe_code: PIPE_CODE, inputs }` — omit `pipe_code` to run the package's declared pipe.
- **`method_id`**: `{ method_id: "mt_…", inputs }` — the catalog resolves the stored method; the module's header says the catalog is unversioned.

The shared client helper, created once per project and reused by every method (if the project already constructs a `PipelexApiClient` somewhere, import that instead):

```ts
// src/pipelex/client.ts
import { PipelexApiClient } from "@pipelex/sdk";

let client: PipelexApiClient | undefined;

/** Reads PIPELEX_API_KEY and PIPELEX_BASE_URL (default https://api.pipelex.com) from the environment. */
export function getPipelexClient(): PipelexApiClient {
  client ??= new PipelexApiClient();
  return client;
}
```

`startAndWaitForResult(options, pollOptions?)` takes the durable path (`start` + poll, default 2 s interval, 20 min budget) on the hosted API and falls back to a blocking `execute` on a bare runner; it returns `RunResults` whose `main_stuff` is always present for a completed run. Let the SDK's typed errors propagate — `RunFailedError`, `RunTimeoutError` (the run keeps going; resume by `pipeline_run_id`), `ApiResponseError` (branch on `.code`), `ApiUnreachableError`, `MissingMainStuffError` — and add the project's own error handling only where it already wraps its other clients. A server-side framework seam (a Next.js Server Action, an Express handler) is the caller's; this module is framework-free.

Parameter types from the signature: `string` for Text and Date (ISO 8601), `number` for Number, `boolean` for YesNo, `{ url: string }` for Image and Document, the generated type for a structured concept or a composite native, `T[]` for a list, `?` for a non-required input. Key names are the pipe's input names as declared, snake_case included.

## What the results carry

The module returns `RunResults` beside the narrowed output because everything below is already parsed on it, and a caller that needs one of these would otherwise have to edit the module or run the method a second time. Each field has its own section in `@pipelex/sdk`'s `docs/run-results.md` — point the user at that page rather than restating it, and write none of these into the project as a helper.

**`results.pipeline_run_id` — the durable handle.** It outlives the process: persisted, it lets a later session read the same run back through the SDK's lifecycle calls, and it is what a `RunTimeoutError` leaves in hand while the run itself carries on server-side. The bare runner has no run store behind the id.

**Produced files — a `pipelex-storage://` reference, and a signed link that expires.** A run that produces an image, a PDF or a document puts the file's durable reference in the content's `url`, beside a `public_url` the storage provider signed when the file was written. The reference is permanent and is what belongs in a record; the signed link is short-lived, so one persisted in a database or baked into a cached page stops working without warning. Bringing the bytes down is the SDK's job and not something to re-implement over `resolveStorageUrl`: `downloadArtifacts` saves everything a run produced under a directory, `resolveArtifacts` mints fresh links for a whole list of references, `collectArtifacts` lists them without touching the network, and `fetchArtifact` streams one within bounded limits. Their page is `docs/artifact-download.md`. In a framework with a client/server split, resolve on the server and hand the browser a link it uses immediately.

**`summarizeUsage(results)` — what the run cost.** It folds the `tokens_usages` / `usage_assembly_error` pair into one run-level reading with a per-pipe rollup, applying the rules `docs/run-usage.md` states — an unrated cost is not a cost of zero, and a partial sum says so — and it is pure: no client, no network, no mutation of its argument. Never add the records up by hand.

**`results.graph_spec` — the graph the run executed.** One node per pipe with its status, its timings and the models and cost attributed to it: the same document a local `pipelex` run writes as `graphspec.json`. The field is typed `unknown` because its canonical declaration is `GraphSpec` in `@pipelex/mthds-ui`, which also ships the viewer that renders it — a project that wants the graph on screen takes that package and loads the viewer client-side only, since it touches browser globals when its module evaluates. `results.graph_assembly_error` says why a graph is missing when one is.

**`results.working_memory` — every named stuff of the run.** Root and aliases, the whole run rather than its output alone, which is what repopulates the inputs of a run read back later.

## The offline gate

Copy `references/codegen-check.mjs` verbatim to `scripts/codegen-check.mjs`, and never format or lint it: step 5 put it in the formatter and linter exclusions beside the generated directory. It imports only Node builtins and `@pipelex/sdk`, runs under plain `node` whatever the project's TypeScript build, and prints through `process.stdout` / `process.stderr` so a `no-console` rule does not fire. Register it and extend the existing gate:

```json
{
  "scripts": {
    "codegen:check": "node scripts/codegen-check.mjs src/generated/summarize-pdf",
    "check": "npm run lint && npm run typecheck && npm run codegen:check"
  }
}
```

Add every method's directory to the `codegen:check` line as it is integrated, and on a refresh add the refreshed method's directory when it is missing, leaving the others as they are. A refresh also re-copies the script when the project's copy differs from this reference, and installs it when the project has none, so a project integrated by an older version of the skill gets the current gate. Exit codes: `0` current, `1` drift or stale source, `2` no verdict (no lock, an unreadable file, a symlink in the tree, a check that throws, `@pipelex/sdk` not importable). It compares the SHA-256 recorded for each source in `sources.json` against the `.mthds` file on disk, and the recorded sources against every `.mthds` file under the sidecar's `bundle_dir`, listed with the same recursive `readdir` the call site's `readBundle` uses — so a file added to the bundle is `stale-source` too, although every recorded hash still matches. It runs from the project root because `sources.json` records its source paths and `bundle_dir` relative to it, and `bundle_dir` is the call site's `BUNDLE_DIR` expressed that way. It resolves `@pipelex/sdk` from its own location, so it stays inside the project and runs where the dependencies are installed — in CI, after the install step. An SDK that is missing, fails to load, or predates the offline check is no verdict with the fix on stderr, never an uncaught error, which would exit `1` and read as drift; a too-old one is raised to 0.18.0 or later, the floor step 8 installs. When `@pipelex/sdk` ships this as a command of its own, the script is replaced by that one line.

## The Node-only boundary

`readFile`, `node:path` and `process.cwd()` in the call site are server-side facts. In a framework with a client/server split (Next.js, Remix, SvelteKit), the module belongs on the server side — a Server Action, a route handler, a loader — and the JS starter marks such modules with `import "server-only"`. Never import it from a component that renders in the browser: the API key would leave the server.

## A project that owns a codegen harness

A project made from the method app (`pipelex-method-apps`' `webapp-js/`) or from `pipelex-starter-js`, or one that copied their codegen kit, has: `npm run codegen` (regenerates every `methods/*` tree through the hosted `/v1/codegen`, writes `contracts.ts` and `sources.json` with a `derived` map), `npm run codegen:check` (offline, in `make check`), `npm run codegen:verify` (semantic, keyed), and `make add-method METHOD=…` (the bundle or the manifest, the tree, the action trio, the narrower, the form, and the registry entry or tab — one shot, never overwrites). On such a project:

- a local bundle is one command when `make add-method` takes a bundle path, as the method app's does and as its usage in `make help` says: `make add-method METHOD=<path to the bundle>` copies the bundle into `methods/<name>/` and writes the whole slice;
- where `make add-method` takes only a catalog id or an address, as the gallery's does, a local bundle goes under `methods/<name>/main.mthds`, then `npm run codegen`; the fan-out follows `docs/codegen.md` and the existing actions under `src/actions/` and narrowers under `src/types/`;
- a catalog or published method goes through `make add-method`;
- the verification is `make check`; the refresh is `npm run codegen`; no `sources.json` of this skill's shape, no `scripts/codegen-check.mjs`, no second generated directory.
