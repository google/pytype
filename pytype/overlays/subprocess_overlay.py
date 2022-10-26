"""Support for the 'subprocess' library."""

from pytype.abstract import abstract
from pytype.overlays import overlay


class SubprocessOverlay(overlay.Overlay):
  """A custom overlay for the 'subprocess' module."""

  def __init__(self, ctx):
    member_map = {
        "Popen": Popen,
    }
    ast = ctx.loader.import_name("subprocess")
    super().__init__(ctx, "subprocess", member_map, ast)


class Popen(abstract.PyTDClass):
  """Custom implementation of subprocess.Popen."""

  class _Unloaded:
    pass

  def __init__(self, ctx):
    pyval = ctx.loader.import_name("subprocess").Lookup("subprocess.Popen")
    super().__init__("Popen", pyval, ctx)
    # lazily loaded because the signatures refer back to Popen itself
    self._new = Popen._Unloaded()

  @property
  def new(self):
    if isinstance(self._new, Popen._Unloaded):
      if "__new__" not in self.pytd_cls:
        self._new = None
      else:
        f = self.pytd_cls.Lookup("__new__")
        sigs = [
            abstract.PyTDSignature(f.name, sig, self.ctx)
            for sig in f.signatures
        ]
        self._new = PopenNew(f.name, sigs, f.kind, self.ctx)
    return self._new

  def get_own_new(self, node, value):
    new = self.new
    if new:
      return node, new.to_variable(node)
    return super().get_own_new(node, value)


class PopenNew(abstract.PyTDFunction):
  """Custom implementation of subprocess.Popen.__new__."""

  def _can_match_multiple(self, args):
    # We need to distinguish between Popen[bytes] and Popen[str]. This requires
    # an overlay because bytes/str can be distinguished definitely based on only
    # a few of the parameters, but pytype will fall back to less precise
    # matching if any of the parameters has an unknown type.
    found_ambiguous_arg = False
    for kw, literal in [("encoding", False), ("errors", False),
                        ("universal_newlines", True), ("text", True)]:
      if kw not in args.namedargs:
        continue
      if literal:
        ambiguous = any(not isinstance(v, abstract.ConcreteValue)
                        for v in args.namedargs[kw].data)
      else:
        ambiguous = any(isinstance(v, abstract.AMBIGUOUS_OR_EMPTY)
                        for v in args.namedargs[kw].data)
      if not ambiguous:
        return False
      found_ambiguous_arg = True
    if found_ambiguous_arg:
      return super()._can_match_multiple(args)
    else:
      return args.has_opaque_starargs_or_starstarargs()
