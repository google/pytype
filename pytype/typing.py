"""Implementation of the types in Python 3's typing.py."""

# pylint's detection of this is error-prone:
# pylint: disable=unpacking-non-sequence


from pytype import abstract
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils


class TypingOverlay(abstract.Module):
  """A representation of the 'typing' module that allows custom overlays."""

  is_lazy = True  # uses _convert_member

  def __init__(self, vm, node, real_module):
    super(TypingOverlay, self).__init__(vm, node, "typing", typing_overload)
    self.real_module = real_module

  def _convert_member(self, name, m):
    return m(name, self.vm, self.vm.root_cfg_node).to_variable(
        self.vm.root_cfg_node, name)

  def get_attribute(self, node, name, valself=None, valcls=None):
    if name in typing_overload:
      return super(TypingOverlay, self).get_attribute(
          node, name, valself, valcls)
    else:
      return self.real_module.get_attribute(
          node, name, valself, valcls)


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


class Union(abstract.ValueWithSlots):
  """Implementation of typing.Union[...]."""

  def __init__(self, name, vm, node, elements=()):
    super(Union, self).__init__(vm.convert.type_type, vm, node)
    self.name = "Union"
    self.elements = elements
    self.set_slot("__getitem__", self.getitem_slot)

  def __str__(self):
    return "Union[" + ", ".join(str(n) for n in self.elements) + "]"

  def getitem_slot(self, node, slice_var):
    slice_tuple = _maybe_extract_tuple(self.vm.convert, node, slice_var)
    values = tuple(s.Data(node)[0] for s in slice_tuple)
    new_union = Union(self.name, self.vm, node, self.elements + values)
    return node, new_union.to_variable(node, "Union")

  def instantiate(self, node):
    n = self.vm.program.NewVariable(self.name)
    for e in self.elements:
      instance = e.instantiate(node)
      n.PasteVariable(instance, node)
    return n

  def match_var_against(self, var, subst, node, view):
    for element in self.elements:
      new_subst = abstract.match_var_against_type(
          var, element, subst, node, view)
      if new_subst is not None:
        return new_subst

  def get_instance_type(self, node, instance=None, seen=None):
    return pytd.UnionType(tuple(
        e.get_instance_type(node, seen=seen)
        for e in self.elements))


class _Container(abstract.ValueWithSlots):
  """Implementation of typing.X[...]."""

  TYPE_PARAM_NAMES = ()

  def __init__(self, name, vm, node, inner=None):
    # TODO(kramm): type_type is wrong. Correct would be "typing.GenericMeta".
    # But in the output, we'd want this to become an alias.
    super(_Container, self).__init__(vm.convert.type_type, vm, node)
    self.name = name
    self.inner = inner
    self.set_slot("__getitem__", self.getitem_slot)

  def getitem_slot(self, node, inner):
    inner = _maybe_extract_tuple(self.vm.convert, node, inner)
    new_list = self.__class__(self.name, self.vm, node, inner)
    return node, new_list.to_variable(node, self.name)

  def match_var_against(self, var, subst, node, view):
    new_subst = None
    for cls in [c for clsv in self.concrete_classes
                for c in clsv.data]:
      new_subst = abstract.match_var_against_type(var, cls, subst, node, view)
      if new_subst is not None:
        subst = new_subst
        break
    else:
      return None
    if self.inner:
      v = view[var].data
      if (isinstance(v, abstract.SimpleAbstractValue) and
          all(param in v.type_parameters for param in self.type_param_names)):
        for param_name, type_param in zip(self.type_param_names, self.inner):
          inner = v.type_parameters[param_name]
          for formal in type_param.data:
            new_subst = abstract.match_var_against_type(
                inner, formal, subst, node, view)
            if new_subst is not None:
              subst = new_subst
              break
          else:
            return None
          return new_subst
      elif isinstance(v, (abstract.Unknown, abstract.Unsolvable)):
        return subst
    else:
      return subst

  def instantiate(self, node):
    concrete_class = self.concrete_classes[0]
    d = abstract.Instance(concrete_class, self.vm, node)
    for i, name in enumerate(self.type_param_names):
      if self.inner is not None:
        param = self.inner[i]
      else:
        param = self.vm.convert.create_new_unsolvable(node, name)
      d.overwrite_type_parameter(node, name, self.vm.instantiate(param, node))
    return d.to_variable(node, self.pytd_name)

  def get_instance_type(self, node, instance=None, seen=None):
    if self.inner:
      type_params = [pytd_utils.JoinTypes([i.get_instance_type(node, seen=seen)
                                           for i in inner.data])
                     for inner in self.inner
                    ]
      return pytd.GenericType(pytd.NamedType(self.pytd_name),
                              tuple(type_params))
    else:
      return pytd.NamedType(self.pytd_name)

  def __str__(self):
    if self.inner:
      list_entries = ", ".join(str(i.data[0]) for i in self.inner)
      return self.name + "[" + list_entries + "]"
    else:
      return self.name


class List(_Container):
  pytd_name = "__builtin__.list"
  type_param_names = ("T",)

  def __init__(self, name, vm, node, inner=None):
    super(List, self).__init__("List", vm, node, inner)
    self.concrete_classes = [self.vm.convert.list_type]

  def instantiate(self, node):
    if self.inner is not None:
      contained_type, = self.inner
      list_items = [self.vm.instantiate(contained_type, node)]
      return self.vm.convert.build_list(node, list_items)
    else:
      return self.vm.convert.build_list(node, [
          self.vm.convert.create_new_unsolvable(node, "inner")])


class Dict(_Container):
  pytd_name = "__builtin__.dict"
  type_param_names = ("K", "V")

  def __init__(self, name, vm, node, inner=None):
    super(Dict, self).__init__("Dict", vm, node, inner)
    self.concrete_classes = [self.vm.convert.dict_type]


class Sequence(_Container):
  pytd_name = "typing.Sequence"
  type_param_names = ("T",)

  def __init__(self, name, vm, node, inner=None):
    super(Sequence, self).__init__("Sequence", vm, node, inner)
    # TODO(kramm): These are incomplete:
    self.concrete_classes = [self.vm.convert.list_type,
                             self.vm.convert.tuple_type,
                             self.vm.convert.set_type]


def build_any(name, vm, node):
  del name
  del node
  return abstract.Unsolvable(vm)


def build_optional(name, vm, node):
  return Union(name, vm, node, (vm.convert.none_type.data[0],))


typing_overload = {
    "Union": Union,
    "List": List,
    "Dict": Dict,
    "Sequence": Sequence,
    "Optional": build_optional,
    "Any": build_any,
}
