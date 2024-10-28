"""Classes that need special handling, typically due to code generation."""

from collections.abc import Sequence
from typing import TYPE_CHECKING
from pytype.abstract import abstract_utils
from pytype.abstract import class_mixin
from pytype.pytd import pytd

if TYPE_CHECKING:
  from pytype import context  # pylint: disable=g-bad-import-order,g-import-not-at-top
  from pytype.typegraph import cfg  # pylint: disable=g-bad-import-order,g-import-not-at-top
  from pytype.abstract import _classes  # pylint: disable=g-bad-import-order,g-import-not-at-top
  from pytype.overlays import named_tuple  # pylint: disable=g-bad-import-order,g-import-not-at-top
  from pytype.overlays import typed_dict  # pylint: disable=g-bad-import-order,g-import-not-at-top


def build_class(
    node: "cfg.CFGNode",
    props: class_mixin.ClassBuilderProperties,
    kwargs: "dict[str, cfg.Variable]",
    ctx: "context.Context",
) -> "tuple[cfg.CFGNode, cfg.Variable | None]":
  """Handle classes whose subclasses define their own class constructors."""

  for base in props.bases:
    base = abstract_utils.get_atomic_value(base, default=None)
    if not isinstance(base, class_mixin.Class):
      continue
    if base.is_enum:
      enum_base = abstract_utils.get_atomic_value(
          ctx.vm.loaded_overlays["enum"].members[
              "Enum"
          ]  # pytype: disable=attribute-error
      )
      return enum_base.make_class(node, props)
    elif base.full_name == "typing.NamedTuple":
      return base.make_class(node, props.bases, props.class_dict_var)
    elif base.is_typed_dict_class:
      return base.make_class(
          node, props.bases, props.class_dict_var, total=kwargs.get("total")
      )
    elif "__dataclass_transform__" in base.metadata:
      node, cls_var = ctx.make_class(node, props)
      return ctx.convert.apply_dataclass_transform(cls_var, node)
  return node, None


class _Builder:
  """Build special classes created by inheriting from a specific class."""

  def __init__(self, ctx: "context.Context"):
    self.ctx = ctx
    self.convert = ctx.convert

  def matches_class(self, c: "_classes.PyTDClass"):
    raise NotImplementedError()

  def matches_base(self, c: "_classes.PyTDClass"):
    raise NotImplementedError()

  def matches_mro(self, c: "_classes.PyTDClass"):
    raise NotImplementedError()

  def make_base_class(
      self,
  ) -> (
      "typed_dict.TypedDictBuilder | named_tuple.NamedTupleClassBuilder | None"
  ):
    raise NotImplementedError()

  def make_derived_class(
      self, name: str, pytd_cls: "_classes.PyTDClass"
  ) -> "typed_dict.TypedDictClass | cfg.Variable | None":
    raise NotImplementedError()

  def maybe_build_from_pytd(
      self, name: str, pytd_cls: pytd.Class
  ) -> "typed_dict.TypedDictBuilder | named_tuple.NamedTupleClassBuilder | typed_dict.TypedDictClass | cfg.Variable | None":
    if self.matches_class(pytd_cls):
      return self.make_base_class()
    elif self.matches_base(pytd_cls):
      return self.make_derived_class(name, pytd_cls)
    else:
      return None

  def maybe_build_from_mro(
      self, abstract_cls: "_classes.PyTDClass", name: str, pytd_cls: pytd.Class
  ) -> "typed_dict.TypedDictClass | cfg.Variable | None":
    if self.matches_mro(abstract_cls):
      return self.make_derived_class(name, pytd_cls)
    return None


class _TypedDictBuilder(_Builder):
  """Build a typed dict."""

  # TODO: b/350643999 - Should rather be a ClassVar[Sequence[str]]
  CLASSES: Sequence[str] = ("typing.TypedDict", "typing_extensions.TypedDict")

  def matches_class(self, c: "_classes.PyTDClass") -> bool:
    return c.name in self.CLASSES

  def matches_base(self, c: "_classes.PyTDClass") -> bool:
    return any(  # pytype: disable=attribute-error
        isinstance(b, pytd.ClassType) and self.matches_class(b) for b in c.bases
    )

  def matches_mro(self, c: "_classes.PyTDClass") -> bool:
    # Check if we have typed dicts in the MRO by seeing if we have already
    # created a TypedDictClass for one of the ancestor classes.
    return any(
        isinstance(b, class_mixin.Class) and b.is_typed_dict_class
        for b in c.mro
    )

  def make_base_class(self) -> "typed_dict.TypedDictBuilder":
    return self.convert.make_typed_dict_builder()

  def make_derived_class(
      self, name: str, pytd_cls: "_classes.PyTDClass"
  ) -> "typed_dict.TypedDictClass":
    return self.convert.make_typed_dict(name, pytd_cls)


class _NamedTupleBuilder(_Builder):
  """Build a namedtuple."""

  # TODO: b/350643999 - Should rather be a ClassVar[Sequence[str]]
  CLASSES: Sequence[str] = ("typing.NamedTuple",)

  def matches_class(self, c: "_classes.PyTDClass") -> bool:
    return c.name in self.CLASSES

  def matches_base(self, c: "_classes.PyTDClass") -> bool:
    return any(  # pytype: disable=attribute-error
        isinstance(b, pytd.ClassType) and self.matches_class(b) for b in c.bases
    )

  def matches_mro(self, c: "_classes.PyTDClass") -> bool:
    # We only create namedtuples by direct inheritance
    return False

  def make_base_class(self) -> "named_tuple.NamedTupleClassBuilder":
    return self.convert.make_namedtuple_builder()

  def make_derived_class(
      self, name: str, pytd_cls: "_classes.PyTDClass"
  ) -> "cfg.Variable":
    return self.convert.make_namedtuple(name, pytd_cls)


_BUILDERS: Sequence[type[_Builder]] = (
    _TypedDictBuilder,
    _NamedTupleBuilder,
)


def maybe_build_from_pytd(
    name: str, pytd_cls: pytd.Class, ctx: "context.Context"
):
  """Try to build a special class from a pytd class."""
  for b in _BUILDERS:
    ret = b(ctx).maybe_build_from_pytd(name, pytd_cls)
    if ret:
      return ret
  return None


def maybe_build_from_mro(
    abstract_cls: "_classes.PyTDClass",
    name: str,
    pytd_cls: pytd.Class,
    ctx: "context.Context",
) -> "typed_dict.TypedDictClass | cfg.Variable | None":
  """Try to build a special class from the MRO of an abstract class."""
  for b in _BUILDERS:
    ret = b(ctx).maybe_build_from_mro(abstract_cls, name, pytd_cls)
    if ret:
      return ret
  return None
