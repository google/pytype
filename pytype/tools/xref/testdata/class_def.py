# pylint: skip-file

#- @A defines/binding ClassA
#- @object ref vname("module.object", _, _, "pytd:__builtin__", _)
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


#- @Bar defines/binding ClassBar
#- ClassBar.node/kind class
class Bar(
#- @A ref ClassA
    A,
#- @B ref ClassB
    B
):
  pass
