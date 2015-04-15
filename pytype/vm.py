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
import linecache
import logging
import re
import repr as reprlib
import sys
import types


from pytype import abstract
from pytype import blocks
from pytype import exceptions
from pytype import import_paths
from pytype import state as frame_state
from pytype import utils
from pytype.pyc import loadmarshal
from pytype.pyc import pyc
from pytype.pytd import cfg as typegraph
from pytype.pytd import pytd
from pytype.pytd import slots
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import builtins

log = logging.getLogger(__name__)


# Create a repr that won't overflow.
_TRUNCATE = 120
_TRUNCATE_STR = 72
repr_obj = reprlib.Repr()
repr_obj.maxother = _TRUNCATE
repr_obj.maxstring = _TRUNCATE_STR
repper = repr_obj.repr


Block = collections.namedtuple("Block", ["type", "handler", "level"])


class ConversionError(ValueError):
  pass


class RecursionException(Exception):
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
    self.vmbuiltins = dict(__builtins__)
    self.vmbuiltins["isinstance"] = self.isinstance
    self._cache_linestarts = {}  # maps frame.f_code => list of (offset, lineno)

    self.program = typegraph.Program()

    self.root_cfg_node = self.program.NewCFGNode("root")
    self.program.entrypoint = self.root_cfg_node

    # Used if we don't have a frame (e.g. when setting up an artificial function
    # call):
    self.default_location = self.root_cfg_node

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

    self.vmbuiltins = {}
    self._set_vmbuiltin("constant", self.builtins_pytd.constants)
    self._set_vmbuiltin("class", self.builtins_pytd.classes)
    self._set_vmbuiltin("function", self.builtins_pytd.functions)
    # Do not do the following because all modules must be explicitly imported.
    # self._set_vmbuiltin("module", self.builtins_pytd.modules)

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
    self.frame.current_op = op
    self.frame.state = state
    if log.isEnabledFor(logging.INFO):
      self.log_opcode(op, state)
    try:
      # dispatch
      bytecode_fn = getattr(self, "byte_%s" % op.name, None)
      if bytecode_fn is None:
        raise VirtualMachineError("Unknown opcode: %s" % op.name)
      if op.has_arg():
        why = bytecode_fn(op)
      else:
        why = bytecode_fn()
    except StopIteration:
      # TODO(kramm): Use abstract types for this.
      self.frame.state = self.frame.state.set_exception(
          sys.exc_info()[0], sys.exc_info()[1], None)
      why = "exception"
    except RecursionException as e:
      # This is not an error - it just means that the block we're analyzing
      # goes into a recursion, and we're already two levels deep.
      why = "recursion"
    except exceptions.ByteCodeException:
      e = sys.exc_info()[1]
      self.frame.state = self.frame.state.set_exception(
          e.exception_type, e.create_instance(), None)
      # TODO(pludemann): capture exceptions that are indicative of
      #                  a bug (AttributeError?)
      log.info("Exception in program: %s: %r",
               e.exception_type.__name__, e.message)
      why = "exception"
    state = self.frame.state
    del self.frame.state
    if why == "reraise":
      why = "exception"
    return why, state

  def join_cfg_nodes(self, nodes):
    assert nodes
    if len(nodes) == 1:
      return nodes[0]
    else:
      ret = self.program.NewCFGNode("ret")
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
        log.error("Skipping block %d,"
                  " we don't have any non errorneous code that goes here.",
                  block.id)
        continue
      op = None
      for op in block:
        why, state = self.run_instruction(op, state)
        if why:
          # we can't process this block any further
          break
      if why in ["return", "yield"]:
        return_nodes.append(state.node)
      if not why and op.carry_on_to_next():
        frame.states[op.next] = state.merge_into(frame.states.get(op.next))
    self.pop_frame(frame)
    if not return_nodes:
      # Happens if all the function does is to throw an exception.
      # (E.g. "def f(): raise NoImplemented")
      # TODO(kramm): Return the exceptions, too.
      return node, frame.return_variable
    return self.join_cfg_nodes(return_nodes), frame.return_variable

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

  @property
  def current_location(self):
    if self.frame:
      return self.frame.state.node
    else:
      return self.root_cfg_node

  def top(self):
    """Return the value at the top of the stack, with no changes."""
    return self.frame.state.data_stack[-1]

  def pop_nth(self, i=0):
    """Pop top value from the stack.

    Default to the top of the stack, but `i` can be a count from the top
    instead.

    Arguments:
      i: If this is given, a value is extracted and removed from the middle
      of the stack.

    Returns:
      A stack entry (typegraph.Variable).
    """
    raise NotImplementedError()

  def pop(self):
    """Pop top value from the value stack."""
    self.frame.state, value = self.frame.state.pop()
    return value

  def push(self, *vals):
    """Push values onto the value stack."""
    self.frame.state = self.frame.state.push(*vals)

  def popn(self, n):
    """Pop a number of values from the value stack.

    A list of `n` values is returned, the deepest value first.

    Arguments:
      n: The number of items to pop

    Returns:
      A list of n values.
    """
    self.frame.state, values = self.frame.state.popn(n)
    return values

  def peek(self, n):
    """Get a value `n` entries down in the stack, without changing the stack."""
    return self.frame.state.data_stack[-n]

  def push_block(self, t, handler=None, level=None):
    if level is None:
      level = len(self.frame.state.data_stack)
    self.frame.state = self.frame.state.push_block(Block(t, handler, level))

  def pop_block(self):
    self.frame.state, block = self.frame.state.pop_block()
    return block

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

  def unwind_block(self, block, state):
    """Adjusts the data stack to account for removing the passed block."""
    if block.type == "except-handler":
      offset = 3
    else:
      offset = 0

    while len(state.data_stack) > block.level + offset:
      state = state.pop_and_discard()

    if block.type == "except-handler":
      state, (tb, value, exctype) = state.popn(3)
      state = state.set_exception(exctype, value, tb)
    return state

  def log_opcode(self, op, state):
    """Write a multi-line log message, including backtrace and stack."""
    if not log.isEnabledFor(logging.INFO):
      return
    # pylint: disable=logging-not-lazy
    indent = " > " * (len(self.frames) - 1)
    stack_rep = repper(self.frame.state.data_stack)
    block_stack_rep = repper(self.frame.state.block_stack)
    # TODO(pludemann): nicer module/file name:
    if self.frame.f_code.co_filename:
      module_name = ".".join(re.sub(
          r"\.py$", "", self.frame.f_code.co_filename).split("/")[-2:])
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

  def pop_slice_and_obj(self, count):
    """Pop a slice from the data stack. Used by slice opcodes (SLICE_0 etc.)."""
    start = 0
    end = None      # we will take this to mean end
    if count == 1:
      start = self.pop()
    elif count == 2:
      end = self.pop()
    elif count == 3:
      end = self.pop()
      start = self.pop()
    obj = self.pop()
    if end is None:
      # TODO(kramm): Does Python do this, too?
      end = self.call_function(self.load_attr(obj, "__len__"), [], {})
    return self.build_slice(start, end, 1), obj

  def store_slice(self, count):
    slice_obj, obj = self.pop_slice_and_obj(count)
    new_value = self.pop()
    self.call_function(self.load_attr(obj, "__setitem__"),
                       [slice_obj, new_value], {})

  def delete_slice(self, count):
    slice_obj, obj = self.pop_slice_and_obj(count)
    self.call_function(self.load_attr(obj, "__delitem__"),
                       [slice_obj], {})

  def get_slice(self, count):
    slice_obj, obj = self.pop_slice_and_obj(count)
    ret = self.call_function(self.load_attr(obj, "__getitem__"),
                             [slice_obj], {})
    self.push(ret)

  def do_raise(self, exc, cause):
    """Raise an exception. Used by byte_RAISE_VARARGS."""
    if exc is None:     # reraise
      exc_type, val, _ = self.frame.state.last_exception
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

    self.frame.state.set_exception(exc_type, val, val.__traceback__)
    return "exception"

  # Importing

  def get_module_attribute(self, mod, name):
    """Return the modules members as a dict."""
    return self.load_attr(mod, name)

  def _set_vmbuiltin(self, descr, values):
    for b in values:
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
      return value
    elif isinstance(pyval, (loadmarshal.CodeType, blocks.OrderedCode)):
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
    none = abstract.AbstractOrConcreteValue("None", None, self)
    none.set_attribute("__class__", self.primitive_classes[type(None)])
    none = none.to_variable("None")
    assert self.is_none(none)
    return none

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
    log.info("Declaring class %s", name)
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
    if any(code is f.f_code for f in self.frames):
      log.info("Detected recursion in %s", code.co_name or code.co_filename)
      raise RecursionException()

    log.info("make_frame: callargs=%s, f_globals=[%s@%x], f_locals=[%s@%x]",
             self.repper(callargs),
             type(f_globals).__name__, id(f_globals),
             type(f_locals).__name__, id(f_locals))
    if f_globals is not None:
      f_globals = f_globals
      if f_locals is None:
        f_locals = f_globals
    elif self.frames:
      assert f_locals is None
      f_globals = self.frame.f_globals
      f_locals = self.convert_locals_or_globals({}, "locals")
    else:
      assert f_locals is None
      # TODO(ampere): __name__, __doc__, __package__ below are not correct
      f_globals = f_locals = self.convert_locals_or_globals({
          "__builtins__": self.vmbuiltins,
          "__name__": "__main__",
          "__doc__": None,
          "__package__": None,
      })

    # Implement NEWLOCALS flag. See Objects/frameobject.c in CPython.
    if code.co_flags & loadmarshal.CodeType.CO_NEWLOCALS:
      f_locals = self.convert_locals_or_globals({}, "locals")

    return frame_state.Frame(self, code, f_globals, f_locals,
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

  def push_abstract_exception(self, state):
    tb = self.new_variable("tb")
    value = self.new_variable("value")
    exctype = self.new_variable("exctype")
    return state.push(tb, value, exctype)

  def jump(self, jump, why=None):
    raise NotImplementedError("Use store_jump instead")
    # TODO(kramm):
    # if why == "exception":
    #   # Don't actually execute jumps to exception handlers. Instead, terminate
    #   # processing of the current block.
    #   return "fatal_exception"

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

  def compile_src(self, src, filename=None):
    code = pyc.compile_src(
        src, python_version=self.python_version, filename=filename)
    return blocks.process_code(code)

  def run_bytecode(self, code, node, f_globals=None, f_locals=None):
    frame = self.make_frame(code, f_globals=f_globals, f_locals=f_locals)
    node, _ = self.run_frame(frame, node)
    if self.frames:  # pragma: no cover
      raise VirtualMachineError("Frames left over!")
    if self.frame is not None and self.frame.data_stack:  # pragma: no cover
      raise VirtualMachineError("Data left on stack!")
    return frame.f_globals, frame.f_locals, node

  def preload_builtins(self, node):
    builtins_code = self.compile_src(
        builtins.GetBuiltinsCode(self.python_version))
    f_globals, f_locals, node = self.run_bytecode(builtins_code, node)
    # at the outer layer, locals are the same as globals
    builtin_names = frozenset(f_globals.members)
    # Don't keep the types recorded so far:
    self._functions.clear()
    return f_globals, f_locals, builtin_names, node

  def run_program(self, src, filename=None, run_builtins=True):
    """Run the code and return the CFG nodes.

    This function loads in the builtins and puts them ahead of `code`,
    so all the builtins are available when processing `code`.

    Args:
      src: The program source code.
      filename: The filename the source is from.
      run_builtins: Whether to preload the native Python builtins.
    Returns:
      A tuple (CFGNode, set) containing the last CFGNode of the program as
        well as all the top-level names defined by it.
    """
    node = self.root_cfg_node.ConnectNew("init")
    if run_builtins:
      f_globals, f_locals, builtin_names, node = self.preload_builtins(node)
    else:
      f_globals, f_locals, builtin_names, node = None, None, frozenset(), node

    code = self.compile_src(src,
                            filename=filename)

    _, _, node = self.run_bytecode(code, node, f_globals, f_locals)
    log.info("Final node: %s", node.name)
    return node, builtin_names

  def call_binary_operator(self, name, x, y):
    """Map a binary operator to "magic methods" (__add__ etc.)."""
    # TODO(pludemann): See TODO.txt for more on reverse operator subtleties.
    results = []
    try:
      attr = self.load_attr(x, name)
    except exceptions.ByteCodeAttributeError:  # from load_attr
      log.info("Failed to find %s on %r", name, x, exc_info=True)
    else:
      results.append(self.call_function(attr, [y]))
    rname = self.reverse_operator_name(name)
    if self.reverse_operators and rname:
      try:
        attr = self.load_attr(y, rname)
      except exceptions.ByteCodeAttributeError:
        log.debug("No reverse operator %s on %r",
                  self.reverse_operator_name(name), y)
      else:
        results.append(self.call_function(attr, [x]))
    log.debug("Results: %r", results)
    return self.join_variables(name, results)

  def binary_operator(self, name):
    x, y = self.popn(2)
    self.push(self.call_binary_operator(name, x, y))

  def inplace_operator(self, name):
    x, y = self.popn(2)
    self.push(self.call_binary_operator(name, x, y))

  def trace_call(self, *args):
    return NotImplemented

  def trace_unknown(self, *args):
    """Fired whenever we create a variable containing 'Unknown'."""
    return NotImplemented

  def trace_classdef(self, *args):
    return NotImplemented

  def trace_functiondef(self, *args):
    return NotImplemented

  def trace_setattribute(self, *args):
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
    nodes = []
    for funcv in funcu.values:
      func = funcv.data
      assert isinstance(func, abstract.AtomicAbstractValue), type(func)
      try:
        new_node, one_result = func.call(
            self.frame.state.node,
            funcv, posargs, namedargs or {})
        self.frame.state = self.frame.state.change_cfg_node(new_node)
      except abstract.FailedFunctionCall as e:
        log.error("FailedFunctionCall for %s", e.obj)
        for msg in e.explanation_lines:
          log.error("... %s", msg)
      else:
        result.AddValues(one_result, self.current_location)
        nodes.append(new_node)
    if nodes:
      final_node = self.join_cfg_nodes(nodes)
      self.frame.state = self.frame.state.change_cfg_node(final_node)
      self.trace_call(final_node, funcu, posargs, namedargs, result)
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
    posargs = list(self.popn(num_pos))
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
    self.trace_setattribute(obj, attr, value)
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

  def push_last_exception(self, state):
    log.info("Pushing exception %r", state.exception)
    exctype, value, tb = state.exception
    return state.push(tb, value, exctype)

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

  def convert_locals_or_globals(self, d, name="globals"):
    if isinstance(d, dict):
      return abstract.LazyAbstractValue(
          name, d, self.maybe_convert_constant, self)
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

  def unary_operator(self, name):
    x = self.pop()
    method = self.load_attr(x, name)  # E.g. __not__
    result = self.call_function(method, [], {})
    self.push(result)

  def byte_UNARY_NOT(self):
    self.pop()  # discard
    self.push(self.instantiate_builtin(bool))

  def byte_UNARY_CONVERT(self):
    self.unary_operator("__repr__")

  def byte_UNARY_NEGATIVE(self):
    self.unary_operator("__neg__")

  def byte_UNARY_POSITIVE(self):
    self.unary_operator("__pos__")

  def byte_UNARY_INVERT(self):
    self.unary_operator("__invert__")

  def byte_BINARY_ADD(self):
    self.binary_operator("__add__")

  def byte_BINARY_SUBTRACT(self):
    self.binary_operator("__sub__")

  def byte_BINARY_DIVIDE(self):
    self.binary_operator("__div__")

  def byte_BINARY_MULTIPLY(self):
    self.binary_operator("__mul__")

  def byte_BINARY_MODULO(self):
    self.binary_operator("__mod__")

  def byte_BINARY_LSHIFT(self):
    self.binary_operator("__lshift__")

  def byte_BINARY_RSHIFT(self):
    self.binary_operator("__rshift__")

  def byte_BINARY_AND(self):
    self.binary_operator("__and__")

  def byte_BINARY_XOR(self):
    self.binary_operator("__xor__")

  def byte_BINARY_OR(self):
    self.binary_operator("__or__")

  def byte_BINARY_FLOOR_DIVIDE(self):
    self.binary_operator("__floordiv__")

  def byte_BINARY_TRUE_DIVIDE(self):
    self.binary_operator("__truediv__")

  def byte_BINARY_POWER(self):
    self.binary_operator("__pow__")

  def byte_BINARY_SUBSCR(self):
    self.binary_operator("__getitem__")

  def byte_INPLACE_ADD(self):
    self.binary_operator("__iadd__")

  def byte_INPLACE_SUBTRACT(self):
    self.inplace_operator("__isub__")

  def byte_INPLACE_MULTIPLY(self):
    self.inplace_operator("__imul__")

  def byte_INPLACE_DIVIDE(self):
    self.inplace_operator("__idiv__")

  def byte_INPLACE_MODULO(self):
    self.inplace_operator("__imod__")

  def byte_INPLACE_POWER(self):
    self.inplace_operator("__ipow__")

  def byte_INPLACE_LSHIFT(self):
    self.inplace_operator("__ilshift__")

  def byte_INPLACE_RSHIFT(self):
    self.inplace_operator("__irshift__")

  def byte_INPLACE_AND(self):
    self.inplace_operator("__iand__")

  def byte_INPLACE_XOR(self):
    self.inplace_operator("__ixor__")

  def byte_INPLACE_OR(self):
    self.inplace_operator("__ior__")

  def byte_INPLACE_FLOOR_DIVIDE(self):
    self.inplace_operator("__ifloordiv__")

  def byte_INPLACE_TRUE_DIVIDE(self):
    self.inplace_operator("__itruediv__")

  def byte_LOAD_CONST(self, op):
    const = self.frame.f_code.co_consts[op.arg]
    self.push(self.load_constant(const))

  def byte_POP_TOP(self):
    self.pop()

  def byte_DUP_TOP(self):
    self.push(self.top())

  def byte_DUP_TOPX(self, op):
    items = self.popn(op.arg)
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

  def byte_LOAD_NAME(self, op):
    """Load a name. Can be a local, global, or builtin."""
    name = self.frame.f_code.co_names[op.arg]
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

  def byte_STORE_NAME(self, op):
    name = self.frame.f_code.co_names[op.arg]
    self.store_local(name, self.pop())

  def byte_DELETE_NAME(self, op):
    name = self.frame.f_code.co_names[op.arg]
    self.del_local(name)

  def byte_LOAD_FAST(self, op):
    """Load a local. Unlike LOAD_NAME, it doesn't fall back to globals."""
    name = self.frame.f_code.co_varnames[op.arg]
    try:
      val = self.load_local(name)
    except KeyError:
      raise exceptions.ByteCodeUnboundLocalError(
          "local variable '%s' referenced before assignment" % name
      )
    self.push(val)

  def byte_STORE_FAST(self, op):
    name = self.frame.f_code.co_varnames[op.arg]
    self.store_local(name, self.pop())

  def byte_DELETE_FAST(self, op):
    name = self.frame.f_code.co_varnames[op.arg]
    self.del_local(name)

  def byte_LOAD_GLOBAL(self, op):
    """Load a global variable, or fall back to trying to load a builtin."""
    name = self.frame.f_code.co_names[op.arg]
    try:
      val = self.load_global(name)
    except KeyError:
      try:
        val = self.load_builtin(name)
      except KeyError:
        raise exceptions.ByteCodeNameError(
            "global name '%s' is not defined" % name)
    self.push(val)

  def byte_STORE_GLOBAL(self, op):
    name = self.frame.f_code.co_names[op.arg]
    self.store_global(name, self.pop())

  def byte_LOAD_CLOSURE(self, op):
    """Used to generate the 'closure' tuple for MAKE_CLOSURE.

    Each entry in that tuple is typically retrieved using LOAD_CLOSURE.

    Args:
      op: The opcode. op.arg is the index of a "cell variable": This corresponds
      to an entry in co_cellvars or co_freevars and is a variable that's bound
      into a closure.
    """
    self.push(self.frame.cells[op.arg])

  def byte_LOAD_DEREF(self, op):
    """Retrieves a value out of a cell."""
    # Since we're working on typegraph.Variable, we don't need to dereference.
    self.push(self.frame.cells[op.arg])

  def byte_STORE_DEREF(self, op):
    """Stores a value in a closure cell."""
    value = self.pop()
    assert isinstance(value, typegraph.Variable)
    self.frame.cells[op.arg].AddValues(value, self.current_location)

  def byte_LOAD_LOCALS(self):
    self.push(self.get_locals_dict_bytecode())

  def byte_COMPARE_OP(self, op):
    x, y = self.popn(2)
    # Explicit, redundant, switch statement, to make it easier to address the
    # behavior of individual compare operations:
    if op.arg == slots.CMP_LT:
      self.push(self.call_binary_operator("__lt__", x, y))
    elif op.arg == slots.CMP_LE:
      self.push(self.call_binary_operator("__le__", x, y))
    elif op.arg == slots.CMP_EQ:
      self.push(self.call_binary_operator("__eq__", x, y))
    elif op.arg == slots.CMP_NE:
      self.push(self.call_binary_operator("__ne__", x, y))
    elif op.arg == slots.CMP_GT:
      self.push(self.call_binary_operator("__gt__", x, y))
    elif op.arg == slots.CMP_GE:
      self.push(self.call_binary_operator("__ge__", x, y))
    elif op.arg == slots.CMP_IS:
      self.push(self.instantiate_builtin(bool))
    elif op.arg == slots.CMP_IS_NOT:
      self.push(self.instantiate_builtin(bool))
    elif op.arg == slots.CMP_NOT_IN:
      self.push(self.instantiate_builtin(bool))
    elif op.arg == slots.CMP_IN:
      self.push(self.instantiate_builtin(bool))
    elif op.arg == slots.CMP_EXC_MATCH:
      self.push(self.instantiate_builtin(bool))
    else:
      raise VirtualMachineError("Invalid argument to COMPARE_OP: %d", op.arg)

  def byte_LOAD_ATTR(self, op):
    name = self.frame.f_code.co_names[op.arg]
    obj = self.pop()
    log.info("LOAD_ATTR: %r %s", type(obj), name)
    val = self.load_attr(obj, name)
    self.push(val)

  def byte_STORE_ATTR(self, op):
    name = self.frame.f_code.co_names[op.arg]
    val, obj = self.popn(2)
    self.store_attr(obj, name, val)

  def byte_DELETE_ATTR(self, op):
    name = self.frame.f_code.co_names[op.arg]
    obj = self.pop()
    self.del_attr(obj, name)

  def store_subscr(self, obj, key, val):
    self.call_function(self.load_attr(obj, "__setitem__"),
                       [key, val], {})

  def byte_STORE_SUBSCR(self):
    val, obj, subscr = self.popn(3)
    self.store_subscr(obj, subscr, val)

  def byte_DELETE_SUBSCR(self):
    obj, subscr = self.popn(2)
    self.del_subscr(obj, subscr)

  def byte_BUILD_TUPLE(self, op):
    count = op.arg
    elts = self.popn(count)
    self.push(self.build_tuple(elts))

  def byte_BUILD_LIST(self, op):
    elts = self.popn(op.arg)
    self.push(self.build_list(elts))

  def byte_BUILD_SET(self, op):
    # TODO(kramm): Not documented in Py2 docs.
    elts = self.popn(op.arg)
    self.push(self.build_set(elts))

  def byte_BUILD_MAP(self, op):
    # op.arg (size) is ignored.
    self.push(self.build_map())

  def byte_STORE_MAP(self):
    # pylint: disable=unbalanced-tuple-unpacking
    the_map, val, key = self.popn(3)
    self.store_subscr(the_map, key, val)
    self.push(the_map)

  def byte_UNPACK_SEQUENCE(self, op):
    seq = self.pop()
    itr = self.call_function(self.load_attr(seq, "__iter__"), [], {})
    values = []
    for _ in range(op.arg):
      # TODO(ampere): Fix for python 3
      values.append(self.call_function(self.load_attr(itr, "next"),
                                       [], {}))
    for value in reversed(values):
      self.push(value)

  def byte_BUILD_SLICE(self, op):
    if op.arg == 2:
      x, y = self.popn(2)
      self.push(self.build_slice(x, y))
    elif op.arg == 3:
      x, y, z = self.popn(3)
      self.push(self.build_slice(x, y, z))
    else:       # pragma: no cover
      raise VirtualMachineError("Strange BUILD_SLICE count: %r" % op.arg)

  def byte_LIST_APPEND(self, op):
    # Used by the compiler e.g. for [x for x in ...]
    val = self.pop()
    the_list = self.peek(op.arg)
    self.call_function(self.load_attr(the_list, "append"), [val], {})

  def byte_SET_ADD(self, op):
    # Used by the compiler e.g. for {x for x in ...}
    count = op.arg
    val = self.pop()
    the_set = self.peek(count)
    self.call_function(self.load_attr(the_set, "add"), [val], {})

  def byte_MAP_ADD(self, op):
    # Used by the compiler e.g. for {x, y for x, y in ...}
    count = op.arg
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

  def byte_JUMP_IF_TRUE_OR_POP(self, op):
    self.store_jump(op.target, self.frame.state)
    self.pop()

  def byte_JUMP_IF_FALSE_OR_POP(self, op):
    self.store_jump(op.target, self.frame.state)
    self.pop()

  def byte_JUMP_IF_TRUE(self, op):  # Not in py2.7
    self.store_jump(op.target, self.frame.state)

  def byte_JUMP_IF_FALSE(self, op):  # Not in py2.7
    self.store_jump(op.target, self.frame.state)

  def byte_POP_JUMP_IF_TRUE(self, op):
    self.pop()
    self.store_jump(op.target, self.frame.state)

  def byte_POP_JUMP_IF_FALSE(self, op):
    self.pop()
    self.store_jump(op.target, self.frame.state)

  def byte_JUMP_FORWARD(self, op):
    self.store_jump(op.target, self.frame.state)

  def byte_JUMP_ABSOLUTE(self, op):
    self.store_jump(op.target, self.frame.state)

  def byte_SETUP_LOOP(self, op):
    self.push_block("loop", op.target)

  def byte_GET_ITER(self):
    self.push(self.load_attr(self.pop(), "__iter__"))
    self.call_function_from_stack(0, [])

  def store_jump(self, target, state):
    self.frame.states[target] = state.merge_into(self.frame.states.get(target))

  def byte_FOR_ITER(self, op):
    self.store_jump(op.target, self.frame.state.pop_and_discard())
    self.push(self.load_attr(self.top(), "next"))
    try:
      self.call_function_from_stack(0, [])
      # The loop is still running, so just continue with the next instruction.
      return None
    except StopIteration:
      pass

  def byte_BREAK_LOOP(self):
    return "break"

  def byte_CONTINUE_LOOP(self, op):
    # This is a trick with the return value.
    # While unrolling blocks, continue and return both have to preserve
    # state as the finally blocks are executed.  For continue, it's
    # where to jump to, for return, it's the value to return.  It gets
    # pushed on the stack for both, so continue puts the jump destination
    # into return_value.
    # TODO(kramm): This probably doesn't work.
    self.return_value = op.target
    return "continue"

  def byte_SETUP_EXCEPT(self, op):
    # Assume that it's possible to throw the exception at the first
    # instruction of the code:
    self.store_jump(op.target,
                    self.push_abstract_exception(self.frame.state))
    self.push_block("setup-except", op.target)

  def byte_SETUP_FINALLY(self, op):
    # Emulate finally by connecting the try to the finally block (with
    # empty reason/why/continuation):
    self.store_jump(op.target, self.frame.state.push(None))
    self.push_block("finally", op.target)

  def byte_POP_BLOCK(self):
    self.pop_block()

  def byte_RAISE_VARARGS_PY2(self, op):
    """Raise an exception (Python 2 version)."""
    # NOTE: the dis docs are completely wrong about the order of the
    # operands on the stack!
    argc = op.arg
    exctype = val = tb = None
    if argc == 0:
      if self.frame.state.exception is None:
        raise exceptions.ByteCodeTypeError(
            "exceptions must be old-style classes "
            "or derived from BaseException, not NoneType")
      exctype, val, tb = self.frame.state.exception
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
    self.frame.state = self.frame.state.set_exception(exctype, val, tb)
    if tb:
      return "reraise"
    else:
      return "exception"

  def byte_RAISE_VARARGS_PY3(self, op):
    """Raise an exception (Python 3 version)."""
    argc = op.arg
    cause = exc = None
    if argc == 2:
      cause = self.pop()
      exc = self.pop()
    elif argc == 1:
      exc = self.pop()
    return self.do_raise(exc, cause)

  def byte_RAISE_VARARGS(self, op):
    if self.python_version[0] == 2:
      return self.byte_RAISE_VARARGS_PY2(op)
    else:
      return self.byte_RAISE_VARARGS_PY3(op)

  def byte_POP_EXCEPT(self):
    block = self.pop_block()
    if block.type != "except-handler":
      raise VirtualMachineError("popped block is not an except handler")
    self.frame.state = self.unwind_block(block, self.frame.state)

  def byte_SETUP_WITH(self, op):
    ctxmgr = self.pop()
    self.push(self.load_attr(ctxmgr, "__exit__"))
    ctxmgr_obj = self.call_function(self.load_attr(ctxmgr, "__enter__"), [])
    if self.python_version[0] == 2:
      self.push_block("with", op.target)
    else:
      assert self.python_version[0] == 3
      self.push_block("finally", op.target)
    self.push(ctxmgr_obj)

  def byte_WITH_CLEANUP(self):
    """Called at the end of a with block. Calls the exit handlers etc."""
    # The code here does some weird stack manipulation: the exit function
    # is buried in the stack, and where depends on what's on top of it.
    # Pull out the exit function, and leave the rest in place.
    u = self.top()
    if isinstance(u, str):
      if u in ("return", "continue"):
        exit_func = self.pop_nth(2)
      else:
        exit_func = self.pop_nth(1)
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

  def byte_MAKE_FUNCTION(self, op):
    """Create a function and push it onto the stack."""
    argc = op.arg
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

  def byte_MAKE_CLOSURE(self, op):
    """Make a function that binds local variables."""
    argc = op.arg
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

  def byte_CALL_FUNCTION(self, op):
    return self.call_function_from_stack(op.arg, [])

  def byte_CALL_FUNCTION_VAR(self, op):
    args = self.pop_varargs()
    return self.call_function_from_stack(op.arg, args)

  def byte_CALL_FUNCTION_KW(self, op):
    kwargs = self.pop_kwargs()
    return self.call_function_from_stack(op.arg, [], kwargs)

  def byte_CALL_FUNCTION_VAR_KW(self, op):
    kwargs = self.pop_kwargs()
    args = self.pop_varargs()
    return self.call_function_from_stack(op.arg, args, kwargs)

  def byte_YIELD_VALUE(self):
    self.return_value = self.pop()
    return "yield"

  def byte_IMPORT_NAME(self, op):
    name = self.frame.f_code.co_names[op.arg]
    level, unused_fromlist = self.popn(2)
    self.push(self.import_name(name, level))
    # TODO(kramm): Do something meaningful with "fromlist"?

  def byte_IMPORT_FROM(self, op):
    name = self.frame.f_code.co_names[op.arg]
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

  def byte_END_FINALLY(self):
    # TODO(kramm): Return a fitting why
    exc = self.pop()
    if self.is_none(exc):
      return
    else:
      log.info("Popping exception %r", exc)
      self.pop()
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

  def byte_SLICE_0(self):
    return self.get_slice(0)

  def byte_SLICE_1(self):
    return self.get_slice(1)

  def byte_SLICE_2(self):
    return self.get_slice(2)

  def byte_SLICE_3(self):
    return self.get_slice(3)

  def byte_STORE_SLICE_0(self):
    return self.store_slice(0)

  def byte_STORE_SLICE_1(self):
    return self.store_slice(1)

  def byte_STORE_SLICE_2(self):
    return self.store_slice(2)

  def byte_STORE_SLICE_3(self):
    return self.store_slice(3)

  def byte_DELETE_SLICE_0(self):
    return self.delete_slice(0)

  def byte_DELETE_SLICE_1(self):
    return self.delete_slice(1)

  def byte_DELETE_SLICE_2(self):
    return self.delete_slice(2)

  def byte_DELETE_SLICE_3(self):
    return self.delete_slice(3)

