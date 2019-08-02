# Lint as: python2, python3
"""A library for accessing pytype's inferred local types."""

from pytype import analyze
from pytype import config
from pytype import errors
from pytype import load_pytd
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import visitors

from pytype.tools.traces import source
from pytype.tools.traces import visitor


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
    # Track the last line for multiline assign statements. This is safe because
    # assign is not an expression and hence cannot be nested.
    # TODO(mdemello): Handle multiline class definitions similarly.
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


class _LineNumberVisitor(visitor.BaseVisitor):

  def __init__(self, *args, **kwargs):
    super(_LineNumberVisitor, self).__init__(*args, **kwargs)
    self.line = 0

  def generic_visit(self, node):
    lineno = getattr(node, "lineno", 0)
    if lineno > self.line:
      self.line = lineno
