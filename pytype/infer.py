"""Code for generating and storing inferred types."""

import collections
import logging
import os
import StringIO
import subprocess
import sys


from pytype import abstract
from pytype import convert_structural
from pytype import exceptions
from pytype import function
from pytype import metrics
from pytype import output
from pytype import state as frame_state
from pytype import typing
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


class CallTracer(vm.VirtualMachine):
  """Virtual machine that records all function calls.

  Attributes:
    exitpoint: A CFG node representing the program exit. Needs to be set before
      analyze_types.
  """

  _CONSTRUCTORS = ("__new__", "__init__")

  def __init__(self, *args, **kwargs):
    super(CallTracer, self).__init__(*args, **kwargs)
    self._unknowns = {}
    self._builtin_map = {}
    self._calls = set()
    self._method_calls = set()
    # Used by init_class.
    self._instance_cache = {}
    # Used by call_init. Can differ from _instance_cache because we also call
    # __init__ on classes not initialized via init_class.
    self._initialized_instances = set()
    self._interpreter_functions = []
    self._analyzed_functions = set()
    self._generated_classes = {}
    self.exitpoint = None

  def create_argument(self, node, signature, name):
    t = signature.annotations.get(name)
    if t:
      node, _, instance = self.init_class(node, t)
      return node, instance
    else:
      return node, self.convert.create_new_unknown(node, force=True)

  def create_varargs(self, node):
    value = abstract.Instance(self.convert.tuple_type, self)
    value.initialize_type_parameter(
        node, abstract.T,
        self.convert.create_new_unknown(node))
    return value.to_variable(node)

  def create_kwargs(self, node):
    key_type = self.convert.primitive_class_instances[str].to_variable(node)
    value_type = self.convert.create_new_unknown(node)
    kwargs = abstract.Instance(self.convert.dict_type, self)
    kwargs.initialize_type_parameter(node, abstract.K, key_type)
    kwargs.initialize_type_parameter(node, abstract.V, value_type)
    return kwargs.to_variable(node)

  def create_method_arguments(self, node, method):
    """Create arguments for the given method.

    Args:
      node: The current node.
      method: An abstract.InterpreterFunction.

    Returns:
      A tuple of a node and an abstract.FunctionArgs object.
    """
    args = []
    for i in range(method.argcount()):
      node, arg = self.create_argument(node, method.signature,
                                       method.signature.param_names[i])
      args.append(arg)
    kws = {}
    for key in method.signature.kwonly_params:
      node, arg = self.create_argument(node, method.signature, key)
      kws[key] = arg
    starargs = self.create_varargs(node) if method.has_varargs() else None
    starstarargs = self.create_kwargs(node) if method.has_kwargs() else None
    return node, abstract.FunctionArgs(posargs=tuple(args),
                                       namedargs=kws,
                                       starargs=starargs,
                                       starstarargs=starstarargs)

  def call_function_with_args(self, node, val, args):
    """Call a function.

    Args:
      node: The given node.
      val: A cfg.Binding containing the function.
      args: An abstract.FunctionArgs object.

    Returns:
      A tuple of (1) a node and (2) a cfg.Variable of the return value.
    """
    fvar = val.AssignToNewVariable(node)
    with val.data.record_calls():
      new_node, ret = self.call_function_in_frame(node, fvar, *args)
    return new_node, ret

  def call_function_in_frame(self, node, var, args, kwargs,
                             starargs, starstarargs):
    frame = frame_state.SimpleFrame()
    self.push_frame(frame)
    log.info("Analyzing %r", [v.name for v in var.data])
    state = frame_state.FrameState.init(node, self)
    try:
      state, ret = self.call_function_with_state(
          state, var, args, kwargs, starargs, starstarargs)
    except (vm.RecursionException, exceptions.ByteCodeException):
      # A legitimate exception, which will be handled in run_instruction. (See,
      # e.g., CheckerTest.testRecursion.) Note that we don't want to pop the
      # frame in the case of a crash (any exception besides the ones we catch
      # here), since the crash might have left us in a bad state that will
      # cause pop_frame to raise an error, masking the actual problem.
      self.pop_frame(frame)
      raise
    else:
      self.pop_frame(frame)
    return state.node, ret

  def maybe_analyze_method(self, node, val):
    method = val.data
    fname = val.data.name
    self._analyzed_functions.add(method)
    if isinstance(method, (abstract.InterpreterFunction,
                           abstract.BoundInterpreterFunction)):
      if (not self.analyze_annotated and method.signature.annotations and
          fname not in self._CONSTRUCTORS):
        log.info("%r has type annotations, not analyzing further.", fname)
      elif method.is_abstract:
        log.info("%r is abstract, not analyzing further.", fname)
      else:
        node, args = self.create_method_arguments(node, method)
        node, _ = self.call_function_with_args(node, val, args)
    return node

  def _call_with_fake_args(self, node, funcv):
    """Attempt to call the given function with made-up arguments."""
    # TODO(tsudol): If expand this beyond __init__, need to handle
    # DictKeyMissing
    nodes = []
    rets = []
    for funcb in funcv.bindings:
      func = funcb.data
      log.info("Trying %s with fake arguments", func)

      if isinstance(func, (abstract.InterpreterFunction,
                           abstract.BoundInterpreterFunction)):
        node, args = self.create_method_arguments(node, func)
        if func.is_attribute_of_class:
          args = args.replace(posargs=args.posargs[1:])
        # Once the args are generated, try calling the function.
        # call_function will check fallback_to_unsolvable if a DictKeyMissing or
        # FailedFunctionCall error is raised when the target function is called.
        # DictKeyMissing doesn't trigger call_with_fake_args, so that shouldn't
        # be raised again, and generating fake arguments should avoid any
        # FailedFunctionCall errors. To prevent an infinite recursion loop, set
        # fallback_to_unsolvable to False just in case.
        # This means any additional errors that may be raised will be passed to
        # the call_function that called this method in the first place.
        node2, ret = self.call_function(node,
                                        funcb.AssignToNewVariable(),
                                        args,
                                        fallback_to_unsolvable=False)
        nodes.append(node2)
        rets.append(ret)

    if nodes:
      ret = self.join_variables(node, rets)
      node = self.join_cfg_nodes(nodes)
      if ret.bindings:
        return node, ret
    log.info("Unable to generate fake arguments for %s", funcv)
    return node, self.convert.create_new_unsolvable(node)

  def analyze_method_var(self, node0, name, var):
    log.info("Analyzing %s", name)
    node1 = node0.ConnectNew(name)
    for val in var.Bindings(node0):
      node2 = self.maybe_analyze_method(node1, val)
      node2.ConnectTo(node0)
    return node0

  def bind_method(self, node, name, methodvar, instance, clsvar):
    bound = self.program.NewVariable()
    for m in methodvar.Data(node):
      bound.AddBinding(m.property_get(instance, clsvar), [], node)
    return bound

  def _instantiate_binding(self, node0, cls):
    """Instantiate a class binding."""
    node0, new = cls.data.get_own_new(node0, cls)
    if not new or (
        any(not isinstance(f, abstract.InterpreterFunction) for f in new.data)):
      # This assumes that any inherited __new__ method defined in a pyi file
      # returns an instance of the current class.
      return cls.data.instantiate(node0)
    instance = self.program.NewVariable()
    for b in new.bindings:
      self._analyzed_functions.add(b.data)
      node0, args = self.create_method_arguments(node0, b.data)
      if args.posargs and (
          b.data.signature.param_names[0] not in b.data.signature.annotations):
        args = args._replace(
            posargs=(cls.AssignToNewVariable(node0),) + args.posargs[1:])
      node1 = node0.ConnectNew()
      node2, ret = self.call_function_with_args(node1, b, args)
      node2.ConnectTo(node0)
      instance.PasteVariable(ret)
    return instance

  def instantiate(self, node, clsv):
    """Build an (dummy) instance from a class, for analyzing it."""
    n = self.program.NewVariable()
    for cls in clsv.Bindings(node):
      n.PasteVariable(self._instantiate_binding(node, cls))
    return n

  def _mark_maybe_missing_members(self, values):
    """Set maybe_missing_members to True on these values and their type params.

    Args:
      values: A list of AtomicAbstractValue objects. On every instance among
        the values, recursively set maybe_missing_members to True on the
        instance and its type parameters.
    """
    values = list(values)
    seen = set()
    while values:
      v = values.pop(0)
      if v not in seen:
        seen.add(v)
        if isinstance(v, abstract.SimpleAbstractValue):
          v.maybe_missing_members = True
          for child in v.type_parameters.values():
            values.extend(child.data)

  def init_class(self, node, cls):
    """Instantiate a class, and also call __init__."""
    key = (self.frame and self.frame.current_opcode, cls)
    if (key not in self._instance_cache or
        self._instance_cache[key] is _INITIALIZING):
      clsvar = cls.to_variable(node)
      instance = self.instantiate(node, clsvar)
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
        self._mark_maybe_missing_members(instance.data)
      else:
        self._instance_cache[key] = _INITIALIZING
        node = self.call_init(node, instance)
      self._instance_cache[key] = clsvar, instance
    clsvar, instance = self._instance_cache[key]
    return node, clsvar, instance

  def call_init(self, node, instance):
    # Call __init__ on each binding.
    # TODO(kramm): This should do join_cfg_nodes, instead of concatenating them.
    for b in instance.bindings:
      if b.data in self._initialized_instances:
        continue
      self._initialized_instances.add(b.data)
      if isinstance(b.data, abstract.SimpleAbstractValue):
        for param in b.data.type_parameters.values():
          node = self.call_init(node, param)
      b_clsvar = b.data.get_class()
      b_clsbind = b_clsvar.bindings[0]
      node, init = self.attribute_handler.get_attribute(
          node, b_clsbind.data, "__init__", b, b_clsbind)
      if init:
        bound_init = self.bind_method(
            node, "__init__", init, b.data, b_clsvar)
        try:
          node = self.analyze_method_var(node, "__init__", bound_init)
        except vm.RecursionException:
          # We've encountered recursion during an __init__ call, which means
          # we have another incompletely initialized instance of the same class
          # (or a subclass) at the same node. (See, e.g.,
          # testRecursiveConstructor and testRecursiveConstructorSubclass in
          # test_classes.ClassesTest.) If we allow the RecursionException to be
          # raised, initialization of that first instance will be aborted.
          # Instead, mark this second instance as incomplete.
          self._mark_maybe_missing_members([b.data])
    return node

  def analyze_class(self, node, val):
    node, clsvar, instance = self.init_class(node, val.data)
    good_instances = [b for b in instance.bindings
                      if b.data.cls and val.data in b.data.cls.data]
    if not good_instances:
      # __new__ returned something that's not an instance of our class.
      instance = val.data.instantiate(node)
      node = self.call_init(node, instance)
    elif len(good_instances) != len(instance.bindings):
      # __new__ returned some extra possibilities we don't need.
      instance = self.join_bindings(node, good_instances)
    for name, methodvar in sorted(val.data.members.items()):
      if name in self._CONSTRUCTORS:
        continue  # We already called this method during initialization.
      b = self.bind_method(node, name, methodvar, instance, clsvar)
      node = self.analyze_method_var(node, name, b)
    return node

  def analyze_function(self, node, val):
    if val.data.is_attribute_of_class:
      # We'll analyze this function as part of a class.
      log.info("Analyze functions: Skipping class method %s", val.data.name)
    elif val.data.is_closure():
      # We analyze closures as part of the function they're defined in.
      log.info("Analyze functions: Skipping closure %s", val.data.name)
    else:
      new_node = node.ConnectNew(val.data.name)
      node2 = self.maybe_analyze_method(new_node, val)
      node2.ConnectTo(node)
    return node

  def analyze_toplevel(self, node, defs):
    for name, var in sorted(defs.items()):  # sort, for determinicity
      if name not in self._builtin_map:
        for value in var.bindings:
          if isinstance(value.data, abstract.InterpreterClass):
            node = self.analyze_class(node, value)
          elif isinstance(value.data, (abstract.InterpreterFunction,
                                       abstract.BoundInterpreterFunction)):
            node = self.analyze_function(node, value)
    # Now go through all top-level non-bound functions we haven't analyzed yet.
    # These are typically hidden under a decorator.
    for f in self._interpreter_functions:
      for value in f.bindings:
        if value.data not in self._analyzed_functions:
          self.analyze_function(node, value)

  def analyze(self, node, defs, maximum_depth):
    assert not self.frame
    self.maximum_depth = sys.maxint if maximum_depth is None else maximum_depth
    node = node.ConnectNew(name="Analyze")
    self.analyze_toplevel(node, defs)
    return node

  def trace_module_member(self, module, name, member):
    if module is None or isinstance(module, typing.TypingOverlay):
      # TypingOverlay takes precedence over typing.pytd.
      trace = True
    else:
      trace = (module.ast is self.loader.typing
               and name not in self._builtin_map)
    if trace:
      self._builtin_map[name] = member.data

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

  def trace_functiondef(self, f):
    if not self.reading_builtins:
      self._interpreter_functions.append(f)

  def trace_namedtuple(self, nt):
    # All namedtuple instances with the same name are equal, so it's fine to
    # overwrite previous instances.
    self._generated_classes[nt.name] = nt

  def pytd_classes_for_unknowns(self):
    classes = []
    for name, var in self._unknowns.items():
      for value in var.FilteredData(self.exitpoint):
        classes.append(value.to_structural_def(self.exitpoint, name))
    return classes

  def pytd_for_types(self, defs):
    data = []
    for name, var in defs.items():
      if name in output.TOP_LEVEL_IGNORE or self._is_builtin(name, var.data):
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
      elif options:
        for option in options:
          try:
            d = option.to_pytd_def(self.exitpoint, name)  # Deep definition
          except NotImplementedError:
            d = option.to_type(self.exitpoint)  # Type only
            if isinstance(d, pytd.NothingType):
              assert isinstance(option, abstract.Empty)
              d = pytd.AnythingType()
          if isinstance(d, pytd.TYPE) and not isinstance(d, pytd.TypeParameter):
            data.append(pytd.Constant(name, d))
          else:
            data.append(d)
      else:
        log.error("No visible options for " + name)
        data.append(pytd.Constant(name, pytd.AnythingType()))
    return pytd_utils.WrapTypeDeclUnit("inferred", data)

  @staticmethod
  def _call_traces_to_function(call_traces, name_transform=lambda x: x):
    funcs = collections.defaultdict(pytd_utils.OrderedSet)
    for node, func, sigs, args, kws, retvar in call_traces:
      # The lengths may be different in the presence of optional and kw args.
      arg_names = max((sig.get_positional_names() for sig in sigs), key=len)
      for i in range(len(arg_names)):
        if not isinstance(func.data, abstract.BoundFunction) or i > 0:
          arg_names[i] = function.argname(i)
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

  def _is_builtin(self, name, data):
    return self._builtin_map.get(name) == data

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
          parents=(pytd.NamedType("__builtin__.object"),),  # not used in solver
          methods=tuple(self._call_traces_to_function(call_records)),
          constants=(),
          template=(),
      ))
    return classes

  def pytd_aliases(self):
    return ()  # TODO(kramm): Compute these.

  def pytd_classes_for_namedtuple_instances(self):
    return tuple(v.pytd_cls for v in self._generated_classes.values())

  def compute_types(self, defs):
    ty = pytd_utils.Concat(
        self.pytd_for_types(defs),
        pytd.TypeDeclUnit(
            "unknowns",
            constants=tuple(),
            type_params=tuple(),
            classes=tuple(self.pytd_classes_for_unknowns()) +
            tuple(self.pytd_classes_for_call_traces()) +
            self.pytd_classes_for_namedtuple_instances(),
            functions=tuple(self.pytd_functions_for_call_traces()),
            aliases=tuple(self.pytd_aliases())))
    ty = ty.Visit(optimize.CombineReturnsAndExceptions())
    ty = ty.Visit(optimize.PullInMethodClasses())
    ty = ty.Visit(visitors.DefaceUnresolved(
        [ty, self.loader.concat_all()], "~unknown"))
    return ty.Visit(visitors.AdjustTypeParameters())

  def _check_return(self, node, actual, formal):
    bad = self.matcher.bad_matches(actual, formal, node)
    if bad:
      combined = pytd_utils.JoinTypes(
          view[actual].data.to_type(node, view=view) for view in bad)
      self.errorlog.bad_return_type(
          self.frames, combined, formal.get_instance_type(node))


def _pretty_variable(var):
  """Return a pretty printed string for a Variable."""
  lines = []
  single_value = len(var.bindings) == 1
  var_desc = "v%d" % var.id
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
    if variable.id in ignored:
      continue
    if all(origin.where == program.entrypoint
           for value in variable.bindings
           for origin in value.origins):
      # Ignore "boring" values (a.k.a. constants)
      continue
    sb.write('%s[label="%d",shape=polygon,sides=4,distortion=.1];\n'
             % (objname(variable), variable.id))
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


def _filename_to_module_name(filename):
  """Helper function for get_module_name."""
  if os.path.dirname(filename).startswith(os.pardir):
    # Don't try to infer a module name for filenames starting with ../
    return None
  return filename.replace(os.sep, ".")


def get_module_name(filename, options):
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
    filename, _ = os.path.splitext(os.path.normpath(filename))
    # We want '' in our lookup path, but we don't want it for prefix tests.
    for path in filter(bool, options.pythonpath):
      path = os.path.normpath(path)
      if not path.endswith(os.sep):
        path += os.sep
      if filename.startswith(path):
        rel_filename = filename[len(path):]
        return _filename_to_module_name(rel_filename)
    # Explicit pythonpath has failed, treat filename as relative to .
    return _filename_to_module_name(filename)


def check_types(py_src, py_filename, errorlog, options, loader,
                run_builtins=True,
                deep=True,
                cache_unknowns=False,
                init_maximum_depth=INIT_MAXIMUM_DEPTH):
  """Verify a PyTD against the Python code."""
  tracer = CallTracer(errorlog=errorlog, options=options,
                      module_name=get_module_name(py_filename, options),
                      cache_unknowns=cache_unknowns,
                      analyze_annotated=True,
                      generate_unknowns=False,
                      loader=loader)
  loc, defs = tracer.run_program(
      py_src, py_filename, init_maximum_depth, run_builtins)
  snapshotter = metrics.get_metric("memory", metrics.Snapshot)
  snapshotter.take_snapshot("infer:check_types:tracer")
  if deep:
    tracer.analyze(loc, defs, maximum_depth=(2 if options.quick else None))
  snapshotter.take_snapshot("infer:check_types:post")
  _maybe_output_debug(options, tracer.program)


def infer_types(src, errorlog, options, loader,
                filename=None, run_builtins=True,
                deep=True,
                cache_unknowns=False, show_library_calls=False,
                analyze_annotated=False,
                init_maximum_depth=INIT_MAXIMUM_DEPTH, maximum_depth=None):
  """Given Python source return its types.

  Args:
    src: A string containing Python source code.
    errorlog: Where error messages go. Instance of errors.ErrorLog.
    options: config.Options object
    loader: A load_pytd.Loader instance to load PYI information.
    filename: Filename of the program we're parsing.
    run_builtins: Whether to preload the native Python builtins when running
      the program.
    deep: If True, analyze all functions, even the ones not called by the main
      execution flow.
    cache_unknowns: If True, do a faster approximation of unknown types.
    show_library_calls: If True, call traces are kept in the output.
    analyze_annotated: If True, analyze methods with type annotations, too.
    init_maximum_depth: Depth of analysis during module loading.
    maximum_depth: Depth of the analysis. Default: unlimited.
  Returns:
    A TypeDeclUnit
  Raises:
    AssertionError: In case of a bad parameter combination.
  """
  tracer = CallTracer(errorlog=errorlog, options=options,
                      module_name=get_module_name(filename, options),
                      cache_unknowns=cache_unknowns,
                      analyze_annotated=analyze_annotated,
                      generate_unknowns=options.protocols,
                      store_all_calls=not deep, loader=loader)
  loc, defs = tracer.run_program(
      src, filename, init_maximum_depth, run_builtins)
  log.info("===Done running definitions and module-level code===")
  snapshotter = metrics.get_metric("memory", metrics.Snapshot)
  snapshotter.take_snapshot("infer:infer_types:tracer")
  if deep:
    tracer.exitpoint = tracer.analyze(loc, defs, maximum_depth)
  else:
    tracer.exitpoint = loc
  snapshotter.take_snapshot("infer:infer_types:post")
  ast = tracer.compute_types(defs)
  ast = tracer.loader.resolve_ast(ast)
  if tracer.has_unknown_wildcard_imports:
    try:
      ast.Lookup("__getattr__")
    except KeyError:
      ast = pytd_utils.Concat(
          ast, builtins.GetDefaultAst(options.python_version))
  # If merged with other if statement, triggers a ValueError: Unresolved class
  # when attempts to load from the protocols file
  if options.protocols:
    protocols_pytd = tracer.loader.import_name("protocols")
  else:
    protocols_pytd = None
  builtins_pytd = tracer.loader.concat_all()
  # Insert type parameters, where appropriate
  ast = ast.Visit(visitors.CreateTypeParametersForSignatures())
  if options.protocols:
    log.info("=========== PyTD to solve =============\n%s", pytd.Print(ast))
    ast = convert_structural.convert_pytd(ast, builtins_pytd, protocols_pytd)
  elif not show_library_calls:
    log.info("Solving is turned off. Discarding call traces.")
    # Rename remaining "~unknown" to "?"
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
