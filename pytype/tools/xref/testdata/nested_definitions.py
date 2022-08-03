# pylint: skip-file

def f():
  #- @A defines/binding ClassA
  #- ClassA.node/kind class
  class A:
    pass


#- @g defines/binding G
def g():
  #- @B defines/binding ClassB
  #- ClassB.node/kind class
  #- ClassB childof G
  class B:
    pass

  return B


#- @h defines/binding H
def h(base):
  #- @C defines/binding ClassC
  #- ClassC.node/kind class
  #- ClassC.node/kind class
  #- ClassC childof H
  class C(base):
    pass

  #- @D defines/binding ClassD
  #- ClassD.node/kind class
  #- ClassD childof H
  class D(C):
    pass

  return D()


#- @Outer defines/binding Outer
class Outer:
  #- @method defines/binding Method
  #- Method childof Outer
  def method(self):
    #- @NestedClass defines/binding NestedClass
    #- NestedClass childof Method
    class NestedClass:
      #- @fn defines/binding Fn
      #- Fn childof NestedClass
      def fn():
        pass
    #- @nested_fn defines/binding NestedFn
    #- NestedFn childof Method
    def nested_fn():
      pass
