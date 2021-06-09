# Lint as: python2, python3
"""Type system extensions for use with pytype."""
from __future__ import google_type_annotations

import typing
from typing import Text, Dict, Any, TypeVar, Callable


if typing.TYPE_CHECKING:

  _GenericCallable = TypeVar('_GenericCallable', bound=Callable[..., Any])

  class Decorator(object):
    """A type annotation for decorators that do not change signatures.

    This is a stand-in for using `Callable[[T], T]` to represent a decorator.

    Given a decorator function, which takes in a callable and returns a callable
    with the same signature, apply this class as a decorator to that function.
    This can also be used for decorator factories.

    Examples:

    Plain decorator (decorator matches Callable[[T], T]):

    >>> @pytype_extensions.Decorator
    ... def MyDecorator(func):
    ...   def wrapper(...):
    ...     ...
    ...   return wrapper

    Decorator factory (factory matches Callable[..., Callable[[T], T]]):

    >>> def MyDecoratorFactory(foo: int) -> pytype_extensions.Decorator:
    ...   @pytype_extensions.Decorator
    ...   def MyDecorator(func):
    ...     def Wrapper(*args, **kwargs):
    ...       return func(foo, *args, **kwargs)
    ...     return Wrapper
    ...   return MyDecorator

    Note for the above example: the return type annotation (first line) is the
    most important one; it indicates to callers that MyDecoratorFactory is
    returning a decorator. The "@pytype_extensions.Decorator" annotation (second
    line) indicates to pytype that MyDecorator is a Decorator; without it, you
    would need to add "pytype: disable=bad-return-type" on the final line.

    This class only exists at build time, for typechecking. At runtime, the
    'Decorator' member of this module is a simple identity function (see below).

    More information: pytype-decorators

    Shortlink: pytype_extensions.Decorator
    """
    # pylint: disable=pointless-statement, line-too-long, unused-argument

    def __init__(self, decorator: Callable[[_GenericCallable], _GenericCallable]):
      ...

    def __call__(self, func: _GenericCallable) -> _GenericCallable:
      ...  # pytype: disable=bad-return-type

else:
  # At runtime, Decorator is a simple identify function that returns its input.
  Decorator = lambda d: d


def assert_type(*unused_args):
  """Prevent runtime errors from assert_type statements.

  assert_type is handled internally by pytype at type checking time; it should
  do nothing at runtime.
  """
