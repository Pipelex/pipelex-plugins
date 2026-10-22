#!/usr/bin/env node
// SPDX-License-Identifier: MIT-0
// codegen-check.mjs — the offline drift gate for Pipelex-generated trees.
//
// Copied verbatim into a project by /pipelex-integrate. Run it from the project root
// with one generated directory per argument:
//
//     node scripts/codegen-check.mjs src/generated/summarize-pdf src/generated/extract-entities
//
// For each directory it (1) runs @pipelex/sdk's runCodegenCheck over the stamped files
// against codegen.lock — pure hashing, no engine, no network, no API key — and (2) compares
// the SHA-256 recorded for each .mthds source in sources.json against the file on disk, and
// the recorded sources against every .mthds file of the method tree the call site sends from
// the sidecar's `bundle_dir`, listed by the MTHDS standard's own lister under the membership
// rule the run follows, so a bundle changed without a regeneration — a file edited, removed or
// added, or one a `.gitignore` or the manifest's `exclude` now keeps out or lets in — is caught
// as `stale-source`; and (3) hashes each template file the sidecar's `templates` records and
// checks that the tree still carries it, so one moved, removed, edited or left out since the
// call site was written is caught the same way.
//
// Exit codes: 0 current · 1 drift or stale source · 2 no verdict (no lock, an unreadable
// file, a symlink in the tree, a check that throws, @pipelex/sdk not importable, or the `mthds`
// package beside it missing or too old). Precedence across directories: 2 > 1 > 0.
//
// It is the twin of codegen_check.py, which does the same for a Python project over
// pipelex-sdk. It imports only Node builtins, @pipelex/sdk and the `mthds` package the SDK
// depends on, whose lister is the one the SDK sends a `directory` with, found from the SDK's
// own location, and writes through process.stdout / process.stderr so a no-console lint rule
// stays quiet. When @pipelex/sdk
// ships this check as a command, replace this file with that one line.

import { createHash } from "node:crypto";
import { lstat, readdir, readFile, realpath, stat } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath, pathToFileURL } from "node:url";

const EXIT_CURRENT = 0;
const EXIT_DRIFT = 1;
const EXIT_NO_VERDICT = 2;

const LOCK_FILENAME = "codegen.lock";
const SIDECAR_FILENAME = "sources.json";
const PRUNED_DIRECTORIES = new Set(["node_modules", ".git", "dist", "build", ".next"]);
// The SDK is tested for the exports the check uses, not for a version, so an SDK that has them gets a
// verdict whatever it is. SDK_MINIMUM is what a message asks the user to install: the floor
// /pipelex-integrate's step 8 puts in the project, which carries these exports and everything the
// call site the skill writes uses. Naming the older release that first carried the exports would send the
// user through a second upgrade.
const SDK_EXPORTS = ["CodegenLockError", "isStampableArtifactPath", "runCodegenCheck"];
// What the gate takes from `mthds`: the lister @pipelex/sdk lists a `directory` with, and its refusal.
const LISTER_EXPORTS = ["MethodTreeError", "listMethodTree"];
// A `template_file` key at the start of a line of a .mthds file: how a bundle file names a template, read only for
// a sidecar written before the skill recorded `templates`, where it says the call site may not send that file.
const TEMPLATE_FILE_KEY = /^\s*["']?template_file["']?\s*=/m;
const SDK_MINIMUM = "0.48.0";

// `ignoreBOM: true` keeps a leading BOM in the decoded string. The default strips it, so an
// artifact given a BOM would hash as its un-BOM'd self, match the lock, and report current while
// the bytes on disk are hand-edited — the gate's one job is to not say that.
const strictUtf8 = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });

const out = (line) => process.stdout.write(`${line}\n`);
const err = (line) => process.stderr.write(`${line}\n`);
const describe = (error) => (error instanceof Error ? `${error.name}: ${error.message}` : String(error));

/**
 * @pipelex/sdk's namespace, or null once the reason it cannot be used is on stderr.
 *
 * Imported here rather than by a static `import` at the top of the file: a static import that
 * cannot resolve fails before any of this runs, and the uncaught error exits 1 — which every
 * gate reads as drift, in a tree nobody checked. A gate that cannot run has no verdict to give.
 */
async function loadSdk() {
  let sdk;
  try {
    sdk = await import("@pipelex/sdk");
  } catch (error) {
    // Only the SDK itself not resolving is the missing-SDK case. A package the SDK imports going
    // missing is ERR_MODULE_NOT_FOUND too, but it names that package, and it means a broken install.
    if (error?.code === "ERR_MODULE_NOT_FOUND" && String(error.message).includes("'@pipelex/sdk'")) {
      err(
        `codegen-check: no verdict — @pipelex/sdk ${SDK_MINIMUM} or later is not importable (${error.message}). ` +
          "Run this script from inside the project, with its dependencies installed, through its package manager, e.g. `npm run codegen:check`.",
      );
    } else {
      err(`codegen-check: no verdict — @pipelex/sdk could not be loaded (${describe(error)}). Reinstall the project's dependencies.`);
    }
    return null;
  }
  const missing = SDK_EXPORTS.filter((name) => typeof sdk[name] !== "function");
  if (missing.length > 0) {
    err(
      `codegen-check: no verdict — the installed @pipelex/sdk has no ${missing.join(", ")}, so it predates the offline check. ` +
        `Raise the project's @pipelex/sdk to ${SDK_MINIMUM} or later and install its dependencies.`,
    );
    return null;
  }
  const lister = await loadLister();
  if (lister === null) return null;
  return { ...sdk, ...lister };
}

/**
 * The `mthds` package @pipelex/sdk depends on, found the way Node finds it for the SDK: in a `node_modules`
 * at or above the SDK's own physical directory. A bare import of `mthds` from this script would resolve from
 * the project root instead, where a package manager that does not hoist, pnpm's default among them, puts no
 * `mthds`. Returns { MethodTreeError, listMethodTree }, or null once the reason is on stderr.
 */
async function loadLister() {
  let mthds;
  try {
    let directory = path.dirname(await realpath(fileURLToPath(import.meta.resolve("@pipelex/sdk"))));
    let manifest = null;
    for (;;) {
      const candidate = path.join(directory, "node_modules", "mthds", "package.json");
      try {
        manifest = { file: candidate, json: JSON.parse(await readFile(candidate, "utf8")) };
        break;
      } catch (error) {
        if (error.code !== "ENOENT" && error.code !== "ENOTDIR") throw error;
      }
      const parent = path.dirname(directory);
      if (parent === directory) break;
      directory = parent;
    }
    if (manifest === null) {
      err("codegen-check: no verdict — the `mthds` package @pipelex/sdk depends on is not installed beside it. Reinstall the project's dependencies.");
      return null;
    }
    const root = manifest.json.exports?.["."];
    const entry = typeof root === "string" ? root : (root?.import ?? root?.default ?? manifest.json.main ?? "index.js");
    mthds = await import(pathToFileURL(path.join(path.dirname(manifest.file), entry)).href);
  } catch (error) {
    err(`codegen-check: no verdict — the \`mthds\` package @pipelex/sdk depends on could not be loaded (${describe(error)}). Reinstall the project's dependencies.`);
    return null;
  }
  const missing = LISTER_EXPORTS.filter((name) => typeof mthds[name] !== "function");
  if (missing.length > 0) {
    err(
      `codegen-check: no verdict — the \`mthds\` package beside @pipelex/sdk has no ${missing.join(", ")}, so it predates the method tree. ` +
        `Raise the project's @pipelex/sdk to ${SDK_MINIMUM} or later and install its dependencies.`,
    );
    return null;
  }
  return { MethodTreeError: mthds.MethodTreeError, listMethodTree: mthds.listMethodTree };
}

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

/** The lock check: { code, lines }. A state of the tree is always an outcome; anything else it throws is `settle`'s. */
async function checkTree(dir, { CodegenLockError, isStampableArtifactPath, runCodegenCheck }) {
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
    throw error; // not a state of the tree, so no verdict for it: see `settle`
  }
}

/** The sidecar check against the .mthds sources and the bundle directory, relative to the project root: { code, lines }. */
async function checkSources(dir, lister) {
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
  const bundleDir = sidecar.bundle_dir;
  if (sources === undefined && bundleDir === undefined) {
    return { code: EXIT_CURRENT, lines: [`  ${SIDECAR_FILENAME} records no sources — a by-ref or by-id integration; source staleness does not apply`] };
  }
  if (typeof sources !== "object" || sources === null || Array.isArray(sources)) {
    return { code: EXIT_DRIFT, lines: [`  stale-source: ${SIDECAR_FILENAME} — \`sources\` is not an object, so staleness cannot be ruled out`] };
  }
  const recordedSources = Object.entries(sources).sort();
  if (recordedSources.length === 0 && bundleDir === undefined) {
    return { code: EXIT_CURRENT, lines: [`  ${SIDECAR_FILENAME} records no sources — a by-ref or by-id integration; source staleness does not apply`] };
  }
  // The hashes alone prove only that the recorded files are unchanged. The call site sends its bundle
  // directory as the method's tree, so a file added beside them changes what runs while every recorded
  // hash still matches: without the directory, that addition cannot be ruled out.
  if (bundleDir === undefined) {
    return {
      code: EXIT_DRIFT,
      lines: [`  stale-source: ${SIDECAR_FILENAME} — records sources but no \`bundle_dir\`, so a .mthds file added to the bundle cannot be ruled out`],
    };
  }
  if (typeof bundleDir !== "string" || bundleDir === "") {
    return { code: EXIT_DRIFT, lines: [`  stale-source: ${SIDECAR_FILENAME} — \`bundle_dir\` is not a non-empty string, so staleness cannot be ruled out`] };
  }

  const lines = [];
  const loaded = await listBundle(bundleDir, lister);
  lines.push(...loaded.lines);
  const recordedPaths = new Set();
  for (const [source, recorded] of recordedSources) {
    const resolved = path.resolve(process.cwd(), source);
    recordedPaths.add(resolved);
    let onDisk;
    try {
      onDisk = sha256(await readFile(resolved));
    } catch (error) {
      lines.push(`  stale-source: ${source} — recorded as a source but ${error.code === "ENOENT" ? "no longer on disk" : `unreadable (${error.message})`}`);
      continue;
    }
    if (onDisk !== recorded) {
      lines.push(`  stale-source: ${source} — edited since the types were generated`);
    } else if (loaded.paths !== null && !loaded.paths.has(resolved)) {
      lines.push(`  stale-source: ${source} — recorded as a source but left out of the tree the call site sends`);
    }
  }
  if (loaded.paths !== null) {
    for (const [resolved, shown] of loaded.paths) {
      if (!recordedPaths.has(resolved)) lines.push(`  stale-source: ${shown} — added to the bundle since the types were generated`);
    }
  }
  lines.push(...(await checkTemplates(sidecar, loaded)));
  return { code: lines.length ? EXIT_DRIFT : EXIT_CURRENT, lines };
}

/**
 * The template files the call site's tree carries, recorded in the sidecar's `templates` as
 * `{ "<template_file>": { path, sha256 } }`: each is hashed against the file at its path and looked up in the
 * tree. A renamed or added `template_file` needs no check here, since it edits a .mthds file the sources above
 * hash. A template the membership rule keeps out of the tree, by a `.gitignore` or the manifest's `exclude`, is
 * never sent, so the run refuses its step. A sidecar written before the skill recorded `templates` has none, and
 * then a bundle file naming a `template_file` is stale: its call site may send no template at all. Returns the
 * lines to report.
 */
async function checkTemplates(sidecar, loaded) {
  const templates = sidecar.templates;
  const lines = [];
  if (templates === undefined) {
    if (loaded.paths === null) return lines;
    for (const [resolved, shown] of loaded.paths) {
      let text;
      try {
        text = await readFile(resolved, "utf8");
      } catch {
        continue; // the source comparison already reports a recorded file it cannot read, and an added one as added
      }
      if (TEMPLATE_FILE_KEY.test(text)) {
        lines.push(`  stale-source: ${shown} — names a \`template_file\`, and ${SIDECAR_FILENAME} records no \`templates\`, so the call site may not send it`);
      }
    }
    return lines;
  }
  // The same fail-closed reading as `sources`: a `templates` coerced to {} would check nothing and exit 0.
  if (typeof templates !== "object" || templates === null || Array.isArray(templates)) {
    return [`  stale-source: ${SIDECAR_FILENAME} — \`templates\` is not an object, so staleness cannot be ruled out`];
  }
  for (const [key, entry] of Object.entries(templates).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))) {
    const wellFormed =
      typeof entry === "object" && entry !== null && !Array.isArray(entry) && typeof entry.path === "string" && entry.path !== "" && typeof entry.sha256 === "string";
    if (!wellFormed) {
      lines.push(`  stale-source: ${SIDECAR_FILENAME} — the \`templates\` entry for ${key} is not a { path, sha256 } object, so staleness cannot be ruled out`);
      continue;
    }
    let onDisk;
    try {
      onDisk = sha256(await readFile(path.resolve(process.cwd(), entry.path)));
    } catch (error) {
      lines.push(`  stale-source: ${entry.path} — recorded as a template file but ${error.code === "ENOENT" ? "no longer on disk" : `unreadable (${error.message})`}`);
      continue;
    }
    if (onDisk !== entry.sha256) {
      lines.push(`  stale-source: ${entry.path} — template file edited since the call site was written`);
    } else if (loaded.members !== null && !loaded.members.has(path.resolve(process.cwd(), entry.path))) {
      lines.push(`  stale-source: ${entry.path} — recorded as a template file but left out of the tree the call site sends`);
    }
  }
  return lines;
}

/**
 * The method tree the call site sends from the bundle directory, listed with the standard's lister as
 * @pipelex/sdk lists a `directory`: a file whose name starts with a dot, one under `node_modules` or
 * `__pycache__`, a run's inputs file, and whatever a `.gitignore` inside the tree or the manifest's `exclude`
 * keeps out are not in it, exactly as they are not in the run. The tree is rooted at the nearest
 * `METHODS.toml` at or above the directory, as the SDK roots it, so a manifest above the bundle makes the run
 * send more than the bundle. Returns { paths, members, lines }: `paths` maps each .mthds file's resolved path
 * to the path shown for it, `members` each file's resolved path to its SHA-256, both null when the tree
 * cannot be listed, which `lines` then explains.
 */
async function listBundle(bundleDir, { MethodTreeError, listMethodTree }) {
  const root = path.resolve(process.cwd(), bundleDir);
  try {
    // Asked first so a missing or non-directory bundle reads the same as in the Python twin.
    if (!(await stat(root)).isDirectory()) {
      return { paths: null, members: null, lines: [`  stale-source: ${bundleDir} — recorded as the bundle directory but not a directory`] };
    }
  } catch (error) {
    const reason = error.code === "ENOENT" ? "no longer on disk" : `unreadable (${error.message})`;
    return { paths: null, members: null, lines: [`  stale-source: ${bundleDir} — recorded as the bundle directory but ${reason}`] };
  }
  let tree;
  try {
    tree = await listMethodTree(root);
  } catch (error) {
    if (!(error instanceof MethodTreeError)) throw error; // not a state of the bundle: see `settle`
    return { paths: null, members: null, lines: [`  stale-source: ${bundleDir} — the call site cannot send it as a method tree (${error.message})`] };
  }
  const lines = [];
  // The lister reports the physical root; the shown and compared paths stay on the bundle directory as recorded.
  const rootFromBundle = path.relative(await realpath(root), tree.root ?? (await realpath(root))).split(path.sep).join("/") || ".";
  if (rootFromBundle !== ".") {
    const shownRoot = path.posix.normalize(path.posix.join(bundleDir, rootFromBundle));
    lines.push(
      `  stale-source: ${bundleDir} — a METHODS.toml at ${shownRoot} roots the tree the call site sends above the bundle directory, ` +
        "so the run sends files the types were not generated from",
    );
  }
  const members = new Map();
  const shown = [];
  for (const member of tree.files) {
    const resolved = path.resolve(root, rootFromBundle, member.path);
    members.set(resolved, member.sha256);
    if (member.path.endsWith(".mthds")) shown.push([resolved, path.posix.normalize(path.posix.join(bundleDir, rootFromBundle, member.path))]);
  }
  // Ordered by the path shown, as the Python twin orders them.
  const paths = new Map(shown.sort(([, a], [, b]) => (a < b ? -1 : a > b ? 1 : 0)));
  if (paths.size === 0) {
    lines.push(`  stale-source: ${bundleDir} — holds no .mthds file, so the call site has no bundle to send`);
  }
  return { paths, members, lines };
}

/**
 * Run one check over one directory. An error the check did not expect is no verdict for that
 * directory, and the precedence below decides the exit code: uncaught, it would end the whole run
 * with exit 1, which reads as drift, and every directory after it would go unchecked.
 */
async function settle(name, check) {
  try {
    return await check();
  } catch (error) {
    return { code: EXIT_NO_VERDICT, lines: [`  no verdict: the ${name} check failed — ${describe(error)}`] };
  }
}

function worse(a, b) {
  // Precedence: no verdict > drift > current.
  if (a === EXIT_NO_VERDICT || b === EXIT_NO_VERDICT) return EXIT_NO_VERDICT;
  if (a === EXIT_DRIFT || b === EXIT_DRIFT) return EXIT_DRIFT;
  return EXIT_CURRENT;
}

async function main(argv) {
  const sdk = await loadSdk();
  if (sdk === null) return EXIT_NO_VERDICT;

  const dirs = argv.slice(2);
  if (dirs.length === 0) {
    err("usage: node scripts/codegen-check.mjs <generated-dir> [<generated-dir> ...]");
    return EXIT_NO_VERDICT;
  }

  let exitCode = EXIT_CURRENT;
  for (const dir of dirs) {
    out(`${dir}`);
    const tree = await settle("lock", () => checkTree(dir, sdk));
    const sources = tree.code === EXIT_NO_VERDICT ? { code: EXIT_CURRENT, lines: [] } : await settle("source", () => checkSources(dir, sdk));
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
