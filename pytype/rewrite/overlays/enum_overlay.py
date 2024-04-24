"""Enum overlay."""
from pytype.rewrite.abstract import abstract
from pytype.rewrite.overlays import overlays


@overlays.register_function('enum', 'EnumMeta.__new__')
class EnumMetaNew(abstract.PytdFunction):

  def call_with_mapped_args(self, *args, **kwargs):
    raise NotImplementedError()
