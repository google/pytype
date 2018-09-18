# pylint: skip-file

#- @A defines/binding ClassA
#- ClassA.node/kind class
class A(object):
  #- @foo defines/binding FnFoo
  #- FnFoo.node/kind function
  def foo(self, x):
    return 10

  @staticmethod
  #- @bar defines/binding FnBar
  #- FnBar.node/kind function
  def bar():
    return 42


class B(A):
  pass


class C(B):
  #- @baz defines/binding FnBaz
  #- @self defines/binding ArgSelf
  #- FnBaz.node/kind function
  #- FnBaz param.0 ArgSelf
  def baz(self):
    #- @self ref ArgSelf
    #- @foo ref/call FnFoo
    return self.foo(10)


#- @foo ref FnFoo
#- @foo ref/call FnFoo
x = B().foo(10)
#- @bar ref FnBar
#- @bar ref/call FnBar
y = C.bar()
