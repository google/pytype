"""Base support for generating classes from data declarations.

Contains common functionality used by dataclasses, attrs and namedtuples.
"""

import logging

from pytype import abstract
from pytype import abstract_utils
from pytype import mixin
from pytype import overlay_utils
from pytype import special_builtins


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

  def maybe_add_late_annotation(self, node, cls, name, value, orig):
    if is_late_annotation(value) and orig is None:
      # We are generating a class member from a bare annotation.
      cls.members[name] = self.vm.convert.none.to_variable(node)
      cls.late_annotations[name] = value
      return True
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


def is_method(var):
  if var is None or is_late_annotation(var):
    return False
  return isinstance(var.data[0], (
      abstract.INTERPRETER_FUNCTION_TYPES,
      special_builtins.PropertyInstance
  ))


def is_late_annotation(val):
  return isinstance(val, abstract.LateAnnotation)


def is_dunder(name):
  return name.startswith("__") and name.endswith("__")
