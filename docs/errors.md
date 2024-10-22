<!--* freshness: { exempt: true } *-->

# Error classes

pytype has the following classes of errors, which can be disabled with a
`pytype: disable=error-class` directive. For example, to suppress an
error for a missing attribute `foo`:

```
x = a.foo  # pytype: disable=attribute-error
```

or, to suppress all attribute errors for a block of code:

```
# pytype: disable=attribute-error
x = a.foo
y = a.bar
# pytype: enable=attribute-error
```

See [Silencing Errors][silencing-errors] for a more detailed example.

<!--ts-->
* [Error classes](#error-classes)
   * [annotation-type-mismatch](#annotation-type-mismatch)
   * [assert-type](#assert-type)
   * [attribute-error](#attribute-error)
   * [bad-concrete-type](#bad-concrete-type)
   * [bad-function-defaults](#bad-function-defaults)
   * [bad-return-type](#bad-return-type)
   * [bad-slots](#bad-slots)
   * [bad-unpacking](#bad-unpacking)
   * [bad-yield-annotation](#bad-yield-annotation)
   * [base-class-error](#base-class-error)
   * [container-type-mismatch](#container-type-mismatch)
   * [dataclass-error](#dataclass-error)
   * [duplicate-keyword-argument](#duplicate-keyword-argument)
   * [final-error](#final-error)
   * [ignored-abstractmethod](#ignored-abstractmethod)
   * [ignored-metaclass](#ignored-metaclass)
   * [ignored-type-comment](#ignored-type-comment)
   * [import-error](#import-error)
   * [incomplete-match](#incomplete-match)
   * [invalid-annotation](#invalid-annotation)
   * [invalid-directive](#invalid-directive)
   * [invalid-function-definition](#invalid-function-definition)
   * [invalid-function-type-comment](#invalid-function-type-comment)
   * [invalid-namedtuple-arg](#invalid-namedtuple-arg)
   * [invalid-signature-mutation](#invalid-signature-mutation)
   * [invalid-super-call](#invalid-super-call)
   * [invalid-typevar](#invalid-typevar)
   * [late-directive](#late-directive)
   * [match-error](#match-error)
   * [missing-parameter](#missing-parameter)
   * [module-attr](#module-attr)
   * [mro-error](#mro-error)
   * [name-error](#name-error)
   * [not-callable](#not-callable)
   * [not-indexable](#not-indexable)
   * [not-instantiable](#not-instantiable)
   * [not-supported-yet](#not-supported-yet)
   * [not-writable](#not-writable)
   * [override-error](#override-error)
   * [paramspec-error](#paramspec-error)
   * [pyi-error](#pyi-error)
   * [python-compiler-error](#python-compiler-error)
   * [recursion-error](#recursion-error)
   * [redundant-function-type-comment](#redundant-function-type-comment)
   * [redundant-match](#redundant-match)
   * [reveal-type](#reveal-type)
   * [signature-mismatch](#signature-mismatch)
   * [typed-dict-error](#typed-dict-error)
   * [unbound-type-param](#unbound-type-param)
   * [unsupported-operands](#unsupported-operands)
   * [wrong-arg-count](#wrong-arg-count)
   * [wrong-arg-types](#wrong-arg-types)
   * [wrong-keyword-args](#wrong-keyword-args)

<!-- Created by https://github.com/ekalinin/github-markdown-toc -->
<!-- Added by: rechen, at: Thu Nov  2 01:55:50 PM PDT 2023 -->

<!--te-->

## annotation-type-mismatch

A variable had a type annotation and an assignment with incompatible types.

Example:

<!-- bad -->
```python
x: int = 'hello world'
```

This error is also raised for wrongly assigning a value in a `TypedDict`:

<!-- bad -->
```python
from typing import TypedDict

class A(TypedDict):
  x: int
  y: str

a = A()
a['x'] = '10'
```

## assert-type

The error message displays the expected and actual type of the expression passed
to `assert_type()` if the two do not match. Example:

<!-- bad -->
```python
x = 10
assert_type(x, str)
```

will raise the error

```
File "foo.py", line 2, in <module>:
Type[int] [assert-type]
Expected: str
  Actual: int
```

The expected type can be either a python type (like `str` or `foo.A`) or its
string representation. The latter form is useful when you want to assert a type
without importing it, e.g.

```python
from collections.abc import Sequence

assert_type(x, Sequence[int])
```

versus

```python
assert_type(x, 'Sequence[int]')
```

`assert_type` can also be used without an `expected` argument to assert that a
type is not `Any`; in that case the error message is

```
File "foo.py", line 10, in f: Asserted type was Any [assert-type]
```

## attribute-error

The attribute being accessed may not exist. Often, the reason is that the
attribute is declared in a method other than `__new__` or `__init__`:

<!-- bad -->
```python
class A:
  def make_foo(self):
    self.foo = 42
  def consume_foo(self):
    return self.foo  # attribute-error
```

To make pytype aware of `foo`, declare its type with a variable annotation:

<!-- good -->
```python
class A:
  foo: int
```

NOTE: This declaration does *not* define the attribute at runtime.

## bad-concrete-type

A generic type was instantiated with incorrect concrete types.
Example:

<!-- bad -->
```python
from typing import Generic, TypeVar

T = TypeVar('T', int, float)

class A(Generic[T]):
  pass

obj = A[str]()  # bad-concrete-type
```

## bad-function-defaults

An attempt was made to set the `__defaults__` attribute of a function with an
object that is not a constant tuple. Example:

<!-- bad -->
```python
import collections
X = collections.namedtuple("X", "a")
X.__new__.__defaults__ = [None]  # bad-function-defaults
```

## bad-return-type

At least one of the possible types for the return value does not match the
declared return type. Example:

<!-- bad -->
```python
def f(x) -> int:
  if x:
    return 42
  else:
    return None  # bad-return-type
```

NOTE: For the corner case of an empty function whose body is a docstring, use
the block form of `disable` to suppress the error:

```python
# pytype: disable=bad-return-type
def f() -> int:
  """Override in subclasses and return int."""
# pytype: enable=bad-return-type
```

## bad-slots

An attempt was made to set the `__slots__` attribute of a class using an object
that's not a string.

<!-- bad -->
```python
class Foo:
  __slots__ = (1, 2, 3)
```

## bad-unpacking

A tuple was unpacked into the wrong number of variables. Example:

<!-- bad -->
```python
a, b = (1, 2, 3)  # bad-unpacking
```

## bad-yield-annotation

A generator function (a function with a `yield`) was not annotated with an
appropriate return type.

<!-- bad -->
```python
def gen() -> int:  # bad-yield-annotation
  yield 1
```

<!-- good -->
```python
def gen() -> Iterator[int]
  # Could also use Generator or Iterable.
  yield 1
```

## base-class-error

The class definition uses an illegal value for a base class. Example:

<!-- bad -->
```python
class A(42):  # base-class-error
  pass
```

## container-type-mismatch

A method call violated the type annotation of a container by modifying its
contained type.

Example:

<!-- bad -->
```python
a: list[int] = [1, 2]
a.append("hello")  # <-- contained type is now `int | str`
```

## dataclass-error

An error was raised while constructing a dataclass.

## duplicate-keyword-argument

A positional argument was supplied again as a keyword argument. Example:

<!-- bad -->
```python
def f(x):
  pass
f(True, x=False)  # duplicate-keyword-argument
```

If you believe you are seeing this error due to a bug on pytype's end, see
[this section][pyi-stub-files] for where the type information we use is located.

## final-error

An attempt was made to subclass, override or reassign a final object or
variable. The exact meaning of "final" is context dependent; see [PEP
591][pep-591] for the full details. Example:

<!-- bad -->
```python
class A:
  FOO: Final[int] = 10

class B(A):
  FOO = 20  # final-error
```

## ignored-abstractmethod

The abc.abstractmethod decorator was used in a non-abstract class. Example:

<!-- bad -->
```python
import abc
class A:  # ignored-abstractmethod
  @abc.abstractmethod
  def f(self):
    pass
```

Add the `abc.ABCMeta` metaclass to fix this issue:

<!-- good -->
```python
import abc
class A(metaclass=abc.ABCMeta):
  @abc.abstractmethod
  def f(self):
    pass
```

## ignored-metaclass

A Python 2 metaclass declaration was found. Example:

<!-- bad -->
```python
class A:
  __metaclass__ = Meta
```

The fix is to switch to a Python 3-style metaclass:

<!-- good -->
```python
class A(metaclass=Meta):
  ...
```

## ignored-type-comment

A type comment was found on a line on which type comments are not allowed.
Example:

<!-- bad -->
```python
def f():
  return 42  # type: float  # ignored-type-comment
```

## import-error

The module being imported was not found.

## incomplete-match

A pattern match over an enum did not cover all possible cases.

<!-- bad -->
```python
from enum import Enum
class Color(Enum):
  RED = 0
  GREEN = 1
  BLUE = 2

def f(x: Color):
  match x:  # incomplete-match
    case Color.RED:
      return 10
    case Color.GREEN:
      return 20
```

## invalid-annotation

Something is wrong with this annotation. A common issue is a TypeVar that
appears only once in a function signature:

<!-- bad -->
```python
from typing import TypeVar
T = TypeVar("T")
def f(x: T):  # bad: the TypeVar appears only once in the signature
  pass
```

A TypeVar is meaningful only when it appears multiple times in the same
class/function, since it's used to indicate that two or more values have the
same type.

Other examples:

<!-- bad -->
```python
from typing import Union

condition: bool = ...
class _Foo: ...
def Foo():
  return _Foo()

def f(x: list[int, str]):  # bad: too many parameters for List
  pass
def f(x: Foo):  # bad: not a type
  pass
def f(x: Union):  # bad: no options in the union
  pass
def f(x: int if condition else str):  # bad: ambiguous type
  pass
```

You will also see this error if you use a forward reference in typing.cast or
pass a bad type to `attr.ib`:

<!-- bad -->
```python
import attr
import typing

v = typing.cast("A", None)  # invalid-annotation
class A:
  pass

@attr.s
class Foo:
  v = attr.ib(type=zip)  # invalid-annotation
```

The solutions are to use a variable annotation and to fix the type:

<!-- good -->
```python
import attr

v: "A" = None
class A:
  pass

@attr.s
class Foo:
  v = attr.ib(type=list)
```

## invalid-directive

The error name is misspelled in a pytype disable/enable directive. Example with
a misspelled `name-error`:

<!-- bad -->
```python
x = TypeDefinedAtRuntime  # pytype: disable=nmae-error  # invalid-directive
```

## invalid-function-definition

An invalid function was constructed, typically with a decorator such as
`@dataclass`. Example:

<!-- bad -->
```python
from dataclasses import dataclass

@dataclass
class A:
  x: int = 10
  y: str
```

which creates

<!-- bad -->
```python
def __init__(x: int = 10, y: str):
  ...
```

with a non-default argument following a default one.

## invalid-function-type-comment

Something was wrong with this function type comment. Examples:

<!-- bad -->
```python
def f(x):
  # type: (int)  # bad: missing return type
  pass
def f(x):
  # type: () -> None  # bad: too few arguments
  pass
def f(x):
  # type: int -> None  # bad: missing parentheses
  pass
```

## invalid-namedtuple-arg

The typename or one of the field names in the namedtuple definition is invalid.
Field names:

*   must not be a Python keyword,
*   must consist of only alphanumeric characters and "_",
*   must not start with "_" or a digit.

Also, there can be no duplicate field names. The typename has the same
requirements, except that it can start with "_".

## invalid-signature-mutation

A method signature in a pyi file has an annotation on `self` that does not match
the base class.

Generic class methods can annotate `self` with more specific type parameters,
which will then specialize the type of the receiver when the method is called,
but the `self` annotation cannot mutate the base class.

<!-- bad -->
```python
class A(Generic[T]):
  def foo(self: B[int]): ...
```

## invalid-super-call

A call to super without any arguments (Python 3) is being made from an invalid
context:

<!-- bad -->
```python
super().foo()
```

<!-- bad -->
```python
class A(B):
  def f():
    super().foo()
```

A super call without any arguments should be made from a method or a function
defined within a class, and the caller should have at least one positional
argument:

<!-- good -->
```python
class A(B):
  def f(self):
    super().foo()
```

## invalid-typevar

Something was wrong with this TypeVar definition. Examples:

<!-- bad -->
```python
from typing import TypeVar
T = TypeVar("S")  # bad: storing TypeVar "S" as "T"
T = TypeVar(42)  # bad: using a non-str value for the TypeVar name
T = TypeVar("T", str)  # bad: supplying a single constraint (did you mean `bound=str`?)
T = TypeVar("T", 0, 100)  # bad: 0 and 100 are not types
```

## late-directive

A `# pytype: disable` without a matching following enable or a `# type: ignore`
appeared on its own line after the first top-level definition. Such a directive
takes effect for the rest of the file, regardless of indentation, which is
probably not what you want:

<!-- bad -->
```python
def f() -> bool:
  # pytype: disable=bad-return-type  # late-directive
  return 42
```

Two equally acceptable fixes:

<!-- good -->
```python
def f() -> bool:
  return 42  # pytype: disable=bad-return-type
```

<!-- good -->
```python
# pytype: disable=bad-return-type
def f() -> bool:
  return 42
# pytype: enable=bad-return-type
```

## match-error

An invalid pattern matching construct was used (e.g. too many positional
parameters)

## missing-parameter

The function was called with a parameter missing. Example:

<!-- bad -->
```python
def add(x, y):
  return x + y
add(42)  # missing-parameter
```

If you believe you are seeing this error due to a bug on pytype's end, see
[this section][pyi-stub-files] for where the type information we use is located.

## module-attr

The module attribute being accessed may not exist. Example:

<!-- bad -->
```python
import sys
sys.nonexistent_attribute  # module-attr
```

## mro-error

A valid method resolution order cannot be created for the class being defined.
Often, the culprit is cyclic inheritance:

<!-- bad -->
```python
class A:
  pass
class B(object, A):  # mro-error
  pass
```

## name-error

This name does not exist in the current namespace. Note that abstract types like
`Sequence`, `Callable`, etc., need to be imported from the collections.abc
module:

<!-- bad -->
```python
MySequenceType = Sequence[str]  # name-error
```

<!-- good -->
```python
from collections.abc import Sequence

MySequenceType = Sequence[str]
```

Note that a name from an outer namespace cannot be referenced if you redefine it
in the current namespace, unless you use the `global` or `nonlocal` keyword:

<!-- bad -->
```python
def f():
  x = 0
  def g():
    x += 1  # name-error
```

<!-- good -->
```python
def f():
  x = 0
  def g():
    nonlocal x
    x += 1
```

## not-callable

The object being called or instantiated is not callable. Example:

<!-- bad -->
```python
x = 42
y = x()  # not-callable
```

## not-indexable

The object being indexed is not indexable. Example:

<!-- bad -->
```python
tuple[3]  # not-indexable
```

## not-instantiable

The class cannot be instantiated because it has abstract methods. Example:

<!-- bad -->
```python
import abc
class A(metaclass=abc.ABCMeta):
  @abc.abstractmethod
  def f(self):
    pass
A()  # not-instantiable
```

## not-supported-yet

This feature is not yet supported by pytype.

The fix for the error "Calling TypeGuard function 'foo' with an arbitrary
expression not supported yet" is to refactor the code passing an arbitrary
expression to `foo` to pass in a local variable instead. For example:

```python
# Before:
if foo(eggs[0]):
  do_something()

# After:
egg = eggs[0]
if foo(egg):
  do_something()
```

## not-writable

The object an attribute was set on doesn't have that attribute, or that
attribute isn't writable:

<!-- bad -->
```python
class Foo:
  __slots__ = ("x", "y")

Foo().z = 42  # not-writable
```

## override-error

This error is reported when `@typing.override` is used to decorate a
non-overriding method:

<!-- bad -->
```python
import typing
class Parent:
  def new_foo(self):
    pass
class Child(Parent):
  @typing.override
  def foo(self):  # override-error
    pass
```

If you enable the `require-override-decorator` feature, then you'll also get
this error when the decorator is forgotten:

<!-- bad -->
```python
# pytype: features=require-override-decorator

class Parent:
  def foo(self):
    pass
class Child(Parent):
  def foo(self):  # override-error
    pass
```

## paramspec-error

A [parameter specification variable][pep-612] was used incorrectly. Examples
include only having a single ParamSpec in a function signature, and not exactly
following the limited syntax for `P.args` and `P.kwargs`.

## pyi-error

The pyi file contains a syntax error.

If you encounter this error in a pyi file that you did not create yourself,
please [file a bug][new-bug].

## python-compiler-error

The Python code contains a syntax error.

## recursion-error

A recursive definition was found in a pyi file. Example:

<!-- bad -->
```python
class A(B): ...
class B(A): ...
```

If you encounter this error in a pyi file that you did not create yourself,
please [file a bug][new-bug].

## redundant-function-type-comment

Using both inline annotations and a type comment to annotate the same function
is not allowed. Example:

<!-- bad -->
```python
def f() -> None:
  # type: () -> None  # redundant-function-type-comment
  pass
```

## redundant-match

A pattern match over an enum covered the same case more than once.

<!-- bad -->
```python
from enum import Enum
class Color(Enum):
  RED = 0
  GREEN = 1
  BLUE = 2

def f(x: Color):
  match x:
    case Color.RED:
      return 10
    case Color.GREEN:
      return 20
    case Color.RED | Color.BLUE:  # redundant-match
      return 20
```

## reveal-type

The error message displays the type of the expression passed to it. Example:

<!-- good -->
```python
import os
reveal_type(os.path.join("hello", u"world"))  # reveal-type: str
```

This feature is implemented as an error to ensure that `reveal_type()` calls are
removed after debugging.

## signature-mismatch

The overriding method signature doesn't match the overridden method:

<!-- bad -->
```python
class A:
  def f(self, x: int) -> None:
    pass

class B(A):
  def f(self, x:int, y: int) -> None:  # signature-mismatch
    pass
```

<!-- good -->
```python
class A:
  def f(self, x: int) -> None:
    pass

class B(A):
  def f(self, x:int, y: int = 0) -> None:
    pass
```

See [FAQ][pytype-faq-signature-mismatch] on why it can cause problems.

## typed-dict-error

A [TypedDict](https://www.python.org/dev/peps/pep-0589/) has been accessed with
an invalid key. Example:

<!-- bad -->
```python
from typing import TypedDict

class A(TypedDict):
  x: int
  y: str

a = A()
a['z'] = 10
```

## unbound-type-param

This error currently applies only to pyi files. The type parameter is not bound
to a class or function. Example:

<!-- bad -->
```python
from typing import AnyStr
x: AnyStr = ...
```

Unbound type parameters are meaningless as types. If you want to take advantage
of types specified by a type parameter's constraints or bound, specify those
directly. So the above example should be rewritten as:

<!-- good -->
```python
x: str | bytes = ...
```

## unsupported-operands

A binary operator was called with incompatible arguments. Example:

<!-- bad -->
```python
x = "hello" ^ "world"  # unsupported-operands
```

## wrong-arg-count

The function was called with the wrong number of arguments. Example:

<!-- bad -->
```python
def add(x, y):
  return x + y
add(1, 2, 3)  # wrong-arg-count
```

If you believe you are seeing this error due to a bug on pytype's end, see
[this section][pyi-stub-files] for where the type information we use is located.

## wrong-arg-types

The function was called with the wrong argument types. Example:

<!-- bad -->
```python
def f(x: int):
  pass
f(42.0)  # wrong-arg-types
```

If you are seeing a Non-Iterable String Error, please see
[FAQ][pytype-faq-noniterable-strings].

If you believe you are seeing this error due to a bug on pytype's end, see
[this section][pyi-stub-files] for where the type information we use is located.

## wrong-keyword-args

The function was called with the wrong keyword arguments. Example:

<!-- bad -->
```python
def f(x=True):
  pass
f(y=False)  # wrong-keyword-args
```

If you believe you are seeing this error due to a bug on pytype's end, see
[this section][pyi-stub-files] for where the type information we use is located.

<!-- General references -->

[pyi-stub-files]: user_guide.md#pytypes-pyi-stub-files
[silencing-errors]: user_guide.md#silencing-errors
[pytype-faq-noniterable-strings]: faq.md#noniterable-strings
[pytype-faq-signature-mismatch]: faq.md#signature-mismatch
[pep-591]: https://www.python.org/dev/peps/pep-0591/
[pep-612]: https://www.python.org/dev/peps/pep-0612/

<!-- References with different internal and external versions -->
[new-bug]: https://github.com/google/pytype/issues/new
