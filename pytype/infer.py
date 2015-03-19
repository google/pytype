"""Code for generating and storing inferred types."""

import collections
import logging
import StringIO
import subprocess


from pytype import abstract
from pytype import convert_structural
from pytype import utils
from pytype import vm
from pytype.pyc import pyc
from pytype.pytd import explain as typegraph_explain
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd.parse import visitors

log = logging.getLogger(__name__)


CallRecord = collections.namedtuple("CallRecord",
                                    ["function", "positional_arguments",
                                     "keyword_arguments", "return_value",
                                     "location"])


class CallTracer(vm.VirtualMachine):
  """Virtual machine that records all function calls."""

  # TODO(pludemann): def isinstance(self, obj, classes) - see
  #                  TypegraphVirtualMachine.isinstance

  def __init__(self, *args, **kwargs):
    super(CallTracer, self).__init__(*args, **kwargs)
    self._call_trace = set()
    self._functions = set()
    self._classes = set()
    self._unknowns = []

  def create_argument(self, method_name, i):
    name = "arg %d of %s" % (i, method_name)
    return abstract.Unknown(self).to_variable(name)

  def analyze_method(self, name, methodvar, main_node):
    assert self.current_location == main_node
    for method in methodvar.data:
      if isinstance(method, (abstract.Function, abstract.BoundFunction)):
        args = [self.create_argument(name, i)
                for i in range(method.argcount())]
        self.call_function(methodvar, args)
        self.connect_source_nodes(main_node)

  def bind_method(self, name, methodvar, instance, clsvar, loc):
    bound = self.program.NewVariable(name)
    for m in methodvar.data:
      bound.AddValue(m.property_get(instance, clsvar), [], loc)
    return bound

  def analyze_class(self, clsvar, main_node):
    instance = self.instantiate(clsvar)
    self.connect_source_nodes(main_node)
    for cls_val in clsvar.values:
      cls = cls_val.data
      init = cls.get_attribute("__init__", instance.values[0], cls_val)
      if init:
        bound_init = self.bind_method("__init__", init, instance, clsvar,
                                      main_node)
        self.analyze_method("__init__", bound_init, main_node)
      for name, methodvar in sorted(cls.members.items()):
        b = self.bind_method(name, methodvar, instance, clsvar, main_node)
        self.analyze_method(name, b, main_node)

  def analyze_classes(self, main_node):
    self.default_location = self.current_location = main_node
    for unused_name, clsvar in sorted(self._classes):
      self.analyze_class(clsvar, main_node)

  def analyze_functions(self, main_node):
    self.default_location = self.current_location = main_node
    for name, f in sorted(self._functions):
      if all(function.cls for function in f.data):
        # We analyze class methods in analyze_class above.
        log.info("Analyze functions: Skipping class method %s", name)
      elif all(function.is_closure() for function in f.data):
        # We analyze closures as part of the function they're defined in.
        log.info("Analyze functions: Skipping closure %s", name)
      else:
        log.info("Analyzing function %s", name)
        self.analyze_method(name, f, main_node)

  def trace_call(self, funcu, posargs, namedargs, result_variable):
    """Add an entry into the call trace.

    Args:
      funcu: A Variable of the possible functions that where called.
      posargs: The positional arguments.
      namedargs: The keyword arguments.
      result_variable: A Variable of the possible result values.
    """
    if all(function.is_closure() for function in funcu.data):
      log.info("Not recording call to closure %s", funcu.name)
      return
    else:
      log.debug("Logging call to %r with %d args, return %r",
                funcu, len(posargs), result_variable)
    assert None not in posargs
    self._call_trace.add(CallRecord(funcu, tuple(posargs),
                                    tuple((namedargs or {}).items()),
                                    result_variable,
                                    self.current_location))

  def trace_functiondef(self, name, f):
    self._functions.add((name, f))

  def trace_classdef(self, name, clsvar):
    self._classes.add((name, clsvar))

  def trace_unknown(self, unknown):
    self._unknowns.extend(unknown.data)

  # pylint: disable=unused-argument
  def compute_types(self, expensive=False, explain=False):
    """Compute the types of all functions and classes self has evaluated.

    Things that could not be assigned a type are omitted.

    The approach is to enumerate over all the functions calls that were made and
    filter their possible types based on the data flow that is possible in the
    typegraph. Once all the actually possible types for a given function are
    generated they are passed to the to PyTD optimizer to simplify them.

    Args:
      expensive: Do full path-sensitive analysis.
      explain: For every omitted type, explain why it was impossible.
    Returns:
      A TypeDeclUnit that has all the classes and functions.
    """
    global_functions = {}  # map names to pytd.FunctionWithSignatures

    # maps names to a dict mapping names to pytd.FunctionWithSignatures
    classes_dict = {clsvar.name: {} for _, clsvar in self._classes}

    for funcvariable, args, kws, rets, loc in self._call_trace:
      log.debug("_call_trace: %s(%s, %s)->%s", funcvariable, args, kws, rets)
      for funcval in funcvariable.values:
        func = funcval.data
        if isinstance(func, abstract.PyTDFunction):
          func = func.signatures[0]
          prefix = "~"
        else:
          prefix = ""
        if not hasattr(func, "get_parameter_names"):
          log.debug("Ignoring %s", func.__class__)
          continue

        for args_selected in utils.variable_product(
            func.get_bound_arguments() + list(args)):
          # Process in deterministic order:
          for kws_selected in sorted(utils.variable_product_dict(dict(kws))):
            for ret_selected in rets.values:
              # This runs for every proposed type for the given function call
              vals = ([funcval, ret_selected] + list(args_selected) +
                      list(kws_selected.values()))
              if expensive:
                is_possible = loc.HasCombination(vals)
                if explain and not is_possible:
                  typegraph_explain.Explain(vals, loc)
              else:
                is_possible = True
              if is_possible or log.isEnabledFor(logging.INFO):
                names = func.get_parameter_names()
                arg_types = (a.data.to_type() for a in args_selected)
                sig = pytd.Signature(
                    tuple(pytd.Parameter(n, t)
                          for n, t in zip(names, arg_types)) +
                    tuple(pytd.Parameter(name, a.data.to_type())
                          for name, a in kws_selected.items()),
                    ret_selected.data.to_type(),
                    has_optional=False,
                    exceptions=(), template=())
                log.debug("is_possible: %s %r: %r at %s",
                          "+" if is_possible else "-", func.get_static_path(),
                          pytd.Print(sig), loc.name)
                path = func.get_static_path()
                if is_possible and path:
                  cls = path.get_innermost_class()
                  f = path.get_function()
                  if cls:
                    methods = classes_dict.setdefault(prefix + cls.name, {})
                    function = methods.setdefault(
                        f.name, pytd.FunctionWithSignatures(f.name, []))
                  else:
                    function = global_functions.setdefault(
                        prefix + f.name, pytd.FunctionWithSignatures(
                            prefix + f.name, []))
                  function.signatures.append(sig)

    classes = tuple(
        pytd.Class(cls_name,
                   (pytd.NamedType("object"),) if cls_name != "object" else (),
                   tuple(pytd.FunctionWithSignatures(method.name,
                                                     tuple(method.signatures,))
                         for method in methods.values()), (), ())
        for cls_name, methods in classes_dict.items())

    unknowns = tuple(u.to_pytd_class() for u in self._unknowns)
    tmp = pytd.TypeDeclUnit(name="unknowns", classes=unknowns, constants=(),
                            functions=(), modules=())
    classes += tmp.Visit(optimize.PullInMethodClasses()).classes

    functions = tuple(pytd.FunctionWithSignatures(f.name, tuple(f.signatures))
                      for f in global_functions.values())

    mod = pytd.TypeDeclUnit("inferred", (), classes, functions, ())
    mod.Visit(visitors.VerifyVisitor())
    mod = mod.Visit(optimize.RemoveDuplicates())
    mod = mod.Visit(visitors.CanonicalOrderingVisitor(sort_signatures=True))
    return mod


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
  """Generate a pseudocode (CFG nodes + assignments) version of a program."""
  s = StringIO.StringIO()
  for node in utils.order_nodes(program.cfg_nodes):
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


def infer_types(src, python_version, filename=None,
                svg_output=None, deep=False, expensive=True,
                remove_builtin_names=True,
                pseudocode_output=False, explain=False, solve_unknowns=False,
                reverse_operators=False):
  """Given Python source return its types.

  Args:
    src: A string containing Python source code.
    python_version: The python version to emulate (major, minor).
    filename: Filename of the program we're parsing.
    svg_output: A filename into which to save an SVG version of the type graph.
    deep: If True, analyze all functions, even the ones not called by the main
      execution flow.
    expensive: If True, do a full path-sensitive analysis.
    remove_builtin_names: if True, remove builtin names from the result.
    pseudocode_output: Filename to write pseudo code to.
    explain: For every omitted type, explain why it was impossible.
    solve_unknowns: If yes, try to replace structural types ("~unknowns") with
      nominal types.
    reverse_operators: If True, emulate operations like __radd__.
  Returns:
    A TypeDeclUnit
  """
  tracer = CallTracer(python_version, reverse_operators)
  program = pyc.compile_and_load(src,
                                 python_version=python_version,
                                 filename=filename)
  loc, builtin_names = tracer.run_program(program)
  log.info("===Done run_program===")
  # TODO(pludemann): make test_inference.InferDedent and this code the same:
  if deep:
    tracer.analyze_classes(loc)
    tracer.analyze_functions(loc)
  ast = tracer.compute_types(expensive=expensive, explain=explain)
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
  if remove_builtin_names:
    ast = ast.Visit(visitors.RemoveFunctionsAndClasses(builtin_names))

  return ast
