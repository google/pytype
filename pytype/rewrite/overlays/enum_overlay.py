"""Enum overlay."""
from pytype.rewrite.abstract import abstract
from pytype.rewrite.overlays import overlays


@overlays.register_function('enum', 'EnumMeta.__new__')
class EnumMetaNew(abstract.PytdFunction):
  """Overlay for EnumMeta.__new__."""

  def _convert_enum_member(self, cls, name, value):
    member = abstract.MutableInstance(self._ctx, cls)
    member.members['name'] = name
    member.members['value'] = value
    return member

  def _call_direct(self, mapped_args):
    argdict = mapped_args.argdict
    cls_name = abstract.get_atomic_constant(argdict['cls'], str)
    base_vars = abstract.get_atomic_constant(argdict['bases'], tuple)
    bases = tuple(base_var.get_atomic_value(abstract.SimpleClass)
                  for base_var in base_vars)
    member_vars = abstract.get_atomic_constant(argdict['classdict'], dict)
    members = {abstract.get_atomic_constant(k, str): v.get_atomic_value()
               for k, v in member_vars.items()}
    if (frame := mapped_args.frame):
      functions = frame.functions
      classes = frame.classes
    else:
      functions = classes = ()
    cls = abstract.InterpreterClass(
        ctx=self._ctx,
        name=cls_name,
        members=members,
        bases=bases,
        keywords={},
        functions=functions,
        classes=classes,
    )
    for k, v in cls.members.items():
      if k.startswith('__') and k.endswith('__'):
        continue
      cls.members[k] = self._convert_enum_member(cls, k, v)
    return abstract.SimpleReturn(cls)

  def call_with_mapped_args(
      self, mapped_args: abstract.MappedArgs[abstract.FrameType],
  ) -> abstract.SimpleReturn:
    try:
      return self._call_direct(mapped_args)
    except ValueError:
      return super().call_with_mapped_args(mapped_args)
