"""Loads abstract representations of imported objects."""

from typing import Any as _Any, Dict, Tuple, Type

from pytype import load_pytd
from pytype.pytd import pytd
from pytype.rewrite.abstract import abstract
from pytype.rewrite.overlays import special_builtins


class Constants:
  """Store of constants and singletons.

  Constants should be accessed via self[<raw value>], which creates the constant
  if it does not exist. Under the hood, constants are stored in self._consts.

  Singletons are stored in self.singles and should be accessed via
  self.singles[<name>]. For convenience, the Any singleton can also be accessed
  as self.Any.
  """

  _SINGLETONS = ('Any', '__build_class__', 'Never', 'NULL')

  def __init__(self, ctx: abstract.ContextType):
    self._ctx = ctx
    self._consts: Dict[_Any, abstract.PythonConstant] = {}
    self.singles: Dict[str, abstract.Singleton] = {}

    for single in self._SINGLETONS:
      self.singles[single] = abstract.Singleton(
          ctx, single, allow_direct_instantiation=True)
    # We use Any all the time, so alias it for convenience.
    self.Any = self.singles['Any']  # pylint: disable=invalid-name

  def __getitem__(self, const: _Any):
    if const not in self._consts:
      self._consts[const] = abstract.PythonConstant(
          self._ctx, const, allow_direct_instantiation=True)
    return self._consts[const]


class AbstractLoader:
  """Abstract loader."""

  def __init__(self, ctx: abstract.ContextType, pytd_loader: load_pytd.Loader):
    self._ctx = ctx
    self._pytd_loader = pytd_loader

    self.consts = Constants(ctx)
    self._special_builtins = {
        'assert_type': special_builtins.AssertType(self._ctx),
    }
    self._special_builtins['NoneType'] = self.consts[None]

  def _load_pytd_node(self, pytd_node: pytd.Node) -> abstract.BaseValue:
    if isinstance(pytd_node, pytd.Class):
      return self._ctx.abstract_converter.pytd_class_to_value(pytd_node)
    elif isinstance(pytd_node, pytd.Function):
      return self._ctx.abstract_converter.pytd_function_to_value(pytd_node)
    elif isinstance(pytd_node, pytd.Constant):
      typ = self._ctx.abstract_converter.pytd_type_to_value(pytd_node.type)
      return typ.instantiate()
    elif isinstance(pytd_node, pytd.Alias):
      return self._ctx.abstract_converter.pytd_alias_to_value(pytd_node)
    else:
      raise NotImplementedError(f'I do not know how to load {pytd_node}')

  def load_builtin(self, name: str) -> abstract.BaseValue:
    if name in self._special_builtins:
      return self._special_builtins[name]
    pytd_node = self._pytd_loader.lookup_pytd('builtins', name)
    if isinstance(pytd_node, pytd.Constant):
      # This usage of eval is safe, as we've already checked that this is the
      # name of a builtin constant.
      return self.consts[eval(name)]  # pylint: disable=eval-used
    return self._load_pytd_node(pytd_node)

  def load_value(self, module: str, name: str) -> abstract.BaseValue:
    if module == 'builtins':
      return self.load_builtin(name)
    pytd_node = self._pytd_loader.lookup_pytd(module, name)
    return self._load_pytd_node(pytd_node)

  def get_module_globals(self) -> Dict[str, abstract.BaseValue]:
    """Gets a module's initial global namespace."""
    return {
        # TODO(b/324464265): Represent __builtins__ as a module.
        '__builtins__': abstract.Module(self._ctx, 'builtins'),
        '__name__': self.consts['__main__'],
        '__file__': self.consts[self._ctx.options.input],
        '__doc__': self.consts[None],
        '__package__': self.consts[None],
    }

  def load_raw_type(self, typ: Type[_Any]) -> abstract.BaseValue:
    """Converts a raw type to an abstract value.

    Args:
      typ: The type.

    Returns:
      The abstract representation of the type. For example, when passed `int`,
      this function returns `abstract.SimpleClass(int)`.
    """
    if typ is type(None):
      return self.consts[None]
    pytd_node = self._pytd_loader.lookup_pytd(typ.__module__, typ.__name__)
    return self._load_pytd_node(pytd_node)

  def build_tuple(self, const: Tuple[_Any, ...]) -> abstract.Tuple:
    """Convert a raw constant tuple to an abstract value."""
    ret = []
    for e in const:
      if isinstance(e, tuple):
        ret.append(self.build_tuple(e).to_variable())
      else:
        ret.append(self.consts[e].to_variable())
    return abstract.Tuple(self._ctx, tuple(ret))
