"""Tests for loading and saving pickled files."""

import pickle

from pytype.tests import test_base
from pytype.tests import test_utils


class PickleTest(test_base.BaseTest):
  """Tests for loading and saving pickled files."""

  def test_container(self):
    pickled = self.Infer("""
      import collections, json
      def f() -> collections.OrderedDict[int, int]:
        return collections.OrderedDict({1: 1})
      def g() -> json.JSONDecoder:
        return json.JSONDecoder()
    """, pickle=True, module_name="foo")
    with test_utils.Tempdir() as d:
      u = d.create_file("u.pickled", pickled)
      ty = self.Infer("""
        import u
        r = u.f()
      """, deep=False, pythonpath=[""], imports_map={"u": u})
      self.assertTypesMatchPytd(ty, """
        from typing import OrderedDict
        import u
        r = ...  # type: OrderedDict[int, int]
      """)

  def test_nested_class_name_clash(self):
    ty = self.Infer("""
      class Foo:
        pass
      class Bar:
        class Foo(Foo):
          pass
    """, module_name="foo", pickle=True)
    ast = pickle.loads(ty).ast
    base, = ast.Lookup("foo.Bar").Lookup("foo.Bar.Foo").bases
    self.assertEqual(base.name, "foo.Foo")

  def test_late_type_indirection(self):
    with self.DepTree([("foo.py", """
      class Foo:
        pass
    """, {"pickle": True}), ("bar.py", """
      import foo
      Bar = foo.Foo
    """, {"pickle": True}), ("baz.pyi", """
      import bar
      class Baz:
        x: bar.Bar
    """, {"pickle": True})]):
      self.Check("""
        import baz
        assert_type(baz.Baz.x, 'foo.Foo')
      """)


if __name__ == "__main__":
  test_base.main()
