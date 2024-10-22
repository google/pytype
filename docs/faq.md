<!--* freshness: { exempt: true } *-->

# FAQ

<!--ts-->
* [FAQ](#faq)
   * [How is pytype different from other type checkers?](#how-is-pytype-different-from-other-type-checkers)
   * [Can I find out what pytype thinks the type of my expression is?](#can-i-find-out-what-pytype-thinks-the-type-of-my-expression-is)
   * [How do I reference a type from within its definition? (Forward References)](#how-do-i-reference-a-type-from-within-its-definition-forward-references)
   * [I'm dynamically populating a class / module using setattr or by modifying locals() / globals(). Now pytype complains about missing attributes or module members. How do I fix this?](#im-dynamically-populating-a-class--module-using-setattr-or-by-modifying-locals--globals-now-pytype-complains-about-missing-attributes-or-module-members-how-do-i-fix-this)
   * [Why didn't pytype catch that my program (might) pass an invalid argument to a function?](#why-didnt-pytype-catch-that-my-program-might-pass-an-invalid-argument-to-a-function)
   * [How do I declare that something can be either byte string or unicode?](#how-do-i-declare-that-something-can-be-either-byte-string-or-unicode)
   * [I'm trying to use a mixin, but pytype raises errors about it. What should I do?](#im-trying-to-use-a-mixin-but-pytype-raises-errors-about-it-what-should-i-do)
   * [Why is pytype taking so long?](#why-is-pytype-taking-so-long)
   * [How do I disable all pytype checks for a particular file?](#how-do-i-disable-all-pytype-checks-for-a-particular-file)
   * [How do I disable all pytype checks for a particular import?](#how-do-i-disable-all-pytype-checks-for-a-particular-import)
   * [How do I write code that is seen by pytype but ignored at runtime?](#how-do-i-write-code-that-is-seen-by-pytype-but-ignored-at-runtime)
   * [How do I silence overzealous pytype errors when adding multiple types to a dict (or list, set, etc.)?](#how-do-i-silence-overzealous-pytype-errors-when-adding-multiple-types-to-a-dict-or-list-set-etc)
   * [How do I get type information for third-party libraries?](#how-do-i-get-type-information-for-third-party-libraries)
   * [Why doesn't str match against string iterables?](#why-doesnt-str-match-against-string-iterables)
   * [How can I automatically generate type annotations for an existing codebase?](#how-can-i-automatically-generate-type-annotations-for-an-existing-codebase)
   * [How do I annotate *args and **kwargs?](#how-do-i-annotate-args-and-kwargs)
   * [Why are signature mismatches in subclasses bad? {#signature-mismatch}](#why-are-signature-mismatches-in-subclasses-bad-signature-mismatch)
   * [What is the nothing type?](#what-is-the-nothing-type)
   * [What does ... mean in a type annotation?](#what-does--mean-in-a-type-annotation)

<!-- Created by https://github.com/ekalinin/github-markdown-toc -->
<!-- Added by: rechen, at: Tue Dec  5 01:23:50 PM PST 2023 -->

<!--te-->

## How is pytype different from other type checkers?

pytype has the ability to infer types for unannotated code. For more
information, check out our [typing FAQ][typing-faq].

## Can I find out what pytype thinks the type of my expression is?

Yes, insert `reveal_type(expr)` as a statement inside your code. This will cause
pytype to emit an error that will describe the type of `expr`.

If you would like to ensure that pytype's view of a type matches what you expect
it to be, use `assert_type(expr, expected-type)` or `assert_type(expr,
'expected-type')`. Note that the string version matches on the string pytype uses
to display the type, so you might have to tweak your expected type a bit to
eliminate false positives (e.g. `assert_type(x, 'foo.A')` might fail because
pytype thinks `x` is of type `bar.foo.A`, due to fully qualifying imports and
resolving aliases, but `assert_type(x, foo.A)` should work even if `foo` is
an alias for `bar.foo`).

To simply verify that pytype has inferred some type for an expression, and not
fallen back to `Any`, use `assert_type(x)` without the second argument.

If you would like to leave the `assert_type` statement in your code (rather than
adding it, running pytype, and removing it), add `from pytype_extensions import
assert_type` to your module.

## How do I reference a type from within its definition? (Forward References)

To reference a type from within its definition (e.g. when a method's return type
is an instance of the class to which the method belongs), specify the type as a
string. This will be resolved later by pytype. For example:

```python
class Person(object):
  def CreatePerson(name: str) -> 'Person':
    ...
```

Alternatively you can add a `__future__.annotations` import to reference the
type without quotes:

```python
from __future__ import annotations

class Person(object):
  def CreatePerson(name: str) -> Person:  # no quotes needed
    ...
```

Note: This import enables [PEP 563](https://www.python.org/dev/peps/pep-0563/),
a previously accepted PEP that has since been superseded by
[PEP 649](https://peps.python.org/pep-0649/). PEP 563's behavior will eventually
be deprecated and removed. However, as of May 2023, a `__future__` import for
PEP 649 is not yet available, so enabling PEP 563 is the best way to avoid
quoted types.

## I'm dynamically populating a class / module using `setattr` or by modifying `locals()` / `globals()`. Now pytype complains about missing attributes or module members. How do I fix this?

Add `_HAS_DYNAMIC_ATTRIBUTES = True` to your class or module.

## Why didn't pytype catch that my program (might) pass an invalid argument to a function?

pytype accepts a function call if there's at least one argument combination that
works. For example,

```python
def f(x: float):
  return x
f(random.random() or 'foo')
```

is not considered an error, because `f()` works for `float`. I.e., the `str`
argument isn't considered. (This will change at some point in the future.) Note
that this is different to attribute checking, where e.g.

```python
(random.random() or 'foo').as_integer_ratio()
```

will indeed result in a type error.

## How do I declare that something can be either byte string or unicode?

Use `str` if it is conceptually a text object and `bytes | str` otherwise. See
the [style guide][style-guide-string-types] for more information.

## I'm trying to use a mixin, but pytype raises errors about it. What should I do?

This happens when a mixin expects the classes it is mixed into to define
particular functions. Let's say we have a `LoggerMixin` class that expects a
`name` method to be used in the log message:

```python
class LoggerMixin:
  ...  # Other initialization.
  def log(self, msg: str):
    self._log.print(f'{self.name()}: {msg}')
```

When pytype checks `LoggerMixin`, it will raise an error that `LoggerMixin` has
no method `name`. The solution is to make the mixin class have all the methods
it needs.

One way to do this is to create an abstract base class that defines the expected
API for the mixin:

```python
import abc
class LoggerMixinInterface(metaclass=abc.ABCMeta):
  @abc.abstractmethod
  def name(self) -> str:
    raise NotImplementedError

class LoggerMixin(LoggerMixinInterface):
  ...  # Other initialization
  def log(self, msg: str):
    self._log.print(f'{self.name()}: {msg}')

class Person(LoggerMixinInterface):
  ...  # Other initialization
  def name(self):
    return self._name
```

With this setup, pytype won't complain about `LoggerMixin.name`, and it's clear
that `LoggerMixin` should only be mixed into classes that implement `name`.

## Why is pytype taking so long?

If pytype is taking a long time on a file, the easiest workaround is to
[disable][how-do-i-disable-all-pytype-checks-for-a-particular-file] it with a
`skip-file` directive. Otherwise, there are a few things you can try to speed up
the analysis:

*   Split up the file. Anecdotally, pytype gets noticeable slower once a file
    grows past ~1500 lines.

*   Annotate parameter and return types of functions to speed up inference.

*   Simplify function inputs (e.g., by reducing the number of types in unions)
    to speed up checking.

*   Split complex variable initializations (i.e. with multiple if-else branches)
    into separate functions. Tracking multiple variable values across multiple
    conditional branches can quickly get unwieldy.

    <!-- bad -->
    ```python
    def foo(config: Config):
      if config.bar:
        a = config.bar.a()
      else:
        a = config.default()
      if config.baz:
        a = config.baz(a)
      # ... similar branching for `b` and `c` ...
      do_foo(a, b, c)
    ```

    <!-- good -->
    ```python
    def _get_a(config: Config) -> A:
      if config.bar:
        a = config.bar.a()
      else:
        a = config.default()
      if config.baz:
        a = config.baz(a)
      return a

    def foo(config: Config):
      a = _get_a(config)
      b = _get_b(config)
      c = _get_c(config)
      do_foo(a, b, c)
    ```

*   Add type annotations to large concrete data structures (e.g., a module-level
    dict of a hundred constants). pytype tracks individual values for some
    builtin data structures, which can quickly get unwieldy. Adding a type
    annotation will force pytype to treat the data structure as an abstract
    instance of its type:

    <!-- bad -->
    ```python
    # Depending on the size of the dictionary and the complexity of the contents,
    # pytype may time out analyzing it.
    MY_HUGE_DICT = {...}
    ```

    <!-- good -->
    ```python
    from typing import Any, Mapping
    # Pytype can use the type annotation rather than inferring a type from the
    # value, considerably speeding up analysis. Replace `Any` with more precise
    # types if possible.
    MY_HUGE_DICT: Mapping[Any, Any] = {...}
    ```

## How do I disable all pytype checks for a particular file?

You can use

```
# pytype: skip-file
```

at the start of the file to disable all checking for a particular file. Callers
will also see the APIs from this file having the type `Any`, but the rest of the
blaze target is still type-checked.

## How do I disable all pytype checks for a particular import?

You can use

```python
from typing import Any
import foo  # type: Any
```

to disable checking for module `foo`. Note that pytype will still verify that
`foo` is present among your target's dependencies. To disable that check as
well, replace `# type: Any` with `# type: ignore`.

## How do I write code that is seen by pytype but ignored at runtime?

You can nest it inside an `if typing.TYPE_CHECKING:` block. This is occasionally
needed to, for instance,
[conditionally import a module][style-guide-conditional-imports] that is only
used to provide type annotations.

Note that regardless of whether you use `TYPE_CHECKING`, if you're using a build
system, you'll need to list all modules you import as dependencies of your
target. That can lead to cycles in your build graph. Typically, that means that,
short of rearranging your source tree, you won't be able to annotate with that
specific type. You can typically work around the "inexpressible" type by
inserting `Any` where you would have used it. See the
[style guide][style-guide-circular-dependencies] for more information.

## How do I silence overzealous pytype errors when adding multiple types to a dict (or list, set, etc.)?

A common pattern is to use a dictionary as a container for values of many types,
for example:

```python
MY_REGISTRY = {
    "slot1": Class1,
    "slot2": Class2,
}
```

This will often cause pytype to produce errors for any operation that is not
valid on *all* of the types. To fix this, annotate the value type as `Any`:

```python
MY_REGISTRY: Dict[str, Any] = {
    ....
}
```

Note that if you modify the dictionary in a different scope from the one in
which it is defined, you may need to re-annotate it at the modification site to
indicate to pytype that you are intentionally doing something it deems unsafe.

## How do I get type information for third-party libraries?

The open-source version of pytype gets type information from the
[typeshed][typeshed] project. Pytype treats all imports from third-party (that
is, pip-installed) libraries that do not have stubs in typeshed as having type
`Any`. Note that pytype does not yet support the [PEP 561][pep-561-issue]
conventions for distributing and packaging type information.

## Why doesn't `str` match against string iterables?

As of early August 2021, Pytype introduced a check that forbids matching `str`
against the following types to prevent a common accidental bug:

*   `Iterable[str]`

*   `Sequence[str]`

*   `Collection[str]`

*   `Container[str]`

NOTE: `str` continues to match against general iterables of type `Any` (e.g.,
`Iterable[Any]`, `Sequence[Any]`, etc.).

If you wish to pass a string `s` into a function that expects a string iterable:

*   To iterate over the characters of `s`, use `iter(s)` or `list(s)`.

*   To create a list with `s` as the only element, use `[s]`.

If you are annotating a function parameter that expects both iterating over a
single string **and** multiple strings, you can use a union (expressed with `|`)
to explicitly allow this. For example,

```py
def f(x: str | Iterable[str]): ...

# Alternatively, if your function expects any kind of Iterable
def g(x: Iterable[Any]): ...
```

## How can I automatically generate type annotations for an existing codebase?

Rather than using generated type annotations, we suggest you embrace an
incremental approach of adding type annotations. Don't let the perfect be the
enemy of the good. While fully annotating your code will better realize the
full benefits of pytype, pytype's inferencer is pretty powerful even with few
or no type annotations.

When starting out, you can add some type annotations now and others later, so if
you feel like adding some, don't let a feeling of needing to add all stop you
from adding whichever few you want. In many cases, you don't need to annotate
everything and will have the most success annotating public code elements and
complicated private code elements.

## How do I annotate `*args` and `**kwargs`?

Varargs (`*args`) and keyword arguments (`**kwargs`) should be annotated with
the type of each individual argument.

Yes:

<!-- good -->
```python
def f(*args: int) -> int:
  return sum(args)

def g(**kwargs: int) -> int:
  return sum(kwargs.values())
```

No:

<!-- bad -->
```python
from typing import Mapping, Sequence

def f(*args: Sequence[int]) -> int:
  return sum(args)

def g(**kwargs: Mapping[str, int]) -> int:
  return sum(kwargs.values())
```

## Why are signature mismatches in subclasses bad? {#signature-mismatch}

A mismatch in the signatures of an overridden method in a superclass and an
overriding method in a subclass can cause the following problems:

*   A valid call to an overridden method can fail on a subclass instance.
    Example:

<!-- bad -->
```python

class A:
  def func(self, x: int) -> int:
    return x

class B(A):
  def func(self) -> int:  # signature-mismatch
    return 0

def f(a: A, x: int) -> int:
  return a.func(x)

a = B()
f(a, 0)
```

Fails with an error:

```
TypeError: func() missing 1 required positional argument: 'x'
```

*   A call to an overridden method on a subclass instance can have different
    results depending on whether the argument is passed by name or by position.
    Example:

<!-- bad -->
```python

class A:
  def func(self, x: int, y: int) -> int:
    return 0

class B(A):
  def func(self, y: int, x: int) -> int:  # signature-mismatch
    return x - y

def f(a: A, x: int, y: int) -> None:
  print(a.func(x, y))
  print(a.func(x=x, y=y))
  print(a.func(x, y=y))

a = B()
f(a, 2, 1)
```

Output:

```
-1
1
Traceback (most recent call last):
TypeError: func() got multiple values for argument 'y'
```

## What is the `nothing` type?

In error messages and type stubs generated by pytype, you may occasionally come
across a type called `nothing`. For example:

```python
def f() -> str:
  return []  # [bad-return-type]
             # Expected: str
             # Actually returned: List[nothing]
```

`nothing` represents an unknown type that has not yet been filled in. It
typically appears in the context of empty containers. It differs from `Any` in
that the union of `Any` with another type is `Any`, but the union of `nothing`
with another type is the other type.

Do not use `nothing` in type annotations; it is an internal detail of pytype's
inference engine.

## What does `...` mean in a type annotation?

`...` in a type annotation has several possible meanings:

*   As the first argument to `Callable`, `...` means that the Callable takes any
    number of arguments of any type, e.g.:

    ```python
    from collections.abc import Callable
    _FUNC: Callable[..., int]
    _FUNC()  # valid call
    _FUNC(0, x=42)  # also valid call
    ```

*   As an optional second argument to `tuple`, `...` means that the tuple has a
    specified element type but variable length, e.g.:

    ```python
    _TUPLE1: tuple[int]  # length 1 tuple of an int
    _TUPLE2: tuple[int, int]  # length 2 tuple of two ints
    _TUPLE3: tuple[int, ...]  # variable length tuple of ints
    ```

*   As a top-level annotation, `...` means that the type is inferred from the
    implementation, e.g.:

    ```python
    def f() -> ...:  # return type inferred as `int`
      return 0
    ```

    This is an experimental feature; see the
    [experimental features documentation][pytype-experimental] for details.

<!-- General references -->

[compatibility]: user_guide.md#compatibility
[how-do-i-disable-all-pytype-checks-for-a-particular-file]: #how-do-i-disable-all-pytype-checks-for-a-particular-file
[oss-pytype]: https://github.com/google/pytype
[pep-561-issue]: https://github.com/google/pytype/issues/151
[pytype-experimental]: support.md#experiments
[typeshed]: https://github.com/python/typeshed
[typing-faq]: typing_faq.md

<!-- References with different internal and external versions -->

[style-guide-circular-dependencies]: https://google.github.io/styleguide/pyguide.html#31914-circular-dependencies

[style-guide-conditional-imports]: https://google.github.io/styleguide/pyguide.html#31913-conditional-imports

[style-guide-string-types]: https://google.github.io/styleguide/pyguide.html#31911-string-types
