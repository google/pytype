"""Support for the 'attrs' library."""

import logging

from pytype import abstract
from pytype import abstract_utils
from pytype import annotations_util
from pytype import overlay


log = logging.getLogger(__name__)


class AttrOverlay(overlay.Overlay):
  """A custom overlay for the 'attr' module."""

  def __init__(self, vm):
    member_map = {
        "s": Attrs.make,
        "ib": Attrib.make,
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
    # TODO(mdemello): Add auto_attribs.
    self.args = {
        "init": True,
        "kw_only": False,
    }

  def _make_init(self, node, attrs):
    # attrs removes leading underscores from attrib names when
    # generating kwargs for __init__.
    for attr in attrs:
      attr.name = attr.name.lstrip("_")

    annotations = {}
    late_annotations = {}
    for attr in attrs:
      if is_late_annotation(attr.typ):
        late_annotations[attr.name] = attr.typ
      elif all(t.cls for t in attr.typ.data):
        types = attr.typ.data
        if len(types) == 1:
          annotations[attr.name] = types[0].cls
        else:
          t = abstract.Union([t.cls for t in types], self.vm)
          annotations[attr.name] = t

    # The kw_only arg is ignored in python2; using it is not an error.
    params = [x.name for x in attrs]
    if self.args["kw_only"] and self.vm.PY3:
      param_names = ("self",)
      kwonly_params = tuple(params)
    else:
      param_names = ("self",) + tuple(params)
      kwonly_params = ()

    defaults = {x.name: x.default for x in attrs if x.default}

    init = abstract.SimpleFunction(
        name="__init__",
        param_names=param_names,
        varargs_name=None,
        kwonly_params=kwonly_params,
        kwargs_name=None,
        defaults=defaults,
        annotations=annotations,
        late_annotations=late_annotations,
        vm=self.vm)
    # This should never happen (see comment in call())
    if late_annotations:
      self.vm.functions_with_late_annotations.append(init)
    return init.to_variable(node)

  def _update_kwargs(self, args):
    for k, v in args.namedargs.items():
      if k in self.args:
        try:
          self.args[k] = abstract_utils.get_atomic_python_constant(v)
        except abstract_utils.ConversionError:
          self.vm.errorlog.not_supported_yet(
              self.vm.frames,
              "Non-constant attr.s argument %r" % k)

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

    # Collect classvars to convert them to attrs.
    #
    # TODO(mdemello): Need support for auto_attribs and defaults.
    ordered_attrs = []
    for name, value, orig in self.vm.ordered_locals[cls.name]:
      if is_attrib(orig):
        if not is_attrib(value) and orig.data[0].has_type:
          # We cannot have both a type annotation and a type argument.
          if is_late_annotation(value):
            err = value.expr
          else:
            err = value.data[0].cls
          self.vm.errorlog.invalid_annotation(self.vm.frames, err)
        else:
          if is_late_annotation(value):
            # This should never happen; we should have resolved all late types
            # in the class by the time @attr.s is invoked.
            log.warning("Found late annotation %s: %s in @attr.s",
                        value.name, value.expr)
            attr = InitParam(name=name,
                             typ=value,
                             default=orig.data[0].default)
            cls.members[name] = orig.data[0].typ
          elif is_attrib(value):
            # Replace the attrib in the class dict with its type.
            attr = InitParam(name=name,
                             typ=value.data[0].typ,
                             default=value.data[0].default)
            cls.members[name] = attr.typ
          else:
            # cls.members[name] has already been set via a typecomment
            attr = InitParam(name=name,
                             typ=value,
                             default=orig.data[0].default)
          ordered_attrs.append(attr)

    # Add an __init__ method
    if self.args["init"]:
      init_method = self._make_init(node, ordered_attrs)
      cls.members["__init__"] = init_method

    return node, cls_var


class InitParam(object):
  """Parameters for the __init__ method."""

  def __init__(self, name, typ, default):
    self.name = name
    self.typ = typ
    self.default = default


class AttribInstance(abstract.SimpleAbstractValue):
  """Return value of an attr.ib() call."""

  def __init__(self, vm, typ, has_type, default=None):
    super(AttribInstance, self).__init__("attrib", vm)
    self.typ = typ
    self.has_type = has_type
    self.default = default


class Attrib(abstract.PyTDFunction):
  """Implements attr.ib."""

  @classmethod
  def make(cls, name, vm):
    return super(Attrib, cls).make(name, vm, "attr")

  def call(self, node, unused_func, args):
    """Returns a type corresponding to an attr."""
    self.match_args(node, args)
    type_var = args.namedargs.get("type")
    default_var = args.namedargs.get("default")
    has_type = type_var is not None
    if type_var:
      typ = type_var.data[0].instantiate(node)
    elif default_var:
      typ = default_var
    else:
      typ = self.vm.new_unsolvable(node)
    typ = AttribInstance(self.vm, typ, has_type, default_var).to_variable(node)
    return node, typ


def is_attrib(var):
  if is_late_annotation(var):
    return False
  return isinstance(var.data[0], AttribInstance)


def is_late_annotation(val):
  return isinstance(val, annotations_util.LateAnnotation)
