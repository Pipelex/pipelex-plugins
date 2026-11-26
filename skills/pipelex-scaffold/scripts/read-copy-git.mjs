#!/usr/bin/env node
// Where a copy of the method app that `npm run create` has not run in stands in git, read before
// anything runs in it, and its own repository when it needs one: /pipelex-scaffold's
// references/uncreated-copy.md runs it.
//
// Usage: node read-copy-git.mjs <dir>
//
// It prints one line, the verdict, and the reference keys on its first word:
//   pristine: <commit> <subject>   <dir> is its repository's root, and that repository holds the
//                                  pristine commit the family's initializer, or the reference by
//                                  hand, made: `Start from Pipelex/pipelex-sdk/method-apps/webapp-js
//                                  …`, or `Start from Pipelex/pipelex-method-apps/webapp-js …` on a
//                                  copy made before the template moved into pipelex-sdk
//   no-commit: <dir>               <dir> is its own repository's root, which has no commit yet; when
//                                  this script made that repository, on `main`, the line says so
//   history: <dir>                 <dir> is its own repository's root, with commits and no pristine one
//   inside: <root>                 <dir> sits untracked in the work tree of <root>, which does not
//                                  ignore it, so it gets no repository and no commit
//   refused: <reason>              nothing was initialized, and <reason> is one of usage,
//                                  no-directory, no-git, template-checkout (the repository holding
//                                  <dir> is the template's own, pipelex-sdk or pipelex-method-apps,
//                                  by its origin), tracked <root> (<root> already tracks <dir>),
//                                  git-failed (git could not read <dir> for a reason other than its
//                                  being outside every repository, such as a repository it calls
//                                  dubious or a directory inside a `.git`) or init-failed (git's
//                                  message on stderr for both)
// The exit code is presentation: 0 unless refused.
//
// The order is the reading's correctness. The history is read first, since a user standing in a copy
// seldom says who made it. Then the origin, before anything is initialized, so that a template's own
// checkout stops whether <dir> is its repository's root or a directory inside it: initializing first
// would hide the family's origin behind a new repository with none. Only then is a repository made,
// and only for a copy outside every repository, or one the enclosing repository ignores, as the
// family's initializer gives it one; a copy inside a work tree that does not ignore it gets none,
// because a repository planted there is one the enclosing repository shows as embedded.
//
// It is Node rather than shell so that it runs the same on macOS, Linux and Windows, where a
// PowerShell-only machine has no bash.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

// A pristine commit's line as `git log --format='%h %s'` prints it.
const PRISTINE = /^[0-9a-f]+ Start from Pipelex\/(pipelex-sdk\/method-apps|pipelex-method-apps)\/webapp-js /;
// The template's own repositories, named exactly, as the initializer's `TEMPLATE_ORIGINS` reads them:
// in any letter case, with or without `.git` or a trailing slash, over https or ssh. A fork under
// another owner, a sibling whose name only begins the same, or the repository's wiki is not one.
const TEMPLATE_ORIGIN = /[/:]pipelex\/(pipelex-sdk|pipelex-method-apps)$/;

class Refusal extends Error {
  constructor(reason, detail = "") {
    super(reason);
    this.reason = reason;
    this.detail = detail;
  }
}

function refuse(reason, detail = "") {
  throw new Refusal(reason, detail);
}

// git's environment: this process's without any PIPELEX_* variable, which git never needs and which
// Node's debug log would otherwise print with the spawn, and without the variables that point git at a
// repository other than the one it finds from <dir>, which a hook or a wrapper can leave set, as the
// family's initializer drops them. Windows reads a variable's name in any case.
const GIT_REDIRECTS = ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX"];
const GIT_ENV = Object.fromEntries(
  Object.entries(process.env).filter(([name]) => !name.toUpperCase().startsWith("PIPELEX_") && !GIT_REDIRECTS.includes(name.toUpperCase())),
);
// git's own message for a directory outside every repository, read in the C locale so that it is the same words
// in every language git speaks.
const OUTSIDE = /not a git repository/i;

// git with its arguments as an array and no shell. The output loses its trailing line breaks, as a
// shell's command substitution would, and `message` joins both streams for a refusal to relay.
function git(args, extraEnv = {}) {
  const env = { ...GIT_ENV, ...extraEnv };
  const result = spawnSync("git", args, { encoding: "utf8", env, maxBuffer: 256 * 1024 * 1024, windowsHide: true });
  const stdout = (result.stdout ?? "").replace(/[\r\n]+$/, "");
  const stderr = (result.stderr ?? "").replace(/[\r\n]+$/, "");
  const message = [stdout, stderr, result.error?.message ?? ""].filter(Boolean).join("\n");
  return { ok: result.status === 0, out: stdout, message };
}

// <dir> where it physically is, symlinks resolved, or null when no directory stands there.
function physicalDirectory(given) {
  try {
    const resolved = fs.realpathSync.native(path.resolve(given));
    return fs.statSync(resolved).isDirectory() ? resolved : null;
  } catch {
    return null;
  }
}

// Whether the repository whose work tree holds <dir>'s parent ignores <dir>, the directory. It is
// asked from the parent, naming <dir> with no trailing slash, which would make `*` match a directory
// a later `!*/` lets through; the `./` keeps a leading `:` from reading as pathspec magic.
function ignoredAround(dir) {
  return git(["-C", path.dirname(dir), "check-ignore", "-q", "--", `./${path.basename(dir)}`]).ok;
}

function initialize(dir) {
  const made = git(["-C", dir, "init", "-q", "-b", "main"]);
  if (!made.ok) {
    refuse("init-failed", made.message);
  }
  return `no-commit: ${dir} (a repository made now on main)`;
}

function readCopyGit(args) {
  if (args.length !== 1 || args[0] === "") {
    refuse("usage", "usage: node read-copy-git.mjs <dir>");
  }
  if (!git(["--version"]).ok) {
    refuse("no-git");
  }
  const dir = physicalDirectory(args[0]);
  if (dir === null) {
    refuse("no-directory", `no directory at ${args[0]}`);
  }

  // `--show-prefix` prints nothing at a repository's root, which needs no path comparison and so
  // survives symlinks and letter case, and fails outside every repository. It fails for other reasons
  // too, a repository of another owner's that git calls dubious, a directory inside a `.git`, and only
  // "not a git repository" means outside every one: anything else is refused with git's message, since
  // a repository initialized there would sit inside one git could not read.
  const prefix = git(["-C", dir, "rev-parse", "--show-prefix"], { LC_ALL: "C", LANGUAGE: "C" });
  if (!prefix.ok && !OUTSIDE.test(prefix.message)) {
    refuse("git-failed", prefix.message);
  }
  // Inside a `.git` directory git answers with an empty prefix, as at a work tree's root.
  if (prefix.ok && git(["-C", dir, "rev-parse", "--is-inside-git-dir"]).out === "true") {
    refuse("git-failed", `${dir} is inside a repository's .git directory`);
  }
  const atRoot = prefix.ok && prefix.out === "";
  if (atRoot) {
    const pristine = git(["-C", dir, "log", "--format=%h %s"])
      .out.split(/\r?\n/)
      .find((line) => PRISTINE.test(line));
    if (pristine !== undefined) {
      return `pristine: ${pristine}`;
    }
  }

  const origin = git(["-C", dir, "remote", "get-url", "origin"]);
  if (origin.ok && TEMPLATE_ORIGIN.test(origin.out.trim().toLowerCase().replace(/\/$/, "").replace(/\.git$/, ""))) {
    refuse("template-checkout", "this is a template's own checkout, not a copy of it");
  }

  if (!prefix.ok) {
    return initialize(dir);
  }
  if (atRoot) {
    return git(["-C", dir, "rev-parse", "-q", "--verify", "HEAD"]).ok ? `history: ${dir}` : `no-commit: ${dir}`;
  }
  const root = git(["-C", dir, "rev-parse", "--show-toplevel"]).out;
  if (git(["-C", dir, "ls-files", "--", "."]).out !== "") {
    refuse(`tracked ${root}`, "an enclosing repository already tracks this directory");
  }
  if (ignoredAround(dir)) {
    return initialize(dir);
  }
  return `inside: ${root}`;
}

// A failure nothing above expected still ends on a verdict and never on a stack trace, which the
// reference cannot key on.
try {
  process.stdout.write(`${readCopyGit(process.argv.slice(2))}\n`);
} catch (error) {
  const refusal = error instanceof Refusal ? error : new Refusal("init-failed", String(error?.message ?? error));
  process.stdout.write(`refused: ${refusal.reason}\n`);
  if (refusal.detail) {
    process.stderr.write(`${refusal.detail}\n`);
  }
  process.exitCode = 1;
}
