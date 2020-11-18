"""Implementation of special members of types and asyncio module."""

from pytype import abstract
from pytype import overlay


class TypesOverlay(overlay.Overlay):
  """A custom overlay for the 'types' module."""

  def __init__(self, vm):
    member_map = {
        "coroutine": CoroutineDecorator.make_for_types
    }
    ast = vm.loader.import_name("types")
    super().__init__(vm, "types", member_map, ast)


class AsyncioOverlay(overlay.Overlay):
  """A custom overlay for the 'asyncio' module."""

  def __init__(self, vm):
    member_map = {
        "coroutine": CoroutineDecorator.make_for_asyncio
    }
    ast = vm.loader.import_name("asyncio")
    super().__init__(vm, "asyncio", member_map, ast)


class CoroutineDecorator(abstract.PyTDFunction):
  """Implements the @types.coroutine and @asyncio.coroutine decorator."""

  @classmethod
  def make_for_types(cls, vm):
    return super().make("coroutine", vm, "types")

  @classmethod
  def make_for_asyncio(cls, vm):
    return super().make("coroutine", vm, "asyncio")

  def call(self, node, unused_func, args):
    """Marks the function as a generator-based coroutine."""
    self.match_args(node, args)
    func_var = args.posargs[0]
    for func in func_var.data:
      code = func.code
      if (not code.has_iterable_coroutine() and
          (self.module == "asyncio" or
           self.module == "types" and code.has_generator())):
        code.set_iterable_coroutine()
    return node, func_var
