"""A abstract virtual machine for python bytecode that generates typegraphs.

A VM for python byte code that uses kramm@ typegraph to generate a trace of the
program execution.
"""

# Disable because there are enough false positives to make it useless
# pylint: disable=unbalanced-tuple-unpacking
# pylint: disable=unpacking-non-sequence

# We have names like "byte_NOP":
# pylint: disable=invalid-name

# Bytecodes don't always use all their arguments:
# pylint: disable=unused-argument

import collections
import dis
import linecache
import logging
import operator
import re
import repr as reprlib
import sys
import types


from pytype import abstract
from pytype import exceptions
from pytype import import_paths
from pytype import pycfg
from pytype import state
from pytype import utils
from pytype.pyc import loadmarshal
from pytype.pytd import cfg as typegraph
from pytype.pytd import pytd
from pytype.pytd import slots
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import builtins

log = logging.getLogger(__name__)


# Create a repr that won't overflow.
repr_obj = reprlib.Repr()
repr_obj.maxother = 120
repr_obj.maxstring = 72
repper = repr_obj.repr


Block = collections.namedtuple("Block", ["type", "handler", "level"])


class ConversionError(ValueError):
  pass


def _get_atomic_value(variable):
  values = variable.values
  if len(values) == 1:
    return values[0].data
  else:
    raise ConversionError(
        "Variable with too many options when trying to get atomic value. %s %s"
        % (variable, [a.data for a in values]))


def _get_atomic_python_constant(variable):
  """Get the concrete atomic Python value stored in this variable.

  This is used for things that are stored in typegraph.Variable, but we
  need the actual data in order to proceed. E.g. function / class defintions.

  Args:
    variable: A typegraph.Variable. It can only have one possible value.
  Returns:
    A Python constant. (Typically, a string, a tuple, or a code object.)
  Raises:
    ValueError: If the value in this Variable is purely abstract, i.e. doesn't
      store a Python value.
    IndexError: If there is more than one possibility for this value.
  """
  atomic = _get_atomic_value(variable)
  if isinstance(atomic, abstract.PythonConstant):
    return atomic.pyval
  raise ConversionError(
      "Only some types are supported: %r" % type(atomic))


class VirtualMachineError(Exception):
  """For raising errors in the operation of the VM."""
  pass


class VirtualMachine(object):
  """A bytecode VM that generates a typegraph as it executes.

  Attributes:
    program: The typegraph.Program used to build the typegraph.
    root_cfg_node: The root CFG node that contains the definitions of builtins.
    current_location: The currently executing CFG node.
    primitive_classes: A mapping from primitive python types to their abstract
      types.
  """

  # TODO(ampere): Expand supported features in this VM.
  #    Base-classes: This will almost certainly require changes to
  #       VirtualMachine.make_class.
  #    Generator: May already work. But will probably need careful support for
  #       stored frames in the presence of the out of order execution.
  #    Modules: Will need some sort of namespace management during execution and
  #       storing how a value is accessed and from where.

  def __init__(self, python_version, reverse_operators=False):
    """Construct a TypegraphVirtualMachine."""
    self.python_version = python_version
    self.reverse_operators = reverse_operators
    # The call stack of frames.
    self.frames = []
    # The current frame.
    self.frame = None
    self.return_value = None
    self.last_exception = None
    self.vmbuiltins = dict(__builtins__)
    self.vmbuiltins["isinstance"] = self.isinstance
    self._cache_linestarts = {}  # maps frame.f_code => list of (offset, lineno)

    # Unary operators: positive, negative, invert, convert, and "not"
    self.unary_operators = dict(
        NOT=operator.not_,
    )
    for op, magic in slots.UnaryOperatorMapping().items():
      self.unary_operators[op] = self.magic_unary_operator(magic)

    # Binary operators. __add__, __radd__ etc.
    self.binary_operators = {
        op: self.magic_binary_operator(magic)
        for op, magic in slots.BinaryOperatorMapping().items()}

    # __eq__, __lt__ etc. Also see FALLBACKS below.
    # The indexes of these correspond to COMPARE_OPS in pytd/slots.py.
    # (enum cmp_op in Include/opcode.h)
    self.compare_operators = [
        # overwritten below:
        operator.lt,
        operator.le,
        operator.eq,
        operator.ne,
        operator.gt,
        operator.ge,
        # overwritten in typegraphvm:
        lambda x, y: x in y,
        lambda x, y: x not in y,
        lambda x, y: x is y,
        lambda x, y: x is not y,
        lambda x, y: issubclass(x, Exception) and issubclass(x, y),
    ]

    for cmp_op, magic in slots.CompareFunctionMapping().items():
      self.compare_operators[cmp_op] = self.magic_binary_operator(magic)

    # __iadd__, __ipow__ etc.
    self.inplace_operators = {
        op: self.magic_binary_operator(magic)
        for op, magic in slots.InplaceOperatorMapping().items()
    }
    self.program = typegraph.Program()

    self.root_cfg_node = self.program.NewCFGNode("root")
    self.program.entrypoint = self.root_cfg_node
    self.current_location = self.root_cfg_node

    # Used if we don't have a frame (e.g. when setting up an artificial function
    # call):
    self.default_location = self.root_cfg_node

    self.source_nodes = [self.root_cfg_node]

    self._convert_cache = {}

    # Initialize primitive_classes to empty to allow convert_constant to run
    self.primitive_classes = {}
    # Now fill primitive_classes with the real values using convert_constant
    self.primitive_classes = {v: self.convert_constant(repr(v), v)
                              for v in [int, long, float, str, unicode,
                                        types.NoneType, complex, bool, slice]}
    self.container_classes = {v: self.convert_constant(repr(v), v)
                              for v in [tuple, list, set, dict]}
    self.str_type = self.primitive_classes[str]
    self.slice_type = self.primitive_classes[slice]
    self.tuple_type = self.container_classes[tuple]
    self.list_type = self.container_classes[list]
    self.set_type = self.container_classes[set]
    self.dict_type = self.container_classes[dict]
    self.function_type = self.convert_constant("function type",
                                               types.FunctionType)

    self.builtins_pytd = abstract.get_builtins_pytds()
    self.builtins_codes = builtins.GetBuiltinsCode()

    self.vmbuiltins = {}
    self._set_vmbuiltin("constant", self.builtins_pytd.constants)
    self._set_vmbuiltin("class", self.builtins_pytd.classes)
    self._set_vmbuiltin("function", self.builtins_pytd.functions)
    # Do not do the following because all modules must be explicitly imported.
    # self._set_vmbuiltin("module", self.builtins_pytd.modules)

    self.compare_operators[slots.CMP_IS] = self.cmp_is
    self.compare_operators[slots.CMP_IS_NOT] = self.cmp_is_not
    self.compare_operators[slots.CMP_NOT_IN] = self.cmp_not_in
    self.compare_operators[slots.CMP_IN] = self.cmp_in
    self.compare_operators[slots.CMP_EXC_MATCH] = self.cmp_exc_match
    self.unary_operators["NOT"] = self.not_op

    self.cfg = pycfg.CFG()

  # Since we process things out of order, all jump instructions assume we do
  # NOT jump, and the "jumping" is done by later processing the jumped-to
  # instruction as a new block.

  def frame_traversal_setup(self, frame):
    """Initialize a frame to allow ancestors first traversal.

    Args:
      frame: The execution frame to update.
    Returns:
      True if we can execute this frame.
    """
    frame.block_table = self.cfg.get_block_table(frame.f_code)
    frame.order = frame.block_table.get_ancestors_first_traversal()
    # A mapping from basic blocks to stack states
    frame.block_start_stack = {}
    frame.current_block = frame.order[0]
    log.debug("Frames %r", self.frames)
    if frame.order[0] in (f.current_block for f in self.frames[:-1]):
      log.debug("Truncating recursion")
      return False
    return True

  def propagate_state_before_opcode(self, frame):
    """Forward the state we have before an opcode to other parts of the CFG."""
    if frame.f_lasti == frame.current_block.end and frame.current_block.jumps:
      # The last instruction, which is typically a jump instruction.
      frame_state = frame.save_state()
      log.debug("Propagating block stack: %r", frame_state.block_stack)
      for next_block in frame.current_block.jumps:
        log.debug("Propagating state before opcode %d to opcode %d",
                  frame.f_lasti, next_block.begin)
        frame.block_start_stack[next_block] = frame_state

  def propagate_state_after_opcode(self, frame, why):
    """Propagate the state we have after an opcode to other parts of the CFG."""
    head = frame.order[0]
    if head.begin <= frame.f_lasti <= head.end:
      # Still running the current block.
      return
    if why:
      # We're returning from (or aborting) the current path, so no other opcodes
      # need to receive our state.
      return
    # For function calls, the block after the CALL_FUNCTION opcode
    # will not be directly connected to the current block, but we still have
    # to propagate our state to it.
    fallthrough = frame.block_table.get_basic_block(frame.f_lasti)
    if fallthrough is not head.following_block:
      log.debug("Not falling through: next block would be %s, "
                "but we jumped to %d",
                head.following_block and head.following_block.begin,
                frame.f_lasti)
      return
    assert fallthrough in head.outgoing, "Bad fallthrough"
    frame_state = frame.save_state()
    log.debug("Propagating block stack: %r", frame_state.block_stack)
    log.debug("Propagating state after opcode %d to %d",
              head.end, fallthrough.begin)
    frame.block_start_stack[fallthrough] = frame_state

  def frame_traversal_next(self, frame, why=None):
    """Move the frame instruction pointer to the next instruction.

    This implements the next instruction operation on the ancestors first
    traversal order.

    Args:
      frame: The execution frame to update.
      why: Whether the last instruction ended this frame (and why).

    Returns:
      False if the traversal is done (every instruction in the frames code
      has been executed. True otherwise.
    """
    head = frame.order[0]

    if not why and head.begin <= frame.f_lasti <= head.end:
      return True  # still executing the same basic block

    # Find a block we have state information for.
    while True:
      frame.order.pop(0)
      if not frame.order:
        return False
      head = frame.order[0]
      if head in (f.current_block for f in self.frames[:-1]):
        log.info("Truncating recursion.")
        continue
      elif head in frame.block_start_stack:
        break
      else:
        log.debug("Discarding block %d (unreachable)", head.begin)

    if log.isEnabledFor(logging.DEBUG):
      log.debug("Switching to block at %d", head.begin)
      src = frame.block_table.get_any_jump_source(head)
      if src:
        log.debug("E.g. reachable from %d-%d", src.begin, src.end)
      else:
        log.debug("(Not directly reachable)")

    assert head in frame.block_start_stack
    frame.restore_state(frame.block_start_stack[head])

    if head.pop_on_enter:
      # For FOR_ITER, which pops the iterator at the end of the loop.
      log.debug("popping %d value(s) on block enter", head.pop_on_enter)
      self.popn(head.pop_on_enter)
    elif head.needs_exc_push:
      self.push_abstract_exception()

    frame.f_lasti = head.begin
    frame.current_block = head
    return True

  def connect_source_nodes(self, to):
    for node in self.source_nodes:
      node.ConnectTo(to)
    self.source_nodes = []

  def run_frame(self, frame):
    """Run a frame until it returns (somehow).

    Exceptions are raised, the return value is returned.

    Arguments:
      frame: The frame to run.

    Returns:
      The return value of the function that belongs to this frame.

    Raises:
      AssertionError: For internal errors.
    """
    if not self.source_nodes:
      self.source_nodes.append(self.current_location)
    self.push_frame(frame)
    frame_ok_to_run = self.frame_traversal_setup(frame)
    while frame_ok_to_run:
      assert frame == self.frame
      block = self.update_location()

      log.info("Backtrace: " + self.backtrace())

      # If we are coming from somewhere interesting (a function call) then add
      # this edge
      self.connect_source_nodes(self.current_location)

      self.propagate_state_before_opcode(frame)
      why = self.run_instruction()
      self.propagate_state_after_opcode(frame, why)

      if (not frame.cfgnode[block].outgoing and
          frame.f_lasti > block.end):
        # Some nodes contain calls that don't cause execution of any new
        # bytecodes/blocks (e.g. calls to pytd functions) - we need to explictly
        # connect these to the following cfg node.
        self.process_block_connections(block, allow_returns=True)

      if why is None:
        # The instruction succeeded. We're moving one instruction forward.
        pass
      elif why in ["return", "yield"]:
        # Store the source of this return for use later
        frame.return_nodes.append(self.current_location)
      elif why in ["exception", "fatal_exception"]:
        # This exception terminates the current execution flow. We'll abandon
        # it and process the next basic block on our "to-do list" (frame.order).
        # TODO(kramm): Connect the current CFG position to all the nearest
        # exception handlers.
        log.info("Aborting current block: %r", why)
      else:
        raise AssertionError("Unknown 'why': %r", why)

      if not self.frame_traversal_next(frame, why):
        break
    self.pop_frame()
    self.source_nodes.extend(frame.return_nodes)

    self.update_location()
    return frame.return_variable

  def magic_unary_operator(self, name):
    def magic_unary_operator_wrapper(x):
      return self.call_function(self.load_attr(x, name), [], {})
    return magic_unary_operator_wrapper

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

  FALLBACKS = {
      "__lt__": operator.lt,
      "__le__": operator.le,
      "__gt__": operator.gt,
      "__ge__": operator.ge,
      "__eq__": operator.eq,
      "__ne__": operator.ne,
  }
  # Native types don't have attributes for inplace operators (for example,
  # "x".__iadd__ doesn't work). So add fallbacks for all of them.
  FALLBACKS.update({
      name: getattr(operator, name)
      for name in dir(operator)
      if name.startswith("__i")
  })

  def top(self):
    """Return the value at the top of the stack, with no changes."""
    return self.frame.data_stack[-1]

  def pop(self, i=0):
    """Pop a value from the stack.

    Default to the top of the stack, but `i` can be a count from the top
    instead.

    Arguments:
      i: If this is given, a value is extracted and removed from the middle
      of the stack.

    Returns:
      A stack entry (typegraph.Variable).
    """
    return self.frame.data_stack.pop(-1 - i)

  def push(self, *vals):
    """Push values onto the value stack."""
    self.frame.push(*vals)

  def popn(self, n):
    """Pop a number of values from the value stack.

    A list of `n` values is returned, the deepest value first.

    Arguments:
      n: The number of items to pop

    Returns:
      A list of n values.
    """
    if n:
      ret = self.frame.data_stack[-n:]
      self.frame.data_stack[-n:] = []
      return ret
    else:
      return []

  def peek(self, n):
    """Get a value `n` entries down in the stack, without changing the stack."""
    return self.frame.data_stack[-n]

  def push_block(self, t, handler=None, level=None):
    if level is None:
      level = len(self.frame.data_stack)
    self.frame.block_stack.append(Block(t, handler, level))

  def pop_block(self):
    return self.frame.block_stack.pop()

  def push_frame(self, frame):
    self.frames.append(frame)
    self.frame = frame

  def pop_frame(self):
    self.frames.pop()
    if self.frames:
      self.frame = self.frames[-1]
    else:
      self.frame = None

  def print_frames(self):
    """Print the call stack, for debugging."""
    for f in self.frames:
      filename = f.f_code.co_filename
      lineno = f.line_number()
      print '  File "%s", line %d, in %s' % (filename, lineno, f.f_code.co_name)
      linecache.checkcache(filename)
      line = linecache.getline(filename, lineno, f.f_globals)
      if line:
        print "  " + line.strip()

  def unwind_block(self, block):
    if block.type == "except-handler":
      offset = 3
    else:
      offset = 0

    while len(self.frame.data_stack) > block.level + offset:
      self.pop()

    if block.type == "except-handler":
      tb, value, exctype = self.popn(3)
      self.last_exception = exctype, value, tb

  def opcodes_are_adjacent(self, pos1, pos2):
    bytecode = ord(self.frame.f_code.co_code[pos1])
    if bytecode < dis.HAVE_ARGUMENT:
      return pos1 + 1 == pos2
    else:
      return pos1 + 3 == pos2

  def parse_byte_and_args(self):
    """Parse a bytecode."""
    f = self.frame
    opoffset = f.f_lasti
    try:
      bytecode = ord(f.f_code.co_code[opoffset])
    except IndexError:
      raise VirtualMachineError(
          "Bad bytecode offset %d in %s (len=%d)" %
          (opoffset, str(f.f_code), len(f.f_code.co_code))
      )
    f.f_lasti += 1
    bytename = dis.opname[bytecode]
    arg = None
    arguments = []
    if bytecode >= dis.HAVE_ARGUMENT:
      arg = f.f_code.co_code[f.f_lasti:f.f_lasti + 2]
      f.f_lasti += 2
      intarg = ord(arg[0]) + (ord(arg[1]) << 8)
      if bytecode in dis.hasconst:
        arg = f.f_code.co_consts[intarg]
      elif bytecode in dis.hasname:
        arg = f.f_code.co_names[intarg]
      elif bytecode in dis.hasjrel:
        arg = f.f_lasti + intarg
      elif bytecode in dis.hasjabs:
        arg = intarg
      elif bytecode in dis.haslocal:
        arg = f.f_code.co_varnames[intarg]
      else:
        arg = intarg
      arguments = [arg]

    return bytename, arguments, opoffset

  def log(self, bytename, arguments, opoffset):
    """Write a multi-line log message, including backtrace and stack."""
    if not log.isEnabledFor(logging.INFO):
      return
    # pylint: disable=logging-not-lazy
    op = "%d: %s" % (opoffset, bytename)
    if arguments:
      op += " " + utils.maybe_truncate(repr(arguments[0]), length=150)
    indent = " > " * (len(self.frames) - 1)
    stack_rep = repper(self.frame.data_stack)
    block_stack_rep = repper(self.frame.block_stack)
    log.info("%s | line: %d", indent, self.frame.line_number())
    log.info("%s | data: %s", indent, stack_rep)
    log.info("%s | blks: %s", indent, block_stack_rep)
    # For more information on frames, see source for module 'dis' or
    # http://security.coverity.com/blog/2014/Nov/understanding-python-bytecode.html
    # TODO(pludemann): nicer module/file name:
    filename = ".".join(re.sub(
        r"\.py$", "", self.frame.f_code.co_filename or "").split("/")[-2:])
    log.info("%s | filename: %s", indent, filename)
    log.info("%s %s", indent, op)

  def repper(self, s):
    return repr_obj.repr(s)

  def dispatch(self, bytename, arguments):
    """Figure out which bytecode function to call."""
    # TODO(kramm): Rename 'why' to 'abort'.
    why = None
    try:
      if bytename.startswith("UNARY_"):
        self.unary_operator(bytename[6:])
      elif bytename.startswith("BINARY_"):
        self.binary_operator(bytename[7:])
      elif bytename.startswith("INPLACE_"):
        self.inplace_operator(bytename[8:])
      elif "SLICE+" in bytename:
        self.slice_operator(bytename)
      else:
        # dispatch
        bytecode_fn = getattr(self, "byte_%s" % bytename, None)
        if not bytecode_fn:      # pragma: no cover
          raise VirtualMachineError(
              "unknown bytecode type: %s" % bytename
          )
        why = bytecode_fn(*arguments)
    except StopIteration:
      # We don't wrap StopIteration exceptions, because of their special role
      # with reference to loops.
      self.last_exception = sys.exc_info()[:2] + (None,)
      why = "exception"
    except exceptions.ByteCodeException:
      e = sys.exc_info()[1]
      self.last_exception = (e.exception_type, e.create_instance(), None)
      # TODO(pludemann): capture exceptions that are indicative of
      #                  a bug (AttributeError?)
      log.info("ByteCodeException: %s %r", e.exception_type, e.message)
      why = "exception"

    return why

  def pop_and_unwind_block(self):
    self.unwind_block(self.pop_block())

  def manage_block_stack(self, why):
    assert why != "yield"
    block = self.frame.block_stack[-1]
    t = block.type, why
    if t == ("loop", "continue"):
      return self.jump(self.return_value, why)
    self.pop_and_unwind_block()
    if t == ("loop", "break"):
      return self.jump(block.handler, why)
    elif t in {("finally", "return"),
               ("finally", "continue"),
               ("with", "return"),
               ("with", "continue")}:
      self.push(self.return_value)
      self.push(why)
      return self.jump(block.handler, why)
    elif t in {("with", "break"),
               ("finally", "break")}:
      self.push(why)
      return self.jump(block.handler, why)
    elif self.python_version[0] == 3 and t in {("setup-except", "exception"),
                                               ("finally", "exception")}:
      self.push_block("except-handler")
      self.push_last_exception()
      self.push_last_exception()  # for PyErr_Normalize_Exception
      return self.jump(block.handler, why)
    elif t in {("setup-except", "exception"),
               ("finally", "exception"),
               ("with", "exception")}:
      self.push_last_exception()
      return self.jump(block.handler, why)
    elif t in {("loop", "return"),
               ("loop", "exception"),
               ("setup-except", "continue"),
               ("setup-except", "break"),
               ("setup-except", "return")}:
      return why
    else:
      raise ValueError(repr(t))

  # Events that cause us to abandon (or pause) an entire execution flow.
  EXIT_STATES = ("fatal_exception", "yield")

  def run_instruction(self):
    """Run one instruction in the current frame.

    Returns:
      None if the frame should continue executing otherwise return the
      reason it should stop.
    """
    frame = self.frame
    bytename, arguments, opoffset = self.parse_byte_and_args()
    if log.isEnabledFor(logging.INFO):
      self.log(bytename, arguments, opoffset)

    # When unwinding the block stack, we need to keep track of why we
    # are doing it.
    why = self.dispatch(bytename, arguments)
    if why == "exception":
      # TODO(kramm): ceval calls PyTraceBack_Here, not sure what that does.
      pass

    if why == "reraise":
      why = "exception"
    while why not in self.EXIT_STATES + (None,) and frame.block_stack:
      # Deal with any block management we need to do.
      why = self.manage_block_stack(why)

    return why

  # Abstraction hooks

  def store_subscr(self, obj, key, val):
    self.call_function(self.load_attr(obj, "__setitem__"),
                       [key, val], {})

  # Stack manipulation

  # Operators

  def unary_operator(self, op):
    x = self.pop()
    self.push(self.unary_operators[op](x))

  def binary_operator(self, op):
    x, y = self.popn(2)
    self.push(self.binary_operators[op](x, y))

  def inplace_operator(self, op):
    x, y = self.popn(2)
    self.push(self.inplace_operators[op](x, y))

  def slice_operator(self, op):  # pylint: disable=invalid-name
    """Apply a slice operator (SLICE+0...SLICE+3)."""
    start = 0
    end = None      # we will take this to mean end
    op, count = op[:-2], int(op[-1])  # "SLICE+1" -> op="SLICE", count=1
    if count == 1:
      start = self.pop()
    elif count == 2:
      end = self.pop()
    elif count == 3:
      end = self.pop()
      start = self.pop()
    l = self.pop()
    if end is None:
      end = self.call_function(self.load_attr(l, "__len__"), [], {})
    if op.startswith("STORE_"):
      self.call_function(self.load_attr(l, "__setitem__"),
                         [self.build_slice(start, end, 1), self.pop()],
                         {})
    elif op.startswith("DELETE_"):
      self.call_function(self.load_attr(l, "__delitem__"),
                         [self.build_slice(start, end, 1)],
                         {})
    else:
      self.push(self.call_function(self.load_attr(l, "__getitem__"),
                                   [self.build_slice(start, end, 1)],
                                   {}))

  def do_raise(self, exc, cause):
    """Raise an exception. Used by byte_RAISE_VARARGS."""
    if exc is None:     # reraise
      exc_type, val, _ = self.last_exception
      if exc_type is None:
        return "exception"    # error
      else:
        return "reraise"

    elif type(exc) == type:
      # As in `raise ValueError`
      exc_type = exc
      val = exc()       # Make an instance.
    elif isinstance(exc, BaseException):
      # As in `raise ValueError('foo')`
      exc_type = type(exc)
      val = exc
    else:
      return "exception"    # error

    # If you reach this point, you're guaranteed that
    # val is a valid exception instance and exc_type is its class.
    # Now do a similar thing for the cause, if present.
    if cause:
      if type(cause) == type:
        cause = cause()
      elif not isinstance(cause, BaseException):
        return "exception"  # error

      val.__cause__ = cause

    self.last_exception = exc_type, val, val.__traceback__
    return "exception"

  # Importing

  def get_module_attribute(self, mod, name):
    """Return the modules members as a dict."""
    return self.load_attr(mod, name)

  def _set_vmbuiltin(self, descr, values):
    for b in values:
      log.info("Initializing builtin %s: %s", descr, b.name)
      self.vmbuiltins[b.name] = b

  def instantiate_builtin(self, cls):
    clsvar = self.primitive_classes[cls]
    value = abstract.SimpleAbstractValue("instance of " + clsvar.name, self)
    value.set_attribute("__class__", clsvar)
    return value.to_variable(name=clsvar.name)

  def instantiate(self, cls):
    # TODO(kramm): Make everything use this
    value = abstract.SimpleAbstractValue("instance of " + cls.name, self)
    value.set_attribute("__class__", cls)
    return value.to_variable(name="instance of " + cls.name)

  def not_op(self, x):
    return self.instantiate_builtin(bool)

  def cmp_is(self, x, y):
    return self.instantiate_builtin(bool)

  def cmp_is_not(self, x, y):
    return self.instantiate_builtin(bool)

  def cmp_in(self, x, y):
    return self.instantiate_builtin(bool)

  def cmp_not_in(self, x, y):
    return self.instantiate_builtin(bool)

  def cmp_exc_match(self, x, y):
    return self.instantiate_builtin(bool)

  def new_variable(self, name, values=None, origins=None, loc=None):
    """Make a new variable using self.program.

    This should be used instead of self.program.NewVariable to allow error
    checking and debugging.

    Args:
      name: The name to give the variable.
      values: The values to put in the variable.
      origins: The origins that each value should have.
      loc: The location for the initial values.
    Returns:
      A new Variable object.
    Raises:
      ValueError: If values, origins and loc are inconsistent wrt each other.
    """
    if loc is self.root_cfg_node:
      log.debug("Creating root variable: %s '%s...' %r", name,
                repr(values)[:100], origins)
    if values:
      assert all(isinstance(v, abstract.AtomicAbstractValue) for v in values)
    if values is not None:
      if origins is None or loc is None:
        raise ValueError("If values is not None, origins and loc must also not "
                         "be None")
      return self.program.NewVariable(name, values, origins, loc)
    else:
      if origins is not None or loc is not None:
        raise ValueError("If values is None, origins and loc must also be None")
      return self.program.NewVariable(name)

  def join_variables(self, name, variables):
    """Create a combined Variable for a list of variables.

    This is destructive: It will reuse and overwrite the input variables. The
    purpose of this function is to create a final result variable for functions
    that return a list of "temporary" variables. (E.g. function calls)

    Args:
      name: Name of the new variable.
      variables: List of variables.
    Returns:
      A typegraph.Variable.
    """
    if not variables:
      return self.program.NewVariable(name)  # return empty var
    elif len(variables) == 1:
      v, = variables
      return v
    else:
      v = self.program.NewVariable(name)
      for r in variables:
        v.AddValues(r, self.current_location)
      return v

  def convert_value_to_string(self, val):
    if isinstance(val, abstract.PythonConstant) and isinstance(val.pyval, str):
      return val.pyval
    raise ConversionError("%s is not a string" % val)

  def create_pytd_instance(self, pytype, sources, subst=None):
    """Create an instance of a PyTD type as a typegraph.Variable.

    Because this (unlike create_pytd_instance_value) creates variables, it can
    also handle union types.

    Args:
      pytype: A PyTD type to construct an instance of.
      sources: Which sources to attach to the variable values.
      subst: The current type parameters.
    Returns:
      A typegraph.Variable.
    Raises:
      ValueError: If we can't resolve a type parameter.
    """
    if isinstance(pytype, pytd.AnythingType):
      return self.create_new_unknown("?")
    name = pytype.name if hasattr(pytype, "name") else pytype.__class__.__name__
    var = self.program.NewVariable(name)
    for t in pytd_utils.UnpackUnion(pytype):
      if isinstance(t, pytd.TypeParameter):
        if not subst or t.name not in subst:
          raise ValueError("Can't resolve type parameter %s using %r" % (
              t.name, subst))
        for v in subst[t.name].values:
          var.AddValue(v.data, list(sources) + [v], self.current_location)
      else:
        value = self.create_pytd_instance_value(t, subst)
        var.AddValue(value, list(sources), self.current_location)
        log.info("New pytd instance for %s: %r", name, value)
    return var

  def create_pytd_instance_value(self, pytype, subst=None):
    """Create an instance of PyTD type.

    This can handle any PyTD type and is used for generating both methods of
    classes (when given a Signature) and instance of classes (when given a
    ClassType).

    Args:
      pytype: A PyTD type to construct an instance of.
      subst: The current type parameters.
    Returns:
      An instance of AtomicAbstractType.
    Raises:
      ValueError: if pytype is not of a known type.
    """
    if isinstance(pytype, pytd.ClassType):
      if not pytype.cls:
        raise ValueError("Class {} must be resolved before typegraphvm can "
                         "instantiate them: {}".format(pytype.name,
                                                       repr(pytype)))
      value = abstract.SimpleAbstractValue(pytype.cls.name, self)
      value.set_attribute("__class__",
                          self.convert_constant(pytype.cls.name, pytype.cls))
      return value
    elif isinstance(pytype, pytd.TypeParameter):
      raise ValueError("Trying to create an instance of type parameter %s. "
                       "Bug in argument parsing?" % pytype.name)
    elif isinstance(pytype, pytd.GenericType):
      assert isinstance(pytype.base_type, pytd.ClassType)
      value = abstract.SimpleAbstractValue(pytd.Print(pytype), self)
      value.set_attribute("__class__",
                          self.convert_constant(
                              pytype.base_type.cls.name + ".__class__",
                              pytype.base_type.cls))
      if isinstance(pytype, pytd.GenericType):
        type_params = pytype.parameters
      else:
        type_params = (pytype.element_type,)
      for formal, actual in zip(pytype.base_type.cls.template, type_params):
        log.info("Setting type parameter: %r %r", formal, actual)
        # TODO(kramm): Should these be classes, not instances?
        p = self.create_pytd_instance(actual, sources=[], subst=subst)
        value.overwrite_type_parameter(formal.name, p)
      return value
    elif isinstance(pytype, pytd.Signature):
      return abstract.PyTDSignature("?", pytype, self)
    elif isinstance(pytype, pytd.FunctionWithSignatures):
      f = abstract.PyTDFunction(pytype.name, [], self)
      f.signatures = [abstract.PyTDSignature(f, sig, self)
                      for sig in pytype.signatures]
      return f
    elif isinstance(pytype, pytd.NothingType):
      return abstract.Nothing(self)
    elif isinstance(pytype, pytd.AnythingType):
      # TODO(kramm): Can we do this without creating a Variable?
      return self.create_new_unknown("?").data[0]
    else:
      # includes pytd.FunctionWithCode, which should never occur
      raise ValueError("Cannot create instance of {}".format(pytype))

  def create_new_unknown(self, name, source=None):
    """Create a new variable containing unknown, originating from this one."""
    unknown = abstract.Unknown(self)
    v = self.program.NewVariable(name)
    val = v.AddValue(unknown, source_set=[source] if source else [],
                     where=self.current_location)
    unknown.owner = val
    self.trace_unknown(v)
    return v

  def convert_constant(self, name, pyval):
    """Convert a constant to a Variable.

    This converts a constant to a typegraph.Variable. Unlike
    convert_constant_to_value, it can handle things that need to be represented
    as a Variable with multiple possible values (i.e., a union type), like
    pytd.FunctionWithSignatures.

    Args:
      name: The name to give the new variable.
      pyval: The Python constant to convert. Can be a PyTD definition or a
      builtin constant.
    Returns:
      A typegraph.Variable.
    Raises:
      ValueError: if pytype is not of a known type.
    """
    result = self.convert_constant_to_value(name, pyval)
    if result is not None:
      return result.to_variable(name)
    # There might still be bugs on the abstract intepreter when it returns,
    # e.g. a list of values instead of a list of types:
    assert pyval.__class__ != typegraph.Variable, pyval
    if pyval.__class__ == tuple:
      # TODO(ampere): This does not allow subclasses. Handle namedtuple
      # correctly.
      # This case needs to go at the end because many things are actually also
      # tuples.
      return self.build_tuple(
          self.maybe_convert_constant("tuple[%d]" % i, v)
          for i, v in enumerate(pyval))
    raise ValueError(
        "Cannot convert {} to an abstract value".format(pyval.__class__))

  def convert_constant_to_value(self, name, pyval):
    # We don't memoize on name, as builtin types like str or list might be
    # reinitialized under different names (e.g. "param 1"), but we want the
    # canonical name and type.
    # We *do* memoize on the type as well, to make sure that e.g. "1.0" and
    # "1" get converted to different constants.
    # Memoization is an optimization, but an important one- mapping constants
    # like "None" to the same AbstractValue greatly simplifies the typegraph
    # structures we're building.
    key = (pyval, type(pyval))
    if key not in self._convert_cache:
      self._convert_cache[key] = self.construct_constant_from_value(name, pyval)
    return self._convert_cache[key]

  def construct_constant_from_value(self, name, pyval):
    """Create a AtomicAbstractValue that represents a python constant.

    This supports both constant from code constant pools and PyTD constants such
    as classes. This also supports built-in python objects such as int and
    float.

    Args:
      name: The name of this constant. Used for naming its attribute variables.
      pyval: The python or PyTD value to convert.
    Returns:
      A Value that represents the constant, or None if we couldn't convert.
    """
    if pyval is type:
      return abstract.SimpleAbstractValue(name, self)
    elif pyval.__class__ in self.primitive_classes:
      clsvar = self.primitive_classes[pyval.__class__]
      value = abstract.AbstractOrConcreteValue(name, pyval, self)
      value.set_attribute("__class__", clsvar)
      log.info("Setting %s.__class__ to %s", value.name, clsvar.name)
      return value
    elif isinstance(pyval, loadmarshal.CodeType):
      return abstract.AbstractOrConcreteValue(name, pyval, self)
    elif pyval.__class__ in [types.FunctionType, types.ModuleType, type]:
      try:
        # TODO(ampere): This will incorrectly handle any object that is named
        # the same as a builtin but is distinct. It will need to be extended to
        # support imports and the like.
        pyclass = abstract.get_pytd(pyval.__name__)
        return self.convert_constant_to_value(name, pyclass)
      except (KeyError, AttributeError):
        log.debug("Failed to find pytd", exc_info=True)
        raise
    elif isinstance(pyval, pytd.TypeDeclUnit):
      members = {val.name: val
                 for val in pyval.constants + pyval.classes + pyval.functions}
      return abstract.Module(self, pyval.name, members)
    elif isinstance(pyval, pytd.Class):
      return abstract.PyTDClass(pyval, self)
    elif isinstance(pyval, pytd.FunctionWithSignatures):
      return self.create_pytd_instance_value(pyval, {})
    elif isinstance(pyval, pytd.FunctionWithCode):
      raise AssertionError("Unexpected FunctionWithCode: {}".format(pyval))
    elif isinstance(pyval, pytd.Constant):
      value = abstract.SimpleAbstractValue(name, self)
      value.set_attribute("__class__",
                          self.convert_constant(name + ".__class__",
                                                pyval.type))
      return value
    elif isinstance(pyval, pytd.ClassType):
      assert pyval.cls
      return self.convert_constant_to_value(pyval.name, pyval.cls)
    elif isinstance(pyval, pytd.UnionType):
      return abstract.Union([self.convert_constant_to_value(pytd.Print(t), t)
                             for t in pyval.type_list], self)
    elif isinstance(pyval, pytd.TypeParameter):
      return abstract.TypeParameter(pyval.name, pyval, self)
    elif isinstance(pyval, pytd.GenericType):
      # TODO(kramm): Remove ParameterizedClass. This should just create a
      # SimpleAbstractValue with type parameters.
      assert isinstance(pyval.base_type, pytd.ClassType)
      type_parameters = {
          param.name: self.convert_constant_to_value(param.name, value)
          for param, value in zip(pyval.base_type.cls.template,
                                  pyval.parameters)
      }
      cls = self.convert_constant_to_value(pytd.Print(pyval.base_type),
                                           pyval.base_type.cls)
      return abstract.ParameterizedClass(cls, type_parameters, self)
    else:
      return None

  def maybe_convert_constant(self, name, pyval):
    """Create a variable that represents a python constant if needed.

    Call self.convert_constant if pyval is not a typegraph.Variable, otherwise
    just return the Variable. This also handles dict values by constructing a
    new abstract value representing it. Dict values are not cached.

    Args:
      name: The name to give to the variable.
      pyval: The python value, PyTD value, or Variable to convert or pass
        through.
    Returns:
      A Variable that may be the one passed in or one in the convert_constant
      cache.
    """
    if isinstance(pyval, typegraph.Variable):
      return pyval
    elif isinstance(pyval, abstract.AtomicAbstractValue):
      return pyval.to_variable(name)
    elif isinstance(pyval, dict):
      value = abstract.LazyAbstractOrConcreteValue(
          name,
          pyval,  # for class members
          member_map=pyval,
          resolver=self.maybe_convert_constant,
          vm=self)
      value.set_attribute("__class__", self.dict_type)
      return value.to_variable(name)
    else:
      return self.convert_constant(name, pyval)

  def make_none(self):
    # TODO(kramm): This should make a new Variable, but not a new instance.
    return self.instantiate_builtin(types.NoneType)

  def make_class(self, name_var, bases, members):
    """Create a class with the name, bases and methods given.

    Args:
      name_var: Class name.
      bases: Base classes.
      members: Members of the class.

    Returns:
      An instance of Class.
    """
    name = _get_atomic_python_constant(name_var)
    log.info("Declaring class %s")
    val = abstract.InterpreterClass(
        name,
        [_get_atomic_value(b)
         for b in _get_atomic_python_constant(bases)],
        _get_atomic_value(members).members,
        self)
    var = self.program.NewVariable(name)
    var.AddValue(val, bases.values + members.values, self.current_location)
    self.trace_classdef(name, var)
    return var

  def make_instance(self, cls, args, kws):
    """Create an instance of the given class with the given constructor args.

    Args:
      cls: Class to instantiate
      args: Extra positional arguments to pass to __new__ and __init__
      kws: Extra keyword arguments to pass to __new__ and __init__

    Raises:
      TypeError: if this is called.
    """
    raise TypeError("TypegraphVirtualMachine should never allow this to be "
                    "called")

  def make_function(self, name, code, globs, defaults, closure=None):
    """Create a function or closure given the arguments."""
    if closure:
      closure = tuple(c for c in _get_atomic_python_constant(closure))
      log.info("closure: %r", closure)
    if not name:
      if _get_atomic_python_constant(code).co_name:
        name = "<function:%s>" % _get_atomic_python_constant(code).co_name
      else:
        name = "<lambda>"
    val = abstract.InterpreterFunction(name,
                                       code=_get_atomic_python_constant(code),
                                       f_locals=self.frame.f_locals,
                                       f_globals=globs,
                                       defaults=defaults,
                                       closure=closure,
                                       vm=self)
    # TODO(ampere): What else needs to be an origin in this case? Probably stuff
    # in closure.
    var = self.program.NewVariable(name)
    var.AddValue(val, code.values, self.current_location)
    if closure is None:
      self.trace_functiondef(name, var)
    return var

  def make_frame(self, code, callargs=None,
                 f_globals=None, f_locals=None, closure=None):
    """Create a new frame object, using the given args, globals and locals."""
    log.info("make_frame: code=%r, callargs=%s, f_globals=%r, f_locals=%r",
             code, self.repper(callargs), (type(f_globals), id(f_globals)),
             (type(f_locals), id(f_locals)))
    if f_globals is not None:
      f_globals = f_globals
      if f_locals is None:
        f_locals = f_globals
    elif self.frames:
      f_globals = self.frame.f_globals
      f_locals = self.convert_locals_or_globals({})
    else:
      # TODO(ampere): __name__, __doc__, __package__ below are not correct
      f_globals = f_locals = self.convert_locals_or_globals({
          "__builtins__": self.vmbuiltins,
          "__name__": "__main__",
          "__doc__": None,
          "__package__": None,
      })

    # Implement NEWLOCALS flag. See Objects/frameobject.c in CPython.
    if code.co_flags & loadmarshal.CodeType.CO_NEWLOCALS:
      f_locals = self.convert_locals_or_globals({})

    return state.Frame(self, code, f_globals, f_locals,
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
      return value is None or _get_atomic_python_constant(value) is None
    except ConversionError:
      return False

  def is_return(self, b1, b2):
    return (pycfg.opcode_is_call(self.frame.f_code.co_code[b1.end]) and
            self.opcodes_are_adjacent(b1.end, b2.begin))

  def process_block_connections(self, block, allow_returns=False):
    # Create a new node to match this one and connect it to all existing
    # neighbors if it is not already.
    cfgnode = self.frame.cfgnode
    if block not in cfgnode:
      cfgnode[block] = self.program.NewCFGNode(block.get_name())
    for other in block.outgoing:
      if other == pycfg.UNKNOWN_TARGET:
        continue
      if other not in cfgnode:
        cfgnode[other] = self.program.NewCFGNode(other.get_name())
      if allow_returns or not self.is_return(block, other):
        cfgnode[block].ConnectTo(cfgnode[other])

  def push_abstract_exception(self):
    tb = self.new_variable("tb")
    value = self.new_variable("value")
    exctype = self.new_variable("exctype")
    self.push(tb, value, exctype)

  def jump(self, jump, why=None):
    """Move the bytecode pointer to `jump`, so it will execute next.

    Jump may be the very next instruction and hence already the value of
    f_lasti. This is used to notify a subclass when a jump was not taken and
    instead we continue to the next instruction.

    Args:
      jump: An integer, location of the instruction to jump to.
      why: Why are we jumping? Might be something like 'exception' or 'break'.
        Can be None, e.g. for simple unconditional jump instructions.

    Returns:
      The new value for 'why'. Returned to dispatch(). This is typically None,
      which means the jump succeeded and we don't need to bubble an exception
      up the chain.
    """
    if why == "exception":
      # Don't actually execute jumps to exception handlers. Instead, terminate
      # processing of the current block.
      return "fatal_exception"
    self.frame.f_lasti = jump
    return None

  def update_location(self):
    """Update self.current_location based on the current instruction.

    Create CFGNodes as needed.

    Returns:
      The new current location.
    """
    frame = self.frame
    if frame:
      block = self.cfg.get_basic_block(frame.f_code, frame.f_lasti)
      self.process_block_connections(block)
      self.current_block = block
      self.current_location = frame.cfgnode[block]
    else:
      block = None
      self.current_location = self.default_location
    return block

  def resume_frame(self, frame):
    # TODO(kramm): The concrete interpreter did this:
    # frame.f_back = self.frame
    # log.info("resume_frame: %r", frame)
    # val = self.run_frame(frame)
    # frame.f_back = None
    # return val
    raise StopIteration()

  def backtrace(self):
    items = []
    for f in self.frames:
      block = self.cfg.get_basic_block(f.f_code, f.f_lasti)
      if block in f.cfgnode:
        cfg_node = f.cfgnode[block]
        items.append("[%d %s]" % (cfg_node.id, cfg_node.name))
      else:
        items.append("{%s}" % block.get_name())
    return " ".join(items)

  def run_code(self, code, f_globals=None, f_locals=None, run_builtins=True):
    """Run a piece of bytecode using the VM."""
    f_locals = self.convert_locals_or_globals(f_locals)
    f_globals = self.convert_locals_or_globals(f_globals)

    # We firsts run self.builtins_codes, which have been loaded from __builtin__.py
    # etc. They are only run for effect, and typically will be a sequence of
    #   LOAD_CONST <code object ...>
    #   MAKE_FUNCTION 0
    #   STORE_NAME '<function name>'
    # (this is Python-2; Python-3 is slightly different)
    # At the end is `RETURN_VALUE None`, so each set of op-codes could also
    # be called by some variant of CALL_FUNCTION.
    # An alternative would be to analyze the code:
    #        {cc.co_name: cc for cc in code.co_consts
    #         if isinstance(cc, types.CodeType)}

    if run_builtins:
      for one_code in self.builtins_codes:
        val, frame, exc, f_globals, f_locals = self.run_one_code(
            one_code, f_globals, f_locals)
      # at the outer layer, locals are the same as globals
      builtin_names = frozenset(f_globals.members)
    else:
      builtin_names = frozenset()
    # Remove the builtins so that "deep" analysis doesn't try to proces them:
    self._functions.clear()
    val, frame, exc, f_globals, f_locals = self.run_one_code(
        code, f_globals, f_locals)
    return val, frame, exc, builtin_names

  def run_one_code(self, code, f_globals, f_locals):
    frame = self.make_frame(code, f_globals=f_globals, f_locals=f_locals)
    try:
      val = self.run_frame(frame)
      exc = None
    except exceptions.ByteCodeException:
      val = None
      exc = sys.exc_info()[1].create_instance()
      # Check some invariants
    if self.frames:      # pragma: no cover
      raise VirtualMachineError("Frames left over!")
    if self.frame is not None and self.frame.data_stack:  # pragma: no cover
      raise VirtualMachineError("Data left on stack! %r" %
                                self.frame.data_stack)
    return val, frame, exc, frame.f_globals, frame.f_locals

  def run_program(self, code):
    """Run the code and return the CFG nodes.

    This function loads in the builtins and puts them ahead of `code`,
    so all the builtins are available when processing `code`.
    """

    _, _, _, builtin_names = self.run_code(code)
    if not self.source_nodes:
      raise VirtualMachineError("Import-level code didn't return")
    main = self.program.NewCFGNode("main")
    self.connect_source_nodes(main)
    return main, builtin_names

  def magic_binary_operator(self, name):
    """Map a binary operator to "magic methods" (__add__ etc.)."""
    # TODO(ampere): Lift this support to VirtualMachine. Sadly that
    # will be tricky since it needs to run two things and then merge the result
    # which is very hard to do in the concrete case.

    # TODO(pludemann): See TODO.txt for more on reverse operator subtleties.

    def magic_operator_wrapper_tg(x, y):
      """A wrapper function that tries both forward and reversed operators."""
      results = []
      try:
        attr = self.load_attr(x, name)
      except exceptions.ByteCodeAttributeError:  # from load_attr
        log.info("Failed to find %s on %r", name, x, exc_info=True)
      else:
        results.append(self.call_function(attr, [y]))
      if self.reverse_operators:
        rname = self.reverse_operator_name(name)
        if rname:
          try:
            attr = self.load_attr(y, rname)
          except exceptions.ByteCodeAttributeError:
            log.info("Failed to find reverse operator %s on %r",
                     self.reverse_operator_name(name),
                     y, exc_info=True)
          else:
            results.append(
                self.call_function(attr, [x]))
      log.debug("Results: %r", results)
      return self.join_variables(name, results)
    return magic_operator_wrapper_tg

  def trace_call(self, *args):
    return NotImplemented

  def trace_unknown(self, *args):
    """Fired whenever we create a variable containing 'Unknown'."""
    return NotImplemented

  def trace_classdef(self, *args):
    return NotImplemented

  def trace_functiondef(self, *args):
    return NotImplemented

  def call_function(self, funcu, posargs, namedargs=None):
    """Call a function.

    Args:
      funcu: A variable of the possible functions to call.
      posargs: The positional arguments to pass (as variables).
      namedargs: The keyword arguments to pass.
    Returns:
      The return value of the called function.
    """
    result = self.program.NewVariable("<return:%s>" % funcu.name)
    for funcv in funcu.values:
      func = funcv.data
      assert isinstance(func, abstract.AtomicAbstractValue), type(func)
      try:
        one_result = func.call(funcv, posargs, namedargs or {})
      except abstract.FailedFunctionCall as e:
        log.error("FailedFunctionCall for %s", e.obj)
        for msg in e.explanation_lines:
          log.error("... %s", msg)
      else:
        result.AddValues(one_result, self.current_location)
    self.trace_call(funcu, posargs, namedargs, result)
    return result

  def call_function_from_stack(self, arg, args, kwargs=None):
    """Pop arguments for a function and call it."""
    num_kw, num_pos = divmod(arg, 256)
    namedargs = abstract.Dict("kwargs", self)
    for _ in range(num_kw):
      key, val = self.popn(2)
      namedargs.setitem(key, val)
    if kwargs:
      namedargs.update(kwargs)
    posargs = self.popn(num_pos)
    posargs.extend(args)
    func = self.pop()
    self.push(self.call_function(func, posargs, namedargs))

  def load_constant(self, value):
    """Converts a Python value to an abstract value."""
    return self.convert_constant(type(value).__name__, value)

  def get_locals_dict(self):
    """Get a real python dict of the locals."""
    return self.frame.f_locals

  def get_locals_dict_bytecode(self):
    """Get a possibly abstract bytecode level representation of the locals."""
    # TODO(ampere): Origins
    log.debug("Returning locals: %r -> %r", self.frame.f_locals,
              self.frame.f_locals)
    return self.maybe_convert_constant("locals", self.frame.f_locals)

  def set_locals_dict_bytecode(self, lcls):
    """Set the locals from a possibly abstract bytecode level dict."""
    self.frame.f_locals = _get_atomic_value(lcls)

  def get_globals_dict(self):
    """Get a real python dict of the globals."""
    return self.frame.f_globals

  @staticmethod
  def load_from(store, name):
    if not store.has_attribute(name):
      raise KeyError(name)
    return store.get_attribute(name)

  def load_local(self, name):
    """Called when a local is loaded onto the stack.

    Uses the name to retrieve the value from the current locals().

    Args:
      name: Name of the local

    Returns:
      The value (typegraph.Variable)
    """
    return self.load_from(self.frame.f_locals, name)

  def load_global(self, name):
    return self.load_from(self.frame.f_globals, name)

  def load_builtin(self, name):
    if name == "__any_object__":
      # for type_inferencer/tests/test_pgms/*.py
      return abstract.Unknown(self).to_variable(name)
    return self.load_from(self.frame.f_builtins, name)

  def store_local(self, name, value):
    """Called when a local is written."""
    assert isinstance(value, typegraph.Variable), (name, repr(value))
    self.frame.f_locals.set_attribute(name, value)
    abstract.variable_set_official_name(value, name)

  def store_global(self, name, value):
    """Same as store_local except for globals."""
    assert isinstance(value, typegraph.Variable)
    self.frame.f_globals.set_attribute(name, value)

  def del_local(self, name):
    """Called when a local is deleted."""
    # TODO(ampere): Implement locals removal or decide not to.
    log.warning("Local variable removal does not actually do "
                "anything in the abstract interpreter")

  def load_attr(self, obj, attr):
    """Load an attribute from an object."""
    assert isinstance(obj, typegraph.Variable)
    # Resolve the value independently for each value of obj
    result = self.program.NewVariable(str(attr))
    log.debug("getting attr %s from %r", attr, obj)
    for val in obj.values:
      if not val.data.has_attribute(attr, val):
        log.debug("No %s on %s", attr, val.data.__class__)
        continue
      attr_var = val.data.get_attribute(attr, val)
      log.debug("got choice for attr %s from %r of %r (0x%x): %r", attr, obj,
                val.data, id(val.data), attr_var)
      if not attr_var:
        continue
      # Loop over the values to check for properties
      for v in attr_var.values:
        value = v.data
        if not value.has_attribute("__get__"):
          result.AddValue(value, [v], self.current_location)
        else:
          getter = value.get_attribute("__get__", v)
          params = [getter,
                    value.get_attribute("__class__", val)]
          get_result = self.call_function(getter, params)
          for getter in get_result.values:
            result.AddValue(getter.data, [getter], self.current_location)
    if not result.values:
      raise exceptions.ByteCodeAttributeError("No such attribute %s" % attr)
    return result

  def store_attr(self, obj, attr, value):
    """Same as load_attr except for setting attributes."""
    assert isinstance(obj, typegraph.Variable)
    assert isinstance(attr, str)
    assert isinstance(value, typegraph.Variable)

    for val in obj.values:
      # TODO(kramm): Check for __set__ on val.data
      val.data.set_attribute(attr, value)

  def del_attr(self, obj, attr):
    """Same as load_attr except for deleting attributes."""
    log.warning("Attribute removal does not actually do "
                "anything in the abstract interpreter")

  def build_string(self, s):
    str_value = abstract.AbstractOrConcreteValue(repr(s), s, self)
    str_value.set_attribute("__class__", self.str_type)
    return str_value.to_variable(name=repr(s))

  def build_content(self, elements):
    var = self.program.NewVariable("<elements>")
    for v in elements:
      var.AddValues(v, self.current_location)
    return var

  def build_slice(self, start, stop, step=None):
    value = abstract.SimpleAbstractValue("slice", self)
    value.set_attribute("__class__", self.slice_type)
    return value.to_variable(name="slice")

  def build_tuple(self, content):
    """Create a VM tuple from the given sequence."""
    content = tuple(content)  # content might be a generator
    value = abstract.AbstractOrConcreteValue("tuple", content, self)
    value.set_attribute("__class__", self.tuple_type)
    value.overwrite_type_parameter("T", self.build_content(content))
    return value.to_variable(name="tuple(...)")

  def build_list(self, content):
    """Create a VM list from the given sequence."""
    content = list(content)  # content might be a generator
    value = abstract.SimpleAbstractValue("list", self)
    value.set_attribute("__class__", self.list_type)
    value.overwrite_type_parameter("T", self.build_content(content))
    return value.to_variable(name="list(...)")

  def build_set(self, content):
    """Create a VM set from the given sequence."""
    content = list(content)  # content might be a generator
    value = abstract.SimpleAbstractValue("set", self)
    value.set_attribute("__class__", self.set_type)
    value.overwrite_type_parameter("T", self.build_content(content))
    return value.to_variable(name="set(...)")

  def build_map(self):
    """Create an empty VM dict."""
    return abstract.Dict("dict()", self).to_variable("dict()")

  def isinstance(self, obj, classes):
    # TODO(ampere): Implement this to add support for isinstance in analyzed
    # code.
    raise NotImplementedError

  def push_last_exception(self):
    log.info("Pushing exception %r", self.last_exception)
    exctype, value, tb = self.last_exception
    self.push(tb, value, exctype)
    self.push(tb, value, exctype)

  def del_subscr(self, obj, subscr):
    log.warning("Subscript removal does not actually do "
                "anything in the abstract interpreter")

  def pop_varargs(self):
    """Retrieve a varargs tuple from the stack. Used by call_function."""
    args_var = self.pop()
    try:
      args = _get_atomic_python_constant(args_var)
      if not isinstance(args, tuple):
        raise ConversionError(type(args))
    except ConversionError:
      # If the *args parameter is non-trivial, just try calling with no
      # arguments.
      # TODO(kramm): When calling a method, we should instead insert Unknown for
      # all parameters that are not otherwise set.
      log.error("Unable to resolve positional arguments: *%s", args_var.name)
      args = []
    return args

  def pop_kwargs(self):
    """Retrieve a kwargs dictionary from the stack. Used by call_function."""
    return self.pop()

  def convert_locals_or_globals(self, d):
    if isinstance(d, dict):
      return abstract.LazyAbstractValue(
          "locals/globals", d, self.maybe_convert_constant, self)
    else:
      assert isinstance(d, (abstract.LazyAbstractValue, types.NoneType))
      return d

  def import_name(self, name, level):
    """Import the module and return the module object."""
    try:
      ast = import_paths.module_name_to_pytd(name, level,
                                             self.python_version)
    except IOError:
      log.error("Couldn't find module %s", name)
      return abstract.Unknown(self).to_variable(name)
    return self.convert_constant(name, ast)

  def print_item(self, item, to=None):
    # We don't need do anything here, since Python's print function accepts
    # any type. (We could exercise the __str__ method on item - but every
    # object has a __str__, so we wouldn't learn anything from that.)
    pass

  def print_newline(self, to=None):
    pass

  def byte_LOAD_CONST(self, const):
    self.push(self.load_constant(const))

  def byte_POP_TOP(self):
    self.pop()

  def byte_DUP_TOP(self):
    self.push(self.top())

  def byte_DUP_TOPX(self, count):
    items = self.popn(count)
    self.push(*items)
    self.push(*items)

  def byte_DUP_TOP_TWO(self):
    # Py3 only
    a, b = self.popn(2)
    self.push(a, b, a, b)

  def byte_ROT_TWO(self):
    a, b = self.popn(2)
    self.push(b, a)

  def byte_ROT_THREE(self):
    a, b, c = self.popn(3)
    self.push(c, a, b)

  def byte_ROT_FOUR(self):
    a, b, c, d = self.popn(4)
    self.push(d, a, b, c)

  def byte_LOAD_NAME(self, name):
    """Load a name. Can be a local, global, or builtin."""
    try:
      val = self.load_local(name)
    except KeyError:
      try:
        val = self.load_global(name)
      except KeyError:
        try:
          val = self.load_builtin(name)
        except KeyError:
          raise exceptions.ByteCodeNameError("name '%s' is not defined" % name)
    self.push(val)

  def byte_STORE_NAME(self, name):
    self.store_local(name, self.pop())

  def byte_DELETE_NAME(self, name):
    self.del_local(name)

  def byte_LOAD_FAST(self, name):
    """Load a local. Unlike LOAD_NAME, it doesn't fall back to globals."""
    try:
      val = self.load_local(name)
    except KeyError:
      raise exceptions.ByteCodeUnboundLocalError(
          "local variable '%s' referenced before assignment" % name
      )
    self.push(val)

  def byte_STORE_FAST(self, name):
    self.byte_STORE_NAME(name)

  def byte_DELETE_FAST(self, name):
    self.byte_DELETE_NAME(name)

  def byte_LOAD_GLOBAL(self, name):
    try:
      val = self.load_global(name)
    except KeyError:
      try:
        val = self.load_builtin(name)
      except KeyError:
        raise exceptions.ByteCodeNameError(
            "global name '%s' is not defined" % name)
    self.push(val)

  def byte_STORE_GLOBAL(self, name):
    self.store_global(name, self.pop())

  def byte_LOAD_CLOSURE(self, i):
    """Used to generate the 'closure' tuple for MAKE_CLOSURE.

    Each entry in that tuple is typically retrieved using LOAD_CLOSURE.

    Args:
      i: The index of a "cell variable": This corresponds to an entry in
        co_cellvars or co_freevars and is a variable that's bound into
        a closure.
    """
    self.push(self.frame.cells[i])

  def byte_LOAD_DEREF(self, i):
    """Retrieves a value out of a cell."""
    # Since we're working on typegraph.Variable, we don't need to dereference.
    self.push(self.frame.cells[i])

  def byte_STORE_DEREF(self, i):
    """Stores a value in a closure cell."""
    value = self.pop()
    assert isinstance(value, typegraph.Variable)
    self.frame.cells[i].AddValues(value, self.current_location)

  def byte_LOAD_LOCALS(self):
    self.push(self.get_locals_dict_bytecode())

  def byte_COMPARE_OP(self, opnum):
    x, y = self.popn(2)
    self.push(self.compare_operators[opnum](x, y))

  def byte_LOAD_ATTR(self, attr):
    obj = self.pop()
    log.info("LOAD_ATTR: %r %s", type(obj), attr)
    val = self.load_attr(obj, attr)
    self.push(val)

  def byte_STORE_ATTR(self, name):
    val, obj = self.popn(2)
    self.store_attr(obj, name, val)

  def byte_DELETE_ATTR(self, name):
    obj = self.pop()
    self.del_attr(obj, name)

  def byte_STORE_SUBSCR(self):
    val, obj, subscr = self.popn(3)
    self.store_subscr(obj, subscr, val)

  def byte_DELETE_SUBSCR(self):
    obj, subscr = self.popn(2)
    self.del_subscr(obj, subscr)

  def byte_BUILD_TUPLE(self, count):
    elts = self.popn(count)
    self.push(self.build_tuple(elts))

  def byte_BUILD_LIST(self, count):
    elts = self.popn(count)
    self.push(self.build_list(elts))

  def byte_BUILD_SET(self, count):
    # TODO(kramm): Not documented in Py2 docs.
    elts = self.popn(count)
    self.push(self.build_set(elts))

  def byte_BUILD_MAP(self, size):
    # size is ignored.
    self.push(self.build_map())

  def byte_STORE_MAP(self):
    # pylint: disable=unbalanced-tuple-unpacking
    the_map, val, key = self.popn(3)
    self.store_subscr(the_map, key, val)
    self.push(the_map)

  def byte_UNPACK_SEQUENCE(self, count):
    seq = self.pop()
    itr = self.call_function(self.load_attr(seq, "__iter__"), [], {})
    values = []
    for _ in range(count):
      # TODO(ampere): Fix for python 3
      values.append(self.call_function(self.load_attr(itr, "next"),
                                       [], {}))
    for value in reversed(values):
      self.push(value)

  def byte_BUILD_SLICE(self, count):
    if count == 2:
      x, y = self.popn(2)
      self.push(self.build_slice(x, y))
    elif count == 3:
      x, y, z = self.popn(3)
      self.push(self.build_slice(x, y, z))
    else:       # pragma: no cover
      raise VirtualMachineError("Strange BUILD_SLICE count: %r" % count)

  def byte_LIST_APPEND(self, count):
    # Used by the compiler e.g. for [x for x in ...]
    val = self.pop()
    the_list = self.peek(count)
    self.call_function(self.load_attr(the_list, "append"), [val], {})

  def byte_SET_ADD(self, count):
    # Used by the compiler e.g. for {x for x in ...}
    val = self.pop()
    the_set = self.peek(count)
    self.call_function(self.load_attr(the_set, "add"), [val], {})

  def byte_MAP_ADD(self, count):
    # Used by the compiler e.g. for {x, y for x, y in ...}
    val, key = self.popn(2)
    the_map = self.peek(count)
    self.call_function(self.load_attr(the_map, "__setitem__"),
                       [key, val], {})

  def byte_PRINT_EXPR(self):
    # Only used in the interactive interpreter, not in modules.
    self.pop()

  def byte_PRINT_ITEM(self):
    item = self.pop()
    self.print_item(item)

  def byte_PRINT_ITEM_TO(self):
    to = self.pop()
    item = self.pop()
    self.print_item(item, to)

  def byte_PRINT_NEWLINE(self):
    self.print_newline()

  def byte_PRINT_NEWLINE_TO(self):
    to = self.pop()
    self.print_newline(to)

  def byte_JUMP_IF_TRUE_OR_POP(self, jump):
    self.pop()

  def byte_JUMP_IF_FALSE_OR_POP(self, jump):
    self.pop()

  def byte_JUMP_IF_TRUE(self, jump):  # Not in py2.7
    pass

  def byte_JUMP_IF_FALSE(self, jump):  # Not in py2.7
    pass

  def byte_POP_JUMP_IF_TRUE(self, jump):
    self.pop()

  def byte_POP_JUMP_IF_FALSE(self, jump):
    self.pop()

  def byte_JUMP_FORWARD(self, jump):
    return self.jump(jump)

  def byte_JUMP_ABSOLUTE(self, jump):
    return self.jump(jump)

  def byte_SETUP_LOOP(self, dest):
    self.push_block("loop", dest)

  def byte_GET_ITER(self):
    self.push(self.load_attr(self.pop(), "__iter__"))
    self.call_function_from_stack(0, [])

  def byte_FOR_ITER(self, jump):
    self.push(self.load_attr(self.top(), "next"))
    try:
      self.call_function_from_stack(0, [])
      # The loop is still running, so just continue with the next instruction.
      return None
    except StopIteration:
      self.pop()
      return self.jump(jump)

  def byte_BREAK_LOOP(self):
    return "break"

  def byte_CONTINUE_LOOP(self, dest):
    # This is a trick with the return value.
    # While unrolling blocks, continue and return both have to preserve
    # state as the finally blocks are executed.  For continue, it's
    # where to jump to, for return, it's the value to return.  It gets
    # pushed on the stack for both, so continue puts the jump destination
    # into return_value.
    self.return_value = dest
    return "continue"

  def byte_SETUP_EXCEPT(self, dest):
    self.push_block("setup-except", dest)

  def byte_SETUP_FINALLY(self, dest):
    self.push_block("finally", dest)

  def byte_POP_BLOCK(self):
    self.pop_block()

  def byte_RAISE_VARARGS_PY2(self, argc):
    """Raise an exception (Python 2 version)."""
    # NOTE: the dis docs are completely wrong about the order of the
    # operands on the stack!
    exctype = val = tb = None
    if argc == 0:
      if self.last_exception is None:
        raise exceptions.ByteCodeTypeError(
            "exceptions must be old-style classes "
            "or derived from BaseException, not NoneType")
      exctype, val, tb = self.last_exception
    elif argc == 1:
      exctype = self.pop()
    elif argc == 2:
      val = self.pop()
      exctype = self.pop()
    elif argc == 3:
      tb = self.pop()
      val = self.pop()
      exctype = self.pop()
    # There are a number of forms of "raise", normalize them somewhat.
    if isinstance(exctype, BaseException):
      val = exctype
      exctype = type(val)
    self.last_exception = (exctype, val, tb)
    if tb:
      return "reraise"
    else:
      return "exception"

  def byte_RAISE_VARARGS_PY3(self, argc):
    """Raise an exception (Python 3 version)."""
    cause = exc = None
    if argc == 2:
      cause = self.pop()
      exc = self.pop()
    elif argc == 1:
      exc = self.pop()
    return self.do_raise(exc, cause)

  def byte_RAISE_VARARGS(self, argc):
    if self.python_version[0] == 2:
      return self.byte_RAISE_VARARGS_PY2(argc)
    else:
      return self.byte_RAISE_VARARGS_PY3(argc)

  def byte_POP_EXCEPT(self):
    block = self.pop_block()
    if block.type != "except-handler":
      raise VirtualMachineError("popped block is not an except handler")
    self.unwind_block(block)

  def byte_SETUP_WITH(self, dest):
    ctxmgr = self.pop()
    self.push(self.load_attr(ctxmgr, "__exit__"))
    ctxmgr_obj = self.call_function(self.load_attr(ctxmgr, "__enter__"), [])
    if self.python_version[0] == 2:
      self.push_block("with", dest)
    else:
      assert self.python_version[0] == 3
      self.push_block("finally", dest)
    self.push(ctxmgr_obj)

  def byte_WITH_CLEANUP(self):
    """Called at the end of a with block. Calls the exit handlers etc."""
    # The code here does some weird stack manipulation: the exit function
    # is buried in the stack, and where depends on what's on top of it.
    # Pull out the exit function, and leave the rest in place.
    u = self.top()
    if isinstance(u, str):
      if u in ("return", "continue"):
        exit_func = self.pop(2)
      else:
        exit_func = self.pop(1)
      v = self.make_none()
      w = self.make_none()
      u = self.make_none()
    elif isinstance(u, type) and issubclass(u, BaseException):
      if self.python_version[0] == 2:
        w, v, u = self.popn(3)
        exit_func = self.pop()
        self.push(w, v, u)
      else:
        assert self.python_version[0] == 3
        w, v, u = self.popn(3)
        tp, exc, tb = self.popn(3)
        exit_func = self.pop()
        self.push(tp, exc, tb)
        self.push(self.make_none())
        self.push(w, v, u)
        block = self.pop_block()
        assert block.type == "except-handler"
        self.push_block(block.type, block.handler, block.level - 1)
    else:
      # This is the case when None just got pushed to the top of the stack,
      # to signal that we're at the end of the with block and no exception
      # occured.
      self.pop()  # pop None
      exit_func = self.pop()
      self.push(self.make_none())
      v = self.make_none()
      w = self.make_none()
    suppress_exception = self.call_function(exit_func, [u, v, w])
    log.info("u is None: %r", self.is_none(u))
    err = (not self.is_none(u)) and bool(suppress_exception)
    if err:
      # An error occurred, and was suppressed
      if self.python_version[0] == 2:
        self.popn(3)
        self.push(self.make_none())
      else:
        assert self.python_version[0] == 3
        self.push("silenced")

  def byte_MAKE_FUNCTION(self, argc):
    """Create a function and push it onto the stack."""
    if self.python_version[0] == 2:
      name = None
    else:
      assert self.python_version[0] == 3
      name = self.pop()
    code = self.pop()
    defaults = self.popn(argc)
    globs = self.get_globals_dict()
    fn = self.make_function(name, code, globs, defaults)
    self.push(fn)

  def byte_MAKE_CLOSURE(self, argc):
    """Make a function that binds local variables."""
    if self.python_version[0] == 2:
      # The py3 docs don't mention this change.
      name = None
    else:
      assert self.python_version[0] == 3
      name = _get_atomic_python_constant(self.pop())
    closure, code = self.popn(2)
    defaults = self.popn(argc)
    globs = self.get_globals_dict()
    fn = self.make_function(name, code, globs, defaults, closure)
    self.push(fn)

  def byte_CALL_FUNCTION(self, arg):
    return self.call_function_from_stack(arg, [])

  def byte_CALL_FUNCTION_VAR(self, arg):
    args = self.pop_varargs()
    return self.call_function_from_stack(arg, args)

  def byte_CALL_FUNCTION_KW(self, arg):
    kwargs = self.pop_kwargs()
    return self.call_function_from_stack(arg, [], kwargs)

  def byte_CALL_FUNCTION_VAR_KW(self, arg):
    kwargs = self.pop_kwargs()
    args = self.pop_varargs()
    return self.call_function_from_stack(arg, args, kwargs)

  def byte_YIELD_VALUE(self):
    self.return_value = self.pop()
    return "yield"

  def byte_IMPORT_NAME(self, name):
    level, unused_fromlist = self.popn(2)
    self.push(self.import_name(name, level))
    # TODO(kramm): Do something meaningful with "fromlist"?

  def byte_IMPORT_FROM(self, name):
    mod = self.top()
    self.push(self.get_module_attribute(mod, name))

  def byte_EXEC_STMT(self):
    unused_stmt, unused_globs, unused_locs = self.popn(3)
    log.warning("Encountered 'exec' statement. 'exec' is unsupported.")

  def byte_BUILD_CLASS(self):
    name, bases, methods = self.popn(3)
    self.push(self.make_class(name, bases, methods))

  def byte_LOAD_BUILD_CLASS(self):
    # New in py3
    self.push(__build_class__)  # pylint: disable=undefined-variable

  def byte_STORE_LOCALS(self):
    self.set_locals_dict_bytecode(self.pop())

  # Removed in py2.7
  def byte_SET_LINENO(self, lineno):
    self.frame.f_lineno = lineno

  def byte_END_FINALLY(self):
    # TODO(kramm): The below is that the concrete interpreter did. Do we need
    # any of that code in the abstract interpretation?
    # v = self.pop()
    # if isinstance(v, str):
    #   why = v
    #   if why in ("return", "continue"):
    #     self.return_value = self.pop()
    #   if why == "silenced":     # PY3
    #     block = self.pop_block()
    #     assert block.type == "except-handler"
    #     self.unwind_block(block)
    #     why = None
    # elif v is None:
    #   why = None
    # elif issubclass(v, BaseException):
    #   exctype = v
    #   val = self.pop()
    #   tb = self.pop()
    #   self.last_exception = (exctype, val, tb)
    #   why = "reraise"
    # else:     # pragma: no cover
    #   raise VirtualMachineError("Confused END_FINALLY")
    # return why
    # TODO(kramm): Return a fitting why
    self.pop()

  def byte_RETURN_VALUE(self):
    self.frame.return_variable.AddValues(self.pop(), self.current_location)
    return "return"

  def byte_IMPORT_STAR(self):
    # TODO(kramm): this doesn't use __all__ properly.
    mod = _get_atomic_value(self.pop())
    if isinstance(mod, abstract.Unknown):
      log.error("Doing 'from module import *' from unresolved module")
      return
    log.info("%r", mod)
    # TODO(kramm): Add Module type to abstract.py
    for name, var in mod.items():
      if name[0] != "_":
        self.store_local(name, var)
