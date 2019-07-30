"""Base class for module overlays."""
from pytype import abstract
from pytype import datatypes


class Overlay(abstract.Module):
  """A layer between pytype and a module's pytd definition.

  An overlay pretends to be a module, but provides members that generate extra
  typing information that cannot be expressed in a pytd file. For example,
  collections.namedtuple is a factory method that generates class definitions
  at runtime. An overlay is needed for Pytype to generate these classes.

  An Overlay will typically import its underlying module in its __init__, e.g.
  by calling vm.loader.import_name(). Due to this, Overlays should only be used
  when their underlying module is imported by the Python script being analyzed!
  A subclass of Overlay should have an __init__ with the signature:
    def __init__(self, vm)

  Attributes:
    real_module: An abstract.Module wrapping the AST for the underlying module.
  """

  # is_lazy tells attribute.py to use load_lazy_attribute, which will in turn
  # call our _convert_member. This is how we intercept calls made to the module
  # members we override.
  is_lazy = True

  def __init__(self, vm, name, member_map, ast):
    """Initialize the overlay.

    Args:
      vm: Instance of vm.VirtualMachine.
      name: A string containing the name of the underlying module.
      member_map: Dict of str to abstract.AtomicAbstractValues that provide type
        information not available in the underlying module.
      ast: An pytd.TypeDeclUnit containing the AST for the underlying module.
        Used to access type information for members of the module that are not
        explicitly provided by the overlay.
    """
    super(Overlay, self).__init__(vm, name, member_map, ast)
    self.real_module = vm.convert.constant_to_value(
        ast, subst=datatypes.AliasingDict(), node=vm.root_cfg_node)

  def _convert_member(self, name, member):
    val = member(name, self.vm)
    val.module = self.name
    var = val.to_variable(self.vm.root_cfg_node)
    self.vm.trace_module_member(self, name, var)
    return var

  def get_module(self, name):
    """Returns the abstract.Module for the given name."""
    if name in self._member_map:
      return self
    else:
      return self.real_module

  def items(self):
    items = super(Overlay, self).items()
    items += [(name, item) for name, item in self.real_module.items()
              if name not in self._member_map]
    return items
