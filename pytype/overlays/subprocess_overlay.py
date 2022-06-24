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

  def _match_bytes_mode(self, args, view):
    """Returns the matching signature if bytes mode was definitely requested."""
    for kw, val in [("encoding", self.ctx.convert.none),
                    ("errors", self.ctx.convert.none),
                    ("universal_newlines", self.ctx.convert.false),
                    ("text", self.ctx.convert.false)]:
      if kw in args.namedargs and view[args.namedargs[kw]].data != val:
        return None
    return self.signatures[-2]

  def _match_text_mode(self, args, view):
    """Returns the matching signature if text mode was definitely requested."""
    for i, (kw, typ) in enumerate([("encoding", self.ctx.convert.str_type),
                                   ("errors", self.ctx.convert.str_type)]):
      if kw in args.namedargs and view[args.namedargs[kw]].data.cls == typ:
        return self.signatures[i]
    for i, (kw,
            val) in enumerate([("universal_newlines", self.ctx.convert.true),
                               ("text", self.ctx.convert.true)], 2):
      if kw in args.namedargs and view[args.namedargs[kw]].data == val:
        return self.signatures[i]
    return None

  def _yield_matching_signatures(self, node, args, view, alias_map):
    # In Python 3, we need to distinguish between Popen[bytes] and Popen[str].
    # This requires an overlay because:
    # (1) the stub uses typing.Literal, which pytype doesn't support yet, and
    # (2) bytes/text can be distinguished definitely based on only a few of
    #     the parameters, but pytype will fall back to less precise matching
    #     if any of the parameters has an unknown type.
    sig = self._match_text_mode(args, view)
    if sig is None:
      sig = self._match_bytes_mode(args, view)
    if sig is None:
      yield from super()._yield_matching_signatures(
          node, args, view, alias_map)
      return
    arg_dict, subst = sig.substitute_formal_args_old(
        node, args, view, alias_map)
    yield sig, arg_dict, subst
