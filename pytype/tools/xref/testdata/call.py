# pylint: skip-file

#- @foo defines/binding FnFoo
#- FnFoo.node/kind function
def foo(x):
  pass

#- @foo ref FnFoo
#- @"foo(123)" ref/call FnFoo
x = foo(123)

#- @bar defines/binding FnBar
#- FnBar.node/kind function
def bar(x):
  #- @foo ref FnFoo
  #- @"foo(123)" ref/call FnFoo
  #- @"foo(123)" childof FnBar
  x = foo(123)
