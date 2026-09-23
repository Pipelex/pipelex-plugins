# Choosing the Python a `PipeFunc` bundle sends

Read this when the bundle being saved holds a `PipeFunc`, before choosing any `.py` file for `python`. The skill's guards on `python` hold throughout: it replaces the stored set, it is never swept from the directory, and a file whose place in the set is unclear is the user's to decide.

Send only the files that implement this bundle's `PipeFunc` steps.

**A `function_name` does not name a file.** It is a key in the runtime's flat, process-wide function registry — by default the decorated function's own name (`capitalize`), and any other string the author passed to `@pipe_func(name=…)` — so nothing in the bundle says which module defines it, and a dotted name is a registry key too, never an import path.

Read the directory's `.py` files and send every one that a registered function needs: the file defining it, and the bundle files it imports from. The catalog stores them as flat, importable module names beside each other, so a helper left out of the set is a helper the runner cannot import — and since `python` replaces rather than merges, leaving it out also deletes the copy the catalog held.
