from pytype import config
from pytype import file_utils

from pytype.tests import test_base

from pytype.tools.xref import indexer


class IndexerTest(test_base.TargetIndependentTest):
  """Tests for the indexer."""

  def index_code(self, code, **kwargs):
    """Generate references from a code string."""
    args = {"version": self.python_version}
    args.update(kwargs)
    with file_utils.Tempdir() as d:
      d.create_file("t.py", code)
      options = config.Options([d["t.py"]])
      options.tweak(**args)
      return indexer.process_file(options)

  def assertDef(self, index, fqname, name, typ):
    self.assertTrue(fqname in index.defs)
    d = index.defs[fqname]
    self.assertEqual(d.name, name)
    self.assertEqual(d.typ, typ)

  def assertDefLocs(self, index, fqname, locs):
    self.assertTrue(fqname in index.locs)
    deflocs = index.locs[fqname]
    self.assertCountEqual([x.location for x in deflocs], locs)

  def test_param_reuse(self):
    ix = self.index_code("""\
        def f(x):
          x = 1 # reuse param variable
    """)
    self.assertDef(ix, "module.f", "f", "FunctionDef")
    self.assertDef(ix, "module.f.x", "x", "Param")
    self.assertDefLocs(ix, "module.f", [(1, 0)])
    self.assertDefLocs(ix, "module.f.x", [(1, 6), (2, 2)])

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
      options.tweak(pythonpath=[d.path], version=self.python_version)
      ix = indexer.process_file(options)
      self.assertDef(ix, "module.foo", "foo", "Import")
      self.assertDef(ix, "module.x.y", "x.y", "Import")
      self.assertDef(ix, "module.c", "c", "Import")
      self.assertDef(ix, "module.b", "b", "ImportFrom")
      self.assertDef(ix, "module.r", "r", "ImportFrom")
      self.assertEqual(ix.modules["module.foo"], "foo")
      self.assertEqual(ix.modules["module.x.y"], "x.y")
      self.assertEqual(ix.modules["module.b"], "a.b")
      self.assertEqual(ix.modules["module.c"], "a.b")
      self.assertEqual(ix.modules["module.r"], "p.q")


test_base.main(globals(), __name__ == "__main__")
