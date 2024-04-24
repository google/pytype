from typing import cast

from pytype.rewrite.abstract import abstract
from pytype.rewrite.tests import test_utils

import unittest


class EnumMetaNewTest(test_utils.ContextfulTestBase):

  def test_call(self):
    # Simulate:
    #   class E(enum.Enum):
    #     X = 42
    metaclass = self.ctx.abstract_loader.load_value('enum', 'EnumMeta')
    name = self.ctx.consts['E']
    base = self.ctx.abstract_loader.load_value('enum', 'Enum')
    members = {self.ctx.consts['X'].to_variable():
               self.ctx.consts[42].to_variable()}
    args = abstract.Args(posargs=(
        metaclass.to_variable(),
        name.to_variable(),
        abstract.Tuple(self.ctx, (base.to_variable(),)).to_variable(),
        abstract.Dict(self.ctx, members).to_variable(),
    ))
    enum_meta_new = cast(abstract.PytdFunction,
                         metaclass.get_attribute('__new__'))
    enum_cls = enum_meta_new.call(args).get_return_value()
    self.assertIsInstance(enum_cls, abstract.SimpleClass)
    self.assertIn('X', enum_cls.members)
    enum_member = enum_cls.members['X']
    self.assertIsInstance(enum_member, abstract.BaseInstance)
    self.assertEqual(enum_member.cls.name, 'E')


if __name__ == '__main__':
  unittest.main()
