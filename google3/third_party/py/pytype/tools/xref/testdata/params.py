# pylint: skip-file

#- @foo defines/binding FnFoo
#- @x defines/binding ArgX
#- @y defines/binding ArgY
#- @z defines/binding ArgZ
#- @a defines/binding ArgA
#- @b defines/binding ArgB
#- FnFoo.node/kind function
#- FnFoo param.0 ArgX
#- FnFoo param.1 ArgY
#- FnFoo param.2 ArgZ
#- FnFoo param.3 ArgA
#- FnFoo param.4 ArgB
def foo(x, y, /, z, *, a, b):
  #- @x ref ArgX
  return x


#- @bar defines/binding FnBar
#- @p defines/binding ArgP
#- @varargs defines/binding ArgVarargs
#- @q defines/binding ArgQ
#- @kwargs defines/binding ArgKwargs
#- FnBar param.0 ArgP
#- FnBar param.1 ArgVarargs
#- FnBar param.2 ArgQ
#- FnBar param.3 ArgKwargs
def bar(p, *varargs, q, **kwargs):
  #- @varargs ref ArgVarargs
  #- @kwargs ref ArgKwargs
  return varargs, kwargs
