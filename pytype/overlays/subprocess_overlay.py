"""Support for the 'subprocess' library."""

from pytype import abstract
from pytype import function
from pytype import overlay


class SubprocessOverlay(overlay.Overlay):
  """A custom overlay for the 'subprocess' module."""

  def __init__(self, vm):
    member_map = {
        "Popen": Popen,
    }
    ast = vm.loader.import_name("subprocess")
    super().__init__(vm, "subprocess", member_map, ast)


class Popen(abstract.PyTDClass):
  """Custom implementation of subprocess.Popen."""

  _UNLOADED = object()

  def __init__(self, vm):
    pyval = vm.loader.import_name("subprocess").Lookup("subprocess.Popen")
    super().__init__("Popen", pyval, vm)
    # lazily loaded because the signatures refer back to Popen itself
    self._new = self._UNLOADED

  @property
  def new(self):
    if self._new is self._UNLOADED:
      try:
        f = self.pytd_cls.Lookup("__new__")
      except KeyError:
        self._new = None
      else:
        sigs = [function.PyTDSignature(f.name, sig, self.vm)
                for sig in f.signatures]
        self._new = PopenNew(f.name, sigs, f.kind, self.vm)
    return self._new

  def get_own_new(self, node, value):
    if self.new:
      return node, self.new.to_variable(node)
    return super().get_own_new(node, value)


class PopenNew(abstract.PyTDFunction):
  """Custom implementation of subprocess.Popen.__new__."""

  def _match_bytes_mode(self, args, view):
    """Returns the matching signature if bytes mode was definitely requested."""
    for kw, val in [("encoding", self.vm.convert.none),
                    ("errors", self.vm.convert.none),
                    ("universal_newlines", self.vm.convert.false),
                    ("text", self.vm.convert.false)]:
      if kw in args.namedargs and view[args.namedargs[kw]].data != val:
        return None
    return self.signatures[-2]

  def _match_text_mode(self, args, view):
    """Returns the matching signature if text mode was definitely requested."""
    for i, (kw, typ) in enumerate([("encoding", self.vm.convert.str_type),
                                   ("errors", self.vm.convert.str_type)]):
      if kw in args.namedargs and view[args.namedargs[kw]].data.cls == typ:
        return self.signatures[i]
    for i, (kw, val) in enumerate([("universal_newlines", self.vm.convert.true),
                                   ("text", self.vm.convert.true)], 2):
      if kw in args.namedargs and view[args.namedargs[kw]].data == val:
        return self.signatures[i]
    return None

  def _yield_matching_signatures(self, node, args, view, alias_map):
    if self.vm.PY2:
      sig = None
    else:
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
      for sig_info in super()._yield_matching_signatures(
          node, args, view, alias_map):
        yield sig_info
      return
    arg_dict, subst = sig.substitute_formal_args(node, args, view, alias_map)
    yield sig, arg_dict, subst
