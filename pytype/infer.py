"""Code for generating and storing inferred types."""

import collections
import logging
import os
import StringIO
import subprocess
import sys


from pytype import abstract
from pytype import convert_structural
from pytype import output
from pytype import state as frame_state
from pytype import utils
from pytype import vm
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import builtins
from pytype.pytd.parse import visitors

log = logging.getLogger(__name__)


CallRecord = collections.namedtuple(
    "CallRecord", ["node", "function", "signatures", "positional_arguments",
                   "keyword_arguments", "return_value"])


# How deep to follow call chains, during module loading:
INIT_MAXIMUM_DEPTH = 4


_INITIALIZING = object()


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

  def __init__(self, *args, **kwargs):
    super(CallTracer, self).__init__(*args, **kwargs)
    self._unknowns = {}
    self._calls = set()
    self._method_calls = set()
    self._instance_cache = {}
    self.exitpoint = None

  def create_argument(self, node, signature, name, method_name):
    t = signature.annotations.get(name)
    if t:
      node, _, instance = self.init_class(node, t)
      return node, instance
    else:
      return node, self.convert.create_new_unknown(node, name)

  def create_varargs(self, node):
    value = abstract.Instance(self.convert.tuple_type, self, node)
    value.initialize_type_parameter(
        node, "T", self.convert.create_new_unknown(node, "varargs_value"))
    return value.to_variable(node, "*args")

  def create_kwargs(self, node):
    key_type = self.convert.primitive_class_instances[str].to_variable(
        node, "str")
    value_type = self.convert.create_new_unknown(node, "kwargs_value")
    kwargs = abstract.Instance(self.convert.dict_type, self, node)
    kwargs.initialize_type_parameter(
        node, abstract.Dict.KEY_TYPE_PARAM, key_type)
    kwargs.initialize_type_parameter(
        node, abstract.Dict.VALUE_TYPE_PARAM, value_type)
    return kwargs.to_variable(node, "**kwargs")

  def call_function_in_frame(self, node, var, args, kwargs,
                             starargs, starstarargs):
    frame = AnalysisFrame()
    self.push_frame(frame)
    log.info("Analyzing %r", [v.name for v in var.data])
    state = frame_state.FrameState.init(node)
    try:
      # May raise, e.g., RecursionError (see CheckerTest.testRecursion). Any
      # error is handled in run_instruction.
      state, ret = self.call_function_with_state(
          state, var, args, kwargs, starargs, starstarargs)
    finally:
      self.pop_frame(frame)
    return state.node, ret

  def maybe_analyze_method(self, val, node):
    method = val.data
    fname = val.data.name
    if isinstance(method, (abstract.InterpreterFunction,
                           abstract.BoundInterpreterFunction)):
      if (not self.analyze_annotated and val.data.signature.annotations and
          fname not in ["__new__", "__init__"]):
        log.info("%r has type annotations, not analyzing futher.", fname)
      else:
        args = []
        for i in range(method.argcount()):
          node, arg = self.create_argument(node, method.signature,
                                           method.signature.param_names[i],
                                           fname)
          args.append(arg)
        kws = {}
        for key in method.signature.kwonly_params:
          node, arg = self.create_argument(node, method.signature, key, fname)
          kws[key] = arg
        starargs = self.create_varargs(node) if method.has_varargs() else None
        starstarargs = self.create_kwargs(node) if method.has_kwargs() else None
        fvar = val.AssignToNewVariable("f", node)
        new_node, _ = self.call_function_in_frame(
            node, fvar, tuple(args), kws, starargs, starstarargs)
        new_node.ConnectTo(node)
        node = new_node
    return node

  def analyze_method_var(self, name, var, node):
    log.info("Analyzing %s", name)
    for val in var.Bindings(node):
      node2 = self.maybe_analyze_method(val, node)
      node2.ConnectTo(node)
    return node

  def bind_method(self, name, methodvar, instance, clsvar, node):
    bound = self.program.NewVariable(name)
    for m in methodvar.Data(node):
      bound.AddBinding(m.property_get(instance, clsvar), [], node)
    return bound

  def instantiate(self, clsv, node):
    """Build an (dummy) instance from a class, for analyzing it."""
    n = self.program.NewVariable(clsv.name)
    for cls in clsv.Data(node):
      instance = cls.instantiate(node)
      n.PasteVariable(instance, node)
    return n

  def init_class(self, node, cls):
    """Instantiate a class, and also call __init__."""
    key = (node, cls)
    if (key not in self._instance_cache or
        self._instance_cache[key] is _INITIALIZING):
      clsvar = cls.to_variable(node, "cls")
      instance = self.instantiate(clsvar, node)
      if key in self._instance_cache:
        # We've encountered a recursive pattern such as
        # class A:
        #   def __init__(self, x: "A"): ...
        # Calling __init__ again would lead to an infinite loop, so
        # we instead create an incomplete instance that will be
        # overwritten later. Note that we have to create a new
        # instance rather than using the one that we're already in
        # the process of initializing - otherwise, setting
        # maybe_missing_members to True would cause pytype to ignore
        # all attribute errors on self in __init__.
        abstract.variable_set(instance, "maybe_missing_members", True)
      else:
        self._instance_cache[key] = _INITIALIZING
        self.call_init(instance, node)
      self._instance_cache[key] = node, clsvar, instance
    return self._instance_cache[key]

  def call_init(self, instance, node, seen=None):
    if seen is None:
      seen = set()
    # Call __init__ on each binding.
    for b in instance.bindings:
      if b.data in seen:
        continue
      seen.add(b.data)
      if isinstance(b.data, abstract.SimpleAbstractValue):
        for param in b.data.type_parameters.values():
          node = self.call_init(param, node, seen)
      b_clsvar = b.data.get_class()
      b_clsbind = b_clsvar.bindings[0]
      node, init = self.attribute_handler.get_attribute(
          node, b_clsbind.data, "__init__", b, b_clsbind)
      if init:
        bound_init = self.bind_method(
            "__init__", init, b.data, b_clsvar, node)
        node = self.analyze_method_var("__init__", bound_init, node)
    return node

  def analyze_class(self, val, node):
    node, clsvar, instance = self.init_class(node, val.data)
    for name, methodvar in sorted(val.data.members.items()):
      if name == "__init__":
        continue  # We already called __init__ in init_class
      b = self.bind_method(name, methodvar, instance, clsvar, node)
      node2 = self.analyze_method_var(name, b, node)
      node2.ConnectTo(node)
    return node

  def analyze_function(self, val, node):
    if val.data.is_attribute_of_class:
      # We'll analyze this function as part of a class.
      log.info("Analyze functions: Skipping class method %s", val.data.name)
    elif val.data.is_closure():
      # We analyze closures as part of the function they're defined in.
      log.info("Analyze functions: Skipping closure %s", val.data.name)
    else:
      node2 = self.maybe_analyze_method(val, node)
      node2.ConnectTo(node)
    return node

  def analyze_toplevel(self, node, defs, ignore):
    for name, var in sorted(defs.items()):  # sort, for determinicity
      if name not in ignore:
        for value in var.bindings:
          if isinstance(value.data, abstract.InterpreterClass):
            node2 = self.analyze_class(value, node)
            node2.ConnectTo(node)
          elif isinstance(value.data, (abstract.InterpreterFunction,
                                       abstract.BoundInterpreterFunction)):
            node2 = self.analyze_function(value, node)
            node2.ConnectTo(node)

  def analyze(self, node, defs, ignore, maximum_depth):
    assert not self.frame
    self.maximum_depth = sys.maxint if maximum_depth is None else maximum_depth
    self.analyze_toplevel(node, defs, ignore)
    return node

  def trace_unknown(self, name, unknown):
    self._unknowns[name] = unknown

  def trace_call(self, node, func, sigs, posargs, namedargs, result):
    """Add an entry into the call trace.

    Args:
      node: The CFG node right after this function call.
      func: A typegraph Value of a function that was called.
      sigs: The signatures that the function might have been called with.
      posargs: The positional arguments, an iterable over cfg.Value.
      namedargs: The keyword arguments, a dict mapping str to cfg.Value.
      result: A Variable of the possible result values.
    """
    log.debug("Logging call to %r with %d args, return %r",
              func, len(posargs), result)
    args = tuple(posargs)
    kwargs = tuple((namedargs or {}).items())
    record = CallRecord(node, func, sigs, args, kwargs, result)
    if isinstance(func.data, abstract.BoundPyTDFunction):
      self._method_calls.add(record)
    elif isinstance(func.data, abstract.PyTDFunction):
      self._calls.add(record)

  def pytd_classes_for_unknowns(self):
    classes = []
    for name, var in self._unknowns.items():
      for value in var.FilteredData(self.exitpoint):
        classes.append(value.to_structural_def(self.exitpoint, name))
    return classes

  def pytd_for_types(self, defs, ignore):
    data = []
    for name, var in defs.items():
      if name in output.TOP_LEVEL_IGNORE or name in ignore:
        continue
      options = var.FilteredData(self.exitpoint)
      if (len(options) > 1 and not
          all(isinstance(o, (abstract.Function, abstract.BoundFunction))
              for o in options)):
        # It's ambiguous whether this is a type, a function or something
        # else, so encode it as a constant.
        combined_types = pytd_utils.JoinTypes(t.to_type(self.exitpoint)
                                              for t in options)
        data.append(pytd.Constant(name, combined_types))
      else:
        for option in options:
          if hasattr(option, "to_pytd_def"):
            d = option.to_pytd_def(self.exitpoint, name)  # Deep definition
          else:
            d = option.to_type(self.exitpoint)  # Type only
            if isinstance(d, pytd.NothingType):
              assert isinstance(option, abstract.Empty)
              d = pytd.AnythingType()
          if isinstance(d, pytd.TYPE):
            data.append(pytd.Constant(name, d))
          else:
            data.append(d)
    return pytd_utils.WrapTypeDeclUnit("inferred", data)

  @staticmethod
  def _call_traces_to_function(call_traces, name_transform=lambda x: x):
    funcs = collections.defaultdict(pytd_utils.OrderedSet)
    for node, func, sigs, args, kws, retvar in call_traces:
      # The lengths may be different in the presence of optional and kw args.
      arg_names = max((sig.get_positional_names() for sig in sigs), key=len)
      for i in range(len(arg_names)):
        if not isinstance(func.data, abstract.BoundFunction) or i > 0:
          arg_names[i] = "_" + str(i)
      arg_types = (a.data.to_type(node) for a in args)
      ret = pytd_utils.JoinTypes(t.to_type(node) for t in retvar.data)
      # TODO(kramm): Record these:
      starargs = None
      starstarargs = None
      funcs[func.data.name].add(pytd.Signature(
          tuple(pytd.Parameter(n, t, False, False, None)
                for n, t in zip(arg_names, arg_types)) +
          tuple(pytd.Parameter(name, a.data.to_type(node), False, False, None)
                for name, a in kws),
          starargs, starstarargs,
          ret, exceptions=(), template=()))
    functions = []
    for name, signatures in funcs.items():
      functions.append(pytd.Function(name_transform(name), tuple(signatures),
                                     pytd.METHOD))
    return functions

  def _pack_name(self, name):
    """Pack a name, for unpacking with type_match.unpack_name_of_partial()."""
    return "~" + name.replace(".", "~")

  def pytd_functions_for_call_traces(self):
    return self._call_traces_to_function(self._calls, self._pack_name)

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
      full_name = cls.module + "." + cls.name if cls.module else cls.name
      classes.append(pytd.Class(
          name=self._pack_name(full_name),
          metaclass=None,
          parents=(),  # not used in solver
          methods=tuple(self._call_traces_to_function(call_records)),
          constants=(),
          template=(),
      ))
    return classes

  def pytd_aliases(self):
    return ()  # TODO(kramm): Compute these.

  def compute_types(self, defs, ignore):
    self.program.Freeze()
    ty = pytd_utils.Concat(
        self.pytd_for_types(defs, ignore),
        pytd.TypeDeclUnit(
            "unknowns",
            constants=tuple(),
            type_params=tuple(),
            classes=tuple(self.pytd_classes_for_unknowns()) +
            tuple(self.pytd_classes_for_call_traces()),
            functions=tuple(self.pytd_functions_for_call_traces()),
            aliases=tuple(self.pytd_aliases())))
    ty = ty.Visit(optimize.PullInMethodClasses())
    ty = ty.Visit(visitors.DefaceUnresolved(
        [ty, self.loader.concat_all()], "~unknown"))
    return ty

  def _create_call_arg(self, name, t, node):
    if t == pytd.ClassType("__builtin__.object"):
      # As an arg, "object" means: we can use anything for this argument,
      # because everything inherits from object.
      # TODO(kramm): Maybe we should use AnythingType for params without type.
      return self.convert.create_new_unsolvable(node, name)
    else:
      return self.convert.convert_constant(
          name, abstract.AsInstance(t), subst={}, node=self.root_cfg_node)

  def _check_return(self, opcode, node, actual, formal):
    bad = self.matcher.bad_matches(actual, formal, node)
    if bad:
      combined = pytd_utils.JoinTypes([t.data.to_type(node) for t in bad])
      self.errorlog.bad_return_type(
          opcode, combined, formal.get_instance_type(node))

  def _check_function(self, pytd_function, f, node, skip_self=False):
    """Check that a function or method is compatible with its PYTD."""
    for sig in pytd_function.signatures:
      args = tuple(self._create_call_arg(p.name, p.type, node)
                   for p in sig.params[(1 if skip_self else 0):])
      nominal_return = self.convert.convert_constant_to_value(
          "ret", sig.return_type, subst={}, node=self.root_cfg_node)
      for val in f.bindings:
        fvar = val.AssignToNewVariable("f", node)
        _, retvar = self.call_function_in_frame(
            node, fvar, args, {}, None, None)
        if retvar.bindings:
          if isinstance(val.data, (abstract.InterpreterFunction,
                                   abstract.BoundInterpreterFunction)):
            self._check_return(
                val.data.get_first_opcode(), node, retvar, nominal_return)
          else:
            log.error("%s is not a function?", val.data.name)
        else:
          log.error("Couldn't call %s", pytd_function.name)

  def check_types(self, node, defs, ast, py_filename, pytd_filename):
    """Verify that the types declared in PyTD work with the Python code.

    E.g. if there's a PyTD signature
      def abs(x: int) -> int
    then we'll call the abs() function with an integer and verify that we get
    an integer back.
    Any error we encounter will be logged.

    Args:
      node: The CFG node at the end of the program.
      defs: All top-level identifiers declared by the program.
      ast: The PyTD AST.
      py_filename: Filename of the Python file.
      pytd_filename: Filename of the PyTD file.
    """
    # TODO(kramm): Do much more checking here.
    for item in ast.functions + ast.classes + ast.constants:
      if item.name not in defs:
        self.errorlog.missing_definition(item, pytd_filename, py_filename)

    if self.errorlog.has_error():
      return

    for pytd_function in ast.functions:
      self._check_function(pytd_function, defs[pytd_function.name], node)

    state = frame_state.FrameState.init(node)
    for pytd_cls in ast.classes:
      cls = defs[pytd_cls.name]
      for val in cls.bindings:
        # TODO(kramm): The call to the constructor of this should use the pytd.
        node2, _, instance = self.init_class(node, val.data)
        for pytd_method in pytd_cls.methods:
          _, method = self._retrieve_attr(state, instance, pytd_method.name)
          if method is None:
            raise NotImplementedError("getattr(%s) failed!" % pytd_method.name)
          # TODO(kramm): Should this be the node returned from _retrieve_attr?
          self._check_function(pytd_method, method, node2, skip_self=True)


def _pretty_variable(var):
  """Return a pretty printed string for a Variable."""
  lines = []
  single_value = len(var.bindings) == 1
  var_desc = "$%d %s" % (var.id, var.name)
  if not single_value:
    # Write a description of the variable (for single value variables this
    # will be written along with the value later on).
    lines.append(var_desc)
    var_prefix = "  "
  else:
    var_prefix = var_desc + " = "

  for value in var.bindings:
    i = 0 if value.data is None else value.data.id
    data = utils.maybe_truncate(value.data)
    binding = "%s#%d %s" % (var_prefix, i, data)

    if len(value.origins) == 1:
      # Single origin.  Use the binding as a prefix when writing the orign.
      prefix = binding + ", "
    else:
      # Multiple origins, write the binding on its own line, then indent all
      # of the origins.
      lines.append(binding)
      prefix = "    "

    for origin in value.origins:
      src = utils.pretty_dnf([[str(v) for v in source_set]
                              for source_set in origin.source_sets])
      lines.append("%s%s @%d" %(prefix, src, origin.where.id))
  return "\n".join(lines)


def program_to_text(program):
  """Generate a text (CFG nodes + assignments) version of a program.

  For debugging only.

  Args:
    program: An instance of cfg.Program

  Returns:
    A string representing all of the data for this program.
  """
  s = StringIO.StringIO()
  seen = set()
  for node in utils.order_nodes(program.cfg_nodes):
    seen.add(node)
    s.write("%s\n" % node.Label())
    s.write("  From: %s\n" % ", ".join(n.Label() for n in node.incoming))
    s.write("  To: %s\n" % ", ".join(n.Label() for n in node.outgoing))
    s.write("\n")
    variables = set(value.variable for value in node.bindings)
    for var in sorted(variables, key=lambda v: v.id):
      # If a variable is bound in more than one node then it will be listed
      # redundantly multiple times.  One alternative would be to only list the
      # values that occur in the given node, and then also list the other nodes
      # that assign the same variable.

      # Write the variable, indenting by two spaces.
      s.write("  %s\n" % _pretty_variable(var).replace("\n", "\n  "))
    s.write("\n")

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
      sum(len(v.bindings) for v in program.variables),
      len(program.variables)))

  sb = StringIO.StringIO()
  sb.write("digraph {\n")
  for node in program.cfg_nodes:
    if node in ignored:
      continue
    sb.write("%s[shape=polygon,sides=4,label=\"<%d>%s\"];\n"
             % (objname(node), node.id, node.name))
    for other in node.outgoing:
      sb.write("%s -> %s [penwidth=2.0];\n" % (objname(node), objname(other)))

  if only_cfg:
    sb.write("}\n")
    return sb.getvalue()

  for variable in program.variables:
    if variable.name in ignored:
      continue
    if all(origin.where == program.entrypoint
           for value in variable.bindings
           for origin in value.origins):
      # Ignore "boring" values (a.k.a. constants)
      continue
    sb.write('%s[label="%s",shape=polygon,sides=4,distortion=.1];\n'
             % (objname(variable), escape(variable.name)))
    for val in variable.bindings:
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


def _get_module_name(filename, options):
  """Return, or try to reverse-engineer, the name of the module we're analyzing.

  If a module was passed using --module-name, that name will be returned.
  Otherwise, this method tries to deduce the module name from the PYTHONPATH
  and the filename. This will not always be possible. (It depends on the
  filename starting with an entry in the pythonpath.)

  The module name is used for relative imports.

  Args:
    filename: The filename of a Python file. E.g. "src/foo/bar/my_module.py".
    options: An instance of config.Options.

  Returns:
    A module name, e.g. "foo.bar.my_module", or None if we can't determine the
    module name.
  """
  if options.module_name is not None:
    return options.module_name
  elif filename:
    filename, _ = os.path.splitext(filename)
    for path in options.pythonpath:
      # TODO(kramm): What if filename starts with "../"?  (os.pardir)
      if filename.startswith(path):
        subdir = filename[len(path):].lstrip(os.sep)
        return subdir.replace(os.sep, ".")


def check_types(py_src, pytd_src, py_filename, pytd_filename, errorlog,
                options,
                run_builtins=True,
                deep=True,
                cache_unknowns=False,
                init_maximum_depth=INIT_MAXIMUM_DEPTH):
  """Verify a PyTD against the Python code."""
  tracer = CallTracer(errorlog=errorlog, options=options,
                      module_name=_get_module_name(py_filename, options),
                      cache_unknowns=cache_unknowns,
                      analyze_annotated=True,
                      generate_unknowns=False)
  loc, defs, builtin_names = tracer.run_program(
      py_src, py_filename, init_maximum_depth, run_builtins)
  if pytd_src is not None:
    del deep  # ignored
    ast = builtins.ParsePyTD(pytd_src, pytd_filename, options.python_version,
                             lookup_classes=True)
    ast = tracer.loader.resolve_ast(ast)
    tracer.check_types(loc, defs, ast,
                       os.path.basename(py_filename),
                       os.path.basename(pytd_filename))
  elif deep:
    tracer.analyze(loc, defs, builtin_names,
                   maximum_depth=(2 if options.quick else None))
  _maybe_output_debug(options, tracer.program)


def infer_types(src,
                errorlog, options,
                filename=None, run_builtins=True,
                deep=True, solve_unknowns=True,
                cache_unknowns=False, extract_locals=True,
                analyze_annotated=False,
                init_maximum_depth=INIT_MAXIMUM_DEPTH, maximum_depth=None):
  """Given Python source return its types.

  Args:
    src: A string containing Python source code.
    errorlog: Where error messages go. Instance of errors.ErrorLog.
    options: config.Options object
    filename: Filename of the program we're parsing.
    run_builtins: Whether to preload the native Python builtins when running
      the program.
    deep: If True, analyze all functions, even the ones not called by the main
      execution flow.
    solve_unknowns: If yes, try to replace structural types ("~unknowns") with
      nominal types.
    cache_unknowns: If True, do a faster approximation of unknown types.
    extract_locals: If not optimizing, should we at least remove the call
      traces?
    analyze_annotated: If True, analyze methods with type annotations, too.
    init_maximum_depth: Depth of analysis during module loading.
    maximum_depth: Depth of the analysis. Default: unlimited.
  Returns:
    A TypeDeclUnit
  Raises:
    AssertionError: In case of a bad parameter combination.
  """
  tracer = CallTracer(errorlog=errorlog, options=options,
                      module_name=_get_module_name(filename, options),
                      cache_unknowns=cache_unknowns,
                      analyze_annotated=analyze_annotated,
                      generate_unknowns=not options.quick)
  loc, defs, builtin_names = tracer.run_program(
      src, filename, init_maximum_depth, run_builtins)
  log.info("===Done run_program===")
  if deep:
    tracer.exitpoint = tracer.analyze(loc, defs, builtin_names, maximum_depth)
  else:
    tracer.exitpoint = loc
  ast = tracer.compute_types(defs, builtin_names)
  ast = tracer.loader.resolve_ast(ast)
  if tracer.has_unknown_wildcard_imports:
    try:
      ast.Lookup("__getattr__")
    except KeyError:
      ast = pytd_utils.Concat(
          ast, builtins.GetDefaultAst(options.python_version))
  builtins_pytd = tracer.loader.concat_all()
  if solve_unknowns:
    log.info("=========== PyTD to solve =============\n%s", pytd.Print(ast))
    ast = convert_structural.convert_pytd(ast, builtins_pytd)
  elif extract_locals:
    log.info("Solving is turned off. Discarding call traces.")
    # Rename "~unknown" to "?"
    ast = ast.Visit(visitors.RemoveUnknownClasses())
    # Remove "~list" etc.:
    ast = convert_structural.extract_local(ast)
  if options.output_cfg or options.output_typegraph:
    if options.output_cfg and options.output_typegraph:
      raise AssertionError("Can output CFG or typegraph, but not both")
    dot = program_to_dot(tracer.program, set([]), bool(options.output_cfg))
    proc = subprocess.Popen(["/usr/bin/dot", "-T", "svg", "-o",
                             options.output_cfg or options.output_typegraph],
                            stdin=subprocess.PIPE)
    proc.stdin.write(dot)
    proc.stdin.close()

  _maybe_output_debug(options, tracer.program)
  return ast, builtins_pytd


def _maybe_output_debug(options, program):
  if options.output_debug:
    text = program_to_text(program)
    if options.output_debug == "-":
      log.info("=========== Program Dump =============\n%s", text)
    else:
      with open(options.output_debug, "w") as fi:
        fi.write(text)
