# pylint: skip-file

#- @A defines/binding ClassA
#- @object ref vname("__builtin__/module.object", _, _, _, _)
#- ClassA.node/kind class
class A(object):
  pass


#- @B defines/binding ClassB
#- @A ref ClassA
#- ClassB.node/kind class
class B(A):
  pass


#- @Foo defines/binding ClassFoo
#- @A ref ClassA
#- @B ref ClassB
#- ClassFoo.node/kind class
class Foo(A, B):
  pass
