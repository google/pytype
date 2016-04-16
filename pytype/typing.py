"""Implementation of the types in Python 3's typing.py."""


from pytype import abstract
from pytype.pytd import pytd


class Typing(abstract.Module):
  is_lazy = True  # uses _convert_member

  def __init__(self, vm):
    super(Typing, self).__init__(vm, "typing", typing_members)

  def _convert_member(self, name, constructor):
    return constructor(name, self.vm).to_variable(self.vm.root_cfg_node, name)


class Union(abstract.ValueWithSlots):
  """Implementation of typing.Union[...]."""

  def __init__(self, name, vm, elements=()):
    super(Union, self).__init__(vm.type_type, vm)
    self.name = "Union"
    self.elements = elements
    self.set_slot("__getitem__", self.getitem_slot)

  def __str__(self):
    return "Union[" + ", ".join(str(n) for n in self.elements) + "]"

  def getitem_slot(self, node, slice_var):
    slice_tuple = abstract.get_atomic_python_constant(slice_var)
    values = tuple(s.Data(node)[0] for s in slice_tuple)
    new_union = Union(self.name, self.vm, self.elements + values)
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

  def get_instance_type(self, instance=None):
    return pytd.UnionType([
        e.get_instance_type()
        for e in self.elements])


class List(abstract.ValueWithSlots):
  """Implementation of typing.List[...]."""

  def __init__(self, name, vm, inner_type=None):
    # TODO(kramm): type_type is wrong. Correct would be "typing.GenericMeta".
    # But in the output, we'd want this to become an alias.
    super(List, self).__init__(vm.type_type, vm)
    self.name = "List"
    self.inner_type = inner_type
    self.set_slot("__getitem__", self.getitem_slot)

  def getitem_slot(self, node, type_var):
    inner_type = abstract.get_atomic_value(type_var)
    new_list = List(self.name, self.vm, inner_type)
    return node, new_list.to_variable(node, "List")

  def instantiate(self, node):
    return self.vm.build_list(node, [
        self.inner_type.to_variable(node, "inner")])

  def match_var_against(self, var, subst, node, view):
    new_subst = abstract.match_var_against_type(
        var, self.vm.list_type.data[0], subst, node, view)
    if new_subst is not None:
      return new_subst

  def get_instance_type(self, instance=None):
    return pytd.GenericType(pytd.NamedType("list"),
                            (self.inner_type.get_instance_type(),))


typing_members = {
    "Union": Union,
    "List": List,
}
