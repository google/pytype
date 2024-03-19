"""Basic datatypes for function definitions and call args."""

import abc
import dataclasses
from typing import Dict, List, Mapping, Optional, Tuple

from pytype.types import base


@dataclasses.dataclass(frozen=True)
class Signature:
  """Representation of a Python function signature.

  Attributes:
    name: Name of the function.
    param_names: A tuple of positional parameter names. This DOES include
      positional-only parameters and does NOT include keyword-only parameters.
    posonly_count: Number of positional-only parameters. (Python 3.8)
    varargs_name: Name of the varargs parameter. (The "args" in *args)
    kwonly_params: Tuple of keyword-only parameters. (Python 3)
      E.g. ("x", "y") for "def f(a, *, x, y=2)". These do NOT appear in
      param_names. Ordered like in the source file.
    kwargs_name: Name of the kwargs parameter. (The "kwargs" in **kwargs)
    defaults: Dictionary, name to value, for all parameters with default values.
    annotations: A dictionary of type annotations. (string to type)
    posonly_params: Tuple of positional-only parameters (i.e., the first
      posonly_count names in param_names).
  """
  name: str
  param_names: Tuple[str, ...]
  posonly_count: int
  varargs_name: Optional[str]
  kwonly_params: Tuple[str, ...]
  kwargs_name: Optional[str]
  defaults: Mapping[str, base.Variable]
  annotations: Mapping[str, base.BaseValue]


@dataclasses.dataclass(eq=True, frozen=True)
class Args:
  """Represents the parameters of a function call.

  Attributes:
    posargs: The positional arguments. A tuple of base.Variable.
    namedargs: The keyword arguments. A dictionary, mapping strings to
      base.Variable.
    starargs: The *args parameter, or None.
    starstarargs: The **kwargs parameter, or None.
  """

  posargs: Tuple[base.Variable, ...]
  namedargs: Dict[str, base.Variable]
  starargs: Optional[base.Variable] = None
  starstarargs: Optional[base.Variable] = None


@dataclasses.dataclass(eq=True, frozen=True)
class Arg:
  """A single function argument. Used for error handling."""
  name: str
  value: base.Variable
  typ: base.BaseValue


class Function(base.BaseValue, abc.ABC):
  """Base class for representation of python functions."""

  @property
  @abc.abstractmethod
  def name(self) -> str:
    """Function name (or placeholder for anonymous functions)."""

  @abc.abstractmethod
  def signatures(self) -> List[Signature]:
    """All signatures of this function."""

  @property
  @abc.abstractmethod
  def decorators(self) -> List[str]:
    """Function decorators."""
