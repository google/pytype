# pylint: skip-file

import collections


#- @A defines/binding ClassA
#- ClassA.node/kind class
class A:
  pass


#- @B defines/binding ClassB
#- ClassB.node/kind class
class B:
  pass


#- @D defines/binding ClassD
#- @A ref ClassA
#- ClassD.node/kind class
class D(A):
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
    B):
  pass


#- @Baz defines/binding ClassBaz
#- ClassBaz.node/kind class
class Baz(collections.namedtuple('Foo', ['bar', 'baz', 'quux'])):
  pass


#- @Quux defines/binding ClassQuux
#- ClassQuux.node/kind class
class Quux:
  pass


def f():
  global Quux
