# pylint: skip-file

a = "hello"
#- @split ref vname("__builtin__/module.str.split", _, _, _, _)
b = a.split('.')
#- @reverse ref vname("__builtin__/module.list.reverse", _, _, _, _)
c = b.reverse()
