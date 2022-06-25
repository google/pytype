<!--* freshness: { owner: 'rechen' reviewed: '2022-06-22' } *-->

# User guide

<!--ts-->
   * [User guide](#user-guide)
      * [Introduction](#introduction)
      * [The typing module](#the-typing-module)
      * [Silencing errors](#silencing-errors)
      * [Variable annotations](#variable-annotations)
      * [Hiding extra dependencies](#hiding-extra-dependencies)
      * [Pyi stub files](#pyi-stub-files)
      * [Pytype's pyi stub files](#pytypes-pyi-stub-files)

<!-- Added by: rechen, at: 2022-06-22T23:51-07:00 -->

<!--te-->

## Introduction

Here's a simple example of plain Python code:

```python
def unannotated(x, y):
  return " + ".join(x, y)
```

This code has a bug: `str.join` should be passed an iterable of strings, not the
individual strings. pytype will discover and report this bug:

```
File "t.py", line 2, in unannotated: Function str.join expects 2 arg(s), got 3 [wrong-arg-count]
  Expected: (self, iterable)
  Actually passed: (self, iterable, _)
```

Here's an example of type annotations:

```python
def annotated(x: int, y: float = 0.0) -> int:
  return x + y
```

The above code uses the syntax from [PEP 3107][pep-3107] and [PEP 484][pep-484]
to declare the parameter and return types of the function `annotated`.

Note that the return type of `annotated` is declared to be an integer, but the
function actually returns a float. pytype will also find this bug:

```
File "t.py", line 2, in annotated: bad option in return type [bad-return-type]
  Expected: int
  Actually returned: float
```

## The `typing` module

The above code only used [built-in types][stdtypes] (`int` and `float`). To
formulate more complex types, you typically need the
[typing][pep-484-the-typing-module] module. It
contains many useful definitions that can, for example, be used to declare a
function that extracts the keys out of a mapping:

```python
from typing import Any, Mapping, Sequence, Text

def keys(mapping: Mapping[Text, Any]) -> Sequence[Text]:
  return tuple(mapping)
```

or describe callable objects or higher order functions:

```python
from typing import Callable

def instantiate(factory: Callable[[], int]) -> int:
  return factory()
```

A particularly useful construct is [`Optional`][optional], which can be used to
specify that a function might return `None`:

```python
from typing import Optional, Sequence, Text

def find_index_of_name(sequence: Sequence[Any], name: Text) -> Optional[int]:
  try:
    return sequence.index(name)
  except ValueError:
    return None
```

or allows a `None` value:

```python
from typing import Optional, Text

def greet(name: Optional[Text]) -> Text:
  return 'Hi John Doe' if name is None else 'Hi ' + name
```

## Silencing errors

Sometimes pytype generates "false positives", i.e. errors that, from the
perspective of the type-checker, are correct, but from a user standpoint aren't.

For example, this is a class that uses late initialization.

```python
import socket
class Server:

  def __init__(self, port):
    self.port = port

  def listen(self):
    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.socket.bind((socket.gethostname(), self.port))
    self.socket.listen(backlog=5)

  def accept(self):
    return self.socket.accept()
```

pytype will complain:

```
File "t.py", line 13, in accept: No attribute 'socket' on Server [attribute-error]
```

(The reasoning is that if you call `accept()` before `listen()`, Python will
crash with an `AttributeError`.)

Note that the error message will contain the class of the error:
`attribute-error`

To silence this warning, change line 13 to this:

```python
return self.socket.accept()  # pytype: disable=attribute-error
```

Alternatively, if there are a lot of these occurrences, put the following at the
start of the file. A `disable` on a line by itself will disable all these
warnings for the rest of the file. (This is true even if the `disable` is within
an indented block.)

```python
# pytype: disable=attribute-error
```

Use `enable` to re-enable a disabled warning:

```python
# pytype: disable=attribute-error
return self.socket.accept()
# pytype: enable=attribute-error
```

There is also a "catch-all". Above, we could have written:

```python
return self.socket.accept()  # type: ignore
```

It's preferred to use the precise form (`pytype: disable=some-error`) instead of
`type: ignore`, and leave the latter for rare and special circumstances.

## Variable annotations

Above, we only silenced the error pytype gave us. A better fix is to make pytype
aware of the attributes `Server` has (or is going to have). For this, we add a
[PEP 526][pep-526]-style *variable annotation*:

```python
class Server:
  socket: socket.socket
```

## Hiding extra dependencies

Adding type annotations to your code sometimes means that you have to add extra
dependencies. For example, say we have the following function:

```python
def start_ftp_server(server):
  return server.start()
```

While this function works in isolation and doesn't need any imports, it
potentially operates on types from another module. Adding the type annotation
reveals that fact:

```python
import ftp

def start_ftp_server(server: ftp.Server):
  return server.start()
```

While we encourage to write the code like above, and hence make it clear that
our code does depend, indirectly, on the types declared in `ftp`, the additional
imports can lead to concerns about load-time performance.

PEP 484 [allows][pep-484-runtime-or-type-checking] to declare imports in a block
that's only evaluated during type-checking. See Google's
[Python Style Guide][style-guide-conditional-imports].

## Pyi stub files

In some cases, it's not possible to add annotations to a module by editing its
source: C extension modules, external python source files, etc . For those
cases, [PEP 484][pep-484-stub-files] allows you to declare a module's types in a
separate "stub" file with a `.pyi` extension. Pyi files follow a subset of the
python syntax and are analogous to header files in C ([examples][pyi-examples]).

If you already have a `.pyi` and would like to merge it back into a `.py` file,
we provide a [tool][merge-pyi] to automate this.

## Pytype's pyi stub files

For builtins, standard library, and third party modules, pytype uses static pyi
files rather than ones generated by running over the Python code. The files are
located in [pytype builtins][pytype-builtins], [pytype stdlib][pytype-stdlib],
and [typeshed][typeshed]. If you find a mistake in one of these files, please
[file a bug][new-bug].

<!-- General references -->
[optional]: https://docs.python.org/3/library/typing.html#typing.Optional
[pep-3107]: https://www.python.org/dev/peps/pep-3107
[pep-484]: https://www.python.org/dev/peps/pep-0484
[pep-484-runtime-or-type-checking]: https://www.python.org/dev/peps/pep-0484/#runtime-or-type-checking
[pep-484-stub-files]: https://www.python.org/dev/peps/pep-0484/#stub-files
[pep-484-the-typing-module]: https://www.python.org/dev/peps/pep-0484/#the-typing-module
[pep-526]: https://www.python.org/dev/peps/pep-0526/
[pyi-examples]: https://github.com/python/typeshed/tree/master/stdlib
[stdtypes]: https://docs.python.org/2/library/stdtypes.html

<!-- References with different internal and external versions -->

[merge-pyi]: https://github.com/google/pytype/tree/main/pytype/tools/merge_pyi

[new-bug]: https://github.com/google/pytype/issues/new

[pytype-builtins]: https://github.com/google/pytype/tree/main/pytype/stubs/builtins

[pytype-stdlib]: https://github.com/google/pytype/tree/main/pytype/stubs/stdlib

[style-guide-conditional-imports]: https://google.github.io/styleguide/pyguide.html#31913-conditional-imports

[typeshed]: https://github.com/python/typeshed
