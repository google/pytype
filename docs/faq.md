# FAQ

<!--ts-->
   * [FAQ](#faq)
      * [How is pytype different from other type checkers?](#how-is-pytype-different-from-other-type-checkers)
      * [Can I find out what pytype thinks the type of my expression is?](#can-i-find-out-what-pytype-thinks-the-type-of-my-expression-is)
      * [How do I reference a type from within its definition? (Forward References)](#how-do-i-reference-a-type-from-within-its-definition-forward-references)
      * [I'm dynamically populating a class / module using setattr or by modifying <code>locals()</code> / <code>globals()</code>. Now pytype complains about missing attributes or module members. How do I fix this?](#im-dynamically-populating-a-class--module-using-setattr-or-by-modifying-locals--globals-now-pytype-complains-about-missing-attributes-or-module-members-how-do-i-fix-this)
      * [Why didn't pytype catch that my program (might) pass an invalid argument to a function?](#why-didnt-pytype-catch-that-my-program-might-pass-an-invalid-argument-to-a-function)
      * [How do I declare that something can be either byte string or unicode?](#how-do-i-declare-that-something-can-be-either-byte-string-or-unicode)
      * [I'm trying to use a mixin, but pytype raises errors about it. What should I do?](#im-trying-to-use-a-mixin-but-pytype-raises-errors-about-it-what-should-i-do)
      * [Why is pytype taking so long?](#why-is-pytype-taking-so-long)
      * [How do I disable all pytype checks for a particular file?](#how-do-i-disable-all-pytype-checks-for-a-particular-file)
      * [How do I disable all pytype checks for a particular import?](#how-do-i-disable-all-pytype-checks-for-a-particular-import)
      * [How do I write code that is seen by pytype but ignored at runtime?](#how-do-i-write-code-that-is-seen-by-pytype-but-ignored-at-runtime)
      * [How do I silence overzealous pytype errors when adding multiple types to a dict (or list, set, etc.)?](#how-do-i-silence-overzealous-pytype-errors-when-adding-multiple-types-to-a-dict-or-list-set-etc)
      * [How do I get type information for third-party libraries?](#how-do-i-get-type-information-for-third-party-libraries)
      * [Why can't I iterate over a string?](#why-cant-i-iterate-over-a-string)

<!-- Added by: rechen, at: 2021-08-05T17:23-07:00 -->

<!--te-->

## How is pytype different from other type checkers?

pytype has the ability to infer types for unannotated code. For more
information, check out:

* A [PyCon lightning talk][lightning-talk] comparing pytype and mypy,
another popular type checker. The slides are [here][lightning-talk-slides].
* A more detailed written discussion in a [Lobste.rs post][lobsters-comment].
* A [paper][type-system-paper] detailing pytype and mypy's differing views of
  python's type system.

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
string. This will be resolved later by PyType. For example:

```python
class Person(object):
  def CreatePerson(name: str) -> 'Person':
    ...
```

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

Use `str` if it is conceptually a text object and `typing.Union[bytes, str]`
otherwise. See the [style guide][style-guide-string-types] for more information.

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

* Split up the file. Anecdotally, pytype gets noticeable slower once a file
  grows past ~1500 lines.
* Annotate the return types of functions to speed up inference.
* Simplify function inputs (e.g., by reducing the number of types in unions) to
  speed up checking.
* Avoid large concrete data structures (e.g., a module-level dict of a hundred
  constants). pytype tracks individual values for some builtin data structures,
  which can quickly get unwieldy.

## How do I disable all pytype checks for a particular file?

You can use

```
# pytype: skip-file
```

at the start of the file to disable all checking for a particular file, while
still checking the rest of the blaze target that includes it.

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

## Why can't I iterate over a string?

As of early August 2021, Pytype introduced a check that forbids matching `str`
against the following types to prevent a common accidental bug:

*   `Iterable[str]`

*   `Sequence[str]`

*   `Collection[str]`

*   `Container[str]`

*   `Mapping[int, str]`

*   _`str` continues to match against the general `Iterable[Any]`,
    `Sequence[Any]`, etc._

If you wish to iterate over the characters of a string, first pass it into the
builtin `iter()` function or the `list()` constructor.

If you are annotating a function parameter that expects both iterating over a
single string **and** multiple strings, you can use `Union` to explicitly allow
this. For example,

```py
def f(x: Union[str, Iterable[str]]): ...

# Alternatively, if your function expects any kind of Iterable
def g(x: Iterable[Any]): ...
```

<!-- General references -->
[compatibility]: user_guide.md#compatibility
[how-do-i-disable-all-pytype-checks-for-a-particular-file]: #how-do-i-disable-all-pytype-checks-for-a-particular-file
[lightning-talk]: https://youtu.be/yFcCuinRVnU?t=2300
[lightning-talk-slides]: https://docs.google.com/presentation/d/1GYqLeLkknjYaYX2JrMzxX8LGw_rlO-6kTk-VNPVG9gY/edit?usp=sharing
[lobsters-comment]: https://lobste.rs/s/0uv5hy/how_quickly_find_type_issues_your_python#c_6ojqaj
[oss-pytype]: https://github.com/google/pytype
[pep-561-issue]: https://github.com/google/pytype/issues/151
[type-system-paper]: https://www.cs.rpi.edu/~milanova/docs/dls2020.pdf
[typeshed]: https://github.com/python/typeshed
[why-is-pytype-taking-so-long]: #why-is-pytype-taking-so-long

<!-- References with different internal and external versions -->

[style-guide-circular-dependencies]: https://google.github.io/styleguide/pyguide.html#31914-circular-dependencies

[style-guide-conditional-imports]: https://google.github.io/styleguide/pyguide.html#31913-conditional-imports

[style-guide-string-types]: https://google.github.io/styleguide/pyguide.html#31911-string-types
