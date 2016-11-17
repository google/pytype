"""A abstract virtual machine for python bytecode that generates typegraphs.

A VM for python byte code that uses pytype/pytd/cfg ("typegraph") to generate a
trace of the program execution.
"""

# We have names like "byte_NOP":
# pylint: disable=invalid-name

# Bytecodes don't always use all their arguments:
# pylint: disable=unused-argument

import collections
import logging
import os
import re
import repr as reprlib
import sys


from pytype import abstract
from pytype import attribute
from pytype import blocks
from pytype import convert
from pytype import exceptions
from pytype import function
from pytype import load_pytd
from pytype import matcher
from pytype import metrics
from pytype import state as frame_state
from pytype import typing
from pytype import utils
from pytype.pyc import loadmarshal
from pytype.pyc import pyc
from pytype.pytd import cfg as typegraph
from pytype.pytd import slots
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import builtins
from pytype.pytd.parse import parser
from pytype.pytd.parse import visitors

log = logging.getLogger(__name__)


# Create a repr that won't overflow.
_TRUNCATE = 120
_TRUNCATE_STR = 72
repr_obj = reprlib.Repr()
repr_obj.maxother = _TRUNCATE
repr_obj.maxstring = _TRUNCATE_STR
repper = repr_obj.repr


Block = collections.namedtuple("Block", ["type", "op", "handler", "level"])

_opcode_counter = metrics.MapCounter("vm_opcode")


class RecursionException(Exception):
  pass


class VirtualMachineError(Exception):
  """For raising errors in the operation of the VM."""
  pass


class VirtualMachine(object):
  """A bytecode VM that generates a typegraph as it executes.

  Attributes:
    program: The typegraph.Program used to build the typegraph.
    root_cfg_node: The root CFG node that contains the definitions of builtins.
    primitive_classes: A mapping from primitive python types to their abstract
      types.
  """

  def __init__(self,
               errorlog,
               options,
               module_name=None,
               generate_unknowns=False,
               analyze_annotated=False,
               cache_unknowns=True):
    """Construct a TypegraphVirtualMachine."""
    self.maximum_depth = sys.maxint
    self.errorlog = errorlog
    self.options = options
    self.python_version = options.python_version
    self.generate_unknowns = generate_unknowns
    self.analyze_annotated = analyze_annotated
    self.cache_unknowns = cache_unknowns
    self.loader = load_pytd.Loader(base_module=module_name, options=options)
    self.frames = []  # The call stack of frames.
    self.functions_with_late_annotations = []
    self.frame = None  # The current frame.
    self.program = typegraph.Program()
    self.root_cfg_node = self.program.NewCFGNode("root")
    self.program.entrypoint = self.root_cfg_node
    self.vmbuiltins = self.loader.builtins
    self.convert = convert.Converter(self)
    self.program.default_data = self.convert.unsolvable
    self.matcher = matcher.AbstractMatcher()
    self.attribute_handler = attribute.AbstractAttributeHandler(self)
    self.has_unknown_wildcard_imports = False
    self.callself_stack = []

    # Map from builtin names to canonical objects.
    self.special_builtins = {
        # The super() function.
        "super": abstract.Super(self),
        # for more pretty branching tests.
        "__random__": self.convert.primitive_class_instances[bool],
        # boolean values.
        "True": self.convert.true,
        "False": self.convert.false,
        "isinstance": abstract.IsInstance(self),
    }

  def remaining_depth(self):
    return self.maximum_depth - len(self.frames)

  def is_at_maximum_depth(self):
    return len(self.frames) > self.maximum_depth

  def run_instruction(self, op, state):
    """Run a single bytecode instruction.

    Args:
      op: An opcode, instance of pyc.opcodes.Opcode
      state: An instance of state.FrameState, the state just before running
        this instruction.
    Returns:
      A tuple (why, state). "why" is the reason (if any) that this opcode aborts
      this function (e.g. through a 'raise'), or None otherwise. "state" is the
      FrameState right after this instruction that should roll over to the
      subsequent instruction.
    """
    _opcode_counter.inc(op.name)
    if log.isEnabledFor(logging.INFO):
      self.log_opcode(op, state)
    self.frame.current_opcode = op
    try:
      # dispatch
      bytecode_fn = getattr(self, "byte_%s" % op.name, None)
      if bytecode_fn is None:
        raise VirtualMachineError("Unknown opcode: %s" % op.name)
      state = bytecode_fn(state, op)
    except RecursionException as e:
      # This is not an error - it just means that the block we're analyzing
      # goes into a recursion, and we're already two levels deep.
      state = state.set_why("recursion")
    except exceptions.ByteCodeException:
      e = sys.exc_info()[1]
      state = state.set_exception(
          e.exception_type, e.create_instance(), None)
      # TODO(pludemann): capture exceptions that are indicative of
      #                  a bug (AttributeError?)
      log.info("Exception in program: %s: %r",
               e.exception_type.__name__, e.message)
      state = state.set_why("exception")
    if state.why == "reraise":
      state = state.set_why("exception")
    del self.frame.current_opcode
    return state

  def join_cfg_nodes(self, nodes):
    assert nodes
    if len(nodes) == 1:
      return nodes[0]
    else:
      ret = self.program.NewCFGNode()
      for node in nodes:
        node.ConnectTo(ret)
      return ret

  def run_frame(self, frame, node):
    """Run a frame (typically belonging to a method)."""
    self.push_frame(frame)
    frame.states[frame.f_code.co_code[0]] = frame_state.FrameState.init(node)
    return_nodes = []
    for block in frame.f_code.order:
      state = frame.states.get(block[0])
      if not state:
        log.warning("Skipping block %d,"
                    " we don't have any non-erroneous code that goes here.",
                    block.id)
        continue
      op = None
      for op in block:
        state = self.run_instruction(op, state)
        if state.why:
          # we can't process this block any further
          break
      if state.why in ["return", "yield"]:
        return_nodes.append(state.node)
      if not state.why and op.carry_on_to_next():
        frame.states[op.next] = state.merge_into(frame.states.get(op.next))
    self.pop_frame(frame)
    if not return_nodes:
      # Happens if all the function does is to throw an exception.
      # (E.g. "def f(): raise NoImplemented")
      # TODO(kramm): Return the exceptions, too.
      assert not frame.return_variable.bindings
      frame.return_variable.AddBinding(self.convert.unsolvable, [], node)
    else:
      node = self.join_cfg_nodes(return_nodes)
    return node, frame.return_variable

  reversable_operators = set([
      "__add__", "__sub__", "__mul__",
      "__div__", "__truediv__", "__floordiv__",
      "__mod__", "__divmod__", "__pow__",
      "__lshift__", "__rshift__", "__and__", "__or__", "__xor__"
  ])

  @staticmethod
  def reverse_operator_name(name):
    if name in VirtualMachine.reversable_operators:
      return "__r" + name[2:]
    return None

  def _try_reverse_operator(self, obj, rname, unreversed_results):
    """Whether we should attempt to call the given reverse operator.

    Args:
      obj: The object to (maybe) call the reverse operator on.
      rname: The name of the reverse operator.
      unreversed_results: Results from calling the unreversed operator.

    Returns:
      True if we should attempt the call.
    """
    if rname:
      for v in obj.data:
        # We do not want to look for a reverse operator on an Unsolvable or
        # Empty value, since it'll simply hand back an Unsolvable. If obj is
        # an Unknown and we already have results from the unreversed operator,
        # trying the reverse one would only cause us to lose precision. See
        # test_operators2.OperatorsWithAnyTests.testPow1 and
        # test_match.MatchTest.testMatchUnknownAgainstContainer for cases for
        # which omitting the Unknown check causes the inferred argument type
        # to revert to "Any".
        if (isinstance(v, (abstract.Unsolvable, abstract.Empty)) or
            (isinstance(v, abstract.Unknown) and unreversed_results)):
          return False
      return True
    return False

  def push_block(self, state, t, op, handler=None, level=None):
    if level is None:
      level = len(state.data_stack)
    return state.push_block(Block(t, op, handler, level))

  def push_frame(self, frame):
    self.frames.append(frame)
    self.frame = frame

  def pop_frame(self, frame):
    popped_frame = self.frames.pop()
    assert popped_frame == frame
    if self.frames:
      self.frame = self.frames[-1]
    else:
      self.frame = None

  def module_name(self):
    if self.frame.f_code.co_filename:
      return ".".join(re.sub(
          r"\.py$", "", self.frame.f_code.co_filename).split(os.sep)[-2:])
    else:
      return ""

  def log_opcode(self, op, state):
    """Write a multi-line log message, including backtrace and stack."""
    if not log.isEnabledFor(logging.INFO):
      return
    indent = " > " * (len(self.frames) - 1)
    stack_rep = repper(state.data_stack)
    block_stack_rep = repper(state.block_stack)
    module_name = self.module_name()
    if module_name:
      name = self.frame.f_code.co_name
      log.info("%s | index: %d, %r, module: %s line: %d",
               indent, op.index, name, module_name, op.line)
    else:
      log.info("%s | index: %d, line: %d",
               indent, op.index, op.line)
    log.info("%s | data_stack: %s", indent, stack_rep)
    log.info("%s | block_stack: %s", indent, block_stack_rep)
    log.info("%s | node: <%d>%s", indent, state.node.id, state.node.name)
    arg = op.pretty_arg if op.has_arg() else ""
    op = "%d: %s %s" % (op.index, op.name,
                        utils.maybe_truncate(arg, _TRUNCATE))
    log.info("%s %s", indent, op)

  def repper(self, s):
    return repr_obj.repr(s)

  # Operators

  def pop_slice_and_obj(self, state, count):
    """Pop a slice from the data stack. Used by slice opcodes (SLICE_0 etc.)."""
    start = 0
    end = None      # we will take this to mean end
    if count == 1:
      state, start = state.pop()
    elif count == 2:
      state, end = state.pop()
    elif count == 3:
      state, end = state.pop()
      state, start = state.pop()
    state, obj = state.pop()
    if end is None:
      # Note that Python only calls __len__ if we have a negative index, not if
      # we omit the index. Since we can't tell whether an index is negative
      # (it might be an abstract integer, or a union type), we just always
      # call __len__.
      state, f = self.load_attr(state, obj, "__len__")
      state, end = self.call_function_with_state(state, f, ())
    return state, self.convert.build_slice(state.node, start, end, 1), obj

  def store_slice(self, state, count):
    state, slice_obj, obj = self.pop_slice_and_obj(state, count)
    state, new_value = state.pop()
    state, f = self.load_attr(state, obj, "__setitem__")
    state, _ = self.call_function_with_state(state, f, (slice_obj, new_value))
    return state

  def delete_slice(self, state, count):
    state, slice_obj, obj = self.pop_slice_and_obj(state, count)
    return self._delete_item(state, obj, slice_obj)

  def get_slice(self, state, count):
    state, slice_obj, obj = self.pop_slice_and_obj(state, count)
    state, f = self.load_attr(state, obj, "__getitem__")
    state, ret = self.call_function_with_state(state, f, (slice_obj,))
    return state.push(ret)

  def do_raise(self, state, exc, cause):
    """Raise an exception. Used by byte_RAISE_VARARGS."""
    if exc is None:     # reraise
      exc_type, val, _ = state.last_exception
      if exc_type is None:
        return state.set_why("exception")
      else:
        return state.set_why("reraise")
    elif isinstance(exc, type):
      # As in `raise ValueError`
      exc_type = exc
      val = exc()       # Make an instance.
    elif isinstance(exc, BaseException):
      # As in `raise ValueError('foo')`
      exc_type = type(exc)
      val = exc
    else:
      return state

    # If you reach this point, you're guaranteed that
    # val is a valid exception instance and exc_type is its class.
    # Now do a similar thing for the cause, if present.
    if cause:
      if isinstance(cause, type):
        cause = cause()
      elif not isinstance(cause, BaseException):
        return state

      val.__cause__ = cause

    state.set_exception(exc_type, val, val.__traceback__)
    return state

  # Importing

  def join_variables(self, node, name, variables):
    return self.program.MergeVariables(node, name, variables)

  def make_class(self, node, name_var, bases, class_dict_var, cls_var):
    """Create a class with the name, bases and methods given.

    Args:
      node: The current CFG node.
      name_var: Class name.
      bases: Base classes.
      class_dict_var: Members of the class, as a Variable containing an
          abstract.Dict value.
      cls_var: The class's metaclass, if any.

    Returns:
      An instance of Class.
    """
    name = abstract.get_atomic_python_constant(name_var)
    log.info("Declaring class %s", name)
    try:
      class_dict = abstract.get_atomic_value(class_dict_var)
    except abstract.ConversionError:
      log.error("Error initializing class %r", name)
      return self.convert.create_new_unknown(node, name)
    for base in bases:
      if not any(isinstance(t, (abstract.Class, abstract.AMBIGUOUS_OR_EMPTY))
                 for t in base.data):
        self.errorlog.base_class_error(self.frame.current_opcode, node, base)
    if not bases:
      # Old style class.
      bases = [self.convert.oldstyleclass_type]
    if isinstance(class_dict, abstract.Unsolvable):
      # An unsolvable appears here if the vm hit maximum depth and gave up on
      # analyzing the class we're now building.
      var = self.convert.create_new_unsolvable(node, name)
    else:
      if cls_var is None:
        cls_var = class_dict.members.get("__metaclass__")
      if cls_var and all(v.data.full_name == "__builtin__.type"
                         for v in cls_var.bindings):
        cls_var = None
      try:
        val = abstract.InterpreterClass(
            name,
            bases,
            class_dict.members,
            cls_var,
            self)
      except pytd_utils.MROError as e:
        self.errorlog.mro_error(self.frame.current_opcode, name, e.mro_seqs)
        var = self.convert.create_new_unsolvable(node, "mro_error")
      else:
        var = self.program.NewVariable(name)
        var.AddBinding(val, class_dict_var.bindings, node)
    return var

  def _make_function(self, name, code, globs, defaults, kw_defaults,
                     closure=None, annotations=None, late_annotations=None):
    """Create a function or closure given the arguments."""
    if closure:
      closure = tuple(c for c in abstract.get_atomic_python_constant(closure))
      log.info("closure: %r", closure)
    if not name:
      if abstract.get_atomic_python_constant(code).co_name:
        name = abstract.get_atomic_python_constant(code).co_name
      else:
        name = "<lambda>"
    val = abstract.InterpreterFunction.make_function(
        name, code=abstract.get_atomic_python_constant(code),
        f_locals=self.frame.f_locals, f_globals=globs,
        defaults=defaults, kw_defaults=kw_defaults,
        closure=closure, annotations=annotations,
        late_annotations=late_annotations, vm=self)
    # TODO(ampere): What else needs to be an origin in this case? Probably stuff
    # in closure.
    var = self.program.NewVariable(name)
    var.AddBinding(val, code.bindings, self.root_cfg_node)
    if late_annotations:
      self.functions_with_late_annotations.append(val)
    return var

  def make_frame(self, node, code, callargs=None,
                 f_globals=None, f_locals=None, closure=None, new_locals=None):
    """Create a new frame object, using the given args, globals and locals."""
    if any(code is f.f_code for f in self.frames):
      log.info("Detected recursion in %s", code.co_name or code.co_filename)
      raise RecursionException()

    log.info("make_frame: callargs=%s, f_globals=[%s@%x], f_locals=[%s@%x]",
             self.repper(callargs),
             type(f_globals).__name__, id(f_globals),
             type(f_locals).__name__, id(f_locals))
    if f_globals is not None:
      f_globals = f_globals
      assert f_locals
    else:
      assert not self.frames
      assert f_locals is None
      # TODO(ampere): __name__, __doc__, __package__ below are not correct
      f_globals = f_locals = self.convert_locals_or_globals({
          "__builtins__": self.vmbuiltins,
          "__name__": "__main__",
          "__doc__": None,
          "__package__": None,
      })

    # Implement NEWLOCALS flag. See Objects/frameobject.c in CPython.
    # (Also allow to override this with a parameter, Python 3 doesn't always set
    #  it to the right value, e.g. for class-level code.)
    if code.co_flags & loadmarshal.CodeType.CO_NEWLOCALS or new_locals:
      f_locals = self.convert_locals_or_globals({}, "locals")

    return frame_state.Frame(node, self, code, f_globals, f_locals,
                             self.frame, callargs or {}, closure)

  def is_none(self, value):
    """Checks whether a value is considered to be "None".

    Important for stack values, which might be a symbolic None.

    Arguments:
      value: A typegraph.Variable.

    Returns:
      Whether the value is None. False if it isn't or if we don't know.
    """
    try:
      return value is None or abstract.get_atomic_python_constant(value) is None
    except abstract.ConversionError:
      return False

  def push_abstract_exception(self, state):
    tb = self.convert.build_list(state.node, [])
    value = self.convert.create_new_unknown(state.node, "value")
    exctype = self.convert.create_new_unknown(state.node, "exctype")
    return state.push(tb, value, exctype)

  def resume_frame(self, node, frame):
    frame.f_back = self.frame
    log.info("resume_frame: %r", frame)
    node, val = self.run_frame(frame, node)
    frame.f_back = None
    return node, val

  def compile_src(self, src, filename=None, mode="exec"):
    code = pyc.compile_src(
        src, python_version=self.python_version,
        python_exe=self.options.python_exe,
        filename=filename, mode=mode)
    return blocks.process_code(code)

  def run_bytecode(self, node, code, f_globals=None, f_locals=None):
    frame = self.make_frame(node, code, f_globals=f_globals, f_locals=f_locals)
    node, return_var = self.run_frame(frame, node)
    return node, frame.f_globals, frame.f_locals, return_var

  def preload_builtins(self, node):
    """Parse __builtin__.py and return the definitions as a globals dict."""
    if self.options.pybuiltins_filename:
      with open(self.options.pybuiltins_filename, "rb") as fi:
        src = fi.read()
    else:
      src = builtins.GetBuiltinsCode(self.python_version)
    builtins_code = self.compile_src(src)
    node, f_globals, f_locals, _ = self.run_bytecode(node, builtins_code)
    assert not self.frames
    # TODO(kramm): pytype doesn't support namespacing of the currently parsed
    # module, so add the module name manually.
    for definition in f_globals.members.values():
      for d in definition.data:
        d.module = "__builtin__"
    # at the outer layer, locals are the same as globals
    builtin_names = frozenset(f_globals.members)
    return node, f_globals, f_locals, builtin_names

  def run_program(self, src, filename, maximum_depth, run_builtins):
    """Run the code and return the CFG nodes.

    This function loads in the builtins and puts them ahead of `code`,
    so all the builtins are available when processing `code`.

    Args:
      src: The program source code.
      filename: The filename the source is from.
      maximum_depth: Maximum depth to follow call chains.
      run_builtins: Whether to preload the native Python builtins.
    Returns:
      A tuple (CFGNode, set) containing the last CFGNode of the program as
        well as all the top-level names defined by it.
    """
    self.maximum_depth = sys.maxint if maximum_depth is None else maximum_depth
    node = self.root_cfg_node.ConnectNew("builtins")
    if run_builtins:
      node, f_globals, f_locals, builtin_names = self.preload_builtins(node)
    else:
      node, f_globals, f_locals, builtin_names = node, None, None, frozenset()

    code = self.compile_src(src, filename=filename)

    node = node.ConnectNew("init")
    node, f_globals, _, _ = self.run_bytecode(node, code, f_globals, f_locals)
    logging.info("Done running bytecode, postprocessing globals")
    # Sort the members so that the official names of values that appear multiple
    # times don't depend on the dictionary's iteration order. When possible, we
    # pick the official name that corresponds to a value's actual name.
    global_members = sorted(
        f_globals.members.items(),
        key=lambda (name, var): (sum(name == v.name for v in var.data), name))
    for name, var in global_members:
      abstract.variable_set_official_name(var, name)
    for func in self.functions_with_late_annotations:
      self._eval_late_annotations(node, func, f_globals)
    assert not self.frames, "Frames left over!"
    log.info("Final node: <%d>%s", node.id, node.name)
    return node, f_globals.members, builtin_names

  def _eval_late_annotations(self, node, func, f_globals):
    """Resolves an instance of abstract.LateClass's expression."""
    for name, annot in func.signature.late_annotations.iteritems():
      # We don't chain node and f_globals as we want to remain in the context
      # where we've just finished evaluating the module. This would prevent
      # nasty things like:
      #
      # def f(a: "A = 1"):
      #   pass
      #
      # def g(b: "A"):
      #   pass
      #
      # Which should simply complain at both annotations that 'A' is not defined
      # in both function annotations. Chaining would cause 'b' in 'g' to yield a
      # different error message.
      code = self.compile_src(annot.expr, mode="eval")
      new_locals = self.convert_locals_or_globals({}, "locals")
      _, _, _, ret = self.run_bytecode(
          node, code, f_globals, new_locals)
      if len(ret.data) == 1:
        x = ret.data[0]
        if x.cls and x.cls.data == self.convert.none_type.data:
          resolved = self.convert.none_type.data[0]
        else:
          resolved = x
      else:
        self.errorlog.invalid_annotation(annot.opcode, annot.name)
        resolved = self.convert.unsolvable
      func.signature.set_annotation(name, resolved)

  def call_binary_operator(self, state, name, x, y, report_errors=False):
    """Map a binary operator to "magic methods" (__add__ etc.)."""
    results = []
    log.debug("Calling binary operator %s", name)
    state, attr = self.load_attr_noerror(state, x, name)
    if attr is None:
      log.info("Failed to find %s on %r", name, x)
    else:
      state, ret = self.call_function_with_state(state, attr, (y,),
                                                 fallback_to_unsolvable=False)
      results.append(ret)
    rname = self.reverse_operator_name(name)
    if self._try_reverse_operator(y, rname, results):
      state, attr = self.load_attr_noerror(state, y, rname)
      if attr is None:
        log.debug("No reverse operator %s on %r", rname, y)
      else:
        state, ret = self.call_function_with_state(state, attr, (x,),
                                                   fallback_to_unsolvable=False)
        results.append(ret)
    result = self.join_variables(state.node, name, results)
    log.debug("Result: %r %r", result, result.data)
    if not result.bindings and report_errors:
      self.errorlog.unsupported_operands(self.frame.current_opcode, state.node,
                                         name, x, y)
      result.AddBinding(self.convert.unsolvable, [], state.node)
    return state, result

  def call_inplace_operator(self, state, iname, x, y):
    """Try to call a method like __iadd__, possibly fall back to __add__."""
    state, attr = self.load_attr_noerror(state, x, iname)
    if attr is None:
      log.info("No inplace operator %s on %r", iname, x)
      name = iname.replace("i", "", 1)  # __iadd__ -> __add__ etc.
      state, ret = self.call_binary_operator(
          state, name, x, y, report_errors=True)
    else:
      # TODO(kramm): If x is a Variable with distinct types, both __add__
      # and __iadd__ might happen.
      state, ret = self.call_function_with_state(state, attr, (y,),
                                                 fallback_to_unsolvable=False)
    return state, ret

  def binary_operator(self, state, name, report_errors=True):
    state, (x, y) = state.popn(2)
    state, ret = self.call_binary_operator(
        state, name, x, y, report_errors=report_errors)
    return state.push(ret)

  def inplace_operator(self, state, name):
    state, (x, y) = state.popn(2)
    state, ret = self.call_inplace_operator(state, name, x, y)
    return state.push(ret)

  def trace_unknown(self, *args):
    """Fired whenever we create a variable containing 'Unknown'."""
    return NotImplemented

  def trace_call(self, *args):
    """Fired whenever we call a builtin using unknown parameters."""
    return NotImplemented

  def call_function_with_state(self, state, funcu, posargs, namedargs=None,
                               starargs=None, starstarargs=None,
                               fallback_to_unsolvable=True):
    assert starargs is None or isinstance(starargs, typegraph.Variable)
    assert starstarargs is None or isinstance(starstarargs, typegraph.Variable)
    node, ret = self.call_function(state.node, funcu, abstract.FunctionArgs(
        posargs=posargs, namedargs=namedargs, starargs=starargs,
        starstarargs=starstarargs), fallback_to_unsolvable, state.condition)
    return state.change_cfg_node(node), ret

  def call_function(self, node, funcu, args, fallback_to_unsolvable=True,
                    condition=None):
    """Call a function.

    Args:
      node: The current CFG node.
      funcu: A variable of the possible functions to call.
      args: The arguments to pass. See abstract.FunctionArgs.
      fallback_to_unsolvable: If the function call fails, create an unknown.
      condition: The currently active if condition.
    Returns:
      A tuple (CFGNode, Variable). The Variable is the return value.
    """
    assert funcu.bindings
    result = self.program.NewVariable("<return:%s>" % funcu.name)
    nodes = []
    error = None
    for funcv in funcu.bindings:
      func = funcv.data
      assert isinstance(func, abstract.AtomicAbstractValue), type(func)
      try:
        new_node, one_result = func.call(node, funcv, args, condition)
      except (abstract.FailedFunctionCall, utils.TooComplexError) as e:
        error = error or e
      else:
        # This is similar to PasteVariable() except that it adds funcv as
        # an additional source.  If this is a common occurence then perhaps
        # we should add an optional arg to PasteVariable().
        for binding in one_result.bindings:
          copy = result.AddBinding(binding.data)
          copy.AddOrigin(new_node, {binding, funcv})
        nodes.append(new_node)
    if nodes:
      node = self.join_cfg_nodes(nodes)
      if not result.bindings:
        result.AddBinding(self.convert.unsolvable, [], node)
      return node, result
    else:
      if fallback_to_unsolvable:
        if isinstance(error, abstract.FailedFunctionCall):
          self.errorlog.invalid_function_call(self.frame.current_opcode, error)
        else:
          # This error isn't useful to a user, so we don't log it.
          assert isinstance(error, utils.TooComplexError)
        return node, self.convert.create_new_unsolvable(node, "failed call")
      else:
        # We were called by something that ignores errors, so don't report
        # the failed call.
        return node, result

  def call_function_from_stack(self, state, num, starargs, starstarargs):
    """Pop arguments for a function and call it."""
    num_kw, num_pos = divmod(num, 256)

    # TODO(kramm): Can we omit creating this Dict if num_kw=0?
    namedargs = abstract.Dict("kwargs", self, state.node)
    for _ in range(num_kw):
      state, (key, val) = state.popn(2)
      namedargs.setitem(state.node, key, val)
    state, posargs = state.popn(num_pos)

    state, func = state.pop()
    state, ret = self.call_function_with_state(
        state, func, posargs, namedargs, starargs, starstarargs)
    state = state.push(ret)
    return state

  def load_constant(self, value):
    """Converts a Python value to an abstract value."""
    return self.convert.convert_constant(type(value).__name__, value)

  def get_globals_dict(self):
    """Get a real python dict of the globals."""
    return self.frame.f_globals

  def load_from(self, state, store, name):
    node = state.node
    node, attr = self.attribute_handler.get_attribute(
        node, store, name, condition=state.condition)
    assert isinstance(node, typegraph.CFGNode)
    if not attr:
      raise KeyError(name)
    state = state.change_cfg_node(node)
    return state, attr

  def load_local(self, state, name):
    """Called when a local is loaded onto the stack.

    Uses the name to retrieve the value from the current locals().

    Args:
      state: The current VM state.
      name: Name of the local

    Returns:
      The value (typegraph.Variable)
    """
    return self.load_from(state, self.frame.f_locals, name)

  def load_global(self, state, name):
    return self.load_from(state, self.frame.f_globals, name)

  def load_special_builtin(self, name):
    if name == "__any_object__":
      # For type_inferencer/tests/test_pgms/*.py, must be a new object
      # each time.
      return abstract.Unknown(self)
    else:
      return self.special_builtins.get(name)

  def load_builtin(self, state, name):
    if name == "__undefined__":
      # For values that don't exist. (Unlike None, which is a valid object)
      return state, self.convert.empty_type
    special = self.load_special_builtin(name)
    if special:
      return state, special.to_variable(state.node, name)
    else:
      return self.load_from(state, self.frame.f_builtins, name)

  def store_local(self, state, name, value):
    """Called when a local is written."""
    assert isinstance(value, typegraph.Variable), (name, repr(value))
    node = self.attribute_handler.set_attribute(
        state.node, self.frame.f_locals, name, value)
    return state.change_cfg_node(node)

  def store_global(self, state, name, value):
    """Same as store_local except for globals."""
    assert isinstance(value, typegraph.Variable)
    node = self.attribute_handler.set_attribute(
        state.node, self.frame.f_globals, name, value)
    return state.change_cfg_node(node)

  def del_local(self, name):
    """Called when a local is deleted."""
    # TODO(ampere): Implement locals removal or decide not to.
    log.warning("Local variable removal does not actually do "
                "anything in the abstract interpreter")

  def del_global(self, name):
    """Called when a global is deleted."""
    log.warning("Global variable removal does not actually do "
                "anything in the abstract interpreter")

  def _retrieve_attr(self, state, obj, attr):
    """Load an attribute from an object."""
    assert isinstance(obj, typegraph.Variable), obj
    # Resolve the value independently for each value of obj
    result = self.program.NewVariable(str(attr))
    log.debug("getting attr %s from %r", attr, obj)
    node = state.node
    nodes = []
    for val in obj.Bindings(node):
      try:
        node2, attr_var = self.attribute_handler.get_attribute_generic(
            node, val.data, attr, val, condition=state.condition)
      except self.convert.TypeParameterError as e:
        self.errorlog.type_param_error(
            self.frame.current_opcode, obj, attr, e.type_param_name)
        node2, attr_var = node, self.convert.unsolvable.to_variable(node, attr)
      if attr_var is None or not attr_var.bindings:
        log.debug("No %s on %s", attr, val.data.__class__)
        continue
      log.debug("got choice for attr %s from %r of %r (0x%x): %r", attr, obj,
                val.data, id(val.data), attr_var)
      if not attr_var:
        continue
      result.PasteVariable(attr_var, node2)
      nodes.append(node2)
    if nodes:
      return self.join_cfg_nodes(nodes), result
    else:
      return node, None

  def _is_only_none(self, node, obj):
    # TODO(kramm): Report an error for *any* None, as opposed to *all* None?
    has_none = True
    for x in obj.Data(node):
      if getattr(x, "cls", False) and x.cls.data == self.convert.none_type.data:
        has_none = True
      else:
        return False
    return has_none

  def _delete_item(self, state, obj, arg):
    state, f = self.load_attr(state, obj, "__delitem__")
    state, _ = self.call_function_with_state(state, f, (arg,))
    return state

  def load_attr(self, state, obj, attr):
    node, result = self._retrieve_attr(state, obj, attr)
    if result is None:
      if obj.bindings:
        if self._is_only_none(state.node, obj):
          self.errorlog.none_attr(self.frame.current_opcode, attr)
        else:
          self.errorlog.attribute_error(self.frame.current_opcode, obj, attr)
      result = self.convert.create_new_unsolvable(node, "bad attr")
    return state.change_cfg_node(node), result

  def load_attr_noerror(self, state, obj, attr):
    node, result = self._retrieve_attr(state, obj, attr)
    return state.change_cfg_node(node), result

  def store_attr(self, state, obj, attr, value):
    """Set an attribute on an object."""
    assert isinstance(obj, typegraph.Variable)
    assert isinstance(attr, str)
    assert isinstance(value, typegraph.Variable)
    if not obj.bindings:
      log.info("Ignoring setattr on %r", obj)
      return state
    nodes = []
    for val in obj.bindings:
      # TODO(kramm): Check whether val.data is a descriptor (i.e. has "__set__")
      nodes.append(self.attribute_handler.set_attribute(
          state.node, val.data, attr, value))
    return state.change_cfg_node(
        self.join_cfg_nodes(nodes))

  def del_attr(self, state, obj, attr):
    """Delete an attribute."""
    # TODO(kramm): Store abstract.Nothing
    log.warning("Attribute removal does not actually do "
                "anything in the abstract interpreter")
    return state

  def push_last_exception(self, state):
    log.info("Pushing exception %r", state.exception)
    exctype, value, tb = state.exception
    return state.push(tb, value, exctype)

  def del_subscr(self, state, obj, subscr):
    return self._delete_item(state, obj, subscr)

  def pop_varargs(self, state):
    """Retrieve a varargs tuple from the stack. Used by call_function."""
    return state.pop()

  def pop_kwargs(self, state):
    """Retrieve a kwargs dictionary from the stack. Used by call_function."""
    return state.pop()

  def convert_locals_or_globals(self, d, name="globals"):
    return abstract.LazyAbstractOrConcreteValue(
        name, d, d, self.convert.maybe_convert_constant, self)

  # TODO(kramm): memoize
  def import_module(self, name, level):
    """Import the module and return the module object.

    Args:
      name: Name of the module. E.g. "sys".
      level: Specifies whether to use absolute or relative imports.
        -1: (Python <= 3.1) "Normal" import. Try both relative and absolute.
         0: Absolute import.
         1: "from . import abc"
         2: "from .. import abc"
         etc.
    Returns:
      An instance of abstract.Module or None if we couldn't find the module.
    """
    if name:
      if level <= 0:
        assert level in [-1, 0]
        if level == -1 and self.loader.base_module:
          # Python 2 tries relative imports first.
          ast = (self.loader.import_relative_name(name) or
                 self.loader.import_name(name))
        else:
          ast = self.loader.import_name(name)
      else:
        # "from .x import *"
        base = self.loader.import_relative(level)
        if base is None:
          return None
        ast = self.loader.import_name(base.name + "." + name)
    else:
      assert level > 0
      ast = self.loader.import_relative(level)
    if ast:
      module = self.convert.construct_constant_from_value(
          ast.name, ast, subst={}, node=self.root_cfg_node)
      if level <= 0 and name == "typing":
        # use a special overlay for stdlib/typing.pytd
        return typing.TypingOverlay(self, self.root_cfg_node, module)
      else:
        return module
    else:
      return None

  def print_item(self, item, to=None):
    # We don't need do anything here, since Python's print function accepts
    # any type. (We could exercise the __str__ method on item - but every
    # object has a __str__, so we wouldn't learn anything from that.)
    pass

  def print_newline(self, to=None):
    pass

  def unary_operator(self, state, name):
    state, x = state.pop()
    state, method = self.load_attr(state, x, name)  # E.g. __not__
    state, result = self.call_function_with_state(state, method, ())
    state = state.push(result)
    return state

  def expand_bool_result(self, node, left, right, name, maybe_predicate):
    result = self.program.NewVariable(name)
    for x in left.Bindings(node):
      for y in right.Bindings(node):
        pyval = maybe_predicate(x.data, y.data)
        result.AddBinding(self.convert.bool_values[pyval],
                          source_set=(x, y), where=node)

    return result

  def byte_UNARY_NOT(self, state, op):
    """Implement the UNARY_NOT bytecode."""
    state, var = state.pop()
    bindings = var.Bindings(state.node)
    true_bindings = [b for b in bindings if b.data.compatible_with(True)]
    false_bindings = [b for b in bindings if b.data.compatible_with(False)]
    if len(true_bindings) == len(false_bindings) == len(bindings):
      # No useful information from bindings, use a generic bool value.
      # This is merely an optimization rather than building separate True/False
      # values each with the same bindings as var.
      result = self.convert.build_bool(state.node)
    else:
      # Build a result with True/False values, each bound to appropriate
      # bindings.  Note that bindings that are True get attached to a result
      # that is False and vice versa because this is a NOT operation.
      result = self.program.NewVariable("unary_not")
      for b in true_bindings:
        result.AddBinding(self.convert.bool_values[False],
                          source_set=(b,), where=state.node)
      for b in false_bindings:
        result.AddBinding(self.convert.bool_values[True],
                          source_set=(b,), where=state.node)
    state = state.push(result)
    return state

  def byte_UNARY_CONVERT(self, state, op):
    return self.unary_operator(state, "__repr__")

  def byte_UNARY_NEGATIVE(self, state, op):
    return self.unary_operator(state, "__neg__")

  def byte_UNARY_POSITIVE(self, state, op):
    return self.unary_operator(state, "__pos__")

  def byte_UNARY_INVERT(self, state, op):
    return self.unary_operator(state, "__invert__")

  def byte_BINARY_ADD(self, state, op):
    return self.binary_operator(state, "__add__")

  def byte_BINARY_SUBTRACT(self, state, op):
    return self.binary_operator(state, "__sub__")

  def byte_BINARY_DIVIDE(self, state, op):
    return self.binary_operator(state, "__div__")

  def byte_BINARY_MULTIPLY(self, state, op):
    return self.binary_operator(state, "__mul__")

  def byte_BINARY_MODULO(self, state, op):
    return self.binary_operator(state, "__mod__")

  def byte_BINARY_LSHIFT(self, state, op):
    return self.binary_operator(state, "__lshift__")

  def byte_BINARY_RSHIFT(self, state, op):
    return self.binary_operator(state, "__rshift__")

  def byte_BINARY_AND(self, state, op):
    return self.binary_operator(state, "__and__")

  def byte_BINARY_XOR(self, state, op):
    return self.binary_operator(state, "__xor__")

  def byte_BINARY_OR(self, state, op):
    return self.binary_operator(state, "__or__")

  def byte_BINARY_FLOOR_DIVIDE(self, state, op):
    return self.binary_operator(state, "__floordiv__")

  def byte_BINARY_TRUE_DIVIDE(self, state, op):
    return self.binary_operator(state, "__truediv__")

  def byte_BINARY_POWER(self, state, op):
    return self.binary_operator(state, "__pow__")

  def byte_BINARY_SUBSCR(self, state, op):
    state = self.binary_operator(state, "__getitem__", report_errors=False)
    if state.top().bindings:
      return state
    else:
      # This typically happens if a dictionary is being filled by code we just
      # haven't analyzed yet. So don't report an error.
      state.top().AddBinding(self.convert.unsolvable,
                             source_set=[], where=state.node)
      return state

  def byte_INPLACE_ADD(self, state, op):
    return self.inplace_operator(state, "__iadd__")

  def byte_INPLACE_SUBTRACT(self, state, op):
    return self.inplace_operator(state, "__isub__")

  def byte_INPLACE_MULTIPLY(self, state, op):
    return self.inplace_operator(state, "__imul__")

  def byte_INPLACE_DIVIDE(self, state, op):
    return self.inplace_operator(state, "__idiv__")

  def byte_INPLACE_MODULO(self, state, op):
    return self.inplace_operator(state, "__imod__")

  def byte_INPLACE_POWER(self, state, op):
    return self.inplace_operator(state, "__ipow__")

  def byte_INPLACE_LSHIFT(self, state, op):
    return self.inplace_operator(state, "__ilshift__")

  def byte_INPLACE_RSHIFT(self, state, op):
    return self.inplace_operator(state, "__irshift__")

  def byte_INPLACE_AND(self, state, op):
    return self.inplace_operator(state, "__iand__")

  def byte_INPLACE_XOR(self, state, op):
    return self.inplace_operator(state, "__ixor__")

  def byte_INPLACE_OR(self, state, op):
    return self.inplace_operator(state, "__ior__")

  def byte_INPLACE_FLOOR_DIVIDE(self, state, op):
    return self.inplace_operator(state, "__ifloordiv__")

  def byte_INPLACE_TRUE_DIVIDE(self, state, op):
    return self.inplace_operator(state, "__itruediv__")

  def byte_LOAD_CONST(self, state, op):
    const = self.frame.f_code.co_consts[op.arg]
    return state.push(self.load_constant(const))

  def byte_POP_TOP(self, state, op):
    return state.pop_and_discard()

  def byte_DUP_TOP(self, state, op):
    return state.push(state.top())

  def byte_DUP_TOPX(self, state, op):
    state, items = state.popn(op.arg)
    state = state.push(*items)
    state = state.push(*items)
    return state

  def byte_DUP_TOP_TWO(self, state, op):
    # Py3 only
    state, (a, b) = state.popn(2)
    return state.push(a, b, a, b)

  def byte_ROT_TWO(self, state, op):
    state, (a, b) = state.popn(2)
    return state.push(b, a)

  def byte_ROT_THREE(self, state, op):
    state, (a, b, c) = state.popn(3)
    return state.push(c, a, b)

  def byte_ROT_FOUR(self, state, op):
    state, (a, b, c, d) = state.popn(4)
    return state.push(d, a, b, c)

  def byte_LOAD_NAME(self, state, op):
    """Load a name. Can be a local, global, or builtin."""
    name = self.frame.f_code.co_names[op.arg]
    try:
      state, val = self.load_local(state, name)
    except KeyError:
      try:
        state, val = self.load_global(state, name)
      except KeyError:
        try:
          state, val = self.load_builtin(state, name)
        except KeyError:
          if not self.has_unknown_wildcard_imports:
            self.errorlog.name_error(self.frame.current_opcode, name)
          return state.push(
              self.convert.create_new_unsolvable(state.node, name))
    return state.push(val)

  def byte_STORE_NAME(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    state, value = state.pop()
    state = self.store_local(state, name, value)
    return state.forward_cfg_node()

  def byte_DELETE_NAME(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    self.del_local(name)
    return state

  def byte_LOAD_FAST(self, state, op):
    """Load a local. Unlike LOAD_NAME, it doesn't fall back to globals."""
    name = self.frame.f_code.co_varnames[op.arg]
    try:
      state, val = self.load_local(state, name)
    except KeyError:
      self.errorlog.name_error(self.frame.current_opcode, name)
      val = self.convert.create_new_unsolvable(state.node, name)
    return state.push(val)

  def byte_STORE_FAST(self, state, op):
    name = self.frame.f_code.co_varnames[op.arg]
    state, value = state.pop()
    state = state.forward_cfg_node()
    state = self.store_local(state, name, value)
    return state

  def byte_DELETE_FAST(self, state, op):
    name = self.frame.f_code.co_varnames[op.arg]
    self.del_local(name)
    return state

  def byte_LOAD_GLOBAL(self, state, op):
    """Load a global variable, or fall back to trying to load a builtin."""
    name = self.frame.f_code.co_names[op.arg]
    try:
      state, val = self.load_global(state, name)
    except KeyError:
      try:
        state, val = self.load_builtin(state, name)
      except KeyError:
        self.errorlog.name_error(self.frame.current_opcode, name)
        return state.push(self.convert.create_new_unsolvable(state.node, name))
    return state.push(val)

  def byte_STORE_GLOBAL(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    state, value = state.pop()
    state = self.store_global(state, name, value)
    return state

  def byte_DELETE_GLOBAL(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    self.del_global(name)
    return state

  def byte_LOAD_CLOSURE(self, state, op):
    """Used to generate the 'closure' tuple for MAKE_CLOSURE.

    Each entry in that tuple is typically retrieved using LOAD_CLOSURE.

    Args:
      state: The current VM state.
      op: The opcode. op.arg is the index of a "cell variable": This corresponds
        to an entry in co_cellvars or co_freevars and is a variable that's bound
        into a closure.
    Returns:
      A new state.
    """
    return state.push(self.frame.cells[op.arg])

  def byte_LOAD_DEREF(self, state, op):
    """Retrieves a value out of a cell."""
    # Since we're working on typegraph.Variable, we don't need to dereference.
    return state.push(self.frame.cells[op.arg])

  def byte_STORE_DEREF(self, state, op):
    """Stores a value in a closure cell."""
    state, value = state.pop()
    assert isinstance(value, typegraph.Variable)
    self.frame.cells[op.arg].PasteVariable(value, state.node)
    return state

  def byte_LOAD_LOCALS(self, state, op):
    log.debug("Returning locals: %r", self.frame.f_locals)
    locals_dict = self.convert.maybe_convert_constant(
        "locals", self.frame.f_locals)
    return state.push(locals_dict)

  def byte_COMPARE_OP(self, state, op):
    """Pops and compares the top two stack values and pushes a boolean."""
    state, (x, y) = state.popn(2)
    # Explicit, redundant, switch statement, to make it easier to address the
    # behavior of individual compare operations:
    if op.arg == slots.CMP_LT:
      state, ret = self.call_binary_operator(state, "__lt__", x, y)
    elif op.arg == slots.CMP_LE:
      state, ret = self.call_binary_operator(state, "__le__", x, y)
    elif op.arg == slots.CMP_EQ:
      state, ret = self.call_binary_operator(state, "__eq__", x, y)
    elif op.arg == slots.CMP_NE:
      state, ret = self.call_binary_operator(state, "__ne__", x, y)
    elif op.arg == slots.CMP_GT:
      state, ret = self.call_binary_operator(state, "__gt__", x, y)
    elif op.arg == slots.CMP_GE:
      state, ret = self.call_binary_operator(state, "__ge__", x, y)
    elif op.arg == slots.CMP_IS:
      ret = self.expand_bool_result(state.node, x, y,
                                    "is_cmp", frame_state.is_cmp)
    elif op.arg == slots.CMP_IS_NOT:
      ret = self.expand_bool_result(state.node, x, y,
                                    "is_not_cmp", frame_state.is_not_cmp)
    elif op.arg == slots.CMP_NOT_IN:
      ret = self.convert.build_bool(state.node)
    elif op.arg == slots.CMP_IN:
      ret = self.convert.build_bool(state.node)
    elif op.arg == slots.CMP_EXC_MATCH:
      ret = self.convert.build_bool(state.node)
    else:
      raise VirtualMachineError("Invalid argument to COMPARE_OP: %d", op.arg)
    if not ret.bindings and op.arg in slots.CMP_ALWAYS_SUPPORTED:
      # Some comparison operations are always supported.
      # (https://docs.python.org/2/library/stdtypes.html#comparisons)
      ret.AddBinding(
          self.convert.primitive_class_instances[bool], [], state.node)
    return state.push(ret)

  def byte_LOAD_ATTR(self, state, op):
    """Pop an object, and retrieve a named attribute from it."""
    name = self.frame.f_code.co_names[op.arg]
    state, obj = state.pop()
    log.debug("LOAD_ATTR: %r %r", obj, name)
    state, val = self.load_attr(state, obj, name)
    return state.push(val)

  def byte_STORE_ATTR(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    state, (val, obj) = state.popn(2)
    state = state.forward_cfg_node()
    state = self.store_attr(state, obj, name, val)
    return state

  def byte_DELETE_ATTR(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    state, obj = state.pop()
    return self.del_attr(state, obj, name)

  def store_subscr(self, state, obj, key, val):
    state, f = self.load_attr(state, obj, "__setitem__")
    state, _ = self.call_function_with_state(state, f, (key, val))
    return state

  def byte_STORE_SUBSCR(self, state, op):
    state, (val, obj, subscr) = state.popn(3)
    state = state.forward_cfg_node()
    state = self.store_subscr(state, obj, subscr, val)
    return state

  def byte_DELETE_SUBSCR(self, state, op):
    state, (obj, subscr) = state.popn(2)
    return self.del_subscr(state, obj, subscr)

  def byte_BUILD_TUPLE(self, state, op):
    count = op.arg
    state, elts = state.popn(count)
    return state.push(self.convert.build_tuple(state.node, elts))

  def byte_BUILD_LIST(self, state, op):
    count = op.arg
    state, elts = state.popn(count)
    return state.push(self.convert.build_list(state.node, elts))

  def byte_BUILD_SET(self, state, op):
    count = op.arg
    state, elts = state.popn(count)
    return state.push(self.convert.build_set(state.node, elts))

  def byte_BUILD_MAP(self, state, op):
    # op.arg (size) is ignored.
    return state.push(self.convert.build_map(state.node))

  def byte_STORE_MAP(self, state, op):
    state, (the_map, val, key) = state.popn(3)
    state = self.store_subscr(state, the_map, key, val)
    return state.push(the_map)

  def byte_UNPACK_SEQUENCE(self, state, op):
    """Pops a tuple (or other iterable) and pushes it onto the VM's stack."""
    state, seq = state.pop()
    state, f = self.load_attr(state, seq, "__iter__")
    state, itr = self.call_function_with_state(state, f, ())
    values = []
    for _ in range(op.arg):
      # TODO(ampere): Fix for python 3
      state, f = self.load_attr(state, itr, "next")
      state, result = self.call_function_with_state(state, f, ())
      values.append(result)
    for value in reversed(values):
      state = state.push(value)
    return state

  def byte_BUILD_SLICE(self, state, op):
    if op.arg == 2:
      state, (x, y) = state.popn(2)
      return state.push(self.convert.build_slice(state.node, x, y))
    elif op.arg == 3:
      state, (x, y, z) = state.popn(3)
      return state.push(self.convert.build_slice(state.node, x, y, z))
    else:       # pragma: no cover
      raise VirtualMachineError("Strange BUILD_SLICE count: %r" % op.arg)

  def byte_LIST_APPEND(self, state, op):
    # Used by the compiler e.g. for [x for x in ...]
    count = op.arg
    state, val = state.pop()
    the_list = state.peek(count)
    state, f = self.load_attr(state, the_list, "append")
    state, _ = self.call_function_with_state(state, f, (val,))
    return state

  def byte_SET_ADD(self, state, op):
    # Used by the compiler e.g. for {x for x in ...}
    count = op.arg
    state, val = state.pop()
    the_set = state.peek(count)
    state, f = self.load_attr(state, the_set, "add")
    state, _ = self.call_function_with_state(state, f, (val,))
    return state

  def byte_MAP_ADD(self, state, op):
    # Used by the compiler e.g. for {x, y for x, y in ...}
    count = op.arg
    state, (val, key) = state.popn(2)
    the_map = state.peek(count)
    state, f = self.load_attr(state, the_map, "__setitem__")
    state, _ = self.call_function_with_state(state, f, (key, val))
    return state

  def byte_PRINT_EXPR(self, state, op):
    # Only used in the interactive interpreter, not in modules.
    return state.pop_and_discard()

  def byte_PRINT_ITEM(self, state, op):
    state, item = state.pop()
    self.print_item(item)
    return state

  def byte_PRINT_ITEM_TO(self, state, op):
    state, to = state.pop()
    state, item = state.pop()
    self.print_item(item, to)
    return state

  def byte_PRINT_NEWLINE(self, state, op):
    self.print_newline()
    return state

  def byte_PRINT_NEWLINE_TO(self, state, op):
    state, to = state.pop()
    self.print_newline(to)
    return state

  def _jump_if(self, state, op, pop=False, jump_if=False, or_pop=False):
    """Implementation of various _JUMP_IF bytecodes.

    Args:
      state: Initial FrameState.
      op: An opcode.
      pop: True if a value is popped off the stack regardless.
      jump_if: True or False (indicates which value will lead to a jump).
      or_pop: True if a value is popped off the stack only when the jump is
          not taken.
    Returns:
      The new FrameState.
    """
    assert not (pop and or_pop)
    # Determine the conditions.  Assume jump-if-true, then swap conditions
    # if necessary.
    if pop:
      state, value = state.pop()
    else:
      value = state.top()
    jump, normal = frame_state.split_conditions(
        state.node, state.condition, value)
    if not jump_if:
      jump, normal = normal, jump
    # Jump.
    if jump is not frame_state.UNSATISFIABLE:
      self.store_jump(op.target, state.forward_cfg_node().set_condition(jump))
    # Don't jump.
    if or_pop:
      state = state.pop_and_discard()
    if normal is frame_state.UNSATISFIABLE:
      return state.set_why("unsatisfiable")
    else:
      return state.forward_cfg_node().set_condition(normal)

  def byte_JUMP_IF_TRUE_OR_POP(self, state, op):
    return self._jump_if(state, op, jump_if=True, or_pop=True)

  def byte_JUMP_IF_FALSE_OR_POP(self, state, op):
    return self._jump_if(state, op, jump_if=False, or_pop=True)

  def byte_JUMP_IF_TRUE(self, state, op):  # Not in py2.7
    return self._jump_if(state, op, jump_if=True)

  def byte_JUMP_IF_FALSE(self, state, op):  # Not in py2.7
    return self._jump_if(state, op, jump_if=False)

  def byte_POP_JUMP_IF_TRUE(self, state, op):
    return self._jump_if(state, op, pop=True, jump_if=True)

  def byte_POP_JUMP_IF_FALSE(self, state, op):
    return self._jump_if(state, op, pop=True, jump_if=False)

  def byte_JUMP_FORWARD(self, state, op):
    self.store_jump(op.target, state.forward_cfg_node())
    return state

  def byte_JUMP_ABSOLUTE(self, state, op):
    self.store_jump(op.target, state.forward_cfg_node())
    return state

  def byte_SETUP_LOOP(self, state, op):
    return self.push_block(state, "loop", op, op.target)

  def byte_GET_ITER(self, state, op):
    """Get the iterator for an object."""
    pre_state, seq = state.pop()
    state, func = self.load_attr_noerror(pre_state, seq, "__iter__")
    if func:
      # Call __iter__().
      state, it = self.call_function_with_state(state, func, ())
    else:
      state, func = self.load_attr_noerror(pre_state, seq, "__getitem__")
      if func:
        # TODO(dbaum): Consider delaying the call to __getitem__ until
        # the iterator's next() is called.  That would more closely match
        # actual execution at the cost of making the code and Iterator class
        # a little more complicated.

        # Call __getitem__(int).
        key = abstract.Instance(self.convert.int_type, self, state.node)
        state, item = self.call_function_with_state(state, func, (
            key.to_variable(state.node, "key"),))
        # Create a new iterator from the returned value.
        it = abstract.Iterator(self, item, state.node).to_variable(
            state.node, "it")
      else:
        # Cannot iterate this object.
        if seq.bindings:
          self.errorlog.attribute_error(
              self.frame.current_opcode, seq, "__iter__")
        it = self.convert.create_new_unsolvable(state.node, "bad attr")
    # Push the iterator onto the stack and return.
    return state.push(it)

  def store_jump(self, target, state):
    self.frame.states[target] = state.merge_into(self.frame.states.get(target))

  def byte_FOR_ITER(self, state, op):
    self.store_jump(op.target, state.pop_and_discard())
    state, f = self.load_attr(state, state.top(), "next")
    state = state.push(f)
    return self.call_function_from_stack(state, 0, None, None)

  def _revert_state_to(self, state, name):
    while state.block_stack[-1].type != name:
      state, block = state.pop_block()
      while block.level < len(state.data_stack):
        state = state.pop_and_discard()
    return state

  def byte_BREAK_LOOP(self, state, op):
    new_state, block = self._revert_state_to(state, "loop").pop_block()
    while block.level < len(new_state.data_stack):
      new_state = new_state.pop_and_discard()
    self.store_jump(op.block_target, new_state)
    return state

  def byte_CONTINUE_LOOP(self, state, op):
    new_state = self._revert_state_to(state, "loop")
    self.store_jump(op.target, new_state)
    return state

  def byte_SETUP_EXCEPT(self, state, op):
    # Assume that it's possible to throw the exception at the first
    # instruction of the code:
    self.store_jump(op.target, self.push_abstract_exception(state))
    return self.push_block(state, "setup-except", op, op.target)

  def byte_SETUP_FINALLY(self, state, op):
    # Emulate finally by connecting the try to the finally block (with
    # empty reason/why/continuation):
    self.store_jump(op.target, state.push(self.convert.build_none(state.node)))
    return self.push_block(state, "finally", op, op.target)

  def byte_POP_BLOCK(self, state, op):
    state, _ = state.pop_block()
    return state

  def byte_RAISE_VARARGS_PY2(self, state, op):
    """Raise an exception (Python 2 version)."""
    # NOTE: the dis docs are completely wrong about the order of the
    # operands on the stack!
    argc = op.arg
    exctype = val = tb = None
    if argc == 0:
      if state.exception is None:
        raise exceptions.ByteCodeTypeError(
            "exceptions must be old-style classes "
            "or derived from BaseException, not NoneType")
      exctype, val, tb = state.exception
    elif argc == 1:
      state, exctype = state.pop()
    elif argc == 2:
      state, val = state.pop()
      state, exctype = state.pop()
    elif argc == 3:
      state, tb = state.pop()
      state, val = state.pop()
      state, exctype = state.pop()
    # There are a number of forms of "raise", normalize them somewhat.
    if isinstance(exctype, BaseException):
      val = exctype
      exctype = type(val)
    state = state.set_exception(exctype, val, tb)
    if tb:
      return state.set_why("reraise")
    else:
      return state.set_why("exception")

  def byte_RAISE_VARARGS_PY3(self, state, op):
    """Raise an exception (Python 3 version)."""
    argc = op.arg
    cause = exc = None
    if argc == 2:
      state, cause = state.pop()
      state, exc = state.pop()
    elif argc == 1:
      state, exc = state.pop()
    return self.do_raise(state, exc, cause)

  def byte_RAISE_VARARGS(self, state, op):
    if self.python_version[0] == 2:
      return self.byte_RAISE_VARARGS_PY2(state, op)
    else:
      return self.byte_RAISE_VARARGS_PY3(state, op)

  def byte_POP_EXCEPT(self, state, op):  # Python 3 only
    # We don't push the special except-handler block, so we don't need to
    # pop it, either.
    return state

  def byte_SETUP_WITH(self, state, op):
    """Starts a 'with' statement. Will push a block."""
    state, ctxmgr = state.pop()
    level = len(state.data_stack)
    state, exit_method = self.load_attr(state, ctxmgr, "__exit__")
    state = state.push(exit_method)
    state, enter = self.load_attr(state, ctxmgr, "__enter__")
    state, ctxmgr_obj = self.call_function_with_state(state, enter, ())
    if self.python_version[0] == 2:
      state = self.push_block(state, "with", op, op.target, level)
    else:
      assert self.python_version[0] == 3
      state = self.push_block(state, "finally", op, op.target, level)
    return state.push(ctxmgr_obj)

  def byte_WITH_CLEANUP(self, state, op):
    """Called at the end of a with block. Calls the exit handlers etc."""
    state, u = state.pop()  # pop 'None'
    state, exit_func = state.pop()
    state = state.push(self.convert.build_none(state.node))
    v = self.convert.build_none(state.node)
    w = self.convert.build_none(state.node)
    state, suppress_exception = self.call_function_with_state(
        state, exit_func, (u, v, w))
    return state

  def _pop_extra_function_args(self, state, arg):
    """Pop function annotations and defaults from the stack."""
    if self.python_version[0] == 2:
      num_pos_defaults = arg & 0xffff
      num_kw_defaults = 0
    else:
      assert self.python_version[0] == 3
      num_pos_defaults = arg & 0xff
      num_kw_defaults = (arg >> 8) & 0xff
    state, raw_annotations = state.popn((arg >> 16) & 0x7fff)
    state, kw_defaults = state.popn(2 * num_kw_defaults)
    state, pos_defaults = state.popn(num_pos_defaults)
    return state, pos_defaults, kw_defaults, raw_annotations

  def _process_one_annotation(self, annotation, name, top_level=True):
    """Change annotation / record errors where required."""
    if (isinstance(annotation, abstract.Instance) and
        annotation.cls.data == self.convert.str_type.data):
      # String annotations : Late evaluation
      if isinstance(annotation, abstract.PythonConstant) and top_level:
        return function.LateAnnotation(
            name=name,
            opcode=self.frame.current_opcode,
            expr=annotation.pyval)
      else:
        self.errorlog.invalid_annotation(self.frame.current_opcode, name)
        return None
    elif annotation.cls and annotation.cls.data == self.convert.none_type.data:
      # PEP 484 allows to write "NoneType" as "None"
      return self.convert.none_type.data[0]
    elif isinstance(annotation, typing.Container) and annotation.inner:
      inner = []
      for inner_annot in annotation.inner:
        data = []
        changed = False
        for b in inner_annot.bindings:
          processed = self._process_one_annotation(b.data, name, False)
          if processed is None:
            return None
          elif processed is not b.data:
            changed = True
          data.append(processed)
        if changed:
          inner.append(self.program.NewVariable(
              inner_annot.name, data, [], self.root_cfg_node))
        else:
          inner.append(inner_annot)
      annotation.inner = tuple(inner)
      return annotation
    elif isinstance(annotation, typing.Union) and annotation.elements:
      elements = []
      for element in annotation.elements:
        processed = self._process_one_annotation(element, name, False)
        if processed is None:
          return None
        elements.append(processed)
      annotation.elements = tuple(elements)
      return annotation
    else:
      return annotation

  def _convert_function_annotations(self, node, raw_annotations):
    if raw_annotations:
      # {"i": int, "return": str} is stored as (int, str, ("i, "return"))
      names = abstract.get_atomic_python_constant(raw_annotations[-1])
      type_list = raw_annotations[:-1]
      annotations = {}
      late_annotations = {}
      for name, t in zip(names, type_list):
        name = abstract.get_atomic_python_constant(name)
        visible = t.Data(node)
        if len(visible) > 1:
          self.errorlog.invalid_annotation(self.frame.current_opcode, name)
        else:
          annot = self._process_one_annotation(visible[0], name)
          if isinstance(annot, function.LateAnnotation):
            late_annotations[name] = annot
          elif annot is not None:
            annotations[name] = annot
      return annotations, late_annotations
    else:
      return {}, {}

  def _convert_kw_defaults(self, values):
    kw_defaults = {}
    for i in range(0, len(values), 2):
      key_var, value = values[i:i + 2]
      key = abstract.get_atomic_python_constant(key_var)
      kw_defaults[key] = value
    return kw_defaults

  def byte_MAKE_FUNCTION(self, state, op):
    """Create a function and push it onto the stack."""
    if self.python_version[0] == 2:
      name = None
    else:
      assert self.python_version[0] == 3
      state, name_var = state.pop()
      name = abstract.get_atomic_python_constant(name_var)
    state, code = state.pop()
    # TODO(dbaum): Handle kw_defaults and annotations (Python 3).
    state, defaults, kw_defaults, annot = self._pop_extra_function_args(
        state, op.arg)
    kw_defaults = self._convert_kw_defaults(kw_defaults)
    annotations, late_annotations = self._convert_function_annotations(
        state.node, annot)
    globs = self.get_globals_dict()
    fn = self._make_function(name, code, globs, defaults, kw_defaults,
                             annotations=annotations,
                             late_annotations=late_annotations)
    return state.push(fn)

  def byte_MAKE_CLOSURE(self, state, op):
    """Make a function that binds local variables."""
    if self.python_version[0] == 2:
      # The py3 docs don't mention this change.
      name = None
    else:
      assert self.python_version[0] == 3
      state, name_var = state.pop()
      name = abstract.get_atomic_python_constant(name_var)
    state, (closure, code) = state.popn(2)
    # TODO(dbaum): Handle kw_defaults and annotations (Python 3).
    state, defaults, kw_defaults, _ = self._pop_extra_function_args(state,
                                                                    op.arg)
    globs = self.get_globals_dict()
    fn = self._make_function(name, code, globs, defaults, kw_defaults,
                             closure=closure)
    return state.push(fn)

  def byte_CALL_FUNCTION(self, state, op):
    return self.call_function_from_stack(state, op.arg, None, None)

  def byte_CALL_FUNCTION_VAR(self, state, op):
    state, args = self.pop_varargs(state)
    return self.call_function_from_stack(state, op.arg, args, None)

  def byte_CALL_FUNCTION_KW(self, state, op):
    state, kwargs = self.pop_kwargs(state)
    return self.call_function_from_stack(state, op.arg, None, kwargs)

  def byte_CALL_FUNCTION_VAR_KW(self, state, op):
    state, kwargs = self.pop_kwargs(state)
    state, args = self.pop_varargs(state)
    return self.call_function_from_stack(state, op.arg, args, kwargs)

  def byte_YIELD_VALUE(self, state, op):
    state, ret = state.pop()
    self.frame.yield_variable.PasteVariable(ret, state.node)
    return state.set_why("yield")

  def byte_IMPORT_NAME(self, state, op):
    """Import a single module."""
    full_name = self.frame.f_code.co_names[op.arg]
    # The identifiers in the (unused) fromlist are repeated in IMPORT_FROM.
    state, (level_var, fromlist) = state.popn(2)
    # The IMPORT_NAME for an "import a.b.c" will push the module "a".
    # However, for "from a.b.c import Foo" it'll push the module "a.b.c". Those
    # two cases are distinguished by whether fromlist is None or not.
    if self.is_none(fromlist):
      name = full_name.split(".", 1)[0]  # "a.b.c" -> "a"
    else:
      name = full_name
    level = abstract.get_atomic_python_constant(level_var)
    try:
      module = self.import_module(name, level)
    except (parser.ParseError, load_pytd.BadDependencyError,
            visitors.ContainerError, visitors.SymbolLookupError) as e:
      self.errorlog.pyi_error(op, full_name, e)
      module = self.convert.unsolvable
    else:
      if module is None:
        log.warning("Couldn't find module %r", name)
        self.errorlog.import_error(self.frame.current_opcode, name)
        module = self.convert.unsolvable
    return state.push(module.to_variable(state.node, name))

  def byte_IMPORT_FROM(self, state, op):
    """IMPORT_FROM is mostly like LOAD_ATTR but doesn't pop the container."""
    name = self.frame.f_code.co_names[op.arg]
    module = state.top()
    try:
      state, attr = self.load_attr_noerror(state, module, name)
    except (parser.ParseError, load_pytd.BadDependencyError,
            visitors.ContainerError) as e:
      full_name = module.data[0].name + "." + name
      self.errorlog.pyi_error(self.frame.current_opcode, full_name, e)
      attr = None
    else:
      if attr is None:
        self.errorlog.import_from_error(self.frame.current_opcode, module, name)
    if attr is None:
      attr = self.convert.unsolvable.to_variable(state.node, name)
    return state.push(attr)

  def byte_EXEC_STMT(self, state, op):
    state, (unused_stmt, unused_globs, unused_locs) = state.popn(3)
    log.warning("Encountered 'exec' statement. 'exec' is unsupported.")
    return state

  def byte_BUILD_CLASS(self, state, op):
    state, (name, _bases, members) = state.popn(3)
    bases = list(abstract.get_atomic_python_constant(_bases))
    return state.push(self.make_class(state.node, name, bases, members, None))

  def byte_LOAD_BUILD_CLASS(self, state, op):
    # New in py3
    return state.push(abstract.BuildClass(self).to_variable(
        state.node, "__build_class__"))

  def byte_STORE_LOCALS(self, state, op):
    state, locals_dict = state.pop()
    self.frame.f_locals = abstract.get_atomic_value(locals_dict)
    return state

  def byte_END_FINALLY(self, state, op):
    state, exc = state.pop()
    if self.is_none(exc):
      return state
    else:
      log.info("Popping exception %r", exc)
      state = state.pop_and_discard()
      state = state.pop_and_discard()
    return state

  def _check_return(self, opcode, node, actual, formal):
    pass  # overridden in infer.py

  def byte_RETURN_VALUE(self, state, op):
    state, var = state.pop()
    if self.frame.allowed_returns is not None:
      self._check_return(self.frame.current_opcode, state.node, var,
                         self.frame.allowed_returns)
      retvar = self.frame.allowed_returns.instantiate(state.node)
    else:
      retvar = var
    self.frame.return_variable.PasteVariable(retvar, state.node)
    return state.set_why("return")

  def byte_IMPORT_STAR(self, state, op):
    """Pops a module and stores all its contents in locals()."""
    # TODO(kramm): this doesn't use __all__ properly.
    state, mod_var = state.pop()
    mod = abstract.get_atomic_value(mod_var)
    # TODO(rechen): Is mod ever an unknown?
    if isinstance(mod, (abstract.Unknown, abstract.Unsolvable)):
      self.has_unknown_wildcard_imports = True
      return state
    log.info("%r", mod)
    # TODO(kramm): Add Module type to abstract.py
    for name, var in mod.items():
      if name[0] != "_" or name == "__getattr__":
        state = self.store_local(state, name, var)
    return state

  def byte_SLICE_0(self, state, op):
    return self.get_slice(state, 0)

  def byte_SLICE_1(self, state, op):
    return self.get_slice(state, 1)

  def byte_SLICE_2(self, state, op):
    return self.get_slice(state, 2)

  def byte_SLICE_3(self, state, op):
    return self.get_slice(state, 3)

  def byte_STORE_SLICE_0(self, state, op):
    return self.store_slice(state, 0)

  def byte_STORE_SLICE_1(self, state, op):
    return self.store_slice(state, 1)

  def byte_STORE_SLICE_2(self, state, op):
    return self.store_slice(state, 2)

  def byte_STORE_SLICE_3(self, state, op):
    return self.store_slice(state, 3)

  def byte_DELETE_SLICE_0(self, state, op):
    return self.delete_slice(state, 0)

  def byte_DELETE_SLICE_1(self, state, op):
    return self.delete_slice(state, 1)

  def byte_DELETE_SLICE_2(self, state, op):
    return self.delete_slice(state, 2)

  def byte_DELETE_SLICE_3(self, state, op):
    return self.delete_slice(state, 3)
