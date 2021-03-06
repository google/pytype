"""Apply decorators to classes and functions."""

from pytype.pytd import base_visitor
from pytype.pytd import pytd
from pytype.pytd.codegen import dataclass


class DecorateClassVisitor(base_visitor.Visitor):
  """Apply class decorators."""

  def VisitClass(self, cls):
    return _process_class(cls)


def _decorate_class(cls: pytd.Class, decorator: str) -> pytd.Class:
  """Apply a single decoator to a class."""
  if decorator == "dataclasses.dataclass":
    return dataclass.make_dataclass(cls)
  else:
    # do nothing for unknown decorators
    return cls


def _process_class(cls: pytd.Class) -> pytd.Class:
  """Apply all decorators to a class."""
  for decorator in reversed(cls.decorators):
    cls = _decorate_class(cls, decorator.type.name)  # pytype: disable=attribute-error
  return cls
