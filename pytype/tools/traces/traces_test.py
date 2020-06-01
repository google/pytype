# Lint as: python2, python3
"""Tests for traces.traces."""

import ast
import collections
import sys
import textwrap
from pytype import config
from pytype import file_utils
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.tests import test_utils
from pytype.tools.traces import traces
import unittest


class _NotImplementedVisitor(traces.MatchAstVisitor):

  def visit_Module(self, node):
    self.match(node)


class _TestVisitor(traces.MatchAstVisitor):

  def __init__(self, *args, **kwargs):
    super(_TestVisitor, self).__init__(*args, **kwargs)
    self.traces_by_node_type = collections.defaultdict(list)

  def generic_visit(self, node):
    try:
      matches = self.match(node)
    except NotImplementedError:
      return
    self.traces_by_node_type[node.__class__].extend(matches)


class TraceTest(unittest.TestCase):
  """Tests for traces.trace."""

  def test_traces(self):
    src = traces.trace("")
    trace, = src.traces[1]
    self.assertEqual(trace.op, "LOAD_CONST")
    self.assertEqual(trace.symbol, None)
    pyval, = trace.types
    self.assertEqual(pyval.name, "__builtin__.NoneType")
    self.assertEqual(pyval.cls.name, "__builtin__.NoneType")

  def test_options(self):
    src = traces.trace("", config.Options.create("rumpelstiltskin"))
    self.assertEqual(src.filename, "rumpelstiltskin")

  def test_external_type(self):
    with file_utils.Tempdir() as d:
      pyi_path = d.create_file("foo.pyi", "class Foo(object): ...")
      imports_info = d.create_file("imports_info", "foo %s" % pyi_path)
      src = traces.trace(
          "import foo\nx = foo.Foo()",
          config.Options.create(imports_map=imports_info))
    trace, = (x for x in src.traces[2] if x.op == "STORE_NAME")
    pyval, = trace.types
    self.assertEqual(pyval.name, "foo.Foo")
    self.assertEqual(pyval.cls.name, "foo.Foo")

  def test_py3_class(self):
    src = traces.trace(textwrap.dedent("""
      class Foo(object):
        pass
    """).lstrip())
    trace, = (x for x in src.traces[1] if x.op == "LOAD_BUILD_CLASS")
    pyval, = trace.types
    self.assertEqual(pyval.name, "typing.Callable")

  def test_unknown(self):
    # pytype represents unannotated function parameters as unknowns. Make sure
    # unknowns don't appear in the traced types.
    src = traces.trace("def f(x): return x")
    trace, = (x for x in src.traces[1] if x.op == "LOAD_FAST")
    pyval, = trace.types
    self.assertIsInstance(pyval, pytd.AnythingType)


class MatchAstTestCase(unittest.TestCase):
  """Base class for testing traces.MatchAstVisitor."""

  def _parse(self, text, options=None):
    text = textwrap.dedent(text).lstrip()
    return ast.parse(text), traces.trace(text, options)

  def _get_traces(self, text, node_type, options=None):
    module, src = self._parse(text, options)
    v = _TestVisitor(src, ast)
    v.visit(module)
    return v.traces_by_node_type[node_type]

  def assertTracesEqual(self, actual_traces, expected_traces):
    self.assertEqual(len(actual_traces), len(expected_traces))
    for trace, expected_trace in zip(actual_traces, expected_traces):
      loc, trace = trace
      expected_loc, expected_op, expected_symbol, expected_annots = (
          expected_trace)
      self.assertEqual(loc, expected_loc)
      self.assertEqual(trace.op, expected_op)
      self.assertEqual(trace.symbol, expected_symbol)
      self.assertEqual(len(trace.types), len(expected_annots))
      for t, annot in zip(trace.types, expected_annots):
        self.assertEqual(pytd_utils.Print(t), annot)


class MatchAstVisitorTest(MatchAstTestCase):
  """Tests for traces.MatchAstVisitor."""

  def test_not_implemented(self):
    module, src = self._parse("")
    v = _NotImplementedVisitor(src, ast)
    with self.assertRaises(NotImplementedError):
      v.visit(module)

  def test_import(self):
    matches = self._get_traces("import os, sys as tzt", ast.Import)
    self.assertTracesEqual(matches, [
        ((1, 7), "IMPORT_NAME", "os", ("module",)),
        ((1, 18), "STORE_NAME", "tzt", ("module",))])

  def test_import_from(self):
    matches = self._get_traces(
        "from os import path as _path, environ", ast.ImportFrom)
    self.assertTracesEqual(matches, [
        ((1, 23), "STORE_NAME", "_path", ("module",)),
        ((1, 30), "STORE_NAME", "environ", ("os._Environ[str]",))])


class MatchAttributeTest(MatchAstTestCase):
  """Tests for traces.MatchAstVisit.match_Attribute."""

  def test_basic(self):
    matches = self._get_traces("""
      x = 0
      print(x.real)
    """, ast.Attribute)
    self.assertTracesEqual(matches, [
        ((2, 8), "LOAD_ATTR", "real", ("int", "int"))])

  def test_multi(self):
    matches = self._get_traces("""
      class Foo(object):
        real = True
      x = 0
      (Foo.real, x.real)
    """, ast.Attribute)
    # The second attribute is at the wrong location due to limitations of
    # source.Code.get_attr_location(), but we can at least test that we get the
    # right number of traces with the right types.
    self.assertTracesEqual(matches, [
        ((4, 5), "LOAD_ATTR", "real", ("Type[Foo]", "bool")),
        ((4, 5), "LOAD_ATTR", "real", ("int", "int"))])

  def test_property(self):
    matches = self._get_traces("""
      class Foo(object):
        @property
        def x(self):
          return 42
      v = Foo().x
    """, ast.Attribute)
    self.assertTracesEqual(matches, [
        ((5, 10), "LOAD_ATTR", "x", ("Foo", "int"))])


class MatchNameTest(MatchAstTestCase):
  """Tests for traces.MatchAstVisitor.match_Name."""

  def test_basic(self):
    matches = self._get_traces("x = 42", ast.Name)
    self.assertTracesEqual(matches, [((1, 0), "STORE_NAME", "x", ("int",))])

  def test_multiline(self):
    matches = self._get_traces("""
      x = (1 +
           2)
    """, ast.Name)
    self.assertTracesEqual(matches, [((1, 0), "STORE_NAME", "x", ("int",))])

  def test_multiline_subscr(self):
    matches = self._get_traces("""
      x = [0]
      x[0] = (1,
              2)
    """, ast.Name)
    x_annot = "List[Union[int, Tuple[int, int]]]"
    self.assertTracesEqual(matches, [((1, 0), "STORE_NAME", "x", (x_annot,)),
                                     ((2, 0), "LOAD_NAME", "x", (x_annot,))])


class MatchCallTest(MatchAstTestCase):
  """Tests for traces.MatchAstVisitor.match_Call."""

  def test_basic(self):
    matches = self._get_traces("""
      def f(x):
        return x + 1.0
      f(42)
    """, ast.Call)
    self.assertTracesEqual(matches, [
        ((3, 0), "CALL_FUNCTION", "f", ("Callable[[Any], Any]", "float"))])

  def _test_chain(self, call_method_op):
    matches = self._get_traces("""
      class Foo(object):
        def f(self, x):
          return x
      Foo().f(42)
    """, ast.Call)
    self.assertTracesEqual(matches, [
        ((4, 0), "CALL_FUNCTION", "Foo", ("Type[Foo]", "Foo")),
        ((4, 0), call_method_op, "f", ("Callable[[Any], Any]", "int"))])

  @test_utils.skipFromPy((3, 7),
                         reason="instance methods match CALL_FUNCTION pre-3.7")
  def test_chain_pre37(self):
    self._test_chain("CALL_FUNCTION")

  @test_utils.skipBeforePy((3, 7),
                           reason="instance methods match CALL_METHOD in 3.7+")
  def test_chain_37(self):
    self._test_chain("CALL_METHOD")

  def test_multiple_bindings(self):
    matches = self._get_traces("""
      class Foo(object):
        @staticmethod
        def f(x):
          return x
      class Bar(object):
        @staticmethod
        def f(x):
          return x + 1.0
      f = Foo.f if __random__ else Bar.f
      f(42)
    """, ast.Call)
    self.assertTracesEqual(matches, [
        ((10, 0), "CALL_FUNCTION", "f",
         ("Callable[[Any], Any]", "Union[int, float]"))])

  def test_bad_call(self):
    matches = self._get_traces("""
      def f(): pass
      f(42)
    """, ast.Call)
    self.assertTracesEqual(
        matches, [((2, 0), "CALL_FUNCTION", "f", ("Callable[[], Any]", "Any"))])

  def _test_literal(self, call_method_op):
    matches = self._get_traces("''.upper()", ast.Call)
    self.assertTracesEqual(matches, [
        ((1, 0), call_method_op, "upper", ("Callable[[], str]", "str"))])

  @test_utils.skipFromPy((3, 7),
                         reason="instance methods match CALL_FUNCTION pre-3.7")
  def test_literal_pre37(self):
    self._test_literal("CALL_FUNCTION")

  @test_utils.skipBeforePy((3, 7),
                           reason="instance methods match CALL_METHOD in 3.7+")
  def test_literal_37(self):
    self._test_literal("CALL_METHOD")

  def test_lookahead(self):
    matches = self._get_traces("""
      def f(x, y, z):
        return x + y + z
      f(
        0,
        1,
        2,
      )
    """, ast.Call)
    self.assertTracesEqual(matches, [
        ((3, 0), "CALL_FUNCTION", "f",
         ("Callable[[Any, Any, Any], Any]", "int"))])


class MatchConstantTest(MatchAstTestCase):

  @test_utils.skipFromPy((3, 8),
                         reason="numbers are ast.Constant in 3.8+")
  def test_num(self):
    matches = self._get_traces("v = 42", ast.Num)
    self.assertTracesEqual(matches, [((1, 4), "LOAD_CONST", 42, ("int",))])

  @test_utils.skipFromPy((3, 8),
                         reason="strings are ast.Constant in 3.8+")
  def test_str(self):
    matches = self._get_traces("v = 'hello'", ast.Str)
    self.assertTracesEqual(matches, [((1, 4), "LOAD_CONST", "hello", ("str",))])

  @test_utils.skipFromPy((3, 8),
                         reason="unicode strings are ast.Constant in 3.8+")
  def test_unicode(self):
    matches = self._get_traces("v = u'hello'", ast.Str)
    self.assertTracesEqual(matches, [((1, 4), "LOAD_CONST", "hello", ("str",))])

  @test_utils.skipFromPy((3, 8),
                         reason="byte strings are ast.Constant in 3.8+")
  def test_bytes(self):
    matches = self._get_traces("v = b'hello'", ast.Bytes)
    self.assertTracesEqual(
        matches, [((1, 4), "LOAD_CONST", b"hello", ("bytes",))])

  @test_utils.skipFromPy((3, 8),
                         reason="bools are ast.Constant in 3.8+")
  def test_bool(self):
    matches = self._get_traces("v = True", ast.NameConstant)
    self.assertTracesEqual(matches, [((1, 4), "LOAD_CONST", True, ("bool",))])

  @test_utils.skipFromPy((3, 8),
                         reason="ellipsis are ast.Constant in 3.8+")
  def test_ellipsis(self):
    matches = self._get_traces("v = ...", ast.Ellipsis)
    self.assertTracesEqual(
        matches, [((1, 4), "LOAD_CONST", Ellipsis, ("ellipsis",))])

  @test_utils.skipBeforePy((3, 8),
                           reason="numbers are ast.Constant in 3.8+")
  def test_num_38(self):
    matches = self._get_traces("v = 42", ast.Constant)
    self.assertTracesEqual(matches, [((1, 4), "LOAD_CONST", 42, ("int",))])

  @test_utils.skipBeforePy((3, 8),
                           reason="strings are ast.Constant in 3.8+")
  def test_str_38(self):
    matches = self._get_traces("v = 'hello'", ast.Constant)
    self.assertTracesEqual(matches, [((1, 4), "LOAD_CONST", "hello", ("str",))])

  @test_utils.skipBeforePy((3, 8),
                           reason="unicode strings are ast.Constant in 3.8+")
  def test_unicode_38(self):
    matches = self._get_traces("v = u'hello'", ast.Constant)
    self.assertTracesEqual(matches, [((1, 4), "LOAD_CONST", "hello", ("str",))])

  @test_utils.skipBeforePy((3, 8),
                           reason="byte strings are ast.Constant in 3.8+")
  def test_bytes_38(self):
    matches = self._get_traces("v = b'hello'", ast.Constant)
    self.assertTracesEqual(
        matches, [((1, 4), "LOAD_CONST", b"hello", ("bytes",))])

  @test_utils.skipBeforePy((3, 8),
                           reason="bools are ast.Constant in 3.8+")
  def test_bool_38(self):
    matches = self._get_traces("v = True", ast.Constant)
    self.assertTracesEqual(matches, [((1, 4), "LOAD_CONST", True, ("bool",))])

  @test_utils.skipBeforePy((3, 8),
                           reason="ellipsis are ast.Constant in 3.8+")
  def test_ellipsis_38(self):
    matches = self._get_traces("v = ...", ast.Constant)
    self.assertTracesEqual(
        matches, [((1, 4), "LOAD_CONST", Ellipsis, ("ellipsis",))])


class MatchSubscriptTest(MatchAstTestCase):

  def test_index(self):
    matches = self._get_traces("""
      v = "hello"
      print(v[0])
    """, ast.Subscript)
    self.assertTracesEqual(
        matches, [((2, 6), "BINARY_SUBSCR", "__getitem__", ("str",))])

  def test_simple_slice(self):
    matches = self._get_traces("""
      v = "hello"
      print(v[:-1])
    """, ast.Subscript)
    self.assertTracesEqual(
        matches, [((2, 6), "BINARY_SUBSCR", "__getitem__", ("str",))])

  def test_complex_slice(self):
    matches = self._get_traces("""
      v = "hello"
      print(v[0:4:2])
    """, ast.Subscript)
    self.assertTracesEqual(
        matches, [((2, 6), "BINARY_SUBSCR", "__getitem__", ("str",))])


class MatchBinOpTest(MatchAstTestCase):

  def test_modulo(self):
    matches = self._get_traces("""
      v = "hello %s"
      print(v % "world")
    """, ast.BinOp)
    self.assertTracesEqual(
        matches, [((2, 6), "BINARY_MODULO", "__mod__", ("str",))])

  def test_modulo_multiline_string(self):
    matches = self._get_traces("""
      ('%s'
       '%s' %
       (__any_object__,
        __any_object__))
    """, ast.BinOp)
    self.assertTracesEqual(
        matches, [((1, 1), "BINARY_MODULO", "__mod__", ("str",))])


class MatchLambdaTest(MatchAstTestCase):

  def test_basic(self):
    matches = self._get_traces("lambda x: x.upper()", ast.Lambda)
    sym = None if sys.version_info.major == 2 else "<lambda>"
    self.assertTracesEqual(
        matches, [((1, 0), "MAKE_FUNCTION", sym, ("Callable[[Any], Any]",))])

  def test_function_locals(self):
    matches = self._get_traces("""
      def f():
        return lambda x: x.upper()
    """, ast.Lambda)
    sym = None if sys.version_info.major == 2 else "f.<locals>.<lambda>"
    self.assertTracesEqual(
        matches, [((2, 9), "MAKE_FUNCTION", sym, ("Callable[[Any], Any]",))])

  def test_multiple_functions(self):
    matches = self._get_traces("""
      def f():
        return (w for w in range(3)), lambda x: x.upper(), lambda y, z: (y, z)
    """, ast.Lambda)
    sym = "f.<locals>.<lambda>"
    self.assertTracesEqual(
        matches, [
            ((2, 32), "MAKE_FUNCTION", sym, ("Callable[[Any], Any]",)),
            ((2, 53), "MAKE_FUNCTION", sym, ("Callable[[Any, Any], Any]",))])


if __name__ == "__main__":
  unittest.main()
