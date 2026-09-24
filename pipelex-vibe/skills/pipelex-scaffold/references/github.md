# A repository on GitHub

Read this when the user asked for the project's repository on GitHub, before running any `gh` command. The skill's guards hold throughout, and one of them is here: creating a repository on GitHub is outward-facing, so **state the exact command and confirm before running it**, in every mode.

## The form

The project is made locally first, on either branch, and the repository is created from it once the pristine commit exists:

```bash
gh repo create <owner>/<name> --private --source <dir> --remote origin
```

The method app is a directory of `pipelex-method-apps`, not a template repository, so `--template` has nothing to point at, and an initializer's project has no template at all. Both therefore take this one form, after their pristine commit.

**A project inside another repository's work tree has neither a repository nor a pristine commit of its own**, on either branch: the method app's `git:` line says so, and so does the pristine-commit script's `inside:` verdict. `gh` refuses it. Create nothing on GitHub: say that the project is part of the enclosing repository, whose own remote carries it, and never follow `gh`'s hint to `git init` the directory, which would plant a repository inside the user's. On `ignored:`, that repository ignores the project, so its remote carries none of it: say that nothing versions the project and that making it a repository is the user's choice, and create nothing on GitHub unless they make one and ask again.

- **Visibility is the user's call.** Ask, and default to `--private`.
- **It pushes nothing.** The user pushes once they have reviewed and committed what came after the pristine commit: the method app's `make create`, or the env example and the `.gitignore` line the initializer branch adds.
- **`gh` must be installed and authenticated**: `gh auth status`. When it is absent or not authenticated, keep the local project, and say the repository can be created later from inside it with `gh repo create --source .`.
