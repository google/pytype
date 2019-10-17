"""Base support for generating classes from data declarations.

Contains common functionality used by dataclasses, attrs and namedtuples.
"""

import abc
import logging

from pytype import abstract
from pytype import abstract_utils
from pytype import mixin
from pytype import overlay_utils
from pytype import special_builtins
import six


log = logging.getLogger(__name__)


# type alias for convenience
Param = overlay_utils.Param


class Attribute(object):
  """Represents a class member variable.

  Members:
    name: field name
    typ: field python type
    init: Whether the field should be included in the generated __init__
    default: Default value
  """

  def __init__(self, name, typ, init, default):
    self.name = name
    self.typ = typ
    self.init = init
    self.default = default

  def __repr__(self):
    return str({"name": self.name, "typ": self.typ, "init": self.init,
                "default": self.default})


@six.add_metaclass(abc.ABCMeta)
class Decorator(abstract.PyTDFunction):
  """Base class for decorators that generate classes from data declarations."""

  def __init__(self, *args, **kwargs):
    super(Decorator, self).__init__(*args, **kwargs)
    # Defaults for the args that we support (dataclasses only support 'init',
    # but the others default to false so they should not affect anything).
    self.args = {
        "init": True,
        "kw_only": False,
        "auto_attribs": False,
    }

  @abc.abstractmethod
  def decorate(self, node, cls):
    """Apply the decorator to cls."""

  def update_kwargs(self, args):
    for k, v in args.namedargs.items():
      if k in self.args:
        try:
          self.args[k] = abstract_utils.get_atomic_python_constant(v)
        except abstract_utils.ConversionError:
          self.vm.errorlog.not_supported_yet(
              self.vm.frames, "Non-constant argument to decorator: %r" % k)

  def init_name(self, attr):
    """Attribute name as an __init__ keyword, could differ from attr.name."""
    return attr.name

  def make_init(self, node, attrs):
    attr_params = []
    for attr in attrs:
      if attr.init:
        # call self.init_name in case the name differs from the field name -
        # e.g. attrs removes leading underscores from attrib names when
        # generating kwargs for __init__.
        attr_params.append(
            Param(name=self.init_name(attr),
                  typ=attr.typ,
                  default=attr.default))

    # The kw_only arg is ignored in python2; using it is not an error.
    if self.args["kw_only"] and self.vm.PY3:
      params = []
      kwonly_params = attr_params
    else:
      params = attr_params
      kwonly_params = []

    return overlay_utils.make_method(self.vm, node, "__init__", params,
                                     kwonly_params)

  def type_clash_error(self, value):
    if is_late_annotation(value):
      err = value.expr
    else:
      err = value.data[0].cls
    self.vm.errorlog.invalid_annotation(self.vm.frames, err)

  def get_class_locals(self, cls, allow_methods=False):
    ordered_locals = self.vm.ordered_locals[cls.name]
    out = []
    for local in ordered_locals:
      name, _, orig = local
      if is_dunder(name):
        continue
      if is_method(orig) and not allow_methods:
        continue
      out.append(local)
    return out

  def get_class_local_annotations(self, cls):
    # TODO(mdemello): This is based on what dataclasses need - we discard dups
    # here since dataclasses take the first recorded annotation to determine the
    # ordering. It should be configurable behaviour.
    traces = self.vm.local_traces[cls.name]
    out = []
    seen = set()
    for local in traces:
      if is_dunder(local.name) or local.name in seen:
        continue
      if not local.is_annotate():
        continue
      seen.add(local.name)
      out.append(local)
    return out

  def add_member(self, node, cls, name, value, orig):
    """Adds a class member, returning whether it's a bare late annotation."""
    if not is_late_annotation(value):
      cls.members[name] = value
      return False
    elif orig is None:
      # We are generating a class member from a bare annotation.
      cls.members[name] = self.vm.convert.none.to_variable(node)
      cls.late_annotations[name] = value
      return True
    else:
      cls.members[name] = orig
      return False

  def get_base_class_attrs(self, cls, cls_attrs, metadata_key):
    # Traverse the MRO and collect base class attributes. We only add an
    # attribute if it hasn't been defined before.
    base_attrs = []
    taken_attr_names = {a.name for a in cls_attrs}
    for base_cls in cls.mro[1:]:
      if not isinstance(base_cls, mixin.Class):
        continue
      sub_attrs = base_cls.metadata.get(metadata_key, None)
      if sub_attrs is None:
        continue
      for a in sub_attrs:
        if a.name not in taken_attr_names:
          taken_attr_names.add(a.name)
          base_attrs.append(a)
    return base_attrs

  def call(self, node, func, args):
    """Construct a decorator, and call it on the class."""
    # call() is invoked twice, once with kwargs to create the decorator object
    # and once with the decorated class as a posarg.

    self.match_args(node, args)

    if args.namedargs:
      self.update_kwargs(args)

    # NOTE: @dataclass is py3-only and has explicitly kwonly args in its
    # constructor.
    #
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

    # decorate() modifies the cls object in place
    self.decorate(node, cls)
    return node, cls_var


class FieldConstructor(abstract.PyTDFunction):
  """Implements constructors for fields."""

  def get_kwarg(self, args, name, default):
    if name not in args.namedargs:
      return default
    try:
      return abstract_utils.get_atomic_python_constant(args.namedargs[name])
    except abstract_utils.ConversionError:
      self.vm.errorlog.not_supported_yet(
          self.vm.frames, "Non-constant argument %r" % name)

  def get_type_from_default(self, node, default_var):
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
      special_builtins.ClassMethodInstance,
      special_builtins.PropertyInstance,
      special_builtins.StaticMethodInstance
  ))


def is_late_annotation(val):
  return isinstance(val, abstract.LateAnnotation)


def is_dunder(name):
  return name.startswith("__") and name.endswith("__")
