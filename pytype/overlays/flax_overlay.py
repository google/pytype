"""Support for flax.struct dataclasses."""

# Flax is a high-performance neural network library for JAX
# see //third_party/py/flax
#
# Since flax.struct.dataclass uses dataclass.dataclass internally, we can simply
# reuse the dataclass overlay with some subclassed constructors to change the
# module name.
#
# NOTE: flax.struct.dataclasses set frozen=True, but since we don't support
# frozen anyway we needn't bother about that for now.


from pytype import abstract
from pytype import abstract_utils
from pytype import function
from pytype import overlay
from pytype.overlays import dataclass_overlay
from pytype.pytd import pytd


class DataclassOverlay(overlay.Overlay):
  """A custom overlay for the 'flax.struct' module."""

  def __init__(self, vm):
    member_map = {
        "dataclass": Dataclass.make,
    }
    ast = vm.loader.import_name("flax.struct")
    super().__init__(vm, "flax.struct", member_map, ast)


class Dataclass(dataclass_overlay.Dataclass):
  """Implements the @dataclass decorator."""

  @classmethod
  def make(cls, vm):
    return super().make(vm, "flax.struct")


# NOTE: flax.linen.module.Module is reexported as flax.linen.Module in
# flax.linen/__init__.py. Due to the way the import system interacts with
# overlays, we cannot just provide an overlay for flax.linen.module.Module and
# trust `flax.linen.Module` to redirect to it whenever needed; we have to
# explicitly handle both ways of referring to the class.


class LinenOverlay(overlay.Overlay):
  """A custom overlay for the 'flax.linen' module."""

  def __init__(self, vm):
    member_map = {
        "Module": Module,
    }
    ast = vm.loader.import_name("flax.linen")
    super().__init__(vm, "flax.linen", member_map, ast)


class LinenModuleOverlay(overlay.Overlay):
  """A custom overlay for the 'flax.linen.module' module."""

  def __init__(self, vm):
    member_map = {
        "Module": Module,
    }
    ast = vm.loader.import_name("flax.linen.module")
    super().__init__(vm, "flax.linen.module", member_map, ast)


class ModuleDataclass(dataclass_overlay.Dataclass):
  """Dataclass with automatic 'name' and 'parent' members."""

  def _add_implicit_field(self, node, cls_locals, key, typ):
    if key in cls_locals:
      self.vm.errorlog.invalid_annotation(
          self.vm.frames, None, name=key,
          details=f"flax.linen.Module defines field '{key}' implicitly")
    default = typ.to_variable(node)
    cls_locals[key] = abstract_utils.Local(node, None, typ, default, self.vm)

  def get_class_locals(self, node, cls):
    cls_locals = super().get_class_locals(node, cls)
    name_type = self.vm.convert.str_type
    # TODO(mdemello): Fill in the parent type properly
    parent_type = self.vm.convert.unsolvable
    self._add_implicit_field(node, cls_locals, "name", name_type)
    self._add_implicit_field(node, cls_locals, "parent", parent_type)
    return cls_locals


class Module(abstract.PyTDClass):
  """Construct a dataclass for any class inheriting from Module."""

  def __init__(self, vm, name="Module", module="flax.linen.module"):
    ast = vm.loader.import_name(module)
    pytd_cls = ast.Lookup(f"{module}.{name}")
    # flax.linen.Module loads as a LateType, we need to convert it and then get
    # the pytd.Class back out to use in our own constructor.
    if isinstance(pytd_cls, pytd.Constant):
      pytd_cls = vm.convert.constant_to_value(pytd_cls).pytd_cls
    super().__init__(name, pytd_cls, vm)

  def init_subclass(self, node, subclass):
    dc = ModuleDataclass.make(self.vm)
    subclass_var = subclass.to_variable(node)
    args = function.Args(
        posargs=(subclass_var,), namedargs=abstract.Dict(self.vm))
    node, _ = dc.call(node, None, args)
    return node

  def get_instance_type(self, node=None, instance=None, seen=None, view=None):
    """Get the type an instance of us would have."""
    # The class is imported as flax.linen.Module but aliases
    # flax.linen.module.Module internally
    return pytd.NamedType("flax.linen.module.Module")

  @property
  def full_name(self):
    # Overide the full name here rather than overriding the module name in the
    # overlay because we might want to overlay other things from flax.linen.
    return "flax.linen.module.Module"

  def __repr__(self):
    return "Overlay(flax.linen.module.Module)"
