"""Tests for reloading generated pyi."""


from pytype import utils
from pytype.pytd import pytd
from pytype.tests import test_inference


class ReingestTest(test_inference.InferenceTest):
  """Tests for reloading the pyi we generate."""

  def testContainer(self):
    ty = self.Infer("""
      class Container:
        def Add(self):
          pass
      class A(Container):
        pass
    """)
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd.Print(ty))
      self.assertNoErrors("""
        # u.py
        from foo import A
        A().Add()
      """, pythonpath=[d.path])

  def testUnion(self):
    ty = self.Infer("""
      class Union(object):
        pass
      x = {"Union": Union}
    """)
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd.Print(ty))
      self.assertNoErrors("""
        from foo import Union
      """, pythonpath=[d.path])


if __name__ == "__main__":
  test_inference.main()
