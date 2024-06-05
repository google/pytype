# pylint: skip-file

#- @foo defines/binding VarFoo
#- VarFoo.node/kind variable
foo = 5

def fun():
  #- @bar defines/binding VarBar
  #- VarBar.node/kind variable
  bar = 10

  def nested():
    #- @baz defines/binding VarBaz
    #- VarBaz.node/kind variable
    baz = 10
    #- @foo ref VarFoo
    foo
    #- @bar ref VarBar
    bar
    #- @baz ref VarBaz
    baz
    # Two references to the same variable should both get linked correctly.
    #- @foo ref VarFoo
    foo
    #- @bar ref VarBar
    bar
    #- @baz ref VarBaz
    baz
