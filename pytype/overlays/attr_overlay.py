"""Support for the 'attrs' library."""

import logging

from pytype import abstract
from pytype import function
from pytype import overlay
from pytype import overlay_utils
from pytype.overlays import classgen

log = logging.getLogger(__name__)

# type aliases for convenience
Param = overlay_utils.Param
Attribute = classgen.Attribute


_ATTRS_METADATA_KEY = "__attrs_attrs__"


class AttrOverlay(overlay.Overlay):
  """A custom overlay for the 'attr' module."""

  def __init__(self, vm):
    member_map = {
        "s": Attrs.make,
        "ib": Attrib.make,
        "Factory": Factory.make,
    }
    ast = vm.loader.import_name("attr")
    super(AttrOverlay, self).__init__(vm, "attr", member_map, ast)


class Attrs(classgen.Decorator):
  """Implements the @attr.s decorator."""

  @classmethod
  def make(cls, name, vm):
    return super(Attrs, cls).make(name, vm, "attr")

  def init_name(self, attr):
    # attrs removes leading underscores from attrib names when generating kwargs
    # for __init__.
    return attr.name.lstrip("_")

  def decorate(self, node, cls):
    """Processes the attrib members of a class."""
    # Collect classvars to convert them to attrs.
    if self.args[cls]["auto_attribs"]:
      ordering = classgen.Ordering.FIRST_ANNOTATE
    else:
      ordering = classgen.Ordering.LAST_ASSIGN
    ordered_locals = self.get_class_locals(
        cls, allow_methods=False, ordering=ordering)
    own_attrs = []
    late_annotation = False  # True if we find a bare late annotation
    for name, (value, orig) in ordered_locals.items():
      if is_attrib(orig):
        if not is_attrib(value) and orig.data[0].has_type:
          # We cannot have both a type annotation and a type argument.
          self.type_clash_error(value)
          attr = Attribute(
              name=name,
              typ=self.vm.new_unsolvable(node),
              init=orig.data[0].init,
              default=orig.data[0].default)
        else:
          if classgen.is_late_annotation(value):
            attr = Attribute(
                name=name,
                typ=value,
                init=orig.data[0].init,
                default=orig.data[0].default)
            cls.members[name] = orig.data[0].typ
          elif is_attrib(value):
            # Replace the attrib in the class dict with its type.
            attr = Attribute(
                name=name,
                typ=value.data[0].typ,
                init=value.data[0].init,
                default=value.data[0].default)
            if classgen.is_late_annotation(attr.typ):
              cls.members[name] = self.vm.new_unsolvable(node)
              cls.late_annotations[name] = attr.typ
              late_annotation = True
            else:
              cls.members[name] = attr.typ
          else:
            # cls.members[name] has already been set via a typecomment
            attr = Attribute(
                name=name,
                typ=value,
                init=orig.data[0].init,
                default=orig.data[0].default)
        own_attrs.append(attr)
      elif self.args[cls]["auto_attribs"]:
        # TODO(b/72678203): typing.ClassVar is the only way to filter a variable
        # out from auto_attribs, but we don't even support importing it.
        attr = Attribute(name=name, typ=value, init=True, default=orig)
        if self.add_member(node, cls, name, value, orig):
          late_annotation = True
        own_attrs.append(attr)

    # See if we need to resolve any late annotations
    if late_annotation:
      self.vm.classes_with_late_annotations.append(cls)

    base_attrs = self.get_base_class_attrs(cls, own_attrs, _ATTRS_METADATA_KEY)
    attrs = base_attrs + own_attrs
    # Stash attributes in class metadata for subclasses.
    cls.metadata[_ATTRS_METADATA_KEY] = attrs

    # Add an __init__ method
    if self.args[cls]["init"]:
      init_method = self.make_init(node, cls, attrs)
      cls.members["__init__"] = init_method


class AttribInstance(abstract.SimpleAbstractValue):
  """Return value of an attr.ib() call."""

  def __init__(self, vm, typ, has_type, init, default=None):
    super(AttribInstance, self).__init__("attrib", vm)
    self.typ = typ
    self.has_type = has_type
    self.init = init
    self.default = default
    # TODO(rechen): attr.ib() returns an instance of attr._make._CountingAttr.
    self.cls = vm.convert.unsolvable


class Attrib(classgen.FieldConstructor):
  """Implements attr.ib."""

  @classmethod
  def make(cls, name, vm):
    return super(Attrib, cls).make(name, vm, "attr")

  def call(self, node, unused_func, args):
    """Returns a type corresponding to an attr."""
    self.match_args(node, args)
    node, default_var = self._get_default_var(node, args)
    type_var = args.namedargs.get("type")
    init = self.get_kwarg(args, "init", True)
    has_type = type_var is not None
    if type_var:
      typ = self._instantiate_type(node, args, type_var)
    elif default_var:
      typ = self.get_type_from_default(node, default_var)
    else:
      typ = self.vm.new_unsolvable(node)
    typ = AttribInstance(self.vm, typ, has_type, init,
                         default_var).to_variable(node)
    return node, typ

  def _get_default_var(self, node, args):
    if "default" in args.namedargs and "factory" in args.namedargs:
      # attr.ib(factory=x) is syntactic sugar for attr.ib(default=Factory(x)).
      raise function.DuplicateKeyword(self.signatures[0].signature, args,
                                      self.vm, "default")
    elif "default" in args.namedargs:
      default_var = args.namedargs["default"]
    elif "factory" in args.namedargs:
      mod = self.vm.import_module("attr", "attr", 0)
      node, attr = self.vm.attribute_handler.get_attribute(node, mod, "Factory")
      # We know there is only one value because Factory is in the overlay.
      factory, = attr.data
      factory_args = function.Args(posargs=(args.namedargs["factory"],))
      node, default_var = factory.call(node, attr.bindings[0], factory_args)
    else:
      default_var = None
    return node, default_var

  def _instantiate_type(self, node, args, type_var):
    cls = type_var.data[0]
    try:
      return self.vm.annotations_util.init_annotation(node, cls, "attr.ib",
                                                      self.vm.frames)
    except self.vm.annotations_util.LateAnnotationError:
      return abstract.LateAnnotation(cls, "attr.ib", self.vm.simple_stack())


def is_attrib(var):
  if var is None or classgen.is_late_annotation(var):
    return False
  return isinstance(var.data[0], AttribInstance)


class Factory(abstract.PyTDFunction):
  """Implementation of attr.Factory."""

  @classmethod
  def make(cls, name, vm):
    return super(Factory, cls).make(name, vm, "attr")
