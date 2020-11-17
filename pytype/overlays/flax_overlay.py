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


from pytype import overlay
from pytype.overlays import dataclass_overlay


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
