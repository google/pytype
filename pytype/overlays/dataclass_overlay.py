"""Support for dataclasses."""

# TODO(mdemello):
# - Handle dataclasses.InitVar
# - Raise an error if we see a duplicate annotation, even though python allows
#     it, since there is no good reason to do that.

import logging

from pytype import abstract
from pytype import function
from pytype import overlay
from pytype.overlays import classgen

log = logging.getLogger(__name__)


_DATACLASS_METADATA_KEY = "__dataclass_fields__"


class DataclassOverlay(overlay.Overlay):
  """A custom overlay for the 'dataclasses' module."""

  def __init__(self, vm):
    member_map = {
        "dataclass": Dataclass.make,
        "field": Field.make,
    }
    ast = vm.loader.import_name("dataclasses")
    super(DataclassOverlay, self).__init__(vm, "dataclasses", member_map, ast)


class Dataclass(classgen.Decorator):
  """Implements the @dataclass decorator."""

  @classmethod
  def make(cls, name, vm):
    return super(Dataclass, cls).make(name, vm, "dataclasses")

  def decorate(self, node, cls):
    """Processes class members."""

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
      if self.add_member(node, cls, name, value, orig):
        late_annotation = True

      if is_field(orig):
        field = orig.data[0]
        orig = field.typ
        init = field.init
      else:
        init = True

      # Check that default matches the declared type
      if orig and not classgen.is_late_annotation(value):
        typ = value.data[0].get_class()
        bad = self.vm.matcher.bad_matches(orig, typ, node)
        if bad:
          binding = bad[0][orig]
          self.vm.errorlog.annotation_type_mismatch(
              self.vm.frames, typ, binding, name)

      attr = classgen.Attribute(name=name, typ=value, init=init, default=orig)
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


class FieldInstance(abstract.SimpleAbstractValue):
  """Return value of a field() call."""

  def __init__(self, vm, typ, init, default=None):
    super(FieldInstance, self).__init__("field", vm)
    self.typ = typ
    self.init = init
    self.default = default
    self.cls = vm.convert.unsolvable


class Field(classgen.FieldConstructor):
  """Implements dataclasses.field."""

  @classmethod
  def make(cls, name, vm):
    return super(Field, cls).make(name, vm, "dataclasses")

  def call(self, node, unused_func, args):
    """Returns a type corresponding to a field."""
    self.match_args(node, args)
    node, default_var = self._get_default_var(node, args)
    init = self.get_kwarg(args, "init", True)
    if default_var:
      typ = self.get_type_from_default(node, default_var)
    else:
      typ = self.vm.new_unsolvable(node)
    typ = FieldInstance(self.vm, typ, init, default_var).to_variable(node)
    return node, typ

  def _get_default_var(self, node, args):
    if "default" in args.namedargs and "default_factory" in args.namedargs:
      # The pyi signatures should prevent this; check left in for safety.
      raise function.DuplicateKeyword(self.signatures[0].signature, args,
                                      self.vm, "default")
    elif "default" in args.namedargs:
      default_var = args.namedargs["default"]
    elif "default_factory" in args.namedargs:
      factory_var = args.namedargs["default_factory"]
      factory, = factory_var.data
      f_args = function.Args(posargs=())
      node, default_var = factory.call(node, factory_var.bindings[0], f_args)
    else:
      default_var = None

    return node, default_var


def is_field(var):
  if var is None or classgen.is_late_annotation(var):
    return False
  return isinstance(var.data[0], FieldInstance)
