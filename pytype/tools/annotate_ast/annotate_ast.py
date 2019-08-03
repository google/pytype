"""Library to take a Python AST and add Pytype type information to it."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections

from pytype import analyze
from pytype import errors
from pytype import io
from pytype import load_pytd
from pytype.pyc import opcodes
from pytype.pytd import pytd_utils

_NAME_LOAD_OPS = {
    opcodes.LOAD_GLOBAL, opcodes.LOAD_FAST, opcodes.LOAD_NAME,
    opcodes.LOAD_DEREF
}

_NAME_STORE_OPS = {
    opcodes.STORE_GLOBAL, opcodes.STORE_FAST, opcodes.STORE_NAME,
    opcodes.STORE_DEREF
}


def annotate_source(source, ast_factory, pytype_options, filename="src.py"):
  """Infer types for `source`, and return an AST of it with types added.

  Args:
    source: Text, the source code to type-infer and parse to an AST.
    ast_factory: Callable[[Options], ast-module-like], a callable that takes the
      Pytype options and returns an ast-module like object used to parse the
      source to an AST and traverse the created ast.Module object.
    pytype_options: pytype.config.Options, the options to pass onto Pytype.
    filename: Text, the logical file path the source came from, if any. This
      file won't be read.

  Returns:
    The created Module object from what `ast_factory` returned.
  """
  traces = infer_types(source, filename, pytype_options)

  ast_module = ast_factory(pytype_options)
  module = ast_module.parse(source, filename)

  visitor = AnnotateAstVisitor(ast_module, traces)
  visitor.visit(module)
  return module


def infer_types(source, filename, options):
  """Infer types for the provided source.

  Args:
    source: Text, the source code to analyze.
    filename: Text, the filename the source came from. The file won't be read.
    options: pytype.config.Options, the options to pass onto Pytype.

  Returns:
    Traces object with information gathered by Pytype.
  """
  errorlog = errors.ErrorLog()
  loader = load_pytd.create_loader(options)

  vm = analyze.CallTracer(
      errorlog=errorlog,
      options=options,
      generate_unknowns=options.protocols,
      loader=loader)

  with io.wrap_pytype_exceptions(PytypeError, filename=filename):
    analyze.infer_types(
        src=source,
        filename=filename,
        errorlog=errorlog,
        options=options,
        loader=loader,
        show_library_calls=True,
        tracer_vm=vm)

  return Traces(vm)


class Traces(object):
  """Collection of Pytype's type inference info."""

  def __init__(self, vm):
    """Creates an instance.

    Args:
      vm: analyze.CallTracer, VM with all the information gathered by Pytype.
    """
    # The vm object has to be kept alive, otherwise the objects in opcode_traces
    # cause a segfault.
    self._vm = vm
    self._ops_by_line = collections.defaultdict(list)

    for op, symbol, type_defs in vm.opcode_traces:
      trace_entry = Trace(op, symbol, type_defs)
      self._ops_by_line[trace_entry.op.line].append(trace_entry)

  def find_unassociated_traces(self, line_num, op_types, symbol):
    """Finds `Trace` objects that haven't been associated to an AST node.

    Args:
      line_num: int, the line number that the traces must be for.
      op_types: Iterable[Type[pyc.opcodes.Opcode]], the types that any opcodes
        matching `line_num` must also be an instance of.
      symbol: Text, the trace symbol name that must also match.

    Returns:
      Sequence[Trace] of matching Traces.
    """
    op_types = tuple(op_types)
    entries = self._ops_by_line[line_num]
    ops = []
    for entry in entries:
      if entry.associated:
        continue
      if not isinstance(entry.op, op_types):
        continue
      if entry.symbol != symbol:
        continue
      ops.append(entry)
    return ops


class Trace(object):
  """Pytype trace information.

  Attributes:
    associated: bool, True if this trace has been associated with an AST node,
      False if not.
  """

  def __init__(self, op, symbol, type_defs):
    self._op = op
    self._symbol = symbol
    self._type_def = _join_type_defs(type_defs[-1] or [])
    self._type_def_annotation = _annotation_str_from_type_def(self.type_def)
    self.associated = False

  @property
  def op(self):
    """Returns opcode.Opcode of the trace opcode."""
    return self._op

  @property
  def symbol(self):
    """Returns Optional[Text] of the symbol name."""
    return self._symbol

  @property
  def type_def(self):
    """Returns Optional[abstract.AtomicAbstractValue] of the Pytype type info."""
    return self._type_def

  @property
  def type_def_annotation(self):
    """Returns Text version of `.type_def`."""
    return self._type_def_annotation


class AnnotateAstVisitor(object):
  """Traverses an AST and sets type information on its nodes.

  This is modeled after ast.NodeVisitor, but doesn't inherit from it because
  it is ast-module agnostic so that different AST implementations can be used.
  """

  def __init__(self, ast, traces):
    """Creates an instance.

    Args:
      ast: An ast-module-like used to traverse AST node.
      traces: Traces object of Pytype trace information.
    """
    self._ast = ast
    self._traces = traces

  def visit(self, node):
    visitor = getattr(self, "visit_" + node.__class__.__name__,
                      self.generic_visit)
    return visitor(node)

  def generic_visit(self, node):
    for child in self._ast.iter_child_nodes(node):
      self.visit(child)

  def visit_Assign(self, node):  # pylint: disable=invalid-name
    """Visits an `Assign` node."""
    # This changes the visit order of Assign nodes from [targets, value]
    # to [value, targets] to better match the opcode order.
    self.visit(node.value)
    for child in node.targets:
      self.visit(child)

  def visit_Name(self, node):  # pylint: disable=invalid-name
    """Visits a `Name` node."""
    if isinstance(node.ctx, self._ast.Del):
      return

    ctx = node.ctx
    if isinstance(ctx, self._ast.Load):
      op_types = _NAME_LOAD_OPS
    elif isinstance(ctx, self._ast.Store):
      op_types = _NAME_STORE_OPS
    else:
      raise ValueError("Unsupported Name.ctx: {}".format(node.ctx))

    ops = self._traces.find_unassociated_traces(node.lineno, op_types, node.id)
    # For lack of a better option, take the first one.
    entry = next(iter(ops), None)
    self._maybe_set_type(node, entry)

  def _maybe_set_type(self, node, trace):
    """Sets type information on the node, if there is any to set."""
    if not trace:
      return
    if trace:
      node.resolved_type = trace.type_def
      node.resolved_annotation = trace.type_def_annotation
      trace.associated = True


class PytypeError(Exception):
  """Wrap exceptions raised by Pytype."""


def _join_type_defs(type_defs):
  return pytd_utils.JoinTypes(v.to_type() for v in type_defs)


def _annotation_str_from_type_def(type_def):
  return pytd_utils.Print(type_def)
