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
    self.real_module = vm.convert.construct_constant_from_value(
        ast.name, ast, subst={}, node=vm.root_cfg_node)

  def _convert_member(self, name, m):
    var = m(name, self.vm, self.vm.root_cfg_node).to_variable(
        self.vm.root_cfg_node)
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


def _maybe_extract_tuple(convert, node, t):
  """Returns a tuple of Variables."""
  values = t.Data(node)
  if len(values) > 1:
    return (t,)
  v, = values
  if not (v.cls and v.cls.data == convert.tuple_type.data):
    return (t,)
  if not isinstance(v, abstract.PythonConstant):
    return (t,)
  return v.pyval


class TypingClass(abstract.ValueWithSlots):
  """Base class of all classes in typing.py."""

  def __init__(self, name, vm, node):
    super(TypingClass, self).__init__(vm.convert.type_type, vm, node)
    self.name = name
    self.set_slot("__getitem__", self.getitem_slot)

  def getitem_slot(self, node, slice_var):
    inner = []
    for var in _maybe_extract_tuple(self.vm.convert, node, slice_var):
      if len(var.bindings) > 1:
        self.vm.errorlog.invalid_annotation(self.vm.frame.current_opcode, self,
                                            "Must be constant")
        inner.append(self.vm.convert.unsolvable)
      else:
        inner.append(var.bindings[0].data)
    value = self._build_value(node, tuple(inner))
    return node, value.to_variable(node)

  def _build_value(self, node, inner):
    raise NotImplementedError(self.__class__.__name__)


class Union(TypingClass):
  """Implementation of typing.Union[...]."""

  def __init__(self, name, vm, node, options=()):
    super(Union, self).__init__(name, vm, node)
    self.options = options

  def _build_value(self, node, inner):
    return abstract.Union(self.options + inner, self.vm)


class Container(TypingClass):
  """Implementation of typing.X[...]."""

  def __init__(self, name, vm, node, base_type):
    super(Container, self).__init__(name, vm, node)
    self.base_type = base_type
    self.type_param_names = tuple(t.name for t in base_type.pytd_cls.template)

  def _build_value(self, node, inner):
    if len(inner) > len(self.type_param_names):
      error = "Expected %d parameter(s), got %d" % (
          len(self.type_param_names), len(inner))
      self.vm.errorlog.invalid_annotation(
          self.vm.frame.current_opcode, self, error)
    params = {name: inner[i] if i < len(inner) else self.vm.convert.unsolvable
              for i, name in enumerate(self.type_param_names)}
    return abstract.ParameterizedClass(self.base_type, params, self.vm)


class Callable(Container):

  def __init__(self, name, vm, node):
    # Note that we cannot use vm.convert.function_type here, since our matcher
    # doesn't know that __builtin__.function and typing.Callable are the same.
    base = vm.convert.convert_name_to_value("typing.Callable")
    super(Callable, self).__init__(name, vm, node, base)

  def _build_value(self, node, inner):
    # We don't do anything with Callable parameters yet.
    return self.base_type


class Tuple(Container):

  def __init__(self, name, vm, node):
    base = abstract.get_atomic_value(vm.convert.tuple_type)
    super(Tuple, self).__init__(name, vm, node, base)

  def _build_value(self, node, inner):
    # Our tuples are homogeneous (for now).
    if len(inner) > 1:
      inner = (abstract.Union(inner, self.vm),)
    return super(Tuple, self)._build_value(node, inner)


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


def build_container(name, vm, node):
  if name in pep484.PEP484_CAPITALIZED:
    pytd_name = "__builtin__." + name.lower()
  else:
    pytd_name = "typing." + name
  base = vm.convert.convert_name_to_value(pytd_name)
  return Container(name, vm, node, base)


def build_any(name, vm, node):
  del name
  del node
  return abstract.Unsolvable(vm)


# TODO(kramm): Do a full implementation of this.
def build_namedtuple(name, vm, node):
  del name
  del node
  return abstract.Unsolvable(vm)


def build_optional(name, vm, node):
  return Union(name, vm, node, (vm.convert.none_type.data[0],))


def build_typevar(name, vm, node):
  vm.errorlog.not_supported_yet(vm.frame.current_opcode, name)
  f = TypeVarFunction(name, vm)
  return abstract.NativeFunction("TypeVar", f.call, vm, node)


def build_generic(name, vm, node):
  del node
  vm.errorlog.not_supported_yet(vm.frame.current_opcode, name)
  return vm.convert.unsolvable


typing_overload = {
    "Any": build_any,
    "Callable": Callable,
    "Generic": build_generic,
    "NamedTuple": build_namedtuple,
    "Optional": build_optional,
    "Tuple": Tuple,
    "TypeVar": build_typevar,
    "Union": Union,
}
