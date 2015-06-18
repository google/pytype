"""Code for generating and storing inferred types."""

import collections
import logging
import StringIO
import subprocess


from pytype import abstract
from pytype import convert_structural
from pytype import output
from pytype import state as frame_state
from pytype import utils
from pytype import vm
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import visitors

log = logging.getLogger(__name__)


CallRecord = collections.namedtuple("CallRecord",
                                    ["function", "positional_arguments",
                                     "keyword_arguments", "return_value"])


class AnalysisFrame(object):
  """Frame representing the "analysis function" that calls everything."""

  def __init__(self):
    self.f_code = None  # for recursion detection
    self.f_builtins = None


class CallTracer(vm.VirtualMachine):
  """Virtual machine that records all function calls.

  Attributes:
    exitpoint: A CFG node representing the program exit. Needs to be set before
      analyze_types.
  """

  # TODO(pludemann): def isinstance(self, obj, classes) - see
  #                  TypegraphVirtualMachine.isinstance

  def __init__(self, *args, **kwargs):
    super(CallTracer, self).__init__(*args, **kwargs)
    self._unknowns = {}
    self._calls = set()
    self.exitpoint = None

  def create_argument(self, node, method_name, i):
    name = "arg %d of %s" % (i, method_name)
    return abstract.Unknown(self).to_variable(node, name)

  def analyze_method(self, val, node):
    method = val.data
    if isinstance(method, (abstract.Function, abstract.BoundFunction)):
      args = [self.create_argument(node, val.data.name, i)
              for i in range(method.argcount())]
      frame = AnalysisFrame()
      self.push_frame(frame)
      state = frame_state.FrameState.init(node)
      state, _ = self.call_function_with_state(state, val.variable, args)
      state = state.connect_to_cfg_node(node)
      self.pop_frame(frame)
      node = state.node
    return node

  def analyze_method_var(self, name, var, node):
    log.info("Analyzing %s", name)
    for val in var.values:
      node2 = self.analyze_method(val, node)
      node2.ConnectTo(node)
    return node

  def bind_method(self, name, methodvar, instance, clsvar, node):
    bound = self.program.NewVariable(name)
    for m in methodvar.data:
      bound.AddValue(m.property_get(instance, clsvar), [], node)
    return bound

  def analyze_class(self, val, node):
    instance = self.instantiate(node, val.variable)
    cls = val.data
    node, init = cls.get_attribute(node, "__init__", instance.values[0], val)
    if init:
      bound_init = self.bind_method("__init__", init, instance, val.variable,
                                    node)
      node = self.analyze_method_var("__init__", bound_init, node)
    for name, methodvar in sorted(cls.members.items()):
      b = self.bind_method(name, methodvar, instance, val.variable, node)
      node2 = self.analyze_method_var(name, b, node)
      node2.ConnectTo(node)
    return node

  def analyze_function(self, val, node):
    if val.data.cls:
      # We analyze class methods in analyze_class above.
      log.info("Analyze functions: Skipping class method %s", val.data.name)
    elif val.data.is_closure():
      # We analyze closures as part of the function they're defined in.
      log.info("Analyze functions: Skipping closure %s", val.data.name)
    else:
      node2 = self.analyze_method(val, node)
      node2.ConnectTo(node)
    return node

  def analyze_toplevel(self, node, defs, ignore):
    for name, var in sorted(defs.items()):  # sort, for determinicity
      if name not in ignore:
        for value in var.values:
          if isinstance(value.data, abstract.Class):
            node2 = self.analyze_class(value, node)
            node2.ConnectTo(node)
          elif isinstance(value.data, abstract.Function):
            node2 = self.analyze_function(value, node)
            node2.ConnectTo(node)

  def analyze(self, node, defs, ignore):
    assert not self.frame
    self.analyze_toplevel(node, defs, ignore)
    return node

  def trace_unknown(self, name, unknown):
    self._unknowns[name] = unknown

  def trace_call(self, func, posargs, namedargs, result):
    """Add an entry into the call trace.

    Args:
      func: A typegraph Value of functions that was called.
      posargs: The positional arguments.
      namedargs: The keyword arguments.
      result: A Variable of the possible result values.
    """
    log.debug("Logging call to %r with %d args, return %r",
              func, len(posargs), result)
    if isinstance(func.data, abstract.BoundPyTDFunction):
      log.info("Not recording call to bound method.")
      return
    self._calls.add(CallRecord(func, tuple(posargs),
                               tuple((namedargs or {}).items()), result))

  def pytd_for_unknowns(self, defs, ignore):
    classes = []
    for name, var in self._unknowns.items():
      for value in var.FilteredData(self.exitpoint):
        classes.append(value.to_pytd_def(name))
    return pytd.TypeDeclUnit("unknowns", (), tuple(classes), ())

  def pytd_for_types(self, defs, ignore):
    for name, var in defs.items():
      abstract.variable_set_official_name(var, name)
    constants = []
    functions = []
    classes = []
    for name, var in defs.items():
      new_classes = []
      new_functions = []
      new_constants = []
      if name in output.TOP_LEVEL_IGNORE or name in ignore:
        continue
      for value in var.FilteredData(self.exitpoint):
        if isinstance(value, abstract.Class):
          new_classes.append(value.to_pytd_def(name))
        elif isinstance(value, abstract.Function):
          new_functions.append(value.to_pytd_def(name))
        else:
          new_constants.append(value.to_type())
      if len(new_classes) >= 2:
        log.warning("Ambiguious top level class %r", name)
        new_constants.append(pytd.NamedType("type"))
      else:
        classes.extend(new_classes)
      if len(new_functions) >= 2:
        log.warning("Ambiguious top level function %r", name)
        new_constants.append(pytd.NamedType("function"))
      else:
        functions.extend(new_functions)
      if new_constants:
        constants.append(
            pytd.Constant(name, pytd_utils.JoinTypes(new_constants)))
    return pytd.TypeDeclUnit(
        "inferred", tuple(constants), tuple(classes), tuple(functions))

  def pytd_for_call_traces(self):
    functions = []
    for funcval, args, kws, rets in self._calls:
      func = funcval.data.signatures[0]
      if isinstance(func, abstract.BoundPyTDFunction):
        # Don't do class methods, only top-level functions
        continue
      signatures = []
      for args_selected in utils.variable_product(
          func.get_bound_arguments() + list(args)):
        for kws_selected in sorted(utils.variable_product_dict(dict(kws))):
          ret = pytd_utils.JoinTypes(r.to_type() for r in rets.data)
          names = func.get_parameter_names()
          arg_types = (a.data.to_type() for a in args_selected)
          signatures.append(pytd.Signature(
              tuple(pytd.Parameter(n, t)
                    for n, t in zip(names, arg_types)) +
              tuple(pytd.Parameter(name, a.data.to_type())
                    for name, a in kws_selected.items()),
              ret, has_optional=False, exceptions=(), template=()))
      functions.append(pytd.Function("~" + func.name, tuple(signatures)))
    return pytd.TypeDeclUnit(
        "call_traces", (), (), tuple(functions))

  def compute_types(self, defs, ignore):
    ty = pytd_utils.Concat(
        self.pytd_for_types(defs, ignore),
        self.pytd_for_unknowns(defs, ignore),
        self.pytd_for_call_traces())
    ty = ty.Visit(optimize.PullInMethodClasses())
    ty = ty.Visit(visitors.DefaceUnresolved([ty, self.builtins_pytd]))
    return ty


def pretty_assignment(v, short=False):
  """Prettyprint a variable assignment.

  Args:
    v: A typegraph.Value
    short: If True, save horizontal space.

  Returns:
    A string.
  """
  if short:
    return "[%d=v%d]" % (v.variable.id, v.data.id)
  else:
    return "[%d=v%d] %s = %r" % (
        v.variable.id, v.data.id, v.variable.name, utils.maybe_truncate(v.data))


def program_to_pseudocode(program):
  """Generate a pseudocode (CFG nodes + assignments) version of a program.

  For debugging only.

  Args:
    program: An instance of cfg.Program

  Returns:
    A string, the "pseudocode" of this program.
  """
  s = StringIO.StringIO()
  seen = set()
  for node in utils.order_nodes(program.cfg_nodes):
    seen.add(node)
    s.write("<%d>%s\n" % (node.id, node.name))
    for value in node.values:
      s.write("  %s\n" % pretty_assignment(value))
      overwritten = False
      for cfg_node, source_sets in value.origins:
        if node != cfg_node:
          overwritten = True
          continue
        if source_sets == [set()]:
          pass  # don't print trivially true source_sets
        else:
          src = utils.pretty_dnf([[pretty_assignment(v, short=True)
                                   for v in source_set]
                                  for source_set in source_sets])
          s.write("    from: %s\n" % src)
      if overwritten:
        s.write("    (also set to this value in other nodes)\n")
    for out in node.outgoing:
      s.write("  jump to <%d>%s\n" % (out.id, out.name))

  # "stray" nodes are nodes that are unreachable in the CFG.
  stray_nodes = set(program.cfg_nodes) - seen
  if stray_nodes:
    s.write("Stray nodes:\n")
    for node in stray_nodes:
      s.write("<%d>%s\n" % (node.id, node.name))

  return s.getvalue()


def program_to_dot(program, ignored):
  """Convert a typegraph.Program into a dot file.

  Args:
    program: The program to convert.
    ignored: A set of names that should be ignored. This affects most kinds of
    nodes.
  Returns:
    A str of the dot code.
  """
  # This function uses the opposite quote style to allow " in strings.
  # pylint: disable=g-inconsistent-quotes
  def objname(n):
    return n.__class__.__name__ + str(id(n))

  def escape(s):
    return repr(s)[1:-1].replace('"', '\\"')

  print("cfg nodes=%d, vals=%d, variables=%d" % (
      len(program.cfg_nodes),
      sum(len(v.values) for v in program.variables),
      len(program.variables)))

  sb = StringIO.StringIO()
  sb.write("digraph {\n")
  for node in program.cfg_nodes:
    if node in ignored:
      continue
    sb.write('%s[shape=polygon,sides=4,label="%s"];\n'
             % (objname(node), node.name))
    for other in node.outgoing:
      sb.write("%s -> %s [penwidth=2.0];\n" % (objname(node), objname(other)))
  for variable in program.variables:
    if variable.name in ignored:
      continue
    sb.write('%s[label="%s",shape=polygon,sides=4,distortion=.1];\n'
             % (objname(variable), escape(variable.name)))
    for val in variable.values:
      sb.write("%s -> %s [arrowhead=none];\n" %
               (objname(variable), objname(val)))
      sb.write('%s[label="%s@0x%x",fillcolor=%s];\n' %
               (objname(val), repr(val.data)[:10], id(val.data),
                "white" if val.origins else "red"))
      for loc, srcsets in val.origins:
        for srcs in srcsets:
          sb.write('%s[label=""];\n' % (objname(srcs)))
          sb.write("%s -> %s [color=pink,arrowhead=none,weight=40];\n"
                   % (objname(val), objname(srcs)))
          if loc not in ignored:
            sb.write("%s -> %s [style=dotted,arrowhead=none,weight=5]\n"
                     % (objname(loc), objname(srcs)))
          for src in srcs:
            sb.write("%s -> %s [color=lightblue,weight=2];\n"
                     % (objname(src), objname(srcs)))
  sb.write("}\n")
  return sb.getvalue()


def infer_types(src, python_version, filename=None, pythonpath=None,
                svg_output=None, deep=False,
                pseudocode_output=False, solve_unknowns=False,
                reverse_operators=False):
  """Given Python source return its types.

  Args:
    src: A string containing Python source code.
    python_version: The python version to emulate (major, minor).
    filename: Filename of the program we're parsing.
    pythonpath: List of directories to search for .pytd-gen files.
    svg_output: A filename into which to save an SVG version of the type graph.
    deep: If True, analyze all functions, even the ones not called by the main
      execution flow.
    pseudocode_output: Filename to write pseudo code to.
    solve_unknowns: If yes, try to replace structural types ("~unknowns") with
      nominal types.
    reverse_operators: If True, emulate operations like __radd__.
  Returns:
    A TypeDeclUnit
  """
  tracer = CallTracer(python_version, reverse_operators,
                      pythonpath=pythonpath)
  loc, defs, builtin_names = tracer.run_program(src, filename)
  log.info("===Done run_program===")
  # TODO(pludemann): make test_inference.InferDedent and this code the same:
  if deep:
    tracer.exitpoint = tracer.analyze(loc, defs, builtin_names)
  else:
    tracer.exitpoint = loc
  ast = tracer.compute_types(defs, builtin_names)
  if solve_unknowns:
    log.info("=========== PyTD to solve =============\n%s", pytd.Print(ast))
    ast = convert_structural.convert_pytd(ast, tracer.builtins_pytd)
  if svg_output:
    dot = program_to_dot(tracer.program, set([]))
    proc = subprocess.Popen(["/usr/bin/dot", "-T", "svg", "-o", svg_output],
                            stdin=subprocess.PIPE)
    proc.stdin.write(dot)
    proc.stdin.close()
  if pseudocode_output:
    src = program_to_pseudocode(tracer.program)
    with open(pseudocode_output, "w") as fi:
      fi.write(src)

  return ast
