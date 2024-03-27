"""Builtin values with special behavior."""

from pytype.rewrite.abstract import abstract


class AssertType(abstract.SimpleFunction[abstract.SimpleReturn]):
  """assert_type implementation."""

  def __init__(self):
    signature = abstract.Signature(
        name='assert_type', param_names=('variable', 'type'))
    super().__init__(name='assert_type', signatures=(signature,))

  def call_with_mapped_args(
      self, mapped_args: abstract.MappedArgs[abstract.FrameType],
  ) -> abstract.SimpleReturn:
    var = mapped_args.argdict['variable']
    typ = mapped_args.argdict['type']
    # TODO(b/241479600): pretty-print the types and log an assert_type error if
    # they don't match.
    del var, typ
    return abstract.SimpleReturn(abstract.PythonConstant(None))
