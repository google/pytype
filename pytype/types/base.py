"""Base types for values and variables."""

from typing import Any


# Base datatypes


class BaseValue:
  """The base class for abstract values.

  A BaseValue is pytype's internal representation of a python object.
  """


# Pytype wraps values in Variables, which contain bindings of named python
# variables or expressions to abstract values. Variables are an internal
# implementation detail that no external code should depend on; we define a
# Variable type alias here simply to use in type signatures.
Variable = Any
