"""Abstract types used internally by pytype."""

from typing import Any, Dict, Sequence

import immutabledict

from pytype.rewrite.abstract import base


# Type aliases
_Variable = base.AbstractVariableType


class ConstKeyDict(base.BaseValue):
  """Dictionary with constant literal keys.

  Used by the python interpreter to construct function args.
  """

  def __init__(self, ctx: base.ContextType, constant: Dict[Any, _Variable]):
    super().__init__(ctx)
    assert isinstance(constant, dict), constant
    self.constant = constant

  def __repr__(self):
    return f"ConstKeyDict({self.constant!r})"

  @property
  def _attrs(self):
    return (immutabledict.immutabledict(self.constant),)


class Splat(base.BaseValue):
  """Representation of unpacked iterables.

  When building a tuple for a function call, we preserve splats as elements
  in a concrete tuple (e.g. f(x, *ys, z) gets called with the concrete tuple
  (x, *ys, z) in starargs) and let the function arg matcher unpack them.
  """

  def __init__(self, ctx: base.ContextType, iterable: Sequence[_Variable]):
    super().__init__(ctx)
    self.iterable = tuple(iterable)

  def __repr__(self):
    return f"splat({self.iterable!r})"

  @property
  def _attrs(self):
    return (self.iterable,)
