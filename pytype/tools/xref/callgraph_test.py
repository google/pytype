from __future__ import print_function

from pytype import config
from pytype import file_utils

from pytype.tests import test_base

from pytype.tools.xref import callgraph
from pytype.tools.xref import indexer


class CallgraphTest(test_base.TargetIndependentTest):
  """Tests for the callgraph."""

  def index_code(self, code, **kwargs):
    """Generate references from a code string."""
    args = {"version": self.python_version}
    args.update(kwargs)
    with file_utils.Tempdir() as d:
      d.create_file("t.py", code)
      options = config.Options.create(d["t.py"])
      options.tweak(**args)
      return indexer.process_file(options, preserve_pytype_vm=True)

  def assertAttrsEqual(self, attrs, expected):
    actual = {(x.name, x.type, x.attr) for x in attrs}
    self.assertCountEqual(actual, expected)

  def assertCallsEqual(self, calls, expected):
    actual = []
    for c in calls:
      actual.append(
          (c.function_id, [(a.name, a.node_type, a.type) for a in c.args]))
    self.assertCountEqual(actual, expected)

  def test_basic(self):
    ix = self.index_code("""\
        def f(x: str):
          y = x.strip()
          return y

        def g(y):
          a = f(y)
          b = complex(1, 2)
          c = b.real
          return c
    """)
    fns = callgraph.collect_functions(ix)
    self.assertCountEqual(fns.keys(), ["module.f", "module.g"])
    f = fns["module.f"]
    self.assertAttrsEqual(f.param_attrs,
                          {("x", "__builtin__.str", "x.strip")})
    self.assertAttrsEqual(f.local_attrs, set())
    self.assertCallsEqual(f.calls, [("str.strip", [])])
    self.assertEqual(f.ret.id, "module.f.y")
    self.assertEqual(f.params, [("x", "str")])

    g = fns["module.g"]
    self.assertAttrsEqual(g.param_attrs, set())
    self.assertAttrsEqual(g.local_attrs,
                          {("b", "__builtin__.complex", "b.real")})
    self.assertCallsEqual(g.calls, [
        ("f", [("y", "Param", "typing.Any")]),
        ("complex", [])
    ])
    self.assertEqual(g.ret.id, "module.g.c")
    self.assertEqual(g.params, [("y", "typing.Any")])

  def test_remote(self):
    code = """\
        import foo

        def f(a, b):
          x = foo.X(a)
          y = foo.Y(a, b)
          z = y.bar()
    """
    stub = """
      class X:
        def __init__(a: str) -> None: ...
      class Y:
        def __init__(a: str, b: int) -> None: ...
        def bar() -> int: ...
    """
    with file_utils.Tempdir() as d:
      d.create_file("t.py", code)
      d.create_file("foo.pyi", stub)
      options = config.Options.create(d["t.py"], pythonpath=d.path,
                                      version=self.python_version)
      ix = indexer.process_file(options, preserve_pytype_vm=True)
    fns = callgraph.collect_functions(ix)
    self.assertCountEqual(fns.keys(), ["module.f"])
    f = fns["module.f"]
    self.assertAttrsEqual(f.param_attrs, [])
    self.assertAttrsEqual(f.local_attrs, [("y", "foo.Y", "y.bar")])
    self.assertCallsEqual(f.calls, [
        ("X", [("a", "Param", "typing.Any")]),
        ("Y", [("a", "Param", "typing.Any"), ("b", "Param", "typing.Any")]),
        ("Y.bar", [])
    ])

  def test_no_outgoing_calls(self):
    """Capture a function with no outgoing calls."""
    ix = self.index_code("""\
        def f(x: int):
          return "hello"
    """)
    fns = callgraph.collect_functions(ix)
    self.assertCountEqual(fns.keys(), ["module.f"])
    f = fns["module.f"]
    self.assertAttrsEqual(f.param_attrs, [])
    self.assertAttrsEqual(f.local_attrs, [])
    self.assertCallsEqual(f.calls, [])
    self.assertEqual(f.params, [("x", "int")])


test_base.main(globals(), __name__ == "__main__")
