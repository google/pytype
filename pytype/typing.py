"""Implementation of the types in Python 3's typing.py."""

# pylint's detection of this is error-prone:
# pylint: disable=unpacking-non-sequence


from pytype import abstract
from pytype.pytd import pep484
from pytype.pytd import pytd


class TypingOverlay(abstract.Module):
  """A representation of the 'typing' module that allows custom overlays."""

  is_lazy = True  # uses _convert_member

  def __init__(self, vm, node):
    member_map = typing_overload.copy()
    ast = vm.loader.typing
    for cls in ast.classes:
      _, name = cls.name.rsplit(".", 1)
      if name not in member_map and pytd.IsContainer(cls) and cls.template:
        member_map[name] = build_container
    super(TypingOverlay, self).__init__(vm, node, "typing", member_map)
    self.real_module = vm.convert.constant_to_value(
        ast, subst={}, node=vm.root_cfg_node)

  def _convert_member(self, name, m):
    var = m(name, self.vm).to_variable(self.vm.root_cfg_node)
    self.vm.trace_module_member(self, name, var)
    return var

  def get_module(self, name):
    if name in self._member_map:
      return self
    else:
      return self.real_module

  def items(self):
    items = super(TypingOverlay, self).items()
    for name, item in self.real_module.items():
      if name not in self._member_map:
        items.append((name, item))
    return items


class Union(abstract.AnnotationClass):
  """Implementation of typing.Union[...]."""

  def __init__(self, name, vm, options=()):
    super(Union, self).__init__(name, vm)
    self.options = options

  def _build_value(self, node, inner):
    return abstract.Union(self.options + inner, self.vm)


class Callable(abstract.AnnotationContainer):

  def __init__(self, name, vm):
    base = abstract.get_atomic_value(vm.convert.function_type)
    super(Callable, self).__init__(name, vm, base)

  def _build_value(self, node, inner):
    # We don't do anything with Callable parameters yet.
    return self.base_cls


class TypeVarFunction(object):
  """Representation of typing.TypeVar, as a function."""

  def __init__(self, name, vm):
    self.name = name
    self.vm = vm

  def call(self, node, *args, **kwargs):
    """Call typing.TypeVar()."""
    if len(args) < 1:
      self.vm.errorlog.invalid_typevar(self.vm.frame.current_opcode,
                                       "Need name as first parameter")
      return node, self.vm.convert.unsolvable.to_variable(node)
    try:
      typevar_name = abstract.get_atomic_python_constant(args[0])
    except abstract.ConversionError:
      self.vm.errorlog.invalid_typevar(self.vm.frame.current_opcode,
                                       "Name must be a constant string")
      return node, self.vm.convert.unsolvable.to_variable(node)
    constraints = args[1:]
    bound = kwargs.get("bound")
    # TODO(kramm): These are variables. We should convert them to booleans.
    covariant = kwargs.get("covariant")
    contravariant = kwargs.get("contravariant")
    typevar = abstract.TypeVariable(typevar_name, self.vm, constraints,
                                    bound, covariant, contravariant)
    self.vm.trace_typevar(typevar_name, typevar)
    return node, typevar.to_variable(node)


def build_container(name, vm):
  if name in pep484.PEP484_CAPITALIZED:
    pytd_name = "__builtin__." + name.lower()
  else:
    pytd_name = "typing." + name
  base = vm.convert.name_to_value(pytd_name)
  return abstract.AnnotationContainer(name, vm, base)


def build_any(name, vm):
  del name
  return abstract.Unsolvable(vm)


# TODO(kramm): Do a full implementation of this.
def build_namedtuple(name, vm):
  del name
  return abstract.Unsolvable(vm)


def build_optional(name, vm):
  return Union(name, vm, (vm.convert.none_type.data[0],))


def build_typevar(name, vm):
  vm.errorlog.not_supported_yet(vm.frame.current_opcode, name)
  f = TypeVarFunction(name, vm)
  return abstract.NativeFunction("TypeVar", f.call, vm)


def build_generic(name, vm):
  vm.errorlog.not_supported_yet(vm.frame.current_opcode, name)
  return vm.convert.unsolvable


typing_overload = {
    "Any": build_any,
    "Callable": Callable,
    "Generic": build_generic,
    "NamedTuple": build_namedtuple,
    "Optional": build_optional,
    "TypeVar": build_typevar,
    "Union": Union,
}
