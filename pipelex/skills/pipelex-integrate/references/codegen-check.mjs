#!/usr/bin/env node
// codegen-check.mjs — the offline drift gate for Pipelex-generated trees.
//
// Copied verbatim into a project by /pipelex-integrate. Run it from the project root
// with one generated directory per argument:
//
//     node scripts/codegen-check.mjs src/generated/summarize-pdf src/generated/extract-entities
//
// For each directory it (1) runs @pipelex/sdk's runCodegenCheck over the stamped files
// against codegen.lock — pure hashing, no engine, no network, no API key — and (2) compares
// the SHA-256 recorded for each .mthds source in sources.json against the file on disk, so
// a bundle edited without a regeneration is caught as `stale-source`.
//
// Exit codes: 0 current · 1 drift or stale source · 2 no verdict (no lock, an unreadable
// file, a symlink in the tree). Precedence across directories: 2 > 1 > 0.
//
// It imports only Node builtins and @pipelex/sdk, and writes through process.stdout /
// process.stderr so a no-console lint rule stays quiet. When @pipelex/sdk ships this check
// as a command, replace this file with that one line.

import { createHash } from "node:crypto";
import { lstat, readdir, readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { CodegenLockError, isStampableArtifactPath, runCodegenCheck } from "@pipelex/sdk";

const EXIT_CURRENT = 0;
const EXIT_DRIFT = 1;
const EXIT_NO_VERDICT = 2;

const LOCK_FILENAME = "codegen.lock";
const SIDECAR_FILENAME = "sources.json";
const PRUNED_DIRECTORIES = new Set(["node_modules", ".git", "dist", "build", ".next"]);

// `ignoreBOM: true` keeps a leading BOM in the decoded string. The default strips it, so an
// artifact given a BOM would hash as its un-BOM'd self, match the lock, and report current while
// the bytes on disk are hand-edited — the gate's one job is to not say that.
const strictUtf8 = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });

const out = (line) => process.stdout.write(`${line}\n`);
const err = (line) => process.stderr.write(`${line}\n`);

/** Every regular file under `root`, as sorted forward-slash paths relative to it. Refuses symlinks. */
async function walk(root, relative = "") {
  const absolute = relative ? path.join(root, relative) : root;
  const entries = await readdir(absolute, { withFileTypes: true });
  const paths = [];
  for (const entry of entries) {
    const rel = relative ? `${relative}/${entry.name}` : entry.name;
    if (entry.isSymbolicLink()) {
      throw new Error(`refusing to read through the symlink ${rel}`);
    }
    if (entry.isDirectory()) {
      if (PRUNED_DIRECTORIES.has(entry.name)) continue;
      paths.push(...(await walk(root, rel)));
    } else if (entry.isFile()) {
      paths.push(rel);
    }
  }
  return paths.sort();
}

async function readStrict(filePath) {
  return strictUtf8.decode(await readFile(filePath));
}

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

/** The lock check: { code, lines } — never throws. */
async function checkTree(dir) {
  let lockContent;
  try {
    lockContent = await readStrict(path.join(dir, LOCK_FILENAME));
  } catch (error) {
    return { code: EXIT_NO_VERDICT, lines: [`  no verdict: ${LOCK_FILENAME} — ${error.code === "ENOENT" ? "not found" : error.message}`] };
  }

  let files;
  try {
    const rootStat = await lstat(dir);
    if (rootStat.isSymbolicLink()) throw new Error("the generated directory itself is a symlink");
    const stampable = (await walk(dir)).filter((rel) => isStampableArtifactPath(rel));
    files = [];
    for (const rel of stampable) {
      files.push({ path: rel, content: await readStrict(path.join(dir, rel)) });
    }
  } catch (error) {
    return { code: EXIT_NO_VERDICT, lines: [`  no verdict: ${error.message}`] };
  }

  try {
    const report = await runCodegenCheck({ lockContent, files });
    if (report.isCurrent) {
      return {
        code: EXIT_CURRENT,
        lines: [`  ${files.length} artifact(s) current (crate ${report.crateFingerprint.slice(0, 12)}, engine ${report.engineVersion})`],
      };
    }
    return { code: EXIT_DRIFT, lines: report.drifts.map((drift) => `  ${drift.category}: ${drift.path} — ${drift.detail}`) };
  } catch (error) {
    if (error instanceof CodegenLockError) {
      return { code: EXIT_NO_VERDICT, lines: [`  no verdict: ${LOCK_FILENAME} — ${error.message}`] };
    }
    throw error;
  }
}

/** The sidecar check against the .mthds sources, relative to the project root: { code, lines }. */
async function checkSources(dir) {
  let sidecar;
  try {
    sidecar = JSON.parse(await readStrict(path.join(dir, SIDECAR_FILENAME)));
  } catch (error) {
    if (error.code === "ENOENT") {
      return { code: EXIT_CURRENT, lines: [`  no ${SIDECAR_FILENAME} — source staleness not checked`] };
    }
    return { code: EXIT_DRIFT, lines: [`  stale-source: ${SIDECAR_FILENAME} — unreadable (${error.message}), so staleness cannot be ruled out`] };
  }

  // The same hazard one level up, and it is why the line below is not `sidecar?.sources`. A file
  // whose whole content is `null`, `[]`, `"x"`, `42` or `true` is valid JSON and is not an object,
  // and optional chaining turns every one of them into `undefined` — the legitimate absent case —
  // so the gate would print "a by-ref or by-id integration" and exit 0 over a sidecar that says
  // nothing of the kind. On the sidecar, `?.` does exactly what `??` would do on `sources`.
  if (typeof sidecar !== "object" || sidecar === null || Array.isArray(sidecar)) {
    return { code: EXIT_DRIFT, lines: [`  stale-source: ${SIDECAR_FILENAME} — not a JSON object, so staleness cannot be ruled out`] };
  }

  // A present-but-wrong-shaped `sources` must fail the way an unreadable sidecar does. Coerced to
  // {} it would check nothing, print nothing and exit 0 — the one input that is both silent and
  // green. An array is the shape to beware (`typeof [] === "object"`, and `method.files` beside it
  // in the sidecar really is an array), and `null` is why this does not use `??`, which would
  // quietly turn an explicit null into the legitimate absent case.
  const sources = sidecar.sources;
  if (sources === undefined) {
    return { code: EXIT_CURRENT, lines: [`  ${SIDECAR_FILENAME} records no sources — a by-ref or by-id integration; source staleness does not apply`] };
  }
  if (typeof sources !== "object" || sources === null || Array.isArray(sources)) {
    return { code: EXIT_DRIFT, lines: [`  stale-source: ${SIDECAR_FILENAME} — \`sources\` is not an object, so staleness cannot be ruled out`] };
  }
  const recordedSources = Object.entries(sources).sort();
  if (recordedSources.length === 0) {
    return { code: EXIT_CURRENT, lines: [`  ${SIDECAR_FILENAME} records no sources — a by-ref or by-id integration; source staleness does not apply`] };
  }

  const lines = [];
  for (const [source, recorded] of recordedSources) {
    let onDisk;
    try {
      onDisk = sha256(await readFile(path.resolve(process.cwd(), source)));
    } catch (error) {
      lines.push(`  stale-source: ${source} — recorded as a source but ${error.code === "ENOENT" ? "no longer on disk" : `unreadable (${error.message})`}`);
      continue;
    }
    if (onDisk !== recorded) {
      lines.push(`  stale-source: ${source} — edited since the types were generated`);
    }
  }
  return { code: lines.length ? EXIT_DRIFT : EXIT_CURRENT, lines };
}

function worse(a, b) {
  // Precedence: no verdict > drift > current.
  if (a === EXIT_NO_VERDICT || b === EXIT_NO_VERDICT) return EXIT_NO_VERDICT;
  if (a === EXIT_DRIFT || b === EXIT_DRIFT) return EXIT_DRIFT;
  return EXIT_CURRENT;
}

async function main(argv) {
  const dirs = argv.slice(2);
  if (dirs.length === 0) {
    err("usage: node scripts/codegen-check.mjs <generated-dir> [<generated-dir> ...]");
    return EXIT_NO_VERDICT;
  }

  let exitCode = EXIT_CURRENT;
  for (const dir of dirs) {
    out(`${dir}`);
    const tree = await checkTree(dir);
    const sources = tree.code === EXIT_NO_VERDICT ? { code: EXIT_CURRENT, lines: [] } : await checkSources(dir);
    const code = worse(tree.code, sources.code);
    const write = code === EXIT_CURRENT ? out : err;
    for (const line of [...tree.lines, ...sources.lines]) write(line);
    if (code === EXIT_DRIFT) err("  Run /pipelex-integrate to refresh the generated types.");
    exitCode = worse(exitCode, code);
  }

  out(`\ncodegen-check: ${exitCode === EXIT_CURRENT ? "current" : exitCode === EXIT_DRIFT ? "drift" : "no verdict"}`);
  return exitCode;
}

// `process.exitCode` rather than `process.exit`: stdout is a pipe under `npm run`, `make` and every
// CI runner, where writes are asynchronous and `process.exit` drops the ones still pending. The code
// would survive either way; the drift lines explaining it are what gets truncated.
process.exitCode = await main(process.argv);
