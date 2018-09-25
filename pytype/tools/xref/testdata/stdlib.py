# pylint: skip-file

import os

#- @path ref vname("module.path", _, _, "pytd:os", _)
#- @split ref vname("module.split", _, _, "pytd:os.path", _)
os.path.split("/x/y")
