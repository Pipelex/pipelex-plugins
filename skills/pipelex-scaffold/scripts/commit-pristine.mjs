#!/usr/bin/env node
// The pristine commit of /pipelex-scaffold's initializer branch: the repository test, a
// .gitignore that keeps the dependency tree out, the staging and the one commit, all held to
// the project directory. Inside another repository's work tree that does not ignore <dir>, and
// in a repository planted there, it writes the .gitignore alone.
//
// Usage: node commit-pristine.mjs <dir> <message>
//
// The first line printed is the verdict, and the stop table keys on it:
//   committed: <sha> <subject>   this script made the commit; the staged paths follow, one per line
//   kept: <sha> <subject>        nothing was left to stage, because the initializer committed the
//                                tree itself (create-next-app does); that commit is the pristine one
//   inside: <root>               <dir> lies in the work tree of the repository at <root>, which does
//                                not ignore it, and is not its root: nothing was initialized, staged
//                                or committed, and the project is new files of that repository, as
//                                the method app's is
//   unversioned: <root>          as inside:, but that repository ignores every file of the project,
//                                though not its directory, and tracks none: no repository versions it
//   nested: <root>               <dir> is the root of a repository that lies in the work tree of the
//                                repository at <root>, which does not ignore it, planted there by the
//                                initializer or the user: nothing was staged or committed in either,
//                                and <dir>/.git is left where it is, since removing it is the user's
//                                choice
//   refused: <reason>            nothing was committed, and <reason> is one of usage, no-git,
//                                no-directory, init-failed, write-failed, stage-failed,
//                                nothing-to-commit, commit-failed; git's own message, if any,
//                                goes to stderr. Any other failure of the file system is
//                                write-failed, with the system's message on stderr
// The exit code is presentation: 0 for committed, kept, inside, unversioned and nested, 1 for
// refused.
//
// It is Node rather than shell so that it runs the same on macOS, Linux and Windows, where a
// PowerShell-only machine has no bash. git is spawned with its arguments as an array and no shell,
// so no path or message is ever parsed by one, and with no PIPELEX_* variable in its environment.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

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
const GIT_ENV = Object.fromEntries(Object.entries(process.env).filter(([name]) => !name.toUpperCase().startsWith("PIPELEX_")));

// git with its arguments as an array and no shell, its environment GIT_ENV, and `input` on its standard
// input. The output loses its trailing line breaks, as a shell's command substitution would, and
// `message` joins both streams for a refusal to relay.
function git(args, input = "") {
  const result = spawnSync("git", args, { encoding: "utf8", env: GIT_ENV, input, maxBuffer: 256 * 1024 * 1024, windowsHide: true });
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

function append(file, text) {
  try {
    fs.appendFileSync(file, text);
  } catch (error) {
    refuse("write-failed", error.message);
  }
}

// Any failure to read the entry, not only its absence, reads as no directory, as a shell's `[ -d ]`.
function isDirectory(file) {
  try {
    return fs.statSync(file).isDirectory();
  } catch {
    return false;
  }
}

function commitPristine(args) {
  if (args.length !== 2 || args[1] === "") {
    refuse("usage", "usage: node commit-pristine.mjs <dir> <message>");
  }
  if (!git(["--version"]).ok) {
    refuse("no-git");
  }
  const dir = physicalDirectory(args[0]);
  if (dir === null) {
    refuse("no-directory", `no directory at ${args[0]}`);
  }
  const message = args[1];

  // An initializer that wrote nothing leaves nothing to commit, and a commit of the .gitignore
  // below alone would read as a scaffold. A lone .git is the user's repository, not a scaffold. A
  // directory that cannot be listed shows nothing to commit either, as an `ls` that fails does.
  let entries;
  try {
    entries = fs.readdirSync(dir);
  } catch (error) {
    refuse("nothing-to-commit", error.message);
  }
  if (entries.every((entry) => entry === ".git")) {
    refuse("nothing-to-commit");
  }

  // The repository test, never inferred from which initializer ran: `uv init` and create-next-app
  // initialize a repository only when no enclosing one exists, so the list of initializers that
  // `git init` is not a substitute. `--show-prefix` prints nothing at a repository's root, which
  // needs no path comparison and so survives symlinks and letter case. The outcomes:
  //   - outside every work tree, and where the enclosing repository ignores <dir> (an ignored tmp/, a
  //     dotfiles repository ignoring `*`), <dir> becomes a repository of its own, and the commit
  //     follows: under an ignored path a repository makes the enclosing one fail no `git add -A` and
  //     shows it nothing, while without one the project has no baseline for its first diff and the
  //     enclosing repository's `git clean -fdx` deletes it;
  //   - at a repository's root, the one the initializer made or the user's lone .git, the commit
  //     lands there (the skill asks first when the repository was the user's), unless that root lies
  //     in another repository's work tree that does not ignore it, which the last case below covers;
  //   - inside another repository's work tree that does not ignore <dir>, <dir> gets no repository
  //     and no commit, as the method app's initializer gives it none: a repository planted there is
  //     one the enclosing repository sees as embedded, and `git -C` sets git's working directory
  //     without scoping anything, so a staging there would sweep the user's worktree into this
  //     commit. What counts is the directory, not its files: under `*` then `!*/`, or `<name>/*`,
  //     the directory is visible though every file in it is ignored, and a repository there would
  //     still show. The project is new files of that repository, left for the user to review and
  //     commit, or, when it shows none of them, under no version control; its index and HEAD are
  //     never touched, and only the .gitignore below is written, so that no `git add` takes the
  //     dependency tree or a `.env`, the enclosing repository's or one the user makes there later.
  // A repository root can lie inside another work tree too, when an initializer ran `git init`
  // there anyway (create-astro tests only for a .git of <dir>'s own) or the user made one. The empty
  // prefix reads as a root like any other, so the parent directory is asked as well, and a root the
  // enclosing repository does not ignore gets no commit, for the reason above: once it has one, the
  // enclosing repository stages it as a pointer to that commit, which no clone can fetch, and stops
  // carrying the project's files. It prints `nested:`, its .gitignore is written by its own rules,
  // which are <dir>'s .gitignore files that the enclosing repository reads as well once <dir>/.git
  // is gone, and neither its index nor its .git is touched: removing that is the user's choice,
  // never this script's.
  const initialize = () => {
    const init = git(["-C", dir, "init", "-q", "-b", "main"]);
    if (!init.ok) {
      refuse("init-failed", init.message);
    }
  };
  let enclosing = "";
  let nested = "";
  const prefix = git(["-C", dir, "rev-parse", "--show-prefix"]);
  if (prefix.ok) {
    if (prefix.out === "") {
      const around = git(["-C", path.dirname(dir), "rev-parse", "--show-toplevel"]);
      if (around.ok && !ignoredAround(dir)) {
        nested = around.out;
      }
    } else if (ignoredAround(dir)) {
      initialize();
    } else {
      enclosing = git(["-C", dir, "rev-parse", "--show-toplevel"]).out;
    }
  } else {
    initialize();
  }

  // With no repository of its own, the project is judged by its own rules, whichever verdict it gets
  // (see projectGit above).
  const ownRules = enclosing ? git(["-C", dir, "rev-parse", "--absolute-git-dir"]).out : "";

  // An ignore rule reaches only untracked paths, so a `.env` or a node_modules/ an initializer had
  // already staged would ride into the commit past the lines written below. Unstage what the index
  // holds of either and HEAD does not, before those lines are read: a path the user committed is
  // theirs, and stays tracked. `-f` because a file rewritten since it was staged, as `npm install`
  // rewrites node_modules/.package-lock.json, is otherwise refused; `--cached` leaves the file itself.
  // An enclosing repository's index is the user's, and is left alone, and so is a nested one's.
  if (!enclosing && !nested) {
    for (const stagedEarly of [".env", "node_modules"]) {
      if (git(["-C", dir, "ls-files", "--cached", "--", stagedEarly]).out === "") {
        continue;
      }
      if (git(["-C", dir, "rev-parse", "-q", "--verify", `HEAD:${stagedEarly}`]).ok) {
        continue;
      }
      const unstaged = git(["-C", dir, "rm", "-r", "-q", "-f", "--cached", "--", stagedEarly]);
      if (!unstaged.ok) {
        refuse("stage-failed", unstaged.message);
      }
    }
  }

  // `npm init -y` and `tsc --init` write no .gitignore, so the staging would commit the whole
  // dependency tree into the commit that is meant to be a readable baseline, and `uv init` writes
  // none inside an enclosing repository. A Python project gets Python's lines and any other gets
  // Node's. An initializer's own .gitignore is kept, and gains only what it does not ignore of what
  // is there: a node_modules/, whatever the language, and a `.env` the initializer wrote, so that it
  // never reaches the commit.
  const gitignore = path.join(dir, ".gitignore");
  if (!fs.existsSync(gitignore)) {
    const python = fs.existsSync(path.join(dir, "pyproject.toml"));
    append(gitignore, python ? "__pycache__/\n*.egg-info/\nbuild/\ndist/\n.venv/\n.env\n" : "node_modules/\ndist/\n.env\n");
  }
  if (isDirectory(path.join(dir, "node_modules")) && !ignoredByTheProject(dir, ownRules, "node_modules")) {
    append(gitignore, "\nnode_modules/\n");
  }
  if (fs.existsSync(path.join(dir, ".env")) && !ignoredByTheProject(dir, ownRules, ".env")) {
    append(gitignore, "\n.env\n");
  }

  if (nested) {
    return [`nested: ${nested}`];
  }
  if (enclosing) {
    // Asked once the .gitignore is written, since the enclosing repository shows that file too unless
    // it ignores it. An empty status alone does not say that it shows none of the project: a project
    // it tracks, deleted and then written again as it was, shows nothing either, so its index must
    // hold nothing under <dir> as well. `--no-optional-locks` keeps the status from rewriting the
    // user's index, and any failure reads as `inside:`.
    const shown = git(["--no-optional-locks", "-C", dir, "status", "--porcelain", "--untracked-files=all", "--", "."]);
    const tracked = shown.ok && shown.out === "" ? git(["-C", dir, "ls-files", "--", "."]) : null;
    const unversioned = tracked !== null && tracked.ok && tracked.out === "";
    return [`${unversioned ? "unversioned" : "inside"}: ${enclosing}`];
  }

  // The pathspec is on both commands. `add -A -- .` bounds what is staged, and a commit without
  // one would commit the whole index, anything the user had staged included.
  const added = git(["-C", dir, "add", "-A", "--", "."]);
  if (!added.ok) {
    refuse("stage-failed", added.message);
  }
  const staged = git(["-C", dir, "diff", "--cached", "--name-only", "--", "."]).out;

  if (staged === "") {
    // An initializer that commits as well as `git init`s has already made this commit. It is
    // taken as the pristine one, and a second, empty commit is never forced on top of it.
    if (!git(["-C", dir, "rev-parse", "-q", "--verify", "HEAD"]).ok) {
      refuse("nothing-to-commit");
    }
    return [`kept: ${git(["-C", dir, "log", "-1", "--format=%h %s"]).out}`];
  }

  const committed = git(["-C", dir, "commit", "-q", "-m", message, "--", "."]);
  if (!committed.ok) {
    refuse("commit-failed", committed.message);
  }
  return [`committed: ${git(["-C", dir, "log", "-1", "--format=%h %s"]).out}`, staged];
}

// A failure nothing above expected, which only the file system can raise, still ends on a verdict
// and never on a stack trace, which the stop table cannot key on.
try {
  process.stdout.write(`${commitPristine(process.argv.slice(2)).join("\n")}\n`);
} catch (error) {
  const refusal = error instanceof Refusal ? error : new Refusal("write-failed", String(error?.message ?? error));
  process.stdout.write(`refused: ${refusal.reason}\n`);
  if (refusal.detail) {
    process.stderr.write(`${refusal.detail}\n`);
  }
  process.exitCode = 1;
}
