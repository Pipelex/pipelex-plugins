# Choosing the Python a `PipeFunc` bundle sends

Read this when the bundle being saved holds a `PipeFunc`, before choosing any `.py` file for `python`. The skill's guards on `python` hold throughout: it replaces the stored set, it is never swept from the directory, and a file whose place in the set is unclear is the user's to decide.

Send only the files that implement this bundle's `PipeFunc` steps.

**A `function_name` names its module.** It is the function's Python import path from the root of the method's folder, split at its last dot: `text_utils.capitalize` names the function `capitalize` of `text_utils.py`, and `funcs.text_utils.capitalize` the one of `funcs/text_utils.py`, each dot of the module path read as a `/`. A name with no dot is no import path at all but the retired function registry's key, which the runtime refuses: say so, and leave its rewrite to the edit skill.

Send the module each step's `function_name` names, and every file of the directory it imports from, read from its `import` lines. **The catalog stores no `.py` file in a subdirectory yet**: it keeps each one by its bare name at the method's root and refuses any other, so a method saved with its Python keeps its modules beside its root `.mthds` file, where `text_utils.capitalize` finds `text_utils.py`. A module or package in a subdirectory cannot be saved: say so, and leave the move, which changes the `function_name`, to the edit skill. A helper left out of the set is a helper the runner cannot import, and since `python` replaces rather than merges, leaving it out also deletes the copy the catalog held.
