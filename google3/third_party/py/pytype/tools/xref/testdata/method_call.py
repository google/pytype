# pylint: skip-file

#- @A defines/binding ClassA
#- ClassA.node/kind record
#- ClassA.subkind class
class A:
  #- @foo defines/binding FnFoo
  #- @self defines/binding ArgSelf
  #- @x defines/binding ArgX
  #- FnFoo.node/kind function
  #- FnFoo param.0 ArgSelf
  #- FnFoo param.1 ArgX
  def foo(self, x):
    pass


#- @bar defines/binding FnBar
#- FnBar.node/kind function
def bar():
  #- @A ref ClassA
  #- @"A()" ref/call ClassA
  #- @"A()" childof FnBar
  #- @foo ref FnFoo
  #- @"foo(10)" ref/call FnFoo
  #- @"foo(10)" childof FnBar
  A().foo(10)
