# Type stubs

<!--ts-->
   * [Type stubs](#type-stubs)
      * [Introduction](#introduction)
      * [Imports](#imports)
      * [Parser](#parser)
      * [AST manipulation](#ast-manipulation)
      * [Stub generation](#stub-generation)
      * [Pickling](#pickling)

<!-- Added by: mdemello, at: 2020-08-10T13:15-07:00 -->

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

## Imports

Import resolution is handled by the [load_pytd.Loader][load_pytd.Loader] class,
which loads type stubs into a cached internal AST representation. The loader
finds stubs for local files in one of two ways:

* When the `--imports_info` flag is passed, this flag point to a file that maps
  all module paths to file paths, which is used to look up the import.
* Otherwise, we search for a module or package with the given name in the
  current directory.

The second approach is used by `pytype-single` by default, but pytype's
whole-project analysis tools always pass in `--imports_info` for more reliable,
reproducible stub finding. The pytype GitHub project uses
[importlab][importlab], another Google open-source project, to generate the
dependency graph from which imports_info is constructed.

If an import can't be resolved locally, pytype falls back to the standard
library, then typeshed/third_party.

<!-- TODO(rechen): Add a diagram showing the relationship between all the
import and load methods in load_pytd. -->

## Parser

The stub parser in [pytype/pyi][pytype.pyi] reads in a type stub and produces an
AST representation of its contents. Its structure is as follows:

`lexer.lex` turns the stub contents into a stream of tokens. `parser.yy` (the
grammar) matches on the tokens and produces expressions that build AST nodes.
`parser.h` declares names that appear in these expressions, and `parser.py`
implements the expressions. `parser_ext.cc` describes the mappings between names
in each step of the process.

A few examples:

* A string produces a `t::STRING` token. `parser_ext.cc` maps `t::STRING` to the
  name `STRING`, which the grammar can then use to refer to strings.
* The `...` constant produces a `t::ELLIPSIS` token, which `parser_ext.cc` maps
  to the name `ELLIPSIS` that the grammar then uses. The grammar outputs the
  expression `kEllipsis`, which is declared in `parser.h` and mapped by
  `parser_ext.cc` to a value again named `ELLIPSIS`. Finally, the `ELLIPSIS`
  value is defined in `parser.py` as an attribute on the `Parser` class.
* The grammar outputs an expression that calls a function, `kNewClass`, in order
  to build a class node. `parser.h` declares `kNewClass`, and `parser_ext.cc`
  maps it to the name of the implementation, `new_class`, which is defined in
  `parser.py` as a method of the `Parser` class.

The AST nodes are defined in
[pytype/pytd/pytd.py][pytype.pytd.pytd] as collections.namedtuple objects whose
attributes may be other namedtuples.

## AST manipulation

## Stub generation

## Pickling

[importlab]: https://github.com/google/importlab

[load_pytd.Loader]: https://github.com/google/pytype/blob/2d8c8960ce8621c9c3d883d44eb3fc219355bd2b/pytype/load_pytd.py#L112

[pytd]: https://github.com/google/pytype/tree/master/pytype/pytd

[pytype.pyi]: https://github.com/google/pytype/tree/master/pytype/pyi

[pytype.pytd.pytd]: https://github.com/google/pytype/blob/master/pytype/pytd/pytd.py

[typeshed]: https://github.com/python/typeshed
