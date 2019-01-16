# pylint: skip-file

#- @A defines/binding ClassA
#- ClassA.node/kind class
class A(object):
  #- @__init__ defines/binding FnInit
  #- @self defines/binding ArgSelf
  #- FnInit.node/kind function
  #- FnInit param.0 ArgSelf
  def __init__(self):
    #- @self ref ArgSelf
    #- @foo defines/binding AttrFoo
    self.foo = []

  def f(self, x):
    #- @foo ref AttrFoo
    self.foo[x] = 10


## The attr can be initialised somewhere other than __init__

#- @B defines/binding ClassB
#- ClassB.node/kind class
class B(object):
  def f(self, x):
    #- @bar ref AttrBar
    self.bar[x]

  #- @init_bar defines/binding FnInitBar
  #- @self defines/binding ArgBSelf
  #- FnInitBar.node/kind function
  #- FnInitBar param.0 ArgBSelf
  def init_bar(self):
    #- @self ref ArgBSelf
    #- @bar defines/binding AttrBar
    self.bar = []
    return self

  ## Attribute accesses could span several lines
  def baz(self):
    (self.
     #- @init_bar ref FnInitBar
     init_bar()
     #- @bar ref AttrBar
     .bar)
