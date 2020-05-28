# Lint as: python3
"""A abstract virtual machine for python bytecode.

A VM for python byte code that uses pytype/pytd/cfg to generate a trace of the
program execution.
"""

# We have names like "byte_NOP":
# pylint: disable=invalid-name

# Bytecodes don't always use all their arguments:
# pylint: disable=unused-argument

import collections
import contextlib
import itertools
import logging
import os
import re

from pytype import abstract
from pytype import abstract_utils
from pytype import annotations_util
from pytype import attribute
from pytype import blocks
from pytype import compare
from pytype import convert
from pytype import datatypes
from pytype import directors
from pytype import function
from pytype import overlay_dict
from pytype import load_pytd
from pytype import matcher
from pytype import metaclass
from pytype import metrics
from pytype import mixin
from pytype import special_builtins
from pytype import state as frame_state
from pytype import utils
from pytype.pyc import loadmarshal
from pytype.pyc import opcodes
from pytype.pyc import pyc
from pytype.pyi import parser
from pytype.pytd import mro
from pytype.pytd import slots
from pytype.pytd import visitors
from pytype.typegraph import cfg
from pytype.typegraph import cfg_utils
import six

log = logging.getLogger(__name__)

_FUNCTION_TYPE_COMMENT_RE = re.compile(r"^\((.*)\)\s*->\s*(\S.*?)\s*$")

# Create a repr that won't overflow.
_TRUNCATE = 120
_TRUNCATE_STR = 72
repr_obj = six.moves.reprlib.Repr()
repr_obj.maxother = _TRUNCATE
repr_obj.maxstring = _TRUNCATE_STR
repper = repr_obj.repr


Block = collections.namedtuple("Block", ["type", "op", "handler", "level"])


class LocalOp(collections.namedtuple("_LocalOp", ["name", "op"])):
  ASSIGN = 1
  ANNOTATE = 2

  def is_assign(self):
    return self.op == self.ASSIGN

  def is_annotate(self):
    return self.op == self.ANNOTATE


class Local:
  """A possibly annotated local variable."""

  def __init__(self, node, op, typ, orig, vm):
    self.last_op = op
    if typ:
      self.typ = vm.program.NewVariable([typ], [], node)
    else:
      # Creating too many variables bloats the typegraph, hurting performance,
      # so we use None instead of an empty variable.
      self.typ = None
    self.orig = orig
    self.vm = vm

  @property
  def stack(self):
    return self.vm.simple_stack(self.last_op)

  def update(self, node, op, typ, orig):
    self.last_op = op
    if typ:
      if self.typ:
        self.typ.AddBinding(typ, [], node)
      else:
        self.typ = self.vm.program.NewVariable([typ], [], node)
    if orig:
      self.orig = orig

  def get_type(self, node, name):
    """Gets the variable's annotation."""
    if not self.typ:
      return None
    values = self.typ.Data(node)
    if len(values) > 1:
      self.vm.errorlog.ambiguous_annotation(self.stack, values, name)
      return self.vm.convert.unsolvable
    elif values:
      return values[0]
    else:
      return None


_opcode_counter = metrics.MapCounter("vm_opcode")


class VirtualMachineError(Exception):
  """For raising errors in the operation of the VM."""


class _FindIgnoredTypeComments(object):
  """A visitor that finds type comments that will be ignored."""

  def __init__(self, type_comments):
    self._type_comments = type_comments
    # Lines will be removed from this set during visiting. Any lines that remain
    # at the end are type comments that will be ignored.
    self._ignored_type_lines = set(type_comments)

  def visit_code(self, code):
    """Interface for pyc.visit."""
    for op in code.co_code:
      # Make sure we have attached the type comment to an opcode.
      if isinstance(op, blocks.STORE_OPCODES):
        if op.annotation:
          annot = op.annotation
          if self._type_comments.get(op.line) == annot:
            self._ignored_type_lines.discard(op.line)
      elif isinstance(op, opcodes.MAKE_FUNCTION):
        if op.annotation:
          _, line = op.annotation
          self._ignored_type_lines.discard(line)
    return code

  def ignored_lines(self):
    """Returns a set of lines that contain ignored type comments."""
    return self._ignored_type_lines


class VirtualMachine(object):
  """A bytecode VM that generates a cfg as it executes."""

  # This class is defined inside VirtualMachine so abstract.py can use it.
  class VirtualMachineRecursionError(Exception):
    pass

  def __init__(self,
               errorlog,
               options,
               loader,
               generate_unknowns=False,
               store_all_calls=False):
    """Construct a TypegraphVirtualMachine."""
    self.maximum_depth = None  # set by run_program() and analyze()
    self.errorlog = errorlog
    self.options = options
    self.python_version = options.python_version
    self.PY2 = self.python_version[0] == 2
    self.PY3 = self.python_version[0] == 3
    self.generate_unknowns = generate_unknowns
    self.store_all_calls = store_all_calls
    self.loader = loader
    self.frames = []  # The call stack of frames.
    # A map: {string_of_undefined_name: List[LateAnnotation]}.
    # Every LateAnnotation depends on a single undefined name, so once that name
    # is defined, we immediately resolve the annotation.
    self.late_annotations = collections.defaultdict(list)
    self.functions_type_params_check = []
    self.concrete_classes = []
    self.frame = None  # The current frame.
    self.program = cfg.Program()
    self.root_cfg_node = self.program.NewCFGNode("root")
    self.program.entrypoint = self.root_cfg_node
    self.annotations_util = annotations_util.AnnotationsUtil(self)
    self.attribute_handler = attribute.AbstractAttributeHandler(self)
    self.matcher = matcher.AbstractMatcher(self)
    self.loaded_overlays = {}  # memoize which overlays are loaded
    self.convert = convert.Converter(self)
    self.program.default_data = self.convert.unsolvable
    self.has_unknown_wildcard_imports = False
    self.callself_stack = []
    self.filename = None
    self.director = None
    self._analyzing = False  # Are we in self.analyze()?
    self.opcode_traces = []
    self._importing = False  # Are we importing another file?
    self._trace_opcodes = True  # whether to trace opcodes
    # If set, we will generate LateAnnotations with this stack rather than
    # logging name errors.
    self._late_annotations_stack = None

    # Track the order of creation of local vars, for attrs and dataclasses.
    self.local_ops = {}
    # Record the annotated and original values of locals.
    self.annotated_locals = {}

    # Map from builtin names to canonical objects.
    self.special_builtins = {
        # The super() function.
        "super": self.convert.super_type,
        # The object type.
        "object": self.convert.object_type,
        # for more pretty branching tests.
        "__random__": self.convert.primitive_class_instances[bool],
        # for debugging
        "reveal_type": special_builtins.RevealType(self),
        # boolean values.
        "True": self.convert.true,
        "False": self.convert.false,
        # builtin classes
        "property": special_builtins.Property(self),
        "staticmethod": special_builtins.StaticMethod(self),
        "classmethod": special_builtins.ClassMethod(self),
    }
    # builtin functions
    for cls in (
        special_builtins.Abs,
        special_builtins.Filter,
        special_builtins.HasAttr,
        special_builtins.IsCallable,
        special_builtins.IsInstance,
        special_builtins.IsSubclass,
        special_builtins.Next,
        special_builtins.Open
    ):
      self.special_builtins[cls.name] = cls.make(self)

  @property
  def current_local_ops(self):
    return self.local_ops[self.frame.f_code.co_name]

  @property
  def current_annotated_locals(self):
    return self.annotated_locals[self.frame.f_code.co_name]

  @contextlib.contextmanager
  def _suppress_opcode_tracing(self):
    old_trace_opcodes = self._trace_opcodes
    self._trace_opcodes = False
    try:
      yield
    finally:
      self._trace_opcodes = old_trace_opcodes

  @contextlib.contextmanager
  def generate_late_annotations(self, stack):
    old_late_annotations_stack = self._late_annotations_stack
    self._late_annotations_stack = stack
    try:
      yield
    finally:
      self._late_annotations_stack = old_late_annotations_stack

  def trace_opcode(self, op, symbol, val):
    """Record trace data for other tools to use."""
    if not self._trace_opcodes:
      return

    if self.frame and not op:
      op = self.frame.current_opcode
    if not op:
      # If we don't have a current opcode, don't emit a trace.
      return

    def get_data(v):
      data = getattr(v, "data", None)
      # Sometimes v is a binding.
      return [data] if data and not isinstance(data, list) else data

    # isinstance(val, tuple) generates false positives for internal classes that
    # are namedtuples.
    if val.__class__ == tuple:
      data = tuple(get_data(v) for v in val)
    else:
      data = (get_data(val),)
    rec = (op, symbol, data)
    self.opcode_traces.append(rec)

  def lookup_builtin(self, name):
    try:
      return self.loader.builtins.Lookup(name)
    except KeyError:
      return self.loader.typing.Lookup(name)

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
    Raises:
      VirtualMachineError: if a fatal error occurs.
    """
    _opcode_counter.inc(op.name)
    self.frame.current_opcode = op
    self._importing = "IMPORT" in op.__class__.__name__
    if log.isEnabledFor(logging.INFO):
      self.log_opcode(op, state)
    # dispatch
    bytecode_fn = getattr(self, "byte_%s" % op.name, None)
    if bytecode_fn is None:
      raise VirtualMachineError("Unknown opcode: %s" % op.name)
    state = bytecode_fn(state, op)
    if state.why in ("reraise", "NoReturn"):
      state = state.set_why("exception")
    self.frame.current_opcode = None
    return state

  def join_cfg_nodes(self, nodes):
    """Get a new node to which the given nodes have been joined."""
    assert nodes
    if len(nodes) == 1:
      return nodes[0]
    else:
      ret = self.program.NewCFGNode(self.frame and
                                    self.frame.current_opcode and
                                    self.frame.current_opcode.line)
      for node in nodes:
        node.ConnectTo(ret)
      return ret

  def run_frame(self, frame, node):
    """Run a frame (typically belonging to a method)."""
    self.push_frame(frame)
    frame.states[frame.f_code.co_code[0]] = frame_state.FrameState.init(
        node, self)
    frame_name = frame.f_code.co_name
    if frame_name not in self.local_ops or frame_name != "<module>":
      # abstract_utils.eval_expr creates a temporary frame called "<module>". We
      # don't care to track locals for this frame and don't want it to overwrite
      # the locals of the actual module frame.
      self.local_ops[frame_name] = []
      self.annotated_locals[frame_name] = {}
    can_return = False
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
      if state.why:
        # return, raise, or yield. Leave the current frame.
        can_return |= state.why in ("return", "yield")
        return_nodes.append(state.node)
      elif op.carry_on_to_next():
        # We're starting a new block, so start a new CFG node. We don't want
        # nodes to overlap the boundary of blocks.
        state = state.forward_cfg_node()
        frame.states[op.next] = state.merge_into(frame.states.get(op.next))
    self.pop_frame(frame)
    if not return_nodes:
      # Happens if the function never returns. (E.g. an infinite loop)
      assert not frame.return_variable.bindings
      frame.return_variable.AddBinding(self.convert.unsolvable, [], node)
    else:
      node = self.join_cfg_nodes(return_nodes)
      if not can_return:
        assert not frame.return_variable.bindings
        # We purposely don't check NoReturn against this function's
        # annotated return type. Raising an error in an unimplemented function
        # and documenting the intended return type in an annotation is a
        # common pattern.
        self._set_frame_return(
            node, frame, self.convert.no_return.to_variable(node))
    return node, frame.return_variable

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
    log.info("%s ## %s", indent, utils.maybe_truncate(str(op), _TRUNCATE))

  def repper(self, s):
    return repr_obj.repr(s)

  # Operators

  def pop_slice_and_obj(self, state, count):
    """Pop a slice from the data stack. Used by slice opcodes (SLICE_0 etc.)."""
    if count == 0:  # x[:]
      start = None
      end = None
    elif count == 1:  # x[i:]
      state, start = state.pop()
      end = None
    elif count == 2:  # x[:j]
      start = None
      state, end = state.pop()
    elif count == 3:  # x[i:j]
      state, end = state.pop()
      state, start = state.pop()
    else:
      raise AssertionError("invalid slice code")
    state, obj = state.pop()
    return state, (start, end), obj

  def store_slice(self, state, count):
    state, slice_args, obj = self.pop_slice_and_obj(state, count)
    slice_obj = self.convert.build_slice(state.node, *slice_args)
    state, new_value = state.pop()
    state, f = self.load_attr(state, obj, "__setitem__")
    state, _ = self.call_function_with_state(state, f, (slice_obj, new_value))
    return state

  def delete_slice(self, state, count):
    state, slice_args, obj = self.pop_slice_and_obj(state, count)
    slice_obj = self.convert.build_slice(state.node, *slice_args)
    return self._delete_item(state, obj, slice_obj)

  def get_slice(self, state, count):
    """Common implementation of all GETSLICE+<n> opcodes."""
    state, (start, end), obj = self.pop_slice_and_obj(state, count)
    method = "__getslice__"
    state, f = self.load_attr_noerror(state, obj, method)
    if f and f.bindings:
      start = start or self.convert.build_int(state.node)
      end = end or self.convert.build_int(state.node)
      args = (start, end)
    else:
      method = "__getitem__"
      state, f = self.load_attr(state, obj, method)
      slice_obj = self.convert.build_slice(state.node, start, end)
      args = (slice_obj,)
    with self._suppress_opcode_tracing():  # don't trace the magic method call
      state, ret = self.call_function_with_state(state, f, args)
    self.trace_opcode(None, method, ret)
    return state.push(ret)

  # Importing

  def join_variables(self, node, variables):
    return cfg_utils.merge_variables(self.program, node, variables)

  def join_bindings(self, node, bindings):
    return cfg_utils.merge_bindings(self.program, node, bindings)

  def merge_values(self, values):
    """Merge a collection of values into a single one."""
    if not values:
      return self.convert.empty
    elif len(values) == 1:
      return next(iter(values))
    else:
      return abstract.Union(values, self)

  def _process_base_class(self, node, base):
    """Process a base class for InterpreterClass creation."""
    new_base = self.program.NewVariable()
    for b in base.bindings:
      base_val = b.data
      if isinstance(b.data, abstract.AnnotationContainer):
        base_val = base_val.base_cls
      # A class like `class Foo(List["Foo"])` would lead to infinite recursion
      # when instantiated because we attempt to recursively instantiate its
      # parameters, so we replace any late annotations with Any.
      # TODO(rechen): only replace the current class's name. We should keep
      # other late annotations in order to support things like:
      #   class Foo(List["Bar"]): ...
      #   class Bar: ...
      base_val = self.annotations_util.remove_late_annotations(base_val)
      if isinstance(base_val, abstract.Union):
        # Union[A,B,...] is a valid base class, but we need to flatten it into a
        # single base variable.
        for o in base_val.options:
          new_base.AddBinding(o, {b}, node)
      else:
        new_base.AddBinding(base_val, {b}, node)
    base = new_base
    if not any(isinstance(t, (mixin.Class, abstract.AMBIGUOUS_OR_EMPTY))
               for t in base.data):
      self.errorlog.base_class_error(self.frames, base)
    return base

  def _filter_out_metaclasses(self, bases):
    """Process the temporary classes created by six.with_metaclass.

    six.with_metaclass constructs an anonymous class holding a metaclass and a
    list of base classes; if we find instances in `bases`, store the first
    metaclass we find and remove all metaclasses from `bases`.

    Args:
      bases: The list of base classes for the class being constructed.

    Returns:
      A tuple of (metaclass, base classes)
    """
    non_meta = []
    meta = None
    for base in bases:
      with_metaclass = False
      for b in base.data:
        if isinstance(b, metaclass.WithMetaclassInstance):
          with_metaclass = True
          if not meta:
            # Only the first metaclass gets applied.
            meta = b.get_class().to_variable(self.root_cfg_node)
          non_meta.extend(b.bases)
      if not with_metaclass:
        non_meta.append(base)
    return meta, non_meta

  def make_class(self, node, name_var, bases, class_dict_var, cls_var,
                 new_class_var=None, is_decorated=False):
    """Create a class with the name, bases and methods given.

    Args:
      node: The current CFG node.
      name_var: Class name.
      bases: Base classes.
      class_dict_var: Members of the class, as a Variable containing an
          abstract.Dict value.
      cls_var: The class's metaclass, if any.
      new_class_var: If not None, make_class() will return new_class_var with
          the newly constructed class added as a binding. Otherwise, a new
          variable if returned.
      is_decorated: True if the class definition has a decorator.


    Returns:
      A node and an instance of Class.
    """
    name = abstract_utils.get_atomic_python_constant(name_var)
    log.info("Declaring class %s", name)
    try:
      class_dict = abstract_utils.get_atomic_value(class_dict_var)
    except abstract_utils.ConversionError:
      log.error("Error initializing class %r", name)
      return self.convert.create_new_unknown(node)
    # Handle six.with_metaclass.
    metacls, bases = self._filter_out_metaclasses(bases)
    if metacls:
      cls_var = metacls
    # Flatten Unions in the bases
    bases = [self._process_base_class(node, base) for base in bases]
    if not bases:
      # A parent-less class inherits from classobj in Python 2 and from object
      # in Python 3.
      if self.PY2:
        base = self.convert.oldstyleclass_type
      else:
        base = self.convert.object_type
      bases = [base.to_variable(self.root_cfg_node)]
    if (isinstance(class_dict, abstract.Unsolvable) or
        not isinstance(class_dict, mixin.PythonConstant)):
      # An unsolvable appears here if the vm hit maximum depth and gave up on
      # analyzing the class we're now building. Otherwise, if class_dict isn't
      # a constant, then it's an abstract dictionary, and we don't have enough
      # information to continue building the class.
      var = self.new_unsolvable(node)
    else:
      if cls_var is None:
        cls_var = class_dict.members.get("__metaclass__")
        if cls_var and self.PY3:
          # This way of declaring metaclasses no longer works in Python 3.
          self.errorlog.ignored_metaclass(
              self.frames, name,
              cls_var.data[0].full_name if cls_var.bindings else "Any")
      if cls_var and all(v.data.full_name == "__builtin__.type"
                         for v in cls_var.bindings):
        cls_var = None
      # pylint: disable=g-long-ternary
      cls = abstract_utils.get_atomic_value(
          cls_var, default=self.convert.unsolvable) if cls_var else None
      try:
        val = abstract.InterpreterClass(
            name,
            bases,
            class_dict.pyval,
            cls,
            self)
        val.is_decorated = is_decorated
      except mro.MROError as e:
        self.errorlog.mro_error(self.frames, name, e.mro_seqs)
        var = self.new_unsolvable(node)
      except abstract_utils.GenericTypeError as e:
        self.errorlog.invalid_annotation(self.frames, e.annot, e.error)
        var = self.new_unsolvable(node)
      else:
        if new_class_var:
          var = new_class_var
        else:
          var = self.program.NewVariable()
        var.AddBinding(val, class_dict_var.bindings, node)
        node = val.call_metaclass_init(node)
        if not val.is_abstract:
          # Since a class decorator could have made the class inherit from
          # ABCMeta, we have to mark concrete classes now and check for
          # abstract methods at postprocessing time.
          self.concrete_classes.append((val, self.simple_stack()))
    self.trace_opcode(None, name, var)
    return node, var

  def _make_function(self, name, node, code, globs, defaults, kw_defaults,
                     closure=None, annotations=None):
    """Create a function or closure given the arguments."""
    if closure:
      closure = tuple(
          c for c in abstract_utils.get_atomic_python_constant(closure))
      log.info("closure: %r", closure)
    if not name:
      name = abstract_utils.get_atomic_python_constant(code).co_name
    if not name:
      name = "<lambda>"
    val = abstract.InterpreterFunction.make(
        name, code=abstract_utils.get_atomic_python_constant(code),
        f_locals=self.frame.f_locals, f_globals=globs,
        defaults=defaults, kw_defaults=kw_defaults,
        closure=closure, annotations=annotations, vm=self)
    # TODO(ampere): What else needs to be an origin in this case? Probably stuff
    # in closure.
    var = self.program.NewVariable()
    var.AddBinding(val, code.bindings, node)
    if val.signature.annotations:
      self.functions_type_params_check.append((val, self.frame.current_opcode))
    return var

  def make_native_function(self, name, method):
    return abstract.NativeFunction(name, method, self)

  def make_frame(self, node, code, f_globals, f_locals, callargs=None,
                 closure=None, new_locals=False, func=None, first_posarg=None):
    """Create a new frame object, using the given args, globals and locals."""
    if any(code is f.f_code for f in self.frames):
      log.info("Detected recursion in %s", code.co_name or code.co_filename)
      raise self.VirtualMachineRecursionError()

    log.info("make_frame: callargs=%s, f_globals=[%s@%x], f_locals=[%s@%x]",
             self.repper(callargs),
             type(f_globals).__name__, id(f_globals),
             type(f_locals).__name__, id(f_locals))

    # Implement NEWLOCALS flag. See Objects/frameobject.c in CPython.
    # (Also allow to override this with a parameter, Python 3 doesn't always set
    #  it to the right value, e.g. for class-level code.)
    if code.has_newlocals() or new_locals:
      f_locals = abstract.LazyConcreteDict("locals", {}, self)

    return frame_state.Frame(node, self, code, f_globals, f_locals,
                             self.frame, callargs or {}, closure, func,
                             first_posarg)

  def simple_stack(self, opcode=None):
    """Get a stack of simple frames.

    Args:
      opcode: Optionally, an opcode to create a stack for.

    Returns:
      If an opcode is provided, a stack with a single frame at that opcode.
      Otherwise, the VM's current stack converted to simple frames.
    """
    if opcode is not None:
      return (frame_state.SimpleFrame(opcode),)
    elif self.frame:
      # Simple stacks are used for things like late annotations, which don't
      # need tracebacks in their errors, so we convert just the current frame.
      return (frame_state.SimpleFrame(self.frame.current_opcode),)
    else:
      return ()

  def push_abstract_exception(self, state):
    tb = self.convert.build_list(state.node, [])
    value = self.convert.create_new_unknown(state.node)
    exctype = self.convert.create_new_unknown(state.node)
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
    code = blocks.process_code(code)
    if mode == "exec":
      self.director.adjust_line_numbers(code)
    return blocks.merge_annotations(
        code, self.director.annotations, self.director.docstrings)

  def run_bytecode(self, node, code, f_globals=None, f_locals=None):
    """Run the given bytecode."""
    if f_globals is not None:
      assert f_locals
    else:
      assert not self.frames
      assert f_locals is None
      # __name__, __doc__, and __package__ are unused placeholder values.
      f_globals = f_locals = abstract.LazyConcreteDict("globals", {
          "__builtins__": self.loader.builtins,
          "__name__": "__main__",
          "__file__": code.co_filename,
          "__doc__": None,
          "__package__": None,
      }, self)
      # __name__ is retrieved by class bodies. So make sure that it's preloaded,
      # otherwise we won't properly cache the first class initialization.
      f_globals.load_lazy_attribute("__name__")
    frame = self.make_frame(node, code, f_globals=f_globals, f_locals=f_locals)
    node, return_var = self.run_frame(frame, node)
    return node, frame.f_globals, frame.f_locals, return_var

  def run_program(self, src, filename, maximum_depth):
    """Run the code and return the CFG nodes.

    Args:
      src: The program source code.
      filename: The filename the source is from.
      maximum_depth: Maximum depth to follow call chains.
    Returns:
      A tuple (CFGNode, set) containing the last CFGNode of the program as
        well as all the top-level names defined by it.
    """
    director = directors.Director(
        src, self.errorlog, filename, self.options.disable)

    # This modifies the errorlog passed to the constructor.  Kind of ugly,
    # but there isn't a better way to wire both pieces together.
    self.errorlog.set_error_filter(director.should_report_error)
    self.director = director
    self.filename = filename

    self.maximum_depth = maximum_depth

    code = self.compile_src(src, filename=filename)
    visitor = _FindIgnoredTypeComments(self.director.type_comments)
    pyc.visit(code, visitor)
    for line in visitor.ignored_lines():
      self.errorlog.ignored_type_comment(
          self.filename, line, self.director.type_comments[line])

    node = self.root_cfg_node.ConnectNew("init")
    node, f_globals, f_locals, _ = self.run_bytecode(node, code)
    logging.info("Done running bytecode, postprocessing globals")
    # Check for abstract methods on non-abstract classes.
    for val, frames in self.concrete_classes:
      if not val.is_abstract:
        for member in sum((var.data for var in val.members.values()), []):
          if isinstance(member, abstract.Function) and member.is_abstract:
            self.errorlog.ignored_abstractmethod(frames, val.name, member.name)
    for annot in itertools.chain.from_iterable(self.late_annotations.values()):
      # If `annot` has already been resolved, this is a no-op. Otherwise, it
      # contains a real name error that will be logged when we resolve it now.
      annot.resolve(node, f_globals, f_locals)
    self.late_annotations = None  # prevent adding unresolvable annotations
    for func, opcode in self.functions_type_params_check:
      func.signature.check_type_parameter_count(self.simple_stack(opcode))
    assert not self.frames, "Frames left over!"
    log.info("Final node: <%d>%s", node.id, node.name)
    return node, f_globals.members

  def _base(self, cls):
    if isinstance(cls, abstract.ParameterizedClass):
      return cls.base_cls
    return cls

  def _overrides(self, node, subcls, supercls, attr):
    """Check whether subcls_var overrides or newly defines the given attribute.

    Args:
      node: The current node.
      subcls: A potential subclass.
      supercls: A potential superclass.
      attr: An attribute name.

    Returns:
      True if subcls_var is a subclass of supercls_var and overrides or newly
      defines the attribute. False otherwise.
    """
    if subcls and supercls and supercls in subcls.mro:
      subcls = self._base(subcls)
      supercls = self._base(supercls)
      for cls in subcls.mro:
        if cls == supercls:
          break
        if cls.is_lazy:
          cls.load_lazy_attribute(attr)
        if attr in cls.members and cls.members[attr].bindings:
          return True
    return False

  def _call_binop_on_bindings(self, node, name, xval, yval):
    """Call a binary operator on two cfg.Binding objects."""
    rname = slots.REVERSE_NAME_MAPPING.get(name)
    if rname and isinstance(xval.data, abstract.AMBIGUOUS_OR_EMPTY):
      # If the reverse operator is possible and x is ambiguous, then we have no
      # way of determining whether __{op} or __r{op}__ is called.  Technically,
      # the result is also unknown if y is ambiguous, but it is almost always
      # reasonable to assume that, e.g., "hello " + y is a string, even though
      # y could define __radd__.
      return node, self.program.NewVariable(
          [self.convert.unsolvable], [xval, yval], node)
    options = [(xval, yval, name)]
    if rname:
      options.append((yval, xval, rname))
      if self._overrides(node, yval.data.cls, xval.data.cls, rname):
        # If y is a subclass of x and defines its own reverse operator, then we
        # need to try y.__r{op}__ before x.__{op}__.
        options.reverse()
    error = None
    for left_val, right_val, attr_name in options:
      if isinstance(left_val.data, mixin.Class) and attr_name == "__getitem__":
        # We're parameterizing a type annotation. Set valself to None to
        # differentiate this action from a real __getitem__ call on the class.
        valself = None
      else:
        valself = left_val
      node, attr_var = self.attribute_handler.get_attribute(
          node, left_val.data, attr_name, valself)
      if attr_var and attr_var.bindings:
        args = function.Args(posargs=(right_val.AssignToNewVariable(),))
        try:
          return self.call_function(
              node, attr_var, args, fallback_to_unsolvable=False)
        except (function.DictKeyMissing, function.FailedFunctionCall) as e:
          # It's possible that this call failed because the function returned
          # NotImplemented.  See, e.g.,
          # test_operators.ReverseTest.check_reverse(), in which 1 {op} Bar()
          # ends up using Bar.__r{op}__. Thus, we need to save the error and
          # try the other operator.
          if e > error:
            error = e
    if error:
      raise error  # pylint: disable=raising-bad-type
    else:
      return node, None

  def call_binary_operator(self, state, name, x, y, report_errors=False):
    """Map a binary operator to "magic methods" (__add__ etc.)."""
    results = []
    log.debug("Calling binary operator %s", name)
    nodes = []
    error = None
    for xval in x.bindings:
      for yval in y.bindings:
        try:
          node, ret = self._call_binop_on_bindings(state.node, name, xval, yval)
        except (function.DictKeyMissing, function.FailedFunctionCall) as e:
          if e > error:
            error = e
        else:
          if ret:
            nodes.append(node)
            results.append(ret)
    if nodes:
      state = state.change_cfg_node(self.join_cfg_nodes(nodes))
    result = self.join_variables(state.node, results)
    log.debug("Result: %r %r", result, result.data)
    if not result.bindings and report_errors:
      if error is None:
        if self.options.report_errors:
          self.errorlog.unsupported_operands(self.frames, name, x, y)
        result = self.new_unsolvable(state.node)
      elif isinstance(error, function.DictKeyMissing):
        if self.options.report_errors:
          self.errorlog.key_error(self.frames, error.name)
        state, result = error.get_return(state)
      else:
        if self.options.report_errors:
          self.errorlog.invalid_function_call(self.frames, error)
        state, result = error.get_return(state)
    return state, result

  def call_inplace_operator(self, state, iname, x, y):
    """Try to call a method like __iadd__, possibly fall back to __add__."""
    state, attr = self.load_attr_noerror(state, x, iname)
    if attr is None:
      log.info("No inplace operator %s on %r", iname, x)
      name = iname.replace("i", "", 1)  # __iadd__ -> __add__ etc.
      state = state.forward_cfg_node()
      state, ret = self.call_binary_operator(
          state, name, x, y, report_errors=True)
    else:
      # TODO(kramm): If x is a Variable with distinct types, both __add__
      # and __iadd__ might happen.
      try:
        state, ret = self.call_function_with_state(state, attr, (y,),
                                                   fallback_to_unsolvable=False)
      except function.FailedFunctionCall as e:
        self.errorlog.invalid_function_call(self.frames, e)
        state, ret = e.get_return(state)
    return state, ret

  def binary_operator(self, state, name, report_errors=True):
    state, (x, y) = state.popn(2)
    with self._suppress_opcode_tracing():  # don't trace the magic method call
      state, ret = self.call_binary_operator(
          state, name, x, y, report_errors=report_errors)
    self.trace_opcode(None, name, ret)
    return state.push(ret)

  def inplace_operator(self, state, name):
    state, (x, y) = state.popn(2)
    state, ret = self.call_inplace_operator(state, name, x, y)
    return state.push(ret)

  def trace_module_member(self, *args):
    """Fired whenever a member of a module is converted."""
    return NotImplemented

  def trace_unknown(self, *args):
    """Fired whenever we create a variable containing 'Unknown'."""
    return NotImplemented

  def trace_call(self, *args):
    """Fired whenever we call a builtin using unknown parameters."""
    return NotImplemented

  def trace_functiondef(self, *args):
    return NotImplemented

  def trace_classdef(self, *args):
    return NotImplemented

  def trace_namedtuple(self, *args):
    return NotImplemented

  def call_init(self, node, unused_instance):
    # This dummy implementation is overwritten in analyze.py.
    return node

  def init_class(self, node, cls, extra_key=None):
    # This dummy implementation is overwritten in analyze.py.
    del cls, extra_key
    return node, None

  def call_function_with_state(self, state, funcu, posargs, namedargs=None,
                               starargs=None, starstarargs=None,
                               fallback_to_unsolvable=True):
    """Call a function with the given state."""
    assert starargs is None or isinstance(starargs, cfg.Variable)
    assert starstarargs is None or isinstance(starstarargs, cfg.Variable)
    node, ret = self.call_function(state.node, funcu, function.Args(
        posargs=posargs, namedargs=namedargs, starargs=starargs,
        starstarargs=starstarargs), fallback_to_unsolvable, allow_noreturn=True)
    if ret.data == [self.convert.no_return]:
      state = state.set_why("NoReturn")
    return state.change_cfg_node(node), ret

  def _call_with_fake_args(self, node, funcu):
    """Attempt to call the given function with made-up arguments."""
    return node, self.new_unsolvable(node)

  def call_function(self, node, funcu, args, fallback_to_unsolvable=True,
                    allow_noreturn=False):
    """Call a function.

    Args:
      node: The current CFG node.
      funcu: A variable of the possible functions to call.
      args: The arguments to pass. See function.Args.
      fallback_to_unsolvable: If the function call fails, create an unknown.
      allow_noreturn: Whether typing.NoReturn is allowed in the return type.
    Returns:
      A tuple (CFGNode, Variable). The Variable is the return value.
    Raises:
      DictKeyMissing: if we retrieved a nonexistent key from a dict and
        fallback_to_unsolvable is False.
      FailedFunctionCall: if the call fails and fallback_to_unsolvable is False.
    """
    assert funcu.bindings
    result = self.program.NewVariable()
    nodes = []
    error = None
    has_noreturn = False
    for funcv in funcu.bindings:
      func = funcv.data
      assert isinstance(func, abstract.AtomicAbstractValue), type(func)
      one_result = None
      try:
        new_node, one_result = func.call(node, funcv, args)
      except (function.DictKeyMissing, function.FailedFunctionCall) as e:
        if e > error:
          error = e
      else:
        if self.convert.no_return in one_result.data:
          if allow_noreturn:
            # Make sure NoReturn was the only thing returned.
            assert len(one_result.data) == 1
            has_noreturn = True
          else:
            for b in one_result.bindings:
              if b.data != self.convert.no_return:
                result.PasteBinding(b)
        else:
          result.PasteVariable(one_result, new_node, {funcv})
        nodes.append(new_node)
    if nodes:
      node = self.join_cfg_nodes(nodes)
      if not result.bindings:
        v = self.convert.no_return if has_noreturn else self.convert.unsolvable
        result.AddBinding(v, [], node)
    elif (isinstance(error, function.FailedFunctionCall) and
          all(abstract_utils.func_name_is_class_init(func.name)
              for func in funcu.data)):
      # If the function failed with a FailedFunctionCall exception, try calling
      # it again with fake arguments. This allows for calls to __init__ to
      # always succeed, ensuring pytype has a full view of the class and its
      # attributes. If the call still fails, _call_with_fake_args will return
      # abstract.Unsolvable.
      node, result = self._call_with_fake_args(node, funcu)
    elif self.options.precise_return and len(funcu.bindings) == 1:
      funcv, = funcu.bindings
      func = funcv.data
      if isinstance(func, abstract.BoundFunction):
        func = func.underlying
      if isinstance(func, abstract.PyTDFunction):
        node, result = func.signatures[0].instantiate_return(node, {}, [funcv])
      elif isinstance(func, abstract.InterpreterFunction):
        sig = func.signature_functions()[0].signature
        ret = sig.annotations.get("return", self.convert.unsolvable)
        node, result = self.init_class(node, ret)
      else:
        result = self.new_unsolvable(node)
    else:
      result = self.new_unsolvable(node)
    self.trace_opcode(
        None, funcu.data[0].name.rpartition(".")[-1], (funcu, result))
    if nodes:
      return node, result
    elif fallback_to_unsolvable:
      if isinstance(error, function.DictKeyMissing):
        self.errorlog.key_error(self.frames, error.name)
      else:
        self.errorlog.invalid_function_call(self.frames, error)
      return node, result
    else:
      # We were called by something that does its own error handling.
      error.set_return(node, result)
      raise error  # pylint: disable=raising-bad-type

  def _process_decorator(self, func, posargs):
    """Specific processing for decorated functions."""
    if len(posargs) != 1 or not posargs[0].bindings:
      return
    # Assume the decorator and decorated function have one binding each.
    # (This is valid due to how decorated functions/classes are created.)
    decorator = func.data[0]
    fn = posargs[0].data[0]
    # TODO(b/153760963) We also need to check if the CALL_FUNCTION opcode has
    # the same line number as the function declaration (it should suffice to
    # check that the opcode lineno is in the set of decorators; we just need a
    # way to access the line number here). Otherwise any function call taking a
    # single function as an arg could trigger this code.
    if fn.is_decorated:
      log.info("Decorating %s with %s", fn.full_name, decorator.full_name)

  def call_function_from_stack(self, state, num, starargs, starstarargs):
    """Pop arguments for a function and call it."""

    namedargs = abstract.Dict(self)

    # The way arguments are put on the stack changed in python 3.6:
    #   https://github.com/python/cpython/blob/3.5/Python/ceval.c#L4712
    #   https://github.com/python/cpython/blob/3.6/Python/ceval.c#L4806
    if self.python_version < (3, 6):
      num_kw, num_pos = divmod(num, 256)

      # TODO(kramm): Can we omit creating this Dict if num_kw=0?
      for _ in range(num_kw):
        state, (key, val) = state.popn(2)
        namedargs.setitem_slot(state.node, key, val)
      state, posargs = state.popn(num_pos)
    else:
      state, args = state.popn(num)
      if starstarargs:
        kwnames = abstract_utils.get_atomic_python_constant(starstarargs, tuple)
        n = len(args) - len(kwnames)
        for key, arg in zip(kwnames, args[n:]):
          namedargs.setitem_slot(state.node, key, arg)
        posargs = args[0:n]
        starstarargs = None
      else:
        posargs = args
    state, func = state.pop()
    self._process_decorator(func, posargs)
    state, ret = self.call_function_with_state(
        state, func, posargs, namedargs, starargs, starstarargs)
    return state.push(ret)

  def get_globals_dict(self):
    """Get a real python dict of the globals."""
    return self.frame.f_globals

  def load_from(self, state, store, name, discard_concrete_values=False):
    """Load an item out of locals, globals, or builtins."""
    assert isinstance(store, abstract.SimpleAbstractValue)
    assert store.is_lazy
    store.load_lazy_attribute(name)
    bindings = store.members[name].Bindings(state.node)
    if not bindings:
      raise KeyError(name)
    ret = self.program.NewVariable()
    self._filter_none_and_paste_bindings(
        state.node, bindings, ret,
        discard_concrete_values=discard_concrete_values)
    return state, ret

  def load_local(self, state, name):
    """Called when a local is loaded onto the stack.

    Uses the name to retrieve the value from the current locals().

    Args:
      state: The current VM state.
      name: Name of the local

    Returns:
      A tuple of the state and the value (cfg.Variable)
    """
    try:
      return self.load_from(state, self.frame.f_locals, name)
    except KeyError:
      # A variable has been declared but not defined, e.g.,
      #   constant: str
      return state, self._load_annotation(state.node, name)

  def load_global(self, state, name):
    return self.load_from(
        state, self.frame.f_globals, name, discard_concrete_values=True)

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
      return state, self.convert.empty.to_variable(self.root_cfg_node)
    special = self.load_special_builtin(name)
    if special:
      return state, special.to_variable(state.node)
    else:
      return self.load_from(state, self.frame.f_builtins, name)

  def load_constant(self, state, op, raw_const):
    const = self.convert.constant_to_var(raw_const, node=state.node)
    self.trace_opcode(op, raw_const, const)
    return state.push(const)

  def _load_annotation(self, node, name):
    annots = abstract_utils.get_annotations_dict(self.frame.f_locals.members)
    if annots:
      typ = annots.get_type(node, name)
      if typ:
        _, ret = self.init_class(node, typ)
        return ret
    raise KeyError(name)

  def _record_local(self, node, op, name, typ, orig_val=None):
    """Record a type annotation on a local variable.

    This method records three types of local operations:
      - An annotation, e.g., `x: int`. In this case, `typ` is PyTDClass(int) and
        `orig_val` is None.
      - An assignment, e.g., `x = 0`. In this case, `typ` is None and `orig_val`
        is Instance(int).
      - An annotated assignment, e.g., `x: int = None`. In this case, `typ` is
        PyTDClass(int) and `orig_val` is Instance(None).

    Args:
      node: The current node.
      op: The current opcode.
      name: The variable name.
      typ: The annotation.
      orig_val: The original value, if any.
    """
    if orig_val:
      self.current_local_ops.append(LocalOp(name, LocalOp.ASSIGN))
    if typ:
      self.current_local_ops.append(LocalOp(name, LocalOp.ANNOTATE))
    if name in self.current_annotated_locals:
      self.current_annotated_locals[name].update(node, op, typ, orig_val)
    else:
      self.current_annotated_locals[name] = Local(node, op, typ, orig_val, self)

  def _store_value(self, state, name, value, local):
    if local:
      target = self.frame.f_locals
    else:
      target = self.frame.f_globals
    node = self.attribute_handler.set_attribute(state.node, target, name, value)
    if target is self.frame.f_globals and self.late_annotations:
      for annot in self.late_annotations[name]:
        annot.resolve(node, self.frame.f_globals, self.frame.f_locals)
    return state.change_cfg_node(node)

  def store_local(self, state, name, value):
    """Called when a local is written."""
    return self._store_value(state, name, value, local=True)

  def store_global(self, state, name, value):
    """Same as store_local except for globals."""
    return self._store_value(state, name, value, local=False)

  def _check_aliased_type_params(self, value):
    for v in value.data:
      if isinstance(v, abstract.Union) and v.formal:
        self.errorlog.not_supported_yet(
            self.frames, "aliases of Unions with type parameters")

  def _apply_annotation(self, state, op, name, orig_val, local):
    """Applies the type annotation, if any, associated with this object."""
    typ, value = self.annotations_util.apply_annotation(
        state, op, name, orig_val)
    if local:
      self._record_local(state.node, op, name, typ, orig_val)
      if typ is None and name in self.current_annotated_locals:
        typ = self.current_annotated_locals[name].get_type(state.node, name)
        if typ == self.convert.unsolvable:
          # An Any annotation can be used to essentially turn off inference in
          # cases where it is causing false positives or other issues.
          value = self.new_unsolvable(state.node)
    if self.options.check_variable_types:
      self.check_annotation_type_mismatch(
          state.node, name, typ, orig_val, self.frames, allow_none=True)
    return value

  def check_annotation_type_mismatch(
      self, node, name, typ, value, stack, allow_none):
    """Checks for a mismatch between a variable's annotation and value.

    Args:
      node: node
      name: variable name
      typ: variable annotation
      value: variable value
      stack: a frame stack for error reporting
      allow_none: whether a value of None is allowed for any type
    """
    if not typ or not value:
      return
    if (value.data == [self.convert.ellipsis] or
        allow_none and value.data == [self.convert.none]):
      return
    contained_type = abstract_utils.match_type_container(
        typ, ("typing.ClassVar", "dataclasses.InitVar"))
    if contained_type:
      typ = contained_type
    bad = self.matcher.bad_matches(value, typ, node)
    for view in bad:
      binding = view[value]
      self.errorlog.annotation_type_mismatch(stack, typ, binding, name)

  def _pop_and_store(self, state, op, name, local):
    """Pop a value off the stack and store it in a variable."""
    state, orig_val = state.pop()
    value = self._apply_annotation(state, op, name, orig_val, local)
    self._check_aliased_type_params(value)
    state = state.forward_cfg_node()
    state = self._store_value(state, name, value, local)
    self.trace_opcode(op, name, value)
    return state.forward_cfg_node()

  def _del_name(self, op, state, name, local):
    """Called when a local or global is deleted."""
    value = abstract.Deleted(self).to_variable(state.node)
    state = state.forward_cfg_node()
    state = self._store_value(state, name, value, local)
    self.trace_opcode(op, name, value)
    return state.forward_cfg_node()

  def _retrieve_attr(self, node, obj, attr):
    """Load an attribute from an object."""
    assert isinstance(obj, cfg.Variable), obj
    # Resolve the value independently for each value of obj
    result = self.program.NewVariable()
    log.debug("getting attr %s from %r", attr, obj)
    nodes = []
    values_without_attribute = []
    for val in obj.bindings:
      node2, attr_var = self.attribute_handler.get_attribute(
          node, val.data, attr, val)
      if attr_var is None or not attr_var.bindings:
        log.debug("No %s on %s", attr, val.data.__class__)
        values_without_attribute.append(val)
        continue
      log.debug("got choice for attr %s from %r of %r (0x%x): %r", attr, obj,
                val.data, id(val.data), attr_var)
      self._filter_none_and_paste_bindings(node2, attr_var.bindings, result)
      nodes.append(node2)
    if nodes:
      return self.join_cfg_nodes(nodes), result, values_without_attribute
    else:
      return node, None, values_without_attribute

  def _data_is_none(self, x):
    assert isinstance(x, abstract.AtomicAbstractValue)
    return x.cls == self.convert.none_type

  def _var_is_none(self, v):
    assert isinstance(v, cfg.Variable)
    return v.bindings and all(self._data_is_none(b.data) for b in v.bindings)

  def _delete_item(self, state, obj, arg):
    state, f = self.load_attr(state, obj, "__delitem__")
    state, _ = self.call_function_with_state(state, f, (arg,))
    return state

  def load_attr(self, state, obj, attr):
    """Try loading an attribute, and report errors."""
    node, result, errors = self._retrieve_attr(state.node, obj, attr)
    self._attribute_error_detection(state, attr, errors)
    if result is None:
      result = self.new_unsolvable(node)
    return state.change_cfg_node(node), result

  def _attribute_error_detection(self, state, attr, errors):
    if not self.options.report_errors:
      return
    for error in errors:
      combination = [error]
      if self.frame.func:
        combination.append(self.frame.func)
      if state.node.HasCombination(combination):
        self.errorlog.attribute_error(self.frames, error, attr)

  def _filter_none_and_paste_bindings(self, node, bindings, var,
                                      discard_concrete_values=False):
    """Paste the bindings into var, filtering out false positives on None."""
    for b in bindings:
      if self._has_strict_none_origins(b):
        if (discard_concrete_values and
            isinstance(b.data, mixin.PythonConstant) and
            not isinstance(b.data.pyval, str)):
          # We need to keep constant strings as they may be forward references.
          var.AddBinding(
              self.convert.get_maybe_abstract_instance(b.data), [b], node)
        else:
          var.PasteBinding(b, node)
      else:
        var.AddBinding(self.convert.unsolvable, [b], node)

  def _has_strict_none_origins(self, binding):
    """Whether the binding has any possible origins, with None filtering.

    Determines whether the binding has any possibly visible origins at the
    current node once we've filtered out false positives on None. The caller
    still must call HasCombination() to find out whether these origins are
    actually reachable.

    Args:
      binding: A cfg.Binding.

    Returns:
      True if there are possibly visible origins, else False.
    """
    if not self._analyzing:
      return True
    has_any_none_origin = False
    walker = cfg_utils.walk_binding(
        binding, keep_binding=lambda b: self._data_is_none(b.data))
    origin = None
    while True:
      try:
        origin = walker.send(origin)
      except StopIteration:
        break
      for source_set in origin.source_sets:
        if not source_set:
          if self.program.is_reachable(src=self.frame.node, dst=origin.where):
            # Checking for reachability works because the current part of the
            # graph hasn't been connected back to the analyze node yet. Since
            # the walker doesn't preserve information about the relationship
            # among origins, we pretend we have a disjunction over source sets.
            return True
          has_any_none_origin = True
    return not has_any_none_origin

  def load_attr_noerror(self, state, obj, attr):
    """Try loading an attribute, ignore errors."""
    node, result, _ = self._retrieve_attr(state.node, obj, attr)
    return state.change_cfg_node(node), result

  def store_attr(self, state, obj, attr, value):
    """Set an attribute on an object."""
    assert isinstance(obj, cfg.Variable)
    assert isinstance(attr, str)
    if not obj.bindings:
      log.info("Ignoring setattr on %r", obj)
      return state
    nodes = []
    for val in obj.bindings:
      # TODO(kramm): Check whether val.data is a descriptor (i.e. has "__set__")
      nodes.append(self.attribute_handler.set_attribute(
          state.node, val.data, attr, value))
    return state.change_cfg_node(self.join_cfg_nodes(nodes))

  def del_attr(self, state, obj, attr):
    """Delete an attribute."""
    # TODO(kramm): Store abstract.Empty
    log.warning("Attribute removal does not actually do "
                "anything in the abstract interpreter")
    return state

  def del_subscr(self, state, obj, subscr):
    return self._delete_item(state, obj, subscr)

  def pop_varargs(self, state):
    """Retrieve a varargs tuple from the stack. Used by call_function."""
    return state.pop()

  def pop_kwargs(self, state):
    """Retrieve a kwargs dictionary from the stack. Used by call_function."""
    return state.pop()

  def import_module(self, name, full_name, level):
    """Import a module and return the module object or None."""
    if self.options.strict_import:
      # Do not import new modules if we aren't in an IMPORT statement.
      # The exception is if we have an implicit "package" module (e.g.
      # `import a.b.c` adds `a.b` to the list of instantiable modules.)
      if not (self._importing or self.loader.has_module_prefix(full_name)):
        return None
    try:
      module = self._import_module(name, level)
      # Since we have explicitly imported full_name, add it to the prefix list.
      self.loader.add_module_prefixes(full_name)
    except (parser.ParseError, load_pytd.BadDependencyError,
            visitors.ContainerError, visitors.SymbolLookupError) as e:
      self.errorlog.pyi_error(self.frames, full_name, e)
      module = self.convert.unsolvable
    return module

  # TODO(kramm): memoize
  def _import_module(self, name, level):
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
        if name in overlay_dict.overlays:
          if name in self.loaded_overlays:
            overlay = self.loaded_overlays[name]
          else:
            overlay = overlay_dict.overlays[name](self)
            # The overlay should be available only if the underlying pyi is.
            if overlay.ast:
              self.loaded_overlays[name] = overlay
            else:
              overlay = self.loaded_overlays[name] = None
          if overlay:
            return overlay
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
      return self.convert.constant_to_value(
          ast, subst=datatypes.AliasingDict(), node=self.root_cfg_node)
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
    result = self.program.NewVariable()
    for x in left.bindings:
      for y in right.bindings:
        pyval = maybe_predicate(x.data, y.data)
        result.AddBinding(self.convert.bool_values[pyval],
                          source_set=(x, y), where=node)

    return result

  def _get_aiter(self, state, obj):
    """Get an async iterator from an object."""
    state, func = self.load_attr(state, obj, "__aiter__")
    if func:
      return self.call_function_with_state(state, func, ())
    else:
      return state, self.new_unsolvable(state.node)

  def _get_iter(self, state, seq, report_errors=True):
    """Get an iterator from a sequence."""
    # TODO(rechen): We should iterate through seq's bindings, in order to fetch
    # the attribute on the sequence's class, but two problems prevent us from
    # doing so:
    # - Iterating through individual bindings causes a performance regression.
    # - Because __getitem__ is used for annotations, pytype sometime thinks the
    #   class attribute is AnnotationClass.getitem_slot.
    state, func = self.load_attr_noerror(state, seq, "__iter__")
    if func:
      # Call __iter__()
      state, itr = self.call_function_with_state(state, func, ())
    else:
      node, func, missing = self._retrieve_attr(state.node, seq, "__getitem__")
      state = state.change_cfg_node(node)
      if func:
        # TODO(dbaum): Consider delaying the call to __getitem__ until
        # the iterator's next() is called.  That would more closely match
        # actual execution at the cost of making the code and Iterator class
        # a little more complicated.

        # Call __getitem__(int).
        state, item = self.call_function_with_state(
            state, func, (self.convert.build_int(state.node),))
        # Create a new iterator from the returned value.
        itr = abstract.Iterator(self, item).to_variable(state.node)
      else:
        itr = self.program.NewVariable()
      if report_errors and self.options.report_errors:
        for m in missing:
          if state.node.HasCombination([m]):
            self.errorlog.attribute_error(self.frames, m, "__iter__")
    return state, itr

  def new_unsolvable(self, node):
    """Create a new unsolvable variable at node."""
    return self.convert.unsolvable.to_variable(node)

  def byte_UNARY_NOT(self, state, op):
    """Implement the UNARY_NOT bytecode."""
    state, var = state.pop()
    true_bindings = [
        b for b in var.bindings if compare.compatible_with(b.data, True)]
    false_bindings = [
        b for b in var.bindings if compare.compatible_with(b.data, False)]
    if len(true_bindings) == len(false_bindings) == len(var.bindings):
      # No useful information from bindings, use a generic bool value.
      # This is merely an optimization rather than building separate True/False
      # values each with the same bindings as var.
      result = self.convert.build_bool(state.node)
    else:
      # Build a result with True/False values, each bound to appropriate
      # bindings.  Note that bindings that are True get attached to a result
      # that is False and vice versa because this is a NOT operation.
      result = self.program.NewVariable()
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

  def byte_BINARY_MATRIX_MULTIPLY(self, state, op):
    return self.binary_operator(state, "__matmul__")

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
    return self.binary_operator(state, "__getitem__")

  def byte_INPLACE_MATRIX_MULTIPLY(self, state, op):
    return self.inplace_operator(state, "__imatmul__")

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
    raw_const = self.frame.f_code.co_consts[op.arg]
    return self.load_constant(state, op, raw_const)

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

  def _is_private(self, name):
    return name.startswith("_") and not name.startswith("__")

  def _name_error_or_late_annotation(self, name):
    if self._late_annotations_stack and self.late_annotations is not None:
      annot = abstract.LateAnnotation(name, self._late_annotations_stack, self)
      log.info("Created %r", annot)
      self.late_annotations[name].append(annot)
      return annot
    else:
      self.errorlog.name_error(self.frames, name)
      return self.convert.unsolvable

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
          if self._is_private(name):
            # Private names must be explicitly imported.
            self.trace_opcode(op, name, None)
            raise KeyError()
          state, val = self.load_builtin(state, name)
        except KeyError:
          if self._is_private(name) or not self.has_unknown_wildcard_imports:
            one_val = self._name_error_or_late_annotation(name)
          else:
            one_val = self.convert.unsolvable
          self.trace_opcode(op, name, None)
          return state.push(one_val.to_variable(state.node))
    self.check_for_deleted(state, name, val)
    self.trace_opcode(op, name, val)
    return state.push(val)

  def byte_STORE_NAME(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    return self._pop_and_store(state, op, name, local=True)

  def byte_DELETE_NAME(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    return self._del_name(op, state, name, local=True)

  def byte_LOAD_FAST(self, state, op):
    """Load a local. Unlike LOAD_NAME, it doesn't fall back to globals."""
    name = self.frame.f_code.co_varnames[op.arg]
    try:
      state, val = self.load_local(state, name)
    except KeyError:
      val = self._name_error_or_late_annotation(name).to_variable(state.node)
    self.check_for_deleted(state, name, val)
    self.trace_opcode(op, name, val)
    return state.push(val)

  def byte_STORE_FAST(self, state, op):
    name = self.frame.f_code.co_varnames[op.arg]
    return self._pop_and_store(state, op, name, local=True)

  def byte_DELETE_FAST(self, state, op):
    name = self.frame.f_code.co_varnames[op.arg]
    return self._del_name(op, state, name, local=True)

  def byte_LOAD_GLOBAL(self, state, op):
    """Load a global variable, or fall back to trying to load a builtin."""
    name = self.frame.f_code.co_names[op.arg]
    if name == "None":
      # Load None itself as a constant to avoid the None filtering done on
      # variables. This workaround is safe because assigning to None is a
      # syntax error.
      return self.load_constant(state, op, None)
    try:
      state, val = self.load_global(state, name)
    except KeyError:
      try:
        state, val = self.load_builtin(state, name)
      except KeyError:
        self.trace_opcode(op, name, None)
        return state.push(
            self._name_error_or_late_annotation(name).to_variable(state.node))
    self.check_for_deleted(state, name, val)
    self.trace_opcode(op, name, val)
    return state.push(val)

  def byte_STORE_GLOBAL(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    return self._pop_and_store(state, op, name, local=False)

  def byte_DELETE_GLOBAL(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    return self._del_name(op, state, name, local=False)

  def get_closure_var_name(self, arg):
    n_cellvars = len(self.frame.f_code.co_cellvars)
    if arg < n_cellvars:
      name = self.frame.f_code.co_cellvars[arg]
    else:
      name = self.frame.f_code.co_freevars[arg - n_cellvars]
    return name

  def check_for_deleted(self, state, name, var):
    if any(isinstance(x, abstract.Deleted) for x in var.Data(state.node)):
      # Referencing a deleted variable
      # TODO(mdemello): A "use-after-delete" error would be more helpful.
      self.errorlog.name_error(self.frames, name)

  def load_closure_cell(self, state, op):
    """Retrieve the value out of a closure cell.

    Used to generate the 'closure' tuple for MAKE_CLOSURE.

    Each entry in that tuple is typically retrieved using LOAD_CLOSURE.

    Args:
      state: The current VM state.
      op: The opcode. op.arg is the index of a "cell variable": This corresponds
        to an entry in co_cellvars or co_freevars and is a variable that's bound
        into a closure.
    Returns:
      A new state.
    """
    cell = self.frame.cells[op.arg]
    visible_bindings = cell.Filter(state.node, strict=False)
    if len(visible_bindings) != len(cell.bindings):
      # We need to filter here because the closure will be analyzed outside of
      # its creating context, when information about what values are visible
      # has been lost.
      new_cell = self.program.NewVariable()
      if visible_bindings:
        for b in visible_bindings:
          new_cell.AddBinding(b.data, {b}, state.node)
      else:
        # TODO(rechen): Is this a bug?
        # See test_closures.ClosuresTest.testNoVisibleBindings.
        new_cell.AddBinding(self.convert.unsolvable)
      # Update the cell because the DELETE_DEREF implementation works on
      # variable identity.
      self.frame.cells[op.arg] = cell = new_cell
    name = self.get_closure_var_name(op.arg)
    self.check_for_deleted(state, name, cell)
    self.trace_opcode(op, name, cell)
    return state.push(cell)

  def byte_LOAD_CLOSURE(self, state, op):
    """Retrieves a value out of a cell."""
    return self.load_closure_cell(state, op)

  def byte_LOAD_DEREF(self, state, op):
    """Retrieves a value out of a cell."""
    return self.load_closure_cell(state, op)

  def byte_STORE_DEREF(self, state, op):
    """Stores a value in a closure cell."""
    state, value = state.pop()
    assert isinstance(value, cfg.Variable)
    name = self.get_closure_var_name(op.arg)
    value = self._apply_annotation(state, op, name, value, True)
    state = state.forward_cfg_node()
    self.frame.cells[op.arg].PasteVariable(value, state.node)
    state = state.forward_cfg_node()
    self.trace_opcode(op, name, value)
    return state

  def byte_DELETE_DEREF(self, state, op):
    value = abstract.Deleted(self).to_variable(state.node)
    name = self.get_closure_var_name(op.arg)
    state = state.forward_cfg_node()
    self.frame.cells[op.arg].PasteVariable(value, state.node)
    state = state.forward_cfg_node()
    self.trace_opcode(op, name, value)
    return state

  def byte_LOAD_CLASSDEREF(self, state, op):
    """Retrieves a value out of either locals or a closure cell."""
    name = self.get_closure_var_name(op.arg)
    try:
      state, val = self.load_local(state, name)
      self.trace_opcode(op, name, val)
      return state.push(val)
    except KeyError:
      return self.load_closure_cell(state, op)

  def byte_LOAD_LOCALS(self, state, op):
    log.debug("Returning locals: %r", self.frame.f_locals)
    locals_dict = self.frame.f_locals.to_variable(self.root_cfg_node)
    return state.push(locals_dict)

  def _cmp_rel(self, state, op_name, x, y):
    """Implementation of relational operators CMP_(LT|LE|EQ|NE|GE|GT).

    Args:
      state: Initial FrameState.
      op_name: An operator name, e.g., "EQ".
      x: A variable of the lhs value.
      y: A variable of the rhs value.

    Returns:
      A tuple of the new FrameState and the return variable.
    """
    ret = self.program.NewVariable()
    # A variable of the values without a special cmp_rel implementation. Needed
    # because overloaded __eq__ implementations do not necessarily return a
    # bool; see, e.g., test_overloaded in test_cmp.
    leftover = self.program.NewVariable()
    for b1 in x.bindings:
      for b2 in y.bindings:
        val = compare.cmp_rel(self, getattr(slots, op_name), b1.data, b2.data)
        if val is None:
          leftover.AddBinding(b1.data, {b1}, state.node)
        else:
          ret.AddBinding(self.convert.bool_values[val], {b1, b2}, state.node)
    if leftover.bindings:
      op = "__%s__" % op_name.lower()
      state, leftover_ret = self.call_binary_operator(state, op, leftover, y)
      ret.PasteVariable(leftover_ret, state.node)
    return state, ret

  def _coerce_to_bool(self, node, var, true_val=True):
    """Coerce the values in a variable to bools."""
    bool_var = self.program.NewVariable()
    for b in var.bindings:
      v = b.data
      if isinstance(v, mixin.PythonConstant) and isinstance(v.pyval, bool):
        const = v.pyval is true_val
      elif not compare.compatible_with(v, True):
        const = not true_val
      elif not compare.compatible_with(v, False):
        const = true_val
      else:
        const = None
      bool_var.AddBinding(self.convert.bool_values[const], {b}, node)
    return bool_var

  def _cmp_in(self, state, x, y, true_val=True):
    """Implementation of CMP_IN/CMP_NOT_IN."""
    state, ret = self.call_binary_operator(state, "__contains__", y, x)
    if ret.bindings:
      ret = self._coerce_to_bool(state.node, ret, true_val=true_val)
    else:
      # For an object without a __contains__ method, cmp_in falls back to
      # checking x against the items produced by y's iterator.
      state, itr = self._get_iter(state, y, report_errors=False)
      if len(itr.bindings) < len(y.bindings):
        # y does not have any of __contains__, __iter__, and __getitem__.
        # (The last two are checked by _get_iter.)
        self.errorlog.unsupported_operands(self.frames, "__contains__", y, x)
      ret = self.convert.build_bool(state.node)
    return state, ret

  def _cmp_is_always_supported(self, op_arg):
    """Checks if the comparison should always succeed."""
    return op_arg in (slots.CMP_ALWAYS_SUPPORTED_PY2 if self.PY2 else
                      slots.CMP_ALWAYS_SUPPORTED_PY3)

  def _instantiate_exception(self, node, exc_type):
    """Instantiate an exception type.

    Args:
      node: The current node.
      exc_type: A cfg.Variable of the exception type.

    Returns:
      A tuple of a cfg.Variable of the instantiated type and a list of
      the flattened exception types in the data of exc_type. None takes the
      place of invalid types.
    """
    value = self.program.NewVariable()
    types = []
    for e in exc_type.data:
      if isinstance(e, abstract.Tuple):
        for sub_exc_type in e.pyval:
          sub_value, sub_types = self._instantiate_exception(node, sub_exc_type)
          value.PasteVariable(sub_value)
          types.extend(sub_types)
      elif (isinstance(e, abstract.Instance) and
            e.cls.full_name == "__builtin__.tuple"):
        sub_exc_type = e.get_instance_type_parameter(abstract_utils.T)
        sub_value, sub_types = self._instantiate_exception(node, sub_exc_type)
        value.PasteVariable(sub_value)
        types.extend(sub_types)
      elif isinstance(e, mixin.Class) and any(
          base.full_name == "__builtin__.BaseException" or
          isinstance(base, abstract.AMBIGUOUS_OR_EMPTY) for base in e.mro):
        node, instance = self.init_class(node, e)
        value.PasteVariable(instance)
        types.append(e)
      else:
        if not isinstance(e, abstract.AMBIGUOUS_OR_EMPTY):
          if isinstance(e, mixin.Class):
            mro_seqs = [e.mro] if isinstance(e, mixin.Class) else []
            msg = "%s does not inherit from BaseException" % e.name
          else:
            mro_seqs = []
            msg = "Not a class"
          self.errorlog.mro_error(self.frames, e.name, mro_seqs, details=msg)
        value.AddBinding(self.convert.unsolvable, [], node)
        types.append(None)
    return value, types

  def byte_COMPARE_OP(self, state, op):
    """Pops and compares the top two stack values and pushes a boolean."""
    state, (x, y) = state.popn(2)
    # Explicit, redundant, switch statement, to make it easier to address the
    # behavior of individual compare operations:
    if op.arg == slots.CMP_LT:
      state, ret = self._cmp_rel(state, "LT", x, y)
    elif op.arg == slots.CMP_LE:
      state, ret = self._cmp_rel(state, "LE", x, y)
    elif op.arg == slots.CMP_EQ:
      state, ret = self._cmp_rel(state, "EQ", x, y)
    elif op.arg == slots.CMP_NE:
      state, ret = self._cmp_rel(state, "NE", x, y)
    elif op.arg == slots.CMP_GT:
      state, ret = self._cmp_rel(state, "GT", x, y)
    elif op.arg == slots.CMP_GE:
      state, ret = self._cmp_rel(state, "GE", x, y)
    elif op.arg == slots.CMP_IS:
      ret = self.expand_bool_result(state.node, x, y,
                                    "is_cmp", frame_state.is_cmp)
    elif op.arg == slots.CMP_IS_NOT:
      ret = self.expand_bool_result(state.node, x, y,
                                    "is_not_cmp", frame_state.is_not_cmp)
    elif op.arg == slots.CMP_NOT_IN:
      state, ret = self._cmp_in(state, x, y, true_val=False)
    elif op.arg == slots.CMP_IN:
      state, ret = self._cmp_in(state, x, y)
    elif op.arg == slots.CMP_EXC_MATCH:
      # When the `try` block is set up, push_abstract_exception pushes on
      # unknowns for the value and exception type. CMP_EXC_MATCH occurs at the
      # beginning  of the `except` block, when we know the exception being
      # caught, so we can replace the unknowns with more useful variables.
      state, _ = state.popn(2)
      exc_type = y
      value, types = self._instantiate_exception(state.node, exc_type)
      if None in types:
        exc_type = self.new_unsolvable(state.node)
      state = state.push(value, exc_type)
      ret = self.convert.build_bool(state.node)
    else:
      raise VirtualMachineError("Invalid argument to COMPARE_OP: %d" % op.arg)
    if not ret.bindings and self._cmp_is_always_supported(op.arg):
      # Some comparison operations are always supported, depending on the target
      # Python version. In this case, always return a (boolean) value.
      # (https://docs.python.org/2/library/stdtypes.html#comparisons or
      # (https://docs.python.org/3/library/stdtypes.html#comparisons)
      ret.AddBinding(
          self.convert.primitive_class_instances[bool], [], state.node)
    return state.push(ret)

  def byte_LOAD_ATTR(self, state, op):
    """Pop an object, and retrieve a named attribute from it."""
    name = self.frame.f_code.co_names[op.arg]
    state, obj = state.pop()
    log.debug("LOAD_ATTR: %r %r", obj, name)
    with self._suppress_opcode_tracing():
      # LOAD_ATTR for @property methods generates an extra opcode trace for the
      # implicit function call, which we do not want.
      state, val = self.load_attr(state, obj, name)
    # We need to trace both the object and the attribute.
    self.trace_opcode(op, name, (obj, val))
    return state.push(val)

  def byte_STORE_ATTR(self, state, op):
    """Store an attribute."""
    name = self.frame.f_code.co_names[op.arg]
    state, (val, obj) = state.popn(2)
    # We do not want to record attributes as local variables.
    val = self._apply_annotation(state, op, name, val, False)
    state = state.forward_cfg_node()
    state = self.store_attr(state, obj, name, val)
    state = state.forward_cfg_node()
    # We need to trace both the object and the attribute.
    self.trace_opcode(op, name, (obj, val))
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
    """Implement obj[subscr] = val."""
    state, (val, obj, subscr) = state.popn(3)
    state = state.forward_cfg_node()
    # Check whether obj is the __annotations__ dict.
    if len(obj.data) == 1 and isinstance(obj.data[0], abstract.AnnotationsDict):
      try:
        name = abstract_utils.get_atomic_python_constant(
            subscr, six.string_types)
      except abstract_utils.ConversionError:
        pass
      else:
        typ = self.annotations_util.extract_annotation(
            state.node, val, name, self.simple_stack(), is_var=True)
        self._record_annotation(state.node, op, name, typ)
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
    state = state.push(self.convert.build_list(state.node, elts))
    return state.forward_cfg_node()

  def byte_BUILD_SET(self, state, op):
    count = op.arg
    state, elts = state.popn(count)
    return state.push(self.convert.build_set(state.node, elts))

  def byte_BUILD_MAP(self, state, op):
    """Build a dictionary."""
    the_map = self.convert.build_map(state.node)
    if self.python_version >= (3, 5):
      state, args = state.popn(2 * op.arg)
      for i in six.moves.range(op.arg):
        key, val = args[2*i], args[2*i+1]
        state = self.store_subscr(state, the_map, key, val)
    else:
      # For python < 3.5 we build the map in STORE_MAP
      pass
    return state.push(the_map)

  def byte_STORE_MAP(self, state, op):
    state, (the_map, val, key) = state.popn(3)
    state = self.store_subscr(state, the_map, key, val)
    return state.push(the_map)

  def _get_literal_sequence(self, data):
    """Helper function for _unpack_sequence."""
    try:
      return self.convert.value_to_constant(data, tuple)
    except abstract_utils.ConversionError:
      # Fall back to looking for a literal list and converting to a tuple
      try:
        return tuple(self.convert.value_to_constant(data, list))
      except abstract_utils.ConversionError:
        if data.cls:
          for base in data.cls.mro:
            if isinstance(base, abstract.TupleClass) and not base.formal:
              # We've found a TupleClass with concrete parameters, which means
              # we're a subclass of a heterogenous tuple (usually a
              # typing.NamedTuple instance).
              new_data = self.merge_values(
                  base.instantiate(self.root_cfg_node).data)
              return self._get_literal_sequence(new_data)
        return None

  def _restructure_tuple(self, state, tup, pre, post):
    """Collapse the middle part of a tuple into a List variable."""
    before = tup[0:pre]
    if post > 0:
      after = tup[-post:]
      rest = tup[pre:-post]
    else:
      after = ()
      rest = tup[pre:]
    rest = self.convert.build_list(state.node, rest)
    return before + (rest,) + after

  def _unpack_sequence(self, state, n_before, n_after=-1):
    """Pops a tuple (or other iterable) and pushes it onto the VM's stack.

    Supports destructuring assignment with potentially a single list variable
    that slurps up the remaining elements:
    1. a, b, c = ...  # UNPACK_SEQUENCE
    2. a, *b, c = ... # UNPACK_EX

    Args:
      state: The current VM state
      n_before: Number of elements before the list (n_elements for case 1)
      n_after: Number of elements after the list (-1 for case 1)
    Returns:
      The new state.
    """
    assert n_after >= -1
    state, seq = state.pop()
    options = []
    nontuple_seq = self.program.NewVariable()
    has_slurp = n_after > -1
    count = n_before + n_after + 1
    for b in seq.bindings:
      tup = self._get_literal_sequence(b.data)
      if tup:
        if has_slurp and len(tup) >= count:
          options.append(self._restructure_tuple(state, tup, n_before, n_after))
          continue
        elif len(tup) == count:
          options.append(tup)
          continue
        else:
          self.errorlog.bad_unpacking(self.frames, len(tup), count)
      nontuple_seq.AddBinding(b.data, {b}, state.node)
    if nontuple_seq.bindings:
      state, itr = self._get_iter(state, nontuple_seq)
      state, f = self.load_attr(state, itr, self.convert.next_attr)
      state, result = self.call_function_with_state(state, f, ())
      # For a non-literal iterable, next() should always return the same type T,
      # so we can iterate `count` times in both UNPACK_SEQUENCE and UNPACK_EX,
      # and assign the slurp variable type List[T].
      option = [result for _ in range(count)]
      if has_slurp:
        option[n_before] = self.convert.build_list_of_type(state.node, result)
      options.append(option)
    values = tuple(self.convert.build_content(value) for value in zip(*options))
    for value in reversed(values):
      if not value.bindings:
        # For something like
        #   for i, j in enumerate(()):
        #     print j
        # there are no bindings for j, so we have to add an empty binding
        # to avoid a name error on the print statement.
        value = self.convert.empty.to_variable(state.node)
      state = state.push(value)
    return state

  def byte_UNPACK_SEQUENCE(self, state, op):
    return self._unpack_sequence(state, op.arg)

  def byte_UNPACK_EX(self, state, op):
    n_before = op.arg & 0xff
    n_after = op.arg >> 8
    return self._unpack_sequence(state, n_before, n_after)

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
        state.node, value)
    if not jump_if:
      jump, normal = normal, jump
    # Jump.
    if jump is not frame_state.UNSATISFIABLE:
      if jump:
        assert jump.binding
        else_state = state.forward_cfg_node(jump.binding).forward_cfg_node()
      else:
        else_state = state.forward_cfg_node()
      self.store_jump(op.target, else_state)
    else:
      else_state = None
    # Don't jump.
    if or_pop:
      state = state.pop_and_discard()
    if normal is frame_state.UNSATISFIABLE:
      return state.set_why("unsatisfiable")
    elif not else_state and not normal:
      return state  # We didn't actually branch.
    else:
      return state.forward_cfg_node(normal.binding if normal else None)

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
    # We ignore the implicit jump in SETUP_LOOP; the interpreter never takes it.
    return self.push_block(state, "loop", op, op.target)

  def byte_GET_ITER(self, state, op):
    """Get the iterator for an object."""
    state, seq = state.pop()
    state, itr = self._get_iter(state, seq)
    # Push the iterator onto the stack and return.
    return state.push(itr)

  def store_jump(self, target, state):
    assert target
    self.frame.states[target] = state.merge_into(self.frame.states.get(target))

  def byte_FOR_ITER(self, state, op):
    self.store_jump(op.target, state.pop_and_discard())
    state, f = self.load_attr(state, state.top(), self.convert.next_attr)
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

  # New python3.8+ exception handling opcodes:
  # BEGIN_FINALLY, END_ASYNC_FOR, CALL_FINALLY, POP_FINALLY
  #
  # TODO(b/157603915): Figure out how to handle 3.8's new exception handling and
  # adjust these opcode handlers accordingly.
  def byte_BEGIN_FINALLY(self, state, op):
    return state

  def byte_CALL_FINALLY(self, state, op):
    return state

  def byte_END_ASYNC_FOR(self, state, op):
    return state

  def byte_POP_FINALLY(self, state, op):
    return state

  def byte_POP_BLOCK(self, state, op):
    state, _ = state.pop_block()
    return state

  def byte_RAISE_VARARGS_PY2(self, state, op):
    """Raise an exception (Python 2 version)."""
    # NOTE: the dis docs are completely wrong about the order of the
    # operands on the stack!
    argc = op.arg
    # TODO(rechen): Type-check the arguments to raise.
    state, _ = state.popn(argc)
    state = state.set_exception()
    if argc in (0, 3):
      return state.set_why("reraise")
    else:
      return state.set_why("exception")

  def byte_RAISE_VARARGS_PY3(self, state, op):
    """Raise an exception (Python 3 version)."""
    argc = op.arg
    state, _ = state.popn(argc)
    if argc == 0 and state.exception:
      return state.set_why("reraise")
    else:
      state = state.set_exception()
      return state.set_why("exception")

  def byte_RAISE_VARARGS(self, state, op):
    if self.PY2:
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
    if self.PY2:
      state = self.push_block(state, "with", op, op.target, level)
    else:
      assert self.PY3
      state = self.push_block(state, "finally", op, op.target, level)
    return state.push(ctxmgr_obj)

  def byte_WITH_CLEANUP(self, state, op):
    """Called at the end of a with block. Calls the exit handlers etc."""
    # In Python 2, cleaning up after a with block is done in a single
    # WITH_CLEANUP opcode. In Python 3, the same functionality is split into
    # a cleanup start and end. See WITH_CLEANUP(_{START,FINISH}) here for how
    # cleanup manipulates the stack:
    #   https://github.com/python/cpython/blob/master/Doc/library/dis.rst
    return self.byte_WITH_CLEANUP_FINISH(
        self.byte_WITH_CLEANUP_START(state, op), op)

  def byte_WITH_CLEANUP_START(self, state, op):
    """Called to start cleaning up a with block. Calls the exit handlers etc."""
    state, u = state.pop()  # pop 'None'
    state, exit_func = state.pop()
    state = state.push(u)
    state = state.push(self.convert.build_none(state.node))
    v = self.convert.build_none(state.node)
    w = self.convert.build_none(state.node)
    state, suppress_exception = self.call_function_with_state(
        state, exit_func, (u, v, w))
    return state.push(suppress_exception)

  def byte_WITH_CLEANUP_FINISH(self, state, op):
    """Called to finish cleaning up a with block."""
    # TODO(mdemello): Should we do something with the result here?
    state, unused_suppress_exception = state.pop()
    state, unused_none = state.pop()
    return state

  def _convert_kw_defaults(self, values):
    kw_defaults = {}
    for i in range(0, len(values), 2):
      key_var, value = values[i:i + 2]
      key = abstract_utils.get_atomic_python_constant(key_var)
      kw_defaults[key] = value
    return kw_defaults

  def _get_extra_function_args(self, state, arg):
    """Get function annotations and defaults from the stack. (Python3.5-)."""
    if self.PY2:
      num_pos_defaults = arg & 0xffff
      num_kw_defaults = 0
    else:
      assert self.PY3
      num_pos_defaults = arg & 0xff
      num_kw_defaults = (arg >> 8) & 0xff
    state, raw_annotations = state.popn((arg >> 16) & 0x7fff)
    state, kw_defaults = state.popn(2 * num_kw_defaults)
    state, pos_defaults = state.popn(num_pos_defaults)
    free_vars = None  # Python < 3.6 does not handle closure vars here.
    kw_defaults = self._convert_kw_defaults(kw_defaults)
    annot = self.annotations_util.convert_function_annotations(
        state.node, raw_annotations)
    return state, pos_defaults, kw_defaults, annot, free_vars

  def _get_extra_function_args_3_6(self, state, arg):
    """Get function annotations and defaults from the stack (Python3.6+)."""
    free_vars = None
    pos_defaults = ()
    kw_defaults = {}
    annot = {}
    if arg & loadmarshal.MAKE_FUNCTION_HAS_FREE_VARS:
      state, free_vars = state.pop()
    if arg & loadmarshal.MAKE_FUNCTION_HAS_ANNOTATIONS:
      state, packed_annot = state.pop()
      annot = abstract_utils.get_atomic_python_constant(packed_annot, dict)
      for k in annot.keys():
        annot[k] = self.annotations_util.convert_function_type_annotation(
            k, annot[k])
    if arg & loadmarshal.MAKE_FUNCTION_HAS_KW_DEFAULTS:
      state, packed_kw_def = state.pop()
      kw_defaults = abstract_utils.get_atomic_python_constant(
          packed_kw_def, dict)
    if arg & loadmarshal.MAKE_FUNCTION_HAS_POS_DEFAULTS:
      state, packed_pos_def = state.pop()
      pos_defaults = abstract_utils.get_atomic_python_constant(
          packed_pos_def, tuple)
    annot = self.annotations_util.convert_annotations_list(
        state.node, annot.items())
    return state, pos_defaults, kw_defaults, annot, free_vars

  def _process_function_type_comment(self, node, op, func):
    """Modifies annotations from a function type comment.

    Checks if a type comment is present for the function.  If so, the type
    comment is used to populate annotations.  It is an error to have
    a type comment when annotations is not empty.

    Args:
      node: The current node.
      op: An opcode (used to determine filename and line number).
      func: An abstract.InterpreterFunction.
    """
    if not op.annotation:
      return

    comment, lineno = op.annotation

    # It is an error to use a type comment on an annotated function.
    if func.signature.annotations:
      self.errorlog.redundant_function_type_comment(op.code.co_filename, lineno)
      return

    # Parse the comment, use a fake Opcode that is similar to the original
    # opcode except that it is set to the line number of the type comment.
    # This ensures that errors are printed with an accurate line number.
    fake_stack = self.simple_stack(op.at_line(lineno))
    m = _FUNCTION_TYPE_COMMENT_RE.match(comment)
    if not m:
      self.errorlog.invalid_function_type_comment(fake_stack, comment)
      return
    args, return_type = m.groups()

    if args != "...":
      annot = args.strip()
      try:
        self.annotations_util.eval_multi_arg_annotation(
            node, func, annot, fake_stack)
      except abstract_utils.ConversionError:
        self.errorlog.invalid_function_type_comment(
            fake_stack, annot, details="Must be constant.")

    ret = self.convert.build_string(None, return_type)
    func.signature.set_annotation(
        "return", self.annotations_util.extract_annotation(
            node, ret, "return", fake_stack))

  def byte_MAKE_FUNCTION(self, state, op):
    """Create a function and push it onto the stack."""
    if self.PY2:
      name = None
    else:
      assert self.PY3
      state, name_var = state.pop()
      name = abstract_utils.get_atomic_python_constant(name_var)
    state, code = state.pop()
    if self.python_version >= (3, 6):
      get_args = self._get_extra_function_args_3_6
    else:
      get_args = self._get_extra_function_args
    state, defaults, kw_defaults, annot, free_vars = get_args(state, op.arg)
    # TODO(dbaum): Add support for per-arg type comments.
    # TODO(dbaum): Add support for variable type comments.
    globs = self.get_globals_dict()
    fn = self._make_function(name, state.node, code, globs, defaults,
                             kw_defaults, annotations=annot, closure=free_vars)
    if op.line in self.director.decorators:
      fn.data[0].is_decorated = True
    self._process_function_type_comment(state.node, op, fn.data[0])
    self.trace_opcode(op, name, fn)
    self.trace_functiondef(fn)
    return state.push(fn)

  def byte_MAKE_CLOSURE(self, state, op):
    """Make a function that binds local variables."""
    if self.PY2:
      # The py3 docs don't mention this change.
      name = None
    else:
      assert self.PY3
      state, name_var = state.pop()
      name = abstract_utils.get_atomic_python_constant(name_var)
    state, (closure, code) = state.popn(2)
    state, defaults, kw_defaults, annot, _ = (
        self._get_extra_function_args(state, op.arg))
    globs = self.get_globals_dict()
    fn = self._make_function(name, state.node, code, globs, defaults,
                             kw_defaults, annotations=annot, closure=closure)
    self.trace_functiondef(fn)
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

  def byte_CALL_FUNCTION_EX(self, state, op):
    """Call a function."""
    if op.arg & loadmarshal.CALL_FUNCTION_EX_HAS_KWARGS:
      state, starstarargs = state.pop()
    else:
      starstarargs = None
    state, starargs = state.pop()
    state, fn = state.pop()
    # TODO(mdemello): fix function.Args() to properly init namedargs,
    # and remove this.
    namedargs = abstract.Dict(self)
    state, ret = self.call_function_with_state(
        state, fn, (), namedargs=namedargs, starargs=starargs,
        starstarargs=starstarargs)
    return state.push(ret)

  def byte_YIELD_VALUE(self, state, op):
    """Yield a value from a generator."""
    state, ret = state.pop()
    value = self.frame.yield_variable.AssignToNewVariable(state.node)
    value.PasteVariable(ret, state.node)
    self.frame.yield_variable = value
    if self.frame.check_return:
      ret_type = self.frame.allowed_returns
      self._check_return(state.node, ret,
                         ret_type.get_formal_type_parameter(abstract_utils.T))
      _, send_var = self.init_class(
          state.node,
          ret_type.get_formal_type_parameter(abstract_utils.T2))
      return state.push(send_var)
    return state.push(self.new_unsolvable(state.node))

  def byte_IMPORT_NAME(self, state, op):
    """Import a single module."""
    full_name = self.frame.f_code.co_names[op.arg]
    # The identifiers in the (unused) fromlist are repeated in IMPORT_FROM.
    state, (level_var, fromlist) = state.popn(2)
    if op.line in self.director.ignore:
      # "import name  # type: ignore"
      self.trace_opcode(op, full_name, None)
      return state.push(self.new_unsolvable(state.node))
    # The IMPORT_NAME for an "import a.b.c" will push the module "a".
    # However, for "from a.b.c import Foo" it'll push the module "a.b.c". Those
    # two cases are distinguished by whether fromlist is None or not.
    if self._var_is_none(fromlist):
      name = full_name.split(".", 1)[0]  # "a.b.c" -> "a"
    else:
      name = full_name
    level = abstract_utils.get_atomic_python_constant(level_var)
    module = self.import_module(name, full_name, level)
    if module is None:
      log.warning("Couldn't find module %r", name)
      self.errorlog.import_error(self.frames, name)
      module = self.convert.unsolvable
    mod = module.to_variable(state.node)
    self.trace_opcode(op, full_name, mod)
    return state.push(mod)

  def byte_IMPORT_FROM(self, state, op):
    """IMPORT_FROM is mostly like LOAD_ATTR but doesn't pop the container."""
    name = self.frame.f_code.co_names[op.arg]
    if op.line in self.director.ignore:
      # "from x import y  # type: ignore"
      # TODO(mdemello): Should we add some sort of signal data to indicate that
      # this should be treated as resolvable even though there is no module?
      self.trace_opcode(op, name, None)
      return state.push(self.new_unsolvable(state.node))
    module = state.top()
    state, attr = self.load_attr_noerror(state, module, name)
    if attr is None:
      full_name = module.data[0].name + "." + name
      self.errorlog.import_error(self.frames, full_name)
      attr = self.new_unsolvable(state.node)
    self.trace_opcode(op, name, attr)
    return state.push(attr)

  def byte_EXEC_STMT(self, state, op):
    state, (unused_stmt, unused_globs, unused_locs) = state.popn(3)
    log.warning("Encountered 'exec' statement. 'exec' is unsupported.")
    return state

  def byte_BUILD_CLASS(self, state, op):
    state, (name, _bases, members) = state.popn(3)
    bases = list(abstract_utils.get_atomic_python_constant(_bases))
    is_decorated = op.line in self.director.decorators
    node, cls = self.make_class(state.node, name, bases, members, None,
                                is_decorated=is_decorated)
    self.trace_classdef(cls)
    return state.change_cfg_node(node).push(cls)

  def byte_LOAD_BUILD_CLASS(self, state, op):
    # New in py3
    cls = abstract.BuildClass(self).to_variable(state.node)
    if op.line in self.director.decorators:
      # Will be copied into the abstract.InterpreterClass
      cls.data[0].is_decorated = True
    self.trace_opcode(op, "", cls)
    return state.push(cls)

  def byte_STORE_LOCALS(self, state, op):
    state, locals_dict = state.pop()
    self.frame.f_locals = abstract_utils.get_atomic_value(locals_dict)
    return state

  def byte_END_FINALLY(self, state, op):
    """Implementation of the END_FINALLY opcode."""
    state, exc = state.pop()
    if self._var_is_none(exc):
      return state
    else:
      log.info("Popping exception %r", exc)
      state = state.pop_and_discard()
      state = state.pop_and_discard()
      # If a pending exception makes it all the way out of an "except" block,
      # no handler matched, hence Python re-raises the exception.
      return state.set_why("reraise")

  def _check_return(self, node, actual, formal):
    return False  # overridden in analyze.py

  def _set_frame_return(self, node, frame, var):
    if frame.allowed_returns is not None:
      _, retvar = self.init_class(node, frame.allowed_returns)
    else:
      retvar = var
    frame.return_variable.PasteVariable(retvar, node)

  def byte_RETURN_VALUE(self, state, op):
    """Get and check the return value."""
    state, var = state.pop()
    if self.frame.check_return:
      if self.frame.f_code.has_generator():
        ret_type = self.frame.allowed_returns
        self._check_return(state.node, var,
                           ret_type.get_formal_type_parameter(abstract_utils.V))
      elif not self.frame.f_code.has_async_generator():
        self._check_return(state.node, var, self.frame.allowed_returns)
    self._set_frame_return(state.node, self.frame, var)
    return state.set_why("return")

  def byte_IMPORT_STAR(self, state, op):
    """Pops a module and stores all its contents in locals()."""
    # TODO(kramm): this doesn't use __all__ properly.
    state, mod_var = state.pop()
    mod = abstract_utils.get_atomic_value(mod_var)
    # TODO(rechen): Is mod ever an unknown?
    if isinstance(mod, (abstract.Unknown, abstract.Unsolvable)):
      self.has_unknown_wildcard_imports = True
      return state
    log.info("%r", mod)
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

  def byte_SETUP_ANNOTATIONS(self, state, op):
    """Sets up variable annotations in locals()."""
    annotations = abstract.AnnotationsDict(self).to_variable(state.node)
    return self.store_local(state, "__annotations__", annotations)

  def _record_annotation(self, node, op, name, typ):
    # Annotations in self.director are handled by _apply_annotation.
    if self.frame.current_opcode.line not in self.director.annotations:
      self._record_local(node, op, name, typ)

  def byte_STORE_ANNOTATION(self, state, op):
    """Implementation of the STORE_ANNOTATION opcode."""
    state, annotations_var = self.load_local(state, "__annotations__")
    name = self.frame.f_code.co_names[op.arg]
    state, value = state.pop()
    typ = self.annotations_util.extract_annotation(
        state.node, value, name, self.simple_stack(), is_var=True)
    self._record_annotation(state.node, op, name, typ)
    key = self.convert.primitive_class_instances[str]
    state = self.store_subscr(
        state, annotations_var, key.to_variable(state.node), value)
    return self.store_local(state, "__annotations__", annotations_var)

  def byte_GET_YIELD_FROM_ITER(self, state, op):
    # TODO(mdemello): We should check if TOS is a generator iterator or
    # coroutine first, and do nothing if it is, else call GET_ITER
    return self.byte_GET_ITER(state, op)

  def _pop_and_unpack_list(self, state, count):
    """Pop count iterables off the stack and concatenate."""
    state, iterables = state.popn(count)
    elements = []
    for var in iterables:
      try:
        itr = abstract_utils.get_atomic_python_constant(
            var, collections.Iterable)
      except abstract_utils.ConversionError:
        # TODO(rechen): The assumption that any abstract iterable unpacks to
        # exactly one element is highly dubious.
        elements.append(self.new_unsolvable(self.root_cfg_node))
      else:
        # Some iterable constants (e.g., tuples) already contain variables,
        # whereas others (e.g., strings) need to be wrapped.
        elements.extend(v if isinstance(v, cfg.Variable)  # pylint: disable=g-long-ternary
                        else self.convert.constant_to_var(v) for v in itr)
    return state, elements

  def byte_BUILD_LIST_UNPACK(self, state, op):
    state, ret = self._pop_and_unpack_list(state, op.arg)
    ret = self.convert.build_list(state.node, ret)
    return state.push(ret)

  def _build_map_unpack(self, state, arg_list):
    """Merge a list of kw dicts into a single dict."""
    args = abstract.Dict(self)
    for arg in arg_list:
      for data in arg.data:
        args.update(state.node, data)
    args = args.to_variable(state.node)
    return args

  def byte_BUILD_MAP_UNPACK(self, state, op):
    state, maps = state.popn(op.arg)
    args = self._build_map_unpack(state, maps)
    return state.push(args)

  def byte_BUILD_MAP_UNPACK_WITH_CALL(self, state, op):
    if self.python_version >= (3, 6):
      state, maps = state.popn(op.arg)
    else:
      state, maps = state.popn(op.arg & 0xff)
    args = self._build_map_unpack(state, maps)
    return state.push(args)

  def byte_BUILD_TUPLE_UNPACK(self, state, op):
    state, ret = self._pop_and_unpack_list(state, op.arg)
    return state.push(self.convert.build_tuple(state.node, ret))

  def byte_BUILD_TUPLE_UNPACK_WITH_CALL(self, state, op):
    return self.byte_BUILD_TUPLE_UNPACK(state, op)

  def byte_BUILD_SET_UNPACK(self, state, op):
    state, ret = self._pop_and_unpack_list(state, op.arg)
    return state.push(self.convert.build_set(state.node, ret))

  def byte_SETUP_ASYNC_WITH(self, state, op):
    state, res = state.pop()
    level = len(state.data_stack)
    state = self.push_block(state, "finally", op, op.target, level)
    return state.push(res)

  def byte_FORMAT_VALUE(self, state, op):
    if op.arg & loadmarshal.FVS_MASK:
      state = state.pop_and_discard()
    # FORMAT_VALUE pops, formats and pushes back a string, so we just need to
    # push a new string onto the stack.
    state = state.pop_and_discard()
    ret = abstract.Instance(self.convert.str_type, self)
    return state.push(ret.to_variable(state.node))

  def byte_BUILD_CONST_KEY_MAP(self, state, op):
    state, keys = state.pop()
    keys = abstract_utils.get_atomic_python_constant(keys, tuple)
    the_map = self.convert.build_map(state.node)
    assert len(keys) == op.arg
    for key in reversed(keys):
      state, val = state.pop()
      state = self.store_subscr(state, the_map, key, val)
    return state.push(the_map)

  def byte_BUILD_STRING(self, state, op):
    # TODO(mdemello): Test this.
    state, _ = state.popn(op.arg)
    ret = abstract.Instance(self.convert.str_type, self)
    return state.push(ret.to_variable(state.node))

  def byte_GET_AITER(self, state, op):
    """Implementation of the GET_AITER opcode."""
    state, obj = state.pop()
    state, itr = self._get_aiter(state, obj)
    if self.python_version < (3, 5):
      if not self._check_return(state.node, itr, self.convert.awaitable_type):
        itr = self.new_unsolvable(state.node)
    # Push the iterator onto the stack and return.
    state = state.push(itr)
    return state

  def byte_GET_ANEXT(self, state, op):
    """Implementation of the GET_ANEXT opcode."""
    state, anext = self.load_attr(state, state.top(), "__anext__")
    state, ret = self.call_function_with_state(state, anext, ())
    if not self._check_return(state.node, ret, self.convert.awaitable_type):
      ret = self.new_unsolvable(state.node)
    return state.push(ret)

  def byte_BEFORE_ASYNC_WITH(self, state, op):
    """Implementation of the BEFORE_ASYNC_WITH opcode."""
    # Pop a context manager and push its `__aexit__` and `__aenter__()`.
    state, ctxmgr = state.pop()
    state, aexit_method = self.load_attr(state, ctxmgr, "__aexit__")
    state = state.push(aexit_method)
    state, aenter_method = self.load_attr(state, ctxmgr, "__aenter__")
    state, ctxmgr_obj = self.call_function_with_state(state, aenter_method, ())
    return state.push(ctxmgr_obj)

  def _to_coroutine(self, state, obj, top=True):
    """Convert any awaitables and generators in obj to coroutines.

    Implements the GET_AWAITABLE opcode, which returns obj unchanged if it is a
    coroutine or generator and otherwise resolves obj.__await__
    (https://docs.python.org/3/library/dis.html#opcode-GET_AWAITABLE). So that
    we don't have to handle awaitable generators specially, our implementation
    converts generators to coroutines.

    Args:
      state: The current state.
      obj: The object, a cfg.Variable.
      top: Whether this is the top-level recursive call, to prevent incorrectly
        recursing into the result of obj.__await__.

    Returns:
      A tuple of the state and a cfg.Variable of coroutines.
    """
    bad_bindings = []
    for b in obj.bindings:
      if self.matcher.match_var_against_type(
          obj, self.convert.coroutine_type, {}, state.node, {obj: b}) is None:
        bad_bindings.append(b)
    if not bad_bindings:  # there are no non-coroutines
      return state, obj
    ret = self.program.NewVariable()
    for b in obj.bindings:
      state = self._binding_to_coroutine(state, b, bad_bindings, ret, top)
    return state, ret

  def _binding_to_coroutine(self, state, b, bad_bindings, ret, top):
    """Helper for _to_coroutine.

    Args:
      state: The current state.
      b: A cfg.Binding.
      bad_bindings: Bindings that are not coroutines.
      ret: A return variable that this helper will add to.
      top: Whether this is the top-level recursive call.

    Returns:
      The state.
    """
    if b not in bad_bindings:  # this is already a coroutine
      ret.PasteBinding(b)
      return state
    if self.matcher.match_var_against_type(
        b.variable, self.convert.generator_type, {}, state.node, {b.variable: b}
    ) is not None:
      # This is a generator; convert it to a coroutine. This conversion is
      # necessary even though generator-based coroutines convert their return
      # values themselves because __await__ can return a generator.
      ret_param = b.data.get_instance_type_parameter(abstract_utils.V)
      coroutine = abstract.Coroutine(self, ret_param, state.node)
      ret.AddBinding(coroutine, [b], state.node)
      return state
    # This is neither a coroutine or a generator; call __await__.
    if not top:  # we've already called __await__
      ret.PasteBinding(b)
      return state
    _, await_method = self.attribute_handler.get_attribute(
        state.node, b.data, "__await__", b)
    if await_method is None or not await_method.bindings:
      # We don't need to log an error here; byte_GET_AWAITABLE will check
      # that the final result is awaitable.
      ret.PasteBinding(b)
      return state
    state, await_obj = self.call_function_with_state(state, await_method, ())
    state, subret = self._to_coroutine(state, await_obj, top=False)
    ret.PasteVariable(subret)
    return state

  def byte_GET_AWAITABLE(self, state, op):
    """Implementation of the GET_AWAITABLE opcode."""
    state, obj = state.pop()
    state, ret = self._to_coroutine(state, obj)
    if not self._check_return(state.node, ret, self.convert.awaitable_type):
      ret = self.new_unsolvable(state.node)
    return state.push(ret)

  def byte_YIELD_FROM(self, state, op):
    """Implementation of the YIELD_FROM opcode."""
    state, unused_none_var = state.pop()
    state, var = state.pop()
    result = self.program.NewVariable()
    for b in var.bindings:
      val = b.data
      if isinstance(val, (abstract.Generator,
                          abstract.Coroutine, abstract.Unsolvable)):
        ret_var = val.get_instance_type_parameter(abstract_utils.V)
        result.PasteVariable(ret_var, state.node, {b})
      elif (isinstance(val, abstract.Instance)
            and isinstance(val.cls,
                           (abstract.ParameterizedClass, abstract.PyTDClass))
            and val.cls.full_name in ("typing.Awaitable",
                                      "__builtin__.coroutine",
                                      "__builtin__.generator")):
        if val.cls.full_name == "typing.Awaitable":
          ret_var = val.get_instance_type_parameter(abstract_utils.T)
        else:
          ret_var = val.get_instance_type_parameter(abstract_utils.V)
        result.PasteVariable(ret_var, state.node, {b})
      else:
        result.AddBinding(val, {b}, state.node)
    return state.push(result)

  def byte_LOAD_METHOD(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    state, self_obj = state.pop()
    state, result = self.load_attr(state, self_obj, name)
    # https://docs.python.org/3/library/dis.html#opcode-LOAD_METHOD says that
    # this opcode should push two values onto the stack: either the unbound
    # method and its `self` or NULL and the bound method. However, pushing only
    # the bound method and modifying CALL_METHOD accordingly works in all cases
    # we've tested.
    return state.push(result)

  def byte_CALL_METHOD(self, state, op):
    state, args = state.popn(op.arg)
    state, func = state.pop()
    state, result = self.call_function_with_state(state, func, args)
    return state.push(result)
