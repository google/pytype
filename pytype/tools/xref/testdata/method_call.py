# pylint: skip-file

#- @A defines/binding ClassA
#- ClassA.node/kind class
class A(object):
  #- @foo defines/binding FnFoo
  #- @self defines/binding ArgSelf
  #- @x defines/binding ArgX
  #- FnFoo.node/kind function
  #- FnFoo param.0 ArgSelf
  #- FnFoo param.1 ArgX
  def foo(self, x):
    pass

#- @foo ref FnFoo
#- @foo ref/call FnFoo
A().foo(10)
