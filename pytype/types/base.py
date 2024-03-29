"""Base types for values and variables."""

from typing import Any

from pytype.pytd import pytd


# Base datatypes


# NOTE: This cannot inherit from abc.ABC due to a conflict with the custom
# metaclasses we use in some of our abstract classes.
class BaseValue:
  """The base class for abstract values.

  A BaseValue is pytype's internal representation of a python object.
  """
  name: str
  cls: 'BaseValue'

  @property
  def ctx(self) -> Any:
    """All abstract objects contain a reference to the VM context."""
    raise NotImplementedError()

  def to_pytd_instance(self, *args, **kwargs) -> pytd.Type:
    """Get the pytd type an instance of us would have."""
    raise NotImplementedError()

  def is_late_annotation(self) -> bool:
    raise NotImplementedError()

  def is_concrete(self) -> bool:
    raise NotImplementedError()


# Pytype wraps values in Variables, which contain bindings of named python
# variables or expressions to abstract values. Variables are an internal
# implementation detail that no external code should depend on; we define a
# Variable type alias here simply to use in type signatures.
Variable = Any
