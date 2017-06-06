"""Implementation of special members of Python 2's abc library."""

from pytype import abstract
from pytype import overlay


class ABCOverlay(overlay.Overlay):
  """A custom overlay for the 'abc' module."""

  def __init__(self, vm):
    member_map = {"abstractmethod": AbstractMethod}
    ast = vm.loader.import_name("abc")
    super(ABCOverlay, self).__init__(vm, "abc", member_map, ast)


class AbstractMethod(abstract.PyTDFunction):
  """Implements the @abc.abstractmethod decorator."""

  def __init__(self, name, vm):
    ast = vm.loader.import_name("abc")
    method = ast.Lookup("abc.abstractmethod")
    sigs = [abstract.PyTDSignature(name, sig, vm) for sig in method.signatures]
    super(AbstractMethod, self).__init__(name, sigs, method.kind, vm)

  def call(self, node, unused_func, args):
    """Marks that the given function is abstract."""
    self._match_args(node, args)

    # Since we have only 1 argument, it's easy enough to extract.
    if args.posargs:
      func_var = args.posargs[0]
    else:
      func_var = args.namedargs["function"]

    for func in func_var.data:
      if isinstance(func, (abstract.Function, abstract.BoundFunction)):
        func.is_abstract = True

    return node, func_var
