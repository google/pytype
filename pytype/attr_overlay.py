"""Support for the 'attrs' library."""

import logging

from pytype import abstract
from pytype import abstract_utils
from pytype import function
from pytype import mixin
from pytype import overlay
from pytype import overlay_utils
from pytype import special_builtins

log = logging.getLogger(__name__)

# type alias for convenience
Param = overlay_utils.Param

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


class Attrs(abstract.PyTDFunction):
  """Implements the @attr.s decorator."""

  @classmethod
  def make(cls, name, vm):
    return super(Attrs, cls).make(name, vm, "attr")

  def __init__(self, *args, **kwargs):
    super(Attrs, self).__init__(*args, **kwargs)
    # Defaults for the args to attr.s that we support.
    self.args = {
        "init": True,
        "kw_only": False,
        "auto_attribs": False,
    }

  def _make_init(self, node, attrs):
    attr_params = []
    for attr in attrs:
      if attr.init:
        # attrs removes leading underscores from attrib names when
        # generating kwargs for __init__.
        attr_params.append(
            Param(
                name=attr.name.lstrip("_"), typ=attr.typ, default=attr.default))

    # The kw_only arg is ignored in python2; using it is not an error.
    if self.args["kw_only"] and self.vm.PY3:
      params = []
      kwonly_params = attr_params
    else:
      params = attr_params
      kwonly_params = []

    return overlay_utils.make_method(self.vm, node, "__init__", params,
                                     kwonly_params)

  def _update_kwargs(self, args):
    for k, v in args.namedargs.items():
      if k in self.args:
        try:
          self.args[k] = abstract_utils.get_atomic_python_constant(v)
        except abstract_utils.ConversionError:
          self.vm.errorlog.not_supported_yet(
              self.vm.frames, "Non-constant attr.s argument %r" % k)

  def _type_clash_error(self, value):
    if is_late_annotation(value):
      err = value.expr
    else:
      err = value.data[0].cls
    self.vm.errorlog.invalid_annotation(self.vm.frames, err)

  def call(self, node, func, args):
    """Processes the attrib members of a class."""
    self.match_args(node, args)

    if args.namedargs:
      self._update_kwargs(args)

    # @attr.s does not take positional arguments in typical usage, but
    # technically this works:
    #   class Foo:
    #     x = attr.ib()
    #   Foo = attr.s(Foo, **kwargs)
    #
    # Unfortunately, it also works to pass kwargs as posargs; we will at least
    # reject posargs if the first arg is not a Callable.
    if not args.posargs:
      return node, self.to_variable(node)

    cls_var = args.posargs[0]
    # We should only have a single binding here
    cls, = cls_var.data

    if not isinstance(cls, mixin.Class):
      # There are other valid types like abstract.Unsolvable that we don't need
      # to do anything with.
      return node, cls_var

    # Collect classvars to convert them to attrs.
    ordered_locals = self.vm.ordered_locals[cls.name]
    own_attrs = []
    late_annotation = False  # True if we find a bare late annotation
    for name, value, orig in ordered_locals:
      if name.startswith("__") and name.endswith("__"):
        continue
      if is_method(orig):
        continue
      if is_attrib(orig):
        if not is_attrib(value) and orig.data[0].has_type:
          # We cannot have both a type annotation and a type argument.
          self._type_clash_error(value)
          attr = Attribute(
              name=name,
              typ=self.vm.new_unsolvable(node),
              init=orig.data[0].init,
              default=orig.data[0].default)
        else:
          if is_late_annotation(value):
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
                init=orig.data[0].init,
                default=value.data[0].default)
            if is_late_annotation(attr.typ):
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
      elif self.args["auto_attribs"]:
        # NOTE: This code should be much of what we need to implement
        # dataclasses too.
        #
        # TODO(b/72678203): typing.ClassVar is the only way to filter a variable
        # out from auto_attribs, but we don't even support importing it.
        attr = Attribute(name=name, typ=value, init=True, default=orig)
        if is_late_annotation(value) and orig is None:
          # We are generating a class member from a bare annotation.
          cls.members[name] = self.vm.convert.none.to_variable(node)
          cls.late_annotations[name] = value
          late_annotation = True
        own_attrs.append(attr)

    # See if we need to resolve any late annotations
    if late_annotation:
      self.vm.classes_with_late_annotations.append(cls)

    taken_attr_names = {a.name for a in own_attrs}

    # Traverse the MRO and collect base class attributes. We only add an
    # attribute if it hasn't been defined before.
    base_attrs = []
    for base_cls in cls.compute_mro()[1:]:
      log.info("cls.name: %s base_cls.name: %s", cls.name, base_cls.name)
      if not isinstance(base_cls, mixin.Class):
        continue
      sub_attrs = base_cls.metadata.get(_ATTRS_METADATA_KEY, None)
      if sub_attrs is None:
        continue
      for a in sub_attrs:
        if a.name not in taken_attr_names:
          taken_attr_names.add(a.name)
          base_attrs.append(a)

    attrs = base_attrs + own_attrs
    # Stash attributes in class metadata for subclasses.
    cls.metadata[_ATTRS_METADATA_KEY] = attrs

    # Add an __init__ method
    if self.args["init"]:
      init_method = self._make_init(node, attrs)
      cls.members["__init__"] = init_method

    return node, cls_var


class Attribute(object):
  """Represents an 'attr' module attribute."""

  def __init__(self, name, typ, init, default):
    self.name = name
    self.typ = typ
    self.init = init
    self.default = default

  def __repr__(self):
    return str({"name": self.name, "typ": self.typ, "init": self.init,
                "default": self.default})


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


class Attrib(abstract.PyTDFunction):
  """Implements attr.ib."""

  @classmethod
  def make(cls, name, vm):
    return super(Attrib, cls).make(name, vm, "attr")

  def call(self, node, unused_func, args):
    """Returns a type corresponding to an attr."""
    self.match_args(node, args)
    node, default_var = self._get_default_var(node, args)
    type_var = args.namedargs.get("type")
    init = self._get_kwarg(args, "init", True)
    has_type = type_var is not None
    if type_var:
      typ = self._instantiate_type(node, args, type_var)
    elif default_var:
      typ = self._get_type_from_default(node, default_var)
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

  def _get_kwarg(self, args, name, default):
    if name not in args.namedargs:
      return default
    try:
      return abstract_utils.get_atomic_python_constant(args.namedargs[name])
    except abstract_utils.ConversionError:
      self.vm.errorlog.not_supported_yet(
          self.vm.frames, "Non-constant attr.ib argument %r" % name)

  def _instantiate_type(self, node, args, type_var):
    cls = type_var.data[0]
    try:
      return self.vm.annotations_util.init_annotation(cls, "attr.ib",
                                                      self.vm.frames, node)
    except self.vm.annotations_util.LateAnnotationError:
      return abstract.LateAnnotation(cls, "attr.ib", self.vm.simple_stack())

  def _get_type_from_default(self, node, default_var):
    if default_var and default_var.data == [self.vm.convert.none]:
      # A default of None doesn't give us any information about the actual type.
      return self.vm.program.NewVariable([self.vm.convert.unsolvable],
                                         [default_var.bindings[0]], node)
    return default_var


def is_method(var):
  if var is None or is_late_annotation(var):
    return False
  return isinstance(var.data[0], (
      abstract.INTERPRETER_FUNCTION_TYPES,
      special_builtins.PropertyInstance
  ))


def is_attrib(var):
  if var is None or is_late_annotation(var):
    return False
  return isinstance(var.data[0], AttribInstance)


def is_late_annotation(val):
  return isinstance(val, abstract.LateAnnotation)


class Factory(abstract.PyTDFunction):
  """Implementation of attr.Factory."""

  @classmethod
  def make(cls, name, vm):
    return super(Factory, cls).make(name, vm, "attr")
