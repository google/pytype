from pytype import config
from pytype import file_utils

from pytype.tests import test_base

from pytype.tools.xref import indexer


def index_code(code):
  """Generate references from a code string."""
  with file_utils.Tempdir() as d:
    d.create_file("t.py", code)
    options = config.Options([d["t.py"]])
    return indexer.process_file(options)


class IndexerTest(test_base.TargetIndependentTest):
  """Tests for the indexer."""

  def assertDef(self, index, fqname, name, typ):
    self.assertTrue(fqname in index.defs)
    d = index.defs[fqname]
    self.assertEqual(d.name, name)
    self.assertEqual(d.typ, typ)

  def assertDefLocs(self, index, fqname, locs):
    self.assertTrue(fqname in index.locs)
    deflocs = index.locs[fqname]
    self.assertCountEqual([x.location for x in deflocs], locs)

  def assertAttrs(self, obj, attr_dict):
    for k, v in attr_dict.items():
      self.assertEqual(v, getattr(obj, k))

  def test_class_def(self):
    ix = index_code("""\
        class A(object):
          pass
        b = A()
    """)
    self.assertDef(ix, "module::A", "A", "ClassDef")
    self.assertDef(ix, "module::b", "b", "Store")
    self.assertDefLocs(ix, "module::A", [(1, 0)])
    self.assertDefLocs(ix, "module::b", [(3, 0)])

  def test_function_def(self):
    ix = index_code("""\
        def f(x, y):
          a = 1  # local variable
    """)
    self.assertDef(ix, "module::f", "f", "FunctionDef")
    self.assertDef(ix, "module:function f::x", "x", "Param")
    self.assertDef(ix, "module:function f::y", "y", "Param")
    self.assertDef(ix, "module:function f::a", "a", "Store")
    self.assertDefLocs(ix, "module::f", [(1, 0)])
    self.assertDefLocs(ix, "module:function f::x", [(1, 6)])
    self.assertDefLocs(ix, "module:function f::y", [(1, 9)])
    self.assertDefLocs(ix, "module:function f::a", [(2, 2)])

  def test_param_reuse(self):
    ix = index_code("""\
        def f(x):
          x = 1 # reuse param variable
    """)
    self.assertDef(ix, "module::f", "f", "FunctionDef")
    self.assertDef(ix, "module:function f::x", "x", "Param")
    self.assertDefLocs(ix, "module::f", [(1, 0)])
    self.assertDefLocs(ix, "module:function f::x", [(1, 6), (2, 2)])

  def test_nested_function(self):
    ix = index_code("""\
        def f(x):
          def g(x):  # shadows x
            x = 1  # should be f:g::x
    """)
    self.assertDef(ix, "module::f", "f", "FunctionDef")
    self.assertDef(ix, "module:function f::x", "x", "Param")
    self.assertDef(ix, "module:function f::g", "g", "FunctionDef")
    self.assertDef(ix, "module:function f:function g::x", "x", "Param")
    self.assertDefLocs(ix, "module:function f::x", [(1, 6)])
    self.assertDefLocs(ix, "module:function f:function g::x", [(2, 8), (3, 4)])

  def test_resolved_imports(self):
    # We need all imports to be valid for pytype
    code = """\
        import foo
        import x.y
        import a.b as c
        from a import b
        from p import q as r
    """
    stub = "class X: pass"
    with file_utils.Tempdir() as d:
      d.create_file("t.py", code)
      d.create_file("foo.pyi", stub)
      d.create_file("x/y.pyi", stub)
      d.create_file("a/b.pyi", stub)
      d.create_file("p/q.pyi", stub)
      options = config.Options([d["t.py"]])
      options.tweak(pythonpath=[d.path])
      ix = indexer.process_file(options)
      self.assertDef(ix, "module::foo", "foo", "Import")
      self.assertDef(ix, "module::x.y", "x.y", "Import")
      self.assertDef(ix, "module::c", "c", "Import")
      self.assertDef(ix, "module::b", "b", "ImportFrom")
      self.assertDef(ix, "module::r", "r", "ImportFrom")
      self.assertEqual(ix.modules["module::foo"], "foo")
      self.assertEqual(ix.modules["module::x.y"], "x.y")
      self.assertEqual(ix.modules["module::b"], "a.b")
      self.assertEqual(ix.modules["module::c"], "a.b")
      self.assertEqual(ix.modules["module::r"], "p.q")

  def test_import_ref(self):
    # We need all imports to be valid for pytype
    code = """\
        import foo
        x = foo.Bar
    """
    stub = "class Bar: pass"
    with file_utils.Tempdir() as d:
      d.create_file("t.py", code)
      d.create_file("foo.pyi", stub)
      options = config.Options([d["t.py"]])
      options.tweak(pythonpath=[d.path])
      ix = indexer.process_file(options)
      self.assertDef(ix, "module::foo", "foo", "Import")
      self.assertDef(ix, "module::x", "x", "Store")
      self.assertEqual(ix.modules["module::foo"], "foo")
      expected = [
          ({"name": "foo", "typ": "Name", "scope": "module",
            "location": (2, 4)},
           {"name": "foo", "scope": "module"}),
          ({"name": "foo.Bar", "typ": "Attribute", "scope": "module",
            "location": (2, 4)},
           {"name": "Bar", "scope": "foo/module"})
      ]
      for (ref, defn), (expected_ref, expected_defn) in zip(ix.links, expected):
        self.assertAttrs(ref, expected_ref)
        self.assertAttrs(defn, expected_defn)


test_base.main(globals(), __name__ == "__main__")
