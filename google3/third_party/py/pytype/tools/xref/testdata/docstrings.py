# pylint: skip-file

#- @A defines/binding ClassA
#- ClassA.node/kind record
#- ClassA.subkind class
class A:
  #- ClassDoc documents ClassA
  #- ClassDoc.node/kind doc
  #- ClassDoc.text "Class docstring"
  """Class docstring"""
  #- @foo defines/binding FnFoo
  #- FnFoo.node/kind function
  def foo(self, x):
    #- MethodDoc documents FnFoo
    #- MethodDoc.node/kind doc
    #- MethodDoc.text "Method docstring"
    """Method docstring"""
    pass
