"""Tests for loading and saving pickled files."""

from pytype import file_utils
from pytype.tests import test_base


class PickleTest(test_base.TargetPython3BasicTest):
  """Tests for loading and saving pickled files."""

  def test_container(self):
    pickled = self.Infer("""
      import collections, json
      def f() -> collections.OrderedDict[int, int]:
        return collections.OrderedDict({1: 1})
      def g() -> json.JSONDecoder:
        return json.JSONDecoder()
    """, pickle=True, module_name="foo")
    with file_utils.Tempdir() as d:
      u = d.create_file("u.pickled", pickled)
      ty = self.Infer("""
        import u
        r = u.f()
      """, deep=False, pythonpath=[""], imports_map={"u": u})
      self.assertTypesMatchPytd(ty, """
        import collections
        u = ...  # type: module
        r = ...  # type: collections.OrderedDict[int, int]
      """)


test_base.main(globals(), __name__ == "__main__")
