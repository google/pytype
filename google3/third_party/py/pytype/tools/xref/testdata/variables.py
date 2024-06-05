# pylint: skip-file

class A():
  #- @foo defines/binding FnFoo
  def foo(self):
    pass

# Follow a type through a chain of variables

#- @x defines/binding VarX
#- VarX.node/kind variable
x = A()
#- @y defines/binding VarY
#- VarY.node/kind variable
y = x
#- @z defines/binding VarZ
#- VarZ.node/kind variable
z = y
#- @foo ref FnFoo
z.foo()
