# pylint: skip-file

a = "hello"
#- @split ref vname("module.str.split", _, _, "pytd:builtins", _)
b = a.split('.')
#- @reverse ref vname("module.list.reverse", _, _, "pytd:builtins", _)
c = b.reverse()
