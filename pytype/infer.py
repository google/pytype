"""Code for generating and storing inferred types."""

import collections
import logging
import os
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
    self.current_opcode = None  # for memoizations of unknowns


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
    self._method_calls = set()
    self.exitpoint = None

  def create_argument(self, node, method_name, i):
    name = "arg %d of %s" % (i, method_name)
    return abstract.Unknown(self).to_variable(node, name)

  def create_varargs(self, node):
    value = abstract.Instance(self.tuple_type, self)
    value.overwrite_type_parameter(
        node, "T", self.create_new_unknown(node, "varargs_value"))
    return value

  def create_kwargs(self, node):
    key_type = self.primitive_class_instances[str].to_variable(node, "str")
    value_type = self.create_new_unknown(node, "kwargs_value")
    kwargs = abstract.Dict("kwargs", self)
    kwargs.overwrite_type_parameter(
        node, abstract.Dict.KEY_TYPE_PARAM, key_type)
    kwargs.overwrite_type_parameter(
        node, abstract.Dict.VALUE_TYPE_PARAM, value_type)
    return kwargs

  def analyze_method(self, val, node):
    method = val.data
    if isinstance(method, (abstract.InterpreterFunction,
                           abstract.BoundInterpreterFunction)):
      args = [self.create_argument(node, val.data.name, i)
              for i in range(method.argcount())]
      varargs = self.create_varargs(node) if method.has_varargs() else None
      kwargs = self.create_kwargs(node) if method.has_kwargs() else None
      frame = AnalysisFrame()
      self.push_frame(frame)
      state = frame_state.FrameState.init(node)
      state, _ = self.call_function_with_state(state, val.variable, args,
                                               kwargs, varargs)
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

  def instantiate(self, cls, node):
    """Build an (dummy) instance from a class, for analyzing it."""
    return abstract.Instance(
        cls.AssignToNewVariable(cls.data.name, node), self
    ).to_variable(node, name=cls.data.name)

  def analyze_class(self, val, node):
    instance = self.instantiate(val, node)
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
    if val.data.parent_class:
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
          if isinstance(value.data, abstract.InterpreterClass):
            node2 = self.analyze_class(value, node)
            node2.ConnectTo(node)
          elif isinstance(value.data, (abstract.InterpreterFunction,
                                       abstract.BoundInterpreterFunction)):
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
      posargs: The positional arguments, an iterable over cfg.Value.
      namedargs: The keyword arguments, a dict mapping str to cfg.Value.
      result: A Variable of the possible result values.
    """
    log.debug("Logging call to %r with %d args, return %r",
              func, len(posargs), result)
    args = tuple(posargs)
    kwargs = tuple((namedargs or {}).items())
    if isinstance(func.data, abstract.BoundFunction):
      # We only need to record calls to pytd classes, since these are the
      # only calls the solver is going to care about later.
      if isinstance(func.data, abstract.BoundPyTDFunction):
        self._method_calls.add(CallRecord(func, args, kwargs, result))
    else:
      self._calls.add(CallRecord(func, args, kwargs, result))

  def pytd_classes_for_unknowns(self):
    classes = []
    for name, var in self._unknowns.items():
      for value in var.FilteredData(self.exitpoint):
        classes.append(value.to_structural_def(name))
    return classes

  def pytd_for_types(self, defs, ignore):
    for name, var in defs.items():
      abstract.variable_set_official_name(var, name)
    data = []
    for name, var in defs.items():
      if name in output.TOP_LEVEL_IGNORE or name in ignore:
        continue
      options = var.FilteredData(self.exitpoint)
      if (len(options) > 1 and not
          all(isinstance(o, (abstract.InterpreterFunction,
                             abstract.BoundInterpreterFunction))
              for o in options)):
        # It's ambiguous whether this is a type, a function or something
        # else, so encode it as a constant.
        combined_types = pytd_utils.JoinTypes(t.to_type() for t in options)
        data.append(pytd.Constant(name, combined_types))
      else:
        for option in options:
          if hasattr(option, "to_pytd_def"):
            d = option.to_pytd_def(name)  # Deep definition
          else:
            d = option.to_type()  # Type only
          if isinstance(d, pytd.TYPE):
            data.append(pytd.Constant(name, d))
          else:
            data.append(d)
    return pytd_utils.WrapTypeDeclUnit("inferred", data)

  @staticmethod
  def _call_traces_to_function(call_traces, prefix=""):
    funcs = collections.defaultdict(pytd_utils.OrderedSet)
    for funcvar, args, kws, retvar in call_traces:
      if isinstance(funcvar.data, abstract.BoundFunction):
        func = funcvar.data.underlying.signatures[0]
      else:
        func = funcvar.data.signatures[0]
      arg_names = func.get_parameter_names()
      arg_types = (a.data.to_type()
                   for a in func.get_bound_arguments() + list(args))
      ret = pytd_utils.JoinTypes(t.to_type() for t in retvar.data)
      funcs[funcvar.data.name].add(pytd.Signature(
          tuple(pytd.Parameter(n, t)
                for n, t in zip(arg_names, arg_types)) +
          tuple(pytd.Parameter(name, a.data.to_type())
                for name, a in kws),
          ret, has_optional=False, exceptions=(), template=()))
    functions = []
    for name, signatures in funcs.items():
      functions.append(pytd.Function(prefix + name, tuple(signatures)))
    return functions

  def pytd_functions_for_call_traces(self):
    return self._call_traces_to_function(self._calls, "~")

  def pytd_classes_for_call_traces(self):
    class_to_records = collections.defaultdict(list)
    for call_record in self._method_calls:
      args = call_record.positional_arguments
      if not any(isinstance(a.data, abstract.Unknown) for a in args):
        # We don't need to record call signatures that don't involve
        # unknowns - there's nothing to solve for.
        continue
      clsvar = args[0].data.get_class()
      for cls in clsvar.data:
        if isinstance(cls, abstract.PyTDClass):
          class_to_records[cls].append(call_record)
    classes = []
    for cls, call_records in class_to_records.items():
      classes.append(pytd.Class(
          name="~" + cls.name,
          parents=(),  # not used in solver
          methods=self._call_traces_to_function(call_records),
          constants=(),
          template=(),
      ))
    return classes

  def compute_types(self, defs, ignore):
    self.program.Freeze()
    ty = pytd_utils.Concat(
        self.pytd_for_types(defs, ignore),
        pytd.TypeDeclUnit(
            "unknowns", (),
            tuple(self.pytd_classes_for_unknowns()) +
            tuple(self.pytd_classes_for_call_traces()),
            tuple(self.pytd_functions_for_call_traces())))
    ty = ty.Visit(optimize.PullInMethodClasses())
    ty = ty.Visit(visitors.DefaceUnresolved([ty, self.loader.concat_all()]))
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


def program_to_dot(program, ignored, only_cfg=False):
  """Convert a typegraph.Program into a dot file.

  Args:
    program: The program to convert.
    ignored: A set of names that should be ignored. This affects most kinds of
    nodes.
    only_cfg: If set, only output the control flow graph.
  Returns:
    A str of the dot code.
  """
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
    sb.write("%s[shape=polygon,sides=4,label=\"%s\"];\n"
             % (objname(node), node.name))
    for other in node.outgoing:
      sb.write("%s -> %s [penwidth=2.0];\n" % (objname(node), objname(other)))

  if only_cfg:
    sb.write("}\n")
    return sb.getvalue()

  for variable in program.variables:
    if variable.name in ignored:
      continue
    if all(origin.where == program.entrypoint
           for value in variable.values
           for origin in value.origins):
      # Ignore "boring" values (a.k.a. constants)
      continue
    sb.write('%s[label="%s",shape=polygon,sides=4,distortion=.1];\n'
             % (objname(variable), escape(variable.name)))
    for val in variable.values:
      sb.write("%s -> %s [arrowhead=none];\n" %
               (objname(variable), objname(val)))
      sb.write("%s[label=\"%s@0x%x\",fillcolor=%s];\n" %
               (objname(val), repr(val.data)[:10], id(val.data),
                "white" if val.origins else "red"))
      for loc, srcsets in val.origins:
        if loc == program.entrypoint:
          continue
        for srcs in srcsets:
          sb.write("%s[label=\"\"];\n" % (objname(srcs)))
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


def _get_module_name(filename, pythonpath):
  """Try to reverse-engineer the module name from the filename.

  This will not always be possible. It depends on the filename starting with
  an entry in the pythonpath. It's used for relative imports.

  Args:
    filename: The filename of a Python file. E.g. "src/foo/bar/my_module.py".
    pythonpath: A tuple of paths.

  Returns:
    A module name, e.g. "foo.bar.my_module", or None if we can't determine the
    module name.
  """
  if filename:
    filename, _ = os.path.splitext(filename)
    for path in pythonpath:
      if filename.startswith(path):
        subdir = filename[len(path):].lstrip(os.path.sep)
        return subdir.replace(os.path.sep, ".")


def infer_types(src, python_version, filename=None, run_builtins=True,
                pybuiltins_filename=None,
                pythonpath=(),
                find_pytd_import_ext=".pytd",
                import_drop_prefixes=(),
                output_cfg=None, output_typegraph=None,
                output_pseudocode=None, deep=True, solve_unknowns=True,
                reverse_operators=False, cache_unknowns=False,
                skip_repeat_calls=True):
  """Given Python source return its types.

  Args:
    src: A string containing Python source code.
    python_version: The python version to emulate (major, minor).
    filename: Filename of the program we're parsing.
    run_builtins: Whether to preload the native Python builtins when running
      the program.
    pybuiltins_filename: Path to Python builtins, or None for default.
    pythonpath: List of directories to search for .pytd-gen files.
    find_pytd_import_ext: Extension pattern to use when looking up import PyTD
                          in pythonpath.
    import_drop_prefixes: List of prefixes to drop when resolving module names.
    output_cfg: A filename into which to save an SVG of the control flow graph.
    output_typegraph: A filename into which to save an SVG of the typegraph.
    output_pseudocode: A filename to write pseudo code to.
    deep: If True, analyze all functions, even the ones not called by the main
      execution flow.
    solve_unknowns: If yes, try to replace structural types ("~unknowns") with
      nominal types.
    reverse_operators: If True, emulate operations like __radd__.
    cache_unknowns: If True, do a faster approximation of unknown types.
    skip_repeat_calls: If True, don't rerun functions that have been called
      before with the same arguments and environment.
  Returns:
    A TypeDeclUnit
  Raises:
    AssertionError: In case of a bad parameter combination.
  """
  tracer = CallTracer(python_version=python_version,
                      module_name=_get_module_name(filename, pythonpath),
                      reverse_operators=reverse_operators,
                      cache_unknowns=cache_unknowns,
                      pythonpath=pythonpath,
                      find_pytd_import_ext=find_pytd_import_ext,
                      import_drop_prefixes=import_drop_prefixes,
                      pybuiltins_filename=pybuiltins_filename,
                      skip_repeat_calls=skip_repeat_calls)
  loc, defs, builtin_names = tracer.run_program(src, filename, run_builtins)
  log.info("===Done run_program===")
  # TODO(pludemann): make test_inference.InferDedent and this code the same:
  if deep:
    tracer.exitpoint = tracer.analyze(loc, defs, builtin_names)
  else:
    tracer.exitpoint = loc
  ast = tracer.compute_types(defs, builtin_names)
  if solve_unknowns:
    log.info("=========== PyTD to solve =============\n%s", pytd.Print(ast))
    ast = convert_structural.convert_pytd(ast, tracer.loader.concat_all())
  if output_cfg or output_typegraph:
    if output_cfg and output_typegraph:
      raise AssertionError("Can output CFG or typegraph, but not both")
    dot = program_to_dot(tracer.program, set([]), bool(output_cfg))
    proc = subprocess.Popen(["/usr/bin/dot", "-T", "svg", "-o",
                             output_cfg or output_typegraph],
                            stdin=subprocess.PIPE)
    proc.stdin.write(dot)
    proc.stdin.close()
  if output_pseudocode:
    src = program_to_pseudocode(tracer.program)
    with open(output_pseudocode, "w") as fi:
      fi.write(src)

  return ast
