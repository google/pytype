# python3
"""Visitor that extracts definitions from an AST."""
import collections
import contextlib
from typing import Dict, List, Tuple

from pytype.tools.pyi_checker import definitions
from typed_ast import ast3

# pylint raises lots of false positives for Namespace and the visit_ methods.
# pylint: disable=invalid-name


# A Namespace is the mapping of names to definitions in a module or class.
Namespace = Dict[str, List[definitions.Definition]]


# TODO(tsudol): Consider special cases:
# - attributes set in __new__() (where we don't have "self")
# - __getattr__ (for type hints) and HAS_DYNAMIC_ATTRIBUTES (for sources)
# - __slots__
class DefinitionFinder(ast3.NodeVisitor):
  """A single-use visitor for extracting definitions from a Python AST.

  visit() must be passed an instance of ast3.mod: ast3.Module,
  ast3.Interactive or ast3.Expression.
  """

  # ast3.NodeVisitor is not very friendly towards static type checking,
  # especially the visit() method. Type annotations are sparse because they just
  # aren't useful.

  def __init__(self, source=""):
    """Initializes the DefinitionFinder.

    Args:
      source: The name of the source of the definitions, e.g. a Python file.
    """
    self._source = source
    # visit() populates _namespace with definitions found in the visited AST.
    self._namespace = collections.defaultdict(list)  # type: Namespace
    # These two flags manage behavior when in the body of a class.
    self._in_class = False
    self._in_method = False

  def _is_store(self, node):
    return isinstance(node.ctx, (ast3.Store, ast3.AugStore))

  def _visit_root(self, node: ast3.mod) -> Namespace:
    """For roots of the ast, visit every child and return the namespace."""
    self.generic_visit(node)
    return self._namespace

  # Module, Interactive and Expression are the three root nodes of the AST.
  visit_Module = _visit_root
  visit_Interactive = _visit_root
  visit_Expression = _visit_root

  def visit_Name(self, node: ast3.Name):
    # Name is the root of all expressions. node.ctx indicates where the
    # expression is used. If the Name is used as a Store, that means it appears
    # on the left-hand side of an assignment expression: a = b will generate
    # Name("a", Store), and the visitor should add an entry for a.
    # However, we ignore bare names (i.e. not self.something) when in a method.
    if self._is_store(node) and not self._in_method:
      self._namespace[node.id].append(
          definitions.Variable.from_node(node, self._source))

  def visit_Attribute(self, node: ast3.Attribute):
    # If this Attribute isn't being used on the left-hand side of an assignment
    # statement, the visitor doesn't need to save it.
    if not self._is_store(node):
      return

    if self._in_class:
      # If in a class, only save "self.attr" expressions.
      if isinstance(node.value, ast3.Name) and node.value.id == "self":
        self._namespace[node.attr].append(definitions.Variable(
            name=node.attr,
            source=self._source,
            lineno=node.lineno,
            col_offset=node.col_offset))
    else:
      # Outside of a class, an expression like "a.b.c" is stored as
      # Variable(name = "a"). When parsed, "a.b.c" becomes
      # Attribute(Attribute(Name("a"), "b"), "c"). Since only "a" needs to be
      # saved, proceed with the visit as normal so visit_Name handles "a".
      # However, "a" and "b" are considered Loads, not Stores, so we need to
      # update the node.
      node.value.ctx = ast3.Store()
      self.generic_visit(node)

  def visit_Subscript(self, node: ast3.Subscript):
    # A Subscript expression may be on the left-hand side of an assignment, but
    # the value field (which should have a hint) is in a Load context.
    if self._is_store(node):
      node.value.ctx = ast3.Store()
      self.generic_visit(node)

  def visit_alias(self, node: ast3.alias):
    # Aliases are the "name as other_name" in "import name as other_name".
    return definitions.Variable(
        name=node.asname if node.asname else node.name,
        source=self._source,
        # These must be filled in later.
        lineno=-1,
        col_offset=-1)

  def visit_Import(self, node: ast3.Import):
    for alias in node.names:
      module = self.visit(alias)
      module.lineno = node.lineno
      module.col_offset = node.col_offset
      self._namespace[module.name].append(module)

  def visit_ImportFrom(self, node: ast3.ImportFrom):
    # For "from m import alias", creates a Variable for only the aliases.
    for alias in node.names:
      module = self.visit(alias)
      module.lineno = node.lineno
      module.col_offset = node.col_offset
      self._namespace[module.name].append(module)

  @contextlib.contextmanager
  def _enter_func(self):
    # Helper context manager for handling _in_method.
    old_in_method = self._in_method
    self._in_method = True
    try:
      yield
    finally:
      self._in_method = old_in_method

  def visit_FunctionDef(self, node: ast3.FunctionDef):
    # Fields can be added in any method of a class, so the visitor needs to
    # check every method body. Attribute processing changes when in a method,
    # so the in_method flag has to be set.
    if self._in_class:
      with self._enter_func():
        self.generic_visit(node)
    # Helper functions will only be discovered when inside a class, and they
    # don't need type hints.
    if not self._in_method:
      self._namespace[node.name].append(
          definitions.Function.from_node(node, self._source))

  @contextlib.contextmanager
  def _enter_class(self):
    """Context manager used when processing class bodies."""
    old_in_class = self._in_class
    old_namespace = self._namespace
    self._in_class = True
    self._namespace = collections.defaultdict(list)
    try:
      yield
    finally:
      self._in_class = old_in_class
      self._namespace = old_namespace

  def visit_ClassDef(self, node: ast3.ClassDef):
    with self._enter_class():
      self.generic_visit(node)
      fields, methods, nested_classes = split_namespace(self._namespace)
    self._namespace[node.name].append(
        definitions.Class.from_node(
            node, fields, methods, nested_classes, self._source))


def split_namespace(namespace: Namespace) -> Tuple[
    Dict[str, List[definitions.Variable]],
    Dict[str, List[definitions.Function]],
    Dict[str, List[definitions.Class]]]:
  """Splits a namespace into Variables, Functions and Classes.

  Arguments:
    namespace: The namespace to split. Will not be changed by this function.

  Raises:
    TypeError if a name has a definition of an unexpected type.

  Returns:
    A list of Variable definitions, a list of Function definitions, and a list
    of Class definitions.
  """
  fields = collections.defaultdict(list)
  funcs = collections.defaultdict(list)
  classes = collections.defaultdict(list)
  for name in namespace:
    for defn in namespace[name]:
      if isinstance(defn, definitions.Variable):
        fields[name].append(defn)
      elif isinstance(defn, definitions.Function):
        funcs[name].append(defn)
      elif isinstance(defn, definitions.Class):
        classes[name].append(defn)
      else:
        raise TypeError("Unexpected definition %s" % defn)
  return fields, funcs, classes
