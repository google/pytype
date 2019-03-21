# pylint: skip-file

#- @test defines/binding FnTest
#- @x defines/binding ArgX
#- FnTest.node/kind function
#- FnTest param.0 ArgX
def test(x):
  #- @x ref ArgX
  return x


#- @foo defines/binding FnFoo
#- @x defines/binding ArgFooX
#- FnFoo.node/kind function
#- FnFoo param.0 ArgFooX
def foo(x):
  #- @test ref/call FnTest
  #- @test childof FnFoo
  return test(x)


#- @y defines/binding VarY
#- @test ref FnTest
#- @test ref/call FnTest
#- VarY.node/kind variable
y = test(2)


# We don't index this, but it shouldn't crash.
z = (lambda x: x)(1)


#- @bar defines/binding VarBar
bar = lambda x: x
# We don't generate ref/call here.
#- @bar ref VarBar
bar(1)
