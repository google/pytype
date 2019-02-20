# pylint: skip-file

import os

#- @path ref vname("module.path", "builtins", _, "pytd:os", _)
#- @split ref vname("module.split", "builtins", _, "pytd:os.path", _)
os.path.split("/x/y")
