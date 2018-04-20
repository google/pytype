"""Implementation of special members of third_party/six."""

import logging

from pytype import abstract
from pytype import function
from pytype import overlay

log = logging.getLogger(__name__)


class SixOverlay(overlay.Overlay):
  """A custom overlay for the 'six' module."""

  def __init__(self, vm):
    member_map = {
        "add_metaclass": AddMetaclass,
        "with_metaclass": WithMetaclass,
        "PY2": build_version_bool(2),
        "PY3": build_version_bool(3),
    }
    ast = vm.loader.import_name("six")
    super(SixOverlay, self).__init__(vm, "six", member_map, ast)


class AddMetaclassInstance(abstract.AtomicAbstractValue):
  """AddMetaclass instance (constructed by AddMetaclass.call())."""

  # Minimal signature, only used for constructing exceptions.
  _SIGNATURE = function.Signature.from_param_names(
      "six.add_metaclass", ("cls",))

  def __init__(self, meta, vm):
    super(AddMetaclassInstance, self).__init__("AddMetaclassInstance", vm)
    self.meta = meta
    self.vm = vm

  def call(self, node, unused, args):
    if len(args.posargs) != 1:
      raise abstract.WrongArgCount(self._SIGNATURE, args, self.vm)
    cls_var = args.posargs[0]
    for b in cls_var.bindings:
      cls = b.data
      log.debug("Adding metaclass %r to class %r", self.meta.data[0], cls)
      cls.cls = self.meta
    return node, cls_var


class AddMetaclass(abstract.PyTDFunction):
  """Implements the @six.add_metaclass decorator."""

  def __init__(self, name, vm):
    super(AddMetaclass, self).__init__(
        *abstract.PyTDFunction.get_constructor_args(name, vm, "six"))

  def call(self, node, unused_func, args):
    """Adds a metaclass."""
    self._match_args(node, args)
    meta = args.posargs[0]
    return node, AddMetaclassInstance(meta, self.vm).to_variable(node)


class WithMetaclassInstance(abstract.AtomicAbstractValue):
  """Anonymous class created by six.with_metaclass."""

  def __init__(self, vm, cls, bases):
    super(WithMetaclassInstance, self).__init__("WithMetaclassInstance", vm)
    self.cls = cls
    self.bases = bases

  def get_class(self):
    return self.cls


class WithMetaclass(abstract.PyTDFunction):
  """Implements six.with_metaclass."""

  def __init__(self, name, vm):
    super(WithMetaclass, self).__init__(
        *abstract.PyTDFunction.get_constructor_args(name, vm, "six"))

  def call(self, node, unused_func, args):
    """Creates an anonymous class to act as a metaclass."""
    self._match_args(node, args)
    meta = args.posargs[0]
    bases = args.posargs[1:]
    result = WithMetaclassInstance(self.vm, meta, bases).to_variable(node)
    return node, result


def build_version_bool(major):
  return lambda _, vm: vm.convert.bool_values[vm.python_version[0] == major]
