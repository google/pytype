"""Loads abstract representations of imported objects."""

from typing import Any, Dict, Type

from pytype import load_pytd
from pytype.pytd import pytd
from pytype.rewrite.abstract import abstract
from pytype.rewrite.overlays import special_builtins


class AbstractLoader:
  """Abstract loader."""

  # Core constants used by pytype internals
  _CONSTANTS = (None,)
  _SINGLETONS = ('Any', '__build_class__', 'Never', 'NULL')

  def __init__(self, ctx: abstract.ContextType, pytd_loader: load_pytd.Loader):
    self._ctx = ctx
    self._pytd_loader = pytd_loader

    self.consts = {}
    for const in self._CONSTANTS:
      self.consts[str(const)] = abstract.PythonConstant(ctx, const)
    for single in self._SINGLETONS:
      self.consts[single] = abstract.Singleton(ctx, single)

    self._special_builtins = {
        'assert_type': special_builtins.AssertType(self._ctx),
    }
    for const in self._CONSTANTS:
      self._special_builtins[str(const)] = self.consts[str(const)]
    self._special_builtins['NoneType'] = self.consts['None']

  def _load_pytd_node(self, module: str, name: str) -> abstract.BaseValue:
    pytd_node = self._pytd_loader.lookup_pytd(module, name)
    if isinstance(pytd_node, pytd.Class):
      return self._ctx.abstract_converter.pytd_class_to_value(pytd_node)
    elif isinstance(pytd_node, pytd.Function):
      return self._ctx.abstract_converter.pytd_function_to_value(pytd_node)
    elif isinstance(pytd_node, pytd.Constant):
      typ = self._ctx.abstract_converter.pytd_type_to_value(pytd_node.type)
      return typ.instantiate()
    else:
      raise NotImplementedError(f'I do not know how to load {pytd_node}')

  def load_builtin_by_name(self, name: str) -> abstract.BaseValue:
    if name in self._special_builtins:
      return self._special_builtins[name]
    return self._load_pytd_node('builtins', name)

  def get_module_globals(self) -> Dict[str, abstract.BaseValue]:
    """Gets a module's initial global namespace."""
    return {
        # TODO(b/324464265): Represent __builtins__ as a module.
        '__builtins__': self.consts['Any'],
        '__name__': abstract.PythonConstant(self._ctx, '__main__'),
        '__file__': abstract.PythonConstant(self._ctx, self._ctx.options.input),
        '__doc__': self.consts['None'],
        '__package__': self.consts['None'],
    }

  def load_raw_type(self, typ: Type[Any]) -> abstract.BaseValue:
    """Converts a raw type to an abstract value.

    Args:
      typ: The type.

    Returns:
      The abstract representation of the type. For example, when passed `int`,
      this function returns `abstract.SimpleClass(int)`.
    """
    if typ is type(None):
      return self.consts['None']
    return self._load_pytd_node(typ.__module__, typ.__name__)
