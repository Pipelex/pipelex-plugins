# Integrating into a TypeScript project

Companion to `/pipelex-integrate` for a project that has a `package.json`. Everything here follows the shape the Pipelex JS starter converged on; the SDK facts were checked against `@pipelex/sdk` 0.17 and move only when that package does.

## Detecting the project

| Question | Signals, in order | When inconclusive |
|---|---|---|
| **TypeScript build** | a `tsconfig.json`; a `typescript` dev dependency; a bundler or runtime that strips types (Next.js, Vite, tsx, Bun, Deno) | a plain JavaScript project is asked — `types.ts` needs a TypeScript build; the alternative is `python-pydantic`'s sibling in this language, which does not exist yet, so the honest answer is "add TypeScript or skip codegen" |
| **Package manager** | the lockfile: `package-lock.json` → npm, `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lock` / `bun.lockb` → bun | none → npm, stated |
| **Generated root** | an existing directory already holding generated code (`generated/`, `gen/`, `__generated__/`) → beside it; else `src/generated/` when `src/` exists; else `generated/` | ask |
| **Formatter** | `.prettierrc*` or a `prettier` dev dependency → add `src/generated/` to `.prettierignore` (create the file if absent); `biome.json*` → the files-ignore key its version uses (`files.ignore` before Biome 2, `files.includes` with a `!` negation from Biome 2 on) | a formatter this table does not name: read its config, add the equivalent, say so |
| **Linter** | `eslint.config.*` (flat config) → add `"src/generated/**"` to `globalIgnores([...])` or an `{ ignores: [...] }` entry; legacy `.eslintrc*` → `.eslintignore`; Biome as above | same |
| **Type checker still covers the tree** | `tsconfig.json` `include` / `exclude` — the generated directory must stay inside `include` and outside `exclude` | an exclusion that would drop it is **not** added; the report says the typecheck is the check that covers generated code |
| **Aggregate gate** | `package.json` `scripts.check` / `ci` / `validate` / `verify`; a Makefile `check` target; a `.github/workflows/*.yml` job with a lint or test step; `.pre-commit-config.yaml` | none: the `codegen:check` script alone, and a sentence in the report saying where to call it |
| **Call-site location** | the project's existing service / action / client layer (`src/actions/`, `src/services/`, `src/lib/`, `src/server/`) → beside it | `src/pipelex/` |
| **Not gitignored** | the generated root and `sources.json` must be committable | a `.gitignore` pattern that swallows them is reported and un-ignored on confirmation |
| **Owns a codegen harness** | `scripts.codegen` in `package.json`; `sources.json` with a `derived` map; `docs/codegen.md`; `make add-method` | either of the first two → the harness section below |

Why the exclusions are not optional: the ts-zod emitter prints at Prettier's defaults (80 columns). A project that prints at another width, or a linter with an autofix, rewrites the bytes, breaks every stamp, and makes the offline check report the whole tree as hand-edited. The type checker, by contrast, must keep covering the tree — that is the check that catches a call site drifting from its types.

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
import { readFile } from "node:fs/promises";
import path from "node:path";
import type { RunResults } from "@pipelex/sdk";
import { parseDocumentSummary } from "../generated/summarize-pdf/binder";
import type { DocumentSummary } from "../generated/summarize-pdf/types";
import { getPipelexClient } from "./client";

const PIPE_CODE = "summarize_pdf";
const BUNDLE_PATH = path.join(process.cwd(), "methods", "summarize-pdf", "main.mthds");

export interface SummarizePdfInputs {
  /** An http(s) URL or a pipelex-storage:// reference. For a local file or bytes,
   *  run `getPipelexClient().prepareInputs({ files: [{ content: bundle }], inputs })` first —
   *  it uploads and rewrites the value. Note: prepareInputs treats any string it does not
   *  recognise as data:, http(s):// or pipelex-storage:// as a LOCAL FILE PATH it reads and
   *  uploads, so a public endpoint must gate schemes before handing values to it. */
  document: { url: string };
  context?: string;
}

export async function summarizePdf(inputs: SummarizePdfInputs): Promise<DocumentSummary> {
  const bundle = await readFile(BUNDLE_PATH, "utf8");
  const results: RunResults = await getPipelexClient().startAndWaitForResult({
    pipe_code: PIPE_CODE,
    mthds_contents: [bundle],
    inputs,
  });
  return parseDocumentSummary(results.main_stuff);
}
```

Variants by selector, replacing the `mthds_contents` line and dropping the bundle read:

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

## The offline gate

Copy `references/codegen-check.mjs` verbatim to `scripts/codegen-check.mjs`. It imports only Node builtins and `@pipelex/sdk`, runs under plain `node` whatever the project's TypeScript build, and prints through `process.stdout` / `process.stderr` so a `no-console` rule does not fire. Register it and extend the existing gate:

```json
{
  "scripts": {
    "codegen:check": "node scripts/codegen-check.mjs src/generated/summarize-pdf",
    "check": "npm run lint && npm run typecheck && npm run codegen:check"
  }
}
```

Add every method's directory to the `codegen:check` line as it is integrated. Exit codes: `0` current, `1` drift or stale source, `2` no verdict (no lock, an unreadable file, a symlink in the tree). It runs from the project root because `sources.json` records source paths relative to it. When `@pipelex/sdk` ships this as a command of its own, the script is replaced by that one line.

## The Node-only boundary

`readFile`, `node:path` and `process.cwd()` in the call site are server-side facts. In a framework with a client/server split (Next.js, Remix, SvelteKit), the module belongs on the server side — a Server Action, a route handler, a loader — and the JS starter marks such modules with `import "server-only"`. Never import it from a component that renders in the browser: the API key would leave the server.

## A project that owns a codegen harness

A project made from `pipelex-starter-js`, or one that copied its codegen kit, has: `npm run codegen` (regenerates every `methods/*` tree through the hosted `/v1/codegen`, writes `contracts.ts` and `sources.json` with a `derived` map), `npm run codegen:check` (offline, in `make check`), `npm run codegen:verify` (semantic, keyed), and `make add-method METHOD=<mt_…|github.com/…>` (manifest, tree, action trio, narrower, form, tab — one shot, never overwrites). On such a project:

- a local bundle goes under `methods/<name>/main.mthds`, then `npm run codegen`; the fan-out follows `docs/codegen.md` and the existing actions under `src/actions/` and narrowers under `src/types/`;
- a catalog or published method goes through `make add-method`;
- the verification is `make check`; the refresh is `npm run codegen`; no `sources.json` of this skill's shape, no `scripts/codegen-check.mjs`, no second generated directory.
