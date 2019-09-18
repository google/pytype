"""Support for dataclasses."""

# TODO(mdemello):
# - Raise a type error if a field with no default follows a field with a default
# - Handle arguments to dataclass (right now even @dataclass() is broken)
# - Handle @dataclass.field()
# - Handle dataclasses.InitVar
# - Raise an error if we see a duplicate annotation, even though python allows
#     it, since there is no good reason to do that.

import logging

from pytype import mixin
from pytype import overlay
from pytype import overlay_utils
from pytype.overlays import classgen

log = logging.getLogger(__name__)

# type alias for convenience
Param = overlay_utils.Param

_DATACLASS_METADATA_KEY = "__dataclass_fields__"


class DataclassOverlay(overlay.Overlay):
  """A custom overlay for the 'dataclasses' module."""

  def __init__(self, vm):
    member_map = {
        "dataclass": Dataclass.make,
    }
    ast = vm.loader.import_name("dataclasses")
    super(DataclassOverlay, self).__init__(vm, "dataclasses", member_map, ast)


class Dataclass(classgen.Decorator):
  """Implements the @dataclass decorator."""

  @classmethod
  def make(cls, name, vm):
    return super(Dataclass, cls).make(name, vm, "dataclasses")

  def call(self, node, func, args):
    """Processes class members."""
    self.match_args(node, args)

    if args.namedargs:
      self.update_kwargs(args)

    cls_var = args.posargs[0]
    # We should only have a single binding here
    cls, = cls_var.data

    if not isinstance(cls, mixin.Class):
      # There are other valid types like abstract.Unsolvable that we don't need
      # to do anything with.
      return node, cls_var

    # Collect classvars to convert them to attrs. @dataclass collects vars with
    # an explicit type annotation, in order of annotation, so that e.g.
    # class A:
    #   x: int
    #   y: str = 'hello'
    #   x = 10
    # would have init(x:int = 10, y:str = 'hello')
    ordered_locals = {x.name: x for x in self.get_class_locals(
        cls, allow_methods=True)}
    ordered_annotations = self.get_class_local_annotations(cls)
    own_attrs = []
    late_annotation = False  # True if we find a bare late annotation
    for local in ordered_annotations:
      name, value, orig = ordered_locals[local.name]
      if self.maybe_add_late_annotation(node, cls, name, value, orig):
        late_annotation = True
      attr = classgen.Attribute(name=name, typ=value, init=True, default=orig)
      own_attrs.append(attr)

    # See if we need to resolve any late annotations
    if late_annotation:
      self.vm.classes_with_late_annotations.append(cls)

    base_attrs = self.get_base_class_attrs(
        cls, own_attrs, _DATACLASS_METADATA_KEY)
    attrs = base_attrs + own_attrs
    # Stash attributes in class metadata for subclasses.
    cls.metadata[_DATACLASS_METADATA_KEY] = attrs

    # Add an __init__ method
    if self.args["init"]:
      init_method = self.make_init(node, attrs)
      cls.members["__init__"] = init_method

    return node, cls_var
