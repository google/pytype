from pytype.rewrite import abstract

import unittest


class PythonConstantTest(unittest.TestCase):

  def test_equal(self):
    c1 = abstract.PythonConstant('a')
    c2 = abstract.PythonConstant('a')
    self.assertEqual(c1, c2)

  def test_not_equal(self):
    c1 = abstract.PythonConstant('a')
    c2 = abstract.PythonConstant('b')
    self.assertNotEqual(c1, c2)


if __name__ == '__main__':
  unittest.main()
