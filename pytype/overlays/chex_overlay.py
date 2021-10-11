"""Overlay for third-party chex.dataclass decorator.

See https://github.com/deepmind/chex#dataclass-dataclasspy. Typing-wise, the
differences between @dataclasses.dataclass and @chex.dataclass are:
* The latter has a mappable_dataclass parameter, defaulting to True, which makes
  the dataclass inherit from Mapping.
* Chex dataclasses have replace, from_tuple, and to_tuple methods.
"""

from pytype import overlay
from pytype import overlay_utils
from pytype.abstract import abstract
from pytype.overlays import classgen
from pytype.overlays import dataclass_overlay
from pytype.pytd import pytd


class ChexOverlay(overlay.Overlay):

  def __init__(self, ctx):
    member_map = {
        "dataclass": Dataclass.make,
    }
    ast = ctx.loader.import_name("chex")
    super().__init__(ctx, "chex", member_map, ast)


class Dataclass(dataclass_overlay.Dataclass):
  """Implements the @dataclass decorator."""

  _DEFAULT_ARGS = {**dataclass_overlay.Dataclass._DEFAULT_ARGS,
                   "mappable_dataclass": True}

  @classmethod
  def make(cls, ctx):
    return super().make(ctx, "chex")

  def _add_replace_method(self, node, cls):
    cls.members["replace"] = classgen.make_replace_method(
        self.ctx, node, cls, kwargs_name="changes")

  def _add_from_tuple_method(self, node, cls):
    # from_tuple is discouraged anyway, so we provide only bare-bones types.
    cls.members["from_tuple"] = overlay_utils.make_method(
        ctx=self.ctx,
        node=node,
        name="from_tuple",
        params=[overlay_utils.Param("args")],
        return_type=cls,
        kind=pytd.MethodTypes.STATICMETHOD,
    )

  def _add_to_tuple_method(self, node, cls):
    # to_tuple is discouraged anyway, so we provide only bare-bones types.
    cls.members["to_tuple"] = overlay_utils.make_method(
        ctx=self.ctx,
        node=node,
        name="to_tuple",
        return_type=self.ctx.convert.tuple_type,
    )

  def _add_mapping_base(self, node, cls):
    mapping = self.ctx.convert.name_to_value("typing.Mapping")
    # The class's MRO is constructed from its bases at the moment the class is
    # created, so both need to be updated.
    bases = cls.bases()
    # If any class in Mapping's MRO already exists in the list of bases, Mapping
    # needs to be inserted before it, otherwise we put it at the end.
    mapping_mro = {x.full_name for x in mapping.mro}
    cls_bases = [x.data[0].full_name for x in bases]
    cls_mro = [x.full_name for x in cls.mro]
    bpos = [i for i, x in enumerate(cls_bases) if x in mapping_mro]
    mpos = [i for i, x in enumerate(cls_mro) if x in mapping_mro]
    if bpos:
      bpos, mpos = bpos[0], mpos[0]
      bases.insert(bpos, mapping.to_variable(node))
      cls.mro = cls.mro[:mpos] + (mapping,) + cls.mro[mpos:]
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
