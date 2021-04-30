"""Overlay for third-party chex.dataclass decorator.

See https://github.com/deepmind/chex#dataclass-dataclasspy. Typing-wise, the
differences between @dataclasses.dataclass and @chex.dataclass are:
* The latter has a mappable_dataclass parameter, defaulting to True, which makes
  the dataclass inherit from Mapping.
* Chex dataclasses have replace, from_tuple, and to_tuple methods.
"""

from pytype import abstract
from pytype import abstract_utils
from pytype import overlay
from pytype import overlay_utils
from pytype.overlays import dataclass_overlay
from pytype.pytd import pytd


class ChexOverlay(overlay.Overlay):

  def __init__(self, vm):
    member_map = {
        "dataclass": Dataclass.make,
    }
    ast = vm.loader.import_name("chex")
    super().__init__(vm, "chex", member_map, ast)


class Dataclass(dataclass_overlay.Dataclass):
  """Implements the @dataclass decorator."""

  _DEFAULT_ARGS = {**dataclass_overlay.Dataclass._DEFAULT_ARGS,
                   "mappable_dataclass": True}

  @classmethod
  def make(cls, vm):
    return super().make(vm, "chex")

  def _add_replace_method(self, node, cls):
    typevar = abstract.TypeParameter(
        abstract_utils.T + cls.name, self.vm, bound=cls)
    cls.members["replace"] = overlay_utils.make_method(
        vm=self.vm,
        node=node,
        name="replace",
        return_type=typevar,
        self_param=overlay_utils.Param("self", typevar),
        kwargs=overlay_utils.Param("changes"),
    )

  def _add_from_tuple_method(self, node, cls):
    # from_tuple is discouraged anyway, so we provide only bare-bones types.
    cls.members["from_tuple"] = overlay_utils.make_method(
        vm=self.vm,
        node=node,
        name="from_tuple",
        params=[overlay_utils.Param("args")],
        return_type=cls,
        kind=pytd.MethodTypes.STATICMETHOD,
    )

  def _add_to_tuple_method(self, node, cls):
    # to_tuple is discouraged anyway, so we provide only bare-bones types.
    cls.members["to_tuple"] = overlay_utils.make_method(
        vm=self.vm,
        node=node,
        name="to_tuple",
        return_type=self.vm.convert.tuple_type,
    )

  def _add_mapping_base(self, node, cls):
    mapping = self.vm.convert.name_to_value("typing.Mapping")
    # The class's MRO is constructed from its bases at the moment the class is
    # created, so both need to be updated.
    bases = cls.bases()
    if bases[-1].data == [self.vm.convert.object_type]:
      bases.insert(-1, mapping.to_variable(node))
      cls.mro = cls.mro[:-1] + (mapping,) + cls.mro[-1:]
    else:
      bases.append(mapping.to_variable(node))
      cls.mro = cls.mro + (mapping,)

  def decorate(self, node, cls):
    super().decorate(node, cls)
    if not isinstance(cls, abstract.InterpreterClass):
      return
    self._add_replace_method(node, cls)
    self._add_from_tuple_method(node, cls)
    self._add_to_tuple_method(node, cls)
    if not self.args[cls]["mappable_dataclass"]:
      return
    self._add_mapping_base(node, cls)
