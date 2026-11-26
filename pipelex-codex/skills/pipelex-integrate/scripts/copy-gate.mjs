#!/usr/bin/env node
// copy-gate.mjs — copies one of /pipelex-integrate's offline gates into the project, byte for byte.
//
// Run from the project root, through node and by this file's absolute path:
//
//   node "<skill-dir>/scripts/copy-gate.mjs" codegen-check.mjs
//   node "<skill-dir>/scripts/copy-gate.mjs" codegen_check.py
//
// It writes `scripts/<name>` under the working directory, creating `scripts/` when it is missing. It
// replaces the skill's `cp` and `mkdir -p` so that the copy runs in every shell (bash, zsh, PowerShell 5.1
// and 7), and it keeps the copy mechanical: the model never reads the gate and writes it back.
//
// A file already at that path is replaced only when it carries the marker line every shipped gate opens
// with, or when the command repeats with `--replace` after the user agreed: the project may keep a gate
// of its own under the same name. The verdict is the last line printed:
//   copied <name> to scripts/<name>        exit 0
//   unchanged: scripts/<name> ...          exit 0, the file already matches the reference
//   refused: scripts/<name> ...            exit 1, the file is the project's own
//   failed: ...                            exit 2, an unknown name or a file system error

import { copyFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const GATES = new Set(["codegen-check.mjs", "codegen_check.py"]);
const MARKER = "Copied verbatim into a project by /pipelex-integrate";

function main(argv) {
  const replace = argv.includes("--replace");
  const names = argv.filter((arg) => arg !== "--replace");
  if (names.length !== 1 || !GATES.has(names[0])) {
    console.log(`failed: name one gate to copy, ${[...GATES].join(" or ")}, optionally with --replace`);
    return 2;
  }
  const name = names[0];
  const source = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "references", name);
  const relative = `scripts/${name}`;
  const target = path.join(process.cwd(), "scripts", name);
  try {
    const reference = readFileSync(source);
    if (existsSync(target)) {
      const current = readFileSync(target);
      if (current.equals(reference)) {
        console.log(`unchanged: ${relative} already matches the reference`);
        return 0;
      }
      if (!replace && !current.toString("utf8").includes(MARKER)) {
        console.log(
          `refused: ${relative} is the project's own, since it lacks the line "${MARKER}"; ` +
            "ask the user before replacing it, and only on their yes run this command again with --replace",
        );
        return 1;
      }
    }
    mkdirSync(path.dirname(target), { recursive: true });
    copyFileSync(source, target);
  } catch (error) {
    console.log(`failed: ${relative}: ${error instanceof Error ? error.message : String(error)}`);
    return 2;
  }
  console.log(`copied ${name} to ${relative}`);
  return 0;
}

process.exitCode = main(process.argv.slice(2));
