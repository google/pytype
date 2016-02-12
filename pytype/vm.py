"""A abstract virtual machine for python bytecode that generates typegraphs.

A VM for python byte code that uses pytype/pytd/cfg ("typegraph") to generate a
trace of the program execution.
"""

# We have names like "byte_NOP":
# pylint: disable=invalid-name

# Bytecodes don't always use all their arguments:
# pylint: disable=unused-argument

import collections
import linecache
import logging
import os
import re
import repr as reprlib
import sys
import types


from pytype import abstract
from pytype import blocks
from pytype import exceptions
from pytype import load_pytd
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


MAX_IMPORT_DEPTH = 12


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
  raise ConversionError("Only some types are supported: %r" % type(atomic))


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
               reverse_operators=False,
               cache_unknowns=True,
               maximum_depth=None):
    """Construct a TypegraphVirtualMachine."""
    self.maximum_depth = sys.maxint if maximum_depth is None else maximum_depth
    self.errorlog = errorlog
    self.options = options
    self.python_version = options.python_version
    self.reverse_operators = reverse_operators
    self.cache_unknowns = cache_unknowns
    self.loader = load_pytd.Loader(
        base_module=module_name,
        options=options)
    # The call stack of frames.
    self.frames = []
    # The current frame.
    self.frame = None

    self.program = typegraph.Program()

    self.root_cfg_node = self.program.NewCFGNode("root")
    self.program.entrypoint = self.root_cfg_node

    self._convert_cache = {}

    # Initialize primitive_classes to empty to allow convert_constant to run
    self.primitive_classes = {}
    # Now fill primitive_classes with the real values using convert_constant
    self.primitive_classes = {v: self.convert_constant(v.__name__, v)
                              for v in [int, long, float, str, unicode,
                                        types.NoneType, complex, bool, slice,
                                        types.CodeType]}

    self.none = abstract.AbstractOrConcreteValue(
        None, self.primitive_classes[types.NoneType], self)
    self.true = abstract.AbstractOrConcreteValue(
        True, self.primitive_classes[bool], self)
    self.false = abstract.AbstractOrConcreteValue(
        False, self.primitive_classes[bool], self)

    self.nothing = abstract.Nothing(self)
    self.unsolvable = abstract.Unsolvable(self)

    self.primitive_class_instances = {}
    for name, clsvar in self.primitive_classes.items():
      instance = abstract.Instance(clsvar, self)
      self.primitive_class_instances[name] = instance
      clsval, = clsvar.values
      self._convert_cache[(abstract.Instance, clsval.data.pytd_cls)] = instance
    self.primitive_class_instances[types.NoneType] = self.none

    self.str_type = self.primitive_classes[str]
    self.int_type = self.primitive_classes[int]
    self.tuple_type = self.convert_constant("tuple", tuple)
    self.list_type = self.convert_constant("list", list)
    self.set_type = self.convert_constant("set", set)
    self.dict_type = self.convert_constant("dict", dict)
    self.module_type = self.convert_constant("module", types.ModuleType)
    self.function_type = self.convert_constant(
        "function", types.FunctionType)
    self.generator_type = self.convert_constant(
        "generator", types.GeneratorType)

    self.undefined = self.program.NewVariable("undefined")

    self.vmbuiltins = {b.name: b for b in (self.loader.builtins.constants +
                                           self.loader.builtins.classes +
                                           self.loader.builtins.functions)}

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
    if log.isEnabledFor(logging.INFO):
      self.log_opcode(op, state)
    self.frame.current_opcode = op
    try:
      # dispatch
      bytecode_fn = getattr(self, "byte_%s" % op.name, None)
      if bytecode_fn is None:
        raise VirtualMachineError("Unknown opcode: %s" % op.name)
      if op.has_arg():
        state = bytecode_fn(state, op)
      else:
        state = bytecode_fn(state)
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

  def push_block(self, state, t, handler=None, level=None):
    if level is None:
      level = len(state.data_stack)
    return state.push_block(Block(t, handler, level))

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
      state, end = self.call_function_with_state(state, f, [], {})
    return state, self.build_slice(state.node, start, end, 1), obj

  def store_slice(self, state, count):
    state, slice_obj, obj = self.pop_slice_and_obj(state, count)
    state, new_value = state.pop()
    state, f = self.load_attr(state, obj, "__setitem__")
    state, _ = self.call_function_with_state(state, f, [slice_obj, new_value],
                                             {})
    return state

  def delete_slice(self, state, count):
    state, slice_obj, obj = self.pop_slice_and_obj(state, count)
    state, f = self.load_attr(state, obj, "__delitem__")
    state, _ = self.call_function_with_state(state, f, [slice_obj], {})
    return state

  def get_slice(self, state, count):
    state, slice_obj, obj = self.pop_slice_and_obj(state, count)
    state, f = self.load_attr(state, obj, "__getitem__")
    state, ret = self.call_function_with_state(state, f, [slice_obj], {})
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
    """Create a combined Variable for a list of variables.

    This is destructive: It will reuse and overwrite the input variables. The
    purpose of this function is to create a final result variable for functions
    that return a list of "temporary" variables. (E.g. function calls)

    Args:
      node: The current CFG node.
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
        v.PasteVariable(r, node)
      return v

  def convert_value_to_string(self, val):
    if isinstance(val, abstract.PythonConstant) and isinstance(val.pyval, str):
      return val.pyval
    raise ConversionError("%s is not a string" % val)

  def _get_maybe_abstract_instance(self, data):
    """Get an instance of the same type as the given data, abstract if possible.

    Get an abstract instance of primitive data stored as an
    AbstractOrConcreteValue. Return any other data as-is. This is used by
    create_pytd_instance to discard concrete values that have been kept
    around for InterpreterFunction.

    Arguments:
      data: The data.

    Returns:
      An instance of the same type as the data, abstract if possible.
    """
    if isinstance(data, abstract.AbstractOrConcreteValue):
      data_type = type(data.pyval)
      if data_type in self.primitive_class_instances:
        return self.primitive_class_instances[data_type]
    return data

  def create_pytd_instance(self, name, pytype, subst, node, source_sets=None,
                           discard_concrete_values=False):
    """Create an instance of a PyTD type as a typegraph.Variable.

    Because this (unlike create_pytd_instance_value) creates variables, it can
    also handle union types.

    Args:
      name: What to call the resulting variable.
      pytype: A PyTD type to construct an instance of.
      subst: The current type parameters.
      node: The current CFG node.
      source_sets: An iterator over instances of SourceSet (or just tuples).
        Each SourceSet describes a combination of values that were used to
        build the new value (e.g., for a function call, parameter types).
      discard_concrete_values: Whether concrete values should be discarded from
        type parameters.
    Returns:
      A typegraph.Variable.
    Raises:
      ValueError: If we can't resolve a type parameter.
    """
    if not source_sets:
      source_sets = [[]]
    if isinstance(pytype, pytd.AnythingType):
      return self.create_new_unsolvable(node, "?")
    name = pytype.name if hasattr(pytype, "name") else pytype.__class__.__name__
    var = self.program.NewVariable(name)
    for t in pytd_utils.UnpackUnion(pytype):
      if isinstance(t, pytd.TypeParameter):
        if not subst or t.name not in subst:
          raise ValueError("Can't resolve type parameter %s using %r" % (
              t.name, subst))
        for v in subst[t.name].values:
          for source_set in source_sets:
            var.AddValue(self._get_maybe_abstract_instance(v.data)
                         if discard_concrete_values else v.data,
                         source_set + [v], node)
      elif isinstance(t, pytd.NothingType):
        pass
      else:
        value = self._create_pytd_instance_value(name, t, subst, node)
        for source_set in source_sets:
          var.AddValue(value, source_set, node)
    return var

  def _create_pytd_instance_value(self, name, pytype, subst, node):
    """Create an instance of PyTD type.

    This can handle any PyTD type and is used for generating both methods of
    classes (when given a Signature) and instance of classes (when given a
    ClassType).

    Args:
      name: What to call the value.
      pytype: A PyTD type to construct an instance of.
      subst: The current type parameters.
      node: The current CFG node.
    Returns:
      An instance of AtomicAbstractType.
    Raises:
      ValueError: if pytype is not of a known type.
    """
    if isinstance(pytype, pytd.ClassType):
      # This key is also used in __init__
      key = (abstract.Instance, pytype.cls)
      if key not in self._convert_cache:
        if pytype.name == "type":
          # special case: An instantiation of "type" can be anything.
          instance = self._create_new_unknown_value("type")
        else:
          instance = abstract.Instance(
              self.convert_constant(str(pytype), pytype), self)
        log.info("New pytd instance for %s: %r", pytype.cls.name, instance)
        self._convert_cache[key] = instance
      return self._convert_cache[key]
    elif isinstance(pytype, pytd.GenericType):
      assert isinstance(pytype.base_type, pytd.ClassType)
      cls = pytype.base_type.cls
      instance = abstract.Instance(
          self.convert_constant(cls.name, cls), self)
      for formal, actual in zip(cls.template, pytype.parameters):
        p = self.create_pytd_instance(repr(formal), actual, subst, node)
        instance.initialize_type_parameter(node, formal.name, p)
      return instance
    else:
      return self.convert_constant_to_value(name, pytype)

  def _create_new_unknown_value(self, action):
    if not self.cache_unknowns or not action or not self.frame:
      return abstract.Unknown(self)
    # We allow only one Unknown at each point in the program, regardless of
    # what the call stack is.
    key = ("unknown", self.frame.current_opcode, action)
    if key not in self._convert_cache:
      self._convert_cache[key] = abstract.Unknown(self)
    return self._convert_cache[key]

  def create_new_unknown(self, node, name, source=None, action=None):
    """Create a new variable containing unknown, originating from this one."""
    unknown = self._create_new_unknown_value(action)
    v = self.program.NewVariable(name)
    val = v.AddValue(unknown, source_set=[source] if source else [], where=node)
    unknown.owner = val
    self.trace_unknown(unknown.class_name, v)
    return v

  def create_new_unsolvable(self, node, name):
    """Create a new variable containing an unsolvable."""
    return self.unsolvable.to_variable(node, name)

  def convert_constant(self, name, pyval):
    """Convert a constant to a Variable.

    This converts a constant to a typegraph.Variable. Unlike
    convert_constant_to_value, it can handle things that need to be represented
    as a Variable with multiple possible values (i.e., a union type), like
    pytd.Function.

    Args:
      name: The name to give the new variable.
      pyval: The Python constant to convert. Can be a PyTD definition or a
      builtin constant.
    Returns:
      A typegraph.Variable.
    Raises:
      ValueError: if pytype is not of a known type.
    """
    if isinstance(pyval, pytd.UnionType):
      options = [self.convert_constant_to_value(pytd.Print(t), t)
                 for t in pyval.type_list]
      return self.program.NewVariable(name, options, [], self.root_cfg_node)
    elif isinstance(pyval, pytd.NothingType):
      return self.program.NewVariable(name, [], [], self.root_cfg_node)
    elif isinstance(pyval, pytd.Alias):
      return self.convert_constant(pytd.Print(pyval), pyval.type)
    elif isinstance(pyval, pytd.ExternalType):
      return self.convert_constant(pytd.Print(pyval), pyval.cls)
    elif isinstance(pyval, pytd.Constant):
      return self.create_pytd_instance(name, pyval.type, {}, self.root_cfg_node)
    result = self.convert_constant_to_value(name, pyval)
    if result is not None:
      return result.to_variable(self.root_cfg_node, name)
    # There might still be bugs on the abstract intepreter when it returns,
    # e.g. a list of values instead of a list of types:
    assert pyval.__class__ != typegraph.Variable, pyval
    if pyval.__class__ == tuple:
      # TODO(ampere): This does not allow subclasses. Handle namedtuple
      # correctly.
      # This case needs to go at the end because many things are actually also
      # tuples.
      return self.build_tuple(
          self.root_cfg_node,
          (self.maybe_convert_constant("tuple[%d]" % i, v)
           for i, v in enumerate(pyval)))
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
    key = ("constant", pyval, type(pyval))
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
    Raises:
      NotImplementedError: If we don't know how to convert a value.
    """
    if pyval is type:
      return abstract.SimpleAbstractValue(name, self)
    elif isinstance(pyval, str):
      return abstract.AbstractOrConcreteValue(pyval, self.str_type, self)
    elif isinstance(pyval, int) and -1 <= pyval <= MAX_IMPORT_DEPTH:
      # For small integers, preserve the actual value (for things like the
      # level in IMPORT_NAME).
      return abstract.AbstractOrConcreteValue(pyval, self.int_type, self)
    elif pyval.__class__ in self.primitive_classes:
      return self.primitive_class_instances[pyval.__class__]
    elif isinstance(pyval, (loadmarshal.CodeType, blocks.OrderedCode)):
      return abstract.AbstractOrConcreteValue(
          pyval, self.primitive_classes[types.CodeType], self)
    elif pyval.__class__ in [types.FunctionType,
                             types.ModuleType,
                             types.GeneratorType,
                             type]:
      try:
        # TODO(ampere): This will incorrectly handle any object that is named
        # the same as a builtin but is distinct. It will need to be extended to
        # support imports and the like.
        pyclass = self.loader.builtins.Lookup(pyval.__name__)
        return self.convert_constant_to_value(name, pyclass)
      except (KeyError, AttributeError):
        log.debug("Failed to find pytd", exc_info=True)
        raise
    elif isinstance(pyval, pytd.Class):
      if "." in name:
        module, base_name = name.rsplit(".", 1)
        cls = abstract.PyTDClass(base_name, pyval, self)
        cls.module = module
        return cls
      else:
        return abstract.PyTDClass(name, pyval, self)
    elif isinstance(pyval, pytd.Function):
      f = abstract.PyTDFunction(pyval.name, [abstract.PyTDSignature(sig, self)
                                             for sig in pyval.signatures], self)
      return f
    elif isinstance(pyval, pytd.ClassType):
      assert pyval.cls
      return self.convert_constant_to_value(pyval.name, pyval.cls)
    elif isinstance(pyval, pytd.NothingType):
      return self.nothing
    elif isinstance(pyval, pytd.AnythingType):
      return self._create_new_unknown_value("AnythingType")
    elif isinstance(pyval, pytd.UnionType):
      return abstract.Union([self.convert_constant_to_value(pytd.Print(t), t)
                             for t in pyval.type_list], self)
    elif isinstance(pyval, pytd.TypeParameter):
      return abstract.TypeParameter(pyval.name, self)
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
    elif pyval.__class__ is tuple:  # only match raw tuple, not namedtuple/Node
      return self.tuple_to_value(self.root_cfg_node,
                                 [self.convert_constant("tuple[%d]" % i, item)
                                  for i, item in enumerate(pyval)])
    else:
      raise NotImplementedError("Can't convert constant %s %r" %
                                (type(pyval), pyval))

  def maybe_convert_constant(self, name, pyval):
    """Create a variable that represents a python constant if needed.

    Call self.convert_constant if pyval is not an AtomicAbstractValue, otherwise
    store said value in a variable. This also handles dict values by
    constructing a new abstract value representing it. Dict values are not
    cached.

    Args:
      name: The name to give to the variable.
      pyval: The python value or PyTD value to convert or pass
        through.
    Returns:
      A Variable.
    """
    assert not isinstance(pyval, typegraph.Variable)
    if isinstance(pyval, abstract.AtomicAbstractValue):
      return pyval.to_variable(self.root_cfg_node, name)
    elif isinstance(pyval, dict):
      value = abstract.LazyAbstractOrConcreteValue(
          name,
          pyval,  # for class members
          member_map=pyval,
          resolver=self.maybe_convert_constant,
          vm=self)
      value.set_attribute(self.root_cfg_node, "__class__", self.dict_type)
      return value.to_variable(self.root_cfg_node, name)
    else:
      return self.convert_constant(name, pyval)

  def make_none(self, node):
    none = self.none.to_variable(node, "None")
    assert self.is_none(none)
    return none

  def make_class(self, node, name_var, bases, class_dict_var):
    """Create a class with the name, bases and methods given.

    Args:
      node: The current CFG node.
      name_var: Class name.
      bases: Base classes.
      class_dict_var: Members of the class, as a Variable containing an
          abstract.Dict value.

    Returns:
      An instance of Class.
    """
    bases_values = bases.values
    bases = list(_get_atomic_python_constant(bases))
    name = _get_atomic_python_constant(name_var)
    log.info("Declaring class %s", name)
    try:
      class_dict = _get_atomic_value(class_dict_var)
    except ConversionError:
      log.error("Error initializing class %r", name)
      return self.create_new_unknown(node, name)
    for base in bases:
      if not any(isinstance(t, (abstract.Class,
                                abstract.Unknown,
                                abstract.Unsolvable))
                 for t in base.data):
        self.errorlog.base_class_error(self.frame.current_opcode, base)
    val = abstract.InterpreterClass(
        name,
        bases,
        class_dict.members,
        self)
    var = self.program.NewVariable(name)
    var.AddValue(val, bases_values + class_dict_var.values, node)
    return var

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
    val = abstract.InterpreterFunction.make_function(
        name, code=_get_atomic_python_constant(code),
        f_locals=self.frame.f_locals, f_globals=globs,
        defaults=defaults, closure=closure, vm=self)
    # TODO(ampere): What else needs to be an origin in this case? Probably stuff
    # in closure.
    var = self.program.NewVariable(name)
    var.AddValue(val, code.values, self.root_cfg_node)
    return var

  def make_frame(self, node, code, callargs=None,
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
    if code.co_flags & loadmarshal.CodeType.CO_NEWLOCALS:
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
      return value is None or _get_atomic_python_constant(value) is None
    except ConversionError:
      return False

  def push_abstract_exception(self, state):
    tb = self.build_list(state.node, [])
    value = self.create_new_unknown(state.node, "value")
    exctype = self.create_new_unknown(state.node, "exctype")
    return state.push(tb, value, exctype)

  def resume_frame(self, node, frame):
    frame.f_back = self.frame
    log.info("resume_frame: %r", frame)
    node, val = self.run_frame(frame, node)
    frame.f_back = None
    return node, val

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
        src, python_version=self.python_version,
        python_exe=self.options.python_exe,
        filename=filename)
    return blocks.process_code(code)

  def run_bytecode(self, node, code, f_globals=None, f_locals=None):
    frame = self.make_frame(node, code, f_globals=f_globals, f_locals=f_locals)
    node, _ = self.run_frame(frame, node)
    if self.frames:  # pragma: no cover
      raise VirtualMachineError("Frames left over!")
    if self.frame is not None and self.frame.data_stack:  # pragma: no cover
      raise VirtualMachineError("Data left on stack!")
    return node, frame.f_globals, frame.f_locals

  def preload_builtins(self, node):
    """Parse __builtin__.py and return the definitions as a globals dict."""
    if self.options.pybuiltins_filename:
      with open(self.options.pybuiltins_filename, "rb") as fi:
        src = fi.read()
    else:
      src = builtins.GetBuiltinsCode(self.python_version)
    builtins_code = self.compile_src(src)
    node, f_globals, f_locals = self.run_bytecode(node, builtins_code)
    # at the outer layer, locals are the same as globals
    builtin_names = frozenset(f_globals.members)
    return node, f_globals, f_locals, builtin_names

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
    node = self.root_cfg_node.ConnectNew("builtins")
    if run_builtins:
      node, f_globals, f_locals, builtin_names = self.preload_builtins(node)
    else:
      node, f_globals, f_locals, builtin_names = node, None, None, frozenset()

    code = self.compile_src(src, filename=filename)

    node = node.ConnectNew("init")
    node, f_globals, _ = self.run_bytecode(node, code, f_globals, f_locals)
    log.info("Final node: <%d>%s", node.id, node.name)
    return node, f_globals.members, builtin_names

  def call_binary_operator(self, state, name, x, y):
    """Map a binary operator to "magic methods" (__add__ etc.)."""
    # TODO(pludemann): See TODO.txt for more on reverse operator subtleties.
    results = []
    log.debug("Calling binary operator %s", name)
    try:
      state, attr = self.load_attr(state, x, name)
    except exceptions.ByteCodeAttributeError:  # from load_attr
      log.info("Failed to find %s on %r", name, x, exc_info=True)
    else:
      state, ret = self.call_function_with_state(state, attr, [y],
                                                 fallback_to_unsolvable=False)
      results.append(ret)
    rname = self.reverse_operator_name(name)
    if self.reverse_operators and rname:
      try:
        state, attr = self.load_attr_noerror(state, y, rname)
      except exceptions.ByteCodeAttributeError:
        log.debug("No reverse operator %s on %r",
                  self.reverse_operator_name(name), y)
      else:
        state, ret = self.call_function_with_state(state, attr, [x],
                                                   fallback_to_unsolvable=False)
        results.append(ret)
    result = self.join_variables(state.node, name, results)
    log.debug("Result: %r", result)
    if not result.values:
      self.errorlog.unsupported_operands(self.frame.current_opcode, name, x, y)
    return state, result

  def binary_operator(self, state, name):
    state, (x, y) = state.popn(2)
    state, ret = self.call_binary_operator(state, name, x, y)
    return state.push(ret)

  def inplace_operator(self, state, name):
    state, (x, y) = state.popn(2)
    state, ret = self.call_binary_operator(state, name, x, y)
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
    node, ret = self.call_function(
        state.node, funcu, posargs, namedargs,
        starargs, starstarargs, fallback_to_unsolvable)
    return state.change_cfg_node(node), ret

  def call_function(self, node, funcu, posargs, namedargs=None, starargs=None,
                    starstarargs=None, fallback_to_unsolvable=True):
    """Call a function.

    Args:
      node: The current CFG node.
      funcu: A variable of the possible functions to call.
      posargs: The known positional arguments to pass (as variables).
      namedargs: The known keyword arguments to pass. dict of str -> Variable.
      starargs: The contents of the *args parameter, if passed, or None.
      starstarargs: The contents of the **kwargs parameter, if passed, or None.
      fallback_to_unsolvable: If the function call fails, create an unknown.
    Returns:
      A tuple (CFGNode, Variable). The Variable is the return value.
    """
    assert funcu.values
    result = self.program.NewVariable("<return:%s>" % funcu.name)
    nodes = []
    error = None
    for funcv in funcu.values:
      func = funcv.data
      assert isinstance(func, abstract.AtomicAbstractValue), type(func)
      try:
        new_node, one_result = func.call(
            node, funcv, posargs, namedargs or {}, starargs, starstarargs)
      except abstract.FailedFunctionCall as e:
        error = error or e
      else:
        result.PasteVariable(one_result, new_node)
        nodes.append(new_node)
    if nodes:
      return self.join_cfg_nodes(nodes), result
    else:
      if fallback_to_unsolvable:
        assert error
        self.errorlog.invalid_function_call(self.frame.current_opcode, e)
        log.warning("failed function call for %s", error.sig.name)
        return node, self.create_new_unsolvable(node, "failed call")
      else:
        # We were called by something that ignores errors, so don't report
        # the failed call.
        return node, result

  def call_function_from_stack(self, state, arg, args, kwargs=None):
    """Pop arguments for a function and call it."""
    num_kw, num_pos = divmod(arg, 256)
    # TODO(kramm): Can we omit creating this dict if kwargs=None and num_kw=0?
    namedargs = abstract.Dict("kwargs", self)
    for _ in range(num_kw):
      state, (key, val) = state.popn(2)
      namedargs.setitem(state.node, key, val)
    starstarargs = None
    if kwargs:
      for v in kwargs.data:  # TODO(kramm): .Data(node)
        did_update = namedargs.update(state.node, v)
        if not did_update and starstarargs is None:
          starstarargs = self.create_new_unsolvable(state.node, "**kwargs")
    state, posargs = state.popn(num_pos)
    posargs = list(posargs)
    if args is not None:
      posargs.extend(args)
      starargs = None
    else:
      starargs = self.create_new_unsolvable(state.node, "*args")
    state, func = state.pop()
    state, ret = self.call_function_with_state(
        state, func, posargs, namedargs, starargs, starstarargs)
    state = state.push(ret)
    return state

  def load_constant(self, value):
    """Converts a Python value to an abstract value."""
    return self.convert_constant(type(value).__name__, value)

  def get_globals_dict(self):
    """Get a real python dict of the globals."""
    return self.frame.f_globals

  def load_from(self, state, store, name):
    node = state.node
    node, attr = store.get_attribute(node, name)
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
    """Load builtins that have a special implementation in pytype."""
    if name == "super":
      # The super() function.
      return abstract.Super(self)
    elif name == "__any_object__":
      # for type_inferencer/tests/test_pgms/*.py
      return abstract.Unknown(self)
    elif name == "__random__":
      # for more pretty branching tests
      return self.primitive_class_instances[bool]
    else:
      return None

  def load_builtin(self, state, name):
    if name == "__undefined__":
      # For values that don't exist. (Unlike None, which is a valid object)
      return state, self.undefined
    special = self.load_special_builtin(name)
    if special:
      return state, special.to_variable(state.node, name)
    else:
      return self.load_from(state, self.frame.f_builtins, name)

  def store_local(self, state, name, value):
    """Called when a local is written."""
    assert isinstance(value, typegraph.Variable), (name, repr(value))
    node = self.frame.f_locals.set_attribute(state.node, name, value)
    return state.change_cfg_node(node)

  def store_global(self, state, name, value):
    """Same as store_local except for globals."""
    assert isinstance(value, typegraph.Variable)
    node = self.frame.f_globals.set_attribute(state.node, name, value)
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

  def _retrieve_attr(self, node, obj, attr, errors=True):
    """Load an attribute from an object."""
    assert isinstance(obj, typegraph.Variable), obj
    # Resolve the value independently for each value of obj
    result = self.program.NewVariable(str(attr))
    log.debug("getting attr %s from %r", attr, obj)
    nodes = []
    for val in obj.Values(node):
      node2, attr_var = val.data.get_attribute(node, attr, val)
      if not attr_var:
        log.debug("No %s on %s", attr, val.data.__class__)
        continue
      log.debug("got choice for attr %s from %r of %r (0x%x): %r", attr, obj,
                val.data, id(val.data), attr_var)
      if not attr_var:
        continue
      result.PasteVariable(attr_var, node2)
      nodes.append(node2)
    if not result.values:
      if errors and obj.values:
        self.errorlog.attribute_error(self.frame.current_opcode, obj, attr)
      raise exceptions.ByteCodeAttributeError("No such attribute %s" % attr)
    return self.join_cfg_nodes(nodes), result

  def load_attr(self, state, obj, attr):
    node, result = self._retrieve_attr(state.node, obj, attr)
    return state.change_cfg_node(node), result

  def load_attr_noerror(self, state, obj, attr):
    node, result = self._retrieve_attr(state.node, obj, attr, errors=False)
    return state.change_cfg_node(node), result

  def store_attr(self, state, obj, attr, value):
    """Set an attribute on an object."""
    assert isinstance(obj, typegraph.Variable)
    assert isinstance(attr, str)
    assert isinstance(value, typegraph.Variable)
    if not obj.values:
      log.info("Ignoring setattr on %r", obj)
      return state
    nodes = []
    for val in obj.values:
      # TODO(kramm): Check whether val.data is a descriptor (i.e. has "__set__")
      nodes.append(val.data.set_attribute(state.node, attr, value))
    return state.change_cfg_node(
        self.join_cfg_nodes(nodes))

  def del_attr(self, state, obj, attr):
    """Delete an attribute."""
    # TODO(kramm): Store abstract.Nothing
    log.warning("Attribute removal does not actually do "
                "anything in the abstract interpreter")
    return state

  def build_bool(self, node, value=None):
    if value is None:
      name, val = "bool", self.primitive_class_instances[bool]
    elif value is True:
      name, val = "True", self.true_value
    elif value is False:
      name, val = "False", self.false_value
    else:
      raise ValueError("Invalid bool value: %r", value)
    return val.to_variable(node, name)

  def build_string(self, node, s):
    return self.convert_constant(repr(s), s)

  def build_content(self, node, elements):
    var = self.program.NewVariable("<elements>")
    for v in elements:
      var.PasteVariable(v, node)
    return var

  def build_slice(self, node, start, stop, step=None):
    return self.primitive_class_instances[slice].to_variable(node, "slice")

  def tuple_to_value(self, node, content):
    """Create a VM tuple from the given sequence."""
    content = tuple(content)  # content might be a generator
    value = abstract.AbstractOrConcreteValue(
        content, self.tuple_type, self)
    value.initialize_type_parameter(node, "T",
                                    self.build_content(node, content))
    return value

  def build_tuple(self, node, content):
    """Create a VM tuple from the given sequence."""
    return self.tuple_to_value(node, content).to_variable(node, name="tuple")

  def build_list(self, node, content):
    """Create a VM list from the given sequence."""
    content = list(content)  # content might be a generator
    value = abstract.Instance(self.list_type, self)
    value.initialize_type_parameter(node, "T",
                                    self.build_content(node, content))
    return value.to_variable(node, name="list(...)")

  def build_set(self, node, content):
    """Create a VM set from the given sequence."""
    content = list(content)  # content might be a generator
    value = abstract.Instance(self.set_type, self)
    value.initialize_type_parameter(node, "T",
                                    self.build_content(node, content))
    return value.to_variable(node, name="set(...)")

  def build_map(self, node):
    """Create an empty VM dict."""
    return abstract.Dict("dict()", self).to_variable(node, "dict()")

  def push_last_exception(self, state):
    log.info("Pushing exception %r", state.exception)
    exctype, value, tb = state.exception
    return state.push(tb, value, exctype)

  def del_subscr(self, state, obj, subscr):
    log.warning("Subscript removal does not actually do "
                "anything in the abstract interpreter")
    # TODO(kramm): store abstract.Nothing
    return state

  def pop_varargs(self, state):
    """Retrieve a varargs tuple from the stack. Used by call_function."""
    state, args_var = state.pop()
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
      args = None
    return state, args

  def pop_kwargs(self, state):
    """Retrieve a kwargs dictionary from the stack. Used by call_function."""
    return state.pop()

  def convert_locals_or_globals(self, d, name="globals"):
    return abstract.LazyAbstractOrConcreteValue(
        name, d, d, self.maybe_convert_constant, self)

  # TODO(kramm): memoize
  def import_module(self, name, level):
    """Import the module and return the module object.

    Args:
      name: Name of the module. E.g. "sys".
      level: Specifies whether to use absolute or relative imports.
        -1: (Python <= 3.1) "Normal" import. Try both absolute and relative.
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
        ast = self.loader.import_name(name)
        if level == -1 and self.loader.base_module and not ast:
          ast = self.loader.import_relative_name(name)
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
      module_data = ast.constants + ast.classes + ast.functions + ast.aliases
      members = {val.name.rsplit(".")[-1]: val
                 for val in module_data}
      return abstract.Module(self, ast.name, members)
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
    state, result = self.call_function_with_state(state, method, [], {})
    state = state.push(result)
    return state

  def byte_UNARY_NOT(self, state):
    state = state.pop_and_discard()
    state = state.push(self.build_bool(state.node))
    return state

  def byte_UNARY_CONVERT(self, state):
    return self.unary_operator(state, "__repr__")

  def byte_UNARY_NEGATIVE(self, state):
    return self.unary_operator(state, "__neg__")

  def byte_UNARY_POSITIVE(self, state):
    return self.unary_operator(state, "__pos__")

  def byte_UNARY_INVERT(self, state):
    return self.unary_operator(state, "__invert__")

  def byte_BINARY_ADD(self, state):
    return self.binary_operator(state, "__add__")

  def byte_BINARY_SUBTRACT(self, state):
    return self.binary_operator(state, "__sub__")

  def byte_BINARY_DIVIDE(self, state):
    return self.binary_operator(state, "__div__")

  def byte_BINARY_MULTIPLY(self, state):
    return self.binary_operator(state, "__mul__")

  def byte_BINARY_MODULO(self, state):
    return self.binary_operator(state, "__mod__")

  def byte_BINARY_LSHIFT(self, state):
    return self.binary_operator(state, "__lshift__")

  def byte_BINARY_RSHIFT(self, state):
    return self.binary_operator(state, "__rshift__")

  def byte_BINARY_AND(self, state):
    return self.binary_operator(state, "__and__")

  def byte_BINARY_XOR(self, state):
    return self.binary_operator(state, "__xor__")

  def byte_BINARY_OR(self, state):
    return self.binary_operator(state, "__or__")

  def byte_BINARY_FLOOR_DIVIDE(self, state):
    return self.binary_operator(state, "__floordiv__")

  def byte_BINARY_TRUE_DIVIDE(self, state):
    return self.binary_operator(state, "__truediv__")

  def byte_BINARY_POWER(self, state):
    return self.binary_operator(state, "__pow__")

  def byte_BINARY_SUBSCR(self, state):
    (container, index) = state.topn(2)
    state = self.binary_operator(state, "__getitem__")
    if state.top().values:
      return state
    else:
      self.errorlog.index_error(
          self.frame.current_opcode, container, index)
      return state

  def byte_INPLACE_ADD(self, state):
    # TODO(kramm): This should fall back to __add__ (also below)
    return self.binary_operator(state, "__iadd__")

  def byte_INPLACE_SUBTRACT(self, state):
    return self.inplace_operator(state, "__isub__")

  def byte_INPLACE_MULTIPLY(self, state):
    return self.inplace_operator(state, "__imul__")

  def byte_INPLACE_DIVIDE(self, state):
    return self.inplace_operator(state, "__idiv__")

  def byte_INPLACE_MODULO(self, state):
    return self.inplace_operator(state, "__imod__")

  def byte_INPLACE_POWER(self, state):
    return self.inplace_operator(state, "__ipow__")

  def byte_INPLACE_LSHIFT(self, state):
    return self.inplace_operator(state, "__ilshift__")

  def byte_INPLACE_RSHIFT(self, state):
    return self.inplace_operator(state, "__irshift__")

  def byte_INPLACE_AND(self, state):
    return self.inplace_operator(state, "__iand__")

  def byte_INPLACE_XOR(self, state):
    return self.inplace_operator(state, "__ixor__")

  def byte_INPLACE_OR(self, state):
    return self.inplace_operator(state, "__ior__")

  def byte_INPLACE_FLOOR_DIVIDE(self, state):
    return self.inplace_operator(state, "__ifloordiv__")

  def byte_INPLACE_TRUE_DIVIDE(self, state):
    return self.inplace_operator(state, "__itruediv__")

  def byte_LOAD_CONST(self, state, op):
    const = self.frame.f_code.co_consts[op.arg]
    return state.push(self.load_constant(const))

  def byte_POP_TOP(self, state):
    return state.pop_and_discard()

  def byte_DUP_TOP(self, state):
    return state.push(state.top())

  def byte_DUP_TOPX(self, state, op):
    state, items = state.popn(op.arg)
    state = state.push(*items)
    state = state.push(*items)
    return state

  def byte_DUP_TOP_TWO(self, state):
    # Py3 only
    state, (a, b) = state.popn(2)
    return state.push(a, b, a, b)

  def byte_ROT_TWO(self, state):
    state, (a, b) = state.popn(2)
    return state.push(b, a)

  def byte_ROT_THREE(self, state):
    state, (a, b, c) = state.popn(3)
    return state.push(c, a, b)

  def byte_ROT_FOUR(self, state):
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
          self.errorlog.name_error(self.frame.current_opcode, name)
          return state.push(self.create_new_unsolvable(state.node, name))
    return state.push(val)

  def byte_STORE_NAME(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    state, value = state.pop()
    state = self.store_local(state, name, value)
    # TODO(kramm): Why does adding
    #  state = state.forward_cfg_node()
    # here break the 'testMaybeAny' test in test_containers.py?
    return state

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
      raise exceptions.ByteCodeUnboundLocalError(
          "local variable '%s' referenced before assignment" % name
      )
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
        raise exceptions.ByteCodeNameError(
            "global name '%s' is not defined" % name)
    return state.push(val)

  def byte_STORE_GLOBAL(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    state, value = state.pop()
    state = self.store_global(state, name, value)
    return state

  def byte_DELETE_GLOBAL(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    self.del_global(name)

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

  def byte_LOAD_LOCALS(self, state):
    log.debug("Returning locals: %r", self.frame.f_locals)
    locals_dict = self.maybe_convert_constant("locals", self.frame.f_locals)
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
      ret = self.build_bool(state.node)
    elif op.arg == slots.CMP_IS_NOT:
      ret = self.build_bool(state.node)
    elif op.arg == slots.CMP_NOT_IN:
      ret = self.build_bool(state.node)
    elif op.arg == slots.CMP_IN:
      ret = self.build_bool(state.node)
    elif op.arg == slots.CMP_EXC_MATCH:
      ret = self.build_bool(state.node)
    else:
      raise VirtualMachineError("Invalid argument to COMPARE_OP: %d", op.arg)
    return state.push(ret)

  def byte_LOAD_ATTR(self, state, op):
    """Pop an object, and retrieve a named attribute from it."""
    name = self.frame.f_code.co_names[op.arg]
    state, obj = state.pop()
    log.debug("LOAD_ATTR: %r %r", obj, name)
    try:
      state, val = self.load_attr(state, obj, name)
    except exceptions.ByteCodeAttributeError:
      log.warning("No such attribute %s", name)
      state = state.push(self.create_new_unsolvable(state.node, "bad attr"))
    else:
      state = state.push(val)
    return state

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
    state, _ = self.call_function_with_state(state, f, [key, val], {})
    return state

  def byte_STORE_SUBSCR(self, state):
    state, (val, obj, subscr) = state.popn(3)
    state = state.forward_cfg_node()
    state = self.store_subscr(state, obj, subscr, val)
    return state

  def byte_DELETE_SUBSCR(self, state):
    state, (obj, subscr) = state.popn(2)
    return self.del_subscr(state, obj, subscr)

  def byte_BUILD_TUPLE(self, state, op):
    count = op.arg
    state, elts = state.popn(count)
    return state.push(self.build_tuple(state.node, elts))

  def byte_BUILD_LIST(self, state, op):
    count = op.arg
    state, elts = state.popn(count)
    return state.push(self.build_list(state.node, elts))

  def byte_BUILD_SET(self, state, op):
    count = op.arg
    state, elts = state.popn(count)
    return state.push(self.build_set(state.node, elts))

  def byte_BUILD_MAP(self, state, op):
    # op.arg (size) is ignored.
    return state.push(self.build_map(state.node))

  def byte_STORE_MAP(self, state):
    state, (the_map, val, key) = state.popn(3)
    state = self.store_subscr(state, the_map, key, val)
    return state.push(the_map)

  def byte_UNPACK_SEQUENCE(self, state, op):
    """Pops a tuple (or other iterable) and pushes it onto the VM's stack."""
    state, seq = state.pop()
    state, f = self.load_attr(state, seq, "__iter__")
    state, itr = self.call_function_with_state(state, f, [], {})
    values = []
    for _ in range(op.arg):
      # TODO(ampere): Fix for python 3
      state, f = self.load_attr(state, itr, "next")
      state, result = self.call_function_with_state(state, f, [], {})
      values.append(result)
    for value in reversed(values):
      state = state.push(value)
    return state

  def byte_BUILD_SLICE(self, state, op):
    if op.arg == 2:
      state, (x, y) = state.popn(2)
      return state.push(self.build_slice(state.node, x, y))
    elif op.arg == 3:
      state, (x, y, z) = state.popn(3)
      return state.push(self.build_slice(state.node, x, y, z))
    else:       # pragma: no cover
      raise VirtualMachineError("Strange BUILD_SLICE count: %r" % op.arg)

  def byte_LIST_APPEND(self, state, op):
    # Used by the compiler e.g. for [x for x in ...]
    count = op.arg
    state, val = state.pop()
    the_list = state.peek(count)
    state, f = self.load_attr(state, the_list, "append")
    state, _ = self.call_function_with_state(state, f, [val], {})
    return state

  def byte_SET_ADD(self, state, op):
    # Used by the compiler e.g. for {x for x in ...}
    count = op.arg
    state, val = state.pop()
    the_set = state.peek(count)
    state, f = self.load_attr(state, the_set, "add")
    state, _ = self.call_function_with_state(state, f, [val], {})
    return state

  def byte_MAP_ADD(self, state, op):
    # Used by the compiler e.g. for {x, y for x, y in ...}
    count = op.arg
    state, (val, key) = state.popn(2)
    the_map = state.peek(count)
    state, f = self.load_attr(state, the_map, "__setitem__")
    state, _ = self.call_function_with_state(state, f, [key, val], {})
    return state

  def byte_PRINT_EXPR(self, state):
    # Only used in the interactive interpreter, not in modules.
    return state.pop_and_discard()

  def byte_PRINT_ITEM(self, state):
    state, item = state.pop()
    self.print_item(item)
    return state

  def byte_PRINT_ITEM_TO(self, state):
    state, to = state.pop()
    state, item = state.pop()
    self.print_item(item, to)
    return state

  def byte_PRINT_NEWLINE(self, state):
    self.print_newline()
    return state

  def byte_PRINT_NEWLINE_TO(self, state):
    state, to = state.pop()
    self.print_newline(to)
    return state

  def byte_JUMP_IF_TRUE_OR_POP(self, state, op):
    self.store_jump(op.target, state.forward_cfg_node())
    return state.pop_and_discard()

  def byte_JUMP_IF_FALSE_OR_POP(self, state, op):
    self.store_jump(op.target, state.forward_cfg_node())
    return state.pop_and_discard()

  def byte_JUMP_IF_TRUE(self, state, op):  # Not in py2.7
    self.store_jump(op.target, state.forward_cfg_node())
    return state

  def byte_JUMP_IF_FALSE(self, state, op):  # Not in py2.7
    self.store_jump(op.target, state.forward_cfg_node())
    return state

  def byte_POP_JUMP_IF_TRUE(self, state, op):
    state, unused_val = state.pop()
    self.store_jump(op.target, state.forward_cfg_node())
    return state

  def byte_POP_JUMP_IF_FALSE(self, state, op):
    state, unused_val = state.pop()
    self.store_jump(op.target, state.forward_cfg_node())
    return state

  def byte_JUMP_FORWARD(self, state, op):
    self.store_jump(op.target, state.forward_cfg_node())
    return state

  def byte_JUMP_ABSOLUTE(self, state, op):
    self.store_jump(op.target, state.forward_cfg_node())
    return state

  def byte_SETUP_LOOP(self, state, op):
    return self.push_block(state, "loop", op.target)

  def byte_GET_ITER(self, state):
    state, seq = state.pop()
    state, it = self.load_attr(state, seq, "__iter__")
    state = state.push(it)
    return self.call_function_from_stack(state, 0, [])

  def store_jump(self, target, state):
    self.frame.states[target] = state.merge_into(self.frame.states.get(target))

  def byte_FOR_ITER(self, state, op):
    self.store_jump(op.target, state.pop_and_discard())
    state, f = self.load_attr(state, state.top(), "next")
    state = state.push(f)
    return self.call_function_from_stack(state, 0, [])

  def byte_BREAK_LOOP(self, state):
    return state.set_why("break")

  def byte_CONTINUE_LOOP(self, state, op):
    # This is a trick with the return value.
    # While unrolling blocks, continue and return both have to preserve
    # state as the finally blocks are executed.  For continue, it's
    # where to jump to, for return, it's the value to return.  It gets
    # pushed on the stack for both, so continue puts the jump destination
    # into return_value.
    # TODO(kramm): This probably doesn't work.
    return state.set_why("continue")

  def byte_SETUP_EXCEPT(self, state, op):
    # Assume that it's possible to throw the exception at the first
    # instruction of the code:
    self.store_jump(op.target, self.push_abstract_exception(state))
    return self.push_block(state, "setup-except", op.target)

  def byte_SETUP_FINALLY(self, state, op):
    # Emulate finally by connecting the try to the finally block (with
    # empty reason/why/continuation):
    self.store_jump(op.target, state.push(None))
    return self.push_block(state, "finally", op.target)

  def byte_POP_BLOCK(self, state):
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

  def byte_POP_EXCEPT(self, state):  # Python 3 only
    state, block = state.pop_block()
    if block.type != "except-handler":
      raise VirtualMachineError("popped block is not an except handler")
    return self.unwind_block(block, state)

  def byte_SETUP_WITH(self, state, op):
    """Starts a 'with' statement. Will push a block."""
    state, ctxmgr = state.pop()
    state, exit_method = self.load_attr(state, ctxmgr, "__exit__")
    state = state.push(exit_method)
    state, enter = self.load_attr(state, ctxmgr, "__enter__")
    state, ctxmgr_obj = self.call_function_with_state(state, enter, [])
    if self.python_version[0] == 2:
      state = self.push_block(state, "with", op.target)
    else:
      assert self.python_version[0] == 3
      state = self.push_block(state, "finally", op.target)
    return state.push(ctxmgr_obj)

  def byte_WITH_CLEANUP(self, state):
    """Called at the end of a with block. Calls the exit handlers etc."""
    # The code here does some weird stack manipulation: the exit function
    # is buried in the stack, and where depends on what's on top of it.
    # Pull out the exit function, and leave the rest in place.
    u = state.top()
    if isinstance(u, str):
      if u in ("return", "continue"):
        state, exit_func = state.pop_nth(2)
      else:
        state, exit_func = state.pop_nth(1)
      v = self.make_none(state.node)
      w = self.make_none(state.node)
      u = self.make_none(state.node)
    elif isinstance(u, type) and issubclass(u, BaseException):
      if self.python_version[0] == 2:
        state, (w, v, u) = state.popn(3)
        state, exit_func = state.pop()
        state = state.push(w, v, u)
      else:
        assert self.python_version[0] == 3
        state, (w, v, u) = state.popn(3)
        state, (tp, exc, tb) = state.popn(3)
        state, (exit_func) = state.pop()
        state = state.push(tp, exc, tb)
        state = state.push(self.make_none(state.node))
        state = state.push(w, v, u)
        state, block = state.pop_block()
        assert block.type == "except-handler"
        state = state.push_block(block.type, block.handler, block.level - 1)
    else:
      # This is the case when None just got pushed to the top of the stack,
      # to signal that we're at the end of the with block and no exception
      # occured.
      state = state.pop_and_discard()  # pop None
      state, exit_func = state.pop()
      state = state.push(self.make_none(state.node))
      v = self.make_none(state.node)
      w = self.make_none(state.node)
    state, suppress_exception = self.call_function_with_state(
        state, exit_func, [u, v, w])
    log.info("u is None: %r", self.is_none(u))
    err = (not self.is_none(u)) and bool(suppress_exception)
    if err:
      # An error occurred, and was suppressed
      if self.python_version[0] == 2:
        state, _ = state.popn(3)
        state.push(self.make_none(state.node))
      else:
        assert self.python_version[0] == 3
        state = state.push("silenced")
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
    state, annotations = state.popn((arg >> 16) & 0x7fff)
    state, kw_defaults = state.popn(2 * num_kw_defaults)
    state, pos_defaults = state.popn(num_pos_defaults)
    return state, pos_defaults, kw_defaults, annotations

  def byte_MAKE_FUNCTION(self, state, op):
    """Create a function and push it onto the stack."""
    if self.python_version[0] == 2:
      name = None
    else:
      assert self.python_version[0] == 3
      state, name_var = state.pop()
      name = _get_atomic_python_constant(name_var)
    state, code = state.pop()
    # TODO(dbaum): Handle kw_defaults and annotations (Python 3).
    state, defaults, _, _ = self._pop_extra_function_args(state, op.arg)
    globs = self.get_globals_dict()
    fn = self.make_function(name, code, globs, defaults)
    return state.push(fn)

  def byte_MAKE_CLOSURE(self, state, op):
    """Make a function that binds local variables."""
    if self.python_version[0] == 2:
      # The py3 docs don't mention this change.
      name = None
    else:
      assert self.python_version[0] == 3
      state, name_var = state.pop()
      name = _get_atomic_python_constant(name_var)
    state, (closure, code) = state.popn(2)
    # TODO(dbaum): Handle kw_defaults and annotations (Python 3).
    state, defaults, _, _ = self._pop_extra_function_args(state, op.arg)
    globs = self.get_globals_dict()
    fn = self.make_function(name, code, globs, defaults, closure)
    return state.push(fn)

  def byte_CALL_FUNCTION(self, state, op):
    return self.call_function_from_stack(state, op.arg, [])

  def byte_CALL_FUNCTION_VAR(self, state, op):
    state, args = self.pop_varargs(state)
    return self.call_function_from_stack(state, op.arg, args)

  def byte_CALL_FUNCTION_KW(self, state, op):
    state, kwargs = self.pop_kwargs(state)
    return self.call_function_from_stack(state, op.arg, [], kwargs)

  def byte_CALL_FUNCTION_VAR_KW(self, state, op):
    state, kwargs = self.pop_kwargs(state)
    state, args = self.pop_varargs(state)
    return self.call_function_from_stack(state, op.arg, args, kwargs)

  def byte_YIELD_VALUE(self, state):
    state, ret = state.pop()
    self.frame.yield_variable.PasteVariable(ret, state.node)
    return state.set_why("yield")

  def byte_IMPORT_NAME(self, state, op):
    """Import a single module."""
    full_name = self.frame.f_code.co_names[op.arg]
    # The identifiers in the (unused) fromlist are repeated in IMPORT_FROM.
    state, (level, fromlist) = state.popn(2)
    # The IMPORT_NAME for an "import a.b.c" will push the module "a".
    # However, for "from a.b.c import Foo" it'll push the module "a.b.c". Those
    # two cases are distinguished by whether fromlist is None or not.
    if self.is_none(fromlist):
      name = full_name.split(".", 1)[0]  # "a.b.c" -> "a"
    else:
      name = full_name
    module = self.import_module(name, _get_atomic_python_constant(level))
    if module is None:
      log.warning("Couldn't find module %r", name)
      self.errorlog.import_error(self.frame.current_opcode, name)
      module = self._create_new_unknown_value("import")
    return state.push(module.to_variable(state.node, name))

  def byte_IMPORT_FROM(self, state, op):
    """IMPORT_FROM is mostly like LOAD_ATTR but doesn't pop the container."""
    name = self.frame.f_code.co_names[op.arg]
    module = state.top()
    state, attr = self.load_attr(state, module, name)
    return state.push(attr)

  def byte_EXEC_STMT(self, state):
    state, (unused_stmt, unused_globs, unused_locs) = state.popn(3)
    log.warning("Encountered 'exec' statement. 'exec' is unsupported.")
    return state

  def byte_BUILD_CLASS(self, state):
    state, (name, bases, methods) = state.popn(3)
    return state.push(self.make_class(state.node, name, bases, methods))

  def byte_LOAD_BUILD_CLASS(self, state):
    # New in py3
    return state.push(__builtins__.__build_class__)

  def byte_STORE_LOCALS(self, state):
    state, locals_dict = state.pop()
    self.frame.f_locals = _get_atomic_value(locals_dict)
    return state

  def byte_END_FINALLY(self, state):
    state, exc = state.pop()
    if self.is_none(exc):
      return state
    else:
      log.info("Popping exception %r", exc)
      state = state.pop_and_discard()
      state = state.pop_and_discard()
    return state

  def byte_RETURN_VALUE(self, state):
    state, var = state.pop()
    self.frame.return_variable.PasteVariable(var, state.node)
    return state.set_why("return")

  def byte_IMPORT_STAR(self, state):
    """Pops a module and stores all its contents in locals()."""
    # TODO(kramm): this doesn't use __all__ properly.
    state, mod_var = state.pop()
    mod = _get_atomic_value(mod_var)
    if isinstance(mod, abstract.Unknown):
      log.error("Doing 'from module import *' from unresolved module")
      return state
    log.info("%r", mod)
    # TODO(kramm): Add Module type to abstract.py
    for name, var in mod.items():
      if name[0] != "_":
        state = self.store_local(state, name, var)
    return state

  def byte_SLICE_0(self, state):
    return self.get_slice(state, 0)

  def byte_SLICE_1(self, state):
    return self.get_slice(state, 1)

  def byte_SLICE_2(self, state):
    return self.get_slice(state, 2)

  def byte_SLICE_3(self, state):
    return self.get_slice(state, 3)

  def byte_STORE_SLICE_0(self, state):
    return self.store_slice(state, 0)

  def byte_STORE_SLICE_1(self, state):
    return self.store_slice(state, 1)

  def byte_STORE_SLICE_2(self, state):
    return self.store_slice(state, 2)

  def byte_STORE_SLICE_3(self, state):
    return self.store_slice(state, 3)

  def byte_DELETE_SLICE_0(self, state):
    return self.delete_slice(state, 0)

  def byte_DELETE_SLICE_1(self, state):
    return self.delete_slice(state, 1)

  def byte_DELETE_SLICE_2(self, state):
    return self.delete_slice(state, 2)

  def byte_DELETE_SLICE_3(self, state):
    return self.delete_slice(state, 3)
