"""Tests for loading and saving pickled files."""


from pytype import utils
from pytype.tests import test_inference


class PickleTest(test_inference.InferenceTest):
  """Tests for loading and saving pickled files."""

  def testContainer(self):
    pickled = self.Infer("""
      from __future__ import google_type_annotations
      import collections, json
      def f() -> collections.OrderedDict[int, int]:
        return collections.OrderedDict({1: 1})
      def g() -> json.JSONDecoder:
        return json.JSONDecoder()
    """, pickle=True, module_name="foo")
    with utils.Tempdir() as d:
      u = d.create_file("u.pickled", pickled)
      ty = self.Infer("""
        import u
        r = u.f()
      """, pythonpath=[""], imports_map={"u": u})
      self.assertTypesMatchPytd(ty, """
        import collections
        u = ...  # type: module
        r = ...  # type: collections.OrderedDict[int, int]
      """)

  def testType(self):
    pickled = self.Infer("""
      x = type
    """, pickle=True, module_name="foo")
    with utils.Tempdir() as d:
      u = d.create_file("u.pickled", pickled)
      ty = self.Infer("""
        import u
        r = u.x
      """, pythonpath=[""], imports_map={"u": u})
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        import collections
        u = ...  # type: module
        r = ...  # type: Type[type]
      """)


if __name__ == "__main__":
  test_inference.main()
