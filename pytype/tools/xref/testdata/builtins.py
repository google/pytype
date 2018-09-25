# pylint: skip-file

a = "hello"
#- @split ref vname("module.str.split", _, _, "pytd:__builtin__", _)
b = a.split('.')
#- @reverse ref vname("module.list.reverse", _, _, "pytd:__builtin__", _)
c = b.reverse()
