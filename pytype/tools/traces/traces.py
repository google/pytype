# Lint as: python2, python3
"""A library for accessing pytype's inferred local types."""

import sys

from pytype import analyze
from pytype import config
from pytype import errors
from pytype import load_pytd
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import visitors

from pytype.tools.traces import source
from pytype.tools.traces import visitor

_ATTR_OPS = frozenset((
    "LOAD_ATTR",
    "STORE_ATTR",
))

_CALL_OPS = frozenset((
    "CALL_FUNCTION",
    "CALL_FUNCTION_EX",
    "CALL_FUNCTION_KW",
    "CALL_FUNCTION_VAR",
    "CALL_FUNCTION_VAR_KW",
    "CALL_METHOD",
))

_LOAD_OPS = frozenset((
    "LOAD_DEREF",
    "LOAD_FAST",
    "LOAD_GLOBAL",
    "LOAD_NAME",
))

_STORE_OPS = frozenset((
    "STORE_DEREF",
    "STORE_FAST",
    "STORE_GLOBAL",
    "STORE_NAME",
))


class TypeTrace(source.AbstractTrace):
  """Traces of inferred type information."""


def trace(src, options=None):
  """Generates type traces for the given source code.

  Args:
    src: The source text.
    options: A pytype.config.Options object that can be used to specify options
      such as the target Python version.

  Returns:
    A source.Code object.
  """
  errorlog = errors.ErrorLog()
  options = options or config.Options.create()
  loader = load_pytd.create_loader(options)
  vm = analyze.CallTracer(
      errorlog=errorlog,
      options=options,
      generate_unknowns=options.protocols,
      loader=loader)
  pytd_module, _ = analyze.infer_types(
      src=src,
      filename=options.input,
      errorlog=errorlog,
      options=options,
      loader=loader,
      tracer_vm=vm)
  raw_traces = []
  for op, symbol, data in vm.opcode_traces:
    raw_traces.append(
        (op, symbol, tuple(_to_pytd(d, loader, pytd_module) for d in data)))
  return source.Code(src, raw_traces, TypeTrace, options.input)


def _to_pytd(datum, loader, ast):
  if not datum:
    return pytd.AnythingType()
  t = pytd_utils.JoinTypes(v.to_type() for v in datum).Visit(
      visitors.RemoveUnknownClasses())
  return loader.resolve_type(t, ast)


class MatchAstVisitor(visitor.BaseVisitor):
  """An AST visitor to match traces to nodes.

  Attributes:
    source: The source and trace information.
  """

  def __init__(self, src_code, *args, **kwargs):
    super(MatchAstVisitor, self).__init__(*args, **kwargs)
    self.source = src_code
    # In Python versions before 3.7, there is a mismatch between where the ast
    # and bytecode representations think some nodes are located, so we manually
    # track the last line for multiline assign statements. This is safe because
    # assign is not an expression and hence cannot be nested.
    self._assign_end_line = None
    # Needed for x[i] = <multiline statement>
    self._assign_subscr = None

  def enter_Assign(self, node):
    self._assign_end_line = self._get_last_line(node.value)
    if isinstance(node.targets[0], self._ast.Subscript):
      self._assign_subscr = node.targets[0].value

  def _get_last_line(self, node):
    """Walks a node, returning the latest line number of any of its children."""
    v = _LineNumberVisitor(self._ast)
    v.visit(node)
    return v.line

  def leave_Assign(self, _):
    self._assign_end_line = None
    self._assign_subscr = None

  def match(self, node):
    """Gets the traces for the given node, along with their locations."""
    method = "match_" + node.__class__.__name__
    try:
      match = getattr(self, method)
    except AttributeError:
      raise NotImplementedError(method)
    return match(node)

  def match_Attribute(self, node):
    return [(self._get_match_location(node, tr.symbol), tr)
            for tr in self._get_traces(node.lineno, _ATTR_OPS, node.attr)]

  def match_Call(self, node):
    # When calling a method of a class, the node name is <value>.<method>, but
    # only the method name is traced.
    name = self._get_node_name(node).rpartition(".")[-1]
    return [(self._get_match_location(node), tr)
            for tr in self._get_traces(node.lineno, _CALL_OPS, name)]

  def match_Import(self, node):
    return list(self._match_import(node, is_from=False))

  def match_ImportFrom(self, node):
    return list(self._match_import(node, is_from=True))

  def match_Name(self, node):
    if isinstance(node.ctx, self._ast.Load):
      if self._assign_subscr and sys.version_info < (3, 7):
        lineno = self._assign_end_line
      else:
        lineno = node.lineno
      ops = _LOAD_OPS
    elif isinstance(node.ctx, self._ast.Store):
      if self._assign_end_line and sys.version_info < (3, 7):
        lineno = self._assign_end_line
      else:
        lineno = node.lineno
      ops = _STORE_OPS
    else:
      return []
    return [(self._get_match_location(node), tr)
            for tr in self._get_traces(lineno, ops, node.id)]

  def _get_traces(self, lineno, ops, symbol):
    for tr in self.source.traces[lineno]:
      if tr.op in ops and tr.symbol == symbol:
        yield tr

  def _get_match_location(self, node, name=None):
    loc = source.Location(node.lineno, node.col_offset)
    if not name:
      return loc
    if isinstance(node, (self._ast.Import, self._ast.ImportFrom)):
      # Search for imported module names
      text = self.source.line(node.lineno)
      c = text.find(" " + name)
      if c == -1:
        c = text.find("," + name)
      if c != -1:
        return source.Location(node.lineno, c + 1)
    elif isinstance(node, self._ast.Attribute):
      attr_loc, _ = self.source.get_attr_location(name, loc)
      return attr_loc
    return loc

  def _get_node_name(self, node):
    if isinstance(node, self._ast.Attribute):
      return "{}.{}".format(self._get_node_name(node.value), node.attr)
    elif isinstance(node, self._ast.Call):
      return self._get_node_name(node.func)
    elif isinstance(node, self._ast.Lambda):
      return "<lambda>"
    elif isinstance(node, self._ast.Name):
      return node.id
    else:
      raise NotImplementedError(node.__class__.__name__)

  def _match_import(self, node, is_from):
    for alias in node.names:
      name = alias.asname if alias.asname else alias.name
      op = "STORE_NAME" if alias.asname or is_from else "IMPORT_NAME"
      for tr in self._get_traces(node.lineno, [op], name):
        yield self._get_match_location(node, name), tr
        break


class _LineNumberVisitor(visitor.BaseVisitor):

  def __init__(self, *args, **kwargs):
    super(_LineNumberVisitor, self).__init__(*args, **kwargs)
    self.line = 0

  def generic_visit(self, node):
    lineno = getattr(node, "lineno", 0)
    if lineno > self.line:
      self.line = lineno
