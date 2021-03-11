# pylint: skip-file

def f():
  #- @A defines/binding ClassA
  #- ClassA.node/kind class
  class A:
    pass


def g():
  #- @B defines/binding ClassB
  #- ClassB.node/kind class
  class B:
    pass

  return B


def h(base):
  #- @C defines/binding ClassC
  #- ClassC.node/kind class
  class C(base):
    pass

  #- @D defines/binding ClassD
  #- ClassD.node/kind class
  class D(C):
    pass

  return D()
