# Abstract values

<!--*
freshness: { owner: 'mdemello' reviewed: '2020-07-09' }
*-->

<!--ts-->
   * [Abstract values](#abstract-values)
      * [Objects, Types and Values](#objects-types-and-values)
      * [Abstract Values](#abstract-values-1)
      * [Type Information](#type-information)

<!-- Added by: mdemello, at: 2020-08-10T13:15-07:00 -->

<!--te-->

## Objects, Types and Values

The regular python interpreter tracks the *values* of objects. That is, given
the code

```
x = "hello world"
```

it will create an object (a block of memory) whose contents are the string
"hello world", and any part of the code that holds a reference to the object
(e.g. the variable `x` here) can retrieve that value.

If an object is mutable, calling one of the mutation methods will change the
contents of the object while retaining the object's identity, for example

```
x = [1, 2, 3]
y = x  # y and x now point to the same list object
x[0] = 4
print(y)  # => [4, 2, 3]
```

Pytype likewise creates and maintains objects, but it tracks the *types* of
those objects rather than their values. In the examples above,

```
x = "hello world"
```

will create an object whose contents are essentially "this is a string", and

```
x = [1, 2, 3]
```

will create an object whose contents are "this is a list of integers". Following
this strategy, mutating the object will not necessarily produce any changes in
its pytype representation - e.g. `x[0] = 4` as above will continue to store the
object as "this is a list of integers", but `x[0] = "foo"` will change its
contents to "this is a list of strings and integers".

## Abstract Values

In broad terms, python objects can be divided into classes and instances. An
instance contains a reference to a class, and the class is referred to as the
"type" of the instance. Again in broad terms, every python object is a
dictionary of key/value pairs, where the entries are the object properties,
methods, and metadata like type annotations. Pytype models this object system
with a hierarchy of python classes whose instances act as abstract
representations of python objects.

This is easier to explain with a concrete example, so consider the following
code:

```
class A(object):
  def __init__(self, x):
    self.x = x

foo = A(10)
```

Pytype would execute the following pseudocode to model it:

```
# Create a "class" object for A
obj1 = abstract.InterpreterClass(
  name = "A",
  bases = [builtinclass_object],
  members = {}
)

# Create a "method" object for __init__, setting its containing class to A
obj2 = abstract.Method(
  name = "__init__",
  containing_class = obj1,
  signature = (args=['x'], return=None)
  bytecode = <bytecode>
)

# Fill in the member dictionary for class A
# Note that we have no information about the type of A.x so we set it to the Any
# type, which matches everything when type checked.
obj1.members['__init__'] = obj2
obj1.members['x'] = builtinclass_Any

# Create an "instance" object for foo
obj3 = abstract.Instance(
  class = obj1,
  initializers = {'x': 10},
  members = {}
)

# Fill in the members for foo, based on the class and the initializer
obj3.members['__init__'] = obj2
obj3.members['x'] = builtinclass_int

# Fill in the variable name assignments
globals = {'A': obj1, 'foo': obj3}
```

The `abstract.*` classes are defined in `abstract.py`. They all inherit from the
base class `AtomicAbstractValue`, which is the pytype representation of a python
object, and store various metadata that is relevant to type inference and
checking (e.g.  the `InterpreterClass` object stores a list of base classes and
a dictionary of members, and the `Instance` object stores a reference to the
`InterpreterClass` object it was instantiated from).

## Type Information

In python, the type of an object is determined (at runtime) by the class it is
created from, as can be seen from this ipython session:

```
In [1]: class A: pass
In [2]: x = A()
In [3]: y = [x]

In [4]: type(A)
Out[4]: type

In [5]: type(x)
Out[5]: __main__.A

In [6]: type(y)
Out[6]: list
```

Pytype determines the same information at "compile" time, by analysing the
bytecode without actually running it. The "type" of an object within pytype is
determined by a combination of several factors:

- What abstract class we have instantiated to represent it
- What the `class` property of that instance is
- What the `type parameters` property of that instance contains.
- What the `type annotations` property of the class contains.

The final two points are important - pytype has a richer (and stricter) type
system than python itself does, but this type system usually represents the
intent of the code better.

For instance, given the following code:

```
x: List[int] = []
x.append("hello")
```

python will consider the type of the object x points to to be `list` throughout,
whereas pytype will first create it as `List[int]`, and then raise a type error
because we are trying to mutate it to `List[int, string]` which contradicts the
type annotation.

Python will *not* raise a type error for the same code, because (a) type
annotations are treated as comments and not directives, and (b) because the type
of all lists is simply `list`, and is not parametrised by the type of its
contents, so there was no type violation.
