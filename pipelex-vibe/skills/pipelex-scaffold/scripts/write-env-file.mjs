#!/usr/bin/env node
// The env file of /pipelex-scaffold's initializer branch: `.env.example` with the two Pipelex
// lines, `.env` ignored by git, then `.env` copied from the example, given the shell's base URL and
// never the shell's key.
//
// Usage: node write-env-file.mjs <dir>
//
// It prints one line and never a value. The line opens with a verdict on the key, and the stop
// table and the report key on it:
//   <key> base-url=<origin> plane=<plane>
//     <key>     kept     `.env` already carried a key, so it was not touched
//               empty    no key: the user puts their own on `.env`'s PIPELEX_API_KEY= line, which
//                        the shell's PIPELEX_API_KEY never fills
//     <origin>  copied   the shell's PIPELEX_BASE_URL was copied into `.env`
//               file     `.env`'s own line stands: the example's production URL, or the user's
//     <plane>   production when the base URL `.env` resolves to is https://api.pipelex.com, or
//               when it names none; other for any other URL
//   refused: <reason>   no key was written, and <reason> is one of usage, no-directory,
//                       not-a-repository (<dir> is not where the pristine commit leaves it: it
//                       has not run), not-ignored, write-failed (a file in <dir> could not be
//                       written, or, except on Windows, a `.env` without a key could not be closed
//                       to other users, or the file system failed otherwise, its message on stderr;
//                       or the shell's PIPELEX_BASE_URL holds a line break, and nothing was written)
// The exit code is presentation: 0 unless refused.
//
// Why the key the shell exports is never copied: it is whichever key was exported last, often a
// test key or one of another organization, and copied into the project it would outlive the shell,
// bill that organization and escape every rotation. The user puts their own key in `.env`.
//
// Why every value moves through this script and never through the model: a value typed into a
// command, a file-editing tool's parameters or a read of the file lands in the transcript, and a
// key there is a key to rotate. The script reads the variables from its own environment, so only
// their names are ever written down, and the file is read here only to test it. No value is ever
// passed to git, which is spawned with its arguments as an array, no shell and no PIPELEX_* variable
// in its environment.
//
// It is Node rather than shell so that it runs the same on macOS, Linux and Windows, where a
// PowerShell-only machine has no bash. Windows has no owner-only file mode, so there `.env` is left
// to the access rules of the folder it is in, and the mode changes below are skipped.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const PRODUCTION = "https://api.pipelex.com";
const WINDOWS = process.platform === "win32";

// The helpers below are the same in commit-pristine.mjs and write-env-file.mjs, each of which runs
// alone; tests/unit/test_pipelex_scaffold_scripts.py holds the two copies together.

class Refusal extends Error {
  constructor(reason, detail) {
    super(reason);
    this.reason = reason;
    this.detail = detail;
  }
}

function refuse(reason, detail = "") {
  throw new Refusal(reason, detail);
}

// git's environment: this process's without any PIPELEX_* variable, which git never needs. Node builds
// every spawn's environment list from `process.env` when it is handed none, and logs that list on
// stderr under `NODE_DEBUG=child_process`, so a key the shell exports would reach the transcript
// through any git call made without this one. The name is compared in upper case because Windows
// reads a variable's name in any case.
//
// The variables that point git at a repository other than the one it finds from <dir>, which a hook or a
// wrapper can leave set, are dropped as well, as the family's initializer drops them.
const GIT_REDIRECTS = ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX"];
// git's search for the repository around <dir> is not cut short either, by a `GIT_CEILING_DIRECTORIES` or at a
// mount point, where git answers "not a git repository" with a repository above: a repository made there
// would sit inside the user's work tree, which the family never does.
const GIT_ENV = {
  ...Object.fromEntries(
    Object.entries(process.env).filter(
      ([name]) =>
        !name.toUpperCase().startsWith("PIPELEX_") &&
        !GIT_REDIRECTS.includes(name.toUpperCase()) &&
        name.toUpperCase() !== "GIT_CEILING_DIRECTORIES",
    ),
  ),
  GIT_DISCOVERY_ACROSS_FILESYSTEM: "1",
};

// git with its arguments as an array and no shell, its environment GIT_ENV with `extraEnv` over it, and
// `input` on its standard input. The output loses its trailing line breaks, as a shell's command
// substitution would, and `message` joins both streams for a refusal to relay.
function git(args, input = "", extraEnv = {}) {
  const env = { ...GIT_ENV, ...extraEnv };
  const result = spawnSync("git", args, { encoding: "utf8", env, input, maxBuffer: 256 * 1024 * 1024, windowsHide: true });
  const stdout = (result.stdout ?? "").replace(/[\r\n]+$/, "");
  const stderr = (result.stderr ?? "").replace(/[\r\n]+$/, "");
  const message = [stdout, stderr, result.error?.message ?? ""].filter(Boolean).join("\n");
  return { ok: result.status === 0, out: stdout, message };
}

// <dir> where it physically is: a symlinked <dir> lies in the work tree its target lies in, which
// every git command below reads from, so its parent is the target's and not the link's. A relative
// <dir> is read from the working directory alone.
function physicalDirectory(given) {
  try {
    const resolved = fs.realpathSync.native(path.resolve(given));
    return fs.statSync(resolved).isDirectory() ? resolved : null;
  } catch {
    return null;
  }
}

// Whether the repository whose work tree holds <dir>'s parent ignores <dir>, the directory: then a
// repository there is as invisible to it as plain files would be. It is asked from the parent,
// naming <dir> with no trailing slash: git reads a path as a directory when one stands there, and
// a slash, which asking from inside as `.` adds, makes `*` and `<name>/*` match an empty last name,
// so a directory a later pattern re-includes (`!*/`) would read as ignored. The `./` keeps a
// leading `:` from reading as pathspec magic, which `--literal-pathspecs` cannot, since
// check-ignore refuses it. Any answer but a plain yes reads as not ignored, because mistaking a
// tracked directory for an ignored one plants a repository in the user's tracked tree, and git
// reads a directory holding a tracked path as not ignored whatever the patterns say.
function ignoredAround(dir) {
  return git(["-C", path.dirname(dir), "check-ignore", "-q", "--", `./${path.basename(dir)}`]).ok;
}

// git over <dir> as its ignore rules are judged. With no repository of its own, <dir> is judged by
// its own rules, whether the enclosing repository shows its files or not: a line in <dir>'s own
// .gitignore binds that repository too, since a deeper .gitignore decides over those above it, and
// binds a repository the user makes there later, which reads no other, while a rule of the
// enclosing repository's, which may ignore every file of the project, binds that repository alone.
// So the enclosing git directory, `ownRules`, takes <dir> as its work tree, which reads only the
// .gitignore files inside <dir>, and `--no-index` keeps its index, whose paths are not <dir>'s, out
// of `check-ignore`.
function projectGit(dir, ownRules, args, input = "") {
  const where = ownRules ? ["-C", dir, `--git-dir=${ownRules}`, `--work-tree=${dir}`] : ["-C", dir];
  return git([...where, ...args], input);
}

function noIndex(ownRules) {
  return ownRules ? ["--no-index"] : [];
}

// Ignored by a .gitignore the project carries. This machine's global excludes file and the
// repository's info/exclude never travel with a clone, so a teammate's `git add` would take what
// only this machine ignores. The global file is pointed at `/dev/null`, the null device on POSIX,
// which Git for Windows opens as `nul`, and the name goes in and the rule's source comes out
// NUL-terminated, so that no character either holds, a colon of a Windows drive included, is read
// as a separator.
function ignoredByTheProject(dir, ownRules, name) {
  const options = ["-c", "core.excludesFile=/dev/null", "check-ignore", ...noIndex(ownRules)];
  if (!projectGit(dir, ownRules, [...options, "-q", "--", name]).ok) {
    return false;
  }
  const source = projectGit(dir, ownRules, [...options, "-v", "-z", "--stdin"], `${name}\0`).out.split("\0")[0];
  return source === ".gitignore" || source.endsWith("/.gitignore") || source.endsWith("\\.gitignore");
}

// End of the helpers both scripts share.

// The characters a dotenv line's spaces may be, as POSIX's [[:space:]] reads them, so that a line
// ending in a carriage return reads as the same line.
const SPACE = "[ \\t\\n\\v\\f\\r]";

// A file's text, without the byte-order mark an editor may put first, which would otherwise hide
// the name on line 1 from every test below.
function readText(file) {
  try {
    return fs.readFileSync(file, "utf8").replace(/^\uFEFF/, "");
  } catch {
    return "";
  }
}

function append(file, text) {
  try {
    fs.appendFileSync(file, text);
  } catch (error) {
    refuse("write-failed", error.message);
  }
}

// Whether <file> assigns <name>, in any form a dotenv reader accepts.
function assigns(file, name) {
  const assignment = new RegExp(`^${SPACE}*(?:export${SPACE}+)?${name}${SPACE}*=`);
  return readText(file)
    .split("\n")
    .some((line) => assignment.test(line));
}

// Appends to <file> whichever of the two Pipelex lines it lacks. A line it carries is never
// repeated, since a dotenv reader resolves a repeated name to its later line.
function addMissingLines(file) {
  let lines = "";
  if (!assigns(file, "PIPELEX_BASE_URL")) {
    lines += `PIPELEX_BASE_URL=${PRODUCTION}\n`;
  }
  if (!assigns(file, "PIPELEX_API_KEY")) {
    lines += "PIPELEX_API_KEY=\n";
  }
  if (lines) {
    append(file, `\n${lines}`);
  }
}

// The value a dotenv reader resolves for a name in <file>: its last assignment, with an `export `
// prefix, the spaces around `=` and one pair of quotes taken off. It is read into the script and
// never printed.
function resolved(file, name) {
  const assignment = new RegExp(`^${SPACE}*(?:export${SPACE}+)?${name}${SPACE}*=${SPACE}*([\\s\\S]*)$`);
  let value = "";
  for (const line of readText(file).split("\n")) {
    const match = assignment.exec(line);
    if (match) {
      value = match[1];
    }
  }
  return value
    .replace(new RegExp(`${SPACE}+$`), "")
    .replace(/^"([\s\S]*)"$/, "$1")
    .replace(/^'([\s\S]*)'$/, "$1");
}

function writeEnvFile(args) {
  if (args.length !== 1) {
    refuse("usage");
  }
  const dir = physicalDirectory(args[0]);
  if (dir === null) {
    refuse("no-directory");
  }
  // A line break in the shell's base URL would write lines of its own into `.env`, an assignment of
  // any name included, so nothing is written at all. The message names the variable, never its value.
  const baseUrl = process.env.PIPELEX_BASE_URL ?? "";
  if (/[\r\n]/.test(baseUrl)) {
    refuse("write-failed", "PIPELEX_BASE_URL holds a line break, which .env cannot carry in one line; nothing was written.");
  }

  // The pristine commit left <dir> the root of a repository of its own, a repository planted inside
  // another's work tree, which it reports as `nested:`, or a directory inside another repository's
  // work tree that does not ignore it, with no repository of its own (`inside:` or `unversioned:`).
  // A root is judged by its own rules, which for a nested one are <dir>'s .gitignore files, read by
  // the enclosing repository too once the user removes <dir>/.git; a directory with no repository of
  // its own by its own rules as well (see projectGit). A <dir> outside every work tree, or one its
  // enclosing repository ignores, is where the pristine commit makes a repository, so it has not
  // run: git could judge no ignore rule there that a repository of the project's reads, and nothing
  // is written.
  const prefix = git(["-C", dir, "rev-parse", "--show-prefix"]);
  if (!prefix.ok) {
    refuse("not-a-repository");
  }
  let ownRules = "";
  if (prefix.out !== "") {
    if (ignoredAround(dir)) {
      refuse("not-a-repository");
    }
    ownRules = git(["-C", dir, "rev-parse", "--absolute-git-dir"]).out;
  }
  const example = path.join(dir, ".env.example");
  const env = path.join(dir, ".env");
  const gitignore = path.join(dir, ".gitignore");

  // The example carries the two lines every Pipelex project shares; an example the initializer
  // wrote for its own variables keeps them, and gains whichever of the two it lacks.
  if (!fs.existsSync(example)) {
    append(example, `PIPELEX_BASE_URL=${PRODUCTION}\nPIPELEX_API_KEY=\n`);
  } else {
    addMissingLines(example);
  }

  // An initializer's `.env*` rule, which create-next-app writes, hides the example as well, and a
  // hidden example is never reviewed, committed or carried by a clone. With no repository of its own,
  // a rule in an enclosing repository's .gitignore files is that repository's policy for its whole
  // tree, which the project's .gitignore adds to and never lifts, and projectGit does not read it.
  if (projectGit(dir, ownRules, ["check-ignore", ...noIndex(ownRules), "-q", "--", ".env.example"]).ok) {
    append(gitignore, "\n!.env.example\n");
  }

  // `.env` is ignored before a key can reach it, and nothing is written when it cannot be.
  if (!ignoredByTheProject(dir, ownRules, ".env")) {
    append(gitignore, "\n.env\n");
    if (!ignoredByTheProject(dir, ownRules, ".env")) {
      refuse("not-ignored");
    }
  }
  // Read with no index, the project's rules cannot see a `<dir>/.env` the enclosing repository tracks,
  // which no rule ignores: that repository answers for its own index.
  if (ownRules && !git(["-C", dir, "check-ignore", "-q", "--", ".env"]).ok) {
    refuse("not-ignored");
  }

  // An existing `.env` is never overwritten: it may hold a key the user wrote. A new one is
  // readable by its owner alone from the moment it exists, since the user's key goes there next.
  if (!fs.existsSync(env)) {
    try {
      fs.writeFileSync(env, fs.readFileSync(example), { mode: 0o600, flag: "wx" });
    } catch (error) {
      refuse("write-failed", error.message);
    }
  }

  // One test on the file's key decides whether anything is written. A file that carries a key is
  // left as it is, because every dotenv reader resolves a repeated name to its later line, so an
  // append after the user's lines would silently replace them. The base URL cannot carry a test of
  // its own: the example ships its line non-empty. A file without a key gains the lines it lacks, so
  // the report's `PIPELEX_API_KEY=` line is there for the user's own key, and is closed to other
  // users before they write it. A base URL the shell sets is copied, since it is the plane the user
  // declared, and a key is refused by every plane but the one that issued it. The shell's key is
  // never copied. The comment goes out only with the line it introduces.
  let origin = "file";
  let key = "empty";
  if (resolved(env, "PIPELEX_API_KEY") !== "") {
    key = "kept";
  } else {
    addMissingLines(env);
    // A `.env` the initializer wrote was made under the user's umask, readable by others as often
    // as not. Only the group's and others' bits go, so a file its owner made read-only stays so.
    if (!WINDOWS) {
      try {
        fs.chmodSync(env, fs.statSync(env).mode & 0o7700);
      } catch (error) {
        refuse("write-failed", error.message);
      }
    }
    if (baseUrl !== "") {
      append(env, `\n# Copied from the shell environment; a later line overrides an earlier one.\nPIPELEX_BASE_URL=${baseUrl}\n`);
      origin = "copied";
    }
  }

  // The plane the file resolves to, read as a dotenv reader reads it.
  const url = resolved(env, "PIPELEX_BASE_URL").replace(/\/$/, "");
  const plane = url === "" || url === PRODUCTION ? "production" : "other";

  return `${key} base-url=${origin} plane=${plane}`;
}

// A failure nothing above expected, which only the file system can raise, still ends on a verdict
// and never on a stack trace, which the stop table cannot key on. A system error's message names a
// path and a cause, never a value this script holds.
try {
  process.stdout.write(`${writeEnvFile(process.argv.slice(2))}\n`);
} catch (error) {
  const refusal = error instanceof Refusal ? error : new Refusal("write-failed", String(error?.message ?? error));
  process.stdout.write(`refused: ${refusal.reason}\n`);
  if (refusal.detail) {
    process.stderr.write(`${refusal.detail}\n`);
  }
  process.exitCode = 1;
}
