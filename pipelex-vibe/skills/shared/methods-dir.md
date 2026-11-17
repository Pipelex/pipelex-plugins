# An existing `methods/` directory

Read this when a skill is about to place a method directory, `methods/<name>/`, and a `methods/` directory already exists in the working directory, in a directory above it up to the project root, or in a Python project's import package. With no project root, only the working directory's own `methods/` counts. A `methods/` the user made is the clearest sign of where they keep methods, clearer than the project markers the skill's own order follows, unless it holds something else. The skill that sent you here keeps its steps and its guards; this file decides only which `methods/` the new directory goes into.

## Grade each one

List each `methods/` found, reading names only, never a file's content:

- **It holds methods**, the strongest sign: at least one of its subdirectories holds a `.mthds` file or a `method.json`. The user keeps methods here, and the new one goes beside them. Other files beside them, a README or an `__init__.py`, change nothing.
- **It is empty**, or holds only a README, an `__init__.py` and dotfiles such as `.gitkeep`: most likely made for methods. A positive sign, weaker than the first.
- **It is a bundle**: it holds `.mthds` files directly, whatever its subdirectories hold; this grade wins over the first. It is one method whose directory is named `methods`, not a home for several, and a method nested inside it would be sent with it whenever it is validated, saved or run by its folder. Never place a method inside it.
- **It holds something else**: source code, assets, subdirectories with no `.mthds` file and no `method.json`. It is some other kind of "methods", such as a code module, and never the home of a method.

## Choose

- **One positive `methods/`**, outside the Python case below: the new method goes in it, as `<that directory>/<name>/`, in place of the skill's default home, even where the default pointed elsewhere.
- **Several positive ones**: one that holds methods wins over an empty one, except in the Python case below, which wins over this comparison. Two of the same grade are a question: name both and ask which.
- **A packaged Python project, or one owning a codegen harness, whose positive `methods/` is outside the import package**: ask, naming both it and `<package>/methods/`, and say why the skill's default is the package: a wheel ships only what is inside the package, and the call site loads the method from beside itself.
- **No positive one**: take the skill's default home. When that home falls inside a `methods/` that is a bundle or holds something else, write nothing there: say what that directory holds, and ask the user for a path.
- **A name already taken**: a `<name>/` in the chosen `methods/` that exists and is not empty belongs to something else, another method or files of the user's. Never write or copy into it; ask for another name. The one exception is a pull into a directory whose `pipelex-method.json` links it to the method being pulled: that directory is this method's, and the pull goes there, as the skill's own steps say.

## Name it like its neighbours

In a `methods/` that holds methods, spell `<name>` with the separator its method directories already use, `summarize-pdf` beside `extract-invoice` and `summarize_pdf` beside `extract_invoice`, even where the project's language would choose the other. Where the neighbours disagree, keep the skill's own casing.

## Say it

Name the directory chosen and the reason in the line that announces where the method goes, in a few words: *in the existing `methods/`, beside `extract_invoice`*, or *not in `src/methods/`, which holds code*. A question takes the place of that line, and is answered before any file is written.
