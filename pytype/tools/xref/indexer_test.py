import json
import textwrap

from pytype import config
from pytype import file_utils

from pytype.tests import test_base

from pytype.tools.xref import indexer
from pytype.tools.xref import kythe
from pytype.tools.xref import output


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

  def generate_kythe(self, code, **kwargs):
    """Generate a kythe index from a code string."""
    with file_utils.Tempdir() as d:
      d.create_file("t.py", code)
      options = config.Options([d["t.py"]])
      options.tweak(pythonpath=[d.path], version=self.python_version)
      kythe_args = kythe.Args(corpus="corpus", root="root")
      ix = indexer.process_file(options, kythe_args=kythe_args)
      # Collect all the references from the kythe graph.
      kythe_index = [json.loads(x) for x in output.json_kythe_graph(ix)]
      return kythe_index

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

  def test_type_annotations(self):
    ix = self.index_code("""\
       from __future__ import google_type_annotations
       def f(x: int) -> int:
         return x
    """)
    self.assertDef(ix, "module.f", "f", "FunctionDef")
    self.assertDef(ix, "module.f.x", "x", "Param")
    self.assertDefLocs(ix, "module.f", [(2, 0)])
    self.assertDefLocs(ix, "module.f.x", [(2, 6)])

  def test_resolved_imports(self):
    # We need all imports to be valid for pytype
    code = """\
        import f
        import x.y
        import a.b as c
        from a import b
        from p import q as r

        fx = f.X()
        cx = c.X()
        bx = b.X()
        rx = r.X()
        yx = x.y.X()
    """
    stub = "class X: pass"
    with file_utils.Tempdir() as d:
      d.create_file("t.py", code)
      d.create_file("f.pyi", stub)
      d.create_file("x/y.pyi", stub)
      d.create_file("a/b.pyi", stub)
      d.create_file("p/q.pyi", stub)
      options = config.Options([d["t.py"]])
      options.tweak(pythonpath=[d.path], version=self.python_version)
      ix = indexer.process_file(options)
      self.assertDef(ix, "module.f", "f", "Import")
      self.assertDef(ix, "module.x.y", "x.y", "Import")
      self.assertDef(ix, "module.c", "c", "Import")
      self.assertDef(ix, "module.b", "b", "ImportFrom")
      self.assertDef(ix, "module.r", "r", "ImportFrom")
      self.assertEqual(ix.modules["module.f"], "f")
      self.assertEqual(ix.modules["module.x.y"], "x.y")
      self.assertEqual(ix.modules["module.b"], "a.b")
      self.assertEqual(ix.modules["module.c"], "a.b")
      self.assertEqual(ix.modules["module.r"], "p.q")

      # Collect all the references from the kythe graph.
      kythe_index = [json.loads(x) for x in output.json_kythe_graph(ix)]
      refs = [x for x in kythe_index
              if x.get("edge_kind") == "/kythe/edge/ref"]

      # Extract the span of text and the target symbol for each reference.
      src = ix.source.text
      out = []
      for r in refs:
        pos = r["source"]["signature"]
        start, end = pos[1:].split(":")
        start, end = int(start), int(end)
        text = src[start:end]
        out.append((text, r["target"]["signature"], r["target"]["path"]))

      expected = {
          # Imports as declarations in the source file
          ("f", "module.f", "t.py"),
          ("c", "module.c", "t.py"),
          ("b", "module.b", "t.py"),
          # Class X in remote files
          ("X", "module.X", "f.py"),
          ("X", "module.X", "a/b.py"),
          ("X", "module.X", "x/y.py"),
          ("X", "module.X", "p/q.py"),
          # Imports as references to remote files
          ("r", "module.r", "t.py"),
          ("b", ":module:", "a/b.py"),
          ("c", ":module:", "a/b.py"),
          ("f", ":module:", "f.py"),
          ("r", ":module:", "p/q.py"),
          ("x.y", ":module:", "x/y.py"),
          # x.y as references to remote files
          ("x", ":module:", "x/__init__.py"),
          ("y", ":module:", "x/y.py"),
      }

      # Resolve filepaths within the tempdir.
      expected = [(ref, target, d[path]) for (ref, target, path) in expected]
      self.assertEqual(set(out), set(expected))

  def test_source_text(self):
    # Don't try to read from the filesystem if we supply source_text
    code = textwrap.dedent("""
        def f(x):
          return 42
    """)
    options = config.Options(["/path/to/nonexistent/file.py"])
    options.tweak(version=self.python_version)
    ix = indexer.process_file(options, source_text=code)
    self.assertDef(ix, "module.f", "f", "FunctionDef")

  def test_kythe_args(self):
    code = textwrap.dedent("""
        def f(x):
          return 42
    """)
    kythe_index = self.generate_kythe(code)
    k = kythe_index[0]["source"]
    self.assertEqual(k["corpus"], "corpus")
    self.assertEqual(k["root"], "root")

  def test_kythe_file_node(self):
    code = textwrap.dedent("""
        def f(x):
          return 42
    """)
    kythe_index = self.generate_kythe(code)
    # File nodes should have signature and lang empty
    file_nodes = kythe_index[0:2]
    for node in file_nodes:
      self.assertEqual(node["source"]["signature"], "")
      self.assertEqual(node["source"]["lang"], "")

    # Other nodes should have lang="python"
    node = kythe_index[3]
    self.assertEqual(node["source"]["lang"], "python")


test_base.main(globals(), __name__ == "__main__")
