# pylint: skip-file

#- @A defines/binding ClassA
#- ClassA.node/kind class
class A(object):
  #- @B defines/binding ClassB
  #- ClassB.node/kind class
  class B(object):
    #- @foo defines/binding FnFoo
    #- @self defines/binding ArgBSelf
    #- FnFoo.node/kind function
    #- FnFoo param.0 ArgBSelf
    def foo(self):
      pass

  #- @bar defines/binding FnBar
  #- @self defines/binding ArgASelf
  #- FnBar.node/kind function
  #- FnBar param.0 ArgASelf
  def bar(self):
    #- @B ref ClassB
    return self.B()

#- @A ref ClassA
#- @B ref ClassB
#- @foo ref FnFoo
A.B().foo()

#- @A ref ClassA
#- @bar ref FnBar
#- @foo ref FnFoo
A().bar().foo()
