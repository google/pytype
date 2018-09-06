# pylint: skip-file

#- @test defines/binding FnTest
#- @x defines/binding ArgX
#- FnTest.node/kind function
#- FnTest param.0 ArgX
def test(x):
  #- @x ref ArgX
  return x

#- @y defines/binding VarY
#- @test ref FnTest
#- @test ref/call FnTest
#- VarY.node/kind variable
y = test(2)
