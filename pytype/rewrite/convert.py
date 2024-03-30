"""Conversion from pytd to abstract representations of Python values."""

from typing import Any, Dict, Tuple, Type

from pytype.pytd import pytd
from pytype.rewrite.abstract import abstract
from pytype.rewrite.overlays import special_builtins


class AbstractConverter:
  """Pytd -> abstract converter."""

  def __init__(self, ctx: abstract.ContextType):
    self._ctx = ctx

  # TODO(b/324464265): Populate from builtins.pytd and move out of convert.py.
  def get_module_globals(
      self, python_version: Tuple[int, int]) -> Dict[str, abstract.BaseValue]:
    """Gets a module's initial global namespace, including builtins."""
    del python_version  # not yet used
    return {
        '__name__': self._ctx.singles.Any,
        'assert_type': special_builtins.AssertType(self._ctx),
        'int': abstract.SimpleClass(self._ctx, 'int', {}),
    }

  def pytd_class_to_value(self, cls: pytd.Class) -> abstract.SimpleClass:
    """Converts a pytd class to an abstract class."""
    return abstract.SimpleClass(self._ctx, cls.name, {})

  def pytd_function_to_value(
      self, func: pytd.Function) -> abstract.PytdFunction:
    """Converts a pytd function to an abstract function."""
    signatures = tuple(
        abstract.Signature.from_pytd(self._ctx, func.name, pytd_sig)
        for pytd_sig in func.signatures)
    return abstract.PytdFunction(self._ctx, func.name, signatures)

  def pytd_type_to_value(self, typ: pytd.Type) -> abstract.BaseValue:
    """Converts a pytd type to an abstract value.

    Args:
      typ: The type.

    Returns:
      The abstract representation of the type. For example, when passed
      `pytd.ClassType(pytd.Class(int))`, this function returns
      `abstract.SimpleClass(int)`.
    """
    if isinstance(typ, pytd.ClassType):
      return self.pytd_class_to_value(typ.cls)
    elif isinstance(typ, pytd.AnythingType):
      return self._ctx.singles.Any
    elif isinstance(typ, pytd.NothingType):
      return self._ctx.singles.Never
    elif isinstance(typ, (pytd.LateType,
                          pytd.Literal,
                          pytd.Annotated,
                          pytd.TypeParameter,
                          pytd.UnionType,
                          pytd.IntersectionType,
                          pytd.GenericType)):
      raise NotImplementedError(
          f'Abstract conversion not yet implemented for {typ}')
    else:
      raise ValueError(f'Cannot convert {typ} to an abstract value')

  def raw_type_to_value(self, typ: Type[Any]) -> abstract.BaseValue:
    """Converts a raw type to an abstract value.

    Args:
      typ: The type.

    Returns:
      The abstract representation of the type. For example, when passed `int`,
      this function returns `abstract.SimpleClass(int)`.
    """
    return abstract.SimpleClass(self._ctx, typ.__name__, {})
