"""Implementation of the types in Python 3's typing.py."""

# pylint's detection of this is error-prone:
# pylint: disable=unpacking-non-sequence


from pytype import abstract
from pytype.pytd import pep484


class TypingOverlay(abstract.Module):
  """A representation of the 'typing' module that allows custom overlays."""

  is_lazy = True  # uses _convert_member

  def __init__(self, vm, node, real_module):
    super(TypingOverlay, self).__init__(vm, node, "typing", typing_overload)
    self.real_module = real_module

  def _convert_member(self, name, m):
    return m(name, self.vm, self.vm.root_cfg_node).to_variable(
        self.vm.root_cfg_node, name)

  def get_module(self, name):
    if name in typing_overload:
      return self
    else:
      return self.real_module


def _maybe_extract_tuple(convert, node, t):
  """Returns a tuple of Variables."""
  values = t.Data(node)
  if len(values) > 1:
    return (t,)
  v, = values
  if not (v.cls and v.cls.data == convert.tuple_type.data):
    return (t,)
  if not isinstance(v, abstract.AbstractOrConcreteValue):
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
        # We don't have access to the name that we're annotating, so we'll use
        # the name of the type with which it's being annotated instead.
        self.vm.errorlog.invalid_annotation(self.vm.frame.current_opcode,
                                            self.name, "Must be constant")
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
    if len(inner) != len(self.type_param_names):
      error = "Expected %d parameter(s), got %d" % (
          len(self.type_param_names), len(inner))
      self.vm.errorlog.invalid_annotation(
          self.vm.frame.current_opcode, self.name, error)
    params = {name: inner[i] if i < len(inner) else self.vm.convert.unsolvable
              for i, name in enumerate(self.type_param_names)}
    return abstract.ParameterizedClass(self.base_type, params, self.vm)


def build_container(name, vm, node):
  if name in pep484.PEP484_CAPITALIZED:
    pytd_name = "__builtin__." + name.lower()
  else:
    pytd_name = "typing." + name
  pytd_base = vm.lookup_builtin(pytd_name)
  base = vm.convert.convert_constant_to_value(
      pytd_base.name, pytd_base, {}, vm.root_cfg_node)
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
  del node
  vm.errorlog.not_supported_yet(vm.frame.current_opcode, name)
  return abstract.Unknown(vm)


# TODO(rechen): There are a lot of other generics in typing.pytd; do they all
# need to be added here?
typing_overload = {
    # Containers
    "Dict": build_container,
    "FrozenSet": build_container,
    "Generator": build_container,
    "List": build_container,
    "Sequence": build_container,
    "Set": build_container,
    # Others
    "Any": build_any,
    "Generic": lambda name, vm, _: abstract.get_unsupported(name, vm),
    "NamedTuple": build_namedtuple,
    "Optional": build_optional,
    "TypeVar": build_typevar,
    "Union": Union,
}
