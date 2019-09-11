# pylint: skip-file

#- @a defines/binding VarA
#- @b defines/binding VarB
#- @c defines/binding VarC
a = b = c = 1

# TODO(b/137314416): @a ref VarA does not work
#- @x defines/binding VarX
x = (a +
#- @b ref VarB
     b +
#- @c ref VarC
     c)

#- @y defines/binding VarY
#- @a ref VarA
y = list(a,
#- @b ref VarB
         b,
#- @c ref VarC
         c)

#- @x ref VarX
#- @y ref VarY
#- @z defines/binding VarZ
z = (x, y)

#- @z ref VarZ
z[1] = (1,
        2)

#- @foo defines/binding Foo
#- Foo.node/kind function
def foo(x,
        y,
        z):
  pass
