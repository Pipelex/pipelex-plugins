#!/usr/bin/env node
// The method app's own `npm run create`, run in a copy of the template it has not run in, its output
// kept in a log: /pipelex-scaffold's references/uncreated-copy.md runs it.
//
// Usage: node run-create.mjs <dir> <method> [<option> <value>]…
//
// It runs `npm run create -- <method> [<option> <value>]…` in <dir> from the directory it is run in,
// so a relative bundle path is read from where the user stood, as the family's initializer reads it.
// Everything the gesture prints, both streams, goes to `create.log` in a new directory under the
// system's temporary directory. Then it prints:
//   the log's last 40 lines
//   warnings:            followed by each distinct line of the whole log opening `! ` (the gesture's
//                        own warnings) or `warning: ` (the bootstrap's), in byte order, once each;
//                        or `warnings: none`
//   npm run create exited <code>; the whole log is <path>
// or one line, when nothing ran:
//   refused: <reason>    usage, or no-directory (no directory at <dir>)
//   failed: npm          npm could not be started, its message on stderr
//   failed: log          the log could not be made or read, the file system's message on stderr
// The exit code is presentation: 0 when the gesture ran, whatever it exited with, 1 otherwise. The
// gesture's own code is the one on the last line.
//
// Why a log: the gesture prints its warnings before `npm run all`, whose output fills the tail, and runs
// the bootstrap twice, so the warnings are read off the whole log, once each. It names variables and
// never prints their values, so the tail is safe to read. The key reaches it from this process's
// environment, or from an env file in <dir>, and never through an argument.
//
// It is Node rather than shell so that it runs the same on macOS, Linux and Windows, where a
// PowerShell-only machine has no bash, no `mktemp` and no `grep`. npm is `npm` on the PATH on macOS
// and Linux; on Windows, where `npm` is `npm.cmd`, which Node does not spawn without a shell, it is the
// `npm-cli.js` the Node installer puts beside `node.exe`, run with this Node, as the template's own
// scripts run it.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const TAIL_LINES = 40;
const WARNING = /^(! |warning: )/;

function npmInvocation() {
  const named = process.env.npm_execpath;
  if (named !== undefined && /\.c?js$/.test(named)) {
    return { command: process.execPath, args: [named] };
  }
  if (process.platform !== "win32") {
    return { command: "npm", args: [] };
  }
  return { command: process.execPath, args: [path.join(path.dirname(process.execPath), "node_modules", "npm", "bin", "npm-cli.js")] };
}

function isDirectory(given) {
  try {
    return fs.statSync(given).isDirectory();
  } catch {
    return false;
  }
}

function runCreate(args) {
  if (args.length < 2 || args[0] === "" || args[1] === "") {
    return { lines: ["refused: usage"], detail: "usage: node run-create.mjs <dir> <method> [<option> <value>]…", code: 1 };
  }
  const [dir, ...gesture] = args;
  if (!isDirectory(dir)) {
    return { lines: ["refused: no-directory"], detail: `no directory at ${dir}`, code: 1 };
  }

  const logDir = fs.mkdtempSync(path.join(os.tmpdir(), "pipelex-create-"));
  const log = path.join(logDir, "create.log");
  const out = fs.openSync(log, "w");
  const npm = npmInvocation();
  let result;
  try {
    result = spawnSync(npm.command, [...npm.args, "--prefix", path.resolve(dir), "run", "create", "--", ...gesture], {
      stdio: ["ignore", out, out],
      windowsHide: true,
    });
  } finally {
    fs.closeSync(out);
  }
  if (result.error !== undefined) {
    return { lines: ["failed: npm"], detail: `${npm.command}: ${result.error.message}`, code: 1 };
  }

  const text = fs.readFileSync(log, "utf8").replace(/\r\n/g, "\n").replace(/\n+$/, "");
  const lines = text === "" ? [] : text.split("\n");
  const warnings = [...new Set(lines.filter((line) => WARNING.test(line)))].sort((first, second) =>
    Buffer.compare(Buffer.from(first), Buffer.from(second)),
  );
  // A gesture ended by a signal has no exit code; the signal stands in its place.
  const exited = result.status ?? result.signal;
  return {
    lines: [
      ...lines.slice(-TAIL_LINES),
      ...(warnings.length === 0 ? ["warnings: none"] : ["warnings:", ...warnings]),
      `npm run create exited ${exited}; the whole log is ${log}`,
    ],
    detail: "",
    code: 0,
  };
}

// A failure nothing above expected, which only the file system can raise (a temporary directory that
// cannot be made or a log that cannot be read), still ends on a line and never on a stack trace.
let outcome;
try {
  outcome = runCreate(process.argv.slice(2));
} catch (error) {
  outcome = { lines: ["failed: log"], detail: String(error?.message ?? error), code: 1 };
}
const { lines, detail, code } = outcome;
process.stdout.write(`${lines.join("\n")}\n`);
if (detail) {
  process.stderr.write(`${detail}\n`);
}
process.exitCode = code;
