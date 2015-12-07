"""Test for function and class decorators."""

import unittest


from pytype.tests import test_inference


class DecoratorsTest(test_inference.InferenceTest):
  """Test for function and class decorators."""

  def testStaticMethodSmoke(self):
    with self.Infer("""
      # from python-dateutil
      class tzwinbase(object):
          def list():
            pass
          # python-dateutil uses the old way of using @staticmethod:
          list = staticmethod(list)
    """, deep=True, solve_unknowns=False, extract_locals=False):
      pass

  @unittest.skip("TODO(kramm): list appears twice")
  def testStaticMethod(self):
    with self.Infer("""
      # from python-dateutil
      class tzwinbase(object):
          def list():
            pass
          list = staticmethod(list)
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertTypesMatchPytd(ty, """
        class tzwinbase(object):
          def list() -> NoneType
      """)


if __name__ == "__main__":
  test_inference.main()
