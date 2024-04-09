"""Builtin values with special behavior."""

from pytype.rewrite.abstract import abstract


class AssertType(abstract.SimpleFunction[abstract.SimpleReturn]):
  """assert_type implementation."""

  def __init__(self, ctx: abstract.ContextType):
    signature = abstract.Signature(
        ctx=ctx, name='assert_type', param_names=('variable', 'type'))
    super().__init__(
        ctx=ctx, name='assert_type', signatures=(signature,), module='builtins')

  def call_with_mapped_args(
      self, mapped_args: abstract.MappedArgs[abstract.FrameType],
  ) -> abstract.SimpleReturn:
    var = mapped_args.argdict['variable']
    typ = mapped_args.argdict['type']
    pp = self._ctx.errorlog.pretty_printer
    actual = pp.print_var_type(var, node=None)
    try:
      expected = abstract.get_atomic_constant(typ, str)
    except ValueError:
      expected = pp.print_type_of_instance(typ.get_atomic_value())
    if actual != expected:
      stack = frame.stack if (frame := mapped_args.frame) else None
      self._ctx.errorlog.assert_type(stack, actual, expected)
    return abstract.SimpleReturn(self._ctx.consts[None])
