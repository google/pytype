"""Abstract types used internally by pytype."""

import collections
from typing import Dict, Tuple

import immutabledict

from pytype.rewrite.abstract import base


# Type aliases
_Variable = base.AbstractVariableType


class FunctionArgTuple(base.BaseValue):
  """Representation of a function arg tuple."""

  def __init__(self, ctx: base.ContextType, constant: Tuple[_Variable, ...]):
    super().__init__(ctx)
    assert isinstance(constant, tuple), constant
    self.constant = constant

  def __repr__(self):
    return f"FunctionArgTuple({self.constant!r})"

  @property
  def _attrs(self):
    return (self.constant,)


class FunctionArgDict(base.BaseValue):
  """Representation of a function kwarg dict."""

  def __init__(
      self,
      ctx: base.ContextType,
      constant: Dict[str, _Variable],
      indefinite: bool = False
  ):
    self._ctx = ctx
    self._check_keys(constant)
    self.constant = constant
    self.indefinite = indefinite

  @classmethod
  def any_kwargs(cls, ctx: base.ContextType):
    """Return a new kwargs dict with only indefinite values."""
    return cls(ctx, {}, indefinite=True)

  def _check_keys(self, constant: Dict[str, _Variable]):
    """Runtime check to ensure the invariant."""
    assert isinstance(constant, dict), constant
    if not all(isinstance(k, str) for k in constant):
      raise ValueError("Passing a non-string key to a function arg dict")

  def __repr__(self):
    indef = "+" if self.indefinite else ""
    return f"FunctionArgDict({indef}{self.constant!r})"

  @property
  def _attrs(self):
    return (immutabledict.immutabledict(self.constant), self.indefinite)


class Splat(base.BaseValue):
  """Representation of unpacked iterables.

  When building a tuple for a function call, we preserve splats as elements
  in a concrete tuple (e.g. f(x, *ys, z) gets called with the concrete tuple
  (x, *ys, z) in starargs) and let the function arg matcher unpack them.
  """

  def __init__(self, ctx: base.ContextType, iterable: base.BaseValue):
    super().__init__(ctx)
    self.iterable = iterable

  @classmethod
  def any(cls, ctx: base.ContextType):
    return cls(ctx, ctx.consts.Any)

  def get_concrete_iterable(self):
    if (isinstance(self.iterable, base.PythonConstant) and
        isinstance(self.iterable.constant, collections.abc.Iterable)):
      return self.iterable.constant
    else:
      raise ValueError("Not a concrete iterable")

  def __repr__(self):
    return f"splat({self.iterable!r})"

  @property
  def _attrs(self):
    return (self.iterable,)
