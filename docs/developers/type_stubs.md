# Type stubs

<!--ts-->
   * [Type stubs](#type-stubs)
      * [Introduction](#introduction)
      * [Importing](#importing)
      * [Parsing](#parsing)
      * [Generating](#generating)
      * [Manipulating](#manipulating)

<!-- Added by: rechen, at: 2020-08-07T13:46-07:00 -->

<!--te-->

## Introduction

A *type stub* is a file with a `.pyi` extension that describe a module's types
while omitting implementation details. For example, if a module `foo` has the
following source code:

```python
class Foo:
  CONSTANT = 42

def do_foo(x):
  return x
```

then `foo.pyi` would be:

```python
from typing import TypeVar

T = TypeVar('T')

class Foo:
  CONSTANT: int

def do_foo(x: T) -> T: ...
```

pytype allows an unannotated parameterized class's contained type to be changed,
an operation we call a *mutation*, which .pyi files do not have a way of
expressing. Thus, pytype uses an extended pyi format, PyTypeDecl ("Python Type
Declaration") or *PyTD*, in which mutations are described by assignment to
`self` in a method body. For example, pytype's `builtins.pytd` types
`dict.update` as:

```python
class dict(Dict[_K, _V]):
  def update(self, other: dict[_K2, _V2]) -> None:
    self = dict[Union[_K, _K2], Union[_V, _V2]]
```

In practice, the terms `pyi` and `pytd` are often used interchangeably.

pytype relies on the stubs provided by the open-source [typeshed][typeshed]
project for most of its standard library and third party type information. For
modules for which accurate mutation information is important, we shadow the
typeshed stubs with custom pytd stubs located in
[pytype/pytd/{builtins,stdlib}][pytd]. During analysis, pytype
will emit stubs of inferred type information for local files to communicate
between `pytype-single` runs.

## Importing

## Parsing

## Generating

## Manipulating

[pytd]: https://github.com/google/pytype/tree/master/pytype/pytd

[typeshed]: https://github.com/python/typeshed
