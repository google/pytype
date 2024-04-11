"""Conversion from pytd to abstract representations of Python values."""

from pytype.pytd import pytd
from pytype.rewrite.abstract import abstract


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
      return self._ctx.consts.singles['Any']
    elif isinstance(typ, pytd.NothingType):
      return self._ctx.consts.singles['Never']
    elif isinstance(typ, pytd.UnionType):
      return abstract.Union(
          self._ctx, tuple(self._pytd_type_to_value(t) for t in typ.type_list))
    # TODO(b/324464265): Everything from this point onward is a dummy
    # implementation that needs to be replaced by a real one.
    elif isinstance(typ, pytd.GenericType):
      return self._pytd_type_to_value(typ.base_type)
    elif isinstance(typ, pytd.TypeParameter):
      return self._ctx.consts.Any
    elif isinstance(typ, pytd.Literal):
      return self._ctx.abstract_loader.load_raw_type(type(typ.value))
    elif isinstance(typ, pytd.Annotated):
      # We discard the Annotated wrapper for now, but we will need to keep track
      # of it because Annotated is a special form that can be used in generic
      # type aliases.
      return self._pytd_type_to_value(typ.base_type)
    elif isinstance(typ, (pytd.LateType, pytd.IntersectionType)):
      raise NotImplementedError(
          f'Abstract conversion not yet implemented for {typ}')
    else:
      raise ValueError(f'Cannot convert {typ} to an abstract value')

  def pytd_alias_to_value(self, alias: pytd.Alias) -> abstract.BaseValue:
    if isinstance(alias.type, pytd.Module):
      return abstract.Module(self._ctx, alias.type.module_name)
    raise NotImplementedError(
        f'Abstract conversion not yet implemented for {alias}')
