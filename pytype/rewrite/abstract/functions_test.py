from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import functions
from pytype.rewrite.tests import test_utils

import unittest


class SignatureTest(unittest.TestCase):

  def test_from_code(self):
    module_code = test_utils.parse("""
      def f(x, /, *args, y, **kwargs):
        pass
    """)
    func_code = module_code.consts[0]
    signature = functions.Signature.from_code('f', func_code)
    self.assertEqual(repr(signature), 'def f(x, /, *args, y, **kwargs)')

  def test_map_args(self):
    signature = functions.Signature('f', ('x', 'y'))
    x = base.PythonConstant('x').to_variable()
    y = base.PythonConstant('y').to_variable()
    args = signature.map_args([x, y])
    self.assertEqual(args, {'x': x, 'y': y})

  def test_fake_args(self):
    signature = functions.Signature('f', ('x', 'y'))
    args = signature.make_fake_args()
    self.assertEqual(set(args), {'x', 'y'})


class InterpreterFunctionTest(unittest.TestCase):

  def test_init(self):
    module_code = test_utils.parse("""
      def f(x, /, *args, y, **kwargs):
        pass
    """)
    func_code = module_code.consts[0]
    f = functions.InterpreterFunction(
        name='f', code=func_code, enclosing_scope=())
    self.assertEqual(len(f.signatures), 1)
    self.assertEqual(repr(f.signatures[0]), 'def f(x, /, *args, y, **kwargs)')


if __name__ == '__main__':
  unittest.main()
