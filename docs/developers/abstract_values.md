# Abstract values

<!--*
freshness: { owner: 'mdemello' reviewed: '2020-07-09' }
*-->

<!--ts-->
   * [Abstract values](#abstract-values)
      * [Objects, Types and Values](#objects-types-and-values)
      * [Abstract Values](#abstract-values-1)
      * [Type Information](#type-information)
      * [Matching](#matching)
      * [Construction](#construction)

<!-- Added by: rechen, at: 2020-11-09T11:54-08:00 -->

<!--te-->

## Objects, Types and Values

The regular python interpreter tracks the *values* of objects. That is, given
the code

```python
x = "hello world"
```

it will create an object (a block of memory) whose contents are the string
"hello world", and any part of the code that holds a reference to the object
(e.g. the variable `x` here) can retrieve that value.

If an object is mutable, calling one of the mutation methods will change the
contents of the object while retaining the object's identity, for example

```python
x = [1, 2, 3]
y = x  # y and x now point to the same list object
x[0] = 4
print(y)  # => [4, 2, 3]
```

Pytype likewise creates and maintains objects, but it tracks the *types* of
those objects rather than their values. In the examples above,

```python
x = "hello world"
```

will create an object whose contents are essentially "this is a string", and

```python
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

```python
class A(object):
  def __init__(self, x):
    self.x = x

foo = A(10)
```

Pytype would execute the following pseudocode to model it:

```python
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

TIP: The [abstract_utils][abstract_utils] module contains many useful functions
for working with abstract values. Additionally, all abstract values have a `vm`
attribute that references the current virtual machine, through which various
[handlers][vm-attributes] for abstract values can be accessed.

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

```python
x: List[int] = []
x.append("hello")
```

python will consider the type of the object x points to to be `list` throughout,
whereas pytype will first create it as `List[int]`, and then raise a type error
because we are trying to mutate it to `List[Union[int, string]]` which
contradicts the type annotation.

Python will *not* raise a type error for the same code, because (a) type
annotations are treated as comments and not directives, and (b) because the type
of all lists is simply `list`, and is not parametrised by the type of its
contents, so there was no type violation.

## Matching

Most of the errors that pytype reports are detected via a mismatch between an
expected and an observed type. [`pytype/matcher.py`][matcher] contains the logic
for matching abstract values against each other. For example, when analyzing:

```python
def f(x: int): ...
f(0)
```

pytype will call

```python
matcher.match_var_against_type(
    Variable(Binding(PythonConstant(0))), PyTDClass(int))
```

in order to determine whether `f(0)` is a valid function call. Here,
`match_var_against_type` will return `True`, since the value `PythonConstant(0)`
is compatible with the type `PyTDClass(int)`.

A second important function of the matcher is to compute type parameter
substitutions. Consider this code snippet:

```python
T = TypeVar('T')
def f(x: T, y: T): ...
f(0, 1)
```

When matching `(0, 1)` against `(T, T)`, the matcher determines that the call is
valid because we can find a substitution, `{T: int}`, that matches the types of
the arguments for `x` and `y`. The matcher also returns this substitution
dictionary so that the type `T` is mapped to can be propagated.

## Construction

[`pytype.convert`][pytype.convert] constructs abstract values from raw Python
constants and [PyTD nodes][type_stubs]. The main conversion method is
`Converter.constant_to_value`, which wraps the `_constant_to_value` method that
contains most of the important logic and adds some caching. A few input-output
examples for `constant_to_value`:

`pyval`         | `constant_to_value(pyval)`
--------------- | --------------------------
`'hello world'` | `abstract.AbstractOrConcreteValue('hello world')`
`0`             | `abstract.AbstractOrConcreteValue(0)`
`42`            | `abstract.Instance(int)`
`pytd.Class(X)` | `abstract.PyTDClass(X)`

Some constants such as strings and small integers have to be represented as
`AbstractOrConcreteValue` objects, which save the concrete value for later use.
String values, for example, often contain forward references, and `-1` through
`2` are common import levels. Otherwise, constants are converted to abstract
instances of their types.

When code under analysis imports another module, pytype parses the other
module's types into PyTD nodes. Those nodes that are used in the current module
are then converted to abstract values as needed.

NOTE: Conversely, [`pytype.output`][stub-generation] converts abstract values
into PyTD nodes.

[abstract_utils]: https://github.com/google/pytype/blob/master/pytype/abstract_utils.py

[matcher]: https://github.com/google/pytype/blob/master/pytype/matcher.py

[pytype.convert]: https://github.com/google/pytype/blob/master/pytype/convert.py

[stub-generation]: type_stubs.md#stub_generation
[type_stubs]: type_stubs.md

[vm-attributes]: https://github.com/google/pytype/blob/62b9bd1d636965e695bd2e735244be47168dc5b0/pytype/vm.py#L147-L151
