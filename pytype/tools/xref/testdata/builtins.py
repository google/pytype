# pylint: skip-file

a = "hello"
#- @split ref vname("module.str.split", _, _, "pytd:builtins", _)
b: list[str] = a.split('.')
#- @reverse ref vname("module.list.reverse", _, _, "pytd:builtins", _)
c: list[str] = b.reverse()
