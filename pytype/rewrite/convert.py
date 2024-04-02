"""Conversion from pytd to abstract representations of Python values."""

from typing import Any, Dict, Tuple, Type

from pytype.pytd import pytd
from pytype.rewrite.abstract import abstract
from pytype.rewrite.overlays import special_builtins


class _Cache:

  def __init__(self):
    self.classes = {}
    self.funcs = {}
    self.types = {}


class AbstractConverter:
  """Pytd -> abstract converter."""

  def __init__(self, ctx: abstract.ContextType):
    self._ctx = ctx
    self._cache = _Cache()

  # TODO(b/324464265): Populate from builtins.pytd and move out of convert.py.
  def get_module_globals(
      self, python_version: Tuple[int, int]) -> Dict[str, abstract.BaseValue]:
    """Gets a module's initial global namespace, including builtins."""
    del python_version  # not yet used
    return {
        '__name__': self._ctx.singles.Any,
        'assert_type': special_builtins.AssertType(self._ctx),
        'int': abstract.SimpleClass(
            self._ctx, name='int', module='builtins', members={}),
    }

  def pytd_class_to_value(self, cls: pytd.Class) -> abstract.SimpleClass:
    """Converts a pytd class to an abstract class."""
    if cls in self._cache.classes:
      return self._cache.classes[cls]
    # TODO(b/324464265): Handle keywords, bases, decorators, slots, template
    module, _, name = cls.name.rpartition('.')
    members = {}
    abstract_class = abstract.SimpleClass(
        ctx=self._ctx,
        name=name,
        members=members,
        module=module or None)
    # Cache the class early so that references to it in its members don't cause
    # infinite recursion.
    self._cache.classes[cls] = abstract_class
    # TODO(b/324464265): For now, don't convert the bodies of builtin classes
    # because they contain lots of stuff the converter doesn't yet support.
    if not cls.name.startswith('builtins.'):
      for method in cls.methods:
        abstract_class.members[method.name] = (
            self.pytd_function_to_value(method))
      for constant in cls.constants:
        constant_type = self.pytd_type_to_value(constant.type)
        abstract_class.members[constant.name] = constant_type.instantiate()
      for nested_class in cls.classes:
        abstract_class.members[nested_class.name] = (
            self.pytd_class_to_value(nested_class))
    return abstract_class

  def pytd_function_to_value(
      self, func: pytd.Function) -> abstract.PytdFunction:
    """Converts a pytd function to an abstract function."""
    if func in self._cache.funcs:
      return self._cache.funcs[func]
    module, _, name = func.name.rpartition('.')
    signatures = tuple(
        abstract.Signature.from_pytd(self._ctx, name, pytd_sig)
        for pytd_sig in func.signatures)
    abstract_func = abstract.PytdFunction(
        ctx=self._ctx,
        name=name,
        signatures=signatures,
        module=module or None,
    )
    self._cache.funcs[func] = abstract_func
    return abstract_func

  def pytd_type_to_value(self, typ: pytd.Type) -> abstract.BaseValue:
    """Converts a pytd type to an abstract value.

    Args:
      typ: The type.

    Returns:
      The abstract representation of the type. For example, when passed
      `pytd.ClassType(pytd.Class(int))`, this function returns
      `abstract.SimpleClass(int)`.
    """
    if typ not in self._cache.types:
      self._cache.types[typ] = self._pytd_type_to_value(typ)
    return self._cache.types[typ]

  def _pytd_type_to_value(self, typ: pytd.Type) -> abstract.BaseValue:
    """Helper for pytd_type_to_value."""
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
    return abstract.SimpleClass(self._ctx, typ.__name__, {}, typ.__module__)
