"""Apply decorators to classes and functions."""

from typing import List

from pytype.pytd import base_visitor
from pytype.pytd import pytd
from pytype.pytd.codegen import dataclass


_DECORATORS = {
    "dataclasses.dataclass": dataclass.make_dataclass
}


# NOTE: This needs to be called in the parser, otherwise the generated code will
# not have all the ast finalizing visitors from load_pytd applied to it.
class DecorateClassVisitor(base_visitor.Visitor):
  """Apply class decorators."""

  def VisitClass(self, cls):
    return _process_class(cls)


def _decorate_class(cls: pytd.Class, decorator: str) -> pytd.Class:
  """Apply a single decoator to a class."""
  factory = _DECORATORS.get(decorator, None)
  if factory:
    return factory(cls)
  else:
    # do nothing for unknown decorators
    return cls


def _decorator_names(cls: pytd.Class) -> List[str]:
  return [x.type.name for x in reversed(cls.decorators)]  # pytype: disable=attribute-error


def _process_class(cls: pytd.Class) -> pytd.Class:
  """Apply all decorators to a class."""
  for decorator in _decorator_names(cls):
    cls = _decorate_class(cls, decorator)
  return cls
