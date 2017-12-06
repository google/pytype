"""Implementation of special members of third_party/six."""

import logging

from pytype import abstract
from pytype import overlay

log = logging.getLogger(__name__)


class SixOverlay(overlay.Overlay):
  """A custom overlay for the 'six' module."""

  def __init__(self, vm):
    member_map = {"add_metaclass": AddMetaclass}
    ast = vm.loader.import_name("six")
    super(SixOverlay, self).__init__(vm, "six", member_map, ast)


class AddMetaclassInstance(abstract.AtomicAbstractValue):
  """AddMetaclass instance (constructed by AddMetaclass.call())."""

  def __init__(self, meta, vm):
    super(AddMetaclassInstance, self).__init__("AddMetaclassInstance", vm)
    self.meta = meta
    self.vm = vm

  def call(self, node, unused, args):
    cls_var = args.posargs[0]
    for b in cls_var.bindings:
      cls = b.data
      log.debug("Adding metaclass %r to class %r", self.meta.data[0], cls)
      cls.cls = self.meta
    return node, cls_var


class AddMetaclass(abstract.PyTDFunction):
  """Implements the @six.add_metaclass decorator."""

  def __init__(self, name, vm):
    ast = vm.loader.import_name("six")
    method = ast.Lookup("six.add_metaclass")
    sigs = [abstract.PyTDSignature(name, sig, vm) for sig in method.signatures]
    super(AddMetaclass, self).__init__(name, sigs, method.kind, vm)

  def call(self, node, unused_func, args):
    """Adds a metaclass."""
    self._match_args(node, args)
    meta = args.posargs[0]
    return node, AddMetaclassInstance(meta, self.vm).to_variable(node)
