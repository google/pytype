"""Implementation of the types in Python 3's typing.py."""


from pytype import abstract
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils


class TypingOverlay(abstract.Module):
  """A representaion of the 'typing' module that allows custom overlays."""

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
    slice_tuple = abstract.get_atomic_python_constant(slice_var)
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
    return pytd.UnionType([
        e.get_instance_type(node, seen=seen)
        for e in self.elements])


class _Container(abstract.ValueWithSlots):
  """Implementation of typing.X[...]."""

  def __init__(self, name, vm, node, inner=None):
    # TODO(kramm): type_type is wrong. Correct would be "typing.GenericMeta".
    # But in the output, we'd want this to become an alias.
    super(_Container, self).__init__(vm.convert.type_type, vm, node)
    self.name = name
    self.inner = inner
    self.set_slot("__getitem__", self.getitem_slot)

  def getitem_slot(self, node, inner):
    new_list = self.__class__(self.name, self.vm, node, inner)
    return node, new_list.to_variable(node, self.name)

  def instantiate(self, node):
    if self.inner:
      return self.vm.convert.build_list(node, [
          self.vm.instantiate(self.inner, node)])
    else:
      return self.vm.convert.build_list(node, [
          self.vm.convert.create_new_unknown(node, "inner")])

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
      # __builtins__.pytd always uses T as type parameter for sequence classes.
      if (isinstance(v, abstract.SimpleAbstractValue) and
          "T" in v.type_parameters):
        inner = v.type_parameters["T"]
        for formal in self.inner.data:
          new_subst = abstract.match_var_against_type(
              inner, formal, subst, node, view)
          if new_subst is not None:
            return new_subst
      elif isinstance(v, (abstract.Unknown, abstract.Unsolvable)):
        return subst
    else:
      return subst

  def get_instance_type(self, node, instance=None, seen=None):
    if self.inner:
      t = pytd_utils.JoinTypes([i.get_instance_type(node, seen=seen)
                                for i in self.inner.data])
      return pytd.GenericType(pytd.NamedType(self.pytd_name), (t,))
    else:
      return pytd.NamedType(self.pytd_name)

  def __str__(self):
    if self.inner:
      return self.name + "[" + str(self.inner.data[0]) + "]"
    else:
      return self.name


class List(_Container):
  pytd_name = "__builtin__.list"

  def __init__(self, name, vm, node, inner=None):
    super(List, self).__init__("List", vm, node, inner)
    self.concrete_classes = [self.vm.convert.list_type]


class Sequence(_Container):
  pytd_name = "typing.Sequence"

  def __init__(self, name, vm, node, inner=None):
    super(Sequence, self).__init__("Sequence", vm, node, inner)
    self.concrete_classes = [self.vm.convert.list_type,
                             self.vm.convert.tuple_type]


typing_overload = {
    "Union": Union,
    "List": List,
    "Sequence": Sequence,
}
