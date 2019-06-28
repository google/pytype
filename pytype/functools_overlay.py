"""Implementation of special objects in functools."""

from pytype import abstract
from pytype import overlay
from pytype.pytd import pytd


class FunctoolsOverlay(overlay.Overlay):

  def __init__(self, vm):
    member_map = {"partial": build_partial}
    ast = vm.loader.import_name("functools")
    super(FunctoolsOverlay, self).__init__(vm, "functools", member_map, ast)


class Partial(abstract.PyTDFunction):
  """Implementation of functools.partial."""

  def _yield_matching_signatures(self, node, args, view, alias_map):
    if args.posargs:
      for f in args.posargs[0].data:
        # If f cannot be represented as a callable with a fixed number of
        # parameters, then we need to use the fallback signature that does not
        # match parameters. We require an overlay for this because it's usually
        # correct for, e.g., `def f(x=None): ...` to match `Callable[[], Any]`.
        if not isinstance(f.to_type(node), pytd.CallableType):
          # We also enter this block when f is a class, which is fine for now
          # because we can't match constructors against callables yet.
          use_fallback = True
          break
      else:
        use_fallback = False
    else:
      use_fallback = False
    if use_fallback:
      sig = self.signatures[-1]
      arg_dict, subst = sig.substitute_formal_args(node, args, view, alias_map)
      yield sig, arg_dict, subst
    else:
      for sig_info in super(Partial, self)._yield_matching_signatures(
          node, args, view, alias_map):
        yield sig_info


def build_partial(name, vm):
  return Partial.make(name, vm, "functools")
