# python3
"""Behavioral tests for pyi checker visitors."""

import textwrap

from pytype.tools.pyi_checker import definitions
from pytype.tools.pyi_checker import visitor
from typed_ast import ast3
import unittest


class DefinitionFinderTest(unittest.TestCase):

  def visit(self, source):
    """Parse a class source string and run the visitor over it."""
    ast = ast3.parse(textwrap.dedent(source))
    return visitor.DefinitionFinder("test").visit(ast)

  def assertLists(self, actual_vars, actual_functions, actual_classes,
                  variables=None, functions=None, classes=None):
    if variables is None:
      variables = []
    if functions is None:
      functions = []
    if classes is None:
      classes = []
    self.assertEqual(sorted(actual_vars), variables)
    self.assertEqual(sorted(actual_functions), functions)
    self.assertEqual(sorted(actual_classes), classes)

  def assertNames(self, actual, *, variables=None, functions=None,
                  classes=None):
    """Checks that every name is present and has the right type."""
    actual_vars, actual_funcs, actual_classes = visitor.split_namespace(actual)
    self.assertLists(actual_vars, actual_funcs, actual_classes,
                     variables, functions, classes)

  def assertClass(self, actual, *, fields=None, methods=None,
                  nested_classes=None):
    """Checks that the given members are found in the class."""
    self.assertLists(actual.fields, actual.methods, actual.nested_classes,
                     fields, methods, nested_classes)

  def test_definitions_basic(self):
    src = """
    x = "hello world"
    y: int
    z += 3
    def a_func(arg1, arg2):
      return arg1 + arg2
    class Thing:
      a: int
      b = 1
      def __init__(self, x):
        self.c = x
      def set_thing(self, y):
        self.d = y
    """
    namespace = self.visit(src)
    self.assertNames(
        namespace,
        variables=["x", "y", "z"],
        functions=["a_func"],
        classes=["Thing"])
    cls, = namespace["Thing"]
    self.assertClass(
        cls,
        fields=["a", "b", "c", "d"],
        methods=["__init__", "set_thing"])

  def test_differing_definition_kinds(self):
    src = """
    if some_condition(a, b):
      def a_func(a, b):
        return do_some_stuff(a, b, a+b)
    else:
      # a_func isn't supported without some_condition!
      a_func = NotImplemented
    """
    namespace = self.visit(src)
    a_func_defs = namespace["a_func"]
    self.assertEqual(len(a_func_defs), 2, "Expected 2 definitions for a_func")
    self.assertIsInstance(a_func_defs[0], definitions.Function)
    self.assertIsInstance(a_func_defs[1], definitions.Variable)

  def test_variables_options(self):
    src = """\
    if some_condition(a, b, c):
      x = 1
    else:
      x = "3"
    for x in y:
      pass
    """
    namespace = self.visit(src)
    self.assertNames(namespace, variables=["x"])
    self.assertEqual(len(namespace["x"]), 3, "Expected 3 definitions for x.")

  def test_variable_assignments(self):
    src = """
    # Attribute
    a.x.y.z = 1
    # Subscript
    b[1:-1] = [2, 12, 22]
    # Starred
    *c = [3, 3, 3]
    # Name
    d = 1
    # List
    [e, f] = ...
    # Tuple
    g, h, i = [x, y, z]
    """
    namespace = self.visit(src)
    self.assertNames(
        namespace,
        variables=["a", "b", "c", "d", "e", "f", "g", "h", "i"])

  def test_import_variables(self):
    src = """
    import a
    from some_mod import b, c, d
    """
    namespace = self.visit(src)
    self.assertNames(
        namespace,
        variables=["a", "b", "c", "d"])

  def test_nested_class(self):
    src = """
    class Outer:
      a: int
      b: int
      class Inner:
        a: str
        b: str
        def __init__(self, w, v):
          self.a = w
          self.b = v
        def set_c(self, c):
          self.c = c  # Visitor should visit function bodies in nested classes.
      def __init__(self, x, y):
        self.a = x + y
        self.b = x - y
        self.i = Inner(a*b, a/b)
    """
    namespace = self.visit(src)
    outer, = namespace["Outer"]
    self.assertClass(
        outer,
        fields=["a", "b", "i"],
        methods=["__init__"],
        nested_classes=["Inner"])
    inner, = outer.nested_classes["Inner"]
    self.assertClass(
        inner,
        fields=["a", "b", "c"],
        methods=["__init__", "set_c"])

  def test_class_attributes(self):
    src = """
    class A:
      z.y: int  # Doesn't make any sense in real python, shouldn't add anything.
      def __init__(self):
        self.a = 1
        x = 3  # Shouldn't add anything, because we're in a class.
        w.v = 4  # Also shouldn't add anything.
      def other_func(self):
        self.b = self.u  # Basically a name error, should only add b.
    """
    cls, = self.visit(src)["A"]
    self.assertClass(
        cls,
        fields=["a", "b"],
        methods=["__init__", "other_func"])

  def test_nested_function_method(self):
    src = """
    class A:
      def test(self, a, b):
        def helper(x, y):
          self.a = x + y  # Closure captures self, so this does add a.
          z = 1  # This shouldn't be added to the class namespace.
          return self.a
        return helper(a, b)
    """
    cls, = self.visit(src)["A"]
    self.assertClass(
        cls,
        fields=["a"],
        methods=["test"])

  def test_nested_function_global(self):
    src = """
    def test(a, b):
      def helper(x, y):
        z = 1
        return x + y
      return helper(a, b)
    """
    namespace = self.visit(src)
    self.assertNames(
        namespace,
        variables=[],
        functions=["test"])

  def test_basic_pyi_hint(self):
    src = """
    x = ...  # type: str
    y: int
    z: int
    def a_func(arg1, arg2): ...
    class Thing:
      a: int
      b: int
      c: Any
      d: Any
      def __init__(self, x): ...
      def set_thing(self, y): ...
    """
    namespace = self.visit(src)
    self.assertNames(
        namespace,
        variables=["x", "y", "z"],
        functions=["a_func"],
        classes=["Thing"])
    cls, = namespace["Thing"]
    self.assertClass(
        cls,
        fields=["a", "b", "c", "d"],
        methods=["__init__", "set_thing"])


if __name__ == "__main__":
  unittest.main()
