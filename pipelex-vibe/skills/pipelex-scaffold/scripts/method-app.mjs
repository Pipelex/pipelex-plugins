#!/usr/bin/env node
// The method app's two npm commands that carry the user's values, run from a request file rather than a
// command line: /pipelex-scaffold's branch A runs `init`, and its references/uncreated-copy.md `create`.
//
// Usage: node method-app.mjs <init | create>
//
// Neither takes a value on its command line. Each reads `pipelex-scaffold-request.json` in the directory it
// is run in, which the agent writes with its own file tools, and removes it once read, so a run never reads
// the request of the one before:
//   { "dir": "<dir>", "method": "<method>", "options": { "title": "…", "license-holder": "…", "dry-run": true } }
// `options` holds the gesture's flags without their leading `--`: name, title, description, author-name,
// author-email, repo-url, license, license-holder, license-year, method-name, pipe and label, each a string,
// a blank one counting as not given, and the switches dry-run and, for `init` alone, no-create, each true or
// false. No value holds a line break. `dir` is resolved from the directory the script runs in, and so is a
// `method` that names a file or a directory there, a leading `~` read as the home directory, which is passed
// on as an absolute path; any other method, a catalog id or an address, is passed on as written.
//
// init     runs the family's initializer, `npm create --yes @pipelex/method-app@latest <dir> -- --method
//          <method> [--<option> <value>]… --quiet`, from the directory the script runs in, its output
//          and its exit code passed through untouched: the initializer's own verdict is its last line.
// create   runs the copy's own `npm run create -- <method> [--<option> <value>]…` in <dir>, after
//          `npm install` when the copy's dependencies are not installed (no record of an install in
//          `node_modules/.package-lock.json`, after `--no-create`, in a copy made by hand, or after an
//          install that failed), as the template's `make create` did. Everything both print, both
//          streams, goes to `create.log` in a new directory under the system's temporary directory. Then
//          it prints:
//            the log's last 40 lines
//            warnings:          followed by each distinct line of the whole log opening `! ` (the
//                               gesture's own warnings) or `warning: ` (the bootstrap's), in byte order,
//                               once each; or `warnings: none`
//            npm run create exited <code>; the whole log is <path>
//          or, when the install failed and the gesture did not start,
//            npm install exited <code>; the whole log is <path>
// Either prints one line instead when nothing ran:
//   refused: <reason>    usage (no such command), no-request <path> (no request file at <path>),
//                        bad-request (the request could not be read or is not as above; what is wrong,
//                        the system's message for a failed read, goes to stderr),
//                        no-directory (create alone: no directory at <dir>), or node-debug (`NODE_DEBUG`
//                        names Node's child_process log, which prints every spawn's environment, the key
//                        included, on stderr; checked before the request is read, which is kept)
//   failed: npm          npm could not be started, the reason on stderr
//   failed: log          create alone: the log could not be made or read, the file system's message on stderr
// The exit code is presentation: for init, the initializer's; for create, 0 when the gesture or the install
// ran, whatever it exited with, and 1 otherwise. The gesture's own code is the one on the last line.
//
// Why a request file: a value the user gave, a title holding an apostrophe or a bundle path holding a
// space, has no quoting that bash, zsh, PowerShell 7 and Windows PowerShell 5.1 all read alike, and a
// crafted one could leave its argument. Read from a file, every value reaches npm as one argument of an
// array, through no shell. Why a log: the gesture prints its warnings before `npm run all`, whose output
// fills the tail, and runs the bootstrap twice, so the warnings are read off the whole log, once each. It
// names variables and never prints their values, so the tail is safe to read. The key reaches npm from
// this process's environment, or from an env file in <dir>, and never through the request. That environment
// cannot leave out the key, which the gesture reads, so the script refuses to spawn anything while Node's own
// child_process log is on, the one place Node would print it.
//
// It is Node rather than shell so that it runs the same on macOS, Linux and Windows, where a
// PowerShell-only machine has no bash, no `mktemp` and no `grep`. npm is the `npm-cli.js` that npm names
// in `npm_execpath` when it runs this script, `npm` on the PATH on macOS and Linux, and on Windows, where
// `npm` is `npm.cmd`, which Node does not spawn without a shell, the `npm-cli.js` beside the first `npm.cmd`
// on the PATH, which is the npm the user would get by typing `npm`, a globally upgraded one included, or,
// failing that, the one the Node installer puts beside `node.exe`, run with this Node, as the template's own
// scripts run it.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const REQUEST = "pipelex-scaffold-request.json";
const TAIL_LINES = 40;
const WARNING = /^(! |warning: )/;
const NPM_SCRIPT = "npm-cli.js";
const VALUE_OPTIONS = new Set([
  "name",
  "title",
  "description",
  "author-name",
  "author-email",
  "repo-url",
  "license",
  "license-holder",
  "license-year",
  "method-name",
  "pipe",
  "label",
]);
const SWITCHES = { init: new Set(["dry-run", "no-create"]), create: new Set(["dry-run"]) };
// npm's install record and the template's own stamp, which `make create` and the initializer touch after an
// install so that the project's first check does not install again.
const NPM_RECORD = path.join("node_modules", ".package-lock.json");
const INSTALL_STAMP = path.join("node_modules", ".lock-installed");
// The variables that point git at another repository, which the initializer drops before it runs npm: the
// copy's install wires its hooks with `git config`, which would otherwise write where they point.
const GIT_REDIRECTS = ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX"];

class Stop extends Error {
  constructor(line, detail = "") {
    super(line);
    this.line = line;
    this.detail = detail;
  }
}

// Whether `NODE_DEBUG` turns on Node's child_process log, matched as Node matches it: names separated by
// commas, `*` matching anything, in any letter case. Node reads the setting once as it starts, so removing
// it from this process's environment would not turn the log off.
function logsSpawns(setting) {
  if (!setting) {
    return false;
  }
  const pattern = setting.replace(/[|\\{}()[\]^$+?.]/g, "\\$&").replaceAll("*", ".*").replaceAll(",", "$|^");
  return new RegExp(`^${pattern}$`, "i").test("child_process");
}

function badRequest(detail) {
  throw new Stop("refused: bad-request", detail);
}

// npm's own script under `npm run`, `npm` on the PATH elsewhere but on Windows, and there the npm-cli.js
// beside the first npm.cmd on the PATH, else beside node.exe. Only npm's own script is taken from
// `npm_execpath`: pnpm, yarn and npx name scripts of their own there. A PATH entry may be written in double
// quotes, which Windows accepts and Node's path functions would keep, so they are stripped first.
function npmInvocation() {
  const windows = process.platform === "win32";
  const pathOf = windows ? path.win32 : path.posix;
  const named = process.env.npm_execpath;
  if (named !== undefined && pathOf.basename(named) === NPM_SCRIPT) {
    return { command: process.execPath, args: [named] };
  }
  if (!windows) {
    return { command: "npm", args: [] };
  }
  const searchPath = Object.entries(process.env).find(([name]) => name.toUpperCase() === "PATH")?.[1] ?? "";
  const beside = (directory) => path.win32.join(directory, "node_modules", "npm", "bin", NPM_SCRIPT);
  const candidates = [
    ...searchPath
      .split(";")
      .map((directory) => directory.trim().replace(/^"(.*)"$/, "$1"))
      .filter((directory) => directory !== "" && fs.existsSync(path.win32.join(directory, "npm.cmd")))
      .map(beside),
    beside(path.win32.dirname(process.execPath)),
  ];
  const found = candidates.find((candidate) => fs.existsSync(candidate));
  if (found === undefined) {
    throw new Stop("failed: npm", `no ${NPM_SCRIPT} beside an npm.cmd on the PATH or beside ${process.execPath}`);
  }
  return { command: process.execPath, args: [found] };
}

function isDirectory(given) {
  try {
    return fs.statSync(given).isDirectory();
  } catch {
    return false;
  }
}

// A path from the request, `~` read as the home directory, as a shell would have expanded it.
function expandHome(given) {
  return given === "~" || /^~[/\\]/.test(given) ? path.join(os.homedir(), given.slice(1)) : given;
}

function text(request, key, required) {
  const value = request[key];
  // A blank option counts as not given, as the gesture and the initializer read one; a blank dir or method is wrong.
  if (!required && (value === undefined || (typeof value === "string" && value.trim() === ""))) {
    return undefined;
  }
  if (typeof value !== "string" || value.trim() === "") {
    badRequest(`"${key}" must be a string that is not blank`);
  }
  if (/[\r\n]/.test(value)) {
    badRequest(`"${key}" holds a line break`);
  }
  return value;
}

// The request in the working directory, removed once read whatever it holds, and the gesture's words.
function readRequest(command) {
  const file = path.resolve(REQUEST);
  let raw;
  try {
    raw = fs.readFileSync(file, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") {
      throw new Stop(`refused: no-request ${file}`, `write the request at ${file} with your file tools first`);
    }
    badRequest(`${file} could not be read: ${error.message}`);
  }
  try {
    fs.rmSync(file, { force: true });
  } catch (error) {
    badRequest(`${file} could not be removed: ${error.message}`);
  }
  let request;
  try {
    request = JSON.parse(raw.replace(/^\uFEFF/, ""));
  } catch (error) {
    badRequest(`${file} is not JSON: ${error.message}`);
  }
  if (request === null || typeof request !== "object" || Array.isArray(request)) {
    badRequest("the request is not a JSON object");
  }
  for (const key of Object.keys(request)) {
    if (!["dir", "method", "options"].includes(key)) {
      badRequest(`"${key}" is not a field of the request: dir, method and options are`);
    }
  }
  const dir = path.resolve(expandHome(text(request, "dir", true)));
  const given = text(request, "method", true);
  const local = path.resolve(expandHome(given));
  const method = fs.existsSync(local) ? local : given;
  const options = request.options ?? {};
  if (options === null || typeof options !== "object" || Array.isArray(options)) {
    badRequest('"options" is not a JSON object');
  }
  const words = [];
  const switches = [];
  for (const [name, value] of Object.entries(options)) {
    if (SWITCHES[command].has(name)) {
      if (typeof value !== "boolean") {
        badRequest(`"${name}" is a switch: true or false`);
      }
      if (value) {
        switches.push(`--${name}`);
      }
    } else if (VALUE_OPTIONS.has(name)) {
      const given = text(options, name, false);
      if (given !== undefined) {
        words.push(`--${name}`, given);
      }
    } else {
      badRequest(`"${name}" is not an option of ${command}`);
    }
  }
  return { dir, method, words: [...words, ...switches] };
}

// npm's environment: this process's, the key included, which the gesture reads, without what points git elsewhere.
function npmEnvironment() {
  return Object.fromEntries(Object.entries(process.env).filter(([name]) => !GIT_REDIRECTS.includes(name.toUpperCase())));
}

function init() {
  const { dir, method, words } = readRequest("init");
  const npm = npmInvocation();
  const result = spawnSync(
    npm.command,
    [...npm.args, "create", "--yes", "@pipelex/method-app@latest", dir, "--", "--method", method, ...words, "--quiet"],
    { stdio: "inherit", env: npmEnvironment(), windowsHide: true },
  );
  if (result.error !== undefined) {
    throw new Stop("failed: npm", `${npm.command}: ${result.error.message}`);
  }
  return { lines: [], detail: "", code: result.status ?? 1 };
}

function touch(file) {
  try {
    fs.closeSync(fs.openSync(file, "a"));
    const now = new Date();
    fs.utimesSync(file, now, now);
  } catch {
    // best effort: the stamp only spares the project's first check an install
  }
}

function create() {
  const { dir, method, words } = readRequest("create");
  if (!isDirectory(dir)) {
    throw new Stop("refused: no-directory", `no directory at ${dir}`);
  }
  const npm = npmInvocation();
  let logDir;
  let log;
  let out;
  try {
    logDir = fs.mkdtempSync(path.join(os.tmpdir(), "pipelex-create-"));
    log = path.join(logDir, "create.log");
    out = fs.openSync(log, "w");
  } catch (error) {
    throw new Stop("failed: log", String(error?.message ?? error));
  }
  const options = { stdio: ["ignore", out, out], env: npmEnvironment(), windowsHide: true };
  let step = "npm install";
  let result;
  try {
    if (!fs.existsSync(path.join(dir, NPM_RECORD))) {
      result = spawnSync(npm.command, [...npm.args, "install"], { ...options, cwd: dir });
      if (result.error === undefined && result.status === 0) {
        touch(path.join(dir, INSTALL_STAMP));
      }
    }
    if (result === undefined || (result.error === undefined && result.status === 0)) {
      step = "npm run create";
      result = spawnSync(npm.command, [...npm.args, "--prefix", dir, "run", "create", "--", method, ...words], options);
    }
  } finally {
    fs.closeSync(out);
  }
  if (result.error !== undefined) {
    throw new Stop("failed: npm", `${npm.command}: ${result.error.message}`);
  }
  if (step === "npm run create" && result.status === 0 && fs.existsSync(path.join(dir, INSTALL_STAMP))) {
    // The gesture re-syncs package-lock.json without installing, as the template's `make create` notes.
    touch(path.join(dir, INSTALL_STAMP));
  }

  let content;
  try {
    content = fs.readFileSync(log, "utf8");
  } catch (error) {
    throw new Stop("failed: log", String(error?.message ?? error));
  }
  const trimmed = content.replace(/\r\n/g, "\n").replace(/\n+$/, "");
  const lines = trimmed === "" ? [] : trimmed.split("\n");
  const warnings = [...new Set(lines.filter((line) => WARNING.test(line)))].sort((first, second) =>
    Buffer.compare(Buffer.from(first), Buffer.from(second)),
  );
  // A step ended by a signal has no exit code; the signal stands in its place.
  const exited = result.status ?? result.signal;
  return {
    lines: [
      ...lines.slice(-TAIL_LINES),
      ...(step === "npm install" ? [] : warnings.length === 0 ? ["warnings: none"] : ["warnings:", ...warnings]),
      `${step} exited ${exited}; the whole log is ${log}`,
    ],
    detail: "",
    code: 0,
  };
}

// A failure nothing above expected still ends on a line and never on a stack trace.
let outcome;
try {
  const [command, ...rest] = process.argv.slice(2);
  if (rest.length !== 0 || !["init", "create"].includes(command)) {
    throw new Stop("refused: usage", "usage: node method-app.mjs <init | create>, with the request in pipelex-scaffold-request.json");
  }
  if (logsSpawns(process.env.NODE_DEBUG)) {
    throw new Stop(
      "refused: node-debug",
      "NODE_DEBUG turns on Node's child_process log, which prints npm's environment, the key included: start the harness from a shell without it",
    );
  }
  outcome = command === "init" ? init() : create();
} catch (error) {
  outcome =
    error instanceof Stop
      ? { lines: [error.line], detail: error.detail, code: 1 }
      : { lines: ["failed: log"], detail: String(error?.message ?? error), code: 1 };
}
const { lines, detail, code } = outcome;
if (lines.length !== 0) {
  process.stdout.write(`${lines.join("\n")}\n`);
}
if (detail) {
  process.stderr.write(`${detail}\n`);
}
process.exitCode = code;
