import ast
import json
import textwrap

from pytype import config
from pytype import file_utils
from pytype.pytd import pytd

from pytype.tests import test_base

from pytype.tools.xref import indexer
from pytype.tools.xref import kythe
from pytype.tools.xref import output


class IndexerTest(test_base.TargetIndependentTest):
  """Tests for the indexer."""

  def index_code(self, code, return_ast=False, **kwargs):
    """Generate references from a code string."""
    ast_factory = kwargs.pop("ast_factory", None)
    keep_pytype_data = kwargs.pop("keep_pytype_data", False)
    annotate_ast = kwargs.pop("annotate_ast", False)

    args = {"version": self.python_version}
    args.update(kwargs)
    with file_utils.Tempdir() as d:
      d.create_file("t.py", code)
      options = config.Options.create(d["t.py"])
      options.tweak(**args)
      ix, ast_root = indexer.process_file(
          options,
          keep_pytype_data=keep_pytype_data,
          ast_factory=ast_factory,
          annotate_ast=annotate_ast)
      if return_ast:
        return ix, ast_root
      else:
        return ix

  def generate_kythe(self, code, **kwargs):
    """Generate a kythe index from a code string."""
    with file_utils.Tempdir() as d:
      d.create_file("t.py", code)
      options = config.Options.create(d["t.py"])
      options.tweak(pythonpath=[d.path], version=self.python_version)
      kythe_args = kythe.Args(corpus="corpus", root="root")
      ix, _ = indexer.process_file(options, kythe_args=kythe_args)
      # Collect all the references from the kythe graph.
      kythe_index = [json.loads(x) for x in output.json_kythe_graph(ix)]
      return kythe_index

  def assertDef(self, index, fqname, name, typ):
    self.assertIn(fqname, index.defs)
    d = index.defs[fqname]
    self.assertEqual(d.name, name)
    self.assertEqual(d.typ, typ)

  def assertDefLocs(self, index, fqname, locs):
    self.assertIn(fqname, index.locs)
    deflocs = index.locs[fqname]
    self.assertCountEqual([x.location for x in deflocs], locs)

  def assertTypeMapEqual(self, type_map, expected):
    self.assertEqual({k: pytd.Print(v) for k, v in type_map.items()}, expected)

  def test_custom_ast_parser(self):
    called = [False]
    def ast_factory(options):
      del options  # Unused
      called[0] = True
      return ast

    unused_indexer, ast_root = self.index_code(
        "x = {}", return_ast=True, ast_factory=ast_factory, annotate_ast=True)
    self.assertTrue(called[0])
    name_node = ast_root.body[0].targets[0]
    self.assertIsNotNone(name_node.resolved_type)
    self.assertIsNotNone(name_node.resolved_annotation)

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
      options = config.Options.create(d["t.py"])
      options.tweak(pythonpath=[d.path], version=self.python_version)
      ix, _ = indexer.process_file(options)
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
    options = config.Options.create("/path/to/nonexistent/file.py")
    options.tweak(version=self.python_version)
    ix, _ = indexer.process_file(options, source_text=code)
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

  def test_multiline_attr(self):
    # Test that lookahead doesn't crash.
    self.index_code(textwrap.dedent("""
        x = ""
        def f():
          return (x.
                  upper())
    """))

  def test_literal_attr(self):
    # Test that creating a ref id from a literal doesn't crash.
    self.index_code(textwrap.dedent("""
      x = {1: 2}.items()
      y = [1, 2].reverse()
    """))

  def test_finalize_refs(self):
    code = textwrap.dedent("""
      x = ""
      def f():
        return x.upper()
    """)
    ix = self.index_code(code, keep_pytype_data=True)
    expected_refs = (("x", "str"), ("x.upper", ("str", "Callable[[], str]")))

    def get_data(ref):
      if ref.data.__class__ is tuple:
        return (ref.name, tuple(pytd.Print(t) for t in ref.data))
      else:
        return (ref.name, pytd.Print(ref.data))

    self.assertCountEqual((get_data(ref) for ref in ix.refs), expected_refs)
    self.assertCountEqual((get_data(ref) for ref, _ in ix.links), expected_refs)

  def test_type_map(self):
    code = textwrap.dedent("""\
      def f():
        x = ""
        return x
    """)
    ix = self.index_code(code, keep_pytype_data=True)
    type_map = output.type_map(ix)
    self.assertTypeMapEqual(type_map, {(3, 9): "str"})

  def test_type_map_attr(self):
    code = textwrap.dedent("""\
      class X:
        n = 42
      def f():
        return X.n
    """)
    ix = self.index_code(code, keep_pytype_data=True)
    type_map = output.type_map(ix)
    self.assertTypeMapEqual(type_map, {(4, 9): "Type[X]", (4, 11): "int"})

  def test_type_map_multiline_attr(self):
    code = textwrap.dedent("""\
      class X:
        n = 42
      def f():
        return (X.
          n)
    """)
    ix = self.index_code(code, keep_pytype_data=True)
    type_map = output.type_map(ix)
    self.assertTypeMapEqual(type_map, {(4, 10): "Type[X]", (5, 4): "int"})

  def test_type_map_multiline_dotattr(self):
    code = textwrap.dedent("""\
      class X:
        n = 42
      def f():
        return (X
          .n)
    """)
    ix = self.index_code(code, keep_pytype_data=True)
    type_map = output.type_map(ix)
    self.assertTypeMapEqual(type_map, {(4, 10): "Type[X]", (5, 5): "int"})

  def test_type_map_missing(self):
    # For obj.attr, sometimes we fail to find the location of attr. Test that
    # the type of obj is still accurate.
    code = textwrap.dedent("""\
      class X:
        n = 42
      def f():
        return (X
        {}
          .n)
    """).format("\n" * 10)
    ix = self.index_code(code, keep_pytype_data=True)
    type_map = output.type_map(ix)
    self.assertTypeMapEqual(type_map, {(4, 10): "Type[X]"})

  def test_unknown(self):
    # pytype represents unannotated function parameters as unknowns. Make sure
    # unknowns don't appear in the type map.
    code = textwrap.dedent("""\
      def f(x): return x
    """)
    ix = self.index_code(code, keep_pytype_data=True)
    type_map = output.type_map(ix)
    self.assertTypeMapEqual(type_map, {(1, 17): "Any"})

  def test_type_resolution(self):
    code = textwrap.dedent("""\
      class X:
        pass
      Y = X
    """)
    ix = self.index_code(code, keep_pytype_data=True)
    pyval = output.type_map(ix)[(3, 4)]
    # Make sure we have pytd.ClassType objects with the right .cls pointers.
    self.assertEqual(pyval.base_type.cls,
                     self.loader.builtins.Lookup("__builtin__.type"))
    self.assertEqual(pyval.parameters[0].cls.name, "X")


test_base.main(globals(), __name__ == "__main__")
