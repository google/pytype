# pylint: skip-file

import os

#- @path ref vname(":module:", "builtins", _, "pytd:os.path", _)
#- @split ref vname("module.split", "builtins", _, "pytd:os.path", _)
os.path.split("/x/y")
